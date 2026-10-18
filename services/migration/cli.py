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

from ..common.errors import safe_exception_class
from ..common.logging import get_logger
from ..common.worker_environment import worker_subprocess_environment

logger = get_logger("migration")

PROJECT_DIR = Path(__file__).parent.parent.parent
SCHEMA_DIR = PROJECT_DIR / "schemas" / "postgres"
SEED_DIR = PROJECT_DIR / "schemas" / "seeds"
SEED_VERSION_PREFIX = re.compile(r"^\d+(?:-\d+)?$")
MOBILE_FORM_SEED_ID = "seed:140_mobile_forms.sql"
MOBILE_FORM_SEED_COLUMNS = (
    "form_id",
    "name",
    "description",
    "form_schema",
    "ui_schema",
    "version",
    "collection_type",
    "status",
    "consent_policy_status",
    "consent_data_category",
    "consent_purpose",
    "consent_scope_type",
    "consent_scope_id",
    "consent_recipient_type",
    "consent_recipient_party_id",
    "consent_recipient_name",
    "consent_version",
    "consent_policy_reviewed_by",
    "consent_policy_reviewed_at",
    "consent_policy_evidence",
)
# Canonical KI tables and migration tracking live in public; exclude "$user" so
# a role-named schema cannot shadow public objects during migrations.
MIGRATION_SEARCH_PATH = "public, topology, tiger"
COMPOSE_COMMAND = ("docker", "compose")


def configure_compose(project: str | None, files: list[str] | None) -> None:
    """Select an explicit deployment, or preserve the legacy ambient default."""
    global COMPOSE_COMMAND
    if project is None and not files:
        COMPOSE_COMMAND = ("docker", "compose")
        return
    if not project or not files:
        raise MigrationError("explicit Compose selection requires both --compose-project and --compose-file")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise MigrationError("Compose project must start with a lowercase letter/digit and use lowercase letters, digits, _ or -")
    command = ["docker", "compose", "--project-directory", str(PROJECT_DIR.resolve()),
               "--env-file", "/dev/null", "-p", project]
    for filename in files:
        path = Path(filename).expanduser().resolve()
        if not path.is_file():
            raise MigrationError(f"Compose manifest is unavailable: {path}")
        command.extend(["-f", str(path)])
    COMPOSE_COMMAND = tuple(command)

# Historical post-apply edits that were merged before checksum enforcement was
# consistently used. Repairs are only permitted for this explicit inventory;
# new drift must be fixed with a new migration.
APPROVED_CHECKSUM_REPAIRS = {
    # The Kernel candidate was bootstrapped from the repository-base version
    # of 000_extensions.sql, which installed these same six extensions before
    # the three optional declarations were split into migration 378. Permit an
    # audited ledger repair only when the exact known checksum is recorded and
    # the complete extension effect is present on the target.
    "schema:000_extensions.sql": "6e5850e52423ffe8cea241f7f5764bb6c074d55813de33c601c9e8b1495723ff",
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
    # The live database contains the historical checksum from the original
    # pilot seed; repair it explicitly before applying the UID correction seed.
    "seed:014_pilot_celo_eas.sql": "2b7f95344a6453cb77fafc591255cb81e3c298553ea227241362d0c12183e9c8",
}

