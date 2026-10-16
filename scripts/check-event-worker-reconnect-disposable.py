#!/usr/bin/env python3
"""Exercise the durable EventBus worker across a disposable PostgreSQL restart."""

from __future__ import annotations

import json
import os
import queue
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _docker(*args: str, check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args], input=stdin, capture_output=True, text=True, check=False
    )
    if check and result.returncode:
        # Avoid echoing arguments because the disposable password is an env value.
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr.strip()}")
    return result


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_log(
    process: subprocess.Popen[str],
    lines: list[str],
    output: queue.Queue[str | None],
    expected: str,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Event worker exited with status {process.returncode}")
        try:
            line = output.get(timeout=min(0.2, deadline - time.monotonic()))
        except queue.Empty:
            continue
        if line is None:
            raise RuntimeError("Event worker output closed before database recovery")
        lines.append(line)
        if expected in line:
            return
    raise TimeoutError(f"Event worker did not log {expected!r} within {timeout:g}s")


def _wait_until_ready(name: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
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
            return
        time.sleep(0.25)
    raise TimeoutError("disposable PostgreSQL did not become ready")


def _sql(name: str, statement: str) -> str:
    result = _docker(
        "exec",
        name,
        "psql",
        "-q",
        "-XAt",
        "-F",
        "|",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        "127.0.0.1",
        "-U",
        "kokonut",
        "-d",
        "kokonut_intelligence",
        "-c",
        statement,
    )
    return result.stdout.strip()


def _enqueue(name: str, event_type: str) -> str:
    payload = json.dumps(
        {
            "severity": "warning",
            "metric": "reconnect_probe",
            "value": 1,
            "threshold": 0,
            "message": "synthetic worker recovery probe",
        },
        separators=(",", ":"),
    )
    return _sql(
        name,
        "INSERT INTO platform_event (event_type, payload) "
        f"VALUES ('{event_type}', '{payload}'::jsonb) RETURNING id",
    )


def _start_loopback_webhook() -> tuple[
    ThreadingHTTPServer,
    threading.Thread,
    queue.Queue[dict[str, str]],
]:
    received: queue.Queue[dict[str, str]] = queue.Queue()
    request_number = 0
    request_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            nonlocal request_number
            size = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(size).decode("utf-8")
            with request_lock:
                request_number += 1
                status_code = 503 if request_number == 1 else 200
            received.put(
                {
                    "idempotency_key": self.headers.get("Idempotency-Key", ""),
                    "payload": payload,
                    "status_code": str(status_code),
                }
            )
            self.send_response(status_code)
            self.end_headers()
            self.wfile.write(b"temporarily unavailable" if status_code == 503 else b"accepted")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, received


def _wait_for_completed(name: str, event_id: str, timeout: float) -> tuple[str, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _sql(
            name,
            "SELECT e.status, COALESCE(e.worker_id, ''), COALESCE(("
            "SELECT d.status FROM event_handler_delivery d "
            "JOIN event_handler h ON h.id = d.handler_id "
            "WHERE d.event_id = e.id AND h.handler_name = 'alert_notifier'"
            "), '') FROM platform_event e "
            f"WHERE e.id = '{event_id}'",
        ).split("|")
        if len(values) == 3 and values[0] == "completed" and values[1] and values[2]:
            return values[1], values[2]
        time.sleep(0.25)
    raise TimeoutError("EventBus worker did not complete the synthetic event")


def _wait_for_notification_state(
    name: str,
    event_id: str,
    outbox_status: str,
    attempt_status: str,
    timeout: float,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _sql(
            name,
            "SELECT o.id, o.status, COALESCE(a.status, '') "
            "FROM notification_outbox o LEFT JOIN LATERAL ("
            "SELECT status FROM notification_outbox_attempt "
            "WHERE outbox_id = o.id ORDER BY attempt_number DESC LIMIT 1"
            ") a ON TRUE "
            f"WHERE o.source_event_id = '{event_id}'",
        ).split("|")
        if len(values) == 3 and values[1:] == [outbox_status, attempt_status]:
            return values[0]
        time.sleep(0.25)
    raise TimeoutError(
        f"notification did not reach outbox={outbox_status}, attempt={attempt_status}"
    )


def _wait_for_webhook(
    received: queue.Queue[dict[str, str]], timeout: float
) -> dict[str, str]:
    try:
        return received.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError("the local webhook did not receive a delivery") from exc


def _make_notification_retryable_now(name: str, notification_id: str) -> None:
    updated_id = _sql(
        name,
        "UPDATE notification_outbox SET available_at = NOW() "
        f"WHERE id = '{notification_id}' AND status = 'retryable' RETURNING id",
    )
    if updated_id != notification_id:
        raise RuntimeError("failed to release the synthetic notification retry")


def main() -> int:
    image = os.environ.get("EVENT_WORKER_RECONNECT_POSTGRES_IMAGE", "postgres:16-alpine")
    timeout = float(os.environ.get("EVENT_WORKER_RECONNECT_TIMEOUT", "30"))
    name = f"kokonut-event-worker-reconnect-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    process: subprocess.Popen[str] | None = None
    lines: list[str] = []
    output: queue.Queue[str | None] = queue.Queue()
    worker_id = "event-worker-reconnect-probe"
    event_type = "threshold_breached"
    webhook_server: ThreadingHTTPServer | None = None
    webhook_thread: threading.Thread | None = None
    webhook_requests: queue.Queue[dict[str, str]] | None = None
    result: dict[str, object] = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "database_image": image,
        "database_port_binding": "127.0.0.1 only",
        "database_volume": False,
        "candidate_or_legacy_modified": False,
        "external_provider_calls": 0,
        "loopback_webhook_calls": 0,
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
        _wait_until_ready(name, timeout)

        for migration in (
            "116_event_bus.sql",
            "165_event_bus_durability.sql",
            "375_notification_outbox.sql",
        ):
            sql = (ROOT / "schemas" / "postgres" / migration).read_text()
            _docker(
                "exec",
                "-i",
                name,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-h",
                "127.0.0.1",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                check=True,
                stdin=sql,
            )
        webhook_server, webhook_thread, webhook_requests = _start_loopback_webhook()

        env = os.environ.copy()
        env.update(
            {
                "KOKONUT_ENV": "development",
                "KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT": "true",
                "PG_HOST": "127.0.0.1",
                "PG_PORT": str(port),
                "PG_DB": "kokonut_intelligence",
                "PG_USER": "kokonut",
                "PG_PASSWORD": password,
                "CLICKHOUSE_ENABLED": "false",
                "ALERT_WEBHOOK_URL": (
                    f"http://127.0.0.1:{webhook_server.server_address[1]}/alerts"
                ),
                "ALERT_SMTP_HOST": "",
                "ALERT_EMAIL_TO": "",
                "DIRECTUS_ADMIN_TOKEN": "",
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
                "KOKONUT_FEATURE_DIRECTUS": "false",
                "KOKONUT_FEATURE_CLICKHOUSE": "false",
                "KOKONUT_FEATURE_GRPC": "false",
                "KOKONUT_FEATURE_METABASE": "false",
                "KOKONUT_FEATURE_MQTT": "false",
                "KOKONUT_FEATURE_PREFECT": "false",
                "KOKONUT_FEATURE_LEGACY_DATASET_SQL": "false",
            }
        )
        worker_code = f"""
from types import SimpleNamespace
from services.events.cli import cmd_worker

args = SimpleNamespace(
    poll_interval=0.25,
    batch_size=10,
    worker_id={worker_id!r},
    lease_seconds=30,
)
raise SystemExit(cmd_worker(args))
"""
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", worker_code],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def collect_output() -> None:
            assert process is not None and process.stdout is not None
            for output_line in process.stdout:
                output.put(output_line.rstrip())
            output.put(None)

        threading.Thread(target=collect_output, daemon=True).start()
        event_before = _enqueue(name, event_type)
        before_worker, before_handler_status = _wait_for_completed(name, event_before, timeout)
        if before_worker != worker_id:
            raise RuntimeError("synthetic pre-outage event was not claimed by the probe worker")
        if before_handler_status != "success":
            raise RuntimeError("allowlisted pre-outage handler did not succeed")
        assert webhook_requests is not None
        notification_before = _wait_for_notification_state(
            name, event_before, "retryable", "failed", timeout
        )
        failed_delivery = _wait_for_webhook(webhook_requests, timeout)
        if failed_delivery["status_code"] != "503":
            raise RuntimeError("the loopback webhook did not simulate its first-attempt outage")
        if failed_delivery["idempotency_key"] != notification_before:
            raise RuntimeError("failed webhook attempt used the wrong notification idempotency key")
        _make_notification_retryable_now(name, notification_before)
        if _wait_for_notification_state(name, event_before, "succeeded", "succeeded", timeout) != notification_before:
            raise RuntimeError("notification retry changed its durable notification identity")
        retry_delivery = _wait_for_webhook(webhook_requests, timeout)
        if retry_delivery["status_code"] != "200":
            raise RuntimeError("the loopback webhook did not accept the retried delivery")
        if retry_delivery["idempotency_key"] != notification_before:
            raise RuntimeError("notification retry did not reuse its idempotency key")

        _docker("stop", "--time", "1", name)
        _wait_for_log(process, lines, output, "Event worker iteration failed", timeout)
        if process.poll() is not None:
            raise RuntimeError("Event worker exited during the database outage")

        _docker("start", name)
        _wait_until_ready(name, timeout)
        event_after = _enqueue(name, event_type)
        after_worker, after_handler_status = _wait_for_completed(name, event_after, timeout)
        if after_worker != worker_id:
            raise RuntimeError("synthetic post-outage event was not claimed by the probe worker")
        if after_handler_status != "success":
            raise RuntimeError("allowlisted post-outage handler did not succeed")
        notification_after = _wait_for_notification_state(
            name, event_after, "succeeded", "succeeded", timeout
        )
        accepted_after_restart = _wait_for_webhook(webhook_requests, timeout)
        if accepted_after_restart["status_code"] != "200":
            raise RuntimeError("post-restart loopback delivery was not accepted")
        if accepted_after_restart["idempotency_key"] != notification_after:
            raise RuntimeError("post-restart delivery used the wrong notification idempotency key")
        if notification_before == notification_after:
            raise RuntimeError("distinct events reused a notification idempotency key")

        result.update(
            {
                "result": "passed",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "event_before_restart_completed": True,
                "event_after_restart_completed": True,
                "handler_succeeded_before_restart": True,
                "handler_succeeded_after_restart": True,
                "both_events_claimed_by_same_worker": True,
                "notification_succeeded_before_restart": True,
                "notification_succeeded_after_restart": True,
                "latest_notification_attempts_succeeded": True,
                "notification_retry_after_transient_failure": True,
                "retry_reused_idempotency_key": True,
                "source_notification_idempotency_keys_distinct": True,
                "loopback_webhook_calls": 3,
                "worker_id": worker_id,
                "migrations_replayed": [
                    "116_event_bus.sql",
                    "165_event_bus_durability.sql",
                    "375_notification_outbox.sql",
                ],
                "limitations": [
                    "Only the event, durable-handler, and notification table migrations were replayed in the disposable database; the full ordered schema ledger was not applied.",
                    "The real allowlisted alert-notification handler ran in its spawned child process and queued webhooks to a temporary HTTP server bound to 127.0.0.1; no remote provider was contacted.",
                    "The local server returned one synthetic 503, then accepted the retry and the post-restart notification. The first notification recovered from retryable/failed to succeeded/succeeded; its retry reused the same durable notification ID as the idempotency key.",
                    "All three loopback requests carried the matching durable notification IDs as idempotency keys; the two source events used distinct IDs.",
                    "The PostgreSQL container had no volume and was bound only to loopback.",
                ],
            }
        )
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        _docker("rm", "--force", name, check=False)
        if webhook_server is not None:
            webhook_server.shutdown()
            webhook_server.server_close()
        if webhook_thread is not None:
            webhook_thread.join(timeout=2)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"result": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise
