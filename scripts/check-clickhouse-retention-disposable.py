#!/usr/bin/env python3
"""Verify ClickHouse no-prune bootstrap and forward schema on a disposable server."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas/clickhouse"
TABLES = (
    "events_raw",
    "wallet_events",
    "sensor_readings",
    "weather_events",
    "financial_events",
    "dlego_events",
    "remote_sensing_events",
    "attestation_events",
)
IMAGE = os.environ.get(
    "CLICKHOUSE_RETENTION_TEST_IMAGE",
    "clickhouse/clickhouse-server:25.8@sha256:a9d328123ff8a61bf6b16448528b577d59deb85758172e13b09054b0727f8adf",
)


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
):
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False, env=env
    )
    if check and result.returncode:
        output = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        )
        raise RuntimeError(f"disposable ClickHouse command failed: {output[-4000:]}")
    return result


def client(container: str, user: str, password: str, sql: str, *, check: bool = True):
    return run(
        [
            "docker", "exec", "-i", container, "clickhouse-client",
            "--user", user, "--password", password,
            "--database", "kokonut_analytics", "--multiquery",
        ],
        input_text=sql,
        check=check,
    )


def last_value(output: str) -> str:
    rows = [line.strip() for line in output.splitlines() if line.strip()]
    if not rows:
        raise AssertionError("ClickHouse returned no scalar value")
    return rows[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI is unavailable")

    container = f"kokonut-clickhouse-retention-{os.getpid()}-{secrets.token_hex(3)}"
    user = "kokonut_test"
    password = secrets.token_urlsafe(24)
    checks: list[str] = []
    started = False
    stage = "create disposable container"

    try:
        run(
            [
                "docker", "run", "--detach", "--network", "none",
                "--name", container,
                "--env", "CLICKHOUSE_DB=kokonut_analytics",
                "--env", f"CLICKHOUSE_USER={user}",
                "--env", f"CLICKHOUSE_PASSWORD={password}",
                "--env", "CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=0",
                IMAGE,
            ]
        )
        started = True

        stage = "wait for ClickHouse readiness"
        deadline = time.monotonic() + 120
        consecutive_ready_checks = 0
        while time.monotonic() < deadline:
            ready = run(
                [
                    "docker", "exec", container, "clickhouse-client", "--user",
                    user, "--password", password, "--query", "SELECT 1",
                ],
                check=False,
            )
            if ready.returncode == 0 and last_value(ready.stdout) == "1":
                consecutive_ready_checks += 1
                if consecutive_ready_checks == 3:
                    break
            else:
                consecutive_ready_checks = 0
            time.sleep(1)
        else:
            raise RuntimeError("disposable ClickHouse did not become ready")

        for path in sorted(SCHEMA_DIR.glob("*.sql")):
            stage = f"apply fresh schema {path.name}"
            if path.name == "011_retention_policy_no_prune.sql":
                result = run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/apply-clickhouse-retention.py"),
                        "--docker-container", container,
                        "--user", user,
                        "--database", "kokonut_analytics",
                    ],
                    env={**os.environ, "CLICKHOUSE_PASSWORD": password},
                )
                checks.append("fresh bootstrap skips TTL removal when no fixed table TTL exists")
                continue
            client(container, user, password, path.read_text())
        checks.append("all ordered ClickHouse schema files apply on a clean database")

        stage = "verify fresh table definitions have no TTL"
        no_ttl = "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name IN (" + ",".join(
            f"'{table}'" for table in TABLES
        ) + ") AND positionCaseInsensitive(create_table_query, 'TTL') > 0 FORMAT TabSeparatedRaw"
        if last_value(client(container, user, password, no_ttl).stdout) != "0":
            raise AssertionError("fresh ClickHouse definitions retain a TTL")
        checks.append("fresh event tables have no table TTL")

        stage = "install synthetic legacy TTLs"
        old_ttls = "\n".join(
            f"ALTER TABLE {table} MODIFY TTL toDateTime(timestamp) + INTERVAL 2 YEAR;"
            for table in TABLES
        )
        client(container, user, password, old_ttls)
        stage = "apply no-prune forward schema"
        retention_runner = [
            sys.executable,
            str(ROOT / "scripts/apply-clickhouse-retention.py"),
            "--docker-container", container,
            "--user", user,
            "--database", "kokonut_analytics",
        ]
        run(retention_runner, env={**os.environ, "CLICKHOUSE_PASSWORD": password})
        stage = "verify forward schema removed legacy TTLs"
        remaining = int(last_value(client(container, user, password, no_ttl).stdout))
        if remaining != 0:
            raise AssertionError(f"forward schema left {remaining} table TTLs")
        checks.append("forward schema removes all eight existing fixed TTLs")

        # A second application verifies the script can be safely rerun by the
        # legacy seed loop without a migration ledger.
        stage = "replay no-prune forward schema"
        run(retention_runner, env={**os.environ, "CLICKHOUSE_PASSWORD": password})
        checks.append("forward schema replays successfully after all TTLs are absent")

        stage = "insert and merge historical synthetic event"
        client(
            container,
            user,
            password,
            """INSERT INTO events_raw
               (timestamp, event_type, source, location_id, entity_id,
                entity_type, action, payload)
               VALUES ('2000-01-01 00:00:00', 'retention_test', 'synthetic',
                       'a0000000-0000-4000-8000-000000000201',
                       'a0000000-0000-4000-8000-000000000301',
                       'test', 'retention_check', '{}');
               OPTIMIZE TABLE events_raw FINAL;
               SELECT count() FROM events_raw WHERE event_type = 'retention_test'
                 FORMAT TabSeparatedRaw;""",
        )
        retained = int(last_value(client(
            container,
            user,
            password,
            "SELECT count() FROM events_raw WHERE event_type = 'retention_test' FORMAT TabSeparatedRaw",
        ).stdout))
        if retained != 1:
            raise AssertionError("synthetic historical event did not survive after TTL removal")
        checks.append("old-dated synthetic event survives a merge after TTL removal")

        result = {
            "date": date.today().isoformat(),
            "migration": "011_retention_policy_no_prune.sql",
            "result": "passed",
            "database": "network-disabled disposable ClickHouse",
            "image": IMAGE,
            "assertions_passed": len(checks),
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "production_database_touched": False,
            "checks": checks,
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    except Exception as exc:
        diagnostics = [f"failed during: {stage}"]
        if started:
            logs = run(["docker", "logs", container], check=False)
            details = "\n".join(
                part for part in (logs.stdout, logs.stderr) if part
            )
            if details:
                diagnostics.append(f"ClickHouse container log tail:\n{details[-5000:]}")
            state = run(
                ["docker", "inspect", "--format", "{{json .State}}", container],
                check=False,
            )
            if state.returncode == 0 and state.stdout.strip():
                diagnostics.append(f"ClickHouse container state: {state.stdout.strip()}")
            server_logs = run(
                [
                    "docker", "exec", container, "sh", "-c",
                    "ps -ef | grep '[c]lickhouse' || true; "
                    "grep -Ei 'error|exception|fatal|signal|shutdown|terminat|listening|start' "
                    "/var/log/clickhouse-server/clickhouse-server.err.log "
                    "/var/log/clickhouse-server/clickhouse-server.log 2>/dev/null | tail -n 100",
                ],
                check=False,
            )
            server_details = "\n".join(
                part for part in (server_logs.stdout, server_logs.stderr) if part
            )
            if server_details:
                diagnostics.append(f"ClickHouse server log tail:\n{server_details[-7000:]}")
        raise RuntimeError("\n".join([str(exc), *diagnostics])) from None
    finally:
        if started:
            run(["docker", "rm", "--force", container], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
