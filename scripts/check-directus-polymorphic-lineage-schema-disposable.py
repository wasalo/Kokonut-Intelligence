#!/usr/bin/env python3
"""Replay current schemas on isolated PostgreSQL and parse preflight queries."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
COMPOSE_FILE = ROOT / "docker-compose.schema-bootstrap.yml"
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-28-recovery/directus-polymorphic-lineage-schema-disposable.json"
DEFAULT_IMAGE = (
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
)
PREFLIGHT_PATH = ROOT / "scripts/directus-polymorphic-lineage-preflight.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "directus_polymorphic_lineage_preflight", PREFLIGHT_PATH,
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError("preflight source is unavailable")
preflight = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight)


class DisposableCommandFailure(RuntimeError):
    def __init__(
        self,
        returncode: int,
        sqlstate: str | None = None,
        safe_metadata: dict[str, object] | None = None,
    ) -> None:
        super().__init__("isolated command failed")
        self.returncode = returncode
        self.sqlstate = sqlstate
        self.safe_metadata = safe_metadata or {}


def extract_sqlstate(diagnostic: str) -> str | None:
    """Keep only PostgreSQL's five-character error code from verbose psql text."""
    match = re.search(
        r"(?:SQL state:\s*|ERROR:\s+)([0-9A-Z]{5})(?=[:\s])",
        diagnostic,
    )
    return match.group(1) if match else None


def extract_safe_aggregate_metadata(stdout: str) -> dict[str, object]:
    """Retain only recognized count rows emitted by the schema-only SQL batch."""
    metadata: dict[str, object] = {}
    for line in stdout.splitlines():
        fields = line.strip().split("\t")
        if fields[0:1] == ["catalog"] and len(fields) == 5 and all(
            value.isdigit() for value in fields[1:]
        ):
            metadata["catalog"] = {
                "relations_expected": int(fields[1]),
                "relations_present": int(fields[2]),
                "columns_expected": int(fields[3]),
                "columns_present": int(fields[4]),
            }
        elif fields[0:1] in (["workflow_history"], ["approval"]) and len(fields) == 2 and fields[1].isdigit():
            metadata[fields[0]] = {"aggregate_group_count": int(fields[1])}
    return metadata


def run(command: list[str], *, env: dict[str, str], input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=3600,
    )
    if result.returncode:
        diagnostic = result.stdout + "\n" + result.stderr
        raise DisposableCommandFailure(
            result.returncode,
            extract_sqlstate(diagnostic),
            extract_safe_aggregate_metadata(result.stdout),
        )
    return result.stdout.strip()


def compose_base(docker: str, project: str) -> list[str]:
    return [
        docker, "compose", "--project-directory", str(ROOT), "--env-file", "/dev/null",
        "-p", project, "-f", str(COMPOSE_FILE),
    ]


def ensure_project_unused(docker: str, project: str, env: dict[str, str]) -> None:
    label = f"label=com.docker.compose.project={project}"
    checks = (
        [docker, "ps", "-a", "--filter", label, "--format", "{{.ID}}"],
        [docker, "volume", "ls", "--filter", label, "--format", "{{.Name}}"],
        [docker, "network", "ls", "--filter", label, "--format", "{{.ID}}"],
    )
    for command in checks:
        if run(command, env=env):
            raise RuntimeError("disposable project already has Docker resources")


def expected_catalog_sql() -> str:
    relations: dict[str, set[str]] = {
        "location": {"id"},
        "workflow_history": {"id", "collection", "record_id"},
        "approval": {"id", "collection", "record_id", "action"},
        "protocol_execution_intent": {"id", "mapping_id"},
        "protocol_project_location": {"id", "location_id"},
    }
    for source in preflight.DIRECT_LOCATION_SOURCES:
        relations[source] = {"id", "location_id"}
    relation_values = ",\n".join(
        f"('public.{name}')" for name in sorted(relations)
    )
    column_values = ",\n".join(
        f"('public.{name}', '{column}')"
        for name, columns in sorted(relations.items())
        for column in sorted(columns)
    )
    return f"""
        WITH expected_relations(relation_name) AS (VALUES {relation_values}),
        expected_columns(relation_name, column_name) AS (VALUES {column_values})
        SELECT
            (SELECT COUNT(*) FROM expected_relations) AS expected_relations,
            (SELECT COUNT(*) FROM expected_relations AS expected
              WHERE to_regclass(expected.relation_name) IS NOT NULL) AS present_relations,
            (SELECT COUNT(*) FROM expected_columns) AS expected_columns,
            (SELECT COUNT(*) FROM expected_columns AS expected
              JOIN information_schema.columns AS actual
                ON actual.table_schema = 'public'
               AND actual.table_name = split_part(expected.relation_name, '.', 2)
               AND actual.column_name = expected.column_name) AS present_columns
    """


