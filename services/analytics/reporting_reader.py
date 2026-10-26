"""Restricted PostgreSQL reader for optional registered reporting queries.

Dashboard rows select a reviewed source-controlled query ID, not SQL text. A
contract executes as the dedicated role provisioned by
``services.migration.analytics_role`` and may read only the curated reporting
views. The ordinary application connection must never be used for the query.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

import psycopg2

REPORTING_SCHEMA = "kokonut_reporting"
REPORTING_VIEWS = frozenset(
    {
        "v_farm_summary",
        "v_verified_metric_values",
        "v_attestation_summary",
    }
)
QUERY_TIMEOUT_MS = 15_000
LOCK_TIMEOUT_MS = 3_000
_PLACEHOLDER_SECRET = re.compile(r"^(replace-with|your[_-]|change[_-]me|todo|none|null)", re.IGNORECASE)


@dataclass(frozen=True)
class ReportingQuery:
    """A reviewed, fixed SQL query exposed to the saved-dashboard runner."""

    sql: str
    scope: str = "exact_location"


# Dashboard data selects a query contract by stable ID. SQL is source-controlled,
# its location predicate is fixed, and all report views already apply their own
# lifecycle/publication policy. Extend this registry only with reviewed output
# contracts; never derive SQL identifiers or clauses from dashboard rows.
REPORTING_QUERY_REGISTRY = MappingProxyType({
    "public_farm_summary_count": ReportingQuery(
        "SELECT count(*) FROM kokonut_reporting.v_farm_summary WHERE location_id = %s"
    ),
    "public_verified_metric_values_count": ReportingQuery(
        "SELECT count(*) FROM kokonut_reporting.v_verified_metric_values WHERE location_id = %s"
    ),
    "public_attestation_summary_count": ReportingQuery(
        "SELECT count(*) FROM kokonut_reporting.v_attestation_summary WHERE location_id = %s"
    ),
})


class ReportingReaderPolicyError(RuntimeError):
    """Raised when the configured login does not satisfy the reader contract."""


def open_reporting_connection():
    """Open a separate reader connection; never fall back to the app role."""
    analytics_user = os.environ.get("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro").strip()
    analytics_password = os.environ.get("KOKONUT_ANALYTICS_PASSWORD", "")
    runtime_user = os.environ.get("PG_USER", "kokonut")
    runtime_password = os.environ.get("PG_PASSWORD") or os.environ.get("POSTGRES_PASSWORD", "")

    if not analytics_user or analytics_user == runtime_user:
        raise ReportingReaderPolicyError("saved reporting queries require a dedicated analytics database role")
    if (
        len(analytics_password) < 24
        or _PLACEHOLDER_SECRET.match(analytics_password)
        or analytics_password == runtime_password
    ):
        raise ReportingReaderPolicyError(
            "saved reporting queries require the distinct provisioned analytics credential"
        )

    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ.get("PG_DB", "kokonut_intelligence"),
        user=analytics_user,
        password=analytics_password,
        connect_timeout=5,
        application_name="kokonut-saved-report-reader",
        options=(
            "-c default_transaction_read_only=on "
            "-c search_path=kokonut_reporting,pg_catalog "
            f"-c statement_timeout={QUERY_TIMEOUT_MS} "
            f"-c lock_timeout={LOCK_TIMEOUT_MS} "
            "-c idle_in_transaction_session_timeout=30000"
        ),
    )


def validate_reporting_connection(conn, *, expected_user: str) -> None:
    """Fail closed unless the live PostgreSQL ACL matches the reporting role."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT current_user, session_user,
                   r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication,
                   r.rolbypassrls, r.rolinherit,
                   has_schema_privilege(r.oid, 'public', 'CREATE'),
                   has_schema_privilege(r.oid, %s, 'CREATE'),
                   has_database_privilege(r.oid, current_database(), 'TEMP')
            FROM pg_roles r WHERE r.rolname = current_user
            """,
            (REPORTING_SCHEMA,),
        )
        identity = cur.fetchone()
        if identity != (expected_user, expected_user, *(False for _ in range(9))):
            raise ReportingReaderPolicyError(
                "saved reporting query login has unexpected identity or elevated privileges"
            )

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_auth_members
                WHERE member = (SELECT oid FROM pg_roles WHERE rolname = current_user)
            )
            """
        )
        if cur.fetchone()[0]:
            raise ReportingReaderPolicyError(
                "saved reporting query login must not inherit or assume another database role"
            )

        cur.execute(
            """
            SELECT n.nspname, c.relname,
                   EXISTS (
                       SELECT 1 FROM pg_depend d
                       WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                         AND d.refclassid = 'pg_extension'::regclass AND d.deptype = 'e'
                   ) AS extension_owned
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
              AND n.nspname NOT LIKE 'pg_temp_%'
              AND has_table_privilege(current_user, c.oid, 'SELECT')
            ORDER BY n.nspname, c.relname
            """
        )
        readable_relations = cur.fetchall()
        application_relations = {
            (schema, relation) for schema, relation, extension_owned in readable_relations if not extension_owned
        }
        expected_relations = {(REPORTING_SCHEMA, view) for view in REPORTING_VIEWS}
        if application_relations != expected_relations:
            raise ReportingReaderPolicyError(
                "saved reporting query login can read outside the approved reporting views"
            )

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
                  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND n.nspname NOT LIKE 'pg_toast%'
                  AND n.nspname NOT LIKE 'pg_temp_%'
                  AND NOT EXISTS (
                      SELECT 1 FROM pg_depend d
                      WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                        AND d.refclassid = 'pg_extension'::regclass AND d.deptype = 'e'
                  )
                  AND (
                      has_table_privilege(current_user, c.oid, 'INSERT') OR
                      has_table_privilege(current_user, c.oid, 'UPDATE') OR
                      has_table_privilege(current_user, c.oid, 'DELETE') OR
                      has_table_privilege(current_user, c.oid, 'TRUNCATE') OR
                      has_table_privilege(current_user, c.oid, 'REFERENCES') OR
                      has_table_privilege(current_user, c.oid, 'TRIGGER')
                  )
            )
            """
        )
        if cur.fetchone()[0]:
            raise ReportingReaderPolicyError("saved reporting query login has application write privileges")

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE p.prosecdef
                  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND has_function_privilege(current_user, p.oid, 'EXECUTE')
            )
            """
        )
        if cur.fetchone()[0]:
            raise ReportingReaderPolicyError(
                "saved reporting query login can execute an unreviewed security-definer function"
            )

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_database
                WHERE datallowconn
                  AND datname <> current_database()
                  AND has_database_privilege(current_user, oid, 'CONNECT')
            )
            """
        )
        if cur.fetchone()[0]:
            raise ReportingReaderPolicyError("saved reporting query login can connect to another database")


def resolve_registered_reporting_query(
    query_id: str,
    location_id: str | None,
) -> tuple[ReportingQuery, str]:
    """Validate a stable query ID and canonical exact-location scope without I/O."""
    contract = REPORTING_QUERY_REGISTRY.get(query_id) if isinstance(query_id, str) else None
    if contract is None:
        raise ValueError("dataset query ID is missing or not registered")
    if contract.scope != "exact_location" or location_id is None:
        raise ValueError("registered dataset query requires an exact location")
    try:
        parsed_location = location_id if isinstance(location_id, UUID) else UUID(location_id)
        canonical_location_id = str(parsed_location)
    except (TypeError, ValueError, AttributeError):
        raise ValueError("registered dataset query requires a valid location ID") from None
    return contract, canonical_location_id


def count_registered_reporting_rows(
    query_id: str,
    location_id: str | None,
    *,
    connection_factory=None,
) -> int:
    """Run one registered report count for exactly one canonical location."""
    contract, canonical_location_id = resolve_registered_reporting_query(query_id, location_id)

    factory = connection_factory or open_reporting_connection
    conn = factory()
    try:
        # Start every catalog-validation and saved-query statement in a
        # read-only transaction. The libpq default is also read-only, providing
        # protection if the query text contains transaction-control syntax.
        conn.set_session(readonly=True, autocommit=False)
        expected_user = os.environ.get("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro").strip()
        validate_reporting_connection(conn, expected_user=expected_user)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL search_path TO kokonut_reporting, pg_catalog")
            cur.execute(f"SET LOCAL statement_timeout = '{QUERY_TIMEOUT_MS}ms'")
            cur.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT_MS}ms'")
            cur.execute(contract.sql, (canonical_location_id,))
            row_count = cur.fetchone()[0]
        conn.commit()
        return int(row_count)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def safe_query_error(exc: Exception) -> str:
    """Return a stable error detail without echoing stored SQL or DB diagnostics."""
    if type(exc) is ReportingReaderPolicyError:
        # This exception carries only fixed policy messages authored here.
        return str(exc)
    sqlstate = getattr(exc, "pgcode", None)
    if sqlstate:
        return f"{type(exc).__name__} (SQLSTATE {sqlstate})"
    return type(exc).__name__
