#!/usr/bin/env python3
"""Replay pollinator migrations and verify managed-hive lifecycle writes in disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIGRATIONS = tuple(
    ROOT / "schemas/postgres" / name
    for name in (
        "155_pollinator_health.sql",
        "602_pollinator_health_kernel_alignment.sql",
        "619_location_pollinator_observation_capture.sql",
        "620_location_pesticide_impact_capture.sql",
        "621_location_pollinator_habitat_capture.sql",
        "622_location_pollinator_hive_capture.sql",
        "623_location_pollinator_hive_inspection_capture.sql",
    )
)
HABITAT_MIGRATION = ROOT / "schemas/postgres/624_location_pollinator_habitat_lifecycle.sql"
MIGRATION = ROOT / "schemas/postgres/625_location_pollinator_hive_lifecycle.sql"
PLATFORM = os.environ.get("HIVE_LIFECYCLE_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-25-recovery/"
    f"cap-006-pollinator-hive-lifecycle{OUTPUT_SUFFIX}-disposable.json"
)
IMAGE = os.environ.get("HIVE_LIFECYCLE_TEST_IMAGE", "postgres:16")


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
    container = f"kokonut-hive-lifecycle-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    connection = None
    checks: list[str] = []
    operator_id, other_operator_id = str(uuid.uuid4()), str(uuid.uuid4())
    location_id, other_location_id = str(uuid.uuid4()), str(uuid.uuid4())
    habitat_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    hive_record_id = str(uuid.uuid4())
    hive_request_id = str(uuid.uuid4())
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
                   RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
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
            for replay in range(2):
                cursor.execute(HABITAT_MIGRATION.read_text())
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON hive_record TO kokonut_runtime, kokonut_directus_runtime")
            for replay in range(2):
                cursor.execute(MIGRATION.read_text())
            cursor.execute(
                "INSERT INTO location (id, name) VALUES (%s, 'Synthetic habitat'), (%s, 'Other')",
                (location_id, other_location_id),
            )
            cursor.execute("INSERT INTO operator_identity (id) VALUES (%s), (%s)", (operator_id, other_operator_id))
            cursor.execute(
                "INSERT INTO operator_scope_grant (operator_id, location_id, resource, action) "
                "VALUES (%s, %s, 'pollinator_health', 'edit')",
                (operator_id, location_id),
            )
            cursor.execute(
                "INSERT INTO pollinator_habitat (id, location_id, habitat_name, habitat_type, area_m2, condition, status) "
                "VALUES (%s, %s, 'Synthetic hedgerow', 'hedgerow', 90.25, 'good', 'active')",
                (habitat_id, location_id),
            )
            cursor.execute(
                "INSERT INTO hive_record (id, location_id, hive_id, hive_type, status) "
                "VALUES (%s, %s, 'H-625', 'langstroth', 'active')",
                (hive_record_id, location_id),
            )
            cursor.execute("SELECT updated_at FROM pollinator_habitat WHERE id = %s", (habitat_id,))
            expected_updated_at = cursor.fetchone()[0]
            cursor.execute("SELECT updated_at FROM hive_record WHERE id = %s", (hive_record_id,))
            hive_expected_updated_at = cursor.fetchone()[0]
            cursor.execute("SELECT CURRENT_DATE")
            maintenance_date = cursor.fetchone()[0]
        checks.append("migrations 155/602/619/620/621/622/623/624/625 apply; migration 625 replays")

        connection.autocommit = False
        call = """SELECT kokonut_security.update_location_pollinator_habitat(
            %s::uuid, %s::uuid, %s::uuid, %s::timestamptz, %s::text, %s::boolean,
            %s::text, %s::boolean, %s::date, %s::boolean, %s::text
        )"""
        params = (
            location_id, habitat_id, request_id, expected_updated_at,
            "degraded", True, "fair", True, maintenance_date, True,
            "Observed thinning; maintenance completed",
        )

        def update(args=params, *, actor=operator_id, scope=location_id, actor_type="operator"):
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

        def expect_update_error(args, expected, *, actor=operator_id, scope=location_id, actor_type="operator"):
            try:
                update(args, actor=actor, scope=scope, actor_type=actor_type)
            except psycopg2.Error as exc:
                if exc.pgcode != expected:
                    raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
                return
            raise AssertionError(f"expected SQLSTATE {expected}, update succeeded")

        first = update()
        if first["replayed"] is not False or first["status"] != "degraded" or first["condition"] != "fair":
            raise AssertionError(f"unexpected habitat update response: {first!r}")
        checks.append("exact signed location edit grant applies reported status/condition/maintenance fields")
        retry = update()
        if retry["event_id"] != first["event_id"] or retry["replayed"] is not True:
            raise AssertionError("exact update retry did not return the original event")
        checks.append("exact retries replay one original event")

        changed = list(params)
        changed[-1] = "different reason with same request ID"
        expect_update_error(tuple(changed), "23505")
        stale = list(params)
        stale[2] = str(uuid.uuid4())
        stale[3] = expected_updated_at
        expect_update_error(tuple(stale), "40001")
        missing = list(params)
        missing[1] = str(uuid.uuid4())
        missing[2] = str(uuid.uuid4())
        expect_update_error(tuple(missing), "P0002")
        checks.append("changed request reuse, stale timestamps, and missing location rows fail closed")

        invalid = list(params)
        invalid[4] = "published"
        invalid[2] = str(uuid.uuid4())
        expect_update_error(tuple(invalid), "22023")
        invalid = list(params)
        invalid[8] = date.today().replace(year=date.today().year + 1)
        invalid[2] = str(uuid.uuid4())
        expect_update_error(tuple(invalid), "22023")
        invalid = list(params)
        invalid[10] = "   "
        invalid[2] = str(uuid.uuid4())
        expect_update_error(tuple(invalid), "22023")
        checks.append("invalid status, future maintenance date, and empty audit reason are rejected")

        expect_update_error(params, "42501", actor=other_operator_id)
        expect_update_error(tuple([other_location_id, *params[1:]]), "42501")
        expect_update_error(params, "42501", scope=other_location_id)
        expect_update_error(params, "42501", actor_type="service")
        checks.append("ungranted operator, wrong location, mismatched context, and non-operator actor are denied")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT status, condition, last_maintenance, updated_by_operator_id "
                "FROM pollinator_habitat WHERE id = %s",
                (habitat_id,),
            )
            stored = cursor.fetchone()
            cursor.execute(
                "SELECT count(*), min(status_before), min(status_after), min(reason) "
                "FROM pollinator_habitat_lifecycle_event WHERE habitat_id = %s",
                (habitat_id,),
            )
            event = cursor.fetchone()
        if stored != ("degraded", "fair", maintenance_date, operator_id):
            raise AssertionError(f"unexpected habitat state/attribution: {stored!r}")
        if event != (1, "active", "degraded", "Observed thinning; maintenance completed"):
            raise AssertionError(f"unexpected append-only change event: {event!r}")
        checks.append("operational state and attributed before/after audit are committed atomically")

        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            for statement, arguments in (
                ("UPDATE pollinator_habitat SET status = 'active' WHERE id = %s", (habitat_id,)),
                ("INSERT INTO pollinator_habitat_lifecycle_event (operator_id, request_id, location_id, habitat_id, input_digest, reason, status_before, status_after, updated_at_after) VALUES (%s, %s, %s, %s, %s, 'direct', 'active', 'active', NOW())", (operator_id, str(uuid.uuid4()), location_id, habitat_id, b"x" * 32)),
                ("SELECT * FROM pollinator_habitat_lifecycle_event", ()),
            ):
                expect_sqlstate(connection, statement, arguments, "42501")
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            if role == "kokonut_runtime":
                with connection.cursor() as cursor:
                    cursor.execute("SET ROLE kokonut_runtime")
                connection.commit()
                expect_update_error(tuple([other_location_id, *params[1:]]), "42501")
        checks.append("runtime and Directus cannot mutate or read the private lifecycle ledger or update habitat rows")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = 'kokonut_pollinator_habitat_lifecycle_writer'"
            )
            role_profile = cursor.fetchone()
            cursor.execute(
                "SELECT has_function_privilege('kokonut_runtime', "
                "'kokonut_security.update_location_pollinator_habitat(uuid,uuid,uuid,timestamp with time zone,text,boolean,text,boolean,date,boolean,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.update_location_pollinator_habitat(uuid,uuid,uuid,timestamp with time zone,text,boolean,text,boolean,date,boolean,text)', 'EXECUTE')"
            )
            function_privileges = cursor.fetchone()
        if role_profile != (False, False, False) or function_privileges != (True, False):
            raise AssertionError(f"unexpected function owner/grants: {role_profile!r} / {function_privileges!r}")
        checks.append("no-login/no-inherit/no-bypass writer is executable only through Gateway runtime")

        hive_call = """SELECT kokonut_security.update_location_pollinator_hive(
            %s::uuid, %s::uuid, %s::uuid, %s::timestamptz, %s::text, %s::boolean,
            %s::date, %s::boolean, %s::text
        )"""
        hive_params = (
            location_id, hive_record_id, hive_request_id, hive_expected_updated_at,
            "inactive", True, maintenance_date, True,
            "Hive moved to recovery area; maintenance completed",
        )

        def update_hive(args=hive_params, *, actor=operator_id, scope=location_id, actor_type="operator"):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE kokonut_runtime")
                    set_context(cursor, actor, scope, actor_type)
                    cursor.execute(hive_call, args)
                    result = cursor.fetchone()[0]
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

        def expect_hive_error(args, expected, *, actor=operator_id, scope=location_id, actor_type="operator"):
            try:
                update_hive(args, actor=actor, scope=scope, actor_type=actor_type)
            except psycopg2.Error as exc:
                if exc.pgcode != expected:
                    raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
                return
            raise AssertionError(f"expected SQLSTATE {expected}, hive update succeeded")

        hive_first = update_hive()
        if (
            hive_first["replayed"] is not False
            or hive_first["status"] != "inactive"
            or hive_first["last_maintenance_date"] != maintenance_date.isoformat()
        ):
            raise AssertionError(f"unexpected managed-hive lifecycle response: {hive_first!r}")
        checks.append("exact signed location edit grant applies operational status and maintenance date")
        hive_retry = update_hive()
        if hive_retry["event_id"] != hive_first["event_id"] or hive_retry["replayed"] is not True:
            raise AssertionError("exact managed-hive retry did not return the original event")
        checks.append("exact managed-hive retries replay the original audit event")

        changed_hive = list(hive_params)
        changed_hive[-1] = "changed reason with same request ID"
        expect_hive_error(tuple(changed_hive), "23505")
        stale_hive = list(hive_params)
        stale_hive[2] = str(uuid.uuid4())
        expect_hive_error(tuple(stale_hive), "40001")
        missing_hive = list(hive_params)
        missing_hive[1] = str(uuid.uuid4())
        missing_hive[2] = str(uuid.uuid4())
        expect_hive_error(tuple(missing_hive), "P0002")
        checks.append("changed request reuse, stale timestamps, and missing location rows fail closed")

        invalid_hive = list(hive_params)
        invalid_hive[4] = "dead"
        invalid_hive[2] = str(uuid.uuid4())
        expect_hive_error(tuple(invalid_hive), "22023")
        invalid_hive = list(hive_params)
        invalid_hive[6] = date.today().replace(year=date.today().year + 1)
        invalid_hive[2] = str(uuid.uuid4())
        expect_hive_error(tuple(invalid_hive), "22023")
        invalid_hive = list(hive_params)
        invalid_hive[8] = "   "
        invalid_hive[2] = str(uuid.uuid4())
        expect_hive_error(tuple(invalid_hive), "22023")
        checks.append("unsupported status, future maintenance date, and empty audit reason are rejected")

        expect_hive_error(hive_params, "42501", actor=other_operator_id)
        expect_hive_error(tuple([other_location_id, *hive_params[1:]]), "42501")
        expect_hive_error(hive_params, "42501", scope=other_location_id)
        expect_hive_error(hive_params, "42501", actor_type="service")
        checks.append("ungranted operator, wrong location, mismatched context, and non-operator actor are denied")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT status, last_maintenance_date, updated_by_operator_id "
                "FROM hive_record WHERE id = %s",
                (hive_record_id,),
            )
            hive_stored = cursor.fetchone()
            cursor.execute(
                "SELECT count(*), min(status_before), min(status_after), min(reason) "
                "FROM pollinator_hive_lifecycle_event WHERE hive_record_id = %s",
                (hive_record_id,),
            )
            hive_event = cursor.fetchone()
        if hive_stored != ("inactive", maintenance_date, operator_id):
            raise AssertionError(f"unexpected hive state/attribution: {hive_stored!r}")
        if hive_event != (
            1, "active", "inactive", "Hive moved to recovery area; maintenance completed"
        ):
            raise AssertionError(f"unexpected immutable hive lifecycle event: {hive_event!r}")
        checks.append("managed-hive state and attributed before/after audit are committed atomically")

        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            for statement, arguments in (
                ("UPDATE hive_record SET status = 'active' WHERE id = %s", (hive_record_id,)),
                ("INSERT INTO pollinator_hive_lifecycle_event (operator_id, request_id, location_id, hive_record_id, input_digest, reason, status_before, status_after, updated_at_after) VALUES (%s, %s, %s, %s, %s, 'direct', 'active', 'active', NOW())", (operator_id, str(uuid.uuid4()), location_id, hive_record_id, b"x" * 32)),
                ("SELECT * FROM pollinator_hive_lifecycle_event", ()),
            ):
                expect_sqlstate(connection, statement, arguments, "42501")
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = 'kokonut_pollinator_hive_lifecycle_writer'"
            )
            hive_role_profile = cursor.fetchone()
            cursor.execute(
                "SELECT has_function_privilege('kokonut_runtime', "
                "'kokonut_security.update_location_pollinator_hive(uuid,uuid,uuid,timestamp with time zone,text,boolean,date,boolean,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.update_location_pollinator_hive(uuid,uuid,uuid,timestamp with time zone,text,boolean,date,boolean,text)', 'EXECUTE')"
            )
            hive_function_privileges = cursor.fetchone()
        if hive_role_profile != (False, False, False) or hive_function_privileges != (True, False):
            raise AssertionError(
                f"unexpected hive function owner/grants: {hive_role_profile!r} / {hive_function_privileges!r}"
            )
        checks.append("runtime and Directus cannot directly alter hive state or inspect the private audit ledger")
        checks.append("no-login/no-inherit/no-bypass hive writer is executable only through Gateway runtime")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "architecture": architecture,
            "migrations": [path.name for path in (*MIGRATIONS, HABITAT_MIGRATION, MIGRATION)],
            "migration_624_applied": True,
            "migration_625_replayed": True,
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
    raise SystemExit(main())
