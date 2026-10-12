#!/usr/bin/env python3
"""Exercise sensor anomaly replay after a hard exit at the commit boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from psycopg2.extras import register_uuid

from services.common.database import get_db
from services.events.bus import EventBus
from services.events.notification_outbox import _deliver

register_uuid()


def scalar(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def crash_worker(event_id: str, worker_id: str) -> None:
    """Run the real event worker and exit after the handler, before receipt ack."""

    class CrashAfterHandlerBus(EventBus):
        def _invoke_handler(
            self, module_path, function_name, event_type, payload, timeout_seconds,
            *, event_id=None,
        ):
            result = super()._invoke_handler(
                module_path, function_name, event_type, payload, timeout_seconds,
                event_id=event_id,
            )
            if event_type == "sensor_reading" and result[0] == "success":
                os._exit(86)
            return result

    bus = CrashAfterHandlerBus(conn=get_db())
    bus.process_pending(batch_size=1, worker_id=worker_id)


def run_recovery_check() -> None:
    conn = get_db()
    try:
        event_migration_sql = Path("schemas/postgres/165_event_bus_durability.sql").read_text()
        with conn.cursor() as cur:
            cur.execute(event_migration_sql)
        conn.commit()

        migration_sql = Path("schemas/postgres/376_sensor_anomaly_delivery.sql").read_text()
        for _ in range(2):
            with conn.cursor() as cur:
                cur.execute(migration_sql)
            conn.commit()

        with conn.cursor() as cur:
            # This scratch volume may be retained between runs; leave only the
            # newly created synthetic source event eligible for the worker.
            cur.execute(
                """
                UPDATE platform_event
                SET status = 'completed', lease_owner = NULL, lease_expires_at = NULL
                WHERE status IN ('pending', 'processing')
                """
            )
            cur.execute("SELECT id FROM sensor_type WHERE name = 'soil_moisture'")
            sensor_type_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO location (name, slug, country) VALUES (%s, %s, %s) RETURNING id",
                ("Synthetic anomaly fixture", f"synthetic-anomaly-{uuid.uuid4().hex[:12]}", "Synthetic"),
            )
            location_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO sensor_device (name, slug, sensor_type_id, location_id, status)
                VALUES (%s, %s, %s, %s, 'active') RETURNING id
                """,
                ("Synthetic soil probe", f"synthetic-probe-{uuid.uuid4().hex[:12]}", sensor_type_id, location_id),
            )
            sensor_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE alert_rule SET enabled = false WHERE name = 'Synthetic critical soil alert'"
            )
            cur.execute(
                """
                INSERT INTO alert_rule
                    (name, sensor_type_id, metric, operator, threshold_value, severity,
                     cooldown_minutes, enabled, auto_create_claim, claim_type,
                     actuator_enabled, actuator_type, actuator_command,
                     human_approval_required)
                VALUES ('Synthetic critical soil alert', %s, 'value', 'lt', 8.0, 'critical',
                        60, true, true, 'sensor_anomaly', true, 'irrigation',
                        'close_valve', false)
                RETURNING id
                """,
                (sensor_type_id,),
            )
            rule_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO sensor_reading
                    (location_id, sensor_id, sensor_type, reading_date, reading_time,
                     value, unit, quality)
                VALUES (%s, %s, 'soil_moisture', CURRENT_DATE, CURRENT_TIME,
                        4.0, 'percent', 'good')
                RETURNING id
                """,
                (location_id, sensor_id),
            )
            reading_id = cur.fetchone()[0]
            event_id = uuid.uuid4()
            payload = {
                "sensor_id": str(sensor_id),
                "sensor_type": "soil_moisture",
                "location_id": str(location_id),
                "value": 4.0,
                "quality": "good",
            }
            cur.execute(
                """
                INSERT INTO platform_event
                    (id, event_type, source_table, source_id, payload, status)
                VALUES (%s, 'sensor_reading', 'sensor_reading', %s, %s::jsonb, 'pending')
                """,
                (event_id, reading_id, json.dumps(payload)),
            )
        conn.commit()
    finally:
        conn.close()

    crash_worker_id = f"sensor-crash-{uuid.uuid4().hex[:12]}"
    crashed = subprocess.run(
        [
            sys.executable, str(Path(__file__).resolve()), "--crash-worker",
            str(event_id), crash_worker_id,
        ],
        check=False,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=45,
    )
    if crashed.returncode != 86:
        raise AssertionError(
            f"expected hard exit 86 after handler effects and before receipt ack, got {crashed.returncode}"
        )

    conn = get_db()
    try:
        before = {
            "alerts": scalar(conn, "SELECT COUNT(*) FROM sensor_alert WHERE reading_id = %s", (reading_id,)),
            "claims": scalar(conn, "SELECT COUNT(*) FROM mrv_claim WHERE sensor_alert_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)", (reading_id,)),
            "effects": scalar(conn, "SELECT COUNT(*) FROM sensor_anomaly_effect WHERE source_reading_id = %s AND outcome = 'alert_created'", (reading_id,)),
            "outbox": scalar(conn, """
                SELECT COUNT(*) FROM notification_outbox o
                JOIN platform_event e ON e.id = o.source_event_id
                WHERE o.event_type = 'sensor_alert' AND e.event_type = 'sensor_alert'
                  AND e.source_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)
                """, (reading_id,)),
            "published_alert_events": scalar(conn, "SELECT COUNT(*) FROM platform_event WHERE event_type = 'sensor_alert' AND source_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)", (reading_id,)),
            "actuations": scalar(conn, "SELECT COUNT(*) FROM actuation_log WHERE sensor_alert_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)", (reading_id,)),
            "ingestion_logs": scalar(conn, "SELECT COUNT(*) FROM ingestion_log WHERE source_system = 'anomaly_detector' AND source_id = %s", (str(reading_id),)),
        }
        if before != {
            "alerts": 1, "claims": 1, "effects": 1, "outbox": 3,
            "published_alert_events": 1, "actuations": 1, "ingestion_logs": 1,
        }:
            raise AssertionError(f"post-crash durable effects differ from expected: {before}")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, lease_owner FROM platform_event WHERE id = %s",
                (event_id,),
            )
            source_event_status, source_event_owner = cur.fetchone()
            cur.execute(
                """
                SELECT d.status, d.attempt_count, COUNT(l.id)
                FROM event_handler_delivery d
                JOIN event_handler h ON h.id = d.handler_id
                LEFT JOIN event_handler_log l ON l.event_id = d.event_id AND l.handler_id = d.handler_id
                WHERE d.event_id = %s AND h.handler_name = 'anomaly_detector'
                GROUP BY d.status, d.attempt_count
                """,
                (event_id,),
            )
            delivery_status_before, delivery_attempt_before, handler_logs_before = cur.fetchone()
            cur.execute("SELECT id FROM sensor_alert WHERE reading_id = %s", (reading_id,))
            alert_id = cur.fetchone()[0]
            cur.execute(
                "SELECT outcome, sensor_alert_id FROM sensor_anomaly_effect WHERE source_reading_id = %s AND alert_rule_id = %s",
                (reading_id, rule_id),
            )
            outcome, effect_alert_id = cur.fetchone()
            cur.execute(
                "SELECT status, human_approval_required, approved_by FROM actuation_log WHERE sensor_alert_id = %s",
                (alert_id,),
            )
            actuation_status, approval_required, approved_by = cur.fetchone()
            cur.execute(
                """
                SELECT o.payload FROM notification_outbox o
                JOIN platform_event e ON e.id = o.source_event_id
                WHERE e.event_type = 'sensor_alert' AND e.source_id = %s
                ORDER BY o.channel
                """,
                (alert_id,),
            )
            persisted_payloads = [json.dumps(row[0], sort_keys=True, default=str) for row in cur.fetchall()]

        if outcome != "alert_created" or str(effect_alert_id) != str(alert_id):
            raise AssertionError("effect receipt did not retain the created alert identity")
        if (source_event_status != "processing" or source_event_owner != crash_worker_id
                or delivery_status_before != "processing" or delivery_attempt_before != 1
                or handler_logs_before != 0):
            raise AssertionError("hard exit did not leave the actual event delivery receipt unacknowledged")
        if actuation_status != "requires_approval" or not approval_required or approved_by is not None:
            raise AssertionError("critical actuation did not remain pending independent human approval")
        if any(secret in "".join(persisted_payloads) for secret in (
            "smtp.invalid", "synthetic-password", "synthetic-token", "synthetic-ops@example.invalid"
        )):
            raise AssertionError("notification payload persisted a provider destination or credential")

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE platform_event
                SET lease_expires_at = NOW() - INTERVAL '1 second'
                WHERE id = %s AND status = 'processing' AND lease_owner = %s
                RETURNING id
                """,
                (event_id, crash_worker_id),
            )
            if cur.fetchone() is None:
                raise AssertionError("could not expire the synthetic source event lease")
        conn.commit()
        recovery_bus = EventBus(conn=conn)
        recovered_stats = recovery_bus.process_pending(
            batch_size=10, worker_id=f"sensor-recovery-{uuid.uuid4().hex[:12]}"
        )
        if recovered_stats != {"processed": 1, "failed": 0, "skipped": 1, "lease_lost": 0}:
            raise AssertionError(f"real event worker did not recover the source event: {recovered_stats}")

        after = {
            "alerts": scalar(conn, "SELECT COUNT(*) FROM sensor_alert WHERE reading_id = %s", (reading_id,)),
            "claims": scalar(conn, "SELECT COUNT(*) FROM mrv_claim WHERE sensor_alert_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)", (reading_id,)),
            "effects": scalar(conn, "SELECT COUNT(*) FROM sensor_anomaly_effect WHERE source_reading_id = %s", (reading_id,)),
            "outbox": scalar(conn, """
                SELECT COUNT(*) FROM notification_outbox o
                JOIN platform_event e ON e.id = o.source_event_id
                WHERE o.event_type = 'sensor_alert' AND e.event_type = 'sensor_alert'
                  AND e.source_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)
                """, (reading_id,)),
            "published_alert_events": scalar(conn, "SELECT COUNT(*) FROM platform_event WHERE event_type = 'sensor_alert' AND source_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)", (reading_id,)),
            "actuations": scalar(conn, "SELECT COUNT(*) FROM actuation_log WHERE sensor_alert_id IN (SELECT id FROM sensor_alert WHERE reading_id = %s)", (reading_id,)),
            "ingestion_logs": scalar(conn, "SELECT COUNT(*) FROM ingestion_log WHERE source_system = 'anomaly_detector' AND source_id = %s", (str(reading_id),)),
        }
        if after != before:
            raise AssertionError(f"replay created duplicate effects: before={before}, after={after}")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.status, d.status, d.attempt_count, COUNT(l.id)
                FROM platform_event e
                JOIN event_handler_delivery d ON d.event_id = e.id
                JOIN event_handler h ON h.id = d.handler_id
                LEFT JOIN event_handler_log l ON l.event_id = d.event_id AND l.handler_id = d.handler_id
                WHERE e.id = %s AND h.handler_name = 'anomaly_detector'
                GROUP BY e.status, d.status, d.attempt_count
                """,
                (event_id,),
            )
            source_event_final_status, delivery_status_after, delivery_attempt_after, handler_logs_after = cur.fetchone()
        if (source_event_final_status != "completed" or delivery_status_after != "success"
                or delivery_attempt_after != 2 or handler_logs_after != 1):
            raise AssertionError("event worker receipt did not complete on attempt two")
    finally:
        conn.close()

    fake_smtp_calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            fake_smtp_calls.append({"host": host, "port": port, "timeout": timeout})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, _username, _password):
            pass

        def send_message(self, message):
            fake_smtp_calls.append({"message_id": message["Message-ID"], "key": message["X-Kokonut-Idempotency-Key"]})

    email_id = uuid.uuid4()
    with patch("services.events.notification_outbox.smtplib.SMTP", FakeSMTP):
        _deliver({
            "id": email_id,
            "channel": "email",
            "payload": {"subject": "Synthetic", "body": "Synthetic body"},
        })
    if len(fake_smtp_calls) != 2 or str(email_id) not in fake_smtp_calls[1]["message_id"]:
        raise AssertionError("email delivery did not use a deterministic outbox Message-ID")
    if fake_smtp_calls[1]["key"] != str(email_id):
        raise AssertionError("email delivery did not include the outbox idempotency key")

    print(json.dumps({
        "result": "passed",
        "migration_reapplications": 2,
        "hard_exit_code": crashed.returncode,
        "recovery_worker_stats": recovered_stats,
        "delivery_receipt": {
            "after_crash": {"status": delivery_status_before, "attempt_count": delivery_attempt_before,
                             "handler_logs": handler_logs_before},
            "after_recovery": {"event_status": source_event_final_status,
                               "status": delivery_status_after,
                               "attempt_count": delivery_attempt_after,
                               "handler_logs": handler_logs_after},
        },
        "effects_after_crash": before,
        "effects_after_replay": after,
        "critical_actuation": {
            "status": actuation_status,
            "human_approval_required": approval_required,
            "approved_by": None,
        },
        "outbox_channels": ["webhook", "directus", "email"],
        "fake_smtp_calls": len(fake_smtp_calls) - 1,
        "network_egress": "disabled; no provider worker or external transport ran",
        "fixture_data": "synthetic",
    }, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--crash-worker":
        crash_worker(sys.argv[2], sys.argv[3])
    else:
        run_recovery_check()
