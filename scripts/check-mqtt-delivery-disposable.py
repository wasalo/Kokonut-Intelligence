#!/usr/bin/env python3
"""Exercise durable MQTT receipts on a new loopback-only PostgreSQL 16 container."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _docker(*args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode:
        # Docker arguments include the disposable password; never print them.
        raise RuntimeError(f"Docker {args[0]} failed with exit code {result.returncode}")
    return result


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _exercise(port: int, password: str) -> dict:
    os.environ.update(
        {
            "KOKONUT_ENV": "development",
            "KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT": "true",
            "PG_HOST": "127.0.0.1",
            "PG_PORT": str(port),
            "PG_DB": "kokonut_intelligence",
            "PG_USER": "kokonut",
            "PG_PASSWORD": password,
            "CLICKHOUSE_ENABLED": "false",
        }
    )

    # Import after installing the disposable connection settings: common.db
    # snapshots PG_* configuration when it is first imported.
    from services.common.cli import get_connection as base_get_connection
    from services.ingestion import mqtt_delivery

    with base_get_connection() as conn:
        conn.execute("CREATE TABLE synthetic_mqtt_source (delivery_key TEXT PRIMARY KEY)")

    source_topic = "sensors/disposable/source-window"
    source_payload = b'{"reading":"source-commit-window"}'
    source_key = mqtt_delivery.delivery_key(source_topic, source_payload)

    crash_environment = os.environ.copy()
    crash_environment.update(
        {
            "KOKONUT_MQTT_CRASH_TOPIC": source_topic,
            "KOKONUT_MQTT_CRASH_PAYLOAD_HEX": source_payload.hex(),
        }
    )
    crash_code = """
import os
from services.common.cli import get_connection
from services.ingestion import mqtt_delivery

topic = os.environ["KOKONUT_MQTT_CRASH_TOPIC"]
payload = bytes.fromhex(os.environ["KOKONUT_MQTT_CRASH_PAYLOAD_HEX"])
delivery_key = mqtt_delivery.delivery_key(topic, payload)

def commit_source_then_terminate():
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO synthetic_mqtt_source (delivery_key) VALUES (:key)",
            {"key": delivery_key},
        )
    os._exit(73)

