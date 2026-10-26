#!/usr/bin/env python3
"""Exercise event workers, notification delivery, and database recovery."""

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
    worker_name: str,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{worker_name} exited with status {process.returncode}")
        try:
            line = output.get(timeout=min(0.2, deadline - time.monotonic()))
        except queue.Empty:
            continue
        if line is None:
            raise RuntimeError("Event worker output closed before database recovery")
        lines.append(line)
        if expected in line:
            return
    raise TimeoutError(
        f"{worker_name} did not log {expected!r} within {timeout:g}s"
    )


def _start_worker_process(
    command: str,
    worker_id: str,
    env: dict[str, str],
) -> tuple[subprocess.Popen[str], list[str], queue.Queue[str | None]]:
    if command not in {
        "cmd_event_worker",
        "cmd_isolated_event_worker",
        "cmd_notification_worker",
    }:
        raise ValueError("unsupported worker command")
    lines: list[str] = []
    output: queue.Queue[str | None] = queue.Queue()
    worker_code = f"""
from types import SimpleNamespace
from services.events.cli import {command}

args = SimpleNamespace(
    poll_interval=0.25,
    batch_size=10,
    worker_id={worker_id!r},
    lease_seconds=30,
)
raise SystemExit({command}(args))
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
        assert process.stdout is not None
        for output_line in process.stdout:
            output.put(output_line.rstrip())
        output.put(None)

    threading.Thread(target=collect_output, daemon=True).start()
    return process, lines, output


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
    threading.Event,
]:
    received: queue.Queue[dict[str, str]] = queue.Queue()
    request_number = 0
    request_lock = threading.Lock()
    release_crash_probe = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            nonlocal request_number
            size = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(size).decode("utf-8")
            with request_lock:
                request_number += 1
                current_request = request_number
                status_code = 503 if request_number == 1 else 200
            received.put(
                {
                    "idempotency_key": self.headers.get("Idempotency-Key", ""),
                    "payload": payload,
                    "status_code": str(status_code),
                    "request_number": str(current_request),
                }
            )
            if current_request == 4:
                # Model a receiver that has accepted the request while the
                # sender loses its connection before receiving the response.
                release_crash_probe.wait(timeout=30)
            self.send_response(status_code)
            self.end_headers()
            try:
                self.wfile.write(
                    b"temporarily unavailable" if status_code == 503 else b"accepted"
                )
            except OSError:
                # The crash probe intentionally kills the sender before this
                # response is released.
                pass

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, received, release_crash_probe


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


def _wait_for_isolated_event(
    name: str, event_id: str, worker_id: str, timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _sql(
            name,
            "SELECT e.status, COALESCE(e.worker_id, ''), "
            "(SELECT count(*) FROM event_handler_delivery d WHERE d.event_id=e.id) "
            "FROM platform_event e "
            f"WHERE e.id = '{event_id}'",
        ).split("|")
        if values == ["completed", worker_id, "0"]:
            return
        time.sleep(0.25)
    raise TimeoutError("isolated EventBus worker did not complete the synthetic event")


def _drain_output(output: queue.Queue[str | None], lines: list[str]) -> None:
    while True:
        try:
            line = output.get_nowait()
        except queue.Empty:
            return
        if line is None:
            return
        lines.append(line)


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


def _expire_notification_lease(name: str, notification_id: str) -> None:
    updated_id = _sql(
        name,
        "UPDATE notification_outbox SET lease_expires_at = NOW() - INTERVAL '1 second' "
        f"WHERE id = '{notification_id}' AND status = 'processing' RETURNING id",
    )
    if updated_id != notification_id:
        raise RuntimeError("failed to expire the killed worker's notification lease")


def main() -> int:
    image = os.environ.get("EVENT_WORKER_RECONNECT_POSTGRES_IMAGE", "postgres:16-alpine")
    timeout = float(os.environ.get("EVENT_WORKER_RECONNECT_TIMEOUT", "30"))
    name = f"kokonut-event-worker-reconnect-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    event_process: subprocess.Popen[str] | None = None
    notification_process: subprocess.Popen[str] | None = None
    isolated_event_process: subprocess.Popen[str] | None = None
    worker_id = "event-worker-reconnect-probe"
    notification_worker_id = "notification-worker-reconnect-probe"
    isolated_worker_id = "isolated-event-dispatch-reconnect-probe"
    notification_lines: list[str] = []
    notification_output: queue.Queue[str | None] = queue.Queue()
    isolated_lines: list[str] = []
    isolated_output: queue.Queue[str | None] = queue.Queue()
    event_type = "threshold_breached"
    webhook_server: ThreadingHTTPServer | None = None
    webhook_thread: threading.Thread | None = None
    webhook_requests: queue.Queue[dict[str, str]] | None = None
    release_crash_probe: threading.Event | None = None
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
        # The bounded fixture intentionally replays only the event/outbox
        # migrations. Current handlers also persist optional location lineage,
        # added to the outbox by migration 406; add only that column because
        # the unrelated sensor tables required by the full migration are not
        # part of this recovery acceptance.
        _sql(
            name,
            "ALTER TABLE public.notification_outbox ADD COLUMN location_id UUID",
        )
        (
            webhook_server,
            webhook_thread,
            webhook_requests,
            release_crash_probe,
        ) = _start_loopback_webhook()

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
                "KOKONUT_FEATURE_EVENT_BUS": "true",
                "KOKONUT_FEATURE_GRPC": "false",
                "KOKONUT_FEATURE_METABASE": "false",
                "KOKONUT_FEATURE_MQTT": "false",
                "KOKONUT_FEATURE_PREFECT": "false",
                "KOKONUT_FEATURE_NOTIFICATION_DELIVERY": "true",
                "KOKONUT_FEATURE_LEGACY_DATASET_SQL": "false",
            }
        )
        event_process, lines, output = _start_worker_process(
            "cmd_event_worker", worker_id, env
        )
        notification_process, notification_lines, notification_output = (
            _start_worker_process(
                "cmd_notification_worker", notification_worker_id, env
            )
        )
        event_before = _enqueue(name, event_type)
        try:
            before_worker, before_handler_status = _wait_for_completed(
                name, event_before, timeout
            )
        except TimeoutError as exc:
            _drain_output(output, lines)
            _drain_output(notification_output, notification_lines)
            event_state = _sql(
                name,
                "SELECT e.status || '|' || COALESCE(e.worker_id, '') || '|' || "
                "COALESCE(e.error_message, '') || '|' || COALESCE(d.status, '') || '|' || "
                "COALESCE(d.last_error, '') || '|' || COALESCE(dl.last_error, '') "
                "FROM platform_event e LEFT JOIN event_handler_delivery d "
                "ON d.event_id = e.id LEFT JOIN event_dead_letter dl "
                "ON dl.original_event_id = e.id "
                f"WHERE e.id = '{event_before}'",
            )
            raise RuntimeError(
                f"{exc}; event worker logs={lines[-20:]}; "
                f"notification worker logs={notification_lines[-20:]}; "
                f"event process exit={event_process.poll()}; "
                f"notification process exit={notification_process.poll()}; "
                f"event state={event_state!r}"
            ) from exc
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
        _wait_for_log(
            event_process, lines, output, "Event worker iteration failed", timeout,
            "event worker",
        )
        _wait_for_log(
            notification_process,
            notification_lines,
            notification_output,
            "Event worker iteration failed",
            timeout,
            "notification worker",
        )
        if event_process.poll() is not None or notification_process.poll() is not None:
            raise RuntimeError("a dedicated worker exited during the database outage")

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

        event_during_worker_crash = _enqueue(name, event_type)
        crash_worker, crash_handler_status = _wait_for_completed(
            name, event_during_worker_crash, timeout
        )
        if crash_worker != worker_id or crash_handler_status != "success":
            raise RuntimeError("crash-probe event did not complete through the allowlisted handler")
        notification_during_crash = _wait_for_notification_state(
            name, event_during_worker_crash, "processing", "processing", timeout
        )
        assert webhook_requests is not None
        accepted_before_crash = _wait_for_webhook(webhook_requests, timeout)
        if accepted_before_crash["request_number"] != "4":
            raise RuntimeError("crash probe did not reach the expected blocked webhook request")
        if accepted_before_crash["idempotency_key"] != notification_during_crash:
            raise RuntimeError("crash-probe request used the wrong notification idempotency key")
        if notification_process.poll() is not None:
            raise RuntimeError("notification worker exited before the crash-probe request")
        notification_process.kill()
        notification_process.wait(timeout=5)
        assert release_crash_probe is not None
        release_crash_probe.set()
        _expire_notification_lease(name, notification_during_crash)

        recovery = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.events",
                "--notification-process",
                "--worker-id",
                "event-notification-crash-recovery",
                "--batch-size",
                "10",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if recovery.returncode:
            raise RuntimeError("replacement notification worker failed its one-shot batch")
        if _wait_for_notification_state(
            name, event_during_worker_crash, "succeeded", "succeeded", timeout
        ) != notification_during_crash:
            raise RuntimeError("worker-crash recovery changed the notification identity")
        retry_after_crash = _wait_for_webhook(webhook_requests, timeout)
        if retry_after_crash["request_number"] != "5":
            raise RuntimeError("replacement worker did not make the expected second delivery")
        if retry_after_crash["idempotency_key"] != accepted_before_crash["idempotency_key"]:
            raise RuntimeError("worker-crash delivery did not reuse the notification idempotency key")
        attempt_history = _sql(
            name,
            "SELECT string_agg(status, ',' ORDER BY attempt_number) "
            "FROM notification_outbox_attempt "
            f"WHERE outbox_id = '{notification_during_crash}'",
        )
        if attempt_history != "lease_lost,succeeded":
            raise RuntimeError("worker-crash attempt history was not lease_lost then succeeded")

        # Stop the compatibility dispatcher before exercising migration 648's
        # dedicated identity so the same event table has exactly one claimant.
        for process in (event_process, notification_process):
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT)
                process.wait(timeout=5)

        event_dispatch_password = secrets.token_urlsafe(32)
        migration_648 = (
            ROOT / "schemas" / "postgres" / "648_isolated_event_dispatch_worker.sql"
        ).read_text(encoding="utf-8")
        _docker(
            "exec", "-i", name, "psql", "-X", "-v", "ON_ERROR_STOP=1",
            "-h", "127.0.0.1", "-U", "kokonut", "-d", "kokonut_intelligence",
            check=True, stdin=migration_648,
        )
        _sql(
            name,
            "ALTER ROLE kokonut_event_dispatch_login WITH LOGIN PASSWORD "
            f"'{event_dispatch_password}'",
        )
        isolated_env = env.copy()
        for shared_name in (
            "DATABASE_URL", "PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD",
            "POSTGRES_PASSWORD", "KOKONUT_DB_ADMIN_USER", "KOKONUT_DB_ADMIN_PASSWORD",
        ):
            isolated_env.pop(shared_name, None)
        isolated_env.update(
            {
                "KOKONUT_FEATURE_ISOLATED_EVENT_DISPATCH": "true",
                "KOKONUT_ISOLATED_WORKER_KEY": "event_dispatch",
                "KOKONUT_EVENT_DISPATCH_DATABASE_URL": (
                    "postgresql://kokonut_event_dispatch_login:"
                    f"{event_dispatch_password}@127.0.0.1:{port}/kokonut_intelligence"
                    "?connect_timeout=2"
                ),
            }
        )
        isolated_event_process, isolated_lines, isolated_output = _start_worker_process(
            "cmd_isolated_event_worker", isolated_worker_id, isolated_env
        )
        isolated_before = _enqueue(name, "isolated_reconnect_probe")
        _wait_for_isolated_event(name, isolated_before, isolated_worker_id, timeout)

        _docker("stop", "--time", "1", name)
        _wait_for_log(
            isolated_event_process, isolated_lines, isolated_output,
            "Event worker iteration failed", timeout, "isolated event worker",
        )
        if isolated_event_process.poll() is not None:
            raise RuntimeError("isolated event worker exited during the database outage")
        _docker("start", name)
        _wait_until_ready(name, timeout)
        isolated_after = _enqueue(name, "isolated_reconnect_probe")
        _wait_for_isolated_event(name, isolated_after, isolated_worker_id, timeout)

        result.update(
            {
                "result": "passed",
                "worker_alive_during_outage": True,
                "event_worker_alive_during_outage": True,
                "notification_worker_alive_during_outage": True,
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
                "worker_killed_before_notification_ack": True,
                "worker_crash_lease_reclaimed": True,
                "duplicate_delivery_reused_idempotency_key": True,
                "worker_crash_attempt_history": attempt_history,
                "isolated_event_worker_alive_during_outage": True,
                "isolated_event_worker_reconnected_after_restart": True,
                "isolated_event_before_restart_completed_without_handler_receipts": True,
                "isolated_event_after_restart_completed_without_handler_receipts": True,
                "isolated_event_worker_id": isolated_worker_id,
                "source_notification_idempotency_keys_distinct": True,
                "loopback_webhook_calls": 5,
                "worker_id": worker_id,
                "notification_worker_id": notification_worker_id,
                "migrations_replayed": [
                    "116_event_bus.sql",
                    "165_event_bus_durability.sql",
                    "375_notification_outbox.sql",
                    "648_isolated_event_dispatch_worker.sql",
                ],
                "fixture_schema_shims": [
                    "notification_outbox.location_id from migration 406",
                ],
                "limitations": [
                    "Only the event, durable-handler, and notification table migrations were replayed in the disposable database; the full ordered schema ledger was not applied.",
                    "The current optional notification location column was added as a minimal fixture shim instead of replaying migration 406, whose unrelated sensor-table prerequisites are outside this recovery test.",
                    "The real allowlisted alert-notification handler ran in its spawned child process and queued webhooks to a temporary HTTP server bound to 127.0.0.1; no remote provider was contacted.",
                    "The local server returned one synthetic 503, then accepted the retry and the post-restart notification. The first notification recovered from retryable/failed to succeeded/succeeded; its retry reused the same durable notification ID as the idempotency key.",
                    "A third notification request was received while its worker was blocked before receiving the HTTP response. The process was killed, its lease expired in the fixture, and a one-shot replacement worker reclaimed it; the attempt history was lease_lost then succeeded, and the duplicate request reused the same idempotency key.",
                    "All five loopback requests carried their matching durable notification IDs as idempotency keys; retries reused the source notification ID, while the three source events used distinct IDs.",
                    "The isolated dispatcher used a synthetic dedicated-login password and only its migration-648 bounded functions; its two unregistered synthetic event types completed with zero handler-delivery rows.",
                    "Both legacy worker processes were stopped before migration 648 was exercised; the isolated dispatcher remained alive during PostgreSQL stop/start and completed a new event after reconnect.",
                    "The PostgreSQL container had no volume and was bound only to loopback.",
                ],
            }
        )
    finally:
        for process in (event_process, notification_process, isolated_event_process):
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        _docker("rm", "--force", name, check=False)
        if release_crash_probe is not None:
            release_crash_probe.set()
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
