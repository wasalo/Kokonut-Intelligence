#!/usr/bin/env python3
"""Replay current schemas on an isolated disposable PostgreSQL/PostGIS database."""

from __future__ import annotations

import argparse
import json
import math
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
OPERATOR_PROBE = ROOT / "scripts/fixtures/sprint_operator_scope_probe.py"
OPERATOR_PROBE_CHECKS = frozenset({
    "runtime and operator-auth logins cannot bypass RLS or create roles or databases",
    "two synthetic tenant/location/identity/grant sets were created",
    "both restricted logins are denied direct operator-session reads",
    "operator-auth login created two sessions through the bounded function",
    "each real runtime login context sees only its synthetic tenant under forced RLS",
    "wrong-location denial clears context and tenant-probe visibility",
    "tenant context is cleared at transaction end",
    "revoked grant and revoked session both fail closed",
    "runtime provisioner denied direct table and column access to private relations",
    "runtime provisioner denied direct mutations on scoped relations and preserved farm-activity ledger reads",
    "runtime provisioner keeps shared advisory rules readable but immutable",
    "runtime can read seeded crop-nutrient removal factors",
    "runtime can query shared greenhouse-gas emission-factor references",
    "runtime can query shared versioned operations protocols",
    "runtime can read static process maturity levels",
    "runtime can read static pollinator species references",
    "runtime can query shared GRI indicator mappings",
    "runtime can query the governance framework registry",
    "runtime can query shared impact frameworks",
    "runtime can query shared impact framework dimensions",
    "runtime can read governed expense categories",
    "runtime can query shared CRISP risk dimension definitions",
    "runtime can read seeded certification types",
    "runtime can read seeded cooperative types",
    "runtime can read seeded insurance product types",
    "runtime provisioner limited API-key reads to reviewed columns and denied all writes",
    "runtime can append and read data-access evidence but cannot update, delete, or truncate it",
})
sys.path.insert(0, str(ROOT))


class ReplayCommandFailure(RuntimeError):
    """A failed captured replay command, retaining its output for safe parsing."""

    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        super().__init__(f"command failed ({returncode})")
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def started_schema_migrations(output: str) -> list[str]:
    """Extract ordered migration IDs logged immediately before each apply."""
    return [
        match.rstrip(".")
        for match in re.findall(r"Applying migration (schema:\S+)", output)
    ]


def failed_batch_progress(
    output: str, *, already_applied: int, total: int
) -> dict[str, object] | None:
    """Summarize the last started migration and completed prefix after batch failure."""
    started = started_schema_migrations(output)
    if not started:
        return None

    applied = already_applied + max(0, len(started) - 1)
    result: dict[str, object] = {
        "schema_files_applied": applied,
        "schema_files_pending": max(0, total - applied - 1),
        "schema_files_failed": 1,
        "failed_migration": started[-1],
    }
    if len(started) > 1:
        result["latest_applied_migration"] = started[-2]
    return result


def safe_error_summary(output: str) -> str | None:
    """Keep only bounded PostgreSQL diagnostic lines in replay evidence."""
    lines = [
        line.strip()
        for line in output.splitlines()
        if re.search(r"\b(?:ERROR|DETAIL|HINT):", line)
    ]
    return " | ".join(lines)[:2000] or None


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
        if capture:
            raise ReplayCommandFailure(
                result.returncode,
                result.stdout or "",
                result.stderr or "",
            )
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:4])}"
        )
    return result


def ensure_disposable_project_unused(project: str, *, command_runner=run) -> None:
    """Refuse a project with existing resources before any compose teardown is possible."""
    label = f"label=com.docker.compose.project={project}"
    checks = (
        ["docker", "ps", "-a", "--filter", label, "--format", "{{.ID}}"],
        ["docker", "volume", "ls", "--filter", label, "--format", "{{.Name}}"],
        ["docker", "network", "ls", "--filter", label, "--format", "{{.ID}}"],
    )
    for command in checks:
        if command_runner(command, capture=True).stdout.strip():
            raise RuntimeError("disposable Compose project already has resources")
    volume_names = command_runner(
        ["docker", "volume", "ls", "--format", "{{.Name}}"], capture=True
    ).stdout.splitlines()
    container_names = command_runner(
        ["docker", "ps", "-a", "--format", "{{.Names}}"], capture=True
    ).stdout.splitlines()
    if f"{project}_schema-bootstrap-data" in volume_names or f"{project}-database-1" in container_names:
        raise RuntimeError("disposable Compose project resource name already exists")


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


