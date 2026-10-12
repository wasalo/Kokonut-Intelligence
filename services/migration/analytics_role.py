"""Provision the optional read-only Kokonut reporting-source login.

Run this one-shot command only against a dedicated Kernel PostgreSQL instance.
It removes inherited PUBLIC database connections on that instance, then grants
the analytics login access to one database and the reviewed reporting views.
It is separate from schema migrations because it manages instance access policy.
"""

from __future__ import annotations

import json
import os
import re

import psycopg2
from psycopg2 import sql

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_PLACEHOLDER_SECRET = re.compile(r"^(replace-with|your[_-]|change[_-]me|todo|none|null)", re.IGNORECASE)
_REPORTING_SCHEMA = "kokonut_reporting"
_REPORTING_VIEWS = (
    "v_farm_summary",
    "v_verified_metric_values",
    "v_attestation_summary",
)
_PRIVATE_POLICY_TABLE = "metric_publication_policy"


def _role_identifier(value: str, label: str) -> sql.Identifier:
    if not _ROLE_NAME.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase PostgreSQL role name")
    return sql.Identifier(value)


def _validate_secret(value: str, *, label: str, other: str = "") -> None:
    if len(value) < 24 or _PLACEHOLDER_SECRET.match(value):
        raise ValueError(f"{label} must be a non-placeholder secret of at least 24 characters")
    if other and value == other:
        raise ValueError(f"{label} must differ from the database administrator credential")


