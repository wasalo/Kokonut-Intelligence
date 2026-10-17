#!/usr/bin/env python3
"""Exercise migration 423 and Gnosis event-log receipt behavior in disposable PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT"] = "true"

MIGRATION = ROOT / "schemas/postgres/423_gnosis_event_log_receipts.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/gnosis-event-receipts-disposable.json"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        details = details.replace(os.environ.get("POSTGRES_PASSWORD", "\0"), "<redacted>")
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable = 0
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        stable = stable + 1 if result.returncode == 0 else 0
        if stable >= 4:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def connect(port: int, password: str):
    return psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user="postgres",
        password=password,
        connect_timeout=5,
    )


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("GNOSIS_RECEIPT_TEST_IMAGE", "postgres:16")
    container = f"kokonut-gnosis-receipt-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    connection = None
    checks: list[str] = []
    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-p",
                "127.0.0.1::5432",
                image,
            ]
        )
        created = True
        wait_ready(docker, container)
        migration = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration 423 applies and replays idempotently")

        port_lines = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_lines:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_lines[0].rsplit(":", 1)[1])
        connection = connect(port, password)

        from services.ingestion.gnosis_indexer import (
            GnosisEventReorgError,
            claim_gnosis_event_log,
        )

        first = {
            "transactionHash": bytes.fromhex("11" * 32),
            "logIndex": 7,
            "blockNumber": 100,
            "blockHash": bytes.fromhex("22" * 32),
        }
        if not claim_gnosis_event_log(connection, "gnosis", first, "VoteProposal"):
            raise AssertionError("new canonical event log was not inserted")
        connection.commit()
        checks.append("new event identity creates a durable receipt")

        if claim_gnosis_event_log(connection, "gnosis", first, "VoteProposal"):
            raise AssertionError("duplicate canonical event was claimed twice")
        connection.commit()
        checks.append("replay of an identical event identity is suppressed")

        reorg = dict(first, blockHash=bytes.fromhex("33" * 32))
        try:
            claim_gnosis_event_log(connection, "gnosis", reorg, "VoteProposal")
        except GnosisEventReorgError:
            connection.rollback()
        else:
            raise AssertionError("changed block hash did not fail closed")
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT block_hash FROM public.gnosis_event_log_receipt
                   WHERE chain='gnosis' AND transaction_hash=%s AND log_index=7""",
                ("0x" + "11" * 32,),
            )
            retained_hash = cursor.fetchone()[0]
        if retained_hash != "0x" + "22" * 32:
            raise AssertionError("reorg mismatch changed the original durable receipt")
        connection.commit()
        checks.append("same transaction/log index with a new block hash is rejected without replacing receipt")

        rolled_back = {
            "transactionHash": bytes.fromhex("44" * 32),
            "logIndex": 2,
            "blockNumber": 101,
            "blockHash": bytes.fromhex("55" * 32),
        }
        claim_gnosis_event_log(connection, "gnosis", rolled_back, "Trade")
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) FROM public.gnosis_event_log_receipt
                   WHERE chain='gnosis' AND transaction_hash=%s AND log_index=2""",
                ("0x" + "44" * 32,),
            )
            count = cursor.fetchone()[0]
        connection.commit()
        if count:
            raise AssertionError("rolled-back receipt escaped its transaction")
        checks.append("receipt creation rolls back with its caller transaction")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE table_schema='public' AND table_name='gnosis_event_log_receipt' "
                "AND constraint_type='PRIMARY KEY'"
            )
            if cursor.fetchone()[0] != 1:
                raise AssertionError("event receipt table is missing its primary key")
        connection.commit()
        checks.append("receipt identity is protected by the database primary key")

        connection.close()
        connection = None
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "migration": MIGRATION.name,
                    "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
                    "postgres_image": image,
                    "checks": checks,
                    "candidate_or_legacy_accessed": False,
                    "provider_accessed": False,
                    "schedule_activated": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"output": str(output), "checks": checks}, indent=2))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
