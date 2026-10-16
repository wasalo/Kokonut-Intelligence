#!/usr/bin/env python3
"""Exercise KGP worker lease renewal across a disposable PostgreSQL restart."""

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
        # passed to `docker run` as an environment value.
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
            raise RuntimeError(f"KGP worker exited with status {process.returncode}")
        try:
            line = output.get(timeout=min(0.2, deadline - time.monotonic()))
        except queue.Empty:
            continue
        if line is None:
            raise RuntimeError("KGP worker output closed before database recovery")
        lines.append(line)
        if expected in line:
            return
    raise TimeoutError(f"KGP worker did not log {expected!r} within {timeout:g}s")


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


def _heartbeat(name: str, deployment_id: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _docker(
            "exec",
            name,
            "psql",
            "-XAt",
            "-h",
            "127.0.0.1",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            "-c",
            (
                "SELECT COALESCE(lease_owner, ''), COALESCE("
                "to_char(heartbeat_at AT TIME ZONE 'UTC', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.US'), '') "
                f"FROM kgp_indexer_cursor WHERE deployment_id = '{deployment_id}'"
            ),
            check=False,
        )
        if result.returncode == 0:
            values = result.stdout.strip().split("|")
            if len(values) == 2 and values[0] == "kgp-reconnect-probe" and values[1]:
                return values[1]
        time.sleep(0.25)
    raise TimeoutError("KGP worker did not claim and heartbeat its disposable lease")


def main() -> int:
    image = os.environ.get("KGP_RECONNECT_POSTGRES_IMAGE", "postgres:16-alpine")
    timeout = float(os.environ.get("KGP_RECONNECT_TIMEOUT", "30"))
    name = f"kokonut-kgp-reconnect-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    deployment_id = str(uuid.uuid4())
    process: subprocess.Popen[str] | None = None
    lines: list[str] = []
    output: queue.Queue[str | None] = queue.Queue()
    result: dict[str, object] = {
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
        _wait_until_ready(name, timeout)
        _docker(
            "exec",
            name,
            "psql",
            "-Xv",
            "ON_ERROR_STOP=1",
            "-h",
            "127.0.0.1",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            "-c",
            """
            CREATE TABLE kgp_indexer_cursor (
                id uuid PRIMARY KEY,
                deployment_id uuid UNIQUE NOT NULL,
                next_block bigint NOT NULL DEFAULT 1,
                last_block_number bigint,
                last_block_hash text,
                lease_owner text,
                lease_token uuid,
                lease_expires_at timestamptz,
                heartbeat_at timestamptz,
                status text NOT NULL DEFAULT 'idle',
                retry_count integer NOT NULL DEFAULT 0,
                last_error text,
                updated_at timestamptz NOT NULL DEFAULT now()
            );
            INSERT INTO kgp_indexer_cursor (id, deployment_id)
            VALUES (gen_random_uuid(), '""" + deployment_id + """');
            """,
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
                "KOKONUT_LOG_LEVEL": "INFO",
                "KGP_CONFIRMATIONS": "12",
            }
        )
        worker_code = f"""
from types import SimpleNamespace
from services.guilds.indexer import KGPIndexer

indexer = object.__new__(KGPIndexer)
indexer.deployment_id = {deployment_id!r}
indexer.contract_addresses = {{}}
indexer.w3 = SimpleNamespace(eth=SimpleNamespace(block_number=0))
indexer.run_forever(poll_interval=0.25, worker_id="kgp-reconnect-probe")
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
        try:
            heartbeat_before = _heartbeat(name, deployment_id, timeout)
        except TimeoutError as exc:
            while True:
                try:
                    worker_line = output.get_nowait()
                except queue.Empty:
                    break
                if worker_line is None:
                    break
                lines.append(worker_line)
            details = " | ".join(lines[-12:])
            raise RuntimeError(f"{exc}; worker output: {details or '<no output>'}") from exc

        _docker("stop", "--time", "1", name)
        _wait_for_log(process, lines, output, "KGP scan failed", timeout)
        if process.poll() is not None:
            raise RuntimeError("KGP worker exited during the database outage")

        _docker("start", name)
        _wait_until_ready(name, timeout)
        deadline = time.monotonic() + timeout
        heartbeat_after = ""
        while time.monotonic() < deadline:
            try:
                candidate = _heartbeat(name, deployment_id, min(2, timeout))
            except TimeoutError:
                continue
            if candidate > heartbeat_before:
                heartbeat_after = candidate
                break
            time.sleep(0.25)
        if not heartbeat_after:
            raise TimeoutError("KGP worker did not renew its lease after PostgreSQL restart")

        result.update(
            {
                "result": "passed",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "lease_heartbeat_before_restart": heartbeat_before,
                "lease_heartbeat_after_restart": heartbeat_after,
                "worker_id": "kgp-reconnect-probe",
                "limitations": [
                    "The cursor schema and row were synthetic; the test exercises the real KGP lease claim, heartbeat, release, and connection loop, not production migrations or chain event processing.",
                    "The Web3 block height was stubbed below the first cursor block, so no RPC or event queries were made.",
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
