#!/usr/bin/env python3
"""
Migration Runner

Tracks and applies PostgreSQL schema and seed migrations.
Uses the existing schema_migration table for tracking.

Usage:
    python3 -m services.migration status
    python3 -m services.migration migrate
    python3 -m services.migration dry-run
"""

import hashlib
import os
import subprocess
import sys
import time
from glob import glob
from pathlib import Path

from ..common.logging import get_logger
from ..common.db import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD

logger = get_logger("migration")

PROJECT_DIR = Path(__file__).parent.parent.parent
SCHEMA_DIR = PROJECT_DIR / "schemas" / "postgres"
SEED_DIR = PROJECT_DIR / "schemas" / "seeds"


def _psql(sql: str) -> subprocess.CompletedProcess:
    """Execute SQL via psql."""
    return subprocess.run(
        [
            "docker", "compose", "exec", "-T", "database",
            "psql", "-U", PG_USER, "-d", PG_DB, "-c", sql,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


def _compute_checksum(filepath: Path) -> str:
    """SHA-256 checksum of file contents."""
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def _discover_files() -> list[dict]:
    """Discover numbered SQL files from schema and seed directories.

    Schemas are sorted before seeds to ensure tables exist before seed data
    is applied on fresh installs.
    """
    files = []

    for pattern, kind in [
        (str(SCHEMA_DIR / "*.sql"), "schema"),
        (str(SEED_DIR / "*.sql"), "seed"),
    ]:
        for path_str in sorted(glob(pattern)):
            p = Path(path_str)
            prefix = p.stem.split("_")[0]
            if prefix.isdigit():
                files.append({
                    "version": prefix,
                    "name": p.stem,
                    "kind": kind,
                    "path": p,
                    "checksum": _compute_checksum(p),
                })

    files.sort(key=lambda f: (f["version"], 0 if f["kind"] == "schema" else 1))
    return files


def _ensure_tracking_table() -> None:
    """Create schema_migration table if it doesn't exist yet."""
    _psql("""
        CREATE TABLE IF NOT EXISTS schema_migration (
            version VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255),
            sql_up TEXT,
            checksum VARCHAR(64),
            status VARCHAR(50) DEFAULT 'pending',
            execution_time_ms INTEGER,
            applied_at TIMESTAMPTZ DEFAULT NOW(),
            applied_by VARCHAR(100)
        )
    """)


def _get_applied() -> dict[str, dict]:
    """Query schema_migration for applied versions."""
    result = _psql(
        "SELECT version, name, checksum, status, applied_at "
        "FROM schema_migration ORDER BY version"
    )
    if result.returncode != 0:
        logger.warning("Could not query schema_migration: %s", result.stderr.strip())
        return {}

    applied = {}
    for line in result.stdout.strip().split("\n"):
        if not line.strip() or line.startswith("-") or line.startswith("version"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            applied[parts[0]] = {
                "name": parts[1],
                "checksum": parts[2],
                "status": parts[3],
            }
    return applied


def _apply_file(file_info: dict) -> bool:
    """Apply a single SQL file via psql and record in schema_migration."""
    filepath = file_info["path"]
    sql = filepath.read_text()

    logger.info("  Applying %s (%s)...", file_info["name"], file_info["kind"])
    start = time.time()

    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "database",
            "psql", "-U", PG_USER, "-d", PG_DB,
            "-v", "ON_ERROR_STOP=1",
            "-f", f"/dev/stdin",
        ],
        input=sql,
        capture_output=True,
        text=True,
        timeout=120,
    )

    elapsed_ms = int((time.time() - start) * 1000)

    if result.returncode != 0:
        logger.error("  ✗ %s failed (%dms): %s", file_info["name"], elapsed_ms, result.stderr.strip()[:200])
        _record_migration(file_info, "failed", elapsed_ms)
        return False

    _record_migration(file_info, "applied", elapsed_ms)
    logger.info("  ✓ %s applied (%dms)", file_info["name"], elapsed_ms)
    return True


def _record_migration(file_info: dict, status: str, elapsed_ms: int) -> None:
    """Insert migration record into schema_migration."""
    insert_sql = f"""
    INSERT INTO schema_migration (version, name, sql_up, checksum, status, execution_time_ms, applied_by)
    VALUES (
        '{file_info['version']}',
        '{file_info['name']}',
        '(see {file_info['path'].name})',
        '{file_info['checksum']}',
        '{status}',
        {elapsed_ms},
        'migration-cli'
    )
    ON CONFLICT (version) DO UPDATE SET
        checksum = EXCLUDED.checksum,
        status = EXCLUDED.status,
        execution_time_ms = EXCLUDED.execution_time_ms,
        applied_at = NOW()
    """
    _psql(insert_sql)


def cmd_status():
    """Show migration status."""
    files = _discover_files()
    applied = _get_applied()

    print(f"{'Version':<10} {'Name':<40} {'Kind':<8} {'Status':<12} {'Checksum'}")
    print(f"{'─' * 10} {'─' * 40} {'─' * 8} {'─' * 12} {'─' * 16}")

    for f in files:
        info = applied.get(f["version"])
        if info:
            status = info["status"]
            checksum_short = info["checksum"][:12]
        else:
            status = "pending"
            checksum_short = f["checksum"][:12]

        print(f"{f['version']:<10} {f['name']:<40} {f['kind']:<8} {status:<12} {checksum_short}")

    total = len(files)
    done = len([f for f in files if f["version"] in applied and applied[f["version"]]["status"] == "applied"])
    pending = total - done
    print(f"\n{total} total, {done} applied, {pending} pending")


def cmd_migrate(dry_run: bool = False):
    """Apply pending migrations."""
    _ensure_tracking_table()
    files = _discover_files()
    applied = _get_applied()

    pending = [
        f for f in files
        if f["version"] not in applied or applied[f["version"]]["status"] != "applied"
    ]

    if not pending:
        print("All migrations already applied.")
        return

    action = "Would apply" if dry_run else "Applying"
    print(f"{action} {len(pending)} migration(s)...\n")

    success = 0
    failed = 0

    for f in pending:
        if dry_run:
            print(f"  {f['version']} {f['name']} ({f['kind']})")
            success += 1
        else:
            if _apply_file(f):
                success += 1
            else:
                failed += 1
                break  # Stop on first failure

    print(f"\n{'Would apply' if dry_run else 'Applied'}: {success}, Failed: {failed}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kokonut migration runner")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show migration status")
    sub.add_parser("migrate", help="Apply pending migrations")

    dry_run_parser = sub.add_parser("dry-run", help="Show what would be applied")
    dry_run_parser.add_argument("--dry-run", action="store_true", default=True)

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command in ("migrate", "dry-run"):
        cmd_migrate(dry_run=(args.command == "dry-run"))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
