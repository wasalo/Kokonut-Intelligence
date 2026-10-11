"""Verify optional consumer database-role boundaries on a disposable restore.

Only the isolated restore is changed. Directus receives DML on its managed
schemas; Metabase owns only its metadata database; the analytics login can read
the three reviewed reporting views and no application tables. Reporting logic
is exercised with transaction-rolled-back synthetic rows. No restored row
payloads or passwords are emitted.
"""

from __future__ import annotations

import json
import os
import uuid

import psycopg2
from psycopg2 import sql


HOST = os.environ.get("PG_HOST", "database")
PORT = int(os.environ.get("PG_PORT", "5432"))
ADMIN_USER = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
ADMIN_PASSWORD = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
APP_DATABASE = os.environ.get("PG_DB", "kokonut_intelligence")
METADATA_DATABASE = "metabase"
DIRECTUS_ROLE = "kokonut_directus_runtime"
METABASE_ROLE = "kokonut_metabase_app"
ANALYTICS_ROLE = "kokonut_analytics_ro"
REPORTING_SCHEMA = "kokonut_reporting"
REPORTING_VIEWS = (
    "v_farm_summary",
    "v_verified_metric_values",
    "v_attestation_summary",
)


def connect(user: str, password: str, database: str):
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=database,
        user=user,
        password=password,
        connect_timeout=10,
    )


def role_ident(name: str) -> sql.Identifier:
    if not name.replace("_", "").isalnum() or not name[0].islower():
        raise ValueError("unexpected fixture role name")
    return sql.Identifier(name)


def ensure_login_role(conn, name: str, password: str) -> None:
    if len(password) < 24 or password == ADMIN_PASSWORD:
        raise ValueError("fixture role passwords must be distinct synthetic secrets of at least 24 characters")
    ident = role_ident(name)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
        if cur.fetchone():
            cur.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN PASSWORD %s NOINHERIT NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                ).format(ident),
                (password,),
            )
        else:
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN PASSWORD %s NOINHERIT NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                ).format(ident),
                (password,),
            )


def grant_database_only(admin, database: str, roles: tuple[str, ...]) -> list[str]:
    with admin.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database WHERE datallowconn OR datname = 'template1'")
        databases = sorted({row[0] for row in cur.fetchall()})
        for name in databases:
            db_ident = sql.Identifier(name)
            cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(db_ident))
            for role in roles:
                cur.execute(
                    sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(db_ident, role_ident(role))
                )
        for role in roles:
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), role_ident(role)
                )
            )
    return databases


def require_denied(conn, statement: str, parameters=None,
                   expected_codes: tuple[str, ...] = ("42501",)) -> None:
    old_autocommit = conn.autocommit
    if statement.lstrip().upper().startswith("CREATE DATABASE"):
        conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(statement, parameters)
    except psycopg2.Error as exc:
        if exc.pgcode not in expected_codes:
            raise AssertionError("privileged operation failed for an unexpected reason") from exc
        if not conn.autocommit:
            conn.rollback()
    else:
        if not conn.autocommit:
            conn.rollback()
        raise AssertionError("a denied operation unexpectedly succeeded")
    finally:
        if statement.lstrip().upper().startswith("CREATE DATABASE"):
            conn.autocommit = old_autocommit


def require_database_denied(user: str, password: str, database: str) -> None:
    try:
        denied = connect(user, password, database)
    except psycopg2.OperationalError as exc:
        if "permission denied" not in str(exc).lower():
            raise AssertionError("cross-database connection failed for an unexpected reason") from exc
        return
    denied.close()
    raise AssertionError(f"{user} unexpectedly connected to {database}")


