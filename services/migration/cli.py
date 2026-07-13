#!/usr/bin/env python3
"""Discover, track, and apply PostgreSQL schema and seed migrations."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from ..common.db import PG_DB, PG_USER
from ..common.logging import get_logger

logger = get_logger("migration")

PROJECT_DIR = Path(__file__).parent.parent.parent
SCHEMA_DIR = PROJECT_DIR / "schemas" / "postgres"
SEED_DIR = PROJECT_DIR / "schemas" / "seeds"
ADVISORY_LOCK_KEY = 777_204_681


class MigrationError(RuntimeError):
    """Raised when migration discovery or database operations are unsafe."""


def _psql(input_sql: str, variables: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Execute SQL through stdin, with values passed as psql variables."""
    command = [
        "docker", "compose", "exec", "-T", "database",
        "psql", "-X", "-U", PG_USER, "-d", PG_DB,
        "-v", "ON_ERROR_STOP=1", "-A", "-t", "-F", "\t",
    ]
    for key, value in (variables or {}).items():
        command.extend(["-v", f"{key}={value}"])
    try:
        result = subprocess.run(
            command, input=input_sql, capture_output=True, text=True, timeout=3600
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MigrationError(f"psql execution failed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown psql error"
        raise MigrationError(detail)
    return result


def _compute_checksum(filepath: Path) -> str:
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def _discover_files() -> list[dict]:
    """Return deterministic schema-first migrations with immutable file IDs."""
    files = []
    seen_ids: set[str] = set()
    for directory, kind in ((SCHEMA_DIR, "schema"), (SEED_DIR, "seed")):
        for path in sorted(directory.glob("*.sql"), key=lambda item: item.name):
            if not path.stem.split("_", 1)[0].isdigit():
                continue
            migration_id = f"{kind}:{path.name}"
            if migration_id in seen_ids:
                raise MigrationError(f"duplicate migration ID discovered: {migration_id}")
            seen_ids.add(migration_id)
            files.append({
                "id": migration_id,
                "version": path.stem.split("_", 1)[0],
                "name": path.stem,
                "kind": kind,
                "path": path,
                "checksum": _compute_checksum(path),
            })
    return files


def _ensure_tracking_table() -> None:
    """Create or upgrade tracking without treating legacy numeric IDs as new IDs."""
    _psql("""
CREATE TABLE IF NOT EXISTS schema_migration (
    version VARCHAR(512) NOT NULL,
    name VARCHAR(255) NOT NULL,
    sql_up TEXT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    execution_time_ms INTEGER,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by VARCHAR(100)
);
ALTER TABLE schema_migration ALTER COLUMN version TYPE VARCHAR(512);
ALTER TABLE schema_migration ADD COLUMN IF NOT EXISTS migration_id VARCHAR(512);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schema_migration_id
    ON schema_migration (migration_id) WHERE migration_id IS NOT NULL;
""")


def _reconcile_legacy(files: list[dict]) -> None:
    """Assign new IDs only where an old numeric row has the exact filename stem."""
    for file_info in files:
        _psql(
            """
UPDATE schema_migration
SET migration_id = :'migration_id'
WHERE migration_id IS NULL
  AND version = :'legacy_version'
  AND name = :'name';
""",
            {
                "migration_id": file_info["id"],
                "legacy_version": file_info["version"],
                "name": file_info["name"],
            },
        )


def _get_applied() -> dict[str, dict]:
    result = _psql("""
SELECT migration_id, name, checksum, status
FROM schema_migration
WHERE migration_id IS NOT NULL
ORDER BY migration_id;
""")
    applied = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 4 or not parts[0]:
            raise MigrationError(f"invalid schema_migration query output: {line!r}")
        migration_id, name, checksum, status = parts
        if migration_id in applied:
            raise MigrationError(f"duplicate tracked migration ID: {migration_id}")
        applied[migration_id] = {"name": name, "checksum": checksum, "status": status}
    return applied


def _validate_applied(files: list[dict], applied: dict[str, dict]) -> None:
    for file_info in files:
        record = applied.get(file_info["id"])
        if record and record["status"] == "applied" and record["checksum"] != file_info["checksum"]:
            raise MigrationError(f"applied migration was modified: {file_info['id']}")


def _apply_files(files: list[dict]) -> None:
    """Apply and track a batch while one PostgreSQL session holds the advisory lock.

    Repository migrations may contain transaction control, so migration SQL and its
    tracking insert cannot universally share a transaction. ON_ERROR_STOP makes any
    boundary failure loud; operators may need to inspect a partially committed file.
    """
    script = [f"SELECT pg_advisory_lock({ADVISORY_LOCK_KEY});"]
    for index, file_info in enumerate(files):
        script.extend([
            file_info["path"].read_text(),
            """
INSERT INTO schema_migration
    (migration_id, version, name, sql_up, checksum, status, execution_time_ms, applied_by)
VALUES
    (:'migration_id_%d', :'migration_id_%d', :'name_%d', :'source_%d',
     :'checksum_%d', 'applied', 0, 'migration-cli')
ON CONFLICT (migration_id) WHERE migration_id IS NOT NULL DO UPDATE SET
    checksum = EXCLUDED.checksum,
    status = EXCLUDED.status,
    execution_time_ms = EXCLUDED.execution_time_ms,
    applied_at = NOW();
""" % (index, index, index, index, index),
        ])
    script.append(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_KEY});")
    variables = {}
    for index, file_info in enumerate(files):
        variables.update({
            f"migration_id_{index}": file_info["id"],
            f"name_{index}": file_info["name"],
            f"source_{index}": f"(see {file_info['path'].name})",
            f"checksum_{index}": file_info["checksum"],
        })
    _psql("\n".join(script), variables)


def _load_state() -> tuple[list[dict], dict[str, dict]]:
    files = _discover_files()
    _ensure_tracking_table()
    _reconcile_legacy(files)
    applied = _get_applied()
    _validate_applied(files, applied)
    return files, applied


def cmd_status() -> None:
    files, applied = _load_state()
    print(f"{'Migration ID':<55} {'Status':<12} {'Checksum'}")
    for file_info in files:
        record = applied.get(file_info["id"])
        status = record["status"] if record else "pending"
        checksum = record["checksum"] if record else file_info["checksum"]
        print(f"{file_info['id']:<55} {status:<12} {checksum[:12]}")
    done = sum(
        applied.get(item["id"], {}).get("status") == "applied" for item in files
    )
    print(f"\n{len(files)} total, {done} applied, {len(files) - done} pending")


def cmd_migrate(dry_run: bool = False) -> None:
    files, applied = _load_state()
    pending = [
        item for item in files
        if applied.get(item["id"], {}).get("status") != "applied"
    ]
    if not pending:
        print("All migrations already applied.")
        return
    action = "Would apply" if dry_run else "Applying"
    print(f"{action} {len(pending)} migration(s)...")
    for item in pending:
        print(f"  {item['id']}")
    if not dry_run:
        _apply_files(pending)
    print(f"\n{'Would apply' if dry_run else 'Applied'}: {len(pending)}, Failed: 0")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kokonut migration runner")
    parser.add_argument("command", choices=("status", "migrate", "dry-run"))
    args = parser.parse_args()
    try:
        if args.command == "status":
            cmd_status()
        else:
            cmd_migrate(dry_run=args.command == "dry-run")
    except MigrationError as exc:
        logger.error("Migration failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
