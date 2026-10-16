#!/usr/bin/env python3
"""Exercise tenant database-readiness SQL on isolated disposable PostgreSQL."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.migration.cli import _discover_files, _validate_sources  # noqa: E402

APP_IMAGE = "kokonut-kernel-candidate-app:latest"
DATABASE_IMAGE = "postgis/postgis:16-3.4"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/tenant-preflight-identity-postgres.json"
RUNTIME_ROLE = "tenant_preflight_fixture"
PREFLIGHT_ROLE = "kokonut_tenant_preflight"


def _docker_executable() -> str:
    executable = shutil.which("docker")
    if executable:
        return executable
    desktop_cli = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if desktop_cli.is_file():
        return str(desktop_cli)
    raise RuntimeError("Docker CLI is unavailable")


def _run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def _wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    consecutive_successes = 0
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                docker,
                "exec",
                container,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "postgres",
                "-d",
                "postgres",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            consecutive_successes += 1
            if consecutive_successes >= 4:
                return
        else:
            consecutive_successes = 0
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def _sql(docker: str, container: str, statement: str) -> None:
    _run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def _fixture_sql(sources: list[dict]) -> str:
    first, second = sources[:2]
    first_id = first["id"].replace("'", "''")
    first_checksum = first["checksum"].replace("'", "''")
    second_id = second["id"].replace("'", "''")
    changed_checksum = "0" * 64
    if second["checksum"] == changed_checksum:
        changed_checksum = "1" * 64
    second_id = second_id.replace("'", "''")

    return f"""
