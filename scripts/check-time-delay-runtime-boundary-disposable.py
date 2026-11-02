#!/usr/bin/env python3
"""Verify migration 726 and time-delay runtime ACLs in disposable PostgreSQL."""

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

MIGRATION = ROOT / "schemas/postgres/726_runtime_time_delay_reference_read_only.sql"
SEED = ROOT / "schemas/seeds/083_time_delays.sql"
IMAGE = os.environ.get(
    "TIME_DELAY_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
CLIENT_IMAGE = os.environ.get(
    "TIME_DELAY_ACL_CLIENT_IMAGE", "kokonut-kernel-candidate-app:latest"
)
MUTATING_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def run(
    command: list[str], *, timeout: int = 90, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:5])} …\n{details}"
        )
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


def _fixture(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE ROLE kokonut NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS"
        )
        cursor.execute(
            "CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
        cursor.execute(
            "CREATE TABLE public.time_delay ("
            "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
            "action_type varchar(100) NOT NULL, effect_type varchar(100) NOT NULL, "
            "expected_delay_hours integer NOT NULL, min_delay_hours integer, "
            "max_delay_hours integer, domain varchar(50) NOT NULL DEFAULT 'farm', "
            "description text, is_enabled boolean NOT NULL DEFAULT true, "
            "created_at timestamptz NOT NULL DEFAULT now(), "
            "UNIQUE (action_type, effect_type))"
        )
        cursor.execute("ALTER TABLE public.time_delay OWNER TO kokonut")
        cursor.execute(
            "GRANT USAGE ON SCHEMA public TO kokonut_directus_runtime"
        )
        cursor.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            "ON TABLE public.time_delay TO kokonut_directus_runtime"
        )
    connection.commit()


def _compatibility_grants(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS")
        cursor.execute("GRANT USAGE ON SCHEMA public TO kokonut_runtime")
        cursor.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            "ON TABLE public.time_delay TO kokonut_runtime"
        )
        # Standalone grants survive table-level REVOKE unless explicitly removed.
        cursor.execute(
            "GRANT INSERT (action_type), UPDATE (expected_delay_hours), "
            "REFERENCES (id) ON TABLE public.time_delay TO kokonut_runtime"
        )
    connection.commit()


def _assert_read_only(connection, *, context: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege('kokonut_runtime', 'public.time_delay', 'SELECT'), "
            + ", ".join(
                "has_table_privilege('kokonut_runtime', 'public.time_delay', %s)"
                for _ in MUTATING_PRIVILEGES
            ),
            MUTATING_PRIVILEGES,
        )
        privileges = cursor.fetchone()
    if privileges != (True, *(False for _ in MUTATING_PRIVILEGES)):
        raise AssertionError(f"runtime table privileges incorrect after {context}: {privileges}")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid = "
            "'public.time_delay'::regclass AND attnum > 0 AND NOT attisdropped"
        )
        columns = [row[0] for row in cursor.fetchall()]
        for column in columns:
            cursor.execute(
                "SELECT has_column_privilege('kokonut_runtime', %s, %s, 'INSERT'), "
                "has_column_privilege('kokonut_runtime', %s, %s, 'UPDATE'), "
                "has_column_privilege('kokonut_runtime', %s, %s, 'REFERENCES')",
                ("public.time_delay", column) * 3,
            )
            if cursor.fetchone() != (False, False, False):
                raise AssertionError(
                    f"runtime column DML remains after {context}: time_delay.{column}"
                )

    _assert_runtime_reads_and_writes(connection)


