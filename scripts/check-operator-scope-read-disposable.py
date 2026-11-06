#!/usr/bin/env python3
"""Verify migration 750's operator scope-read boundary on disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/operator_tenant_context_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/750_operator_scope_read_functions.sql"
IMAGE = "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
DEFAULT_OUTPUT = ROOT / (
    f"docs/refactor/builds/{datetime.now(timezone.utc):%Y-%m-%d}-recovery/"
    "operator-scope-read-750-disposable.json"
)
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OWNER_OPERATOR_ID = "a0000000-0000-0000-0000-000000000901"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable acceptance command failed ({result.returncode})\n{details}")
    return result.stdout


def docker_sql(container: str, password: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", "--env", f"PGPASSWORD={password}", container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "-t", "-A",
            "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(container: str, password: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker", "exec", "--env", f"PGPASSWORD={password}", container,
                "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def expect_denied(connection, statement: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
    except psycopg2.Error as exc:
        if exc.pgcode != "42501":
            raise AssertionError(f"expected insufficient privilege, received SQLSTATE {exc.pgcode}") from exc
        return
    raise AssertionError("role unexpectedly succeeded: " + statement)


def validate(host_port: int, admin_password: str) -> list[str]:
    connection = psycopg2.connect(
        host="127.0.0.1",
        port=host_port,
        dbname="postgres",
        user="postgres",
        password=admin_password,
        connect_timeout=5,
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                          rolreplication, rolbypassrls, rolinherit
                     FROM pg_roles WHERE rolname = 'kokonut_operator_scope_read_owner'"""
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False):
                raise AssertionError("scope-read owner has unsafe role attributes")
            cursor.execute(
                """SELECT count(*) FROM pg_auth_members AS membership
                     JOIN pg_roles AS role ON role.oid IN (membership.roleid, membership.member)
                    WHERE role.rolname = 'kokonut_operator_scope_read_owner'"""
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("scope-read owner has role membership")
            cursor.execute(
                """SELECT has_function_privilege(
                           'kokonut_operator_auth',
                           'kokonut_security.operator_scope_grant_read_allows(uuid,text,text,uuid)',
                           'EXECUTE'
                       ), has_function_privilege(
                           'kokonut_operator_auth',
                           'kokonut_security.operator_scope_grant_read_scopes(uuid)',
                           'EXECUTE'
                       ), has_function_privilege(
                           'kokonut_runtime',
                           'kokonut_security.operator_scope_grant_read_allows(uuid,text,text,uuid)',
                           'EXECUTE'
                       ), has_function_privilege(
                           'kokonut_runtime',
                           'kokonut_security.operator_scope_grant_read_scopes(uuid)',
                           'EXECUTE'
                       )"""
            )
            if cursor.fetchone() != (True, True, False, False):
                raise AssertionError("scope-read function EXECUTE grants do not match the auth/runtime boundary")
            cursor.execute(
                """SELECT has_table_privilege(
                           'kokonut_operator_auth', relation_name, 'SELECT'
                       )
                     FROM unnest(ARRAY[
                         'public.operator_scope_grant', 'public.operator_identity',
                         'public.location', 'public.operator_organization_membership',
                         'public.organization', 'public.location_tenant_owner_verification',
                         'public.location_organization_share'
                     ]) AS relation_name"""
            )
            if any(value[0] for value in cursor.fetchall()):
                raise AssertionError("operator-auth login has direct table-level scope reads")

        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_operator_auth")
            for query, parameters, expected in (
                (
                    "SELECT kokonut_security.operator_scope_grant_read_allows(%s::uuid, %s, %s, %s::uuid)",
                    (OWNER_OPERATOR_ID, "farm_activity", "read", LOCATION_ID),
                    True,
                ),
                (
                    "SELECT kokonut_security.operator_scope_grant_read_allows(%s::uuid, %s, %s, %s::uuid)",
                    ("a0000000-0000-0000-0000-000000000902", "farm_activity", "review", LOCATION_ID),
                    True,
                ),
                (
                    "SELECT kokonut_security.operator_scope_grant_read_allows(%s::uuid, %s, %s, %s::uuid)",
                    ("a0000000-0000-0000-0000-000000000907", "farm_activity", "expired_share", LOCATION_ID),
                    False,
                ),
                (
                    "SELECT kokonut_security.operator_scope_grant_read_allows(%s::uuid, %s, %s, %s::uuid)",
                    ("a0000000-0000-0000-0000-000000000905", "farm_activity", "read", LOCATION_ID),
                    False,
                ),
                (
                    "SELECT kokonut_security.operator_scope_grant_read_allows(%s::uuid, %s, %s, %s::uuid)",
                    ("a0000000-0000-0000-0000-000000000904", "farm_activity", "legacy_read", LOCATION_ID),
                    True,
                ),
            ):
                cursor.execute(query, parameters)
                if cursor.fetchone() != (expected,):
                    raise AssertionError("scope-check result changed for tenant/legacy fixture case")
            cursor.execute(
                """SELECT resource, action, location_id::text
                     FROM kokonut_security.operator_scope_grant_read_scopes(%s::uuid)
                    ORDER BY resource, action, location_id""",
                (OWNER_OPERATOR_ID,),
            )
            owner_scopes = cursor.fetchall()
            if owner_scopes != [("farm_activity", "read", LOCATION_ID)]:
                raise AssertionError("scope-list response differs from the active, ordered owner scopes")
            cursor.execute(
                """SELECT resource, action, location_id::text
                     FROM kokonut_security.operator_scope_grant_read_scopes(%s::uuid)
                    ORDER BY resource, action, location_id""",
                ("a0000000-0000-0000-0000-000000000903",),
            )
            if cursor.fetchall() != [
                ("farm_activity", "read", LOCATION_ID),
                ("report_snapshot", "read", LOCATION_ID),
            ]:
                raise AssertionError("multi-tenant scope listing lost stable ordering or tenant-valid scopes")
            for relation in (
                "operator_scope_grant",
                "operator_identity",
                "location",
                "operator_organization_membership",
                "organization",
                "location_tenant_owner_verification",
                "location_organization_share",
            ):
                expect_denied(connection, f"SELECT * FROM public.{relation} LIMIT 1")
            cursor.execute("RESET ROLE")

        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_runtime")
            expect_denied(
                connection,
                "SELECT kokonut_security.operator_scope_grant_read_allows("
                "'a0000000-0000-0000-0000-000000000901'::uuid, 'farm_activity', 'read', "
                "'a0000000-0000-0000-0000-000000000001'::uuid)",
            )
            cursor.execute("RESET ROLE")

        return [
            "migration 750 applies and replays with the isolated NOLOGIN scope-read owner",
            "operator-auth receives only the two bounded scope-read functions and no direct scope-table SELECT",
            "general runtime cannot execute the new operator-auth scope functions",
            "legacy location grants, active organization sharing, disabled identities, and expired shares retain exact semantics",
            "scope listings retain stable resource/action/location ordering under forced RLS",
        ]
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    suffix = uuid.uuid4().hex[:10]
    container = f"kokonut-operator-scope-read-{suffix}"
    network = f"kokonut-operator-scope-read-net-{suffix}"
    admin_password = secrets.token_urlsafe(32)
    network_created = False
    container_started = False
    try:
        run(
            [
                "docker", "network", "create", "--driver", "bridge",
                "--opt", "com.docker.network.bridge.enable_ip_masquerade=false", network,
            ]
        )
        network_created = True
        run(
            [
                "docker", "run", "--detach", "--rm", "--network", network,
                "--name", container, "--publish", "127.0.0.1::5432",
                "--env", f"POSTGRES_PASSWORD={admin_password}", IMAGE,
            ]
        )
        container_started = True
        wait_ready(container, admin_password)
        docker_sql(
            container,
            admin_password,
            "CREATE ROLE kokonut_operator_auth NOLOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;",
        )
        docker_sql(container, admin_password, FIXTURE.read_text(encoding="utf-8"))
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_sql(container, admin_password, migration_sql)
        docker_sql(container, admin_password, migration_sql)
        docker_sql(
            container,
            admin_password,
            """ALTER TABLE public.operator_scope_grant ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.operator_scope_grant FORCE ROW LEVEL SECURITY;
               ALTER TABLE public.operator_identity ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.operator_identity FORCE ROW LEVEL SECURITY;
               ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
               ALTER TABLE public.operator_organization_membership ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.operator_organization_membership FORCE ROW LEVEL SECURITY;
               ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.organization FORCE ROW LEVEL SECURITY;
               ALTER TABLE public.location_tenant_owner_verification ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.location_tenant_owner_verification FORCE ROW LEVEL SECURITY;
               ALTER TABLE public.location_organization_share ENABLE ROW LEVEL SECURITY;
               ALTER TABLE public.location_organization_share FORCE ROW LEVEL SECURITY;""",
        )
        published = run(["docker", "port", container, "5432/tcp"]).strip().splitlines()
        if not published:
            raise RuntimeError("disposable PostgreSQL has no host-side test mapping")
        host_port = int(published[0].rsplit(":", 1)[1])
        checks = validate(host_port, admin_password)
        report = {
            "acceptance": "operator_scope_read_migration_750_disposable",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_image": IMAGE,
            "checks": checks,
            "candidate_database_touched": False,
            "production_database_touched": False,
            "external_network_requests": 0,
            "synthetic_rows_remaining": 0,
            "scope_limit": "Validates the migration-owned operator-auth scope read path and tenant predicate on synthetic PostgreSQL 16 under forced RLS. It does not narrow existing kokonut_runtime table grants or establish tenant isolation for other Gateway/worker SQL.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - disposable acceptance diagnostics.
        print(f"OPERATOR SCOPE READ ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        if container_started:
            logs = subprocess.run(["docker", "logs", container], text=True, capture_output=True, check=False)
            if logs.stdout or logs.stderr:
                print("DISPOSABLE POSTGRES LOGS:", file=sys.stderr)
                print(logs.stdout, file=sys.stderr, end="")
                print(logs.stderr, file=sys.stderr, end="")
        return 1
    finally:
        if container_started:
            subprocess.run(["docker", "stop", container], text=True, capture_output=True, check=False)
        if network_created:
            subprocess.run(["docker", "network", "rm", network], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
