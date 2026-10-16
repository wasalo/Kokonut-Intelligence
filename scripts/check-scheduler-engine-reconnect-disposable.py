#!/usr/bin/env python3
"""Exercise the real scheduler engine across a disposable PostgreSQL restart."""

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
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr.strip()}")
    return result


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_log(
    process: subprocess.Popen[str],
    output: queue.Queue[str | None],
    expected: str,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Scheduler worker exited with status {process.returncode}")
        try:
            line = output.get(timeout=min(0.2, deadline - time.monotonic()))
        except queue.Empty:
            continue
        if line is None:
            raise RuntimeError("Scheduler worker output closed before database recovery")
        if expected in line:
            return
    raise TimeoutError(f"Scheduler worker did not log {expected!r} within {timeout:g}s")


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


def _create_task(name: str, suffix: str) -> str:
    task_name = f"reconnect_probe_{suffix}_{uuid.uuid4().hex[:8]}"
    return _sql(
        name,
        "INSERT INTO scheduled_task "
        "(name, module_path, cron_expression, timeout_seconds, command_args, next_run_at) "
        "VALUES ("
        f"'{task_name}', 'services.events', '* * * * *', 30, "
        "'[\"--process\",\"--batch-size\",\"10\"]'::jsonb, NOW() - INTERVAL '1 minute') "
        "RETURNING id",
    )


def _wait_for_completed(name: str, task_id: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _sql(
            name,
            "SELECT status, COALESCE(worker_id, '') FROM task_run "
            f"WHERE task_id = '{task_id}' ORDER BY started_at DESC LIMIT 1",
        ).split("|")
        if len(values) == 2 and values[0] == "completed" and values[1]:
            return values[1]
        time.sleep(0.25)
    raise TimeoutError("SchedulerEngine did not complete the synthetic task")


def main() -> int:
    image = os.environ.get("SCHEDULER_ENGINE_RECONNECT_POSTGRES_IMAGE", "postgres:16-alpine")
    timeout = float(os.environ.get("SCHEDULER_ENGINE_RECONNECT_TIMEOUT", "45"))
    name = f"kokonut-scheduler-engine-reconnect-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    process: subprocess.Popen[str] | None = None
    output: queue.Queue[str | None] = queue.Queue()
    worker_id = "scheduler-engine-reconnect-probe"
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

        migrations = (
            "116_event_bus.sql",
            "117_task_scheduler.sql",
            "164_scheduler_durability.sql",
            "165_event_bus_durability.sql",
            "337_scheduler_ownership.sql",
            "371_scheduler_run_windows.sql",
        )
        for migration in migrations:
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
                "KOKONUT_FEATURE_DIRECTUS": "false",
                "KOKONUT_FEATURE_CLICKHOUSE": "false",
                "KOKONUT_FEATURE_GRPC": "false",
                "KOKONUT_FEATURE_METABASE": "false",
                "KOKONUT_FEATURE_MQTT": "false",
                "KOKONUT_FEATURE_PREFECT": "false",
                "KOKONUT_FEATURE_LEGACY_DATASET_SQL": "false",
                "ALERT_WEBHOOK_URL": "",
                "ALERT_SMTP_HOST": "",
                "ALERT_EMAIL_TO": "",
                "DIRECTUS_ADMIN_TOKEN": "",
            }
        )
        worker_code = f"""
from services.scheduler.worker import run_worker
run_worker(tick_interval=1, worker_id={worker_id!r})
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
        task_before = _create_task(name, "before")
        first_worker = _wait_for_completed(name, task_before, timeout)
        if first_worker != worker_id:
            raise RuntimeError("pre-outage task was not claimed by the probe worker")

        _docker("stop", "--time", "1", name)
        _wait_for_log(process, output, "Scheduler tick failed", timeout)
        if process.poll() is not None:
            raise RuntimeError("scheduler worker exited during the database outage")

        _docker("start", name)
        _wait_until_ready(name, timeout)
        task_after = _create_task(name, "after")
        second_worker = _wait_for_completed(name, task_after, timeout)
        if second_worker != worker_id:
            raise RuntimeError("post-outage task was not claimed by the probe worker")

        result.update(
            {
                "result": "passed",
                "scheduler_engine": "real SchedulerEngine",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "task_before_restart_completed": True,
                "task_after_restart_completed": True,
                "both_runs_claimed_by_same_worker": True,
                "task_command": "python -m services.events --process --batch-size 10",
                "worker_id": worker_id,
                "migrations_replayed": list(migrations),
                "limitations": [
                    "Only the scheduler, event bus, and durable ownership migrations were replayed; the full schema ledger was not applied.",
                    "The bounded task ran EventBus processing against an empty synthetic queue; no domain provider or external service ran.",
                    "The outage occurred between completed tasks, so this does not test recovery or lease reclaim after a worker dies mid-task.",
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