def provision_reporting_view_grants(admin) -> list[str]:
    """Grant only the versioned reporting surface to the source login."""
    with admin.cursor() as cur:
        cur.execute("SELECT to_regnamespace(%s)", (REPORTING_SCHEMA,))
        if cur.fetchone()[0] is None:
            raise AssertionError("reporting schema is missing; apply its tracked migration first")
        cur.execute(
            "SELECT c.relname, pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND c.relname = ANY(%s) ORDER BY c.relname",
            (REPORTING_SCHEMA, list(REPORTING_VIEWS)),
        )
        owners = cur.fetchall()
        if {name for name, _owner in owners} != set(REPORTING_VIEWS):
            raise AssertionError("one or more curated reporting views are missing")
        if any(owner == ANALYTICS_ROLE for _name, owner in owners):
            raise AssertionError("analytics source role must not own reporting views")

        role = role_ident(ANALYTICS_ROLE)
        schema = sql.Identifier(REPORTING_SCHEMA)
        cur.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(schema, role))
        cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(schema, role))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, role))
        for view_name in REPORTING_VIEWS:
            cur.execute(
                sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                    schema, sql.Identifier(view_name), role
                )
            )
        cur.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND has_table_privilege(%s, c.oid, 'SELECT') "
            "AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname",
            (REPORTING_SCHEMA, ANALYTICS_ROLE),
        )
        readable = [row[0] for row in cur.fetchall()]
        if readable != sorted(REPORTING_VIEWS):
            raise AssertionError("analytics role does not have exactly the approved view grants")
        cur.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND has_table_privilege(%s, c.oid, 'INSERT') "
            "AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname",
            (REPORTING_SCHEMA, ANALYTICS_ROLE),
        )
        if cur.fetchall():
            raise AssertionError("analytics role unexpectedly has INSERT on a reporting relation")
    admin.commit()
    return readable


def insert_reporting_fixture_registry(cur, registry_id: str, farm_id: str | None,
                                      location_id: str, registry_slug: str) -> None:
    cur.execute(
        "INSERT INTO public.farm_registry_record "
        "(id, farm_id, location_id, registry_slug, project_date, forecasted_budget, "
        "land_size_m2, project_location, source_of_funding, governance_mechanism, "
        "token_allocation, public_goods_allocation_pct, project_summary, local_problem, "
        "proposed_solution, status) "
        "VALUES (%s, %s, %s, %s, DATE '2999-01-01', 0, 10000, '{}'::jsonb, "
        "'isolated fixture', 'cooperative', 'isolated fixture', 10, "
        "'isolated fixture', 'isolated fixture', 'isolated fixture', 'published')",
        (registry_id, farm_id, location_id, registry_slug),
    )


def insert_reporting_fixture_farm(cur, farm_id: str, location_id: str, fixture_id: str,
                                 index: int, area: float, unit: str) -> None:
    cur.execute(
        "INSERT INTO public.farm "
        "(id, location_id, name, slug, total_area, area_unit, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'active')",
        (
            farm_id,
            location_id,
            f"Kernel reporting fixture {fixture_id} {index}",
            f"kernel-report-{fixture_id}-{index}",
            area,
            unit,
        ),
    )


def insert_reporting_fixture_plot(cur, plot_id: str, farm_id: str,
                                 fixture_id: str, index: int) -> None:
    cur.execute(
        "INSERT INTO public.plot (id, farm_id, name, slug, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (
            plot_id,
            farm_id,
            f"Kernel reporting fixture plot {fixture_id} {index}",
            f"kernel-report-plot-{fixture_id}-{index}",
        ),
    )