def operator_scope_probe_command(container_id: str, client_image: str) -> list[str]:
    """Run the probe in the replay database's network namespace, without a host port."""
    if not re.fullmatch(r"[a-f0-9]{12,64}", container_id):
        raise ValueError("invalid disposable database container ID")
    return [
        "docker", "run", "--rm", "--pull=never",
        "--network", f"container:{container_id}",
        "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--env", "SPRINT_DISPOSABLE", "--env", "SPRINT_DATABASE",
        "--env", "SPRINT_ADMIN_PASSWORD", "--env", "SPRINT_RUNTIME_PASSWORD",
        "--env", "SPRINT_AUTH_PASSWORD", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--volume", f"{ROOT / 'services'}:/workspace/services:ro",
        "--volume", f"{ROOT / 'VERSION'}:/workspace/VERSION:ro",
        "--volume", f"{OPERATOR_PROBE}:/workspace/probe.py:ro",
        "--workdir", "/workspace", "--entrypoint", "python3",
        client_image, "/workspace/probe.py",
    ]


def resource_limit_values(memory_limit: str | None, cpu_limit: float | None) -> tuple[int | None, int | None]:
    """Parse resource budgets into Docker's HostConfig byte and nanocpu units."""
    memory_bytes = None
    if memory_limit is not None:
        match = re.fullmatch(r"([1-9][0-9]*)([KMG]i?B?)?", memory_limit, re.IGNORECASE)
        if match is None:
            raise ValueError("memory limit must be a positive byte count or K/KB/KiB, M/MB/MiB, G/GB/GiB value")
        amount = int(match.group(1))
        unit = (match.group(2) or "").upper()
        multiplier = {
            "": 1,
            "K": 1000,
            "KB": 1000,
            "KIB": 1024,
            "M": 1000**2,
            "MB": 1000**2,
            "MIB": 1024**2,
            "G": 1000**3,
            "GB": 1000**3,
            "GIB": 1024**3,
        }[unit]
        memory_bytes = amount * multiplier
        if memory_bytes < 64 * 1024 * 1024:
            raise ValueError("memory limit must be at least 64 MiB")

    nano_cpus = None
    if cpu_limit is not None:
        if not math.isfinite(cpu_limit) or cpu_limit <= 0 or cpu_limit > 64:
            raise ValueError("CPU limit must be greater than 0 and at most 64")
        nano_cpus = round(cpu_limit * 1_000_000_000)
    return memory_bytes, nano_cpus


def apply_resource_limits(
    project: str,
    *,
    memory_bytes: int | None,
    nano_cpus: int | None,
    env: dict[str, str],
    command_runner=run,
) -> dict[str, int] | None:
    """Set and verify Docker limits on a created but not yet started database."""
    if memory_bytes is None and nano_cpus is None:
        return None
    container_id = command_runner(
        compose_base(project) + ["ps", "-a", "-q", "database"], env=env, capture=True
    ).stdout.strip()
    if not re.fullmatch(r"[a-f0-9]{12,64}", container_id):
        raise RuntimeError("could not identify the fresh disposable database")
    update = ["docker", "update"]
    if memory_bytes is not None:
        # Docker Desktop requires a finite swap ceiling alongside memory.
        # Equal values disable swap so the measured memory cap is exact.
        update.extend(("--memory", str(memory_bytes), "--memory-swap", str(memory_bytes)))
    if nano_cpus is not None:
        update.extend(("--cpus", f"{nano_cpus / 1_000_000_000:g}"))
    update.append(container_id)
    command_runner(update)
    inspection = command_runner(
        [
            "docker", "inspect", container_id,
            "--format", "{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.NanoCpus}}",
        ],
        capture=True,
    ).stdout.strip().split()
    if len(inspection) != 3:
        raise RuntimeError("could not verify disposable database resource limits")
    observed_memory, observed_memory_swap, observed_nano_cpus = map(int, inspection)
    if (
        memory_bytes is not None and observed_memory != memory_bytes
    ) or (
        memory_bytes is not None and observed_memory_swap != memory_bytes
    ) or (
        nano_cpus is not None and observed_nano_cpus != nano_cpus
    ):
        raise RuntimeError("Docker did not apply the requested database resource limits")
    return {
        "memory_bytes": observed_memory,
        "memory_swap_bytes": observed_memory_swap,
        "nano_cpus": observed_nano_cpus,
    }


