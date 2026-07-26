#!/usr/bin/env python3
"""Discover, track, and apply PostgreSQL schema and seed migrations."""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path

from ..common.db import PG_DB, PG_USER
from ..common.logging import get_logger

logger = get_logger("migration")

PROJECT_DIR = Path(__file__).parent.parent.parent
SCHEMA_DIR = PROJECT_DIR / "schemas" / "postgres"
SEED_DIR = PROJECT_DIR / "schemas" / "seeds"

# Historical post-apply edits that were merged before checksum enforcement was
# consistently used. Repairs are only permitted for this explicit inventory;
# new drift must be fixed with a new migration.
APPROVED_CHECKSUM_REPAIRS = {
    "schema:046_ecological_modeling.sql": "01dfc20ab0b3c2ae9c74faa3763866aa5c250deccef377f13f4128cd9c16c5ab",
    "schema:051_gap_closures.sql": "dcf5faf820dd4803119d418bbdbfa65edbfc61497d8417848d7fa99bb2d7c5f4",
    "schema:057_tree_tracking.sql": "e87318464ba890f4da3ab19a8ffbfe939bf03943993817213f7bfc7f412a016b",
    "schema:058_spatial_export.sql": "2a70fefcbbcd25a28dc15fe9ed27ae863366e5a3d6ba8ad3dd72493f4bf905f4",
    "schema:070_financial_enhancements.sql": "85301081479ceda6932d1a430f2ed0ccddf1b6aa404726545094b0a0b9060f94",
    "schema:085_capacity_utilization.sql": "bddb08229767af58d6b128d5669387faa711173407e988bc2e49cd37ac45a67f",
    "schema:086_abundance_estimates.sql": "705e09e5a7683cb66c56a57173cd6b83fc59396ba4d81a4b8f84398eb6f287d0",
    "schema:100_data_stream.sql": "7fc1fb607359cf29a7d2398daadf3608e193d7b927186a76421cace6e2811b70",
    "schema:182_process_mining.sql": "32084e5b1be5168a58bf0634625a6c201b8855cf7a6d5736634e3c9406ce3cbb",
    "schema:214_stakeholder_compatibility_views.sql": "75221cfbf771cff335571377a817e9bbb5195d3db5dfb2b213dc61842972ff5c",
    "schema:298_consent_privacy_p0.sql": "d6b7aa4f5317ec65756461b08233530e243cf3531a43c3faba51d867ef05cd12",
    "seed:046_ecological_modeling.sql": "220f6fe668d63a997f7ef4dbc01f773ee8e9d3755c9ab0872d3acb1fef7a9f3d",
    "seed:029_pilot_impact_accountability.sql": "688934bec47685f3d353283e8202e8ac887d392fe46ec24fb3c694e34b5a9fe7",
}


class MigrationError(RuntimeError):
    """Raised when migration discovery or database operations are unsafe."""


