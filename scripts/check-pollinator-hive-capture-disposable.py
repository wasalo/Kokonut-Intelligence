#!/usr/bin/env python3
"""Replay pollinator migrations and exercise managed-hive capture in disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATIONS = (
    ROOT / "schemas/postgres/155_pollinator_health.sql",
    ROOT / "schemas/postgres/602_pollinator_health_kernel_alignment.sql",
)
MIGRATION = ROOT / "schemas/postgres/622_location_pollinator_hive_capture.sql"
PLATFORM = os.environ.get("HIVE_CAPTURE_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-25-recovery/"
    f"cap-006-pollinator-hive-capture{OUTPUT_SUFFIX}-disposable.json"
)
IMAGE = os.environ.get("HIVE_CAPTURE_TEST_IMAGE", "postgres:16")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} …\n{details}")
    return result.stdout.strip()


def set_context(cursor, operator_id: str | None, location_id: str | None, actor_type="operator") -> None:
    cursor.execute("SELECT set_config('kokonut.actor_id', %s, true)", (operator_id or "",))
    cursor.execute("SELECT set_config('kokonut.location_id', %s, true)", (location_id or "",))
    cursor.execute("SELECT set_config('kokonut.actor_type', %s, true)", (actor_type or "",))


def expect_sqlstate(connection, statement: str, params: tuple, expected: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
    except psycopg2.Error as exc:
        if exc.pgcode != expected:
            raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
        connection.rollback()
        return
    raise AssertionError(f"expected SQLSTATE {expected}, statement succeeded")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-hive-capture-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    connection = None
    checks: list[str] = []
    operator_id, other_operator_id = str(uuid.uuid4()), str(uuid.uuid4())
    location_id, other_location_id = str(uuid.uuid4()), str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    try:
        command = [docker, "run"]
        if PLATFORM:
            command.extend(["--platform", PLATFORM])
        command.extend([
            "--detach", "--rm", "--name", container,
            "--env", f"POSTGRES_PASSWORD={password}",
            "--publish", "127.0.0.1::5432", IMAGE,
        ])
        run(command)
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = subprocess.run(
                [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
                text=True, capture_output=True, check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        architecture = run([docker, "exec", container, "uname", "-m"])
        mapping = json.loads(run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container]))
        port = int(mapping["5432/tcp"][0]["HostPort"])
        connection = psycopg2.connect(
            host="127.0.0.1", port=port, dbname="postgres", user="postgres",
            password=password, connect_timeout=5,
        )
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION pgcrypto")
            cursor.execute("CREATE ROLE kokonut_runtime NOLOGIN")
            cursor.execute("CREATE ROLE kokonut_directus_runtime NOLOGIN")
            cursor.execute("CREATE SCHEMA kokonut_security")
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)")
            cursor.execute("CREATE TABLE operator_identity (id UUID PRIMARY KEY)")
            cursor.execute("CREATE TABLE operator_scope_grant (operator_id UUID, location_id UUID, resource TEXT, action TEXT, revoked_at TIMESTAMPTZ)")
            cursor.execute(
                """CREATE FUNCTION kokonut_security.current_tenant_context()
                   RETURNS TABLE(actor_id UUID, location_id UUID, actor_type TEXT)
                   LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
                   AS $$ SELECT nullif(current_setting('kokonut.actor_id', true), '')::uuid,
                                    nullif(current_setting('kokonut.location_id', true), '')::uuid,
                                    nullif(current_setting('kokonut.actor_type', true), '') $$"""
            )
            cursor.execute(
                """CREATE FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
                   RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER
                   SET search_path = pg_catalog
                   AS $$ SELECT EXISTS (
                       SELECT 1 FROM public.operator_scope_grant AS grant_row
                        WHERE grant_row.operator_id = $1 AND grant_row.resource = $2
                          AND grant_row.action = $3 AND grant_row.location_id = $4
                          AND grant_row.revoked_at IS NULL
                   ) $$"""
            )
            cursor.execute("GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON location TO kokonut_runtime, kokonut_directus_runtime")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text())
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON hive_record TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute(MIGRATION.read_text())
            cursor.execute(MIGRATION.read_text())
            cursor.execute(
                "INSERT INTO location (id, name) VALUES (%s, 'Synthetic'), (%s, 'Other')",
                (location_id, other_location_id),
            )
            cursor.execute("INSERT INTO operator_identity (id) VALUES (%s), (%s)", (operator_id, other_operator_id))
            cursor.execute(
                "INSERT INTO operator_scope_grant (operator_id, location_id, resource, action) "
                "VALUES (%s, %s, 'pollinator_health', 'create')",
                (operator_id, location_id),
            )
        checks.append("migrations 155/602 and migration 622 apply; migration 622 replays")

        connection.autocommit = False
        call = """SELECT kokonut_security.create_location_pollinator_hive(
            %s::uuid, %s::uuid, %s::text, %s::text, %s::text,
            %s::smallint, %s::text, %s::integer, %s::smallint, %s::text
        )"""
        params = (
            location_id, request_id, "KOK-TEST-001", "langstroth", "moderate",
            None, "present", 10, 2024, "Synthetic managed-hive inventory",
        )

        def create(args=params, *, actor=operator_id, scope=location_id, actor_type="operator"):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE kokonut_runtime")
                    set_context(cursor, actor, scope, actor_type)
                    cursor.execute(call, args)
                    result = cursor.fetchone()[0]
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

        def expect_capture_error(args, expected, *, actor=operator_id, scope=location_id, actor_type="operator"):
            try:
                create(args, actor=actor, scope=scope, actor_type=actor_type)
            except psycopg2.Error as exc:
                if exc.pgcode != expected:
                    raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
                return
            raise AssertionError(f"expected SQLSTATE {expected}, capture succeeded")

        first = create()
        if first["status"] != "active" or first["replayed"] is not False:
            raise AssertionError("new hive inventory was not returned as active")
        hive_record_id = first["hive_record_id"]
        checks.append("exact signed location create grant creates an active attributed hive inventory entry")

        replay = create()
        if replay["hive_record_id"] != hive_record_id or replay["replayed"] is not True:
            raise AssertionError("same request retry did not return the original hive")
        changed = list(params)
        changed[3] = "top-bar"
        expect_capture_error(tuple(changed), "23505")
        duplicate_id = list(params)
        duplicate_id[1] = str(uuid.uuid4())
        expect_capture_error(tuple(duplicate_id), "23505")
        checks.append("exact retries are idempotent; changed-input reuse and duplicate location hive IDs are rejected")

        expect_capture_error(params, "42501", actor=other_operator_id)
        expect_capture_error(tuple([other_location_id, *params[1:]]), "42501", scope=other_location_id)
        expect_capture_error(params, "42501", scope=other_location_id)
        expect_capture_error(params, "42501", actor_type="worker")
        checks.append("ungranted actors, mismatched locations, and non-operator context are denied")

        invalid = list(params)
        invalid[6] = "queen_unknown"
        expect_capture_error(tuple(invalid), "22023")
        invalid = list(params)
        invalid[7] = 501
        expect_capture_error(tuple(invalid), "22023")
        invalid = list(params)
        invalid[8] = datetime.now(timezone.utc).year + 1
        expect_capture_error(tuple(invalid), "22023")
        checks.append("invalid queen status, frame count, and future queen year are rejected")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT location_id, hive_id, hive_type, colony_strength, colony_strength_score, "
                "queen_status, frame_count, queen_year, status, created_by_operator_id "
                "FROM hive_record WHERE id = %s",
                (hive_record_id,),
            )
            stored = cursor.fetchone()
        if stored != (
            location_id, "KOK-TEST-001", "langstroth", "moderate", None,
            "present", 10, 2024, "active", operator_id,
        ):
            raise AssertionError(f"stored hive attribution/domain-state mismatch: {stored!r}")
        checks.append("stored operational state and creator attribution match the submitted inventory")

        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
            connection.commit()
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            expect_sqlstate(
                connection,
                "INSERT INTO hive_record (location_id, hive_id) VALUES (%s, 'UNAUTHORIZED')",
                (location_id,),
                "42501",
            )
            expect_sqlstate(connection, "SELECT * FROM pollinator_hive_capture_receipt", (), "42501")
        checks.append("runtime and Directus cannot directly insert hives or read private receipts")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = 'kokonut_pollinator_hive_writer'"
            )
            props = cursor.fetchone()
            cursor.execute(
                "SELECT has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_pollinator_hive(uuid,uuid,text,text,text,smallint,text,integer,smallint,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_pollinator_hive(uuid,uuid,text,text,text,smallint,text,integer,smallint,text)', 'EXECUTE')"
            )
            grants = cursor.fetchone()
            cursor.execute(
                "SELECT count(*), count(*) FILTER (WHERE status <> 'active') FROM hive_record"
            )
            rows = cursor.fetchone()
            cursor.execute("SELECT count(*) FROM pollinator_hive_capture_receipt")
            receipts = cursor.fetchone()[0]
        if props != (False, False, False) or grants != (True, False):
            raise AssertionError(f"unexpected writer role or function grants: {props!r}/{grants!r}")
        if rows != (1, 0) or receipts != 1:
            raise AssertionError(f"unexpected hive/receipt counts: {rows!r}/{receipts!r}")
        checks.append("dedicated owner is no-login/no-inherit/no-bypass and only Gateway can execute capture")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "architecture": architecture,
            "migrations": [path.name for path in (*MIGRATIONS, MIGRATION)],
            "migration_622_replayed": True,
            "checks": checks,
            "assertions_passed": len(checks),
            "candidate_database_touched": False,
            "legacy_database_touched": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - expose SQL acceptance failures.
        print(f"pollinator hive capture check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
