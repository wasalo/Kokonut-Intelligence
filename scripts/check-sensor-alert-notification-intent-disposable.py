#!/usr/bin/env python3
"""Exercise bounded sensor-alert notification intents in disposable PostgreSQL 16."""

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
NOTIFICATION_FIXTURE = ROOT / "tests/fixtures/sensor_alert_notification_intent_disposable.sql"
MIGRATIONS = (
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/406_sensor_anomaly_location_lineage.sql",
    ROOT / "schemas/postgres/407_sensor_anomaly_effect_functions.sql",
    ROOT / "schemas/postgres/408_sensor_alert_event_function.sql",
    ROOT / "schemas/postgres/409_sensor_alert_notification_intent.sql",
)
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/"
    "sensor-alert-notification-intent-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"
READING_ID = "a0000000-0000-0000-0000-000000000021"
SOURCE_EVENT_ID = "a0000000-0000-0000-0000-000000000031"
ALERT_ID = "a0000000-0000-0000-0000-000000000041"
RULE_ID = "a0000000-0000-0000-0000-000000000052"
ALERT_EVENT_ID = "a0000000-0000-0000-0000-000000000061"
RESOURCE = "sensor_reading"
ACTION = "process"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
FUNCTION_SIGNATURE = (
    "kokonut_security.enqueue_sensor_alert_notification_intent"
    "(uuid,uuid,uuid,uuid,uuid,uuid,text,text,jsonb)"
)
ENQUEUE_SQL = f"SELECT {FUNCTION_SIGNATURE.split('(')[0]}(%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::jsonb)"
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
PUBLISH_SQL = """
SELECT kokonut_security.publish_sensor_alert_event(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
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
            docker, "exec", "-i", container, "psql", "-X", "-q",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable_checks = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
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
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def set_context(connection) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    context = set_worker_tenant_context(
        connection, credential=RAW_CREDENTIAL, location_id=LOCATION_ID,
        resource=RESOURCE, action=ACTION,
    )
    if context.tenant_id != TENANT_ID or context.location_id != LOCATION_ID:
        raise AssertionError("signed worker setter returned an unexpected tenant scope")


def payload(channel: str = "webhook") -> dict:
    if channel == "webhook":
        return {
            "text": "[CRITICAL] Synthetic critical soil alert",
            "alert_id": ALERT_ID,
            "severity": "critical",
            "message": "Synthetic critical soil alert",
            "sensor_device_id": SENSOR_ID,
            "sensor_name": "Synthetic soil probe",
            "sensor_type": "soil_moisture",
            "location_id": LOCATION_ID,
            "location_name": "Synthetic Farm One",
            "reading_value": 46.25,
            "threshold_value": 42.0,
            "triggered_at": "2026-10-16T12:00:00+00:00",
            "claim_id": None,
        }
    if channel == "directus":
        return {
            "subject": "Sensor Alert: Synthetic soil probe",
            "message": "Synthetic critical soil alert",
            "type": "critical",
            "recipient": "role:00000000-0000-0000-0000-000000000006",
            "status": "unread",
        }
    return {
        "subject": "[CRITICAL] Sensor Alert: Synthetic soil probe",
        "body": "Synthetic alert body\nAlert ID: " + ALERT_ID,
    }


def enqueue(
    connection,
    *,
    event_id=ALERT_EVENT_ID,
    source_event_id=SOURCE_EVENT_ID,
    reading_id=READING_ID,
    rule_id=RULE_ID,
    alert_id=ALERT_ID,
    location_id=LOCATION_ID,
    channel="webhook",
    destination="primary",
    message=None,
):
    selected_payload = payload(channel) if message is None else message
    with connection.cursor() as cursor:
        cursor.execute(
            ENQUEUE_SQL,
            (
                event_id, source_event_id, reading_id, rule_id, alert_id,
                location_id, channel, destination,
                json.dumps(selected_payload, separators=(",", ":")),
            ),
        )
        return cursor.fetchone()[0]


def expect_sqlstate(connection, params: tuple, expected: str, label: str) -> None:
    if isinstance(params[-1], dict):
        params = (*params[:-1], json.dumps(params[-1], separators=(",", ":")))
    try:
        with connection.cursor() as cursor:
            cursor.execute(ENQUEUE_SQL, params)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != expected:
            raise AssertionError(
                f"{label}: expected SQLSTATE {expected}, received {exc.pgcode}"
            ) from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: operation unexpectedly succeeded")


def direct_denial(connection, statement: str, label: str) -> None:
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


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("ANOMALY_NOTIFICATION_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-notification-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={admin_password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURES[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURES[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[2].read_text(encoding="utf-8"))
        docker_sql(docker, container, EVENT_FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[3].read_text(encoding="utf-8"))
        docker_sql(docker, container, NOTIFICATION_FIXTURE.read_text(encoding="utf-8"))
        migration_sql = MIGRATIONS[4].read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 409 applies and replays after worker context and effect migrations")

        docker_sql(
            docker, container,
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
        port_lines = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_lines:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_lines[0].rsplit(":", 1)[1])
        worker = connect(port, "kokonut_worker_login", "worker-execution-fixture")
        runtime = connect(port, "kokonut_runtime", "worker-runtime-fixture")
        operator_auth = connect(port, "kokonut_operator_auth", "worker-auth-fixture")
        admin = connect(port, "postgres", admin_password)
        try:
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
                 ALERT_ID, LOCATION_ID, "webhook", "primary",
                 json.dumps(payload(), separators=(",", ":"))),
                "42501", "missing signed worker context",
            )
            checks.append("notification enqueue rejects calls without a signed worker scope")

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute(RESERVE_SQL, (SOURCE_EVENT_ID, READING_ID, RULE_ID, LOCATION_ID))
                if cursor.fetchone()[0] is not True:
                    raise AssertionError("fixture receipt reservation did not insert")
                cursor.execute(
                    OUTCOME_SQL,
                    (SOURCE_EVENT_ID, READING_ID, RULE_ID, LOCATION_ID, ALERT_ID),
                )
                if cursor.fetchone()[0] is not True:
                    raise AssertionError("fixture receipt did not link to the synthetic alert")
                cursor.execute(
                    PUBLISH_SQL,
                    (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
                )
                if cursor.fetchone()[0] is not True:
                    raise AssertionError("fixture alert event was not published")
            worker.commit()

            set_context(worker)
            if enqueue(worker) is not True:
                raise AssertionError("first valid webhook intent was not inserted")
            worker.commit()
            checks.append("matching signed receipt and published alert create one webhook intent")

            set_context(worker)
            if enqueue(worker) is not False:
                raise AssertionError("identical webhook retry was not suppressed")
            worker.commit()
            checks.append("identical source/channel/destination retries are idempotent")

            for channel in ("directus", "email"):
                set_context(worker)
                if enqueue(worker, channel=channel) is not True:
                    raise AssertionError(f"valid {channel} intent was not inserted")
                worker.commit()
            checks.append("Directus and email channel payload contracts are accepted")

            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT event_type, channel, destination_key, payload, status, "
                    "attempt_count, location_id::text FROM public.notification_outbox "
                    "WHERE source_event_id = %s::uuid ORDER BY channel",
                    (ALERT_EVENT_ID,),
                )
                rows = cursor.fetchall()
                if len(rows) != 3:
                    raise AssertionError(f"expected 3 channel intents, got {len(rows)}")
                for row in rows:
                    if row[0] != "sensor_alert" or row[2] != "primary":
                        raise AssertionError(f"unexpected notification identity: {row}")
                    if row[4:] != ("pending", 0, LOCATION_ID):
                        raise AssertionError(f"notification did not start pending: {row}")
            checks.append("all channel intents are location-bound, pending, and have zero attempts")

            set_context(worker)
            changed = payload()
            changed["location_name"] = "Different same-tenant payload"
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
                 ALERT_ID, LOCATION_ID, "webhook", "primary",
                 json.dumps(changed, separators=(",", ":"))),
                "23505", "same identity with different payload",
            )
            checks.append("conflicting stable identity fails without replacing saved payload")

            invalid_cases = (
                (("other-channel"), "primary", payload(), "22023", "channel allowlist"),
                (("webhook"), "other", payload(), "22023", "destination allowlist"),
                (("webhook"), "primary", {**payload(), "secret": "must not persist"}, "22023", "payload key allowlist"),
                (("webhook"), "primary", {**payload(), "message": "forged alert"}, "42501", "alert content mismatch"),
            )
            for channel, destination, invalid_payload, sqlstate, label in invalid_cases:
                set_context(worker)
                expect_sqlstate(
                    worker,
                    (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
                     ALERT_ID, LOCATION_ID, channel, destination,
                     json.dumps(invalid_payload, separators=(",", ":"))),
                    sqlstate, label,
                )
            oversized = payload()
            oversized["location_name"] = "x" * 17000
            set_context(worker)
            expect_sqlstate(
                worker,
                (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
                 ALERT_ID, LOCATION_ID, "webhook", "primary",
                 json.dumps(oversized, separators=(",", ":"))),
                "22023", "oversized payload",
            )
            checks.append("invalid channels, destinations, payloads, content, and oversized messages fail closed")

            for params, label in (
                ((ALERT_EVENT_ID, "a0000000-0000-0000-0000-000000000032",
                  READING_ID, RULE_ID, ALERT_ID, LOCATION_ID, "webhook", "primary", payload()),
                 "wrong source event"),
                ((ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
                  ALERT_ID, OTHER_LOCATION_ID, "webhook", "primary", payload()),
                 "wrong requested location"),
                ((SOURCE_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
                  ALERT_ID, LOCATION_ID, "webhook", "primary", payload()),
                 "non-alert published event"),
            ):
                set_context(worker)
                expect_sqlstate(worker, params, "42501", label)
            checks.append("wrong source, non-alert event, and out-of-scope location are rejected")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.notification_outbox SET status = 'succeeded', "
                    "attempt_count = 4 WHERE source_event_id = %s::uuid AND channel = 'webhook'",
                    (ALERT_EVENT_ID,),
                )
                cursor.execute(
                    "INSERT INTO public.notification_outbox_attempt (outbox_id, attempt_number, status) "
                    "SELECT id, 4, 'succeeded' FROM public.notification_outbox "
                    "WHERE source_event_id = %s::uuid AND channel = 'webhook'",
                    (ALERT_EVENT_ID,),
                )
            admin.commit()
            set_context(worker)
            if enqueue(worker) is not False:
                raise AssertionError("completed notification was not idempotently recognized")
            worker.commit()
            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT status, attempt_count FROM public.notification_outbox "
                    "WHERE source_event_id = %s::uuid AND channel = 'webhook'",
                    (ALERT_EVENT_ID,),
                )
                if cursor.fetchone() != ("succeeded", 4):
                    raise AssertionError("retry changed durable delivery state")
                cursor.execute("SELECT count(*) FROM public.notification_outbox_attempt")
                if cursor.fetchone()[0] != 1:
                    raise AssertionError("intent retry mutated delivery attempt history")
            checks.append("retry preserves delivered status, attempt count, and attempt history")

            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT has_any_column_privilege('kokonut_worker_execution', "
                    "'public.notification_outbox', 'SELECT'), "
                    "has_any_column_privilege('kokonut_worker_execution', "
                    "'public.notification_outbox', 'INSERT'), "
                    "has_any_column_privilege('kokonut_worker_execution', "
                    "'public.notification_outbox', 'UPDATE'), "
                    "has_table_privilege('kokonut_worker_execution', "
                    "'public.notification_outbox', 'DELETE'), "
                    "has_table_privilege('kokonut_worker_execution', "
                    "'public.notification_outbox_attempt', 'SELECT'), "
                    "has_function_privilege('kokonut_worker_execution', %s, 'EXECUTE'), "
                    "has_function_privilege('kokonut_anomaly_notification_owner', %s, 'EXECUTE')",
                    (FUNCTION_SIGNATURE, FUNCTION_SIGNATURE),
                )
                privilege_row = cursor.fetchone()
                if privilege_row != (False, False, False, False, False, True, True):
                    raise AssertionError(
                        f"worker notification privileges exceed bounded EXECUTE: {privilege_row}"
                    )
                cursor.execute(
                    "SELECT has_column_privilege('kokonut_anomaly_notification_owner', "
                    "'public.notification_outbox', 'location_id', 'INSERT'), "
                    "has_column_privilege('kokonut_anomaly_notification_owner', "
                    "'public.notification_outbox', 'status', 'SELECT'), "
                    "has_column_privilege('kokonut_anomaly_notification_owner', "
                    "'public.notification_outbox', 'status', 'UPDATE'), "
                    "has_table_privilege('kokonut_anomaly_notification_owner', "
                    "'public.notification_outbox_attempt', 'SELECT')"
                )
                if cursor.fetchone() != (True, False, False, False):
                    raise AssertionError("notification function owner has excessive table privileges")
                cursor.execute(
                    "SELECT role.rolcanlogin, role.rolinherit, role.rolsuper, "
                    "role.rolcreatedb, role.rolcreaterole, role.rolreplication, "
                    "role.rolbypassrls, EXISTS (SELECT 1 FROM pg_auth_members "
                    "WHERE roleid = role.oid OR member = role.oid) "
                    "FROM pg_roles AS role "
                    "WHERE role.rolname = 'kokonut_anomaly_notification_owner'"
                )
                if cursor.fetchone() != (False, False, False, False, False, False, False, False):
                    raise AssertionError("notification owner role has unsafe attributes or memberships")
            for connection, role_name in (
                (runtime, "kokonut_runtime"),
                (operator_auth, "kokonut_operator_auth"),
            ):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_function_privilege(current_user, %s, 'EXECUTE')",
                        (FUNCTION_SIGNATURE,),
                    )
                    if cursor.fetchone()[0]:
                        raise AssertionError(f"{role_name} can execute notification function")
            checks.append("worker has bounded function EXECUTE only; runtime and auth roles cannot call it")

            for statement, label in (
                ("SELECT * FROM public.notification_outbox", "direct outbox SELECT"),
                (
                    "INSERT INTO public.notification_outbox "
                    "(source_event_id,event_type,channel,destination_key,payload,location_id) "
                    f"VALUES ('{ALERT_EVENT_ID}','sensor_alert','webhook','primary','{{}}', '{LOCATION_ID}')",
                    "direct outbox INSERT",
                ),
                ("UPDATE public.notification_outbox SET status = 'discarded'", "direct outbox UPDATE"),
                ("DELETE FROM public.notification_outbox", "direct outbox DELETE"),
                ("SELECT * FROM public.notification_outbox_attempt", "direct attempt SELECT"),
            ):
                direct_denial(worker, statement, label)
            checks.append("worker cannot directly read or mutate notification rows or attempt history")

            for connection in (worker, runtime, operator_auth, admin):
                connection.close()
        finally:
            for connection in (worker, runtime, operator_auth, admin):
                if not connection.closed:
                    connection.close()

        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 409 bounded sensor-alert notification intent",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS],
            "migration_409_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
            "migration_replay": "passed",
            "command": "python3 scripts/check-sensor-alert-notification-intent-disposable.py",
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
                text=True, capture_output=True, check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
