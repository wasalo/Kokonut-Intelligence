"""Exercise the Kernel runtime role against an isolated populated restore.

The only write is a temporary synthetic table, removed by the admin connection
in ``finally``. No restored domain row is read back or changed.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql

from services.gateway.locations import public_locations
from services.migration.runtime_role import provision_runtime_role

DATABASE = os.environ.get("PG_DB", "kokonut_intelligence_restore")
HOST = os.environ.get("PG_HOST", "database")
PORT = int(os.environ.get("PG_PORT", "5432"))
ADMIN_USER = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
ADMIN_PASSWORD = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
RUNTIME_USER = os.environ.get("KOKONUT_RUNTIME_USER", "kokonut_runtime")
RUNTIME_PASSWORD = os.environ.get("KOKONUT_RUNTIME_PASSWORD", "")
OPERATOR_AUTH_USER = os.environ.get("KOKONUT_OPERATOR_AUTH_USER", "kokonut_operator_auth")
OPERATOR_AUTH_PASSWORD = os.environ.get("KOKONUT_OPERATOR_AUTH_PASSWORD", "")
OPERATOR_SESSION_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "schemas/postgres/395_operator_session_auth_boundary.sql"
)
GATEWAY_CONTEXT_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "schemas/postgres/396_signed_gateway_credential_tenant_context.sql"
)


def connect(user: str, password: str, database: str = DATABASE):
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=database,
        user=user,
        password=password,
        connect_timeout=10,
    )


def expect_denied(conn, statement: str, parameters=None) -> None:
    original_autocommit = conn.autocommit
    database_ddl = statement.lstrip().upper().startswith("CREATE DATABASE")
    if database_ddl:
        conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(statement, parameters)
    except psycopg2.Error as exc:
        if "permission denied" not in str(exc).lower():
            raise AssertionError("privileged action failed for an unexpected reason") from exc
        if not conn.autocommit:
            conn.rollback()
    else:
        if not conn.autocommit:
            conn.rollback()
        raise AssertionError("runtime role unexpectedly completed a privileged action")
    finally:
        if database_ddl:
            conn.autocommit = original_autocommit



def main() -> int:
    if not ADMIN_PASSWORD or not RUNTIME_PASSWORD or not OPERATOR_AUTH_PASSWORD:
        raise SystemExit("synthetic admin, runtime, and operator-auth credentials are required")

    admin = connect(ADMIN_USER, ADMIN_PASSWORD)
    runtime = None
    probe_table = f"kernel_role_restore_probe_{uuid.uuid4().hex[:12]}"
    probe_created = False
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != DATABASE:
                raise AssertionError("connected database does not match the isolated restore target")
            cur.execute(OPERATOR_SESSION_MIGRATION.read_text())
            cur.execute(GATEWAY_CONTEXT_MIGRATION.read_text())
            cur.execute(
                sql.SQL(
                    "CREATE TABLE public.{} (id BIGSERIAL PRIMARY KEY, payload TEXT NOT NULL)"
                ).format(sql.Identifier(probe_table))
            )
        admin.commit()
        probe_created = True

        first = provision_runtime_role(
            admin,
            database=DATABASE,
            admin_user=ADMIN_USER,
            admin_password=ADMIN_PASSWORD,
            runtime_user=RUNTIME_USER,
            runtime_password=RUNTIME_PASSWORD,
            operator_auth_user=OPERATOR_AUTH_USER,
            operator_auth_password=OPERATOR_AUTH_PASSWORD,
        )
        second = provision_runtime_role(
            admin,
            database=DATABASE,
            admin_user=ADMIN_USER,
            admin_password=ADMIN_PASSWORD,
            runtime_user=RUNTIME_USER,
            runtime_password=RUNTIME_PASSWORD,
            operator_auth_user=OPERATOR_AUTH_USER,
            operator_auth_password=OPERATOR_AUTH_PASSWORD,
        )
        if first["status"] != "provisioned" or second["status"] != "provisioned":
            raise AssertionError("role provisioning was not repeatable")

        runtime = connect(RUNTIME_USER, RUNTIME_PASSWORD)
        public_rows = public_locations()
        with runtime.cursor() as cur:
            cur.execute("SELECT postgis_version(), ST_SRID(ST_SetSRID(ST_MakePoint(0, 0), 4326))")
            postgis_version, srid = cur.fetchone()
            cur.execute("SELECT count(*) FROM schema_migration")
            migration_count = cur.fetchone()[0]

        with runtime.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO public.{} (payload) VALUES (%s) RETURNING id").format(
                    sql.Identifier(probe_table)
                ),
                ("synthetic",),
            )
            probe_id = cur.fetchone()[0]
            cur.execute(
                sql.SQL("SELECT payload FROM public.{} WHERE id = %s").format(
                    sql.Identifier(probe_table)
                ),
                (probe_id,),
            )
            if cur.fetchone()[0] != "synthetic":
                raise AssertionError("runtime SELECT did not return the synthetic probe row")
            cur.execute(
                sql.SQL("UPDATE public.{} SET payload = %s WHERE id = %s").format(
                    sql.Identifier(probe_table)
                ),
                ("updated", probe_id),
            )
            if cur.rowcount != 1:
                raise AssertionError("runtime UPDATE did not affect exactly one probe row")
            cur.execute(
                sql.SQL("DELETE FROM public.{} WHERE id = %s").format(sql.Identifier(probe_table)),
                (probe_id,),
            )
            if cur.rowcount != 1:
                raise AssertionError("runtime DELETE did not affect exactly one probe row")
        runtime.commit()

        expect_denied(runtime, "CREATE TABLE public.kernel_role_persistent_ddl_denied (id INTEGER)")
        expect_denied(runtime, "CREATE ROLE kernel_role_create_denied")
        expect_denied(runtime, "CREATE DATABASE kernel_role_create_denied")
        expect_denied(runtime, sql.SQL("SET ROLE {}").format(sql.Identifier(ADMIN_USER)).as_string(runtime))
        mobile_credential_denials = (
            "SELECT device_token_hash FROM public.mobile_device LIMIT 1",
            "SELECT push_token FROM public.mobile_device LIMIT 1",
            "SELECT code_hash FROM public.mobile_device_enrollment LIMIT 1",
        )
        for statement in mobile_credential_denials:
            expect_denied(runtime, statement)

        denied_databases = []
        for other_database in ("postgres", "kokonut_intelligence"):
            try:
                unexpected = connect(RUNTIME_USER, RUNTIME_PASSWORD, other_database)
            except psycopg2.OperationalError as exc:
                if "permission denied" not in str(exc).lower():
                    raise AssertionError("unrelated database connection failed for an unexpected reason") from exc
                denied_databases.append(other_database)
            else:
                unexpected.close()
                raise AssertionError(f"runtime role unexpectedly connected to {other_database}")

        with admin.cursor() as cur:
            cur.execute(
                "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, "
                "r.rolbypassrls, r.rolinherit, has_schema_privilege(r.oid, 'public', 'CREATE') "
                "FROM pg_roles r WHERE r.rolname = %s",
                (RUNTIME_USER,),
            )
            attributes = cur.fetchone()
        if attributes != (False, False, False, False, False, False, False):
            raise AssertionError("runtime role retained elevated attributes")

        print(
            json.dumps(
                {
                    "result": "passed",
                    "fixture_data": "public projection queried in-memory; only count emitted; synthetic probe removed",
                    "database": DATABASE,
                    "schema_migration_rows": migration_count,
                    "public_location_query": "passed",
                    "public_location_count": len(public_rows),
                    "postgis_query": "passed",
                    "postgis_version": postgis_version.split(" ")[0],
                    "srid": srid,
                    "provisioning_runs": [first["status"], second["status"]],
                    "synthetic_probe_dml": ["SELECT", "INSERT", "UPDATE", "DELETE", "sequence use"],
                    "denied_actions": [
                        "persistent table DDL",
                        "CREATE ROLE",
                        "CREATE DATABASE",
                        "SET ROLE admin",
                    ],
                    "denied_mobile_credential_reads": [
                        "device_token_hash",
                        "push_token",
                        "code_hash",
                    ],
                    "denied_unrelated_databases": denied_databases,
                    "role_attributes": {
                        "superuser": attributes[0],
                        "createdb": attributes[1],
                        "createrole": attributes[2],
                        "replication": attributes[3],
                        "bypassrls": attributes[4],
                        "inherit": attributes[5],
                        "public_schema_create": attributes[6],
                    },
                    "secrets_printed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if runtime is not None:
            runtime.close()
        if probe_created:
            with admin.cursor() as cur:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS public.{} CASCADE").format(sql.Identifier(probe_table)))
            admin.commit()
        admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