def provision_analytics_role(
    conn,
    *,
    database: str,
    admin_user: str,
    admin_password: str,
    analytics_user: str,
    analytics_password: str,
    isolated_instance: bool,
) -> dict[str, object]:
    """Set the analytics login to an explicit, view-only target-database ACL."""
    analytics_ident = _role_identifier(analytics_user, "analytics_user")
    if admin_user == analytics_user:
        raise ValueError("analytics_user must differ from admin_user")
    if not admin_password:
        raise ValueError("admin password must be provided")
    _validate_secret(analytics_password, label="analytics password", other=admin_password)
    if not database or "\x00" in database:
        raise ValueError("database name is required")
    if not isolated_instance:
        raise ValueError("PUBLIC database access changes require a dedicated Kernel PostgreSQL instance")

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(), r.rolsuper FROM pg_roles r WHERE r.rolname = %s",
                (admin_user,),
            )
            admin_state = cur.fetchone()
            if not admin_state or admin_state != (database, True):
                raise RuntimeError("connect to the target database as its PostgreSQL superuser")

            cur.execute(
                "SELECT oid FROM pg_roles WHERE rolname = %s",
                (analytics_user,),
            )
            existing = cur.fetchone()
            if existing:
                role_oid = existing[0]
                cur.execute(
                    """
                    SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner = %s)
                        OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = %s
                                   AND nspname NOT LIKE 'pg_%%'
                                   AND nspname <> 'information_schema')
                        OR EXISTS (SELECT 1 FROM pg_database WHERE datdba = %s)
                    """,
                    (role_oid, role_oid, role_oid),
                )
                if cur.fetchone()[0]:
                    raise RuntimeError("analytics role owns database objects; review and transfer them first")
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE member = %s OR roleid = %s)",
                    (role_oid, role_oid),
                )
                if cur.fetchone()[0]:
                    raise RuntimeError("analytics role has role memberships; review them before provisioning")
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_default_acl d
                        CROSS JOIN LATERAL aclexplode(d.defaclacl) a
                        WHERE a.grantee = %s
                    )
                    """,
                    (role_oid,),
                )
                if cur.fetchone()[0]:
                    raise RuntimeError("analytics role appears in default privileges; review them first")
                cur.execute(
                    sql.SQL(
                        "ALTER ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                    ).format(analytics_ident),
                    (analytics_password,),
                )
            else:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                    ).format(analytics_ident),
                    (analytics_password,),
                )

            cur.execute("SELECT datname FROM pg_database WHERE datallowconn OR datname = 'template1'")
            database_names = sorted({row[0] for row in cur.fetchall()})
            if database not in database_names:
                raise RuntimeError("target database is not available for connection")
            for name in database_names:
                db_ident = sql.Identifier(name)
                cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(db_ident))
                cur.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(
                        db_ident, analytics_ident
                    )
                )
            cur.execute(
                sql.SQL("REVOKE TEMPORARY ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database))
            )
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), analytics_ident
            ))
            cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))

            cur.execute(
                """
                SELECT nspname FROM pg_namespace
                WHERE nspname <> 'information_schema'
                  AND nspname NOT LIKE 'pg_%%'
                ORDER BY nspname
                """
            )
            schemas = [row[0] for row in cur.fetchall()]
            for schema in schemas:
                schema_ident = sql.Identifier(schema)
                cur.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
                    schema_ident, analytics_ident
                ))
                cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {}").format(
                    schema_ident, analytics_ident
                ))
                cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {} FROM {}").format(
                    schema_ident, analytics_ident
                ))
                cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                    schema_ident, analytics_ident
                ))

            cur.execute(
                """
                SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
                """,
                (_REPORTING_SCHEMA, _PRIVATE_POLICY_TABLE),
            )
            policy = cur.fetchone()
            if not policy or policy[1] not in ("r", "p"):
                raise RuntimeError("curated metric publication policy table is unavailable")
            for view in _REPORTING_VIEWS:
                cur.execute(
                    """
                    SELECT c.relkind, pg_get_userbyid(c.relowner)
                    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = %s
                    """,
                    (_REPORTING_SCHEMA, view),
                )
                row = cur.fetchone()
                if not row or row[0] != "v" or row[1] != admin_user:
                    raise RuntimeError(f"reviewed reporting view is missing or has an unexpected owner: {view}")

            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(_REPORTING_SCHEMA), analytics_ident
            ))
            for view in _REPORTING_VIEWS:
                cur.execute(sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                    sql.Identifier(_REPORTING_SCHEMA), sql.Identifier(view), analytics_ident
                ))
            cur.execute(sql.SQL("ALTER ROLE {} SET search_path TO pg_catalog, {}").format(
                analytics_ident, sql.Identifier(_REPORTING_SCHEMA)
            ))

            cur.execute(
                """
                SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication,
                       r.rolbypassrls, r.rolinherit,
                       has_schema_privilege(r.oid, 'public', 'CREATE'),
                       has_schema_privilege(r.oid, %s, 'CREATE'),
                       has_database_privilege(r.oid, %s, 'TEMP')
                FROM pg_roles r WHERE r.rolname = %s
                """,
                (_REPORTING_SCHEMA, database, analytics_user),
            )
            attributes = cur.fetchone()
            if attributes != (False, False, False, False, False, False, False, False, False):
                raise RuntimeError("analytics role retains an administrative, DDL, or temporary privilege")

            cur.execute(
                """
                SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                FROM pg_database WHERE datallowconn OR datname = 'template1'
                ORDER BY datname
                """,
                (analytics_user,),
            )
            database_access = {name: allowed for name, allowed in cur.fetchall()}
            if database_access.get(database) is not True or any(
                allowed for name, allowed in database_access.items() if name != database
            ):
                raise RuntimeError("analytics role must connect only to its configured database")

            cur.execute(
                """
                SELECT count(*)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'kokonut_reporting' AND c.relkind = 'v'
                  AND c.relname = ANY(%s)
                  AND has_table_privilege(%s, c.oid, 'SELECT')
                """,
                (list(_REPORTING_VIEWS), analytics_user),
            )
            if cur.fetchone()[0] != len(_REPORTING_VIEWS):
                raise RuntimeError("analytics role cannot read every approved reporting view")
            cur.execute(
                "SELECT has_table_privilege(%s, %s, 'SELECT')",
                (analytics_user, f"{_REPORTING_SCHEMA}.{_PRIVATE_POLICY_TABLE}"),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("analytics role can read the private metric publication policy")

            cur.execute(
                """
                SELECT count(*)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                  AND has_table_privilege(%s, c.oid, 'SELECT')
                  AND NOT EXISTS (
                      SELECT 1 FROM pg_depend d
                      WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                        AND d.refclassid = 'pg_extension'::regclass AND d.deptype = 'e'
                  )
                """,
                (analytics_user,),
            )
            unreviewed_public_relations = cur.fetchone()[0]
            if unreviewed_public_relations:
                raise RuntimeError("analytics role can read unreviewed application relations in public")

            cur.execute(
                """
                SELECT count(*)
                FROM pg_depend d JOIN pg_class c ON d.classid = 'pg_class'::regclass AND d.objid = c.oid
                JOIN pg_extension e ON d.refclassid = 'pg_extension'::regclass AND d.refobjid = e.oid
                CROSS JOIN LATERAL aclexplode(coalesce(
                    c.relacl, acldefault(
                        CASE WHEN c.relkind = 'S' THEN 'S'::\"char\" ELSE 'r'::\"char\" END,
                        c.relowner
                    )
                )) a
                WHERE d.deptype = 'e' AND a.grantee = 0 AND a.privilege_type = 'SELECT'
                """
            )
            public_extension_relations = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM pg_depend d JOIN pg_class c ON d.classid = 'pg_class'::regclass AND d.objid = c.oid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_extension e ON d.refclassid = 'pg_extension'::regclass AND d.refobjid = e.oid
                CROSS JOIN LATERAL aclexplode(coalesce(
                    c.relacl, acldefault(
                        CASE WHEN c.relkind = 'S' THEN 'S'::\"char\" ELSE 'r'::\"char\" END,
                        c.relowner
                    )
                )) a
                WHERE d.deptype = 'e' AND a.grantee = 0 AND a.privilege_type = 'SELECT'
                  AND has_schema_privilege(%s, n.oid, 'USAGE')
                  AND has_table_privilege(%s, c.oid, 'SELECT')
                """,
                (analytics_user, analytics_user),
            )
            analytics_extension_relations = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM pg_depend d JOIN pg_proc p ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid
                JOIN pg_extension e ON d.refclassid = 'pg_extension'::regclass AND d.refobjid = e.oid
                CROSS JOIN LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                WHERE d.deptype = 'e' AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
                """
            )
            public_extension_functions = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM pg_depend d JOIN pg_proc p ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid
                JOIN pg_extension e ON d.refclassid = 'pg_extension'::regclass AND d.refobjid = e.oid
                CROSS JOIN LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                WHERE d.deptype = 'e' AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
                  AND p.prosecdef
                """
            )
            public_extension_security_definer = cur.fetchone()[0]
            if public_extension_security_definer:
                raise RuntimeError(
                    "PUBLIC can execute SECURITY DEFINER extension functions; review their access before provisioning"
                )
            cur.execute(
                """
                SELECT count(*)
                FROM pg_depend d JOIN pg_proc p ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid
                JOIN pg_namespace n ON n.oid = p.pronamespace
                JOIN pg_extension e ON d.refclassid = 'pg_extension'::regclass AND d.refobjid = e.oid
                CROSS JOIN LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                WHERE d.deptype = 'e' AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
                  AND has_schema_privilege(%s, n.oid, 'USAGE')
                  AND has_function_privilege(%s, p.oid, 'EXECUTE')
                """,
                (analytics_user, analytics_user),
            )
            analytics_extension_functions = cur.fetchone()[0]
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "status": "provisioned",
        "database": database,
        "analytics_user": analytics_user,
        "role_attributes": {
            "superuser": False,
            "createdb": False,
            "createrole": False,
            "replication": False,
            "bypassrls": False,
            "inherit": False,
        },
        "public_connect_revoked_from": database_names,
        "analytics_connect_grants": database_access,
        "approved_reporting_views": list(_REPORTING_VIEWS),
        "private_policy_table_select": False,
        "unreviewed_public_application_relations_readable": unreviewed_public_relations,
        "public_extension_metadata_relations_granted": public_extension_relations,
        "analytics_extension_metadata_relations_accessible": analytics_extension_relations,
        "public_execute_extension_functions_inherited": public_extension_functions,
        "analytics_extension_functions_executable": analytics_extension_functions,
        "public_executable_extension_security_definer_functions": public_extension_security_definer,
    }