# This two-history repair is bound to both exact files: the candidate's
# repository-base checksum and the current source checksum. If 000_extensions
# changes again, the explicit compatibility review must be updated first.
APPROVED_CHECKSUM_REPAIR_TARGETS = {
    "schema:000_extensions.sql": "cf493b739f31cb2a9fb215dd5c7ccbc1ed2c8a2584ce156857416360a741a245",
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
    # Source-only commands such as `validate` must not load SOPS credentials.
    # Import the configured connection only when a command actually contacts
    # PostgreSQL.
    from ..common.db import PG_DB, PG_USER

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False)
    try:
        tmp.write(f"SET search_path = {MIGRATION_SEARCH_PATH};\n{input_sql}")
        tmp.flush()
        tmp_name = tmp.name
        tmp.close()
        psql_args = [
            "psql", "-X", "-q", "-U", PG_USER, "-d", PG_DB,
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
        compose = shlex.join(COMPOSE_COMMAND)
        shell_cmd = [
            "sh", "-c",
            f"{compose} exec -T database {quoted_args} < '{escaped_tmp}'",
        ]
        try:
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                env=worker_subprocess_environment(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MigrationError(
                f"psql execution failed ({safe_exception_class(exc)})"
            ) from exc
        if result.returncode != 0:
            raise MigrationError(
                f"psql execution failed with exit status {result.returncode}"
            )
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
            version = path.stem.split("_", 1)[0]
            if kind == "schema" and not version.isdigit():
                continue
            if kind == "seed" and not SEED_VERSION_PREFIX.fullmatch(version):
                continue
            migration_id = f"{kind}:{path.name}"
            if migration_id in seen_ids:
                raise MigrationError(f"duplicate migration ID discovered: {migration_id}")
            seen_ids.add(migration_id)
            files.append({
                "id": migration_id,
                "version": version,
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
        # Seeds intentionally share version prefixes: the version is a coarse
        # grouping and ordering is enforced by the full ``seed:<filename>``
        # migration ID (checksummed per file). Examples: multiple ``000_*``
        # bootstrap seeds, ``038_pilot_commons_liberation`` vs
        # ``038_commons_liberation_and_stewardship``, ``101_adaptation_velocity_config``
        # vs ``101_pilot_data_stream_posts``. Schema migrations, however, must
        # have one unambiguous numeric version.
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
            raise MigrationError("invalid schema_migration query output")
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
    if migration_id == "schema:000_extensions.sql":
        result = _psql("""
SELECT count(*) = 6
FROM pg_extension
WHERE extname = ANY(ARRAY[
    'uuid-ossp', 'pgcrypto', 'postgis', 'postgis_topology', 'pg_trgm', 'pg_stat_statements'
]);
""")
        if result.stdout.strip().lower() != "t":
            raise MigrationError(
                "schema validation failed: all six extensions from the historical source must exist"
            )
        return
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
    expected_new_checksum = APPROVED_CHECKSUM_REPAIR_TARGETS.get(migration_id)
    if expected_new_checksum and file_info["checksum"] != expected_new_checksum:
        raise MigrationError(
            f"current source checksum is not approved for repair of {migration_id}"
        )
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


_TRANSACTION_CONTROL_LINE = re.compile(
    r"^\s*(BEGIN|START\s+TRANSACTION|COMMIT)\s*;\s*$", re.IGNORECASE
)


def _migration_body_without_transaction(migration_id: str, sql_content: str) -> str:
    """Remove balanced transaction markers so runner and ledger share one."""
    lines = sql_content.splitlines()
    boundary_lines: set[int] = set()
    transaction_open = False
    for index, line in enumerate(lines):
        match = _TRANSACTION_CONTROL_LINE.match(line)
        if not match:
            continue
        command = match.group(1).upper()
        if command == "COMMIT":
            if not transaction_open:
                raise MigrationError(
                    f"migration has unsupported transaction boundaries: {migration_id}"
                )
            transaction_open = False
        else:
            if transaction_open:
                raise MigrationError(
                    f"migration has nested transaction boundaries: {migration_id}"
                )
            transaction_open = True
        boundary_lines.add(index)

    if not boundary_lines:
        return sql_content
    if transaction_open:
        raise MigrationError(
            f"migration has unsupported transaction boundaries: {migration_id}"
        )
    return "\n".join(
        line for index, line in enumerate(lines)
        if index not in boundary_lines
    ) + "\n"


def _mobile_form_seed_state_query(seed_path: Path) -> str:
    """Build a source-derived check for empty or exactly matching form state."""
    sql_source = seed_path.read_text()
    values_marker = "FROM (VALUES"
    alias_marker = ") AS seed ("
    try:
        values_start = sql_source.index(values_marker) + len(values_marker)
        values_end = sql_source.index(alias_marker, values_start)
        columns_start = values_end + len(alias_marker)
        columns_end = sql_source.index(")", columns_start)
    except ValueError as exc:
        raise MigrationError(
            "mobile form seed source no longer matches the reviewed VALUES layout"
        ) from exc

    columns = tuple(
        column.strip()
        for column in sql_source[columns_start:columns_end].split(",")
    )
    if columns != MOBILE_FORM_SEED_COLUMNS:
        raise MigrationError(
            "mobile form seed columns changed; update and review its parity guard first"
        )
    values = sql_source[values_start:values_end].strip()
    if not values:
        raise MigrationError("mobile form seed has no source rows")

    actual_form_differences = ", ".join(
        f"CASE WHEN actual.{column} IS DISTINCT FROM expected.{column} "
        f"THEN '{column}' END"
        for column in columns
        if column != "form_id"
    )
    active_revision_differences = ", ".join(
        f"CASE WHEN revision.{column} IS DISTINCT FROM expected.{column} "
        f"THEN '{column}' END"
        for column in columns
        if column not in {"form_id", "version"}
    )
    return f"""
WITH expected ({", ".join(columns)}) AS (
    VALUES
{values}
)
SELECT CASE
    WHEN NOT EXISTS (
        SELECT 1
        FROM expected
        JOIN public.mobile_form AS actual USING (form_id)
    )
    AND NOT EXISTS (
        SELECT 1
        FROM expected
        JOIN public.mobile_form_version AS revision USING (form_id)
    ) THEN 'empty'
    WHEN EXISTS (
        SELECT 1
        FROM expected
        LEFT JOIN public.mobile_form AS actual USING (form_id)
        LEFT JOIN public.mobile_form_version AS revision
          ON revision.form_id = expected.form_id
         AND revision.version = expected.version
         AND revision.status = expected.status
        WHERE actual.form_id IS NULL
           OR concat_ws(',', {actual_form_differences}) <> ''
           OR revision.form_id IS NULL
           OR concat_ws(',', {active_revision_differences}) <> ''
    ) THEN 'mismatch'
    ELSE 'matched'
END
"""


def _assert_mobile_form_seed_matches_source(seed_path: Path) -> str:
    """Allow a clean insert or a verified no-op; reject partial or divergent rows."""
    result = _psql(_mobile_form_seed_state_query(seed_path))
    state = result.stdout.strip()
    if state not in {"empty", "matched"}:
        if state == "mismatch":
            raise MigrationError(
                "existing mobile form or active revision differs from "
                "seed:140_mobile_forms.sql; reconcile it before recording this seed"
            )
        raise MigrationError("could not verify existing mobile-form seed state")
    return state


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
        precondition_sql = ""
        if migration_id == MOBILE_FORM_SEED_ID:
            state_query = _mobile_form_seed_state_query(file_info["path"]).strip().rstrip(";")
            precondition_sql = f"""
LOCK TABLE public.mobile_form IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.mobile_form_version IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE
    seed_state TEXT;
BEGIN
    SELECT ({state_query}) INTO seed_state;
    IF seed_state = 'mismatch' THEN
        RAISE EXCEPTION USING MESSAGE =
            'existing mobile form or active revision differs from seed:140_mobile_forms.sql; reconcile it before recording this seed';
    END IF;
END;
$$;
"""
        sql_content = _migration_body_without_transaction(
            migration_id, file_info["path"].read_text()
        )
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
BEGIN;
{precondition_sql}
{sql_content}
{sql_track}
COMMIT;
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


def cmd_migrate(
    dry_run: bool = False,
    schemas_only: bool = False,
    only_migrations: list[str] | None = None,
) -> None:
    files, applied = _load_state(include_seeds=not schemas_only)
    if only_migrations is not None:
        if not only_migrations:
            raise MigrationError("--only-migration requires at least one migration ID")
        if len(set(only_migrations)) != len(only_migrations):
            raise MigrationError("--only-migration IDs must be unique")
        by_id = {item["id"]: item for item in files}
        missing = [migration_id for migration_id in only_migrations if migration_id not in by_id]
        if missing:
            raise MigrationError(
                "selected migration IDs were not discovered: " + ", ".join(missing)
            )
        files = [by_id[migration_id] for migration_id in only_migrations]
    pending = [
        item for item in files
        if applied.get(item["id"], {}).get("status") != "applied"
    ]
    if (
        only_migrations is not None
        and any(item["id"] == MOBILE_FORM_SEED_ID for item in pending)
    ):
        # Refuse before earlier members of a curated batch can run; _apply_files
        # repeats the source comparison under table locks before the seed body.
        seed_file = next(
            item for item in pending if item["id"] == MOBILE_FORM_SEED_ID
        )
        _assert_mobile_form_seed_matches_source(seed_file["path"])
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
    parser.add_argument("--compose-project", help="Explicit Compose project; requires --compose-file")
    parser.add_argument("--compose-file", action="append",
                        help="Explicit Compose manifest (repeat for overlays); requires --compose-project")
    parser.add_argument(
        "--schemas-only",
        action="store_true",
        help="Apply only PostgreSQL schema migrations, excluding seed data",
    )
    parser.add_argument(
        "--only-migration",
        action="append",
        dest="only_migrations",
        help="Apply only this discovered migration ID (repeat to preserve an explicit order)",
    )
    args = parser.parse_args()
    try:
        configure_compose(args.compose_project, args.compose_file)
        if args.only_migrations and args.command != "migrate":
            raise MigrationError("--only-migration is supported only by the migrate command")
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
            cmd_migrate(
                schemas_only=args.schemas_only,
                only_migrations=args.only_migrations,
            )
    except MigrationError as exc:
        logger.error("Migration failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
