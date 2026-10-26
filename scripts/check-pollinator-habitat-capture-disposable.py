#!/usr/bin/env python3
"""Replay pollinator migrations and exercise habitat capture in disposable PostgreSQL 16."""

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
from decimal import Decimal
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATIONS = (
    ROOT / "schemas/postgres/155_pollinator_health.sql",
    ROOT / "schemas/postgres/602_pollinator_health_kernel_alignment.sql",
    ROOT / "schemas/postgres/619_location_pollinator_observation_capture.sql",
    ROOT / "schemas/postgres/620_location_pesticide_impact_capture.sql",
)
MIGRATION = ROOT / "schemas/postgres/621_location_pollinator_habitat_capture.sql"
PLATFORM = os.environ.get("HABITAT_CAPTURE_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-25-recovery/"
    f"cap-006-pollinator-habitat-capture{OUTPUT_SUFFIX}-disposable.json"
)
IMAGE = os.environ.get("HABITAT_CAPTURE_TEST_IMAGE", "postgres:16")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} …\n{details}")
    return result.stdout.strip()


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


def set_context(cursor, operator_id: str | None, location_id: str | None, actor_type="operator") -> None:
    cursor.execute("SELECT set_config('kokonut.actor_id', %s, true)", (operator_id or "",))
    cursor.execute("SELECT set_config('kokonut.location_id', %s, true)", (location_id or "",))
    cursor.execute("SELECT set_config('kokonut.actor_type', %s, true)", (actor_type or "",))


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-habitat-capture-{os.getpid()}-{secrets.token_hex(3)}"
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
            cursor.execute("CREATE TABLE farm (id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id), name TEXT NOT NULL)")
            cursor.execute("CREATE TABLE plot (id UUID PRIMARY KEY, farm_id UUID NOT NULL REFERENCES farm(id), name TEXT NOT NULL)")
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
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON location, farm, plot TO kokonut_runtime, kokonut_directus_runtime")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text())
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON pollinator_habitat TO kokonut_runtime, kokonut_directus_runtime")
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
        checks.append("migration 620 prerequisite applies after pollinator migrations 155/602/619")

        checks.append("migration 621 applies and replays after pollinator migrations 155/602/619/620")

        connection.autocommit = False
        call = """SELECT kokonut_security.create_location_pollinator_habitat(
            %s::uuid, %s::uuid, %s::text, %s::text, %s::numeric,
            %s::jsonb, %s::smallint, %s::smallint, %s::boolean, %s::text, %s::text
        )"""
        params = (
            location_id, request_id, "Synthetic native strip", "wildflower_strip", 125.5,
            '["Native clover", "Buttonwood"]', 3, 9, True,
            "Undisturbed ground edge", "Synthetic habitat inventory",
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

        def expect_capture_error(args, expected, *, actor=operator_id, scope=location_id):
            try:
                create(args, actor=actor, scope=scope)
            except psycopg2.Error as exc:
                if exc.pgcode != expected:
                    raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
                return
            raise AssertionError(f"expected SQLSTATE {expected}, capture succeeded")

        first = create()
        if first["status"] != "active" or first["replayed"] is not False:
            raise AssertionError("new self-reported habitat was not returned as active inventory")
        habitat_id = first["habitat_id"]
        checks.append("exact signed location create grant creates self-reported active habitat inventory")

        replay = create()
        if replay["habitat_id"] != habitat_id or replay["replayed"] is not True:
            raise AssertionError("same request retry did not return the original habitat")
        changed = list(params)
        changed[3] = "hedgerow"
        expect_capture_error(tuple(changed), "23505")
        checks.append("same-input retries are idempotent and changed-input reuse is rejected")

        expect_capture_error(params, "42501", actor=other_operator_id)
        expect_capture_error(tuple([other_location_id, *params[1:]]), "42501", scope=other_location_id)
        expect_capture_error(params, "42501", scope=other_location_id)
        checks.append("ungranted actors, wrong requested locations, and mismatched signed context are denied")

        invalid = list(params)
        invalid[1] = str(uuid.uuid4())
        invalid[4] = -1
        expect_capture_error(tuple(invalid), "22023")
        invalid = list(params)
        invalid[1] = str(uuid.uuid4())
        invalid[6] = 13
        expect_capture_error(tuple(invalid), "22023")
        checks.append("out-of-bounds area and bloom-month values are rejected")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT status, created_by_operator_id, habitat_type, area_m2, plant_species "
                "FROM pollinator_habitat WHERE id = %s",
                (habitat_id,),
            )
            stored = cursor.fetchone()
        if stored != (
            "active", operator_id, "wildflower_strip", Decimal("125.50"),
            ["Native clover", "Buttonwood"],
        ):
            raise AssertionError(f"stored habitat attribution/domain-state mismatch: {stored!r}")
        checks.append("operator attribution persists; active remains the descriptive inventory state")

        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            for statement, arguments in (
                (
                    "INSERT INTO pollinator_habitat (location_id, habitat_name, habitat_type) "
                    "VALUES (%s, 'Unauthorized', 'other')",
                    (location_id,),
                ),
                ("UPDATE pollinator_habitat SET status = 'inactive' WHERE id = %s", (habitat_id,)),
                ("DELETE FROM pollinator_habitat WHERE id = %s", (habitat_id,)),
            ):
                expect_sqlstate(connection, statement, arguments, "42501")
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            expect_sqlstate(connection, "SELECT * FROM pollinator_habitat_capture_receipt", (), "42501")
        checks.append("runtime and Directus cannot insert, update, delete, or read private receipts")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = 'kokonut_pollinator_habitat_writer'"
            )
            props = cursor.fetchone()
        if props != (False, False, False):
            raise AssertionError(f"habitat writer owner is not bounded: {props!r}")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_pollinator_habitat(uuid,uuid,text,text,numeric,jsonb,smallint,smallint,boolean,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_pollinator_habitat(uuid,uuid,text,text,numeric,jsonb,smallint,smallint,boolean,text,text)', 'EXECUTE')"
            )
            function_grants = cursor.fetchone()
        if function_grants != (True, False):
            raise AssertionError(f"unexpected Gateway/Directus function grants: {function_grants!r}")
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_directus_runtime")
        connection.commit()
        expect_sqlstate(connection, call, params, "42501")
        checks.append("dedicated writer is no-login/no-inherit/no-bypass and Directus cannot execute the capture function")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT count(*), count(*) FILTER (WHERE status <> 'active') "
                "FROM pollinator_habitat"
            )
            rows, non_active = cursor.fetchone()
            cursor.execute("SELECT count(*) FROM pollinator_habitat_capture_receipt")
            receipts = cursor.fetchone()[0]
        if (rows, non_active, receipts) != (1, 0, 1):
            raise AssertionError(f"unexpected row/domain-state/receipt counts: {rows}/{non_active}/{receipts}")
        checks.append("one private receipt and one active self-reported inventory entry remain after retries and denials")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "architecture": architecture,
            "migrations": [path.name for path in (*MIGRATIONS, MIGRATION)],
            "migration_621_replayed": True,
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
        print(f"pollinator habitat capture check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