def exercise_reporting_views(admin) -> dict[str, str]:
    """Check reporting policy with synthetic rows in a transaction rolled back."""
    fixture_id = uuid.uuid4().hex
    location_id = str(uuid.uuid4())
    farm_specific_location_id = str(uuid.uuid4())
    metric_id = str(uuid.uuid4())
    attestation_schema_id = str(uuid.uuid4())
    attestation_ids = [str(uuid.uuid4()) for _ in range(4)]
    farm_ids = [str(uuid.uuid4()) for _ in range(5)]
    registry_ids = [str(uuid.uuid4()) for _ in range(3)]
    plot_ids = [str(uuid.uuid4()) for _ in range(5)]
    metric_value_id = str(uuid.uuid4())
    reviewer_id = str(uuid.uuid4())
    reviewer_id_2 = str(uuid.uuid4())
    metric_key = f"kernel_reporting_fixture_{fixture_id}"
    method = f"kernel-reporting-fixture-{fixture_id}"
    metric_period_start = "2999-01-01"
    metric_period_end = "2999-01-31"

    admin.rollback()
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.location (id, name, slug, country, region, status) "
                "VALUES (%s, %s, %s, 'Test', 'Test', 'active'), "
                "(%s, %s, %s, 'Test', 'Test', 'active')",
                (
                    location_id,
                    f"Kernel reporting fixture {fixture_id}",
                    f"kernel-report-location-{fixture_id}",
                    farm_specific_location_id,
                    f"Kernel reporting scoped fixture {fixture_id}",
                    f"kernel-report-scoped-{fixture_id}",
                ),
            )
            cur.execute(
                "INSERT INTO public.metric_definition "
                "(id, metric_key, display_name, unit, active) "
                "VALUES (%s, %s, 'Kernel reporting fixture metric', 'fixture_units', TRUE)",
                (metric_id, metric_key),
            )
            insert_reporting_fixture_registry(
                cur,
                registry_ids[0],
                None,
                location_id,
                f"kernel-report-location-wide-{fixture_id}",
            )
            cur.execute(
                "INSERT INTO public.attestation_schema "
                "(id, schema_uid, name, chain, active) VALUES (%s, %s, %s, 'celo', TRUE)",
                (
                    attestation_schema_id,
                    f"0x{fixture_id}{'0' * 32}",
                    f"Kernel reporting fixture {fixture_id}",
                ),
            )
            cur.executemany(
                "INSERT INTO public.attestation_record "
                "(id, schema_id, claim_type, subject_id, subject_type, claim_data, status, chain, attested_at) "
                "VALUES (%s, %s, 'impact', %s, 'location', '{\"synthetic\":true}'::jsonb, %s, %s, %s)",
                (
                    (attestation_ids[0], attestation_schema_id, location_id, "verified", "celo", "2026-01-01T00:00:00Z"),
                    (attestation_ids[1], attestation_schema_id, location_id, "published", "celo", "2026-02-01T00:00:00Z"),
                    (attestation_ids[2], attestation_schema_id, location_id, "published", "gnosis", "2026-03-01T00:00:00Z"),
                    (attestation_ids[3], attestation_schema_id, location_id, "draft", "celo", "2026-04-01T00:00:00Z"),
                ),
            )
            cur.execute(
                "SELECT farm_count, plot_count, total_area_ha, area_data_complete "
                "FROM kokonut_reporting.v_farm_summary WHERE location_id=%s",
                (location_id,),
            )
            baseline = cur.fetchone()
            if baseline != (0, 0, 0, True):
                raise AssertionError("location-wide registry baseline is not an empty, complete summary")

            # Two equal-area farms with three plots must add 5 hectares, not
            # duplicate one farm's area or multiply it by its plot count.
            for index in range(2):
                insert_reporting_fixture_farm(
                    cur, farm_ids[index], location_id, fixture_id, index, 2.5, "hectares"
                )
            for index, farm_index in enumerate((0, 0, 1)):
                insert_reporting_fixture_plot(cur, plot_ids[index], farm_ids[farm_index], fixture_id, index)

            cur.execute(
                "INSERT INTO public.metric_value "
                "(id, metric_id, location_id, period_start, period_end, value, unit, "
                "computation_method, computed_at, verified, metadata, verified_by, "
                "verified_at, verification_notes) "
                "VALUES (%s, %s, %s, %s, %s, 7.125, 'fixture_units', %s, NOW(), TRUE, "
                "'{}'::jsonb, %s, NOW(), 'isolated reporting fixture')",
                (
                    metric_value_id,
                    metric_id,
                    location_id,
                    metric_period_start,
                    metric_period_end,
                    method,
                    reviewer_id,
                ),
            )
            cur.execute(
                "INSERT INTO kokonut_reporting.metric_publication_policy "
                "(metric_id, status) VALUES (%s, 'draft')",
                (metric_id,),
            )

        with admin.cursor() as cur:
            cur.execute("SET LOCAL ROLE kokonut_analytics_ro")
            cur.execute(
                "SELECT farm_count, plot_count, total_area_ha, area_data_complete "
                "FROM kokonut_reporting.v_farm_summary WHERE location_id=%s",
                (location_id,),
            )
            farm_row = cur.fetchone()
            if farm_row != (2, 3, 5.0, True):
                raise AssertionError("equal-area farm and farm-to-plot aggregation is incorrect")
            cur.execute(
                "SELECT count(*) FROM kokonut_reporting.v_verified_metric_values "
                "WHERE location_id=%s AND metric_key=%s AND period_start=%s "
                "AND period_end=%s AND computation_method=%s",
                (location_id, metric_key, metric_period_start, metric_period_end, method),
            )
            if cur.fetchone()[0] != 0:
                raise AssertionError("draft metric publication policy exposed a verified value")
            cur.execute(
                "SELECT chain, claim_type, total_attestations, published_count, "
                "first_attestation, latest_attestation "
                "FROM kokonut_reporting.v_attestation_summary WHERE location_id=%s",
                (location_id,),
            )
            attestation_row = cur.fetchone()
            if (
                attestation_row is None
                or attestation_row[0] != "celo"
                or attestation_row[1] != "impact"
                or attestation_row[2:4] != (2, 1)
                or attestation_row[4].strftime("%Y-%m-%d") != "2026-01-01"
                or attestation_row[5].strftime("%Y-%m-%d") != "2026-02-01"
            ):
                raise AssertionError("Celo attestation scope or lifecycle aggregation is incorrect")
            cur.execute("RESET ROLE")

        with admin.cursor() as cur:
            cur.execute(
                "UPDATE kokonut_reporting.metric_publication_policy "
                "SET status='published', reviewed_by=%s, reviewed_at=NOW(), "
                "review_notes='isolated reporting fixture' WHERE metric_id=%s",
                (reviewer_id_2, metric_id),
            )
            if cur.rowcount != 1:
                raise AssertionError("synthetic metric policy could not transition to published")
            cur.execute("SET LOCAL ROLE kokonut_analytics_ro")
            cur.execute(
                "SELECT value, unit, period_start, period_end, computation_method, verified_at "
                "FROM kokonut_reporting.v_verified_metric_values "
                "WHERE location_id=%s AND metric_key=%s AND period_start=%s "
                "AND period_end=%s AND computation_method=%s",
                (location_id, metric_key, metric_period_start, metric_period_end, method),
            )
            metric_row = cur.fetchone()
            if (
                metric_row is None
                or float(metric_row[0]) != 7.125
                or metric_row[1] != "fixture_units"
                or str(metric_row[2]) != metric_period_start
                or str(metric_row[3]) != metric_period_end
                or metric_row[4] != method
                or metric_row[5] is None
            ):
                raise AssertionError("published metric did not preserve period, method, and review fields")
            cur.execute("RESET ROLE")

        with admin.cursor() as cur:
            insert_reporting_fixture_farm(
                cur, farm_ids[2], location_id, fixture_id, 2, 1, "fixture_unknown_unit"
            )
            cur.execute("SET LOCAL ROLE kokonut_analytics_ro")
            cur.execute(
                "SELECT total_area_ha, area_data_complete "
                "FROM kokonut_reporting.v_farm_summary WHERE location_id=%s",
                (location_id,),
            )
            if cur.fetchone() != (None, False):
                raise AssertionError("unsupported farm-area units were reported as a complete total")
            cur.execute("RESET ROLE")

            # Farm-specific registry approval includes only the named farm and
            # its active plots, even when another active farm shares the location.
            cur.execute(
                "INSERT INTO public.farm "
                "(id, location_id, name, slug, total_area, area_unit, status) "
                "VALUES (%s, %s, 'Approved scoped farm', %s, 1, 'hectares', 'active'), "
                "(%s, %s, 'Unregistered scoped farm', %s, 9, 'hectares', 'active')",
                (
                    farm_ids[3],
                    farm_specific_location_id,
                    f"kernel-report-approved-{fixture_id}",
                    farm_ids[4],
                    farm_specific_location_id,
                    f"kernel-report-hidden-{fixture_id}",
                ),
            )
            insert_reporting_fixture_registry(
                cur,
                registry_ids[1],
                farm_ids[3],
                farm_specific_location_id,
                f"kernel-report-registry-scoped-{fixture_id}",
            )
            insert_reporting_fixture_plot(cur, plot_ids[3], farm_ids[3], fixture_id, 3)
            insert_reporting_fixture_plot(cur, plot_ids[4], farm_ids[4], fixture_id, 4)
            cur.execute("SET LOCAL ROLE kokonut_analytics_ro")
            cur.execute(
                "SELECT farm_count, plot_count, total_area_ha, area_data_complete "
                "FROM kokonut_reporting.v_farm_summary WHERE location_id=%s",
                (farm_specific_location_id,),
            )
            if cur.fetchone() != (1, 1, 1.0, True):
                raise AssertionError("farm-specific registry approval exposed an unregistered farm")
            cur.execute("RESET ROLE")
        admin.rollback()
        return {
            "equal_area_farm_and_plot_aggregation": "passed",
            "unsupported_area_unit_fail_closed": "passed",
            "farm_specific_registry_scope": "passed",
            "celo_attestation_scope_and_lifecycle": "passed",
            "verified_metric_requires_published_allowlist": "passed",
            "metric_period_method_and_review_fields": "passed",
        }
    finally:
        # The entire reporting behavior probe is intentionally rolled back.
        admin.rollback()


