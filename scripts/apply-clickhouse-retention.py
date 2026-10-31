#!/usr/bin/env python3
"""Apply ClickHouse schema 011 only to tables that still declare a table TTL."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/clickhouse/011_retention_policy_no_prune.sql"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALTER_TTL = re.compile(
    r"^\s*ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+REMOVE\s+TTL\s*;\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def run_sql(args: argparse.Namespace, sql: str) -> str:
    client = ["clickhouse-client"]
    if args.compose_file:
        command = ["docker", "compose"]
        if args.project_name:
            command.extend(["--project-name", args.project_name])
        for compose_file in args.compose_file:
            command.extend(["-f", str(compose_file)])
        command.extend(["exec", "-T", args.service, *client])
    elif args.docker_container:
        command = ["docker", "exec", "-i", args.docker_container, *client]
    else:
        command = client

    command.extend(["--user", args.user, "--database", args.database, "--query", sql])
    password = os.environ.get("CLICKHOUSE_PASSWORD")
    if password:
        command[command.index("--database"):command.index("--database")] = ["--password", password]

    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"ClickHouse query failed: {detail[-3000:]}")
    return result.stdout.strip()


def apply_migration(args: argparse.Namespace) -> list[str]:
    sql = MIGRATION.read_text()
    tables = ALTER_TTL.findall(sql)
    if len(tables) != 8 or len(set(tables)) != len(tables):
        raise RuntimeError("retention migration must list each of the eight expected tables once")

    changes: list[str] = []
    for table in tables:
        exists = run_sql(
            args,
            "SELECT count() FROM system.tables "
            f"WHERE database = currentDatabase() AND name = '{table}' FORMAT TabSeparatedRaw",
        )
        if exists != "1":
            raise RuntimeError(f"expected ClickHouse table is missing from the selected database: {table}")

        has_ttl = run_sql(
            args,
            "SELECT toUInt8(positionCaseInsensitive(create_table_query, ' TTL ') > 0) "
            "FROM system.tables "
            f"WHERE database = currentDatabase() AND name = '{table}' FORMAT TabSeparatedRaw",
        )
        if has_ttl == "1":
            run_sql(args, f"ALTER TABLE `{table}` REMOVE TTL")
            changes.append(table)
        elif has_ttl == "0":
            changes.append(f"{table}: already has no table TTL")
        else:
            raise RuntimeError(f"could not determine table TTL state for {table}")

    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("CH_DB", "kokonut_analytics"))
    parser.add_argument("--user", default=os.environ.get("CLICKHOUSE_USER", "kokonut"))
    parser.add_argument("--compose-file", type=Path, action="append")
    parser.add_argument("--project-name")
    parser.add_argument("--service", default=os.environ.get("CH_SERVICE", "clickhouse"))
    parser.add_argument("--docker-container")
    args = parser.parse_args()

    if not IDENTIFIER.fullmatch(args.database):
        parser.error("database must be a simple SQL identifier")
    if bool(args.compose_file) == bool(args.docker_container):
        parser.error("select exactly one of --compose-file or --docker-container")
    if args.compose_file and any(not path.is_file() for path in args.compose_file):
        parser.error("a Compose file does not exist")

    try:
        changes = apply_migration(args)
    except (OSError, RuntimeError) as exc:
        print(f"ClickHouse retention update failed: {exc}", file=sys.stderr)
        return 1

    changed = [item for item in changes if ": already has no table TTL" not in item]
    print(f"ClickHouse no-prune migration checked {len(changes)} tables; removed TTL from {len(changed)}.")
    for item in changes:
        print(f"  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