CREATE ROLE {RUNTIME_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE {PREFLIGHT_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION BYPASSRLS NOINHERIT;
CREATE TABLE public.schema_migration (
    migration_id text NOT NULL,
    checksum text NOT NULL,
    status text NOT NULL
);
INSERT INTO public.schema_migration (migration_id, checksum, status) VALUES
    ('{first_id}', '{first_checksum}', 'applied'),
    ('{second_id}', '{changed_checksum}', 'applied'),
    ('schema:999_preflight_removed.sql', 'removed-source', 'applied');
CREATE TABLE public.scheduled_task (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    module_path text NOT NULL,
    command_args jsonb NOT NULL,
    is_enabled boolean NOT NULL
);
INSERT INTO public.scheduled_task (name, module_path, command_args, is_enabled) VALUES
    ('synthetic-valid', 'services.metrics', '["--compute", "--all", "--location-id", "a0000000-0000-0000-0000-000000000901"]', true),
    ('synthetic-unbounded', 'services.export.dataset_refresh', '["--all"]', true),
    ('synthetic-invalid', 'services.events', '["--cleanup"]', true),
    ('disabled-task', 'services.metrics', '["--compute", "--all-locations"]', false);
CREATE TABLE public.preflight_no_rls_probe (id integer);
GRANT INSERT ON public.preflight_no_rls_probe TO {RUNTIME_ROLE};
CREATE TABLE public.preflight_owner_rls_probe (id integer);
ALTER TABLE public.preflight_owner_rls_probe OWNER TO {RUNTIME_ROLE};
ALTER TABLE public.preflight_owner_rls_probe ENABLE ROW LEVEL SECURITY;
CREATE TABLE public.location (id uuid);
ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.schema_migration, public.scheduled_task TO {RUNTIME_ROLE};
GRANT SELECT ON public.schema_migration, public.scheduled_task TO {PREFLIGHT_ROLE};
GRANT SELECT ON public.location TO {PREFLIGHT_ROLE};
GRANT CONNECT ON DATABASE postgres TO {RUNTIME_ROLE};
GRANT CONNECT ON DATABASE postgres TO {PREFLIGHT_ROLE};
GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE};
GRANT USAGE ON SCHEMA public TO {PREFLIGHT_ROLE};
"""


def _runner_source() -> str:
    return r"""
import json
from services.common.cli import get_connection
from services.migration.cli import _discover_files
from services.mobile.tenant_preflight import (
    _preflight_execution_identity,
    _migration_preflight,
    _runtime_role_preflight,
    _scheduled_task_preflight,
    get_preflight_connection,
)

with get_preflight_connection(connect_timeout=5) as preflight_connection:
    identity = _preflight_execution_identity(preflight_connection)
assert identity["status"] == "ready", identity
assert identity["direct_login"] is True and identity["transaction_read_only"] is True, identity
assert identity["dml_relation_count"] == 0 and identity["owned_relation_count"] == 0, identity
assert identity["role_membership_count"] == 0, identity
assert identity["bypasses_rls"] is True and identity["inventory_rls_enabled_relation_count"] == 1, identity

with get_connection(connect_timeout=5) as connection:
    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    migration = _migration_preflight(connection, True)
    runtime = _runtime_role_preflight(connection)
    schedules = _scheduled_task_preflight(connection)

assert migration["status"] == "drift_detected", migration
assert migration["applied_source_migration_count"] == 2, migration
assert migration["pending_source_migration_count"] == migration["source_migration_count"] - 2, migration
assert migration["checksum_drift_count"] == 1, migration
assert migration["applied_ledger_rows_without_source_count"] == 1, migration
assert runtime["status"] == "dml_with_rls_bypass_risk", runtime
assert runtime["superuser"] is False and runtime["bypasses_rls"] is False, runtime
assert runtime["rls_enabled_relation_count"] == 2, runtime
assert runtime["rls_forced_relation_count"] == 0, runtime
assert runtime["dml_relation_without_rls_count"] == 1, runtime
assert runtime["dml_relation_with_rls_bypass_risk_count"] == 2, runtime
assert schedules["enabled_task_count"] == 3, schedules
assert schedules["contract_valid_count"] == 2, schedules
assert schedules["contract_rejected_count"] == 1, schedules
assert schedules["known_unbounded_scope_task_count"] == 1, schedules
assert schedules["enabled_tasks_without_signed_tenant_context_count"] == 3, schedules
report = {
    "execution_identity": identity,
    "migration": migration,
    "runtime_role": runtime,
    "scheduled_tasks": schedules,
}
serialized = json.dumps(report)
for marker in (
    "tenant_preflight_fixture",
    "synthetic-valid",
    "synthetic-unbounded",
    "synthetic-invalid",
    "a0000000-0000-0000-0000-000000000901",
    "kokonut_tenant_preflight",
    "services.metrics",
    "services.events",
    "--all-locations",
    "--cleanup",
    *[source["id"] for source in _discover_files(include_seeds=False)],
    *[source["checksum"] for source in _discover_files(include_seeds=False)],
):
    assert marker not in serialized, "preflight output exposed a fixture identifier or checksum"
print(serialized)
""".strip()


def main() -> int:
    docker = _docker_executable()
    sources = _discover_files(include_seeds=False)
    _validate_sources(sources)
    if len(sources) < 2:
        raise RuntimeError("at least two current schema migrations are required")

    suffix = secrets.token_hex(5)
    network = f"tenant-preflight-check-{suffix}"
    database = f"tenant-preflight-db-{suffix}"
    container_started = network_started = False
    try:
        _run([docker, "image", "inspect", APP_IMAGE])
        _run([docker, "image", "inspect", DATABASE_IMAGE])
        _run([docker, "network", "create", "--internal", network])
        network_started = True
        _run(
            [
                docker,
                "run",
                "--detach",
                "--rm",
                "--network",
                network,
                "--name",
                database,
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                DATABASE_IMAGE,
            ]
        )
        container_started = True
        _wait_ready(docker, database)
        _sql(docker, database, _fixture_sql(sources))

        result = json.loads(
            _run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--network",
                    network,
                    "--volume",
                    f"{ROOT / 'services'}:/workspace/services:ro",
                    "--volume",
                    f"{ROOT / 'schemas'}:/workspace/schemas:ro",
                    "--volume",
                    f"{ROOT / 'VERSION'}:/workspace/VERSION:ro",
                    "--workdir",
                    "/workspace",
                    "--env",
                    f"PG_HOST={database}",
                    "--env",
                    "PG_PORT=5432",
                    "--env",
                    "PG_DB=postgres",
                    "--env",
                    f"PG_USER={RUNTIME_ROLE}",
                    "--env",
                    "KOKONUT_ENV=development",
                    "--env",
                    f"KOKONUT_RUNTIME_USER={RUNTIME_ROLE}",
                    "--env",
                    f"KOKONUT_TENANT_PREFLIGHT_DSN=postgresql://{PREFLIGHT_ROLE}@{database}:5432/postgres",
                    "--env",
                    "PYTHONDONTWRITEBYTECODE=1",
                    "--entrypoint",
                    "python3",
                    APP_IMAGE,
                    "-c",
                    _runner_source(),
                ]
            )
        )

        _run([docker, "rm", "--force", database])
        container_started = False
        _run([docker, "network", "rm", network])
        network_started = False

        report = {
            "result": "passed",
            "scope": "Actual PostgreSQL 16 system catalogs and synthetic fixture rows on an isolated internal Docker network.",
            "app_image": APP_IMAGE,
            "database_image": DATABASE_IMAGE,
            "published_ports": False,
            "network_egress": "blocked",
            "fixture_rows": "synthetic only",
            "checks": [
                "the direct kokonut_tenant_preflight login is transaction-read-only, has no role memberships, and has no public DML, ownership, or object-creation privileges",
                "the global-read identity bypasses RLS only while an inventory relation enables RLS, preventing filtered counts",
                "local migration sources compare with matched, drifted, pending, and removed-source ledger rows",
                "a non-elevated database role reports DML on an RLS-disabled table and an owned RLS table without FORCE RLS",
                "enabled scheduler arguments use the shared operation contracts and identify known unbounded scope",
                "task names, command arguments, role names, migration IDs, and checksums are absent from the output",
            ],
            "readiness": result,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "repository_secrets_read": False,
            "cleanup": {"database_container_removed": True, "internal_network_removed": True},
        }
        DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if container_started:
            subprocess.run([docker, "rm", "--force", database], capture_output=True, check=False)
        if network_started:
            subprocess.run([docker, "network", "rm", network], capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - keep disposable-check failures concise.
        print(f"TENANT PREFLIGHT POSTGRES CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