def role_attributes(admin, names: tuple[str, ...]) -> dict[str, list[bool]]:
    result = {}
    with admin.cursor() as cur:
        for name in names:
            cur.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, "
                "rolinherit FROM pg_roles WHERE rolname = %s",
                (name,),
            )
            attrs = cur.fetchone()
            if attrs != (False, False, False, False, False, False):
                raise AssertionError(f"{name} has an unexpected privileged role attribute")
            cur.execute(
                "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid "
                "WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = %s)",
                (name,),
            )
            if cur.fetchone()[0] != 0:
                raise AssertionError(f"{name} has unexpected role memberships")
            result[name] = list(attrs)
    return result


def transfer_metadata_relations(metadata_admin) -> int:
    """Transfer only Metabase-owned relation objects in its application schema."""
    transferred = 0
    with metadata_admin.cursor() as cur:
        cur.execute(
            "SELECT c.relname, c.relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = %s) "
            "AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S') "
            "AND NOT (c.relkind = 'S' AND EXISTS (SELECT 1 FROM pg_depend d "
            "WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid "
            "AND d.refclassid = 'pg_class'::regclass AND d.deptype IN ('a', 'i'))) "
            "ORDER BY c.relkind, c.relname",
            (ADMIN_USER,),
        )
        relations = cur.fetchall()
        for name, kind in relations:
            statement = "ALTER SEQUENCE {}.{} OWNER TO {}" if kind == "S" else "ALTER TABLE {}.{} OWNER TO {}"
            cur.execute(
                sql.SQL(statement).format(
                    sql.Identifier("public"),
                    sql.Identifier(name),
                    role_ident(METABASE_ROLE),
                )
            )
            transferred += 1
    return transferred


