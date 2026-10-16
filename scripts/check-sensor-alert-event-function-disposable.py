#!/usr/bin/env python3
"""Exercise bounded sensor-alert event publication in disposable PostgreSQL 16."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = (
    ROOT / "tests/fixtures/worker_tenant_context_disposable.sql",
    ROOT / "tests/fixtures/sensor_anomaly_effect_functions_disposable.sql",
)
EVENT_FIXTURE = ROOT / "tests/fixtures/sensor_alert_event_function_disposable.sql"
MIGRATIONS = (
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/406_sensor_anomaly_location_lineage.sql",
    ROOT / "schemas/postgres/407_sensor_anomaly_effect_functions.sql",
    ROOT / "schemas/postgres/408_sensor_alert_event_function.sql",
)
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/"
    "sensor-alert-event-function-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
READING_ID = "a0000000-0000-0000-0000-000000000021"
EVENT_ID = "a0000000-0000-0000-0000-000000000031"
ALERT_ID = "a0000000-0000-0000-0000-000000000041"
OTHER_LOCATION_ALERT_ID = "a0000000-0000-0000-0000-000000000042"
RULE_ID = "a0000000-0000-0000-0000-000000000052"
ALERT_EVENT_ID = "a0000000-0000-0000-0000-000000000061"
RESOURCE = "sensor_reading"
ACTION = "process"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()

PUBLISH_SQL = """
SELECT kokonut_security.publish_sensor_alert_event(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
RESERVE_SQL = """
SELECT kokonut_security.reserve_sensor_anomaly_effect(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
OUTCOME_SQL = """
SELECT kokonut_security.record_sensor_anomaly_effect_outcome(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'alert_created', %s::uuid
)
"""


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
            "POSTGRES_PASSWORD=<redacted>" if part.startswith("POSTGRES_PASSWORD=") else part
            for part in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable_checks = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode == 0:
            stable_checks += 1
            if stable_checks >= 4:
                return
        else:
            stable_checks = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user=user,
        password=password,
        connect_timeout=5,
    )


def set_context(connection) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    context = set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource=RESOURCE,
        action=ACTION,
    )
    if context.tenant_id != TENANT_ID or context.location_id != LOCATION_ID:
        raise AssertionError("signed worker setter returned an unexpected tenant scope")


def publish(connection, *, event_id=ALERT_EVENT_ID, location_id=LOCATION_ID, alert_id=ALERT_ID):
    with connection.cursor() as cursor:
        cursor.execute(
            PUBLISH_SQL,
            (event_id, EVENT_ID, READING_ID, RULE_ID, alert_id, location_id),
        )
        return cursor.fetchone()[0]


def expect_sqlstate(connection, params: tuple, expected: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(PUBLISH_SQL, params)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != expected:
            raise AssertionError(
                f"{label}: expected SQLSTATE {expected}, received {exc.pgcode}"
            ) from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: publication unexpectedly succeeded")


def expect_direct_denial(connection, statement: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            cursor.execute(statement)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != "42501":
            raise AssertionError(f"{label}: expected 42501, received {exc.pgcode}") from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: direct queue access unexpectedly succeeded")


def expected_payload() -> dict:
    return {
        "alert_id": ALERT_ID,
        "sensor_device_id": "a0000000-0000-0000-0000-000000000011",
        "sensor_id": "a0000000-0000-0000-0000-000000000011",
        "severity": "critical",
        "rule_name": "Synthetic threshold 052",
        "reading_value": 46.25,
        "threshold_value": 42.0,
        "message": "Synthetic critical soil alert",
        "location_id": LOCATION_ID,
    }


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    image = os.getenv("ANOMALY_EVENT_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-event-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={admin_password}",
                "-p",
                "127.0.0.1::5432",
                image,
            ]
        )
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURES[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURES[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[2].read_text(encoding="utf-8"))
        docker_sql(docker, container, EVENT_FIXTURE.read_text(encoding="utf-8"))
        migration_sql = MIGRATIONS[3].read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 408 applies and replays after signed context and receipt migrations")
        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'sensor-anomaly');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
                '{RESOURCE}', '{ACTION}', 'disposable fixture'
            );
            """,
        )
        mapped = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not mapped:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(mapped[0].rsplit(":", 1)[1])
        worker = connect(port, "kokonut_worker_login", "worker-execution-fixture")
        runtime = connect(port, "kokonut_runtime", "worker-runtime-fixture")
        operator_auth = connect(port, "kokonut_operator_auth", "worker-auth-fixture")
        admin = connect(port, "postgres", admin_password)
        try:
            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute(RESERVE_SQL, (EVENT_ID, READING_ID, RULE_ID, LOCATION_ID))
                if cursor.fetchone()[0] is not True:
                    raise AssertionError("fixture receipt reservation did not insert")
                cursor.execute(
                    OUTCOME_SQL,
                    (EVENT_ID, READING_ID, RULE_ID, LOCATION_ID, ALERT_ID),
                )
                if cursor.fetchone()[0] is not True:
                    raise AssertionError("fixture receipt did not link to the synthetic alert")
            worker.commit()
            checks.append("migration 407 receipt functions create the source proof required by event publication")

            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
                "42501",
                "unsigned alert event publication",
            )
            checks.append("event publication requires a signed worker scope")

            set_context(worker)
            if publish(worker) is not True:
                raise AssertionError("first valid alert event was not inserted")
            worker.commit()
            checks.append("matching alert_created receipt publishes one canonical event")

            set_context(worker)
            if publish(worker) is not False:
                raise AssertionError("identical event retry was not suppressed")
            worker.commit()
            checks.append("same event ID and payload are idempotent on retry")

            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT event_type, source_table, source_id::text, payload, priority, status, max_retries "
                    "FROM public.platform_event WHERE id = %s::uuid",
                    (ALERT_EVENT_ID,),
                )
                event_row = cursor.fetchone()
                if event_row != (
                    "sensor_alert",
                    "sensor_alert",
                    ALERT_ID,
                    expected_payload(),
                    "high",
                    "pending",
                    3,
                ):
                    raise AssertionError(f"event payload or initial state differs: {event_row}")
            checks.append("event payload and initial priority/status/retry values match the current handler contract")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.platform_event SET status = 'completed', processed_at = NOW() "
                    "WHERE id = %s::uuid",
                    (ALERT_EVENT_ID,),
                )
            admin.commit()
            set_context(worker)
            if publish(worker) is not False:
                raise AssertionError("completed event did not remain idempotent")
            worker.commit()
            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM public.platform_event WHERE id = %s::uuid",
                    (ALERT_EVENT_ID,),
                )
                if cursor.fetchone()[0] != "completed":
                    raise AssertionError("event retry modified durable queue status")
            checks.append("event retry leaves completed queue state untouched")

            set_context(worker)
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, "a0000000-0000-0000-0000-000000000032", READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
                "42501",
                "mismatched source event",
            )
            set_context(worker)
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, EVENT_ID, READING_ID, RULE_ID, OTHER_LOCATION_ALERT_ID, LOCATION_ID),
                "42501",
                "cross-location alert",
            )
            set_context(worker)
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, EVENT_ID, READING_ID, RULE_ID, ALERT_ID, OTHER_LOCATION_ID),
                "42501",
                "cross-location requested scope",
            )
            checks.append("wrong source, alert, and requested location are rejected")

            set_context(worker)
            expect_sqlstate(
                worker,
                (EVENT_ID, EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
                "23505",
                "event ID collision",
            )
            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT event_type, source_table, payload FROM public.platform_event WHERE id = %s::uuid",
                    (EVENT_ID,),
                )
                source_event = cursor.fetchone()
                if source_event[0] != "sensor_reading" or source_event[1] != "sensor_reading":
                    raise AssertionError("event ID collision altered the source event")
            checks.append("stable event ID collision fails without replacing source content")

            with admin.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT has_any_column_privilege(
                               'kokonut_worker_execution', 'public.platform_event', 'SELECT'
                           ),
                           has_any_column_privilege(
                               'kokonut_worker_execution', 'public.platform_event', 'INSERT'
                           ),
                           has_any_column_privilege(
                               'kokonut_worker_execution', 'public.platform_event', 'UPDATE'
                           ),
                           has_table_privilege(
                               'kokonut_worker_execution', 'public.platform_event', 'DELETE'
                           ),
                           has_function_privilege(
                               'kokonut_worker_execution',
                               'kokonut_security.publish_sensor_alert_event(uuid,uuid,uuid,uuid,uuid,uuid)',
                               'EXECUTE'
                           )
                    """
                )
                privilege_row = cursor.fetchone()
                if privilege_row != (False, False, False, False, True):
                    raise AssertionError(f"unexpected worker event privileges: {privilege_row}")
            for connection, role_name in ((runtime, "kokonut_runtime"), (operator_auth, "kokonut_operator_auth")):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_function_privilege(current_user, %s, 'EXECUTE')",
                        ("kokonut_security.publish_sensor_alert_event(uuid,uuid,uuid,uuid,uuid,uuid)",),
                    )
                    if cursor.fetchone()[0]:
                        raise AssertionError(f"{role_name} can execute alert event function")
            checks.append("worker has bounded event EXECUTE only; runtime and operator-auth cannot execute it")

            for statement, label in (
                ("SELECT * FROM public.platform_event", "direct event SELECT"),
                (
                    "INSERT INTO public.platform_event "
                    "(id, event_type, source_table, source_id, payload, priority, status, max_retries) "
                    f"VALUES ('a0000000-0000-0000-0000-000000000062', 'sensor_alert', "
                    f"'sensor_alert', '{ALERT_ID}', '{{}}'::jsonb, 'normal', 'pending', 3)",
                    "direct event INSERT",
                ),
                (
                    "UPDATE public.platform_event SET status = 'processing' "
                    f"WHERE id = '{ALERT_EVENT_ID}'::uuid",
                    "direct event UPDATE",
                ),
                (
                    "DELETE FROM public.platform_event "
                    f"WHERE id = '{ALERT_EVENT_ID}'::uuid",
                    "direct event DELETE",
                ),
            ):
                expect_direct_denial(worker, statement, label)
            checks.append("worker role cannot directly SELECT, INSERT, UPDATE, or DELETE global event rows")

            for connection in (worker, runtime, operator_auth, admin):
                connection.close()
        finally:
            for connection in (worker, runtime, operator_auth, admin):
                if not connection.closed:
                    connection.close()

        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 408 bounded canonical sensor-alert event publication",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS],
            "migration_408_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
            "migration_replay": "passed",
            "command": "python3 scripts/check-sensor-alert-event-function-disposable.py",
            "container_network": "loopback-only published port; runner makes no external requests",
            "checks": [{"result": "passed", "description": item} for item in checks],
            "candidate_or_legacy_database_access": False,
            "worker_credential_printed": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
