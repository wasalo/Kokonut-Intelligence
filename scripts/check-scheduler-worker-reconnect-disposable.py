#!/usr/bin/env python3
"""Exercise scheduler worker reconnect after a disposable PostgreSQL restart."""

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


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if check and result.returncode:
        # Avoid echoing command arguments because the disposable password is
        # passed to `docker run` as an argument.
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr.strip()}")
    return result


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_new_line(
    process: subprocess.Popen[str],
    lines: list[str],
    output: queue.Queue[str | None],
    start: int,
    expected: str,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"scheduler worker exited with status {process.returncode}")
        remaining = deadline - time.monotonic()
        try:
            line = output.get(timeout=min(0.2, remaining))
        except queue.Empty:
            continue
        if line is None:
            tail = " | ".join(lines[-12:])
            raise RuntimeError(f"scheduler worker output closed before expected recovery: {tail}")
        lines.append(line)
        if any(expected in item for item in lines[start:]):
            return
    raise TimeoutError(f"scheduler worker did not log {expected!r} within {timeout:g}s")


def main() -> int:
    image = os.environ.get("SCHEDULER_RECONNECT_POSTGRES_IMAGE", "postgres:16-alpine")
    timeout = float(os.environ.get("SCHEDULER_RECONNECT_TIMEOUT", "30"))
    name = f"kokonut-scheduler-reconnect-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    process = None
    lines: list[str] = []
    output: queue.Queue[str | None] = queue.Queue()
    result = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "database_image": image,
        "database_port_binding": "127.0.0.1 only",
        "database_volume": False,
        "candidate_or_legacy_modified": False,
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

        readiness_deadline = time.monotonic() + timeout
        while time.monotonic() < readiness_deadline:
            ready = _docker(
                "exec",
                name,
                "pg_isready",
                "-h", "127.0.0.1", "-U",
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
            }
        )
        worker_code = """
import services.scheduler.worker as worker

class ProbeEngine:
    def __init__(self, worker_id):
        self.worker_id = worker_id

    def tick(self):
        return {"launched": 1, "failed": 0, "skipped": 0, "no_resources": 0}

worker.get_scheduler = lambda conn, worker_id=None: ProbeEngine(worker_id)
worker.run_worker(tick_interval=1, worker_id="reconnect-probe")
"""
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", worker_code],
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
        _wait_for_new_line(process, lines, output, 0, "Tick complete: launched=1", timeout)
        first_success_count = sum("Tick complete: launched=1" in line for line in lines)

        _docker("stop", "--time", "1", name)
        _wait_for_new_line(
            process,
            lines,
            output,
            len(lines),
            "Scheduler tick failed",
            timeout,
        )
        if process.poll() is not None:
            raise RuntimeError("scheduler worker exited during the database outage")

        _docker("start", name)
        success_start = len(lines)
        _wait_for_new_line(process, lines, output, success_start, "Tick complete: launched=1", timeout)
        recovered_success_count = sum("Tick complete: launched=1" in line for line in lines[success_start:])
        if recovered_success_count < 1:
            raise RuntimeError("worker did not log a successful tick after PostgreSQL restart")

        result.update(
            {
                "result": "passed",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "successful_tick_before_restart": first_success_count > 0,
                "successful_tick_after_restart": True,
                "worker_id": "reconnect-probe",
                "limitations": [
                    "The scheduler engine was stubbed; the test verifies PostgreSQL reconnect and worker process survival, not task SQL, leases, or provider delivery.",
                    "The PostgreSQL container had no volume and was bound only to loopback.",
                ],
            }
        )
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
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