def verify_analytics_login(
    *,
    host: str,
    port: int,
    database: str,
    analytics_user: str,
    analytics_password: str,
    other_databases: list[str],
) -> dict[str, object]:
    """Connect as the source login and verify view reads plus key denials."""
    conn = psycopg2.connect(
        host=host, port=port, dbname=database, user=analytics_user,
        password=analytics_password, connect_timeout=10,
    )
    try:
        conn.autocommit = False
        view_counts: dict[str, int] = {}
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, session_user")
            if cur.fetchone() != (analytics_user, analytics_user):
                raise RuntimeError("analytics login connected with an unexpected identity")
            for view in _REPORTING_VIEWS:
                cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(_REPORTING_SCHEMA), sql.Identifier(view)
                ))
                view_counts[view] = cur.fetchone()[0]

            denied = []
            for label, statement in (
                ("application migration ledger", "SELECT * FROM public.schema_migration LIMIT 0"),
                (
                    "private metric publication policy",
                    "SELECT * FROM kokonut_reporting.metric_publication_policy LIMIT 0",
                ),
                (
                    "reporting schema DDL",
                    "CREATE TABLE kokonut_reporting.kernel_analytics_role_probe (id integer)",
                ),
                ("public schema DDL", "CREATE TABLE public.kernel_analytics_role_probe (id integer)"),
                ("temporary table creation", "CREATE TEMP TABLE kernel_analytics_temp_probe (id integer)"),
            ):
                cur.execute("SAVEPOINT analytics_acl_probe")
                try:
                    cur.execute(statement)
                except psycopg2.errors.InsufficientPrivilege:
                    cur.execute("ROLLBACK TO SAVEPOINT analytics_acl_probe")
                    denied.append(label)
                else:
                    cur.execute("ROLLBACK TO SAVEPOINT analytics_acl_probe")
                    raise RuntimeError(f"analytics login unexpectedly allowed: {label}")
                finally:
                    cur.execute("RELEASE SAVEPOINT analytics_acl_probe")
        conn.rollback()
    finally:
        conn.close()

    cross_database_denials = []
    for other_database in other_databases:
        if other_database == database:
            continue
        try:
            probe = psycopg2.connect(
                host=host, port=port, dbname=other_database, user=analytics_user,
                password=analytics_password, connect_timeout=5,
            )
        except psycopg2.Error as exc:
            message = str(exc).lower()
            expected_denial = (
                getattr(exc, "pgcode", None) == "42501"
                or (
                    "permission denied for database" in message
                    and "connect privilege" in message
                )
            )
            if not expected_denial:
                raise
            cross_database_denials.append(other_database)
        else:
            probe.close()
            raise RuntimeError(f"analytics login unexpectedly connected to {other_database}")

    return {
        "status": "verified",
        "analytics_user": analytics_user,
        "view_row_counts": view_counts,
        "denied_operations": denied,
        "cross_database_connect_denied": cross_database_denials,
    }


