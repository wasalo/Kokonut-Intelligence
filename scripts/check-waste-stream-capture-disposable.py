#!/usr/bin/env python3
"""Apply/replay migration 613 and exercise waste capture on disposable PG16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
import uuid
from datetime import date
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
BASE_MIGRATION = ROOT / "schemas/postgres/153_waste_management.sql"
MIGRATION = ROOT / "schemas/postgres/613_location_waste_stream_capture.sql"
PLATFORM = os.environ.get("WASTE_CAPTURE_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-24-recovery/"
    f"cap-006-waste-stream-capture{OUTPUT_SUFFIX}-disposable.json"
)
IMAGE = os.environ.get("WASTE_CAPTURE_TEST_IMAGE", "postgres:16")


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
            text=True,
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def expect_denied(connection, query: str, params: tuple, sqlstate: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
    except psycopg2.Error as exc:
        if exc.pgcode != sqlstate:
            raise AssertionError(f"expected SQLSTATE {sqlstate}, got {exc.pgcode}") from exc
        connection.rollback()
        return
    raise AssertionError(f"expected SQLSTATE {sqlstate} but operation succeeded")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    container = f"kokonut-waste-capture-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    connection = None
    checks: list[str] = []
    operator_id, location_id, other_location_id, ungranted_operator_id = [
        str(uuid.uuid4()) for _ in range(4)
    ]
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
        wait_ready(docker, container)
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
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)")
            cursor.execute("CREATE TABLE operator_identity (id UUID PRIMARY KEY)")
            cursor.execute(
                "CREATE TABLE operator_scope_grant (operator_id UUID, location_id UUID, "
                "resource TEXT, action TEXT, revoked_at TIMESTAMPTZ)"
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
                """CREATE FUNCTION public.operator_scope_grant_allows(
                       UUID, TEXT, TEXT, UUID
                   ) RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER
                   SET search_path = pg_catalog
                   AS $$ SELECT EXISTS (
                       SELECT 1 FROM public.operator_scope_grant AS grant_row
                        WHERE grant_row.operator_id = $1
                          AND grant_row.resource = $2 AND grant_row.action = $3
                          AND grant_row.location_id = $4 AND grant_row.revoked_at IS NULL
                   ) $$"""
            )
            cursor.execute("GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime")
            cursor.execute("GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_directus_runtime")
            cursor.execute(BASE_MIGRATION.read_text())
            cursor.execute(BASE_MIGRATION.read_text())
            cursor.execute(
                "GRANT SELECT (id, status, quantity_kg, quantity_unit, created_by) "
                "ON public.waste_stream TO kokonut_runtime"
            )
            cursor.execute("INSERT INTO location VALUES (%s, 'Synthetic'), (%s, 'Other')", (location_id, other_location_id))
            cursor.execute(
                "INSERT INTO operator_identity VALUES (%s), (%s)",
                (operator_id, ungranted_operator_id),
            )
            cursor.execute(
                "INSERT INTO operator_scope_grant VALUES (%s, %s, 'waste_management', 'create', NULL)",
                (operator_id, location_id),
            )
            cursor.execute(MIGRATION.read_text())
            cursor.execute(MIGRATION.read_text())
        checks.append("migration 613 applies and replays after the canonical migration-153 table")

        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_runtime")
            cursor.execute("SELECT set_config('kokonut.actor_id', %s, false)", (operator_id,))
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (location_id,))
            cursor.execute("SELECT set_config('kokonut.actor_type', 'operator', false)")
            cursor.execute(
                "SELECT kokonut_security.create_location_waste_stream_record("
                "%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, request_id, "crop_residue", "Banana stems", "12.50",
                    date.today(), "composting", "synthetic capture",
                ),
            )
            created = cursor.fetchone()[0]
            cursor.execute(
                "SELECT status, quantity_kg, quantity_unit, created_by FROM public.waste_stream WHERE id = %s",
                (created["record_id"],),
            )
            row = cursor.fetchone()
            if row != ("recorded", 12.5, "kg", operator_id):
                raise AssertionError(f"unexpected recorded waste fields: {row}")
            if created["replayed"] is not False or created["location_id"] != location_id:
                raise AssertionError("initial capture response was not location-bound")
            cursor.execute(
                "SELECT kokonut_security.create_location_waste_stream_record("
                "%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, request_id, "crop_residue", "Banana stems", "12.50",
                    date.today(), "composting", "synthetic capture",
                ),
            )
            replayed = cursor.fetchone()[0]
            if replayed["record_id"] != created["record_id"] or replayed["replayed"] is not True:
                raise AssertionError("identical retry did not replay the original entry")
        connection.commit()
        checks.append("exact create grant captures a recorded kg row and an identical retry returns the same ID")

        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (other_location_id,))
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_waste_stream_record(%s, %s, %s, %s, %s, %s, %s, %s)",
            (other_location_id, str(uuid.uuid4()), "crop_residue", "Wrong location", 1, date.today(), None, None),
            "42501",
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (location_id,))
            cursor.execute("SELECT set_config('kokonut.actor_id', %s, false)", (ungranted_operator_id,))
            cursor.execute("SELECT set_config('kokonut.actor_type', 'operator', false)")
        connection.commit()
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_waste_stream_record(%s, %s, %s, %s, %s, %s, %s, %s)",
            (location_id, str(uuid.uuid4()), "crop_residue", "No grant", 1, date.today(), None, None),
            "42501",
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.actor_id', %s, false)", (operator_id,))
            cursor.execute("SELECT set_config('kokonut.actor_type', 'mobile_device', false)")
        connection.commit()
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_waste_stream_record(%s, %s, %s, %s, %s, %s, %s, %s)",
            (location_id, str(uuid.uuid4()), "crop_residue", "Wrong actor", 1, date.today(), None, None),
            "42501",
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.actor_type', 'operator', false)")
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (location_id,))
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_waste_stream_record(%s, %s, %s, %s, %s, %s, %s, %s)",
            (location_id, str(uuid.uuid4()), "unsupported", "Invalid type", 1, date.today(), None, None),
            "22023",
        )
        checks.append("mismatched location, missing exact create grant, wrong actor type, and invalid category fail closed")

        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_waste_stream_record(%s, %s, %s, %s, %s, %s, %s, %s)",
            (location_id, request_id, "crop_residue", "Changed payload", 12.5, date.today(), "composting", "synthetic capture"),
            "23505",
        )
        connection.rollback()
        checks.append("idempotency key reuse with changed input conflicts")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_runtime', 'public.waste_stream_capture_receipt', 'SELECT'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.waste_stream_capture_receipt', 'SELECT'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_waste_stream_record(uuid,uuid,text,text,numeric,date,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_waste_stream_record(uuid,uuid,text,text,numeric,date,text,text)', 'EXECUTE'), "
                "pg_get_userbyid((SELECT proowner FROM pg_proc WHERE oid = "
                "'kokonut_security.create_location_waste_stream_record(uuid,uuid,text,text,numeric,date,text,text)'::regprocedure))"
            )
            runtime_select, directus_select, runtime_execute, directus_execute, owner = cursor.fetchone()
            if runtime_select or directus_select or not runtime_execute or directus_execute or owner != "kokonut_waste_stream_writer":
                raise AssertionError("capture receipt or function owner privilege boundary is incorrect")
        checks.append("runtime/Directus cannot read private receipts; Directus cannot execute and function owner is isolated")

        evidence = {
            "status": "passed",
            "postgres_image": IMAGE,
            "platform": PLATFORM or "native",
            "migrations": [BASE_MIGRATION.name, MIGRATION.name],
            "checks": checks,
            "candidate_or_legacy_database_used": False,
            "provider_calls": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if started:
            subprocess.run([docker, "rm", "--force", container], check=False, capture_output=True, text=True)


if __name__ == "__main__":
    raise SystemExit(main())
