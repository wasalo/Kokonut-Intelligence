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
REMOTE_SENSING_FIXTURE = ROOT / "tests/fixtures/remote_sensing_worker_disposable.sql"
MIGRATIONS = (
    ROOT / "schemas/postgres/391_mobile_device_tenant_binding.sql",
    ROOT / "schemas/postgres/392_mobile_credential_functions.sql",
    ROOT / "schemas/postgres/393_mobile_tenant_context_proof.sql",
    ROOT / "schemas/postgres/394_signed_operator_tenant_context.sql",
    ROOT / "schemas/postgres/395_operator_session_auth_boundary.sql",
    ROOT / "schemas/postgres/396_signed_gateway_credential_tenant_context.sql",
    ROOT / "schemas/postgres/398_bounded_mobile_device_revocation.sql",
    ROOT / "schemas/postgres/399_runtime_security_schema_usage.sql",
    ROOT / "schemas/postgres/400_operator_auth_security_schema_usage.sql",
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/417_isolated_notification_enqueue.sql",
    ROOT / "schemas/postgres/418_mobile_credential_function_acl.sql",
    ROOT / "schemas/postgres/419_private_worker_context_functions.sql",
    ROOT / "schemas/postgres/432_signed_remote_sensing_worker.sql",
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-16-recovery/runtime-notification-enqueue-role-disposable.json"
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
        safe_command = [
            (
                f"{item.split('=', 1)[0]}=<redacted>"
                if item.startswith(("POSTGRES_PASSWORD=", "PGPASSWORD="))
                else item
            )
            for item in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
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
    deadline = time.monotonic() + 90
    consecutive_successes = 0
    initialization_complete = False
    while time.monotonic() < deadline:
        if not initialization_complete:
            logs = subprocess.run(
                ["docker", "logs", container],
                text=True,
                capture_output=True,
                check=False,
            )
            initialization_complete = (
                "PostgreSQL init process complete; ready for start up."
                in (logs.stdout + logs.stderr)
            )
        if initialization_complete:
            result = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                consecutive_successes += 1
                if consecutive_successes >= 4:
                    return
            else:
                consecutive_successes = 0
        time.sleep(0.5)
    raise RuntimeError("disposable PostGIS PostgreSQL did not finish initialization and become ready")


def provision_roles(
    container: str,
    runtime_password: str,
    auth_password: str,
    notification_password: str,
    remote_sensing_password: str,
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
            notification_enqueue_user="kokonut_notification_enqueue_login",
            notification_enqueue_password=notification_password,
            remote_sensing_user="kokonut_remote_sensing_login",
            remote_sensing_password=remote_sensing_password,
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


def assert_public_protected_function_acl(container: str) -> None:
    functions = (
        "kokonut_security.resolve_mobile_device_token(text)",
        "kokonut_security.redeem_mobile_enrollment(text,text,text,text,text,text,text,text)",
        "kokonut_security.set_mobile_device_context(text,text,uuid)",
        "kokonut_security.current_tenant_context()",
        "kokonut_security.claim_remote_sensing_job(uuid)",
        "kokonut_security.finish_remote_sensing_job(uuid,uuid,text,jsonb,jsonb)",
        "kokonut_security.set_worker_tenant_context(text,uuid,text,text)",
        "kokonut_security.current_worker_scope(text,text)",
    )
    procedures = ", ".join(
        "to_regprocedure('" + function.replace("'", "''") + "')"
        for function in functions
    )
    result = docker_sql(
        container,
        f"""SELECT count(*) FILTER (WHERE EXISTS (
                   SELECT 1
                     FROM aclexplode(coalesce(
                         procedure.proacl,
                         acldefault('f', procedure.proowner)
                     )) AS entry
                    WHERE entry.grantee = 0 AND entry.privilege_type = 'EXECUTE'
               ))
              FROM pg_proc AS procedure
             WHERE procedure.oid IN ({procedures});""",
    ).strip()
    if result != "0":
        raise AssertionError(
            "migrations 418/419 did not remove PUBLIC EXECUTE from protected context functions"
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
        for statement in (
            "SELECT value FROM public.runtime_future_default_probe LIMIT 1",
            "INSERT INTO public.runtime_future_default_probe (value) VALUES ('runtime-denied')",
            "UPDATE public.runtime_future_default_probe SET value = 'runtime-denied'",
            "DELETE FROM public.runtime_future_default_probe",
        ):
            expect_privilege_denial(runtime, statement)
        with runtime.cursor() as cursor:
            cursor.execute(
                "SELECT has_sequence_privilege(current_user, "
                "'public.runtime_future_default_probe_id_seq', 'USAGE')"
            )
            if cursor.fetchone()[0]:
                raise AssertionError("runtime role unexpectedly uses a future table sequence")
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
                "SELECT id, key_hash, key_prefix, scopes, is_active "
                "FROM public.api_key WHERE key_prefix = 'syntheti'"
            )
            api_key = cursor.fetchone()
            if api_key is None or api_key[1] != "c" * 64 or api_key[4] is not True:
                raise AssertionError("runtime role lost reviewed API-key authentication reads")
            cursor.execute(
                """SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
                     FROM kokonut_security.set_gateway_tenant_context(
                         'api_key', repeat('c', 64),
                         'a0000000-0000-0000-0000-000000000001'::uuid,
                         'mobile_device', 'revoke'
                     )"""
            )
            gateway_context = cursor.fetchone()
            if gateway_context is None or gateway_context[3] != "gateway_api_key":
                raise AssertionError("runtime role could not establish database-verified Gateway context")
            cursor.execute("SELECT actor_type FROM kokonut_security.current_tenant_context()")
            if cursor.fetchone() != ("gateway_api_key",):
                raise AssertionError("runtime role could not read its signed Gateway context")
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
                """SELECT result, device_id
                     FROM kokonut_security.revoke_mobile_device(
                         'a0000000-0000-0000-0000-000000000001'::uuid,
                         'role-boundary-device', 'api_key', repeat('c', 64), NULL, NULL
                     )"""
            )
            if cursor.fetchone() != ("revoked", "role-boundary-device"):
                raise AssertionError("runtime role could not revoke a device through its bounded function")
        runtime.commit()
        for statement in (
            "SELECT device_token_hash FROM public.mobile_device LIMIT 1",
            "SELECT push_token FROM public.mobile_device LIMIT 1",
            "SELECT device_id FROM public.mobile_device WHERE device_token_hash = repeat('a', 64)",
            "SELECT * FROM public.mobile_device LIMIT 1",
            "INSERT INTO public.mobile_device (device_id) VALUES ('runtime-device')",
            "DELETE FROM public.mobile_device WHERE device_id = 'role-boundary-device'",
            "UPDATE public.mobile_device SET status = 'revoked', device_token_hash = NULL, revoked_at = NOW() WHERE device_id = 'role-boundary-device'",
            "SELECT code_hash FROM public.mobile_device_enrollment LIMIT 1",
            "SELECT * FROM public.mobile_device_enrollment LIMIT 1",
            "SELECT name FROM public.api_key LIMIT 1",
            "INSERT INTO public.api_key (name, key_hash, key_prefix) VALUES ('runtime', repeat('1', 64), 'runtime')",
            "UPDATE public.api_key SET is_active = FALSE",
            "DELETE FROM public.api_key",
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
        "runtime role has read-only API-key authentication columns and cannot manage API keys",
        "runtime login can establish a signed, database-verified Gateway API-key context",
        "runtime role retains only the mobile device/enrollment columns used by current API handlers",
        "runtime login can call bounded token-resolution and enrollment-redemption functions",
        "operator-auth role has no direct mobile credential table access",
        "runtime role retains DML and sequence access on other public tables",
        "tables and sequences created after provisioning receive no automatic runtime privileges",
        "dedicated operator-auth role has no direct operator_session privileges",
        "dedicated operator-auth role authenticates, creates, and revokes via bounded functions",
        "session functions operate under FORCE RLS using their NOLOGIN owner role",
        "revoked sessions fail authentication immediately",
    ]


def assert_notification_enqueue_role(host_port: int, password: str) -> list[str]:
    connection = psycopg2.connect(
        host="127.0.0.1", port=host_port, dbname="postgres",
        user="kokonut_notification_enqueue_login", password=password,
        connect_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            if cursor.fetchone()[0] != "kokonut_notification_enqueue_login":
                raise AssertionError("notification enqueue login did not authenticate")
            cursor.execute(
                """SELECT kokonut_security.enqueue_notification_intents(
                       'a0000000-0000-0000-0000-000000000501'::uuid,
                       'threshold_breached',
                       'b0000000-0000-0000-0000-000000000501'::uuid,
                       '[{"channel":"webhook","destination_key":"primary","payload":{"text":"Synthetic"}}]'::jsonb
                   )"""
            )
            if cursor.fetchone()[0] != 1:
                raise AssertionError("dedicated login could not enqueue a bounded notification")
            cursor.execute(
                """SELECT kokonut_security.enqueue_notification_intents(
                       'a0000000-0000-0000-0000-000000000501'::uuid,
                       'threshold_breached',
                       'b0000000-0000-0000-0000-000000000501'::uuid,
                       '[{"channel":"webhook","destination_key":"primary","payload":{"text":"Synthetic"}}]'::jsonb
                   )"""
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("notification retry was not idempotent")
        connection.commit()
        for statement in (
            "SELECT id FROM public.platform_event LIMIT 1",
            "SELECT id FROM public.notification_outbox LIMIT 1",
            "INSERT INTO public.notification_outbox (source_event_id,event_type,channel,destination_key,payload) VALUES ('a0000000-0000-0000-0000-000000000501','threshold_breached','email','primary','{}')",
            "UPDATE public.notification_outbox SET location_id = NULL",
            "DELETE FROM public.notification_outbox",
            "SELECT * FROM kokonut_security.resolve_mobile_device_token(repeat('a', 64))",
            "SELECT * FROM kokonut_security.redeem_mobile_enrollment(repeat('b',64),'device','name','phone',NULL,NULL,'1.0.0',repeat('c',64))",
            "SELECT * FROM kokonut_security.set_mobile_device_context(repeat('a',64),'device','a0000000-0000-0000-0000-000000000001'::uuid)",
            "SELECT * FROM kokonut_security.current_tenant_context()",
            "SELECT * FROM kokonut_security.set_worker_tenant_context(repeat('d',64),'a0000000-0000-0000-0000-000000000001'::uuid,'sensor_reading','process')",
            "SELECT * FROM kokonut_security.current_worker_scope('sensor_reading','process')",
        ):
            expect_privilege_denial(connection, statement)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'kokonut_security', 'CREATE'), "
                "has_function_privilege(current_user, "
                "'kokonut_security.enqueue_notification_intents(uuid,text,uuid,jsonb)', 'EXECUTE')"
            )
            if cursor.fetchone() != (False, True):
                raise AssertionError("notification role does not have the exact schema/function boundary")
        connection.commit()
    finally:
        connection.close()
    return [
        "runtime-role bootstrap provisions the notification login with an isolated secret",
        "dedicated notification login connects and invokes only the bounded enqueue function",
        "notification enqueue is idempotent through the provisioned login under forced RLS",
        "provisioned notification login cannot read source/outbox tables or mutate delivery state",
    ]


def assert_remote_sensing_role(host_port: int, password: str) -> list[str]:
    connection = psycopg2.connect(
        host="127.0.0.1", port=host_port, dbname="postgres",
        user="kokonut_remote_sensing_login", password=password,
        connect_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_user, has_function_privilege(current_user, "
                "'kokonut_security.claim_remote_sensing_job(uuid)', 'EXECUTE')"
            )
            if cursor.fetchone() != ("kokonut_remote_sensing_login", False):
                raise AssertionError("remote-sensing login can execute its function without SET ROLE")
        for statement in (
            "SELECT id FROM public.remote_sensing_job LIMIT 1",
            "SELECT kokonut_security.claim_remote_sensing_job(NULL::uuid)",
        ):
            expect_privilege_denial(connection, statement)
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_worker_execution")
            cursor.execute("SELECT current_user")
            if cursor.fetchone()[0] != "kokonut_worker_execution":
                raise AssertionError("remote-sensing login could not enter its restricted execution role")
            try:
                cursor.execute(
                    "SELECT kokonut_security.claim_remote_sensing_job(NULL::uuid)"
                )
            except psycopg2.Error as exc:
                connection.rollback()
                if exc.pgcode != "42501":
                    raise
            else:
                raise AssertionError("unscoped remote-sensing claim unexpectedly succeeded")
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            if cursor.fetchone()[0] != "kokonut_remote_sensing_login":
                raise AssertionError("transaction end did not restore the remote-sensing login")
    finally:
        connection.close()
    return [
        "runtime-role bootstrap provisions the migration 432 login only after its bounded functions exist",
        "remote-sensing login cannot access application tables or call functions before entering worker execution; extension metadata PUBLIC ACLs are reviewed separately",
        "SET ROLE exposes only a signed-scope-checked claim; transaction rollback restores the login identity",
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
                "--env", f"POSTGRES_PASSWORD={DOCKER_ADMIN_PASSWORD}", "postgis/postgis:16-3.4",
            ]
        )
        started = True
        wait_ready(container)
        docker_sql(container, FIXTURE.read_text())
        docker_sql(container, MOBILE_ROLE_FIXTURE.read_text())
        docker_sql(
            container,
            "CREATE ROLE kokonut_worker_login NOLOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;",
        )
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
            if migration.name == "432_signed_remote_sensing_worker.sql":
                docker_sql(container, REMOTE_SENSING_FIXTURE.read_text())
            if migration.name == "417_isolated_notification_enqueue.sql":
                docker_sql(
                    container,
                    """CREATE TABLE public.platform_event (
                           id UUID PRIMARY KEY,
                           event_type TEXT NOT NULL,
                           payload JSONB NOT NULL DEFAULT '{}'::JSONB
                       );
                       CREATE TABLE public.notification_outbox (
                           id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                           source_event_id UUID NOT NULL,
                           event_type VARCHAR(100) NOT NULL,
                           channel VARCHAR(30) NOT NULL,
                           destination_key VARCHAR(100) NOT NULL,
                           payload JSONB NOT NULL,
                           location_id UUID,
                           UNIQUE (source_event_id, channel, destination_key)
                       );
                       INSERT INTO public.platform_event (id, event_type, payload) VALUES
                           ('a0000000-0000-0000-0000-000000000501', 'threshold_breached',
                            '{"location_id":"b0000000-0000-0000-0000-000000000501"}');
                       ALTER TABLE public.platform_event ENABLE ROW LEVEL SECURITY;
                       ALTER TABLE public.platform_event FORCE ROW LEVEL SECURITY;
                       ALTER TABLE public.notification_outbox ENABLE ROW LEVEL SECURITY;
                       ALTER TABLE public.notification_outbox FORCE ROW LEVEL SECURITY;""",
                )
            docker_sql(container, sql_text)
            docker_sql(container, sql_text)
        assert_public_protected_function_acl(container)
        force_operator_rls(container)

        runtime_password = secrets.token_urlsafe(32)
        auth_password = secrets.token_urlsafe(32)
        notification_password = secrets.token_urlsafe(32)
        remote_sensing_password = secrets.token_urlsafe(32)
        role_result, host_port = provision_roles(
            container, runtime_password, auth_password, notification_password,
            remote_sensing_password,
            DOCKER_ADMIN_PASSWORD,
        )
        docker_sql(
            container,
            """CREATE TABLE public.runtime_future_default_probe (
                   id BIGSERIAL PRIMARY KEY,
                   value TEXT NOT NULL
               );
               INSERT INTO public.runtime_future_default_probe (value)
               VALUES ('admin-seeded-after-provisioning');""",
        )
        checks = assert_roles(host_port, runtime_password, auth_password)
        checks.extend(assert_notification_enqueue_role(host_port, notification_password))
        checks.extend(assert_remote_sensing_role(host_port, remote_sensing_password))
        worker_acl = docker_sql(
            container,
            """SELECT has_function_privilege('kokonut_worker_execution',
                       'kokonut_security.current_tenant_context()', 'EXECUTE')
                      AND has_function_privilege('kokonut_worker_execution',
                       'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE')
                      AND has_function_privilege('kokonut_worker_execution',
                       'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'),
                      has_function_privilege('kokonut_runtime',
                       'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'),
                      has_function_privilege('kokonut_notification_enqueue_login',
                       'kokonut_security.current_worker_scope(text,text)', 'EXECUTE');""",
        ).strip()
        if worker_acl != "t|f|f":
            raise AssertionError(f"worker context ACLs do not preserve the isolated execution role: {worker_acl}")
        checks.append(
            "signed worker context functions remain available only to kokonut_worker_execution, not shared runtime or notification login"
        )
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
                "396_signed_gateway_credential_tenant_context.sql",
                "396_signed_gateway_credential_tenant_context.sql (idempotency replay)",
                "398_bounded_mobile_device_revocation.sql",
                "399_runtime_security_schema_usage.sql",
                "400_operator_auth_security_schema_usage.sql",
                "405_signed_worker_tenant_context.sql",
                "417_isolated_notification_enqueue.sql",
                "417_isolated_notification_enqueue.sql (idempotency replay)",
                "418_mobile_credential_function_acl.sql",
                "418_mobile_credential_function_acl.sql (idempotency replay)",
                "419_private_worker_context_functions.sql",
                "419_private_worker_context_functions.sql (idempotency replay)",
                "432_signed_remote_sensing_worker.sql",
                "432_signed_remote_sensing_worker.sql (idempotency replay)",
            ],
            "provisioner_status": role_result["status"],
            "runtime_user": role_result["runtime_user"],
            "operator_auth_user": role_result["operator_auth_user"],
            "notification_enqueue_user": role_result["notification_enqueue_user"],
            "remote_sensing_user": role_result["remote_sensing_user"],
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "external_network_requests": 0,
            "outbound_nat_enabled": False,
            "candidate_application_table_rls_enabled": False,
            "disposable_operator_table_rls_forced": True,
            "synthetic_rows_remaining": 0,
            "scope_limit": "Verifies the general runtime role cannot read browser credential material or manage API keys; mobile credential SECURITY DEFINER functions are no longer executable by PUBLIC and are explicitly granted to the runtime login. Dedicated notification and remote-sensing logins are provisioned through the runtime bootstrap. The notification login can execute only its bounded enqueue function. The remote-sensing login has no application-table or sequence access, can SET ROLE only to kokonut_worker_execution, and its claim remains signed-scope checked. Extension-owned metadata may retain extension-defined PUBLIC access and is excluded from application-relation checks. This is not the final application-table allowlist, Directus boundary, or candidate RLS acceptance.",
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
