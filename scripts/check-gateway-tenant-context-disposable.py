#!/usr/bin/env python3
"""Replay migration 396 and verify signed Gateway tenant context in disposable PostgreSQL."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MIGRATION = ROOT / "schemas/postgres/396_signed_gateway_credential_tenant_context.sql"
DEFAULT_EVIDENCE = (
    ROOT
    / "docs/refactor/builds/2026-10-14-recovery/gateway-tenant-context-disposable.json"
)


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def sql(container: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X",
            "-v", "ON_ERROR_STOP=1", "-t", "-A", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(container: str) -> None:
    deadline = time.monotonic() + 60
    last_output = ""
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        last_output = result.stdout + result.stderr
        time.sleep(0.5)
    raise RuntimeError(f"disposable PostgreSQL did not become ready: {last_output.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()

    container = f"kokonut-gateway-tenant-context-{uuid.uuid4().hex[:10]}"
    started = False
    checks = [
        "migration 396 applies and replays idempotently",
        "runtime API-key table writes are denied while reviewed gRPC read columns remain available",
        "exact active owner-scoped API key establishes signed context and forced RLS returns only its tenant row",
        "location-free, wildcard, wrong-location, expired, and inactive API keys are denied and clear prior context",
        "duplicate API-key hashes are rejected by the migration's unique index",
        "exact active location-scoped capability establishes signed context under forced RLS",
        "wrong-location, expired, and revoked capabilities are denied and clear prior context",
        "the final allowed capability use passes after usage increment; over-limit is denied",
        "zero max-usage retains the existing unlimited capability semantics",
        "caller-forged GUC values fail signed context validation and forced RLS",
        "transaction end clears the Gateway tenant context",
    ]
    try:
        run([
            "docker", "run", "--detach", "--rm", "--network", "none",
            "--name", container, "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16",
        ])
        started = True
        wait_ready(container)
        sql(container, (FIXTURES / "gateway_tenant_context_disposable.sql").read_text())
        migration_sql = MIGRATION.read_text()
        sql(container, migration_sql)
        sql(container, migration_sql)
        sql(container, (FIXTURES / "gateway_tenant_context_assertions.sql").read_text())

        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with Docker network disabled",
            "migration": MIGRATION.name,
            "idempotency_replay": True,
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "rls_enabled_outside_disposable_database": False,
            "scope_limit": (
                "Uses a minimal compatible schema for Gateway tenant context. It does not replay the full migration chain, "
                "exercise every Gateway handler, or enable RLS on candidate/deployed data."
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - acceptance should show infrastructure and SQL failures plainly.
        print(f"DISPOSABLE GATEWAY TENANT CONTEXT CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if started:
            subprocess.run(["docker", "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
