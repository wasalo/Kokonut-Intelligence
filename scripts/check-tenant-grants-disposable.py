#!/usr/bin/env python3
"""Replay migrations 387-389 and exercise tenant authorization in disposable PostgreSQL."""

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
MIGRATIONS = ROOT / "schemas" / "postgres"
DEFAULT_EVIDENCE = (
    ROOT
    / "docs"
    / "refactor"
    / "builds"
    / "2026-10-13-recovery"
    / "tenant-grants-migrations-disposable.json"
)

CHECKS = [
    "ordered 387-389 replay on a minimal compatible PostgreSQL 16 schema",
    "replay of migrations 388 and 389 is idempotent",
    "confirmed Kokonut Network ownership is recorded for both seed locations",
    "owner access succeeds and partner access needs an explicit active share",
    "expired and revoked shares deny partner access",
    "revoked membership, inactive organization, disabled identity, and revoked grant deny access",
    "unverified location and stale ownership verification deny tenant access",
    "legacy NULL-tenant grants remain compatible but still require an enabled identity",
    "Field Collector draft insert requires current create and review grants",
    "Field Collector draft edit requires all three current grants",
    "workflow events require current action grants; draft-edited events require review grants",
    "legacy NULL-tenant grants pass the Field Collector trigger boundary",
    "non-target manual records remain outside the Field Collector tenant triggers",
]


def run(command: list[str], *, input_text: str | None = None, capture: bool = True) -> str:
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if completed.returncode:
        details = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{details}")
    return completed.stdout or ""


def sql(container: str, statement: str) -> str:
    return run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_until_ready(container: str) -> None:
    deadline = time.monotonic() + 60
    last_error = ""
    while time.monotonic() < deadline:
        check = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if check.returncode == 0:
            return
        last_error = check.stdout.strip()
        time.sleep(1)
    raise RuntimeError(f"disposable PostgreSQL did not become ready: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_EVIDENCE,
        help="sanitized JSON evidence destination",
    )
    args = parser.parse_args()

    container = f"kokonut-tenant-grants-check-{uuid.uuid4().hex[:10]}"
    started = False
    try:
        run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                "none",
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "postgres:16",
            ]
        )
        started = True
        wait_until_ready(container)

        sql(container, (FIXTURES / "tenant_grants_migrations_387_389_disposable.sql").read_text())
        for migration in (
            "387_kokonut_network_tenant_ownership.sql",
            "388_tenant_aware_operator_grants.sql",
            "389_tenant_aware_field_collector_write_guards.sql",
        ):
            sql(container, (MIGRATIONS / migration).read_text())

        # Repeat the new migration pair to catch non-idempotent DDL or seed behavior.
        for migration in (
            "388_tenant_aware_operator_grants.sql",
            "389_tenant_aware_field_collector_write_guards.sql",
        ):
            sql(container, (MIGRATIONS / migration).read_text())

        sql(container, (FIXTURES / "tenant_grants_migrations_387_389_assertions.sql").read_text())

        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with Docker network disabled",
            "candidate_database_touched": False,
            "migrations": [
                "387_kokonut_network_tenant_ownership.sql",
                "388_tenant_aware_operator_grants.sql",
                "389_tenant_aware_field_collector_write_guards.sql",
            ],
            "idempotency_replay": [
                "388_tenant_aware_operator_grants.sql",
                "389_tenant_aware_field_collector_write_guards.sql",
            ],
            "checks": CHECKS,
            "scope_limit": (
                "Uses a minimal compatible schema for the touched tables. It does not replay "
                "the full repository migration chain or test migrations 384-385 trigger interaction."
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - report disposable acceptance failures plainly.
        print(f"DISPOSABLE TENANT GRANT CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