def sql_validation() -> str:
    return f"""
\\set VERBOSITY verbose
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT 'catalog' AS check_name, expected_relations, present_relations,
       expected_columns, present_columns
  FROM ({expected_catalog_sql()}) AS catalog_counts;
SELECT 'workflow_history' AS check_name, COUNT(*) AS aggregate_group_count
  FROM ({preflight.build_workflow_history_query()}) AS grouped_counts;
SELECT 'approval' AS check_name, COUNT(*) AS aggregate_group_count
  FROM ({preflight.build_approval_query()}) AS grouped_counts;
ROLLBACK;
"""


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        print(json.dumps({"result": "blocked", "reason": "Docker CLI unavailable"}, sort_keys=True))
        return 2

    try:
        from services.migration.cli import _discover_files, _validate_sources

        migrations = _discover_files(include_seeds=False)
        _validate_sources(migrations)
    except Exception as exc:  # noqa: BLE001 - output must not expose environment details.
        print(json.dumps({"result": "failed", "phase": "source_validation", "error_type": type(exc).__name__}, sort_keys=True))
        return 1

    project = f"kokonut-directus-lineage-{date.today():%Y%m%d}-{secrets.token_hex(4)}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project):
        print(json.dumps({"result": "failed", "phase": "project_name"}, sort_keys=True))
        return 1

    password = secrets.token_urlsafe(24)
    env = os.environ.copy()
    env.update({
        "KOKONUT_ENV": "development",
        "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
        "KOKONUT_BOOTSTRAP_POSTGRES_IMAGE": os.environ.get("DIRECTUS_LINEAGE_TEST_IMAGE", DEFAULT_IMAGE),
        "POSTGRES_PASSWORD": password,
        "PG_USER": "kokonut",
        "PG_DB": "kokonut_intelligence",
    })
    compose = compose_base(docker, project)
    started = False
    migrations_applied = False
    cleanup_verified = False
    phase = "project_preflight"
    evidence: dict[str, object] | None = None
    failure: dict[str, str] | None = None
    try:
        ensure_project_unused(docker, project, env)
        phase = "image_preflight"
        run([docker, "image", "inspect", env["KOKONUT_BOOTSTRAP_POSTGRES_IMAGE"], "--format", "{{.Os}}/{{.Architecture}}"], env=env)
        phase = "disposable_database_start"
        started = True
        run(compose + ["up", "-d", "--wait", "--wait-timeout", "300", "database"], env=env)
        container_id = run(compose + ["ps", "-q", "database"], env=env)
        if not re.fullmatch(r"[a-f0-9]{12,64}", container_id):
            raise RuntimeError("could not identify the disposable schema container")
        inspect = run(
            [
                docker, "inspect", container_id, "--format",
                "{{json .HostConfig.NetworkMode}}|{{json .NetworkSettings.Ports}}",
            ],
            env=env,
        )
        try:
            network_mode, encoded_ports = inspect.split("|", 1)
            published_ports = json.loads(encoded_ports)
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("could not verify disposable network isolation") from exc
        if network_mode.strip('"') != "none" or any(
            bindings for bindings in published_ports.values() if bindings
        ):
            raise RuntimeError("disposable database is not isolated from host networking")
        phase = "ordered_schema_migrations"
        migration_command = [
            sys.executable, "-m", "services.migration", "migrate", "--schemas-only",
            "--compose-project", project, "--compose-file", str(COMPOSE_FILE),
        ]
        run(migration_command, env=env)
        migrations_applied = True
        phase = "generated_sql_schema_validation"
        result = run(
            compose + [
                "exec", "-T", "database", "psql", "-X", "-q", "-U", "kokonut",
                "-d", "kokonut_intelligence", "-A", "-t", "-F", "\t",
                "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose",
            ],
            env=env,
            input_text=sql_validation(),
        )
        rows = [line.split("\t") for line in result.splitlines() if line.strip()]
        safe_metadata = extract_safe_aggregate_metadata(result)
        if len(rows) != 3 or rows[0][0] != "catalog":
            raise RuntimeError("unexpected schema validation result shape")
        expected_relations, present_relations, expected_columns, present_columns = map(int, rows[0][1:])
        if expected_relations != present_relations or expected_columns != present_columns:
            raise RuntimeError("allowlisted source schema is incomplete")
        if rows[1][0] != "workflow_history" or int(rows[1][1]) != 0:
            raise RuntimeError("schema-only workflow history fixture was not empty")
        if rows[2][0] != "approval" or int(rows[2][1]) != 0:
            raise RuntimeError("schema-only approval fixture was not empty")
        evidence = {
            "result": "passed",
            "validation_scope": "schema_only_disposable_postgresql",
            "schema_migrations_discovered": len(migrations),
            "schema_migrations_applied": len(migrations),
            "latest_schema_migration_id": migrations[-1]["id"],
            "seed_migrations_applied": 0,
            "source_relations_expected": expected_relations,
            "source_relations_present": present_relations,
            "required_columns_expected": expected_columns,
            "required_columns_present": present_columns,
            "safe_aggregate_metadata": safe_metadata,
            "workflow_history_aggregate_group_count": 0,
            "approval_aggregate_group_count": 0,
            "transaction": "repeatable_read_read_only",
            "network_mode": "none",
            "host_ports_published": False,
            "candidate_or_legacy_touched": False,
            "populated_row_acceptance": "not_run",
        }
    except Exception as exc:  # noqa: BLE001 - suppress subprocess/database diagnostics.
        failure = {"result": "failed", "phase": phase, "error_type": type(exc).__name__}
        if isinstance(exc, DisposableCommandFailure):
            failure["command_exit_code"] = str(exc.returncode)
            if exc.sqlstate is not None:
                failure["sqlstate"] = exc.sqlstate
            if exc.safe_metadata:
                failure["safe_aggregate_metadata"] = exc.safe_metadata
    finally:
        if started:
            cleanup = subprocess.run(
                compose + ["down", "--volumes", "--remove-orphans"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if cleanup.returncode and failure is None:
                failure = {
                    "result": "failed",
                    "phase": "disposable_cleanup",
                    "error_type": "CleanupFailure",
                }
            elif cleanup.returncode == 0:
                try:
                    ensure_project_unused(docker, project, env)
                    cleanup_verified = True
                except Exception as exc:  # noqa: BLE001 - no resource identifiers are emitted.
                    if failure is None:
                        failure = {
                            "result": "failed",
                            "phase": "disposable_cleanup_verification",
                            "error_type": type(exc).__name__,
                        }
                    else:
                        failure["cleanup_error_type"] = type(exc).__name__
            elif failure is not None:
                failure["cleanup_error_type"] = "CleanupFailure"

    if failure is not None:
        failure_evidence: dict[str, object] = {
            **failure,
            "validation_scope": "schema_only_disposable_postgresql",
            "schema_migrations_discovered": len(migrations),
            "schema_migrations_applied": len(migrations) if migrations_applied else None,
            "seed_migrations_applied": 0,
            "network_mode": "none" if started else "not_started",
            "host_ports_published": False,
            "cleanup": "completed_and_verified" if cleanup_verified else "not_verified",
            "candidate_or_legacy_touched": False,
            "populated_row_acceptance": "not_run",
        }
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(failure_evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps(failure, sort_keys=True))
        return 1
    if evidence is None:
        print(json.dumps({"result": "failed", "phase": "evidence", "error_type": "MissingEvidence"}, sort_keys=True))
        return 1
    evidence["cleanup"] = "completed_and_verified"
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