mqtt_delivery.process_delivery(topic, payload, commit_source_then_terminate)
raise SystemExit(74)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", crash_code],
        cwd=ROOT,
        env=crash_environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=20,
    )
    _assert(crashed.returncode == 73, f"delivery process did not terminate in the receipt gap: {crashed.returncode}")

    def persist_source_once() -> str:
        with base_get_connection() as conn:
            inserted = conn.execute(
                """INSERT INTO synthetic_mqtt_source (delivery_key) VALUES (:key)
                   ON CONFLICT (delivery_key) DO NOTHING RETURNING delivery_key""",
                {"key": source_key},
            ).first()
        return "accepted" if inserted else "duplicate"

    with base_get_connection() as conn:
        committed_source = conn.execute(
            "SELECT count(*) AS count FROM synthetic_mqtt_source WHERE delivery_key = :key",
            {"key": source_key},
        ).first()["count"]
        rolled_back_receipt = conn.execute(
            "SELECT count(*) AS count FROM mqtt_delivery WHERE delivery_key = :key",
            {"key": source_key},
        ).first()["count"]
    _assert(committed_source == 1 and rolled_back_receipt == 0, "source/receipt commit boundary was not preserved")
    recovered = mqtt_delivery.process_delivery(
        source_topic, source_payload, persist_source_once
    )
    with base_get_connection() as conn:
        source_after_recovery = conn.execute(
            "SELECT count(*) AS count FROM synthetic_mqtt_source WHERE delivery_key = :key",
            {"key": source_key},
        ).first()["count"]
    _assert(recovered["status"] == "accepted" and source_after_recovery == 1, "redelivery duplicated the source effect")

    topic = "sensors/disposable/receipt-state"
    accepted_payload = b'{"reading":1}'
    accepted_calls = 0

    def accepted_handler() -> str:
        nonlocal accepted_calls
        accepted_calls += 1
        return "accepted"

    first = mqtt_delivery.process_delivery(topic, accepted_payload, accepted_handler)
    duplicate = mqtt_delivery.process_delivery(
        topic,
        accepted_payload,
        lambda: (_ for _ in ()).throw(AssertionError("terminal duplicate ran its handler")),
    )
    _assert(first["status"] == "accepted" and first["attempt_count"] == 1, "accepted receipt was not persisted")
    _assert(duplicate == first and accepted_calls == 1, "terminal duplicate was not suppressed")

    failed_payload = b'{"reading":2}'
    failures = [
        mqtt_delivery.process_delivery(
            topic,
            failed_payload,
            lambda: (_ for _ in ()).throw(ValueError("synthetic failure")),
        )
        for _ in range(5)
    ]
    terminal_duplicate = mqtt_delivery.process_delivery(
        topic,
        failed_payload,
        lambda: (_ for _ in ()).throw(AssertionError("dead-letter duplicate ran its handler")),
    )
    _assert([item["status"] for item in failures] == ["failed"] * 4 + ["dead_letter"], "five-attempt bound changed")
    _assert(all(item["attempt_count"] == index for index, item in enumerate(failures, start=1)), "retry count was not durable")
    _assert(terminal_duplicate["attempt_count"] == 5, "dead-letter duplicate changed the attempt count")

    replayed = mqtt_delivery.process_delivery(
        topic,
        failed_payload,
        lambda: "accepted",
        replay_actor="disposable-operator",
        replay_reason="synthetic PostgreSQL recovery acceptance",
    )
    _assert(replayed["status"] == "accepted" and replayed["attempt_count"] == 1, "replay did not start a new attempt budget")

    rejected_payload = b'{"reading":3}'
    rejected = mqtt_delivery.process_delivery(topic, rejected_payload, lambda: "rejected")
    rejected_duplicate = mqtt_delivery.process_delivery(
        topic,
        rejected_payload,
        lambda: (_ for _ in ()).throw(AssertionError("rejected duplicate ran its handler")),
    )
    _assert(rejected["status"] == "rejected" and rejected_duplicate == rejected, "rejected receipt was not terminal")

    disposable_payload = b'{"reading":4}'
    disposable = mqtt_delivery.process_delivery(topic, disposable_payload, lambda: "rejected")
    from services.ingestion import mqtt_delivery_cli

    disposal_output = io.StringIO()
    with contextlib.redirect_stdout(disposal_output):
        mqtt_delivery_cli.command(
            SimpleNamespace(
                list=False,
                actor="disposable-operator",
                reason="synthetic PostgreSQL disposal acceptance",
                replay=None,
                dispose=disposable["id"],
                limit=50,
            )
        )
    _assert(
        json.loads(disposal_output.getvalue()) == {"id": disposable["id"], "status": "disposed"},
        "operator disposal CLI did not return its terminal result",
    )
    disposed_duplicate = mqtt_delivery.process_delivery(
        topic,
        disposable_payload,
        lambda: (_ for _ in ()).throw(AssertionError("disposed duplicate ran its handler")),
    )
    _assert(disposed_duplicate["status"] == "disposed", "operator disposal was not terminal")

    concurrent_payload = b'{"reading":5}'
    start = threading.Barrier(2)
    handler_lock = threading.Lock()
    handler_calls = 0

    def slow_handler() -> str:
        nonlocal handler_calls
        with handler_lock:
            handler_calls += 1
        time.sleep(0.3)
        return "accepted"

    def concurrent_delivery() -> dict:
        start.wait(timeout=10)
        return mqtt_delivery.process_delivery(topic, concurrent_payload, slow_handler)

    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent_results = list(pool.map(lambda _: concurrent_delivery(), range(2)))
    _assert(handler_calls == 1, "concurrent identical deliveries executed more than once")
    _assert(
        all(item["status"] == "accepted" and item["attempt_count"] == 1 for item in concurrent_results),
        "concurrent deliveries did not converge on the accepted receipt",
    )

    from services.common.database import get_db

    raw_lock_connection = get_db()
    lock_cursor = raw_lock_connection.cursor()
    lock_cursor.execute(
        "UPDATE mqtt_delivery SET updated_at = updated_at WHERE delivery_key = %s",
        (mqtt_delivery.delivery_key(topic, accepted_payload),),
    )
    lock_error = None
    try:
        mqtt_delivery.process_delivery(
            topic,
            accepted_payload,
            lambda: (_ for _ in ()).throw(AssertionError("terminal receipt ran during lock timeout")),
        )
    except Exception as exc:  # noqa: BLE001 - assert PostgreSQL's timeout class
        lock_error = type(exc).__name__
    finally:
        raw_lock_connection.rollback()
        lock_cursor.close()
        raw_lock_connection.close()
    _assert(lock_error == "LockNotAvailable", f"expected lock timeout, got {lock_error!r}")
    lock_recovered = mqtt_delivery.process_delivery(
        topic,
        accepted_payload,
        lambda: (_ for _ in ()).throw(AssertionError("terminal receipt changed after lock recovery")),
    )
    _assert(lock_recovered["status"] == "accepted", "delivery did not recover after releasing the row lock")

    oversized_topic = "sensors/disposable/oversized/readings"
    oversized_payload = b"x" * 10_241
    oversized_key = mqtt_delivery.delivery_key(oversized_topic, oversized_payload)
    payload_constraint_error = None
    try:
        with base_get_connection() as conn:
            conn.execute(
                """INSERT INTO mqtt_delivery (delivery_key, topic, payload)
                   VALUES (:key, :topic, :payload)""",
                {"key": oversized_key, "topic": oversized_topic, "payload": oversized_payload},
            )
    except Exception as exc:  # noqa: BLE001 - assert PostgreSQL's CHECK failure class
        payload_constraint_error = type(exc).__name__
    _assert(payload_constraint_error == "CheckViolation", "database accepted evidence over 10 KiB")

    private_error_payload = b'{"reading":6}'
    private_error_secret = "synthetic-private-database-detail"
    private_error_delivery = mqtt_delivery.process_delivery(
        topic,
        private_error_payload,
        lambda: (_ for _ in ()).throw(ValueError("synthetic failure")),
    )
    with base_get_connection() as conn:
        conn.execute(
            "UPDATE mqtt_delivery SET last_error = :error WHERE id = :id",
            {"error": private_error_secret, "id": private_error_delivery["id"]},
        )

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        mqtt_delivery_cli.command(
            SimpleNamespace(list=True, actor=None, reason=None, replay=None, dispose=None, limit=50)
        )
    _assert(private_error_secret not in output.getvalue(), "private delivery listing leaked raw failure detail")
    _assert("[details redacted]" in output.getvalue(), "private delivery listing omitted its redaction marker")

    from services.ingestion import mqtt_subscriber

    original_subscriber = mqtt_subscriber.MQTTSensorSubscriber
    original_print_json = mqtt_delivery_cli.print_json
    operator_handler_calls = 0
    operator_handler_lock = threading.Lock()

    class _SyntheticSubscriber:
        def _handle_reading(self, payload, location_id, device_id):
            nonlocal operator_handler_calls
            with operator_handler_lock:
                operator_handler_calls += 1
            time.sleep(0.25)
            return "accepted"

        def stop(self):
            return None

    mqtt_subscriber.MQTTSensorSubscriber = _SyntheticSubscriber
    mqtt_delivery_cli.print_json = lambda value: None
    try:
        replay_topic = "sensors/disposable/replay/readings"
        replay_payload = b'{"reading":7}'
        replay_receipt = mqtt_delivery.process_delivery(
            replay_topic,
            replay_payload,
            lambda: (_ for _ in ()).throw(ValueError("synthetic retryable failure")),
        )
        replay_start = threading.Barrier(2)

        def operator_replay() -> str:
            replay_start.wait(timeout=10)
            try:
                mqtt_delivery_cli.command(
                    SimpleNamespace(
                        list=False,
                        actor="disposable-reviewer",
                        reason="concurrent synthetic replay",
                        replay=replay_receipt["id"],
                        dispose=None,
                        limit=50,
                    )
                )
            except ValueError:
                return "denied"
            return "accepted"

        with ThreadPoolExecutor(max_workers=2) as pool:
            replay_results = list(pool.map(lambda _: operator_replay(), range(2)))
        _assert(sorted(replay_results) == ["accepted", "denied"], "concurrent replay did not admit exactly one operator")
        _assert(operator_handler_calls == 1, "concurrent replay executed the sensor handler more than once")

        dispose_topic = "sensors/disposable/dispose/readings"
        dispose_payload = b'{"reading":8}'
        dispose_receipt = mqtt_delivery.process_delivery(dispose_topic, dispose_payload, lambda: "rejected")
        dispose_start = threading.Barrier(2)

        def operator_dispose() -> str:
            dispose_start.wait(timeout=10)
            try:
                mqtt_delivery_cli.command(
                    SimpleNamespace(
                        list=False,
                        actor="disposable-reviewer",
                        reason="concurrent synthetic disposal",
                        replay=None,
                        dispose=dispose_receipt["id"],
                        limit=50,
                    )
                )
            except ValueError:
                return "denied"
            return "disposed"

        with ThreadPoolExecutor(max_workers=2) as pool:
            dispose_results = list(pool.map(lambda _: operator_dispose(), range(2)))
        _assert(sorted(dispose_results) == ["denied", "disposed"], "concurrent disposal did not admit exactly one operator")
        with base_get_connection() as conn:
            replay_actions = conn.execute(
                "SELECT count(*) AS count FROM mqtt_delivery_action WHERE delivery_id = :id AND action = 'replay'",
                {"id": replay_receipt["id"]},
            ).first()["count"]
            dispose_actions = conn.execute(
                "SELECT count(*) AS count FROM mqtt_delivery_action WHERE delivery_id = :id AND action = 'dispose'",
                {"id": dispose_receipt["id"]},
            ).first()["count"]
            disposed_status = conn.execute(
                "SELECT status FROM mqtt_delivery WHERE id = :id",
                {"id": dispose_receipt["id"]},
            ).first()["status"]
        _assert(replay_actions == dispose_actions == 1, "operator action history was duplicated or lost")
        _assert(disposed_status == "disposed", "concurrent disposal did not leave a terminal status")
    finally:
        mqtt_subscriber.MQTTSensorSubscriber = original_subscriber
        mqtt_delivery_cli.print_json = original_print_json

    with mqtt_delivery.get_connection() as conn:
        action_count = conn.execute(
            "SELECT count(*) AS count FROM mqtt_delivery_action"
        ).first()["count"]
        persisted = conn.execute(
            "SELECT count(*) AS count FROM mqtt_delivery WHERE topic = :topic",
            {"topic": topic},
        ).first()["count"]
    _assert(action_count == 4, "replay/disposal audit rows were not persisted")
    _assert(persisted == 6, "unexpected number of synthetic receipt rows")

    return {
        "result": "passed",
        "database_target": "new disposable PostgreSQL 16 container; no volume; host port bound to 127.0.0.1",
        "assertions": {
            "accepted_receipt_and_terminal_duplicate_suppression": "passed",
            "five_persisted_failures_and_dead_letter_duplicate_suppression": "passed",
            "reviewed_replay_audit_and_fresh_attempt_budget": "passed",
            "rejected_receipt_and_duplicate_suppression": "passed",
            "operator_disposal_audit_and_terminal_duplicate_suppression": "passed",
            "operator_disposal_cli_output_is_terminal": "passed",
            "concurrent_identical_deliveries_execute_handler_once": "passed",
            "process_crash_between_source_and_receipt_commits_recovers_idempotently": "passed",
            "row_lock_timeout_and_redelivery_recovery": "passed",
            "database_payload_constraint_rejects_oversized_evidence": "passed",
            "operator_delivery_list_redacts_raw_failure_details": "passed",
            "concurrent_operator_replay_and_disposal_are_single_winner": "passed",
            "synthetic_receipt_rows": persisted,
            "operator_action_rows": action_count,
        },
        "candidate_or_legacy_modified": False,
        "provider_or_broker_contacted": False,
        "limitations": [
            "This exercises receipt SQL, not MQTT broker ACK or persistent-session behavior.",
            "The child exits after a synthetic source commit; this does not establish actual source/outbox parity or restart a real subscriber or broker.",
            "It does not verify replay after device-authorization changes or live sensor/provider parity.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional path for the sanitized JSON result",
    )
    args = parser.parse_args()

    name = f"kokonut-mqtt-receipts-{uuid.uuid4().hex[:8]}"
    image = os.environ.get("MQTT_DELIVERY_POSTGRES_IMAGE", "postgres:16-alpine")
    port = _free_port()
    password = secrets.token_urlsafe(24)
    result: dict = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "check": "CAP-040 MQTT durable receipt PostgreSQL acceptance",
        "database_image": image,
        "database_volume": False,
        "host_port_binding": "127.0.0.1 only",
    }

    try:
        _docker(
            "run",
            "--detach",
            "--name",
            name,
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--env",
            "POSTGRES_DB=kokonut_intelligence",
            "--env",
            "POSTGRES_USER=kokonut",
            "--env",
            f"POSTGRES_PASSWORD={password}",
            image,
        )
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            ready = _docker(
                "exec",
                name,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise TimeoutError("disposable PostgreSQL did not become ready")

        migration = (ROOT / "schemas/postgres/372_mqtt_delivery_records.sql").read_text()
        _docker(
            "exec",
            "--interactive",
            name,
            "psql",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            "-v",
            "ON_ERROR_STOP=1",
            input_text=migration,
        )
        result.update(_exercise(port, password))
    except Exception as exc:
        result.update({"result": "failed", "error": type(exc).__name__})
        raise
    finally:
        _docker("rm", "--force", name, check=False)

    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized)
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"result": "failed", "error": type(exc).__name__}), file=sys.stderr)
        raise