def parse_operator_scope_probe(output: str) -> dict[str, object]:
    """Accept only a completed two-tenant probe; never infer success from exit alone."""
    result = json.loads(output)
    if not isinstance(result, dict) or result.get("result") != "passed":
        raise ValueError("operator scope probe did not report success")
    if any(result.get(key) != 2 for key in (
        "synthetic_tenant_count", "synthetic_location_count", "synthetic_operator_count"
    )):
        raise ValueError("operator scope probe did not cover both synthetic tenants")
    checks = result.get("checks")
    if not isinstance(checks, list) or any(not isinstance(item, str) for item in checks):
        raise ValueError("operator scope probe did not report its checks")
    if len(checks) != len(OPERATOR_PROBE_CHECKS) or set(checks) != OPERATOR_PROBE_CHECKS:
        raise ValueError("operator scope probe did not complete every required check")
    count = result.get("runtime_public_tables_with_dml_and_rls_disabled")
    if type(count) is not int or count < 0:
        raise ValueError("operator scope probe did not report its runtime DML exposure")
    scoped_write = result.get("runtime_scoped_write_policy")
    expected_scoped_fields = {
        "private_relations_expected",
        "mutation_denied_relations_expected",
        "private_relations_verified",
        "mutation_denied_relations_verified",
        "direct_table_privilege_violations",
        "direct_column_privilege_violations",
        "farm_activity_ledger_readable",
        "append_only_relations_expected",
        "append_only_relations_verified",
        "append_only_select_insert_verified",
        "append_only_mutations_denied",
        "append_only_column_grants_denied",
    }
    if not isinstance(scoped_write, dict) or set(scoped_write) != expected_scoped_fields:
        raise ValueError("operator scope probe did not report the runtime scoped-write boundary")
    if (
        scoped_write["private_relations_expected"] != 79
        or scoped_write["mutation_denied_relations_expected"] != 36
        or scoped_write["private_relations_verified"] != 79
        or scoped_write["mutation_denied_relations_verified"] != 36
        or scoped_write["direct_table_privilege_violations"] != 0
        or scoped_write["direct_column_privilege_violations"] != 0
        or scoped_write["farm_activity_ledger_readable"] != 1
        or scoped_write["append_only_relations_expected"] != 2
        or scoped_write["append_only_relations_verified"] != 2
        or scoped_write["append_only_select_insert_verified"] != 2
        or scoped_write["append_only_mutations_denied"] != 2
        or scoped_write["append_only_column_grants_denied"] != 2
    ):
        raise ValueError("operator scope probe did not verify every runtime scoped-write ACL")
    if result.get("runtime_api_key_policy") != {
        "select_columns": [
            "id", "key_hash", "key_prefix", "role_id", "scopes", "expires_at", "is_active"
        ],
        "insert_columns": [],
        "update_columns": [],
        "delete": False,
        "verified_by_provisioner": True,
    }:
        raise ValueError("operator scope probe did not verify the API-key column boundary")
    if result.get("runtime_append_only_policy") != {
        "relations_expected": 2,
        "relations_verified": 2,
        "select_insert_verified": 2,
        "mutations_denied": 2,
        "column_grants_denied": 2,
        "verified_by_provisioner": True,
    }:
        raise ValueError("operator scope probe did not verify the append-only audit boundary")
    relation_acl = result.get("runtime_public_relation_acl")
    if relation_acl is not None:
        if not isinstance(relation_acl, list):
            raise ValueError("operator scope probe returned an invalid relation ACL inventory")
        required_fields = {
            "schema", "relation", "kind", "select", "insert", "update",
            "delete", "truncate", "rls_enabled", "rls_forced",
        }
        for relation in relation_acl:
            if not isinstance(relation, dict) or set(relation) != required_fields:
                raise ValueError("operator scope probe returned an invalid relation ACL row")
            if relation["schema"] != "public" or not isinstance(relation["relation"], str):
                raise ValueError("operator scope probe returned an unexpected relation scope")
            if relation["kind"] not in {"r", "p", "v", "m", "f"} or any(
                type(relation[field]) is not bool
                for field in ("select", "insert", "update", "delete", "truncate", "rls_enabled", "rls_forced")
            ):
                raise ValueError("operator scope probe returned invalid relation ACL values")
        observed = sum(
            row["kind"] in {"r", "p"}
            and (row["insert"] or row["update"] or row["delete"])
            and not row["rls_enabled"]
            for row in relation_acl
        )
        if observed != count:
            raise ValueError("operator scope probe relation ACL inventory does not match its exposure count")
        default_acl = result.get("runtime_default_acl")
        if not isinstance(default_acl, list) or any(
            not isinstance(row, dict)
            or set(row) != {"grantor", "object_type", "schema", "runtime_or_public_grantee"}
            or type(row["runtime_or_public_grantee"]) is not bool
            for row in default_acl
        ):
            raise ValueError("operator scope probe returned an invalid default ACL inventory")
    return result


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
    parser.add_argument(
        "--memory-limit",
        help="optional disposable database memory cap (for example 1536MiB)",
    )
    parser.add_argument(
        "--cpu-limit",
        type=float,
        help="optional disposable database CPU cap (for example 2)",
    )
    parser.add_argument(
        "--operator-scope-probe", action="store_true",
        help="also exercise synthetic operator logins and tenant context after the full replay",
    )
    parser.add_argument(
        "--probe-image", default="kokonut-kernel-candidate-app:latest",
        help="locally available Kernel client image for the optional operator probe",
    )
    args = parser.parse_args()

    try:
        memory_bytes, nano_cpus = resource_limit_values(args.memory_limit, args.cpu_limit)
    except ValueError as exc:
        parser.error(str(exc))

    if args.platform not in {"linux/arm64", "linux/amd64"}:
        parser.error("platform must be linux/arm64 or linux/amd64")
    project_prefix = (
        "kokonut-arm64-schema"
        if args.platform == "linux/arm64"
        else "kokonut-native-schema"
    )
    project = args.project or f"{project_prefix}-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8]}"
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

    platform_label = "arm64-qemu" if args.platform == "linux/arm64" else "native"
    output = args.output or ROOT / "docs/refactor/builds" / f"{date.today():%Y-%m-%d}-recovery" / f"{platform_label}-current-schema-{ids[-1].split(':', 1)[1].split('_', 1)[0]}.json"
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
        "resource_limits": {
            "requested_memory_bytes": memory_bytes,
            "requested_cpu_count": (nano_cpus / 1_000_000_000) if nano_cpus is not None else None,
            "verified_database_limits": None,
        },
        "cleanup": {"attempted": False, "completed": False},
    }
    stage = "image_inspection"
    started_at = time.monotonic()
    project_started = False
    try:
        stage = "project_conflict_preflight"
        ensure_disposable_project_unused(project)
        stage = "image_inspection"
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
        if memory_bytes is not None or nano_cpus is not None:
            run(compose + ["create", "database"], env=env)
            evidence["resource_limits"]["verified_database_limits"] = apply_resource_limits(
                project,
                memory_bytes=memory_bytes,
                nano_cpus=nano_cpus,
                env=env,
            )
        run(compose + ["up", "-d", "--wait", "database"], env=env)
        database_container_id = run(
            compose + ["ps", "-q", "database"], env=env, capture=True
        ).stdout.strip()
        if not re.fullmatch(r"[a-f0-9]{12,64}", database_container_id):
            raise RuntimeError("could not identify the disposable database container")
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
        try:
            run(
                migration_command(project, database, ids[:split_at]),
                env=env,
                capture=True,
            )
        except ReplayCommandFailure as exc:
            migration_starts = started_schema_migrations(exc.stderr + "\n" + exc.stdout)
            if migration_starts:
                failed_migration = migration_starts[-1]
                applied_count = max(0, len(migration_starts) - 1)
                evidence["schema_files_applied"] = applied_count
                evidence["schema_files_pending"] = max(
                    0, len(ids) - applied_count - 1
                )
                evidence["schema_files_failed"] = 1
                evidence["failed_migration"] = failed_migration
                if applied_count:
                    evidence["latest_applied_migration"] = migration_starts[-2]
                stage = f"migration_{failed_migration.split(':', 1)[1]}"
            raise
        evidence["schema_files_applied"] = split_at
        evidence["schema_files_pending"] = len(ids) - split_at
        evidence["latest_applied_migration"] = ids[split_at - 1]

        remaining_migrations = ids[split_at:]
        stage = "schemas_after_signed_source_reader"
        try:
            run(
                migration_command(project, database, remaining_migrations),
                env=env,
                capture=True,
            )
        except ReplayCommandFailure as exc:
            progress = failed_batch_progress(
                exc.stderr + "\n" + exc.stdout,
                already_applied=split_at,
                total=len(ids),
            )
            if progress is not None:
                evidence.update(progress)
                failed_migration = str(progress["failed_migration"])
                stage = f"migration_{failed_migration.split(':', 1)[1]}"
            raise
        evidence["schema_files_applied"] = len(ids)
        evidence["schema_files_pending"] = 0
        evidence["latest_applied_migration"] = ids[-1]

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
        evidence["database_oom_killed"] = json.loads(
            run(
                ["docker", "inspect", database_container_id, "--format", "{{json .State.OOMKilled}}"],
                capture=True,
            ).stdout.strip()
        )
        if (
            applied != len(ids)
            or pending != 0
            or failed != 0
            or seeds != 0
            or evidence["database_oom_killed"]
            or status["pg_stat_public_select"]
            or evidence["container_architecture"] != {"linux/arm64": "aarch64", "linux/amd64": "x86_64"}[args.platform]
        ):
            raise RuntimeError("schema count, seed count, or ARM64 architecture check failed")
        if args.operator_scope_probe:
            stage = "operator_scope_probe_image_inspection"
            client_image = run(
                ["docker", "image", "inspect", args.probe_image, "--format", "{{.Os}}/{{.Architecture}} {{.Id}}"],
                capture=True,
            ).stdout.strip().split(maxsplit=1)
            evidence["operator_scope_probe_image"] = {
                "name": args.probe_image,
                "platform": client_image[0] if client_image else None,
                "image_id": client_image[1] if len(client_image) > 1 else None,
            }
            if len(client_image) != 2 or client_image[0] != args.platform:
                raise RuntimeError(f"probe image platform is not {args.platform}")
            stage = "operator_scope_probe"
            probe_env = env.copy()
            probe_env.update({
                "SPRINT_DISPOSABLE": "yes",
                "SPRINT_DATABASE": database,
                "SPRINT_ADMIN_PASSWORD": env["POSTGRES_PASSWORD"],
                "SPRINT_RUNTIME_PASSWORD": secrets.token_urlsafe(32),
                "SPRINT_AUTH_PASSWORD": secrets.token_urlsafe(32),
            })
            try:
                probe_output = run(
                    operator_scope_probe_command(database_container_id, args.probe_image),
                    env=probe_env, capture=True,
                ).stdout
            except ReplayCommandFailure as exc:
                try:
                    failure = json.loads(exc.stdout)
                except json.JSONDecodeError:
                    failure = {}
                if isinstance(failure, dict):
                    evidence["operator_scope_probe_failure"] = {
                        key: failure.get(key) for key in ("result", "stage", "error_type", "sqlstate")
                    }
                raise
            try:
                evidence["operator_scope_probe"] = parse_operator_scope_probe(probe_output)
            except ValueError as exc:
                evidence["operator_scope_probe_parse_failure"] = str(exc)
                raise
        evidence["result"] = "passed"
    except Exception as exc:  # evidence stores only safe failure metadata
        evidence["failed_stage"] = stage
        evidence["failure"] = type(exc).__name__
        if isinstance(exc, ReplayCommandFailure):
            command_diagnostic = safe_error_summary(exc.stderr + "\n" + exc.stdout)
            if command_diagnostic:
                evidence["command_diagnostic"] = command_diagnostic
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
                migration_diagnostic = safe_error_summary(diagnostic.stderr)
                if migration_diagnostic:
                    evidence["migration_diagnostic"] = migration_diagnostic
        print(f"schema replay failed during {stage} ({type(exc).__name__})", file=sys.stderr)
    finally:
        evidence["elapsed_seconds"] = round(time.monotonic() - started_at, 1)
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
