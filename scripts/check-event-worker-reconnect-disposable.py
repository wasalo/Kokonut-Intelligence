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
    return _sql(
        name,
        "INSERT INTO platform_event (event_type, payload) "
        f"VALUES ('{event_type}', '{{}}'::jsonb) RETURNING id",
    )


def _wait_for_completed(name: str, event_id: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _sql(
            name,
            "SELECT status, COALESCE(worker_id, '') FROM platform_event "
            f"WHERE id = '{event_id}'",
        ).split("|")
        if len(values) == 2 and values[0] == "completed" and values[1]:
            return values[1]
        time.sleep(0.25)
    raise TimeoutError("EventBus worker did not complete the synthetic event")


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
    event_type = f"reconnect_probe_{uuid.uuid4().hex[:12]}"
    result: dict[str, object] = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "database_image": image,
        "database_port_binding": "127.0.0.1 only",
        "database_volume": False,
        "candidate_or_legacy_modified": False,
        "external_provider_calls": 0,
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
                "ALERT_WEBHOOK_URL": "",
                "ALERT_SMTP_HOST": "",
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
        before_worker = _wait_for_completed(name, event_before, timeout)
        if before_worker != worker_id:
            raise RuntimeError("synthetic pre-outage event was not claimed by the probe worker")

        _docker("stop", "--time", "1", name)
        _wait_for_log(process, lines, output, "Event worker iteration failed", timeout)
        if process.poll() is not None:
            raise RuntimeError("Event worker exited during the database outage")

        _docker("start", name)
        _wait_until_ready(name, timeout)
        event_after = _enqueue(name, event_type)
        after_worker = _wait_for_completed(name, event_after, timeout)
        if after_worker != worker_id:
            raise RuntimeError("synthetic post-outage event was not claimed by the probe worker")

        result.update(
            {
                "result": "passed",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "event_before_restart_completed": True,
                "event_after_restart_completed": True,
                "both_events_claimed_by_same_worker": True,
                "worker_id": worker_id,
                "migrations_replayed": [
                    "116_event_bus.sql",
                    "165_event_bus_durability.sql",
                    "375_notification_outbox.sql",
                ],
                "limitations": [
                    "Only the event, durable-handler, and notification table migrations were replayed in the disposable database; the full ordered schema ledger was not applied.",
                    "Synthetic events had no matching handlers, so the real EventBus lease and completion SQL ran without invoking application handlers.",
                    "Notification processing used the real outbox query against an empty queue; no external delivery provider was configured.",
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

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"result": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise
