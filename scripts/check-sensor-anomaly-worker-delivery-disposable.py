#!/usr/bin/env python3
"""Exercise the event-driven anomaly worker on disposable PostgreSQL 16."""

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

FIXTURES_AND_MIGRATIONS = (
    ("tests/fixtures/worker_tenant_context_disposable.sql", "schemas/postgres/405_signed_worker_tenant_context.sql"),
    ("tests/fixtures/sensor_anomaly_effect_functions_disposable.sql", "schemas/postgres/406_sensor_anomaly_location_lineage.sql"),
    (None, "schemas/postgres/407_sensor_anomaly_effect_functions.sql"),
    ("tests/fixtures/sensor_alert_event_function_disposable.sql", "schemas/postgres/408_sensor_alert_event_function.sql"),
    ("tests/fixtures/sensor_alert_notification_intent_disposable.sql", "schemas/postgres/409_sensor_alert_notification_intent.sql"),
    ("tests/fixtures/sensor_alert_actuation_intent_disposable.sql", "schemas/postgres/410_sensor_alert_actuation_intent.sql"),
    ("tests/fixtures/sensor_alert_draft_claim_intent_disposable.sql", "schemas/postgres/411_sensor_alert_draft_claim_intent.sql"),
    ("tests/fixtures/sensor_anomaly_worker_reads_disposable.sql", "schemas/postgres/412_sensor_anomaly_worker_reads.sql"),
    ("tests/fixtures/sensor_anomaly_alert_write_disposable.sql", "schemas/postgres/413_sensor_anomaly_alert_write.sql"),
    ("tests/fixtures/sensor_anomaly_worker_delivery_disposable.sql", "schemas/postgres/414_sensor_anomaly_worker_delivery.sql"),
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/sensor-anomaly-worker-delivery-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"
READING_ID = "a0000000-0000-0000-0000-000000000026"
SOURCE_EVENT_ID = "a0000000-0000-0000-0000-000000000037"
RULE_ID = "a0000000-0000-0000-0000-000000000091"
RAW_CREDENTIAL = "synthetic-anomaly-worker-credential-for-disposable-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode()).hexdigest()


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        safe_command = [
            "POSTGRES_PASSWORD=<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
            for item in command
        ]
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v",
         "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def query(connection, statement: str, params: tuple = ()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        result = cursor.fetchall()
    connection.commit()
    return result


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("ANOMALY_DELIVERY_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-delivery-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    connections = []
    checks: list[str] = []
    migration_414 = ROOT / "schemas/postgres/414_sensor_anomaly_worker_delivery.sql"
    original_env = {
        name: os.environ.get(name)
        for name in (
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL",
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL",
            "ALERT_WEBHOOK_URL",
            "ALERT_SMTP_HOST",
            "ALERT_EMAIL_TO",
            "KOKONUT_FEATURE_DIRECTUS",
        )
    }
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={admin_password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        for fixture_name, migration_name in FIXTURES_AND_MIGRATIONS:
            if fixture_name:
                docker_sql(docker, container, (ROOT / fixture_name).read_text(encoding="utf-8"))
            migration_text = (ROOT / migration_name).read_text(encoding="utf-8")
            docker_sql(docker, container, migration_text)
            if migration_name.endswith("414_sensor_anomaly_worker_delivery.sql"):
                docker_sql(docker, container, migration_text)
        checks.append("migrations 405–414 apply in order and migration 414 replays cleanly")

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
                'sensor_reading', 'process', 'disposable fixture'
            );
            """,
        )
        port_lines = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_lines:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_lines[0].rsplit(":", 1)[1])
        admin_password_worker = "worker-execution-fixture"
        admin = connect(port, "postgres", admin_password)
        worker = connect(port, "kokonut_worker_login", admin_password_worker)
        connections.extend((admin, worker))

        os.environ["KOKONUT_SENSOR_ANOMALY_DATABASE_URL"] = (
            f"postgresql://kokonut_worker_login:{admin_password_worker}@127.0.0.1:{port}/postgres"
        )
        os.environ["KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL"] = RAW_CREDENTIAL
        os.environ["ALERT_WEBHOOK_URL"] = "https://synthetic.invalid/anomaly"
        os.environ["ALERT_SMTP_HOST"] = ""
        os.environ["ALERT_EMAIL_TO"] = ""
        os.environ["KOKONUT_FEATURE_DIRECTUS"] = "false"

        from services.ingestion.sensor_anomaly_worker import process_sensor_reading

        first = process_sensor_reading(
            sensor_id=SENSOR_ID, location_id=LOCATION_ID, event_id=SOURCE_EVENT_ID
        )
        if first != {
            "rules": 1, "reserved": 1, "alerts": 1, "claims": 1,
            "notifications": 1, "actuation_intents": 1, "skipped": 0,
        }:
            raise AssertionError(f"bounded worker transaction had unexpected effects: {first}")
        checks.append("signed worker transaction creates the alert, draft claim, notification and approval intent")

        alert_rows = query(
            admin,
            """SELECT alert.id::text, alert.location_id::text,
                      alert.reading_id::text, alert.claim_id::text,
                      effect.outcome, effect.sensor_alert_id::text,
                      claim.status, claim.source_sensor_reading_event_id::text
                 FROM public.sensor_alert AS alert
                 JOIN public.sensor_anomaly_effect AS effect
                   ON effect.sensor_alert_id = alert.id
                 JOIN public.mrv_claim AS claim ON claim.id = alert.claim_id
                WHERE alert.reading_id = %s::uuid AND alert.alert_rule_id = %s::uuid""",
            (READING_ID, RULE_ID),
        )
        if len(alert_rows) != 1:
            raise AssertionError(f"expected one alert/claim/receipt lineage, got {alert_rows}")
        alert_id = alert_rows[0][0]
        if alert_rows[0][1:] != (
            LOCATION_ID, READING_ID, alert_rows[0][3], "alert_created", alert_id,
            "draft", SOURCE_EVENT_ID,
        ):
            raise AssertionError(f"alert/claim lineage is inconsistent: {alert_rows}")

        event_rows = query(
            admin,
            """SELECT id::text, payload
                 FROM public.platform_event
                WHERE event_type = 'sensor_alert' AND source_id = %s::uuid""",
            (alert_id,),
        )
        if len(event_rows) != 1:
            raise AssertionError(f"expected one canonical sensor_alert event: {event_rows}")
        alert_event_id, event_payload = event_rows[0]
        required_event_keys = {
            "alert_id", "sensor_device_id", "severity", "rule_name",
            "reading_value", "threshold_value", "triggered_at", "claim_id",
            "sensor_name", "sensor_type", "location_id", "location_name",
        }
        if not required_event_keys.issubset(event_payload):
            raise AssertionError(f"canonical alert event lacks notification context: {event_payload}")
        checks.append("published event contains the same source-derived context used by channel formatters")

        notification_rows = query(
            admin,
            """SELECT event_type, channel, destination_key, payload, location_id::text
                 FROM public.notification_outbox WHERE source_event_id = %s::uuid""",
            (alert_event_id,),
        )
        if len(notification_rows) != 1 or notification_rows[0][0:3] != (
            "sensor_alert", "webhook", "primary"
        ) or notification_rows[0][4] != LOCATION_ID:
            raise AssertionError(f"notification intent is not source scoped: {notification_rows}")
        from services.events.notification_outbox import enqueue_event_notification

        queued_again = enqueue_event_notification(
            admin,
            event_id=alert_event_id,
            event_type="sensor_alert",
            payload=event_payload,
            location_id=LOCATION_ID,
            environment=dict(os.environ),
        )
        admin.commit()
        if queued_again != 0:
            raise AssertionError("follow-up event retry did not deduplicate its notification intent")
        checks.append("follow-up event notification handling is idempotent with the transactionally queued intent")

        actuation_rows = query(
            admin,
            """SELECT location_id::text, sensor_alert_id::text,
                      source_alert_event_id::text, human_approval_required,
                      approved_by, status
                 FROM public.actuation_log WHERE sensor_alert_id = %s::uuid""",
            (alert_id,),
        )
        if actuation_rows != [(
            LOCATION_ID, alert_id, alert_event_id, True, None, "requires_approval"
        )]:
            raise AssertionError(f"actuation intent bypassed its approval boundary: {actuation_rows}")
        checks.append("actuator-enabled alert creates only an approval-required intent; no command is sent")

        replay = process_sensor_reading(
            sensor_id=SENSOR_ID, location_id=LOCATION_ID, event_id=SOURCE_EVENT_ID
        )
        if replay["alerts"] != 0 or replay["skipped"] != 1:
            raise AssertionError(f"worker retry did not skip its completed rule receipt: {replay}")
        counts = query(
            admin,
            """SELECT
                      (SELECT count(*) FROM public.sensor_alert WHERE id = %s::uuid),
                      (SELECT count(*) FROM public.notification_outbox WHERE source_event_id = %s::uuid),
                      (SELECT count(*) FROM public.actuation_log WHERE source_alert_event_id = %s::uuid)""",
            (alert_id, alert_event_id, alert_event_id),
        )
        if counts != [(1, 1, 1)]:
            raise AssertionError(f"worker retry duplicated a durable effect: {counts}")
        checks.append("source event replay suppresses duplicate alert, notification, and actuator records")

        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            try:
                cursor.execute("SELECT * FROM public.sensor_alert LIMIT 0")
            except psycopg2.Error as exc:
                worker.rollback()
                if exc.pgcode != "42501":
                    raise
            else:
                worker.rollback()
                raise AssertionError("worker execution unexpectedly has direct sensor_alert SELECT")
        checks.append("forced-RLS function owners work while worker execution has no direct alert table access")

        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Signed event-driven sensor anomaly transaction and delivery",
            "database": "isolated disposable PostgreSQL 16 container",
            "migration_414_sha256": hashlib.sha256(migration_414.read_bytes()).hexdigest(),
            "migrations": [migration for _, migration in FIXTURES_AND_MIGRATIONS],
            "result": "passed",
            "checks": [{"result": "passed", "description": item} for item in checks],
            "network": "no external providers contacted; webhook URL is synthetic and used only to select a formatter",
            "candidate_or_legacy_database_access": False,
            "raw_worker_credential_printed": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        for connection in connections:
            try:
                connection.close()
            except Exception:
                pass
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
