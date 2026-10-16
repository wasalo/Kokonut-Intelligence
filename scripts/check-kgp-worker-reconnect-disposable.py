#!/usr/bin/env python3
"""Exercise KGP event projection and worker recovery in disposable PostgreSQL."""

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
indexer.w3 = SimpleNamespace(eth=SimpleNamespace(
    block_number=0,
    get_block=lambda _number: SimpleNamespace(hash=bytes.fromhex("f7" * 32)),
))
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


def _exercise_protocol_projection(port: int, password: str, deployment_id: str) -> dict[str, object]:
    """Run dependent synthetic registry/domain/task logs through the indexer."""
    # The disposable check supplies its own database settings; importing the
    # indexer must not attempt to decrypt the repository's unrelated secrets.
    os.environ["KOKONUT_ENV"] = "development"
    os.environ["KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT"] = "true"

    from types import SimpleNamespace

    import psycopg2
    from eth_abi import encode

    from services.guilds.indexer import EVENT_TOPICS, KGPIndexer

    contract_addresses = {
        "registry": "0x3333333333333333333333333333333333333333",
        "domains": "0x4444444444444444444444444444444444444444",
        "tasks": "0x5555555555555555555555555555555555555555",
    }
    guild_id = "0x" + "a1" * 32
    guild_key = "0x" + "b2" * 32
    block_hash = "0x" + "c3" * 32

    topics_by_name = {
        name: bytes.fromhex(topic[2:]) for topic, name in EVENT_TOPICS.items()
    }

    def indexed_uint(value: int) -> bytes:
        return value.to_bytes(32, byteorder="big")

    def synthetic_log(event_name, address, topics, data, block_number, log_index, tx_byte):
        return {
            "address": address,
            "topics": [topics_by_name[event_name], *topics],
            "data": data,
            "blockNumber": block_number,
            "blockHash": bytes.fromhex(block_hash[2:]),
            "transactionHash": bytes.fromhex(tx_byte * 32),
            "transactionIndex": 0,
            "logIndex": log_index,
        }

    raw_logs = [
        synthetic_log(
            "GuildCreated",
            contract_addresses["registry"],
            [bytes.fromhex(guild_id[2:]), bytes.fromhex(guild_key[2:]), bytes.fromhex("00" * 12 + "e5" * 20)],
            encode(["string"], ["Synthetic KGP projection guild"]),
            8,
            2,
            "d4",
        ),
        synthetic_log(
            "DomainCreated",
            contract_addresses["domains"],
            [indexed_uint(7), bytes.fromhex(guild_id[2:]), indexed_uint(0)],
            encode(["string", "address"], ["Synthetic KGP domain", "0x" + "e5" * 20]),
            9,
            3,
            "d5",
        ),
        synthetic_log(
            "TaskCreated",
            contract_addresses["tasks"],
            [indexed_uint(19), bytes.fromhex(guild_id[2:]), indexed_uint(7)],
            encode(["bytes32"], [bytes.fromhex("f6" * 32)]),
            10,
            4,
            "d6",
        ),
    ]

    class SyntheticEth:
        block_number = 30
        current_block_hash = bytes.fromhex(block_hash[2:])

        def get_logs(self, query):
            return [log for log in raw_logs if log["address"] == query["address"]]

        def get_block(self, _number):
            return SimpleNamespace(hash=self.current_block_hash)

    connection = psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="kokonut_intelligence",
        user="kokonut",
        password=password,
        connect_timeout=5,
    )
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE kgp_protocol_deployment "
                    "SET registry_address = %s, domain_address = %s, task_board_address = %s "
                    "WHERE id = %s",
                    (
                        contract_addresses["registry"],
                        contract_addresses["domains"],
                        contract_addresses["tasks"],
                        deployment_id,
                    ),
                )
                cursor.execute(
                    "INSERT INTO kokonut_guild (guild_key, name, onchain_guild_key) "
                    "VALUES (%s, %s, %s)",
                    ("synthetic-kgp-projection", "Synthetic KGP projection guild", guild_key),
                )

        indexer = KGPIndexer(
            SimpleNamespace(eth=SyntheticEth()),
            connection,
            deployment_id,
            contract_addresses,
            100,
        )
        projected_count = indexer.scan_once()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT guild.onchain_guild_id, guild.onchain_guild_key,
                       guild.chain_projection, guild.source_chain_event_id::text,
                       event.id::text, event.processing_status, event.processing_attempts
                FROM kokonut_guild AS guild
                JOIN kgp_chain_event AS event
                  ON event.deployment_id = %s
                 AND event.event_name = 'GuildCreated'
                WHERE guild.guild_key = %s
                """,
                (deployment_id, "synthetic-kgp-projection"),
            )
            guild_projection = cursor.fetchone()
            cursor.execute(
                """
                SELECT domain.onchain_domain_id, domain.name,
                       domain.chain_projection, domain.source_chain_event_id::text,
                       event.id::text, event.processing_status, event.processing_attempts
                FROM guild_domain AS domain
                JOIN kgp_chain_event AS event ON event.id = domain.source_chain_event_id
                WHERE domain.deployment_id = %s AND domain.onchain_domain_id = 7
                """,
                (deployment_id,),
            )
            domain_projection = cursor.fetchone()
            cursor.execute(
                """
                SELECT task.onchain_task_id, task.task_key, task.chain_projection,
                       task.source_chain_event_id::text, event.id::text,
                       event.processing_status, event.processing_attempts
                FROM guild_task AS task
                JOIN kgp_chain_event AS event ON event.id = task.source_chain_event_id
                WHERE task.deployment_id = %s AND task.onchain_task_id = 19
                """,
                (deployment_id,),
            )
            task_projection = cursor.fetchone()
            cursor.execute(
                "SELECT event_name, processing_status, processing_attempts "
                "FROM kgp_chain_event WHERE deployment_id = %s "
                "ORDER BY block_number, log_index",
                (deployment_id,),
            )
            processed_events = cursor.fetchall()
            cursor.execute(
                "SELECT next_block FROM kgp_indexer_cursor WHERE deployment_id = %s",
                (deployment_id,),
            )
            next_block = cursor.fetchone()[0]
        if (
            not guild_projection
            or guild_projection[:3] != (guild_id, guild_key, True)
            or guild_projection[3] != guild_projection[4]
            or guild_projection[5:] != ("processed", 0)
        ):
            raise RuntimeError(f"synthetic GuildCreated event did not project: {guild_projection!r}")
        if (
            not domain_projection
            or domain_projection[:3] != (7, "Synthetic KGP domain", True)
            or domain_projection[3] != domain_projection[4]
            or domain_projection[5:] != ("processed", 0)
        ):
            raise RuntimeError(f"synthetic DomainCreated event did not project: {domain_projection!r}")
        if (
            not task_projection
            or task_projection[:3] != (19, "0x" + "f6" * 32, True)
            or task_projection[3] != task_projection[4]
            or task_projection[5:] != ("processed", 0)
        ):
            raise RuntimeError(f"synthetic TaskCreated event did not project: {task_projection!r}")
        if projected_count != 3 or next_block != 19:
            raise RuntimeError(
                f"expected three processed dependent events and cursor 19, got "
                f"{projected_count} and {next_block}"
            )
        expected_events = [
            ("GuildCreated", "processed", 0),
            ("DomainCreated", "processed", 0),
            ("TaskCreated", "processed", 0),
        ]
        if processed_events != expected_events:
            raise RuntimeError(f"unexpected chain-event processing results: {processed_events!r}")

        # Re-read the same canonical logs from a rewound synthetic cursor. The
        # event idempotency keys must prevent duplicate projection rows.
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE kgp_indexer_cursor SET next_block = 1, confirmed_block = 0 "
                    "WHERE deployment_id = %s",
                    (deployment_id,),
                )
        duplicate_count = indexer.scan_once()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM kgp_chain_event WHERE deployment_id = %s",
                (deployment_id,),
            )
            event_rows = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM kokonut_guild "
                "WHERE guild_key = %s AND onchain_guild_id = %s AND chain_projection",
                ("synthetic-kgp-projection", guild_id),
            )
            guild_rows = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM guild_domain "
                "WHERE deployment_id = %s AND onchain_domain_id = 7 AND chain_projection",
                (deployment_id,),
            )
            domain_rows = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM guild_task "
                "WHERE deployment_id = %s AND onchain_task_id = 19 AND chain_projection",
                (deployment_id,),
            )
            task_rows = cursor.fetchone()[0]
        if duplicate_count != 0 or (event_rows, guild_rows, domain_rows, task_rows) != (3, 1, 1, 1):
            raise RuntimeError(
                "canonical log replay created duplicate chain/projection rows: "
                f"processed={duplicate_count}, counts={(event_rows, guild_rows, domain_rows, task_rows)}"
            )

        # Change the stubbed canonical tip. The real reorg path must orphan
        # projections, preserve the explicit guild-key match, and rebuild state
        # when those same protocol events reappear on the replacement branch.
        replacement_hash = bytes.fromhex("f7" * 32)
        SyntheticEth.current_block_hash = replacement_hash
        for raw_log in raw_logs:
            raw_log["blockHash"] = replacement_hash
        reorg_count = indexer.scan_once()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM kgp_chain_event "
                "WHERE deployment_id = %s AND is_canonical = FALSE "
                "AND processing_status = 'rejected'",
                (deployment_id,),
            )
            orphaned_events = cursor.fetchone()[0]
            cursor.execute(
                "SELECT onchain_guild_id, onchain_guild_key, chain_projection, source_chain_event_id "
                "FROM kokonut_guild WHERE guild_key = %s",
                ("synthetic-kgp-projection",),
            )
            guild_after_reorg = cursor.fetchone()
            cursor.execute(
                "SELECT COUNT(*) FROM guild_domain "
                "WHERE deployment_id = %s AND chain_projection",
                (deployment_id,),
            )
            domains_after_reorg = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM guild_task "
                "WHERE deployment_id = %s AND chain_projection",
                (deployment_id,),
            )
            tasks_after_reorg = cursor.fetchone()[0]
        if reorg_count != 0 or orphaned_events != 3:
            raise RuntimeError(
                f"synthetic reorg did not orphan the expected three events: "
                f"scan={reorg_count}, orphaned={orphaned_events}"
            )
        if guild_after_reorg != (None, guild_key, False, None):
            raise RuntimeError(f"guild identity binding was not retained across reorg: {guild_after_reorg!r}")
        if domains_after_reorg != 0 or tasks_after_reorg != 0:
            raise RuntimeError(
                "chain-owned dependent projections remained after reorg: "
                f"domains={domains_after_reorg}, tasks={tasks_after_reorg}"
            )

        reprojected_count = indexer.scan_once()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT event_name, processing_status, processing_attempts, is_canonical "
                "FROM kgp_chain_event WHERE deployment_id = %s "
                "ORDER BY block_number, log_index",
                (deployment_id,),
            )
            recanonical_events = cursor.fetchall()
            cursor.execute(
                "SELECT COUNT(*) FROM kokonut_guild "
                "WHERE guild_key = %s AND onchain_guild_id = %s AND chain_projection",
                ("synthetic-kgp-projection", guild_id),
            )
            recanonical_guilds = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM guild_domain "
                "WHERE deployment_id = %s AND onchain_domain_id = 7 AND chain_projection",
                (deployment_id,),
            )
            recanonical_domains = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM guild_task "
                "WHERE deployment_id = %s AND onchain_task_id = 19 AND chain_projection",
                (deployment_id,),
            )
            recanonical_tasks = cursor.fetchone()[0]
        if reprojected_count != 3 or recanonical_events != [
            ("GuildCreated", "processed", 0, True),
            ("DomainCreated", "processed", 0, True),
            ("TaskCreated", "processed", 0, True),
        ]:
            raise RuntimeError(f"canonical branch events were not replayed: {recanonical_events!r}")
        if (recanonical_guilds, recanonical_domains, recanonical_tasks) != (1, 1, 1):
            raise RuntimeError(
                "replacement branch projections were not rebuilt: "
                f"{(recanonical_guilds, recanonical_domains, recanonical_tasks)}"
            )
        return {
            "synthetic_events": ["GuildCreated", "DomainCreated", "TaskCreated"],
            "processed_event_count": projected_count,
            "projection_source_event_links_match": True,
            "all_event_rows_processed": True,
            "canonical_log_replay_idempotent": True,
            "event_rows_after_replay": event_rows,
            "guild_projection_rows_after_replay": guild_rows,
            "domain_projection_rows_after_replay": domain_rows,
            "task_projection_rows_after_replay": task_rows,
            "synthetic_reorg_detected": True,
            "orphaned_events_after_reorg": orphaned_events,
            "replacement_branch_replay_count": reprojected_count,
            "replacement_branch_projections_rebuilt": True,
        }
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
        projection = _exercise_protocol_projection(port, password, deployment_id)
        result["schema_migrations_applied"] = applied_schemas
        result["schema_migrations_expected"] = expected_schemas
        result["event_projection"] = projection

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
                    "All current ordered PostgreSQL schema migrations were applied, but the deployment, cursor, and prelinked guild rows are synthetic; no seed data or candidate/legacy database was used.",
                    "Live Web3/RPC was not used. One synthetic GuildCreated log was returned to the real indexer, and block height was stubbed for the worker recovery phase.",
                    "The canonical log was replayed after rewinding the disposable cursor; the idempotency key retained one chain-event row and one projected guild row.",
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
