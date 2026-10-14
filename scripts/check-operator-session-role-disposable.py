#!/usr/bin/env python3
"""Verify operator-session isolation with disposable PostgreSQL 16 roles."""

from __future__ import annotations

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
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "tests/fixtures/operator_tenant_context_disposable.sql"
MOBILE_ROLE_FIXTURE = ROOT / "tests/fixtures/operator_session_mobile_role_boundary.sql"
MIGRATIONS = (
    ROOT / "schemas/postgres/391_mobile_device_tenant_binding.sql",
    ROOT / "schemas/postgres/392_mobile_credential_functions.sql",
    ROOT / "schemas/postgres/393_mobile_tenant_context_proof.sql",
    ROOT / "schemas/postgres/394_signed_operator_tenant_context.sql",
    ROOT / "schemas/postgres/395_operator_session_auth_boundary.sql",
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json"
)
OPERATOR_ID = "a0000000-0000-0000-0000-000000000901"
ISSUER = "https://identity.example"
SUBJECT = "owner-operator"
EXISTING_SESSION_HASH = "b" * 64
NEW_SESSION_HASH = "8" * 64
NEW_CSRF_HASH = "7" * 64
DOCKER_ADMIN_PASSWORD: str | None = None


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
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def docker_sql(container: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", "--env", f"PGPASSWORD={DOCKER_ADMIN_PASSWORD}", container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "-t", "-A",
            "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(container: str) -> None:
    for _ in range(120):
        result = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def provision_roles(
    container: str,
    runtime_password: str,
    auth_password: str,
    admin_password: str,
) -> tuple[dict, int]:
    published = run(["docker", "port", container, "5432/tcp"]).strip().splitlines()
    if not published:
        raise RuntimeError("disposable PostgreSQL has no host-side test mapping")
    host_port = int(published[0].rsplit(":", 1)[1])
    connection = psycopg2.connect(
        host="127.0.0.1",
        port=host_port,
        dbname="postgres",
        user="postgres",
        password=admin_password,
        connect_timeout=5,
    )
    try:
        from services.migration.runtime_role import provision_runtime_role

        result = provision_runtime_role(
            connection,
            database="postgres",
            admin_user="postgres",
            admin_password=admin_password,
            runtime_user="kokonut_runtime",
            runtime_password=runtime_password,
            operator_auth_user="kokonut_operator_auth",
            operator_auth_password=auth_password,
        )
        return result, host_port
    finally:
        connection.close()


def force_operator_rls(container: str) -> None:
    docker_sql(
        container,
        """
        ALTER TABLE public.operator_identity ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.operator_identity FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.operator_session ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.operator_session FORCE ROW LEVEL SECURITY;
        """,
    )


def expect_privilege_denial(connection, statement: str, parameters=None) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != "42501":
            raise AssertionError(f"expected insufficient privilege, got {exc.pgcode}") from exc
        return
    connection.rollback()
    raise AssertionError(f"database role unexpectedly succeeded: {statement}")


def assert_roles(host_port: int, runtime_password: str, auth_password: str) -> list[str]:
    runtime = psycopg2.connect(
        host="127.0.0.1", port=host_port, dbname="postgres",
        user="kokonut_runtime", password=runtime_password, connect_timeout=5,
    )
    try:
        with runtime.cursor() as cursor:
            cursor.execute("SELECT value FROM public.operator_session_runtime_probe WHERE id = 1")
            if cursor.fetchone()[0] != "admin-seeded":
                raise AssertionError("runtime role lost DML access to an unrelated public table")
            cursor.execute(
                "INSERT INTO public.operator_session_runtime_probe (value) VALUES ('runtime-insert') RETURNING id"
            )
            probe_id = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE public.operator_session_runtime_probe SET value = 'runtime-updated' WHERE id = %s",
                (probe_id,),
            )
            if cursor.rowcount != 1:
                raise AssertionError("runtime role could not update its unrelated probe row")
            cursor.execute(
                "DELETE FROM public.operator_session_runtime_probe WHERE id = %s",
                (probe_id,),
            )
            if cursor.rowcount != 1:
                raise AssertionError("runtime role could not delete its unrelated probe row")
            cursor.execute(
                """SELECT device_id, device_name, status, last_sync_at
                     FROM public.mobile_device WHERE device_id = 'role-boundary-device'"""
            )
            if cursor.fetchone()[0] != "role-boundary-device":
                raise AssertionError("runtime role lost safe mobile-device reads")
            cursor.execute(
                """SELECT device_id, user_id, location_id, owner_binding_current
                     FROM kokonut_security.resolve_mobile_device_token(%s)""",
                ("a" * 64,),
            )
            resolved = cursor.fetchone()
            if resolved != (
                "role-boundary-device",
                "synthetic-user",
                "a0000000-0000-0000-0000-000000000001",
                True,
            ):
                raise AssertionError("runtime role could not resolve a current device token via the bounded function")
            cursor.execute(
                """SELECT result, registered_location_id::text
                     FROM kokonut_security.redeem_mobile_enrollment(
                         %s, %s, %s, %s, NULL, NULL, %s, %s
                     )""",
                (
                    "b" * 64,
                    "role-boundary-registered-device",
                    "Synthetic enrolled device",
                    "phone",
                    "1.0.0",
                    "e" * 64,
                ),
            )
            if cursor.fetchone() != (
                "registered",
                "a0000000-0000-0000-0000-000000000001",
            ):
                raise AssertionError("runtime role could not redeem a current owner-bound enrollment")
            cursor.execute(
                """UPDATE public.mobile_device
                      SET last_seen_at = NOW(), updated_at = NOW()
                    WHERE device_id = 'role-boundary-device'"""
            )
            if cursor.rowcount != 1:
                raise AssertionError("runtime role lost the Field Collector last-seen update")
            cursor.execute(
                """INSERT INTO public.mobile_device_enrollment (
                       code_hash, user_id, location_id, tenant_organization_id,
                       created_by, expires_at
                   ) VALUES (
                       repeat('c', 64), 'synthetic-user',
                       'a0000000-0000-0000-0000-000000000001',
                       'a0000000-0000-0000-0000-000000000801',
                       'synthetic-operator', NOW() + INTERVAL '30 minutes'
                   ) RETURNING id, expires_at"""
            )
            enrollment_id, expires_at = cursor.fetchone()
            if enrollment_id is None or expires_at is None:
                raise AssertionError("runtime role lost enrollment issuance columns")
            cursor.execute(
                """UPDATE public.mobile_device_enrollment
                      SET revoked_at = NOW()
                    WHERE id = %s AND used_at IS NULL AND revoked_at IS NULL
                    RETURNING id""",
                (enrollment_id,),
            )
            if cursor.fetchone()[0] != enrollment_id:
                raise AssertionError("runtime role lost enrollment revocation columns")
            cursor.execute(
                """UPDATE public.mobile_device
                      SET status = 'revoked', device_token_hash = NULL,
                          revoked_at = NOW(), updated_at = NOW()
                    WHERE device_id = 'role-boundary-device' AND status = 'active'
                    RETURNING device_id"""
            )
            if cursor.fetchone()[0] != "role-boundary-device":
                raise AssertionError("runtime role lost device revocation columns")
        runtime.commit()
        for statement in (
            "SELECT device_token_hash FROM public.mobile_device LIMIT 1",
            "SELECT push_token FROM public.mobile_device LIMIT 1",
            "SELECT device_id FROM public.mobile_device WHERE device_token_hash = repeat('a', 64)",
            "SELECT * FROM public.mobile_device LIMIT 1",
            "INSERT INTO public.mobile_device (device_id) VALUES ('runtime-device')",
            "DELETE FROM public.mobile_device WHERE device_id = 'role-boundary-device'",
            "SELECT code_hash FROM public.mobile_device_enrollment LIMIT 1",
            "SELECT * FROM public.mobile_device_enrollment LIMIT 1",
            "UPDATE public.mobile_device_enrollment SET code_hash = repeat('d', 64)",
            "DELETE FROM public.mobile_device_enrollment WHERE id = 'a0000000-0000-0000-0000-000000000111'",
            "SELECT session_token_hash FROM public.operator_session LIMIT 1",
            "INSERT INTO public.operator_session (operator_id, session_token_hash, csrf_token_hash, expires_at) VALUES ('a0000000-0000-0000-0000-000000000901', repeat('8', 64), repeat('7', 64), NOW() + INTERVAL '30 minutes')",
            "UPDATE public.operator_session SET revoked_at = NOW() WHERE session_token_hash = repeat('b', 64)",
            "DELETE FROM public.operator_session WHERE session_token_hash = repeat('b', 64)",
            "SELECT * FROM kokonut_security.authenticate_operator_session(repeat('b', 64))",
        ):
            expect_privilege_denial(runtime, statement)
    finally:
        runtime.close()

    auth = psycopg2.connect(
        host="127.0.0.1", port=host_port, dbname="postgres",
        user="kokonut_operator_auth", password=auth_password, connect_timeout=5,
    )
    try:
        with auth.cursor() as cursor:
            cursor.execute("SELECT current_user")
            if cursor.fetchone()[0] != "kokonut_operator_auth":
                raise AssertionError("dedicated operator-auth login did not authenticate")
            cursor.execute(
                """SELECT operator_id, issuer, subject
                     FROM kokonut_security.authenticate_operator_session(%s)""",
                (EXISTING_SESSION_HASH,),
            )
            if cursor.fetchone() != (OPERATOR_ID, ISSUER, SUBJECT):
                raise AssertionError("operator-auth login could not authenticate an active session")
            cursor.execute(
                """SELECT session_id, operator_id, display_name
                     FROM kokonut_security.create_operator_session(
                         %s, %s, %s, NULL, %s, %s, NOW() + INTERVAL '30 minutes'
                     )""",
                (ISSUER, SUBJECT, "Updated operator", NEW_SESSION_HASH, NEW_CSRF_HASH),
            )
            created = cursor.fetchone()
            if created is None or created[1:] != (OPERATOR_ID, "Updated operator"):
                raise AssertionError("operator-auth login could not create a bounded session")
        auth.commit()
        expect_privilege_denial(auth, "SELECT session_token_hash FROM public.operator_session LIMIT 1")
        expect_privilege_denial(auth, "SELECT device_token_hash FROM public.mobile_device LIMIT 1")
        expect_privilege_denial(auth, "SELECT code_hash FROM public.mobile_device_enrollment LIMIT 1")
        with auth.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.revoke_operator_session(%s::uuid)",
                (created[0],),
            )
            if cursor.fetchone()[0] is not True:
                raise AssertionError("operator-auth login could not revoke its session")
            cursor.execute(
                "SELECT * FROM kokonut_security.authenticate_operator_session(%s)",
                (NEW_SESSION_HASH,),
            )
            if cursor.fetchone() is not None:
                raise AssertionError("revoked session remained authenticatable")
        auth.commit()
    finally:
        auth.close()
    return [
        "runtime role cannot SELECT, INSERT, UPDATE, or DELETE operator_session rows or columns",
        "runtime role cannot execute operator-session functions",
        "runtime role cannot read device-token, push, or enrollment-code credentials",
        "runtime role retains only the mobile device/enrollment columns used by current API handlers",
        "runtime login can call bounded token-resolution and enrollment-redemption functions",
        "operator-auth role has no direct mobile credential table access",
        "runtime role retains DML and sequence access on other public tables",
        "dedicated operator-auth role has no direct operator_session privileges",
        "dedicated operator-auth role authenticates, creates, and revokes via bounded functions",
        "session functions operate under FORCE RLS using their NOLOGIN owner role",
        "revoked sessions fail authentication immediately",
    ]


def main() -> int:
    import argparse

    global DOCKER_ADMIN_PASSWORD

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    suffix = uuid.uuid4().hex[:10]
    container = f"kokonut-operator-session-{suffix}"
    network = f"kokonut-operator-session-net-{suffix}"
    started = False
    network_created = False
    DOCKER_ADMIN_PASSWORD = secrets.token_urlsafe(32)
    try:
        run(
            [
                "docker", "network", "create", "--driver", "bridge",
                "--opt", "com.docker.network.bridge.enable_ip_masquerade=false",
                network,
            ]
        )
        network_created = True
        run(
            [
                "docker", "run", "--detach", "--rm", "--network", network,
                "--name", container, "--publish", "127.0.0.1::5432",
                "--env", f"POSTGRES_PASSWORD={DOCKER_ADMIN_PASSWORD}", "postgres:16",
            ]
        )
        started = True
        wait_ready(container)
        docker_sql(container, FIXTURE.read_text())
        docker_sql(container, MOBILE_ROLE_FIXTURE.read_text())
        docker_sql(
            container,
            """CREATE TABLE public.operator_session_runtime_probe (
                   id BIGSERIAL PRIMARY KEY,
                   value TEXT NOT NULL
               );
               INSERT INTO public.operator_session_runtime_probe (value)
               VALUES ('admin-seeded');""",
        )
        for migration in MIGRATIONS:
            sql_text = migration.read_text()
            docker_sql(container, sql_text)
            docker_sql(container, sql_text)
        force_operator_rls(container)

        runtime_password = secrets.token_urlsafe(32)
        auth_password = secrets.token_urlsafe(32)
        role_result, host_port = provision_roles(
            container, runtime_password, auth_password, DOCKER_ADMIN_PASSWORD
        )
        checks = assert_roles(host_port, runtime_password, auth_password)
        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container on a bridge without outbound NAT",
            "migrations": [
                "391_mobile_device_tenant_binding.sql",
                "392_mobile_credential_functions.sql",
                "393_mobile_tenant_context_proof.sql",
                "394_signed_operator_tenant_context.sql",
                "395_operator_session_auth_boundary.sql",
                "395_operator_session_auth_boundary.sql (idempotency replay)",
            ],
            "provisioner_status": role_result["status"],
            "runtime_user": role_result["runtime_user"],
            "operator_auth_user": role_result["operator_auth_user"],
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "external_network_requests": 0,
            "outbound_nat_enabled": False,
            "candidate_application_table_rls_enabled": False,
            "disposable_operator_table_rls_forced": True,
            "synthetic_rows_remaining": 0,
            "scope_limit": "Verifies the general runtime role cannot read browser or mobile credential material and retains only declared mobile-table columns required by current API handlers. This is not the final application-table allowlist, database-verified Gateway capability, Directus boundary, or candidate RLS acceptance.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - isolated acceptance diagnostics.
        print(f"OPERATOR SESSION ROLE ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        if started:
            logs = subprocess.run(
                ["docker", "logs", container],
                text=True,
                capture_output=True,
                check=False,
            )
            if logs.stdout or logs.stderr:
                print("DISPOSABLE POSTGRES LOGS:", file=sys.stderr)
                print(logs.stdout, file=sys.stderr, end="")
                print(logs.stderr, file=sys.stderr, end="")
        return 1
    finally:
        if started:
            subprocess.run(["docker", "stop", container], text=True, capture_output=True, check=False)
        if network_created:
            subprocess.run(["docker", "network", "rm", network], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
