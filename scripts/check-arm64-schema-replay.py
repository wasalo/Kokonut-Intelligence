#!/usr/bin/env python3
"""Replay current schemas on an isolated disposable PostgreSQL/PostGIS database."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.schema-bootstrap.yml"
SOURCE_READER_MIGRATION = "schema:541_agent_synthesis_source_reader.sql"
sys.path.insert(0, str(ROOT))


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a checked command, optionally capturing its small machine result."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        input=input_text,
        text=True,
        capture_output=capture,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:4])}"
        )
    return result


def compose_base(project: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "--env-file",
        "/dev/null",
        "-p",
        project,
        "-f",
        str(COMPOSE_FILE),
    ]


def migration_command(
    project: str, database: str, migration_ids: list[str]
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "services.migration",
        "migrate",
        "--schemas-only",
        "--compose-project",
        project,
        "--compose-file",
        str(COMPOSE_FILE),
    ]
    for migration_id in migration_ids:
        command.extend(("--only-migration", migration_id))
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        default="kokonut-kernel-postgis-arm64:local",
        help="locally available ARM64 PostgreSQL/PostGIS image",
    )
    parser.add_argument("--platform", default="linux/arm64")
    parser.add_argument("--project", help="unique disposable Compose project name")
    parser.add_argument("--output", type=Path, help="evidence JSON output path")
    args = parser.parse_args()

    if args.platform not in {"linux/arm64", "linux/amd64"}:
        parser.error("platform must be linux/arm64 or linux/amd64")
    project = args.project or f"kokonut-arm64-schema-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project):
        parser.error("project must be a lowercase Docker Compose project name")

    from services.migration.cli import _discover_files, _validate_sources

    files = _discover_files(include_seeds=False)
    _validate_sources(files)
    ids = [file_info["id"] for file_info in files]
    if SOURCE_READER_MIGRATION not in ids:
        raise SystemExit(f"source-reader migration not found: {SOURCE_READER_MIGRATION}")
    split_at = ids.index(SOURCE_READER_MIGRATION)
    if len(ids) != len(set(ids)):
        raise SystemExit("schema migration IDs must be unique")

    output = args.output or ROOT / "docs/refactor/builds" / f"{date.today():%Y-%m-%d}-recovery" / f"arm64-qemu-current-schema-{ids[-1].split(':', 1)[1].split('_', 1)[0]}.json"
    compose = compose_base(project)
    database = f"kokonut_bootstrap_{os.getpid()}"
    env = os.environ.copy()
    env.update(
        {
            "KOKONUT_ENV": "development",
            "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
            "KOKONUT_BOOTSTRAP_POSTGRES_IMAGE": args.image,
            "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
            "PG_USER": "kokonut",
            "PG_DB": database,
        }
    )
    evidence: dict[str, object] = {
        "result": "failed",
        "date": date.today().isoformat(),
        "source_revision": run(["git", "rev-parse", "--short", "HEAD"], capture=True).stdout.strip(),
        "working_tree_dirty": bool(run(["git", "status", "--short"], capture=True).stdout.strip()),
        "runtime_architecture": args.platform,
        "execution": "QEMU on Docker host" if args.platform == "linux/arm64" else "native Docker host",
        "database_image": {"name": args.image},
        "isolated_compose_project": project,
        "schema_files_expected": len(ids),
        "schema_files_applied": 0,
        "schema_files_pending": len(ids),
        "schema_files_failed": None,
        "latest_migration": ids[-1],
        "network_mode": "none",
        "host_ports_published": False,
        "seeds_applied": 0,
        "farm_data_loaded": False,
        "candidate_or_legacy_touched": False,
        "cleanup": {"attempted": False, "completed": False},
    }
    stage = "image_inspection"
    started = time.monotonic()
    project_started = False
    try:
        image = run(
            ["docker", "image", "inspect", args.image, "--format", "{{.Os}}/{{.Architecture}} {{.Id}}"],
            capture=True,
        ).stdout.strip().split(maxsplit=1)
        if len(image) != 2 or image[0] != args.platform:
            raise RuntimeError(f"image platform is not {args.platform}")
        evidence["database_image"] = {
            "name": args.image,
            "platform": image[0],
            "image_id": image[1],
        }

        stage = "database_start"
        project_started = True
        run(compose + ["up", "-d", "--wait", "database"], env=env)
        run(
            compose
            + ["exec", "-T", "database", "psql", "-X", "-U", "kokonut", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
            env=env,
            input_text=(ROOT / "scripts/bootstrap-optional-roles.sql").read_text(),
        )
        run(
            compose
            + ["exec", "-T", "database", "psql", "-X", "-U", "kokonut", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{database}"'],
            env=env,
        )

        stage = "schemas_before_signed_source_reader"
        run(migration_command(project, database, ids[:split_at]), env=env)
        evidence["schema_files_applied"] = split_at
        evidence["schema_files_pending"] = len(ids) - split_at
        evidence["latest_applied_migration"] = ids[split_at - 1]

        for migration_id in ids[split_at:]:
            stage = f"migration_{migration_id.split(':', 1)[1]}"
            run(migration_command(project, database, [migration_id]), env=env)
            evidence["schema_files_applied"] = int(evidence["schema_files_applied"]) + 1
            evidence["schema_files_pending"] = int(evidence["schema_files_pending"]) - 1
            evidence["latest_applied_migration"] = migration_id

        stage = "schema_verification"
        query = (
            "SELECT pg_catalog.jsonb_build_object("
            "'applied', count(*) FILTER (WHERE migration_id LIKE 'schema:%' AND status='applied'), "
            "'pending', count(*) FILTER (WHERE migration_id LIKE 'schema:%' AND status='pending'), "
            "'failed', count(*) FILTER (WHERE migration_id LIKE 'schema:%' AND status='failed'), "
            "'latest', (SELECT name FROM schema_migration WHERE migration_id LIKE 'schema:%' "
            "ORDER BY substring(migration_id FROM '^schema:([0-9]+)')::integer DESC LIMIT 1), "
            "'seeds', count(*) FILTER (WHERE migration_id LIKE 'seed:%'), "
            "'pg_stat_public_select', (SELECT COALESCE(bool_or("
            "acl.grantee = 0 AND acl.privilege_type = 'SELECT'), false) "
            "FROM pg_class AS relation "
            "CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE("
            "relation.relacl, pg_catalog.acldefault('r', relation.relowner)"
            ")) AS acl "
            "WHERE relation.oid IN (to_regclass('public.pg_stat_statements'), "
            "to_regclass('public.pg_stat_statements_info'))))::text "
            "FROM schema_migration"
        )
        status_output = run(
            compose
            + ["exec", "-T", "database", "psql", "-X", "-U", "kokonut", "-d", database, "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", query],
            env=env,
            capture=True,
        ).stdout.strip()
        try:
            status = json.loads(status_output)
        except json.JSONDecodeError as exc:
            evidence["schema_status_output"] = status_output[:1000]
            raise RuntimeError("unexpected migration status JSON") from exc
        evidence["schema_status"] = status
        applied = int(status["applied"])
        pending = int(status["pending"])
        failed = int(status["failed"])
        seeds = int(status["seeds"])
        evidence["schema_files_applied"] = applied
        evidence["schema_files_pending"] = pending
        evidence["schema_files_failed"] = failed
        evidence["latest_migration"] = status["latest"]
        evidence["seeds_applied"] = seeds
        evidence["pg_stat_statements_public_select"] = bool(status["pg_stat_public_select"])
        evidence["container_architecture"] = run(
            compose + ["exec", "-T", "database", "uname", "-m"], env=env, capture=True
        ).stdout.strip()
        if (
            applied != len(ids)
            or pending != 0
            or failed != 0
            or seeds != 0
            or status["pg_stat_public_select"]
            or evidence["container_architecture"] != {"linux/arm64": "aarch64", "linux/amd64": "x86_64"}[args.platform]
        ):
            raise RuntimeError("schema count, seed count, or ARM64 architecture check failed")
        evidence["result"] = "passed"
    except Exception as exc:  # evidence stores only safe failure metadata
        evidence["failed_stage"] = stage
        evidence["failure"] = type(exc).__name__
        if stage.startswith("migration_"):
            migration_id = f"schema:{stage.removeprefix('migration_')}"
            evidence["failed_migration"] = migration_id
            evidence["schema_files_failed"] = 1
            evidence["schema_files_pending"] = max(
                0,
                len(ids)
                - int(evidence["schema_files_applied"])
                - 1,
            )
            sql_file = next((entry["path"] for entry in files if entry["id"] == migration_id), None)
            if sql_file is not None:
                diagnostic_sql = (
                    "SET search_path = public, topology, tiger;\n"
                    + sql_file.read_text(encoding="utf-8")
                )
                diagnostic = subprocess.run(
                    compose
                    + ["exec", "-T", "database", "psql", "-X", "-q", "-U", "kokonut", "-d", database, "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose", "-c", diagnostic_sql],
                    cwd=ROOT,
                    env=env,
                    input=None,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                safe_lines = [
                    line.strip()
                    for line in diagnostic.stderr.splitlines()
                    if "ERROR:" in line or "DETAIL:" in line or "HINT:" in line
                ]
                if safe_lines:
                    evidence["migration_diagnostic"] = " | ".join(safe_lines)[:2000]
        print(f"schema replay failed during {stage} ({type(exc).__name__})", file=sys.stderr)
    finally:
        evidence["elapsed_seconds"] = round(time.monotonic() - started, 1)
        if project_started:
            evidence["cleanup"] = {"attempted": True, "completed": False}
            cleanup = subprocess.run(
                compose + ["down", "--volumes", "--remove-orphans"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            evidence["cleanup"] = {
                "attempted": True,
                "completed": cleanup.returncode == 0,
            }
            if cleanup.returncode:
                evidence["result"] = "failed"
                evidence["cleanup_error"] = "compose teardown failed"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(output)

    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