def _assert_runtime_reads_and_writes(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE kokonut_runtime")
        cursor.execute("SELECT count(*) FROM public.time_delay")
        if cursor.fetchone()[0] < 1:
            raise AssertionError("runtime SELECT did not return reference rows")

        denied_statements = (
            (
                "INSERT INTO public.time_delay "
                "(action_type,effect_type,expected_delay_hours) VALUES ('blocked','insert',1)"
            ),
            ("UPDATE public.time_delay SET expected_delay_hours = 1"),
            ("DELETE FROM public.time_delay"),
        )
        for statement in denied_statements:
            try:
                cursor.execute(statement)
            except psycopg2.errors.InsufficientPrivilege:
                connection.rollback()
                with connection.cursor() as reset_cursor:
                    reset_cursor.execute("RESET ROLE")
                    reset_cursor.execute("SET ROLE kokonut_runtime")
            else:
                raise AssertionError(f"runtime write unexpectedly succeeded: {statement.split()[0]}")
        cursor.execute("RESET ROLE")
    connection.commit()


def _assert_directus_and_owner_grants(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege('kokonut_directus_runtime', 'public.time_delay', 'SELECT'), "
            "has_table_privilege('kokonut_directus_runtime', 'public.time_delay', 'INSERT'), "
            "has_table_privilege('kokonut_directus_runtime', 'public.time_delay', 'UPDATE'), "
            "has_table_privilege('kokonut_directus_runtime', 'public.time_delay', 'DELETE'), "
            "has_table_privilege('kokonut', 'public.time_delay', 'INSERT'), "
            "has_table_privilege('kokonut', 'public.time_delay', 'UPDATE'), "
            "has_table_privilege('kokonut', 'public.time_delay', 'DELETE')"
        )
        if cursor.fetchone() != (True, True, True, True, True, True, True):
            raise AssertionError("migration changed Directus or owner maintenance grants")


def _apply_migration(connection, migration: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(migration)
    connection.commit()


def check_database(host: str, port: int, password: str) -> dict[str, object]:
    connection = _connect(host, port, password)
    try:
        connection.autocommit = True
        _fixture(connection)

        migration = MIGRATION.read_text(encoding="utf-8")
        _apply_migration(connection, migration)
        _apply_migration(connection, migration)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime')"
            )
            if cursor.fetchone()[0]:
                raise AssertionError("role-absent migration unexpectedly created runtime role")

        _compatibility_grants(connection)
        _apply_migration(connection, migration)
        _apply_migration(connection, migration)

        # Apply the curated seed twice as its owner, then update an existing key
        # to demonstrate maintenance upsert rights remain intact.
        seed = SEED.read_text(encoding="utf-8")
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut")
            cursor.execute(seed)
            cursor.execute(seed)
            cursor.execute(
                "INSERT INTO public.time_delay "
                "(action_type, effect_type, expected_delay_hours) "
                "VALUES ('cover_crop_planting', 'soil_carbon_increase', 999) "
                "ON CONFLICT (action_type, effect_type) DO UPDATE "
                "SET expected_delay_hours = EXCLUDED.expected_delay_hours"
            )
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT count(*), min(expected_delay_hours) FROM public.time_delay"
            )
            seed_count, minimum_delay = cursor.fetchone()
        if seed_count != 20 or minimum_delay != 6:
            raise AssertionError("owner seed replay/upsert produced unexpected reference rows")
        _assert_read_only(connection, context="migration apply, replay, and seed load")
        _assert_directus_and_owner_grants(connection)

        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_directus_runtime")
            cursor.execute(
                "UPDATE public.time_delay SET description = 'Directus grant retained' "
                "WHERE action_type = 'cover_crop_planting'"
            )
            cursor.execute("RESET ROLE")
        _assert_directus_and_owner_grants(connection)

        # The provisioner applies the source-declared policy after broad legacy
        # grants. Reopen both table and column privileges to exercise that path.
        _compatibility_regrant(connection)
        from services.migration import runtime_role

        with connection.cursor() as cursor:
            applied = runtime_role._apply_scoped_write_boundary(
                cursor, sql.Identifier("kokonut_runtime")
            )
            runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
        if applied["relations"].get("time_delay") is not True:
            raise AssertionError("runtime provisioner did not apply time_delay denial")
        _assert_read_only(connection, context="runtime provisioner reapplication")
        _assert_directus_and_owner_grants(connection)

        return {
            "ok": True,
            "migration": MIGRATION.name,
            "migration_apply_and_replay": "passed",
            "runtime_select": "preserved",
            "runtime_table_and_column_writes": "denied",
            "runtime_provisioner_reapplication": "passed",
            "owner_seed_replay_and_upsert": "passed",
            "directus_grants_unchanged": "passed",
            "container_network": "internal-only",
            "host_binding": "none",
            "target": "disposable PostgreSQL only",
        }
    finally:
        connection.close()


def _compatibility_regrant(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            "ON TABLE public.time_delay TO kokonut_runtime"
        )
        cursor.execute(
            "GRANT INSERT (action_type), UPDATE (expected_delay_hours), "
            "REFERENCES (id) ON TABLE public.time_delay TO kokonut_runtime"
        )


def check_client() -> dict[str, object]:
    host = os.environ.get("TIME_DELAY_ACL_DATABASE_HOST", "").strip()
    password = os.environ.get("TIME_DELAY_ACL_DATABASE_PASSWORD", "")
    try:
        port = int(os.environ.get("TIME_DELAY_ACL_DATABASE_PORT", "5432"))
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

    network = f"kokonut-time-delay-acl-net-{uuid.uuid4().hex[:10]}"
    container = f"kokonut-time-delay-acl-{uuid.uuid4().hex[:10]}"
    password = secrets.token_urlsafe(32)
    network_created = False
    container_started = False
    try:
        run([docker, "network", "create", "--internal", network])
        network_created = True
        run(
            [
                docker,
                "run",
                "--pull=never",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                network,
                "--network-alias",
                "database",
                "--env",
                f"POSTGRES_PASSWORD={password}",
                IMAGE,
            ]
        )
        container_started = True
        client_result = run(
            [
                docker,
                "run",
                "--pull=never",
                "--rm",
                "--network",
                network,
                "--mount",
                f"type=bind,source={ROOT},target=/workspace,readonly",
                "--workdir",
                "/workspace",
                "--env",
                f"TIME_DELAY_ACL_DATABASE_HOST={container}",
                "--env",
                "TIME_DELAY_ACL_DATABASE_PORT=5432",
                "--env",
                f"TIME_DELAY_ACL_DATABASE_PASSWORD={password}",
                CLIENT_IMAGE,
                "python3",
                "scripts/check-time-delay-runtime-boundary-disposable.py",
                "--client",
            ],
            timeout=180,
        )
        try:
            evidence = json.loads(client_result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("disposable PostgreSQL client returned invalid evidence") from exc
        if evidence.get("ok") is not True:
            raise RuntimeError("disposable PostgreSQL client did not report success")
        return evidence
    finally:
        if container_started:
            run([docker, "rm", "--force", container], check=False)
        if network_created:
            run([docker, "network", "rm", network], check=False)


def main() -> int:
    result = check_client() if "--client" in sys.argv[1:] else check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"time_delay runtime ACL check failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
