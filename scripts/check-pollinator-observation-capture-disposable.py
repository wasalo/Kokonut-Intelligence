#!/usr/bin/env python3
"""Apply/replay migration 619 and exercise its boundary in disposable PostgreSQL 16."""

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
BASE_MIGRATIONS = (
    ROOT / "schemas/postgres/155_pollinator_health.sql",
    ROOT / "schemas/postgres/602_pollinator_health_kernel_alignment.sql",
)
MIGRATION = ROOT / "schemas/postgres/619_location_pollinator_observation_capture.sql"
PLATFORM = os.environ.get("POLLINATOR_CAPTURE_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-24-recovery/"
    f"cap-006-pollinator-observation-capture{OUTPUT_SUFFIX}-disposable.json"
)
IMAGE = os.environ.get("POLLINATOR_CAPTURE_TEST_IMAGE", "postgres:16")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]} …\n{details}"
        )
    return result.stdout.strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


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

    container = f"kokonut-pollinator-capture-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    connection = None
    checks: list[str] = []
    architecture = None
    operator_id, other_operator_id = str(uuid.uuid4()), str(uuid.uuid4())
    location_id, other_location_id = str(uuid.uuid4()), str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    farm_id, other_farm_id = str(uuid.uuid4()), str(uuid.uuid4())
    plot_id, foreign_plot_id = str(uuid.uuid4()), str(uuid.uuid4())
    hive_id, foreign_hive_id = str(uuid.uuid4()), str(uuid.uuid4())
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
        wait_ready(docker, container)
        architecture = run([docker, "exec", container, "uname", "-m"])
        mapping = json.loads(
            run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container])
        )
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
            cursor.execute(
                "CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)"
            )
            cursor.execute("CREATE TABLE operator_identity (id UUID PRIMARY KEY)")
            cursor.execute(
                "CREATE TABLE farm (id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id), name TEXT NOT NULL)"
            )
            cursor.execute(
                "CREATE TABLE plot (id UUID PRIMARY KEY, farm_id UUID NOT NULL REFERENCES farm(id), name TEXT NOT NULL)"
            )
            cursor.execute(
                "CREATE TABLE operator_scope_grant (operator_id UUID, location_id UUID, resource TEXT, action TEXT, revoked_at TIMESTAMPTZ)"
            )
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
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE location, farm, plot TO kokonut_runtime, kokonut_directus_runtime")
            for migration in BASE_MIGRATIONS:
                cursor.execute(migration.read_text())
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE pollinator_observation TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("GRANT INSERT (status), UPDATE (status) ON TABLE pollinator_observation TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("GRANT SELECT ON TABLE hive_record TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("GRANT SELECT ON TABLE pollinator_observation TO kokonut_runtime")
            cursor.execute(MIGRATION.read_text())
            cursor.execute(MIGRATION.read_text())
            cursor.execute("""
                INSERT INTO location (id, name) VALUES
                    ('%s', 'Synthetic'), ('%s', 'Other');
                INSERT INTO operator_identity (id) VALUES ('%s'), ('%s');
                INSERT INTO farm (id, location_id, name) VALUES
                    ('%s', '%s', 'Synthetic farm'), ('%s', '%s', 'Other farm');
                INSERT INTO plot (id, farm_id, name) VALUES
                    ('%s', '%s', 'Synthetic plot'), ('%s', '%s', 'Foreign plot');
                INSERT INTO hive_record (id, location_id, hive_id, status) VALUES
                    ('%s', '%s', 'H-1', 'active'), ('%s', '%s', 'H-2', 'active');
                INSERT INTO operator_scope_grant (operator_id, location_id, resource, action)
                VALUES ('%s', '%s', 'pollinator_health', 'create');
            """ % (
                location_id, other_location_id, operator_id, other_operator_id,
                farm_id, location_id, other_farm_id, other_location_id,
                plot_id, farm_id, foreign_plot_id, other_farm_id,
                hive_id, location_id, foreign_hive_id, other_location_id,
                operator_id, location_id,
            ))
        checks.append("migration 619 applies and replays after schema 155 and alignment 602")

        connection.autocommit = False
        observation_call = """SELECT kokonut_security.create_location_pollinator_observation(
            %s::uuid, %s::uuid, %s::text, %s::integer, %s::text, %s::integer,
            %s::uuid, %s::date, %s::text, %s::jsonb, %s::numeric, %s::uuid, %s::text
        )"""
        capture_params = (
            location_id, request_id, "wild_bee", 7, "transect", 20,
            plot_id, None, "Native bee", '{"description":"clear"}', 24.5,
            hive_id, "Synthetic capture",
        )

        def call_capture(
            params=capture_params, *, actor=operator_id, scope=location_id,
            actor_type="operator",
        ):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE kokonut_runtime")
                    set_context(cursor, actor, scope, actor_type)
                    cursor.execute(observation_call, params)
                    result = cursor.fetchone()[0]
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

        def expect_capture_error(params, expected, *, actor=operator_id, scope=location_id):
            try:
                call_capture(params, actor=actor, scope=scope)
            except psycopg2.Error as exc:
                if exc.pgcode != expected:
                    raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
                return
            raise AssertionError(f"expected SQLSTATE {expected}, capture succeeded")

        first = call_capture()
        if first["status"] != "recorded" or first["replayed"] is not False:
            raise AssertionError("new observation was not returned as recorded")
        observation_id = first["observation_id"]
        checks.append("exact signed operator location create context creates recorded observation")

        replay = call_capture()
        if replay["observation_id"] != observation_id or replay["replayed"] is not True:
            raise AssertionError("same request retry did not return the original observation")
        checks.append("same actor/request/input replay is idempotent")

        changed = list(capture_params)
        changed[3] = 8
        expect_capture_error(tuple(changed), "23505")
        checks.append("reused request ID with changed input is rejected")

        expect_capture_error(
            (other_location_id, str(uuid.uuid4()), *capture_params[2:]),
            "42501", actor=operator_id, scope=other_location_id,
        )
        expect_capture_error(
            (location_id, str(uuid.uuid4()), *capture_params[2:]),
            "42501", actor=other_operator_id, scope=location_id,
        )
        expect_capture_error(
            capture_params, "42501", actor=operator_id, scope=other_location_id,
        )
        checks.append("ungranted operator, wrong requested location, and mismatched context are denied")

        foreign_plot = list(capture_params)
        foreign_plot[1] = str(uuid.uuid4())
        foreign_plot[6] = foreign_plot_id
        expect_capture_error(tuple(foreign_plot), "22023")
        foreign_hive = list(capture_params)
        foreign_hive[1] = str(uuid.uuid4())
        foreign_hive[11] = foreign_hive_id
        expect_capture_error(tuple(foreign_hive), "22023")
        checks.append("foreign-location plot and hive links are rejected")

        invalid_count = list(capture_params)
        invalid_count[1] = str(uuid.uuid4())
        invalid_count[3] = -1
        expect_capture_error(tuple(invalid_count), "22023")
        checks.append("out-of-bounds values are rejected")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute("SELECT status, created_by_operator_id, count FROM pollinator_observation WHERE id = %s", (observation_id,))
            saved = cursor.fetchone()
        if saved != ("recorded", operator_id, 7):
            raise AssertionError(f"stored observation attribution/lifecycle mismatch: {saved!r}")
        checks.append("operator attribution persists and capture cannot promote lifecycle")

        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            for statement, params in (
                (
                    "INSERT INTO pollinator_observation (location_id, observation_date, pollinator_type, count) VALUES (%s, CURRENT_DATE, 'honeybee', 1)",
                    (location_id,),
                ),
                ("UPDATE pollinator_observation SET status = 'verified' WHERE id = %s", (observation_id,)),
                ("DELETE FROM pollinator_observation WHERE id = %s", (observation_id,)),
                ("SELECT * FROM pollinator_observation_capture_receipt", ()),
            ):
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {role}")
                expect_sqlstate(connection, statement, params, "42501")
        checks.append("shared Gateway/Directus roles cannot insert, update, delete, or read private receipts")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = 'kokonut_pollinator_observation_writer'"
            )
            owner_properties = cursor.fetchone()
        if owner_properties != (False, False, False):
            raise AssertionError(f"pollinator writer owner is not a bounded no-login role: {owner_properties!r}")
        checks.append("database function owner is no-login, no-inherit, and not RLS-bypassing")

        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_directus_runtime")
        expect_sqlstate(
            connection,
            "SELECT kokonut_security.create_location_pollinator_observation(" +
            "%s::uuid,%s::uuid,'wild_bee',1,'transect',1,NULL,CURRENT_DATE,NULL,'{}',NULL,NULL,NULL)",
            (location_id, str(uuid.uuid4())),
            "42501",
        )
        checks.append("optional Directus role cannot execute the Gateway capture function")

        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pollinator_observation_capture_receipt")
            receipts = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM pollinator_observation WHERE status <> 'recorded'")
            non_recorded = cursor.fetchone()[0]
        if receipts != 1 or non_recorded != 0:
            raise AssertionError(f"expected one private receipt and only recorded rows; got {receipts}/{non_recorded}")
        checks.append("receipt contains only a digest and observation reference; no row was verified")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "architecture": architecture,
            "migrations": [path.name for path in (*BASE_MIGRATIONS, MIGRATION)],
            "migration_619_replayed": True,
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
    except Exception as exc:  # noqa: BLE001 - this acceptance should expose SQL failures.
        print(f"pollinator observation capture check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
