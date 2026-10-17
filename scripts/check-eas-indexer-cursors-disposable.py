#!/usr/bin/env python3
"""Exercise EAS recipient cursor migration and transaction boundaries."""

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
# This fixture uses only its explicit disposable DSN and must never decrypt the
# repository's developer or production secret file during its imports.
os.environ["KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT"] = "true"

MIGRATION = ROOT / "schemas/postgres/421_eas_recipient_cursors.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/eas-recipient-cursor-disposable.json"
LEGACY_CURSOR = "a0000000-0000-0000-0000-000000000001"
SECOND_CURSOR = "a0000000-0000-0000-0000-000000000002"
UNSUPPORTED_CURSOR = "a0000000-0000-0000-0000-000000000003"
NEW_CURSOR = "a0000000-0000-0000-0000-000000000004"


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
            docker, "exec", "-i", container, "psql", "-X", "-q",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    successes = 0
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def connect(port: int, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user="postgres",
        password=password, connect_timeout=5,
    )


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("EAS_CURSOR_TEST_IMAGE", "postgres:16")
    container = f"kokonut-eas-cursor-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    connection = None
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={password}", "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(
            docker,
            container,
            f"""
            CREATE TABLE public.wallet_profile (
                id UUID PRIMARY KEY,
                chain TEXT NOT NULL
            );
            CREATE TABLE public.chain_indexer_status (
                chain TEXT NOT NULL,
                indexer_type TEXT NOT NULL,
                last_synced_block BIGINT,
                last_synced_at TIMESTAMPTZ,
                status TEXT,
                error_message TEXT,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (chain, indexer_type)
            );
            INSERT INTO public.wallet_profile (id, chain) VALUES
                ('{LEGACY_CURSOR}', 'celo'),
                ('{SECOND_CURSOR}', 'celo'),
                ('{UNSUPPORTED_CURSOR}', 'gnosis');
            INSERT INTO public.chain_indexer_status (
                chain, indexer_type, status, metadata
            ) VALUES ('celo', 'eas', 'legacy', '{{"last_attestation_time": 200}}');
            """,
        )
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 421 applies and replays idempotently")

        port_lines = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_lines:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_lines[0].rsplit(":", 1)[1])
        connection = connect(port, password)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT chain, wallet_id::text, last_attestation_time
                  FROM eas_indexer_cursor ORDER BY chain, wallet_id
                """
            )
            backfilled = cursor.fetchall()
        expected = [
            ("celo", LEGACY_CURSOR, 200),
            ("celo", SECOND_CURSOR, 200),
        ]
        if backfilled != expected:
            raise AssertionError(f"legacy cursor backfill was unexpected: {backfilled}")
        checks.append("legacy chain watermark backfills existing supported wallets only")

        from services.ingestion.base import update_indexer_status
        from services.ingestion.eas_indexer import (
            advance_attestation_cursor,
            get_chain_attestation_watermark,
            get_last_attestation_time,
        )

        docker_sql(
            docker,
            container,
            f"INSERT INTO public.wallet_profile (id, chain) VALUES ('{NEW_CURSOR}', 'celo')",
        )
        if get_last_attestation_time(connection, "celo", NEW_CURSOR) != 0:
            raise AssertionError("newly tracked recipient did not start at zero")
        checks.append("newly tracked wallet starts with an independent zero cursor")

        advance_attestation_cursor(connection, "celo", LEGACY_CURSOR, 250)
        advance_attestation_cursor(connection, "celo", SECOND_CURSOR, 205)
        advance_attestation_cursor(connection, "celo", SECOND_CURSOR, 190)
        if get_chain_attestation_watermark(connection, "celo") != 250:
            raise AssertionError("chain status watermark did not reflect the maximum recipient cursor")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT last_attestation_time FROM eas_indexer_cursor WHERE chain='celo' AND wallet_id=%s",
                (SECOND_CURSOR,),
            )
            if cursor.fetchone()[0] != 205:
                raise AssertionError("recipient cursor regressed or followed another wallet")
        connection.commit()
        checks.append("recipient cursors advance independently and never regress")

        advance_attestation_cursor(connection, "celo", LEGACY_CURSOR, 300)
        update_indexer_status(
            "celo", "eas", status="healthy",
            metadata={"last_attestation_time": 300}, db=connection,
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT last_attestation_time FROM eas_indexer_cursor WHERE chain='celo' AND wallet_id=%s",
                (LEGACY_CURSOR,),
            )
            cursor_value = cursor.fetchone()[0]
            cursor.execute(
                "SELECT status, metadata->>'last_attestation_time' FROM chain_indexer_status WHERE chain='celo' AND indexer_type='eas'"
            )
            status = cursor.fetchone()
        if cursor_value != 250 or status != ("legacy", "200"):
            raise AssertionError("cursor/status escaped a rolled-back data transaction")
        checks.append("cursor and indexer status roll back together with an uncommitted projection batch")
        connection.close()
        connection = None

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "database_image": image,
                    "migration": MIGRATION.name,
                    "migration_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
                    "checks": checks,
                    "status": "passed",
                    "candidate_or_legacy_database_touched": False,
                    "provider_calls": 0,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "checks": checks, "evidence": str(output)}))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True, capture_output=True, check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
