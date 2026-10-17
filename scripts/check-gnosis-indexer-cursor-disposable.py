#!/usr/bin/env python3
"""Verify migration 424 isolates the Gnosis Moloch cursor in disposable PostgreSQL."""

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

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/424_gnosis_indexer_cursor_namespace.sql"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/gnosis-indexer-cursor-disposable.json"
)


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
    ready_count = 0
    while time.monotonic() < deadline:
        probe = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        ready_count = ready_count + 1 if probe.returncode == 0 else 0
        if ready_count >= 4:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    image = os.getenv("GNOSIS_CURSOR_TEST_IMAGE", "postgres:16")
    container = f"kokonut-gnosis-cursor-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    migration_sql = MIGRATION.read_text(encoding="utf-8")

    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--network",
                "none",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                image,
            ]
        )
        created = True
        wait_ready(docker, container)

        docker_sql(
            docker,
            container,
            """
            CREATE TABLE public.chain_indexer_status (
                chain VARCHAR(50) NOT NULL,
                indexer_type VARCHAR(50) NOT NULL,
                last_synced_block BIGINT,
                last_synced_at TIMESTAMPTZ,
                status VARCHAR(50),
                error_message TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (chain, indexer_type)
            );
            INSERT INTO public.chain_indexer_status (
                chain, indexer_type, last_synced_block, last_synced_at,
                status, error_message, metadata
            ) VALUES (
                'gnosis', 'rpc', 41000000, NOW(), 'healthy', NULL,
                '{"wallet_rpc_fixture": true}'::jsonb
            );
            """,
        )
        docker_sql(docker, container, migration_sql)
        checks.append("migration 424 copies the existing shared cursor on an isolated database")

        docker_sql(
            docker,
            container,
            """
            DO $$
            DECLARE copied public.chain_indexer_status%ROWTYPE;
                   legacy public.chain_indexer_status%ROWTYPE;
            BEGIN
                SELECT * INTO copied FROM public.chain_indexer_status
                 WHERE chain = 'gnosis' AND indexer_type = 'gnosis_moloch';
                SELECT * INTO legacy FROM public.chain_indexer_status
                 WHERE chain = 'gnosis' AND indexer_type = 'rpc';
                IF copied.last_synced_block <> 41000000
                   OR copied.status <> 'paused'
                   OR copied.metadata->>'cursor_origin' <> 'legacy_shared_rpc'
                   OR copied.metadata->>'wallet_rpc_fixture' <> 'true'
                   OR copied.metadata ? 'cursor_reviewed' THEN
                    RAISE EXCEPTION 'dedicated cursor did not preserve the boundary and mark its origin';
                END IF;
                IF legacy.last_synced_block <> 41000000
                   OR legacy.status <> 'healthy'
                   OR legacy.metadata->>'wallet_rpc_fixture' <> 'true' THEN
                    RAISE EXCEPTION 'legacy wallet RPC cursor was changed';
                END IF;
            END
            $$;
            """,
        )
        checks.append("copied cursor is paused with provenance; the wallet RPC row remains intact")

        docker_sql(
            docker,
            container,
            "UPDATE public.chain_indexer_status SET last_synced_block = 41001000 "
            "WHERE chain = 'gnosis' AND indexer_type = 'rpc';",
        )
        docker_sql(docker, container, migration_sql)
        docker_sql(
            docker,
            container,
            """
            DO $$
            BEGIN
                IF (SELECT COUNT(*) FROM public.chain_indexer_status
                    WHERE chain = 'gnosis' AND indexer_type = 'gnosis_moloch') <> 1 THEN
                    RAISE EXCEPTION 'migration replay created a duplicate dedicated cursor';
                END IF;
                IF (SELECT last_synced_block FROM public.chain_indexer_status
                    WHERE chain = 'gnosis' AND indexer_type = 'gnosis_moloch') <> 41000000 THEN
                    RAISE EXCEPTION 'migration replay overwrote the dedicated cursor';
                END IF;
                IF (SELECT last_synced_block FROM public.chain_indexer_status
                    WHERE chain = 'gnosis' AND indexer_type = 'rpc') <> 41001000 THEN
                    RAISE EXCEPTION 'migration replay changed the wallet RPC cursor';
                END IF;
            END
            $$;
            """,
        )
        checks.append("migration replay is idempotent and never overwrites either cursor")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "migration": MIGRATION.name,
                    "migration_sha256": hashlib.sha256(migration_sql.encode()).hexdigest(),
                    "postgres_image": image,
                    "checks": checks,
                    "network_enabled": False,
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
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
