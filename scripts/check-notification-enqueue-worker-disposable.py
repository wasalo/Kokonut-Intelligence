#!/usr/bin/env python3
"""Verify the isolated notification enqueue SQL boundary on disposable PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/notification_enqueue_worker_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/417_isolated_notification_enqueue.sql"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/notification-enqueue-worker-disposable.json"
)
LOGIN = "kokonut_notification_enqueue_login"
PASSWORD = secrets.token_urlsafe(32)
ADMIN_PASSWORD = secrets.token_urlsafe(32)
EVENT_LOCATION = "a0000000-0000-0000-0000-000000000001"
LOCATION_ID = "b0000000-0000-0000-0000-000000000001"
STALE_EVENT = "a0000000-0000-0000-0000-000000000002"
OTHER_EVENT = "a0000000-0000-0000-0000-000000000003"
MALFORMED_EVENTS = (
    "a0000000-0000-0000-0000-000000000004",
    "a0000000-0000-0000-0000-000000000005",
    "a0000000-0000-0000-0000-000000000006",
    "a0000000-0000-0000-0000-000000000007",
)


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    expect_success: bool = True,
) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=45,
    )
    output = result.stdout + result.stderr
    if expect_success and result.returncode:
        safe_command = [
            (
                f"{item.split('=', 1)[0]}=<redacted>"
                if item.startswith(("POSTGRES_PASSWORD=", "PGPASSWORD="))
                else item
            )
            for item in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{output}"
        )
    if not expect_success and result.returncode == 0:
        raise AssertionError("expected disposable operation to be denied")
    return output


def docker_sql(docker: str, container: str, statement: str, *, user: str = "postgres", password: str | None = None,
               expect_success: bool = True) -> str:
    command = [docker, "exec", "-i"]
    if password is None and user == "postgres":
        password = ADMIN_PASSWORD
    if password is not None:
        command.extend(["--env", f"PGPASSWORD={password}"])
    command.append(container)
    command.extend(
        [
            "psql", "-h", "127.0.0.1", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
            "-U", user, "-d", "postgres",
        ]
    )
    return run(command, input_text=statement, expect_success=expect_success)


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def call_function(event_id: str, event_type: str, location_id: str | None, intents: object) -> str:
    location = "NULL" if location_id is None else f"{literal(location_id)}::uuid"
    return (
        "SELECT kokonut_security.enqueue_notification_intents("
        f"{literal(event_id)}::uuid, {literal(event_type)}, {location}, "
        f"{literal(json.dumps(intents, separators=(',', ':')))}::jsonb);"
    )


def require_denial(
    docker: str,
    container: str,
    statement: str,
    expected_text: str,
    *,
    user: str = LOGIN,
    password: str = PASSWORD,
) -> None:
    output = docker_sql(
        docker,
        container,
        statement,
        user=user,
        password=password,
        expect_success=False,
    )
    if expected_text not in output:
        raise AssertionError(f"denial did not match expected contract: {output}")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-notification-enqueue-{secrets.token_hex(6)}"
    created = False
    checks: list[str] = []
    migration_sql = MIGRATION.read_text(encoding="utf-8")
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT

    try:
        created = True
        run(
            [
                docker, "run", "-d", "--rm", "--network", "none", "--name", container,
                "-e", f"POSTGRES_PASSWORD={ADMIN_PASSWORD}", "postgres:16-alpine",
            ]
        )
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, migration_sql)
        docker_sql(
            docker,
            container,
            f"ALTER ROLE {LOGIN} WITH LOGIN PASSWORD {literal(PASSWORD)};",
        )
        # Replay after provisioning a login. The migration must retain its safe
        # role attributes, grants, policies and function owner.
        docker_sql(docker, container, migration_sql)
        checks.append("migration 417 applies, promotes only through explicit provisioning, and replays")

        valid_intents = [
            {"channel": "webhook", "destination_key": "primary", "payload": {"text": "Synthetic"}},
            {"channel": "email", "destination_key": "primary", "payload": {"subject": "Synthetic"}},
        ]
        queued = docker_sql(
            docker,
            container,
            call_function(EVENT_LOCATION, "threshold_breached", LOCATION_ID, valid_intents),
            user=LOGIN,
            password=PASSWORD,
        ).strip()
        if queued != "2":
            raise AssertionError(f"expected two new notification intents; got {queued}")
        repeated = docker_sql(
            docker,
            container,
            call_function(EVENT_LOCATION, "threshold_breached", LOCATION_ID, valid_intents),
            user=LOGIN,
            password=PASSWORD,
        ).strip()
        if repeated != "0":
            raise AssertionError(f"repeated notification request was not idempotent: {repeated}")
        checks.append("valid source-matched notification intents enqueue once and replay idempotently under forced RLS")

        stale_intents = [
            {"channel": "directus", "destination_key": "primary", "payload": {"message": "Stale"}}
        ]
        stale_insert = docker_sql(
            docker,
            container,
            call_function(STALE_EVENT, "data_stale", None, stale_intents),
            user=LOGIN,
            password=PASSWORD,
        ).strip()
        if stale_insert != "1":
            raise AssertionError(f"location-free data_stale event failed: {stale_insert}")
        require_denial(
            docker, container,
            call_function(EVENT_LOCATION, "threshold_breached", None, valid_intents),
            "notification location does not match its source event",
        )
        require_denial(
            docker, container,
            call_function(STALE_EVENT, "threshold_breached", None, stale_intents),
            "notification source event is missing or mismatched",
        )
        require_denial(
            docker, container,
            call_function(OTHER_EVENT, "other_event", None, stale_intents),
            "notification enqueue arguments are invalid",
        )
        checks.append("source event existence/type and optional location lineage are enforced")

        malformed = [
            ([{"channel": "sms", "destination_key": "primary", "payload": {}}], "notification intent content is invalid"),
            ([{"channel": "webhook", "destination_key": "primary", "payload": {}, "extra": True}], "notification intent shape is invalid"),
            ([{"channel": "webhook", "destination_key": "primary", "payload": {"text": "x" * 17000}}], "notification intent content is invalid"),
            ([
                {"channel": "webhook", "destination_key": "primary", "payload": {}},
                {"channel": "webhook", "destination_key": "primary", "payload": {}},
            ], "notification intent contains a duplicate destination"),
        ]
        for event_id, (intents, expected) in zip(MALFORMED_EVENTS, malformed):
            require_denial(
                docker, container,
                call_function(event_id, "threshold_breached", LOCATION_ID, intents),
                expected,
            )
        checks.append("channel, exact JSON shape, payload size, and duplicate-destination allowlists are enforced")

        conflict = [{"channel": "webhook", "destination_key": "primary", "payload": {"text": "Changed"}}]
        require_denial(
            docker, container,
            call_function(EVENT_LOCATION, "threshold_breached", LOCATION_ID, conflict),
            "notification identity conflicts with existing content",
        )
        checks.append("same event/channel with changed payload is rejected rather than overwritten")

        direct_denials = (
            ("SELECT id FROM public.platform_event LIMIT 1;", "permission denied for table platform_event"),
            ("SELECT id FROM public.notification_outbox LIMIT 1;", "permission denied for table notification_outbox"),
            ("INSERT INTO public.notification_outbox (source_event_id,event_type,channel,destination_key,payload) VALUES ('a0000000-0000-0000-0000-000000000001','threshold_breached','webhook','primary','{}');", "permission denied for table notification_outbox"),
            ("UPDATE public.notification_outbox SET location_id = NULL;", "permission denied for table notification_outbox"),
            ("DELETE FROM public.notification_outbox;", "permission denied for table notification_outbox"),
            ("UPDATE public.platform_event SET payload = '{}'::jsonb;", "permission denied for table platform_event"),
            ("DELETE FROM public.platform_event;", "permission denied for table platform_event"),
        )
        for statement, expected in direct_denials:
            require_denial(docker, container, statement, expected)
        shared_identity_denial = docker_sql(
            docker,
            container,
            f"SET ROLE {LOGIN}; {call_function(STALE_EVENT, 'data_stale', None, stale_intents)}",
            user="postgres",
            expect_success=False,
        )
        if "notification enqueue requires its dedicated login" not in shared_identity_denial:
            raise AssertionError(f"session identity guard did not reject SET ROLE: {shared_identity_denial}")
        checks.append("dedicated login has function-only access; direct table access and shared SET ROLE are denied")

        rows = docker_sql(
            docker,
            container,
            "SELECT count(*) || '|' || count(*) FILTER (WHERE location_id IS NOT NULL) FROM public.notification_outbox;",
        ).strip()
        rls = docker_sql(
            docker,
            container,
            "SELECT bool_and(relrowsecurity AND relforcerowsecurity)::text FROM pg_class WHERE oid IN ('public.platform_event'::regclass,'public.notification_outbox'::regclass);",
        ).strip()
        if rows != "3|2" or rls != "true":
            raise AssertionError(f"outbox lineage or forced RLS state differs: rows={rows}, rls={rls}")
        checks.append("location lineage remains optional and both source/outbox tables retain FORCE RLS")

        output_payload = {
            "schema_version": 1,
            "date": datetime.now().astimezone().date().isoformat(),
            "scope": "isolated EventBus notification enqueue operation",
            "database": "disposable PostgreSQL 16 container with --network none",
            "migration_sha256": hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
            "result": "passed",
            "checks": [{"result": "passed", "description": item} for item in checks],
            "candidate_or_legacy_database_access": False,
            "network": "disabled for the disposable database container",
            "secret_values_printed": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(output_payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(output_payload, indent=2))
        return 0
    finally:
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )


if __name__ == "__main__":
    raise SystemExit(main())