def main() -> int:
    database = os.environ.get("PG_DB", "kokonut_intelligence")
    host = os.environ.get("PG_HOST", "database")
    port = int(os.environ.get("PG_PORT", "5432"))
    admin_user = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
    admin_password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    analytics_user = os.environ.get("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro")
    analytics_password = os.environ.get("KOKONUT_ANALYTICS_PASSWORD", "")
    isolated_instance = os.environ.get("KOKONUT_ANALYTICS_ROLE_DEDICATED_INSTANCE") == "true"
    if not admin_password or not analytics_password:
        raise SystemExit("admin and analytics credentials must be provided through the environment")

    conn = psycopg2.connect(
        host=host, port=port, dbname=database, user=admin_user,
        password=admin_password, connect_timeout=10,
    )
    try:
        provisioned = provision_analytics_role(
            conn,
            database=database,
            admin_user=admin_user,
            admin_password=admin_password,
            analytics_user=analytics_user,
            analytics_password=analytics_password,
            isolated_instance=isolated_instance,
        )
    finally:
        conn.close()

    verified = verify_analytics_login(
        host=host,
        port=port,
        database=database,
        analytics_user=analytics_user,
        analytics_password=analytics_password,
        other_databases=list(provisioned["public_connect_revoked_from"]),
    )
    print(json.dumps({**provisioned, "login_verification": verified}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
