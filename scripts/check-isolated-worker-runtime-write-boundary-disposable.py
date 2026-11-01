#!/usr/bin/env python3
"""Verify migration 723 and runtime-role write denials on disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIGRATION = ROOT / "schemas/postgres/723_isolated_worker_runtime_write_boundaries.sql"
IMAGE = os.environ.get(
    "ISOLATED_WORKER_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
CLIENT_IMAGE = os.environ.get(
    "ISOLATED_WORKER_ACL_CLIENT_IMAGE", "kokonut-kernel-candidate-app:latest"
)
RELATIONS = (
    "event_handler_delivery",
    "event_handler_log",
    "data_freshness_check",
    "data_freshness_alert_state",
    "data_freshness_alert_history",
    "notification_outbox_attempt",
)
MUTATING_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def run(command: list[str], *, timeout: int = 90, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        redacted = [
            "POSTGRES_PASSWORD=<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
            for item in command
        ]
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed: {' '.join(redacted[:6])} …\n{details}")
    return result


def _connect(host: str, port: int, password: str):
    deadline = time.monotonic() + 60
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            return psycopg2.connect(
                host=host,
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=3,
            )
        except psycopg2.Error as exc:
            last_error = type(exc).__name__
            time.sleep(0.25)
    raise RuntimeError(f"disposable PostgreSQL did not become ready ({last_error})")


def _privileges(connection, role: str, relation: str) -> dict[str, bool]:
    privileges = ("SELECT", *MUTATING_PRIVILEGES)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT " + ", ".join("has_table_privilege(%s, %s, %s)" for _ in privileges),
            tuple(value for privilege in privileges for value in (role, f"public.{relation}", privilege)),
        )
        values = cursor.fetchone()
    return dict(zip(privileges, values, strict=True))


def _assert_runtime_read_only(connection) -> None:
    for relation in RELATIONS:
        observed = _privileges(connection, "kokonut_runtime", relation)
        if not observed["SELECT"] or any(observed[p] for p in MUTATING_PRIVILEGES):
            raise AssertionError(f"runtime table privileges are incorrect for {relation}: {observed}")
        for column in ("id", "marker", "updated_at"):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_column_privilege('kokonut_runtime', %s, %s, 'SELECT'), "
                    "has_column_privilege('kokonut_runtime', %s, %s, 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', %s, %s, 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', %s, %s, 'REFERENCES')",
                    (f"public.{relation}", column) * 4,
                )
                select_access, *column_writes = cursor.fetchone()
            if not select_access or any(column_writes):
                raise AssertionError(
                    f"runtime column privileges are incorrect for {relation}.{column}"
                )


def _fixture(connection) -> None:
    with connection.cursor() as cursor:
        for role in ("kokonut_runtime", "kokonut_directus_runtime", "kokonut_maintenance_probe"):
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(role))
            )
        for relation in RELATIONS:
            cursor.execute(
                sql.SQL(
                    "CREATE TABLE public.{} (id uuid PRIMARY KEY, marker text, "
                    "updated_at timestamptz NOT NULL DEFAULT now())"
                ).format(sql.Identifier(relation))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
                    "ON TABLE public.{} TO kokonut_runtime, kokonut_directus_runtime, "
                    "kokonut_maintenance_probe"
                ).format(sql.Identifier(relation))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT INSERT (id, marker, updated_at), "
                    "UPDATE (id, marker, updated_at), "
                    "REFERENCES (id, marker, updated_at) "
                    "ON TABLE public.{} TO kokonut_runtime"
                ).format(sql.Identifier(relation))
            )
        cursor.execute(
            "CREATE TABLE public.scheduled_task ("
            "id text PRIMARY KEY, name text NOT NULL, module_path text NOT NULL, "
            "command_args jsonb NOT NULL, cadence_minutes integer NOT NULL, "
            "is_enabled boolean NOT NULL, task_settings jsonb NOT NULL, "
            "updated_at timestamptz NOT NULL)"
        )
        cursor.execute(
            "INSERT INTO public.scheduled_task "
            "(id, name, module_path, command_args, cadence_minutes, is_enabled, task_settings, updated_at) "
            "VALUES "
            "('exact', 'data_freshness_check', 'services.ingestion.data_freshness', '[\"--check\"]', 60, true, '{\"owner\":\"ops\"}', '2020-01-01T00:00:00Z'), "
            "('custom-args', 'data_freshness_check', 'services.ingestion.data_freshness', '[\"--check\",\"--source\",\"weather\"]', 30, false, '{\"custom\":true}', '2020-01-01T00:00:00Z'), "
            "('wrong-name', 'other_task', 'services.ingestion.data_freshness', '[\"--check\"]', 15, true, '{}', '2020-01-01T00:00:00Z')"
        )
    connection.commit()


def _assert_schedule_scope(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, module_path, command_args, cadence_minutes, is_enabled, "
            "task_settings, updated_at FROM public.scheduled_task ORDER BY id"
        )
        rows = cursor.fetchall()
    by_id = {row[0]: row[1:] for row in rows}
    exact = by_id["exact"]
    if exact[:6] != (
        "data_freshness_check", "services.ingestion.freshness_worker", ["--check"],
        60, True, {"owner": "ops"},
    ) or exact[6].year <= 2020:
        raise AssertionError("the exact legacy freshness schedule was not safely migrated")
    custom = by_id["custom-args"]
    if custom[:6] != (
        "data_freshness_check", "services.ingestion.data_freshness",
        ["--check", "--source", "weather"], 30, False, {"custom": True},
    ) or custom[6].year != 2020:
        raise AssertionError("custom freshness schedule arguments or settings were changed")
    unrelated = by_id["wrong-name"]
    if unrelated[1] != "services.ingestion.data_freshness":
        raise AssertionError("an unrelated scheduled task was changed")


def check_database(host: str, port: int, password: str) -> dict[str, object]:
    connection = _connect(host, port, password)
    try:
        _fixture(connection)
        connection.autocommit = True

        migration = MIGRATION.read_text(encoding="utf-8")
        with connection.cursor() as cursor:
            cursor.execute(migration)
            cursor.execute(migration)
        _assert_runtime_read_only(connection)
        _assert_schedule_scope(connection)

        for relation in RELATIONS:
            directus = _privileges(connection, "kokonut_directus_runtime", relation)
            maintenance = _privileges(connection, "kokonut_maintenance_probe", relation)
            if any(not directus[p] or not maintenance[p] for p in ("SELECT", *MUTATING_PRIVILEGES)):
                raise AssertionError(f"migration changed non-runtime grants on {relation}")

        # Simulate a later compatibility regrant, then exercise the same scoped
        # policy helper called by runtime-role provisioning.
        with connection.cursor() as cursor:
            for relation in RELATIONS:
                cursor.execute(
                    sql.SQL(
                        "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
                        "ON TABLE public.{} TO kokonut_runtime"
                    ).format(sql.Identifier(relation))
                )
                cursor.execute(
                    sql.SQL(
                        "GRANT INSERT (id, marker, updated_at), "
                        "UPDATE (id, marker, updated_at), "
                        "REFERENCES (id, marker, updated_at) "
                        "ON TABLE public.{} TO kokonut_runtime"
                    ).format(sql.Identifier(relation))
                )
        from services.migration import runtime_role

        with connection.cursor() as cursor:
            applied = runtime_role._apply_scoped_write_boundary(
                cursor, sql.Identifier("kokonut_runtime")
            )
            runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
        if any(applied["relations"].get(relation) is not True for relation in RELATIONS):
            raise AssertionError("runtime provisioner did not restore every migration-723 policy")
        _assert_runtime_read_only(connection)
        return {
            "ok": True,
            "migration": MIGRATION.name,
            "migration_replay": "passed",
            "runtime_select": "preserved",
            "runtime_table_and_column_writes": "denied",
            "runtime_provisioner_reapplication": "passed",
            "directus_and_maintenance_grants": "preserved",
            "exact_schedule_migrated": True,
            "custom_and_unrelated_schedule_values": "preserved",
            "container_network": "internal-only",
            "host_binding": "none",
            "target": "disposable PostgreSQL only",
        }
    finally:
        connection.close()


def check_client() -> dict[str, object]:
    host = os.environ.get("ISOLATED_WORKER_ACL_DATABASE_HOST", "").strip()
    password = os.environ.get("ISOLATED_WORKER_ACL_DATABASE_PASSWORD", "")
    try:
        port = int(os.environ.get("ISOLATED_WORKER_ACL_DATABASE_PORT", "5432"))
    except ValueError as exc:
        raise RuntimeError("invalid disposable database port") from exc
    if not host or not password or not 1 <= port <= 65535:
        raise RuntimeError("disposable database client configuration is incomplete")
    return check_database(host, port, password)


def check() -> dict[str, object]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for the disposable PostgreSQL check")
    run([docker, "image", "inspect", CLIENT_IMAGE], timeout=30)
    network = f"kokonut-isolated-acl-net-{uuid.uuid4().hex[:10]}"
    container = f"kokonut-isolated-acl-{uuid.uuid4().hex[:10]}"
    password = secrets.token_urlsafe(32)
    network_created = False
    container_started = False
    try:
        run([docker, "network", "create", "--internal", network])
        network_created = True
        run([
            docker, "run", "--pull=never", "--detach", "--rm", "--name", container,
            "--network", network,
            "--env", f"POSTGRES_PASSWORD={password}", IMAGE,
        ])
        container_started = True
        client_result = run([
            docker, "run", "--pull=never", "--rm", "--network", network,
            "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
            "--workdir", "/workspace",
            "--env", "KOKONUT_DENY_SHARED_DATABASE=true",
            "--env", f"ISOLATED_WORKER_ACL_DATABASE_HOST={container}",
            "--env", "ISOLATED_WORKER_ACL_DATABASE_PORT=5432",
            "--env", f"ISOLATED_WORKER_ACL_DATABASE_PASSWORD={password}",
            CLIENT_IMAGE, "python3", "scripts/check-isolated-worker-runtime-write-boundary-disposable.py", "--client",
        ], timeout=180)
        try:
            evidence = json.loads(client_result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("disposable worker ACL client returned invalid evidence") from exc
        if evidence.get("ok") is not True:
            raise RuntimeError("disposable worker ACL client did not report success")
        return evidence
    finally:
        if container_started:
            run([docker, "rm", "--force", container], check=False)
        if network_created:
            run([docker, "network", "rm", network], check=False)


def main() -> int:
    if "--client" in sys.argv[1:]:
        result = check_client()
    else:
        result = check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"isolated-worker runtime ACL check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