def _psql(input_sql: str, variables: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Execute SQL via a temp file with shell input redirection.

    Writing SQL to a temp file and using shell input redirection
    (``docker compose exec ... psql < /tmp/file``) avoids the SIGPIPE
    (exit 141) that ``subprocess.run(input=...)`` triggers when piped
    through ``docker compose exec -T database psql`` — especially with
    large ``BEGIN``/``COMMIT``-wrapped migrations and ``ON_ERROR_STOP=1``.
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False)
    try:
        tmp.write(input_sql)
        tmp.flush()
        tmp_name = tmp.name
        tmp.close()
        psql_args = [
            "psql", "-X", "-U", PG_USER, "-d", PG_DB,
            "-v", "ON_ERROR_STOP=1", "-A", "-t",
            "-f", "-",
        ]
        for key, value in (variables or {}).items():
            psql_args.extend(["-v", f"{key}={value}"])
        # Shell input-redirected psql: the shell opens the temp file as stdin
        # for ``docker compose exec``, avoiding both the Python subprocess stdin
        # pipe (which caused SIGPIPE via ``subprocess.run(input=...)``) and the
        # ``cat file | psql`` pattern (which reintroduced SIGPIPE via cat).
        escaped_tmp = tmp_name.replace("'", "'\\''")
        quoted_args = " ".join(shlex.quote(argument) for argument in psql_args)
        shell_cmd = [
            "sh", "-c",
            f"docker compose exec -T database {quoted_args} < '{escaped_tmp}'",
        ]
        try:
            result = subprocess.run(
                shell_cmd, capture_output=True, text=True, timeout=3600
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MigrationError(f"psql execution failed: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown psql error"
            raise MigrationError(detail)
        return result
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _compute_checksum(filepath: Path) -> str:
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def _discover_files(*, include_seeds: bool = True) -> list[dict]:
    """Return deterministic schema-first migrations with immutable file IDs."""
    files = []
    seen_ids: set[str] = set()
    directories = [(SCHEMA_DIR, "schema")]
    if include_seeds:
        directories.append((SEED_DIR, "seed"))
    for directory, kind in directories:
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


def _validate_sources(files: list[dict]) -> None:
    """Reject ambiguous migration sources before any database work starts."""
    versions: set[tuple[str, str]] = set()
    for file_info in files:
        version_key = (file_info["kind"], file_info["version"])
        # Seeds historically use several independent 000 files. Schema
        # migrations, however, must have one unambiguous numeric version.
        if file_info["kind"] == "schema" and version_key in versions:
            raise MigrationError(
                "duplicate migration version discovered: "
                f"{file_info['kind']}:{file_info['version']}"
            )
        versions.add(version_key)

        sql = file_info["path"].read_text()
        if "\x00" in sql:
            raise MigrationError(f"migration contains a NUL byte: {file_info['id']}")
        if re.search(r"(?im)^\s*\\connect\b", sql):
            raise MigrationError(
                f"migration cannot change databases with \\connect: {file_info['id']}"
            )


def _ensure_tracking_table() -> None:
    """Create or upgrade tracking without treating legacy numeric IDs as new IDs."""
    _psql("""
SELECT pg_advisory_lock(777204681);
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
CREATE TABLE IF NOT EXISTS schema_migration_repair (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_id VARCHAR(512) NOT NULL,
    old_checksum VARCHAR(64) NOT NULL,
    new_checksum VARCHAR(64) NOT NULL,
    reason TEXT NOT NULL,
    repaired_by VARCHAR(100) NOT NULL,
    repaired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (migration_id, old_checksum, new_checksum)
);
SELECT pg_advisory_unlock(777204681);
""")


def _reconcile_legacy(files: list[dict]) -> None:
    """Assign new IDs only where an old numeric row has the exact filename stem."""
    if not files:
        return
    values = []
    variables = {}
    for index, file_info in enumerate(files):
        values.append(
            f"(:'migration_id_{index}', :'legacy_version_{index}', :'name_{index}')"
        )
        variables.update({
            f"migration_id_{index}": file_info["id"],
            f"legacy_version_{index}": file_info["version"],
            f"name_{index}": file_info["name"],
        })
    _psql(
        f"""
SELECT pg_advisory_lock(777204681);
UPDATE schema_migration tracked
SET migration_id = candidates.migration_id
FROM (VALUES {', '.join(values)}) AS candidates(migration_id, legacy_version, name)
WHERE tracked.migration_id IS NULL
  AND tracked.version = candidates.legacy_version
  AND tracked.name = candidates.name;
SELECT pg_advisory_unlock(777204681);
""",
        variables,
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
        parts = line.split("|")
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


def _validate_repair_schema(migration_id: str) -> None:
    """Validate the live schema before repairing the known historical drift."""
    if migration_id not in APPROVED_CHECKSUM_REPAIRS:
        raise MigrationError(f"no approved checksum repair exists for {migration_id}")
    if migration_id == "seed:046_ecological_modeling.sql":
        result = _psql("""
SELECT EXISTS (
    SELECT 1 FROM farm_zone
    WHERE id = 'a0000000-0000-0000-0000-000000000700'
);
""")
        if result.stdout.strip().lower() != "t":
            raise MigrationError("schema validation failed: Adelphi syntropic zone is required")
        return
    if migration_id != "schema:046_ecological_modeling.sql":
        return
    result = _psql("""
SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'ecological_interaction'
      AND column_name = 'evidence_maturity'
) AND EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'ecological_interaction'
      AND indexname = 'idx_eco_interaction_maturity'
);
""")
    if result.stdout.strip().lower() != "t":
        raise MigrationError(
            "schema validation failed: ecological_interaction evidence_maturity column and index are required"
        )


def repair_checksum(
    migration_id: str,
    expected_old_checksum: str,
    reason: str,
    repaired_by: str,
) -> str:
    """Repair one explicitly approved historical checksum after live validation."""
    files = _discover_files()
    file_info = next((item for item in files if item["id"] == migration_id), None)
    if not file_info:
        raise MigrationError(f"migration not found: {migration_id}")
    if expected_old_checksum == file_info["checksum"]:
        raise MigrationError("old and current checksums are identical; no repair is needed")
    if APPROVED_CHECKSUM_REPAIRS.get(migration_id) != expected_old_checksum:
        raise MigrationError(f"checksum repair is not approved for {migration_id}")
    if not reason.strip() or not repaired_by.strip():
        raise MigrationError("repair reason and operator are required")

    _ensure_tracking_table()
    _validate_repair_schema(migration_id)
    current = _psql(
        """
SELECT checksum || E'\t' || status
FROM schema_migration
WHERE migration_id = :'migration_id';
""",
        {"migration_id": migration_id},
    ).stdout.strip()
    if current != f"{expected_old_checksum}\tapplied":
        raise MigrationError(
            f"tracking row does not match expected applied checksum for {migration_id}"
        )

    repair_id = str(uuid.uuid4())
    _psql(
        """
BEGIN;
SELECT pg_advisory_lock(777204681);
INSERT INTO schema_migration_repair
    (id, migration_id, old_checksum, new_checksum, reason, repaired_by)
VALUES
    (:'repair_id'::uuid, :'migration_id', :'old_checksum', :'new_checksum', :'reason', :'repaired_by');
UPDATE schema_migration
SET checksum = :'new_checksum'
WHERE migration_id = :'migration_id'
  AND checksum = :'old_checksum'
  AND status = 'applied';
SELECT pg_advisory_unlock(777204681);
COMMIT;
""",
        {
            "repair_id": repair_id,
            "migration_id": migration_id,
            "old_checksum": expected_old_checksum,
            "new_checksum": file_info["checksum"],
            "reason": reason,
            "repaired_by": repaired_by,
        },
    )
    return repair_id


def _apply_files(files: list[dict]) -> None:
    """Apply migrations one at a time, each in its own psql session.

    This avoids SIGPIPE (exit 141) when the monolithic batch grows to 300+
    migrations: a single ``subprocess.run(input=<2 MB>)`` piped through
    ``docker compose exec -T`` breaks if psql exits early (e.g. a statement
    failure inside a ``BEGIN``/``COMMIT`` block with ``ON_ERROR_STOP=1``).

    Each migration is its own ``_psql()`` call, so:
    - Successfully applied migrations are committed before the next starts.
    - A failure in one migration does not kill the pipe for subsequent ones.
    - On re-run, already-applied migrations are skipped via ``ON CONFLICT``.
    """
    for file_info in files:
        migration_id = file_info["id"]
        logger.info("Applying migration %s...", migration_id)
        sql_content = file_info["path"].read_text()
        sql_track = """
INSERT INTO schema_migration
    (migration_id, version, name, sql_up, checksum, status, execution_time_ms, applied_by)
VALUES
    (:'migration_id', :'migration_id', :'name', :'source',
     :'checksum', 'applied', 0, 'migration-cli')
ON CONFLICT (migration_id) WHERE migration_id IS NOT NULL DO UPDATE SET
    checksum = EXCLUDED.checksum,
    status = EXCLUDED.status,
    execution_time_ms = EXCLUDED.execution_time_ms,
    applied_at = NOW();
"""
        # The lock and applied-state recheck must be in the same psql session
        # as the migration. Otherwise two runners can pass a check between
        # separate subprocess sessions and both execute the same file.
        guarded_sql = f"""
SELECT pg_advisory_lock(777204681);
SELECT EXISTS (
    SELECT 1 FROM schema_migration
    WHERE migration_id = :'migration_id' AND status = 'applied'
) AS migration_applied \\gset check_
\\if :check_migration_applied
    SELECT pg_advisory_unlock(777204681);
\\else
{sql_content}
{sql_track}
    SELECT pg_advisory_unlock(777204681);
\\endif
"""
        _psql(
            guarded_sql,
            {
                "migration_id": migration_id,
                "name": file_info["name"],
                "source": f"(see {file_info['path'].name})",
                "checksum": file_info["checksum"],
            },
        )


def _load_state(*, include_seeds: bool = True) -> tuple[list[dict], dict[str, dict]]:
    files = _discover_files(include_seeds=include_seeds)
    _validate_sources(files)
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


def cmd_migrate(dry_run: bool = False, schemas_only: bool = False) -> None:
    files, applied = _load_state(include_seeds=not schemas_only)
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


def cmd_plan(schemas_only: bool = False) -> None:
    """Show pending migrations without changing database state."""
    files = _discover_files(include_seeds=not schemas_only)
    _validate_sources(files)
    try:
        applied = _get_applied()
    except MigrationError as exc:
        raise MigrationError(
            "migration tracking tables are unavailable; run bootstrap before planning"
        ) from exc
    _validate_applied(files, applied)
    pending = [
        item for item in files
        if applied.get(item["id"], {}).get("status") != "applied"
    ]
    print(f"{len(pending)} pending migration(s):")
    for item in pending:
        print(f"  {item['id']}")


def cmd_validate(schemas_only: bool = False) -> None:
    """Validate migration source ordering and syntax boundaries without applying SQL."""
    files = _discover_files(include_seeds=not schemas_only)
    _validate_sources(files)
    print(f"Validated {len(files)} migration source files.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kokonut migration runner")
    parser.add_argument(
        "command", choices=("status", "migrate", "plan", "dry-run", "validate", "repair")
    )
    parser.add_argument("--migration-id", help="Migration ID for an audited checksum repair")
    parser.add_argument("--expected-old-checksum", help="Checksum currently recorded in the database")
    parser.add_argument("--reason", help="Reason for the exceptional repair")
    parser.add_argument("--repaired-by", help="Operator performing the repair")
    parser.add_argument("--confirm", action="store_true", help="Confirm the audited checksum repair")
    parser.add_argument(
        "--schemas-only",
        action="store_true",
        help="Apply only PostgreSQL schema migrations, excluding seed data",
    )
    args = parser.parse_args()
    try:
        if args.command == "status":
            cmd_status()
        elif args.command == "validate":
            cmd_validate(schemas_only=args.schemas_only)
        elif args.command == "repair":
            if not args.confirm:
                raise MigrationError("checksum repair requires --confirm")
            missing = [
                name for name, value in (
                    ("--migration-id", args.migration_id),
                    ("--expected-old-checksum", args.expected_old_checksum),
                    ("--reason", args.reason),
                    ("--repaired-by", args.repaired_by),
                ) if not value
            ]
            if missing:
                raise MigrationError(f"repair requires: {', '.join(missing)}")
            repair_id = repair_checksum(
                args.migration_id, args.expected_old_checksum, args.reason, args.repaired_by
            )
            print(f"Checksum repair recorded: {repair_id}")
        elif args.command in {"plan", "dry-run"}:
            cmd_plan(schemas_only=args.schemas_only)
        else:
            cmd_migrate(schemas_only=args.schemas_only)
    except MigrationError as exc:
        logger.error("Migration failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