def main() -> int:
    directus_password = os.environ.get("DIRECTUS_ROLE_PASSWORD", "")
    metabase_password = os.environ.get("METABASE_ROLE_PASSWORD", "")
    analytics_password = os.environ.get("ANALYTICS_ROLE_PASSWORD", "")
    roles = (DIRECTUS_ROLE, METABASE_ROLE, ANALYTICS_ROLE)
    if not ADMIN_PASSWORD or any(not value for value in (directus_password, metabase_password, analytics_password)):
        raise SystemExit("synthetic fixture credentials must be supplied through the environment")
    if len({ADMIN_PASSWORD, directus_password, metabase_password, analytics_password}) != 4:
        raise SystemExit("all fixture credentials must be distinct")

    admin = connect(ADMIN_USER, ADMIN_PASSWORD, APP_DATABASE)
    directus = metabase = analytics = None
    directus_probe = f"kernel_directus_probe_{uuid.uuid4().hex[:10]}"
    metabase_probe = f"kernel_metabase_probe_{uuid.uuid4().hex[:10]}"
    directus_probe_created = False
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT current_database(), rolsuper FROM pg_roles WHERE rolname = current_user")
            db_name, is_superuser = cur.fetchone()
            if db_name != APP_DATABASE or not is_superuser:
                raise AssertionError("fixture admin is not the expected superuser on the isolated target")
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (METADATA_DATABASE,))
            if cur.fetchone() is None:
                raise AssertionError("the restored Metabase metadata database is missing")
        admin.commit()

        ensure_login_role(admin, DIRECTUS_ROLE, directus_password)
        ensure_login_role(admin, METABASE_ROLE, metabase_password)
        ensure_login_role(admin, ANALYTICS_ROLE, analytics_password)
        admin.commit()

        all_databases = grant_database_only(admin, APP_DATABASE, (DIRECTUS_ROLE, ANALYTICS_ROLE))
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(METADATA_DATABASE), role_ident(METABASE_ROLE)
                )
            )
        admin.commit()

        directus_schemas = ["public"]
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'kokonut'")
            if cur.fetchone():
                directus_schemas.append("kokonut")
            for schema in directus_schemas:
                ident = sql.Identifier(schema)
                cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(ident, role_ident(DIRECTUS_ROLE)))
                cur.execute(
                    sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
                        ident, role_ident(DIRECTUS_ROLE)
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                        ident, role_ident(DIRECTUS_ROLE)
                    )
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                    ).format(role_ident(ADMIN_USER), ident, role_ident(DIRECTUS_ROLE))
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
                    ).format(role_ident(ADMIN_USER), ident, role_ident(DIRECTUS_ROLE))
                )
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(role_ident(DIRECTUS_ROLE))
            )
        admin.commit()

        # A Directus runtime identity can edit application rows but cannot migrate schema.
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE TABLE public.{} (id BIGSERIAL PRIMARY KEY, payload TEXT NOT NULL)").format(
                    sql.Identifier(directus_probe)
                )
            )
        admin.commit()
        directus_probe_created = True
        directus = connect(DIRECTUS_ROLE, directus_password, APP_DATABASE)
        with directus.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO public.{} (payload) VALUES ('synthetic') RETURNING id").format(
                    sql.Identifier(directus_probe)
                )
            )
            probe_id = cur.fetchone()[0]
            cur.execute(
                sql.SQL("UPDATE public.{} SET payload = 'updated' WHERE id = %s").format(
                    sql.Identifier(directus_probe)
                ),
                (probe_id,),
            )
            if cur.rowcount != 1:
                raise AssertionError("Directus role could not update its synthetic row")
            cur.execute(
                sql.SQL("DELETE FROM public.{} WHERE id = %s").format(sql.Identifier(directus_probe)),
                (probe_id,),
            )
            if cur.rowcount != 1:
                raise AssertionError("Directus role could not delete its synthetic row")
        directus.commit()
        require_denied(directus, "CREATE TABLE public.kernel_directus_ddl_denied (id INTEGER)")
        require_denied(directus, "CREATE ROLE kernel_directus_role_denied")
        require_denied(directus, "CREATE DATABASE kernel_directus_database_denied")
        require_denied(directus, sql.SQL("SET ROLE {}").format(role_ident(ADMIN_USER)).as_string(directus))
        require_database_denied(DIRECTUS_ROLE, directus_password, METADATA_DATABASE)
        require_database_denied(DIRECTUS_ROLE, directus_password, "postgres")

        # The metadata database is a separate service-owned database. Its role can
        # perform product migrations there, but has no cluster/database admin power.
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                    sql.Identifier(METADATA_DATABASE), role_ident(METABASE_ROLE)
                )
            )
        admin.commit()
        metadata_admin = connect(ADMIN_USER, ADMIN_PASSWORD, METADATA_DATABASE)
        metadata_relations_transferred = transfer_metadata_relations(metadata_admin)
        with metadata_admin.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(role_ident(METABASE_ROLE))
            )
            cur.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                ).format(role_ident(METABASE_ROLE))
            )
            cur.execute(
                sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                    role_ident(METABASE_ROLE)
                )
            )
            cur.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=%s) "
                "AND c.relkind IN ('r','p','v','m','f','S')",
                (METABASE_ROLE,),
            )
            metadata_relations_owned_by_role = cur.fetchone()[0]
            if metadata_relations_owned_by_role == 0:
                raise AssertionError("Metabase role owns no application relations in its metadata database")
        metadata_admin.commit()
        metadata_admin.close()
        metabase = connect(METABASE_ROLE, metabase_password, METADATA_DATABASE)
        with metabase.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE TABLE public.{} (id BIGSERIAL PRIMARY KEY, payload TEXT NOT NULL)").format(
                    sql.Identifier(metabase_probe)
                )
            )
            cur.execute(
                sql.SQL("INSERT INTO public.{} (payload) VALUES ('synthetic') RETURNING id").format(
                    sql.Identifier(metabase_probe)
                )
            )
            probe_id = cur.fetchone()[0]
            cur.execute(
                sql.SQL("ALTER TABLE public.{} ADD COLUMN migration_probe BOOLEAN DEFAULT TRUE").format(
                    sql.Identifier(metabase_probe)
                )
            )
            cur.execute(
                sql.SQL("SELECT count(*) FROM public.{} WHERE migration_probe").format(
                    sql.Identifier(metabase_probe)
                )
            )
            if cur.fetchone()[0] != 1:
                raise AssertionError("Metabase metadata role failed synthetic table migration/DML")
            cur.execute(sql.SQL("DROP TABLE public.{}").format(sql.Identifier(metabase_probe)))
        metabase.commit()
        require_denied(metabase, "CREATE ROLE kernel_metabase_role_denied")
        require_denied(metabase, "CREATE DATABASE kernel_metabase_database_denied")
        require_database_denied(METABASE_ROLE, metabase_password, APP_DATABASE)
        require_database_denied(METABASE_ROLE, metabase_password, "postgres")

        # Grant only the actual product reporting views. The hidden policy table
        # and canonical public relations remain inaccessible to this login.
        reporting_views = provision_reporting_view_grants(admin)
        with admin.cursor() as cur:
            cur.execute(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND has_table_privilege(%s, c.oid, 'SELECT') "
                "AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname",
                (ANALYTICS_ROLE,),
            )
            analytics_public_relation_names = [row[0] for row in cur.fetchall()]
            public_extension_metadata = {
                "geography_columns",
                "geometry_columns",
                "pg_stat_statements",
                "pg_stat_statements_info",
                "spatial_ref_sys",
            }
            if set(analytics_public_relation_names) - public_extension_metadata:
                raise AssertionError("analytics source role can read an unreviewed public relation")
        admin.commit()
        analytics = connect(ANALYTICS_ROLE, analytics_password, APP_DATABASE)
        with analytics.cursor() as cur:
            for view_name in REPORTING_VIEWS:
                cur.execute(
                    sql.SQL("SELECT count(*) FROM {}.{}").format(
                        sql.Identifier(REPORTING_SCHEMA), sql.Identifier(view_name)
                    )
                )
                cur.fetchone()
        analytics.commit()
        require_denied(
            analytics,
            "SELECT * FROM public.metric_value",
        )
        require_denied(analytics, "SELECT * FROM public.schema_migration")
        require_denied(
            analytics,
            "SELECT * FROM kokonut_reporting.metric_publication_policy",
        )
        require_denied(
            analytics,
            "CREATE TABLE kokonut_reporting.ddl_denied (id INTEGER)",
        )
        require_denied(
            analytics,
            "INSERT INTO kokonut_reporting.v_farm_summary "
            "(location_id) VALUES ('00000000-0000-0000-0000-000000000000')",
            expected_codes=("42501", "55000"),
        )
        reporting_behavior = exercise_reporting_views(admin)
        require_database_denied(ANALYTICS_ROLE, analytics_password, METADATA_DATABASE)
        require_database_denied(ANALYTICS_ROLE, analytics_password, "postgres")

        attributes = role_attributes(admin, roles)
        with admin.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND has_table_privilege(%s, c.oid, 'INSERT') "
                "AND c.relkind IN ('r','p','v','m','f')",
                (DIRECTUS_ROLE,),
            )
            directus_public_dml_relations = cur.fetchone()[0]
            cur.execute(
                "SELECT pg_get_userbyid(datdba) = %s FROM pg_database WHERE datname = %s",
                (METABASE_ROLE, METADATA_DATABASE),
            )
            metadata_database_owned = cur.fetchone()[0]
        if not metadata_database_owned:
            raise AssertionError("Metabase role does not own only its application database")

        print(
            json.dumps(
                {
                    "result": "passed",
                    "scope": (
                        "current-schema scratch database in an isolated copy of the populated recovery volume; "
                        "Metabase metadata remains populated; application probes are synthetic and rolled back"
                    ),
                    "database_names": sorted(all_databases),
                    "directus_runtime": {
                        "role": DIRECTUS_ROLE,
                        "schemas": directus_schemas,
                        "dml_probe": "passed",
                        "ddl_and_admin_denials": ["CREATE TABLE", "CREATE ROLE", "CREATE DATABASE", "SET ROLE admin"],
                        "public_relations_with_dml": directus_public_dml_relations,
                        "ownership": "none",
                    },
                    "metabase_metadata": {
                        "role": METABASE_ROLE,
                        "database": METADATA_DATABASE,
                        "database_owned_by_role": metadata_database_owned,
                        "application_relations_owned_by_role": metadata_relations_owned_by_role,
                        "synthetic_migration_ddl_and_dml": "passed",
                        "cluster_admin_denials": ["CREATE ROLE", "CREATE DATABASE"],
                    },
                    "analytics_source": {
                        "role": ANALYTICS_ROLE,
                        "readable_reporting_views": reporting_views,
                        "curated_view_select": "passed",
                        "unreviewed_public_relations_readable": 0,
                        "public_extension_metadata_relations": len(analytics_public_relation_names),
                        "behavioral_probes": reporting_behavior,
                        "denials": [
                            "base table SELECT",
                            "metric publication policy SELECT",
                            "CREATE TABLE",
                            "view INSERT",
                        ],
                    },
                    "cross_database_connect_denied": {
                        DIRECTUS_ROLE: [METADATA_DATABASE, "postgres"],
                        METABASE_ROLE: [APP_DATABASE, "postgres"],
                        ANALYTICS_ROLE: [METADATA_DATABASE, "postgres"],
                    },
                    "role_attributes": attributes,
                    "source_recovery_volume_mutated": False,
                    "isolated_clone_role_setup_applied": True,
                    "scratch_reporting_fixture_rows_rolled_back": True,
                    "metabase_metadata_ownership_changed_in_clone": True,
                    "private_payloads_or_passwords_printed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        for conn in (directus, metabase, analytics):
            if conn is not None:
                conn.close()
        admin.rollback()
        with admin.cursor() as cur:
            if directus_probe_created:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS public.{} CASCADE").format(sql.Identifier(directus_probe)))
        admin.commit()
        admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
