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
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _compose(
    project: str,
    compose_file: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            "/dev/null",
            "-p",
            project,
            "-f",
            str(compose_file),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode:
        raise RuntimeError(f"Docker Compose {args[0]} failed: {result.stderr.strip()}")
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


def _sql(project: str, compose_file: Path, statement: str) -> str:
    result = _compose(
        project,
        compose_file,
        "exec",
        "-T",
        "database",
        "psql",
        "-q",
        "-XAt",
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


def _wait_until_ready(project: str, compose_file: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready = _compose(
            project,
            compose_file,
            "exec",
            "-T",
            "database",
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


def _heartbeat(
    project: str,
    compose_file: Path,
    deployment_id: str,
    expected_worker: str,
    timeout: float,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            output = _sql(
                project,
                compose_file,
            (
                "SELECT COALESCE(lease_owner, ''), COALESCE("
                "to_char(heartbeat_at AT TIME ZONE 'UTC', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.US'), '') "
                f"FROM kgp_indexer_cursor WHERE deployment_id = '{deployment_id}'"
            ),
            )
        except RuntimeError:
            output = ""
        if output:
            values = output.split("|")
            if len(values) == 2 and values[0] == expected_worker and values[1]:
                return values[1]
        time.sleep(0.25)
    raise TimeoutError("KGP worker did not claim and heartbeat its disposable lease")


def _worker_code(deployment_id: str, worker_id: str) -> str:
    return f"""
from types import SimpleNamespace
from services.guilds.indexer import KGPIndexer

indexer = object.__new__(KGPIndexer)
indexer.deployment_id = {deployment_id!r}
indexer.contract_addresses = {{}}
indexer.w3 = SimpleNamespace(eth=SimpleNamespace(block_number=0))
indexer.run_forever(poll_interval=0.25, worker_id={worker_id!r})
"""


def _replay_schema_migrations(port: int, password: str) -> int:
    """Validate and transactionally replay each current schema source file."""
    import psycopg2

    from services.migration.cli import (
        _discover_files,
        _migration_body_without_transaction,
        _validate_sources,
    )

    migrations = _discover_files(include_seeds=False)
    _validate_sources(migrations)
    connection = psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="kokonut_intelligence",
        user="kokonut",
        password=password,
        connect_timeout=5,
        options="-c statement_timeout=120000 -c lock_timeout=15000",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migration (
                    version VARCHAR(512) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    sql_up TEXT NOT NULL,
                    checksum VARCHAR(64) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    execution_time_ms INTEGER,
                    applied_at TIMESTAMPTZ DEFAULT NOW(),
                    applied_by VARCHAR(100)
                )
                """
            )
            cursor.execute(
                "ALTER TABLE schema_migration ALTER COLUMN version TYPE VARCHAR(512)"
            )
            cursor.execute(
                "ALTER TABLE schema_migration "
                "ADD COLUMN IF NOT EXISTS migration_id VARCHAR(512)"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_schema_migration_id "
                "ON schema_migration (migration_id) WHERE migration_id IS NOT NULL"
            )
        connection.commit()

        for migration in migrations:
            sql = _migration_body_without_transaction(
                migration["id"], migration["path"].read_text()
            )
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SET search_path = public, topology, tiger")
                        cursor.execute(sql)
                        cursor.execute(
                            """
                            INSERT INTO schema_migration
                                (migration_id, version, name, sql_up, checksum,
                                 status, execution_time_ms, applied_by)
                            VALUES (%s, %s, %s, %s, %s, 'applied', 0, 'kgp-disposable-check')
                            """,
                            (
                                migration["id"],
                                migration["id"],
                                migration["name"],
                                f"(see {migration['path'].name})",
                                migration["checksum"],
                            ),
                        )
            except Exception as exc:
                raise RuntimeError(
                    f"ordered schema migration {migration['id']} failed: {exc}"
                ) from exc
        return len(migrations)
    finally:
        connection.close()


def main() -> int:
    image = os.environ.get(
        "KGP_RECONNECT_POSTGRES_IMAGE",
        "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
    )
    timeout = float(os.environ.get("KGP_RECONNECT_TIMEOUT", "45"))
    project = f"kokonut-kgp-schema-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    deployment_id = str(uuid.uuid4())
    worker_id = "kgp-reconnect-probe"
    recovery_worker_id = "kgp-crash-recovery"
    process: subprocess.Popen[str] | None = None
    lines: list[str] = []
    output: queue.Queue[str | None] = queue.Queue()
    compose_handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix="kokonut-kgp-", delete=False
    )
    compose_file = Path(compose_handle.name)
    compose_handle.write(
        "services:\n"
        "  database:\n"
        f"    image: {json.dumps(image)}\n"
        "    restart: 'no'\n"
        "    environment:\n"
        f"      POSTGRES_DB: {json.dumps('kokonut_intelligence')}\n"
        f"      POSTGRES_USER: {json.dumps('kokonut')}\n"
        f"      POSTGRES_PASSWORD: {json.dumps(password)}\n"
        "    ports:\n"
        f"      - {json.dumps(f'127.0.0.1:{port}:5432')}\n"
    )
    compose_handle.close()
    result: dict[str, object] = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "database_image": image,
        "database_port_binding": "127.0.0.1 only",
        "database_volume": False,
        "database_network": "default bridge; outbound calls are not used",
        "schema_migration_mode": (
            "ordered validated repository schema sources; one transaction per file"
        ),
        "external_provider_calls": 0,
        "candidate_or_legacy_modified": False,
    }
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
            "POSTGRES_PASSWORD": password,
            "KOKONUT_LOG_LEVEL": "INFO",
            "KGP_CONFIRMATIONS": "12",
        }
    )

    try:
        _compose(project, compose_file, "up", "--detach", "database")
        _wait_until_ready(project, compose_file, timeout)
        applied_schemas = _replay_schema_migrations(port, password)
        expected_schemas = sum(
            path.stem.split("_", 1)[0].isdigit()
            for path in (ROOT / "schemas" / "postgres").glob("*.sql")
        )
        applied_schemas = int(
            _sql(
                project,
                compose_file,
                "SELECT COUNT(*) FROM schema_migration "
                "WHERE migration_id LIKE 'schema:%' AND status = 'applied'",
            )
        )
        if applied_schemas != expected_schemas:
            raise RuntimeError(
                "ordered schema replay count mismatch: "
                f"expected {expected_schemas}, applied {applied_schemas}"
            )
        _sql(
            project,
            compose_file,
            "INSERT INTO kgp_protocol_deployment "
            "(id, deployment_key, chain_id, network_name, proxy_address, "
            "implementation_address, contract_version) VALUES ("
            f"'{deployment_id}', 'disposable-{uuid.uuid4().hex}', 100, "
            "'disposable', '0x1111111111111111111111111111111111111111', "
            "'0x2222222222222222222222222222222222222222', 'acceptance')",
        )
        _sql(
            project,
            compose_file,
            "INSERT INTO kgp_indexer_cursor (deployment_id, next_block) "
            f"VALUES ('{deployment_id}', 1)",
        )
        result["schema_migrations_applied"] = applied_schemas
        result["schema_migrations_expected"] = expected_schemas

        process = subprocess.Popen(
            [sys.executable, "-u", "-c", _worker_code(deployment_id, worker_id)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        initial_process = process

        def collect_output(worker_process=initial_process) -> None:
            assert worker_process is not None and worker_process.stdout is not None
            for output_line in worker_process.stdout:
                output.put(output_line.rstrip())
            output.put(None)

        threading.Thread(target=collect_output, daemon=True).start()
        try:
            heartbeat_before = _heartbeat(
                project, compose_file, deployment_id, worker_id, timeout
            )
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

        _compose(project, compose_file, "stop", "--timeout", "1", "database")
        _wait_for_log(process, lines, output, "KGP scan failed", timeout)
        if process.poll() is not None:
            raise RuntimeError("KGP worker exited during the database outage")

        _compose(project, compose_file, "start", "database")
        _wait_until_ready(project, compose_file, timeout)
        deadline = time.monotonic() + timeout
        heartbeat_after = ""
        while time.monotonic() < deadline:
            try:
                candidate = _heartbeat(
                    project, compose_file, deployment_id, worker_id, min(2, timeout)
                )
            except TimeoutError:
                continue
            if candidate > heartbeat_before:
                heartbeat_after = candidate
                break
            time.sleep(0.25)
        if not heartbeat_after:
            raise TimeoutError("KGP worker did not renew its lease after PostgreSQL restart")

        process.kill()
        process.wait(timeout=5)
        expired = _sql(
            project,
            compose_file,
            "UPDATE kgp_indexer_cursor SET lease_expires_at = NOW() - INTERVAL '1 second' "
            f"WHERE deployment_id = '{deployment_id}' AND lease_owner = '{worker_id}' "
            "RETURNING deployment_id",
        )
        if not expired.splitlines() or expired.splitlines()[0].strip() != deployment_id:
            raise RuntimeError(f"could not expire the killed KGP worker lease: {expired!r}")

        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                _worker_code(deployment_id, recovery_worker_id),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            text=True,
        )
        heartbeat_after_reclaim = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                candidate = _heartbeat(
                    project,
                    compose_file,
                    deployment_id,
                    recovery_worker_id,
                    min(2, timeout),
                )
            except TimeoutError:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"replacement KGP worker exited with status {process.returncode}"
                    )
                continue
            if candidate > heartbeat_after:
                heartbeat_after_reclaim = candidate
                break
            time.sleep(0.25)
        if not heartbeat_after_reclaim:
            raise TimeoutError("replacement KGP worker did not reclaim and heartbeat its lease")

        result.update(
            {
                "result": "passed",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "lease_heartbeat_before_restart": heartbeat_before,
                "lease_heartbeat_after_restart": heartbeat_after,
                "worker_killed_and_lease_reclaimed": True,
                "lease_owner_before_reclaim": worker_id,
                "lease_owner_after_reclaim": recovery_worker_id,
                "lease_heartbeat_after_reclaim": heartbeat_after_reclaim,
                "worker_id": worker_id,
                "limitations": [
                    "All current ordered PostgreSQL schema migrations were applied, but the deployment and cursor rows are synthetic; no seed data or candidate/legacy database was used.",
                    "The Web3 block height was stubbed below the first cursor block, so no RPC or event queries were made.",
                    "The PostgreSQL container had no volume and published only a loopback port. The default bridge permits egress, but this check makes no external provider or chain calls.",
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
        _compose(
            project,
            compose_file,
            "down",
            "--volumes",
            "--remove-orphans",
            check=False,
        )
        compose_file.unlink(missing_ok=True)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"result": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise
