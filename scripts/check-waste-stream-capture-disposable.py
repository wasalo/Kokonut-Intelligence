#!/usr/bin/env python3
"""Apply/replay migrations 613/614 and exercise waste captures on disposable PG16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
BASE_MIGRATION = ROOT / "schemas/postgres/153_waste_management.sql"
MIGRATION = ROOT / "schemas/postgres/613_location_waste_stream_capture.sql"
COMPOSTING_MIGRATION = ROOT / "schemas/postgres/614_location_composting_capture.sql"
RECYCLING_MIGRATION = ROOT / "schemas/postgres/615_location_recycling_capture.sql"
INCIDENT_MIGRATION = ROOT / "schemas/postgres/616_location_pollution_incident_gateway.sql"
PLATFORM = os.environ.get("WASTE_CAPTURE_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-24-recovery/"
    f"cap-006-waste-incident-capture{OUTPUT_SUFFIX}-disposable.json"
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
            cursor.execute(
                "GRANT SELECT (id, status, feedstock_type, feedstock_kg, compost_method, "
                "temperature_c, moisture_pct, duration_days, finished_volume_kg, metadata, created_by) "
                "ON public.composting_record TO kokonut_runtime"
            )
            cursor.execute(
                "GRANT SELECT (id, location_id, record_date, material_type, quantity_kg, "
                "destination, revenue, status, metadata, created_by) "
                "ON public.recycling_log TO kokonut_runtime"
            )
            cursor.execute(
                "GRANT SELECT (id, location_id, incident_date, incident_type, severity, "
                "description, affected_area, remedial_action, resolved, resolution_date, "
                "notes, status, metadata, created_at, created_by, updated_by) "
                "ON public.pollution_incident TO kokonut_runtime"
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
            cursor.execute(COMPOSTING_MIGRATION.read_text())
            cursor.execute(COMPOSTING_MIGRATION.read_text())
            cursor.execute(RECYCLING_MIGRATION.read_text())
            cursor.execute(RECYCLING_MIGRATION.read_text())
            cursor.execute(INCIDENT_MIGRATION.read_text())
            cursor.execute(INCIDENT_MIGRATION.read_text())
            cursor.execute(
                "INSERT INTO operator_scope_grant VALUES (%s, %s, 'waste_management', 'review', NULL)",
                (operator_id, location_id),
            )
        checks.append("migrations 613, 614, 615, and 616 apply and replay after the canonical migration-153 tables")

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

        compost_request_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.create_location_composting_record("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, compost_request_id, date.today(), "other", "Banana stems",
                    "100.00", "vermiculture", "Vermicomposting", "55.0", "60.0", 30,
                    "45.00", "6.50",
                    "synthetic compost capture",
                ),
            )
            compost_created = cursor.fetchone()[0]
            if (
                compost_created["location_id"] != location_id
                or compost_created["status"] != "recorded"
                or compost_created["replayed"] is not False
            ):
                raise AssertionError("compost capture response did not preserve recorded location scope")
            cursor.execute(
                "SELECT status, feedstock_type, feedstock_kg, compost_method, "
                "finished_volume_kg, (metadata->>'ph')::numeric, created_by, "
                "metadata->'legacy_composting_inputs' "
                "FROM public.composting_record WHERE id = %s",
                (compost_created["record_id"],),
            )
            compost_row = cursor.fetchone()
            if compost_row != (
                "recorded", "other", 100.0, "vermiculture", 45.0,
                Decimal("6.50"), operator_id,
                {"feedstock_type": "Banana stems", "compost_method": "Vermicomposting"},
            ):
                raise AssertionError(f"unexpected compost capture row: {compost_row}")
            cursor.execute(
                "SELECT kokonut_security.create_location_composting_record("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, compost_request_id, date.today(), "other", "Banana stems",
                    "100.00", "vermiculture", "Vermicomposting", "55.0", "60.0", 30,
                    "45.00", "6.50",
                    "synthetic compost capture",
                ),
            )
            compost_replay = cursor.fetchone()[0]
            if (
                compost_replay["record_id"] != compost_created["record_id"]
                or compost_replay["replayed"] is not True
            ):
                raise AssertionError("compost exact retry did not return the original record")
        connection.commit()
        checks.append("composting capture writes recorded process data, preserves bounded freeform labels, and replays the exact request")

        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_composting_record(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                location_id, compost_request_id, date.today(), "other", "Banana stems",
                "100.00", "vermiculture", "Vermicomposting", "55.0", "60.0", 30,
                "45.00", "6.50",
                "changed compost payload",
            ),
            "23505",
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (other_location_id,))
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_composting_record(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                other_location_id, str(uuid.uuid4()), date.today(), "crop_residue", None,
                "100.00", "vermiculture", None, None, None, None, None, None, None,
            ),
            "42501",
        )
        connection.rollback()
        checks.append("compost changed-input replay conflicts and mismatched signed location is denied")
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (location_id,))

        recycling_request_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.create_location_recycling_record("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, recycling_request_id, date.today(), "other", "Steel scrap",
                    "8.00", "Scrap yard", "12.50", "synthetic recycling capture",
                ),
            )
            recycling_created = cursor.fetchone()[0]
            if (
                recycling_created["location_id"] != location_id
                or recycling_created["status"] != "recorded"
                or recycling_created["replayed"] is not False
            ):
                raise AssertionError("recycling response did not preserve recorded location scope")
            cursor.execute(
                "SELECT status, material_type, quantity_kg, destination, revenue, "
                "metadata->>'legacy_material_type', created_by "
                "FROM public.recycling_log WHERE id = %s",
                (recycling_created["record_id"],),
            )
            recycling_row = cursor.fetchone()
            if recycling_row != (
                "recorded", "other", 8.0, "Scrap yard", 12.5, "Steel scrap", operator_id,
            ):
                raise AssertionError(f"unexpected recycling capture row: {recycling_row}")
            cursor.execute(
                "SELECT kokonut_security.create_location_recycling_record("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, recycling_request_id, date.today(), "other", "Steel scrap",
                    "8.00", "Scrap yard", "12.50", "synthetic recycling capture",
                ),
            )
            recycling_replay = cursor.fetchone()[0]
            if (
                recycling_replay["record_id"] != recycling_created["record_id"]
                or recycling_replay["replayed"] is not True
            ):
                raise AssertionError("recycling exact retry did not return the original record")
        connection.commit()
        checks.append("recycling capture maps and preserves freeform labels, stores revenue, and replays exact requests")

        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_recycling_record(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                location_id, recycling_request_id, date.today(), "other", "Steel scrap",
                "8.00", "Changed destination", "12.50", "synthetic recycling capture",
            ),
            "23505",
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (other_location_id,))
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_recycling_record(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                other_location_id, str(uuid.uuid4()), date.today(), "plastic", None,
                "1.00", "Recycling center", None, None,
            ),
            "42501",
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (location_id,))
        expect_denied(
            connection,
            "INSERT INTO public.recycling_log (id, location_id, record_date, material_type, quantity_kg, status) "
            "VALUES (%s, %s, CURRENT_DATE, 'plastic', 1, 'recorded')",
            (str(uuid.uuid4()), location_id),
            "42501",
        )
        checks.append("recycling changed-input reuse and foreign-location access fail; direct runtime inserts are denied")

        incident_request_id = str(uuid.uuid4())
        incident_date = date.today()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.create_location_pollution_incident("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, incident_request_id, incident_date, "air_emission",
                    "air_pollution", "high", "Synthetic plume report", "North plot",
                    "Field reporter", "Synthetic incident capture",
                ),
            )
            incident_created = cursor.fetchone()[0]
            if (
                incident_created["location_id"] != location_id
                or incident_created["status"] != "open"
                or incident_created["replayed"] is not False
            ):
                raise AssertionError("incident capture did not return an open scoped record")
            cursor.execute(
                "SELECT status, resolved, incident_type, severity, description, affected_area, "
                "metadata->>'reported_by', metadata->>'legacy_incident_type', created_by "
                "FROM public.pollution_incident WHERE id = %s",
                (incident_created["incident_id"],),
            )
            incident_row = cursor.fetchone()
            if incident_row != (
                "open", False, "air_emission", "high", "Synthetic plume report",
                "North plot", "Field reporter", "air_pollution", operator_id,
            ):
                raise AssertionError(f"unexpected open incident row: {incident_row}")
            cursor.execute(
                "SELECT kokonut_security.create_location_pollution_incident("
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    location_id, incident_request_id, incident_date, "air_emission",
                    "air_pollution", "high", "Synthetic plume report", "North plot",
                    "Field reporter", "Synthetic incident capture",
                ),
            )
            incident_replay = cursor.fetchone()[0]
            if (
                incident_replay["incident_id"] != incident_created["incident_id"]
                or incident_replay["replayed"] is not True
            ):
                raise AssertionError("incident exact retry did not return the original incident")
        connection.commit()
        checks.append("incident capture maps legacy types, preserves bounded attribution, opens, and exactly replays")

        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_pollution_incident(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                location_id, incident_request_id, incident_date, "air_emission",
                "air_pollution", "high", "Changed report", "North plot",
                "Field reporter", "Synthetic incident capture",
            ),
            "23505",
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (other_location_id,))
        expect_denied(
            connection,
            "SELECT kokonut_security.create_location_pollution_incident(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                other_location_id, str(uuid.uuid4()), incident_date, "runoff", None,
                "medium", "Wrong location", None, None, None,
            ),
            "42501",
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('kokonut.location_id', %s, false)", (location_id,))

        incident_resolution_request_id = str(uuid.uuid4())
        resolution_date = date.today()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.resolve_location_pollution_incident(%s, %s, %s, %s, %s)",
                (
                    location_id, incident_created["incident_id"],
                    incident_resolution_request_id, resolution_date, "Synthetic cleanup",
                ),
            )
            resolution = cursor.fetchone()[0]
            if resolution["status"] != "resolved" or resolution["replayed"] is not False:
                raise AssertionError("incident resolution did not return a new resolved result")
            cursor.execute(
                "SELECT status, resolved, remedial_action, resolution_date, updated_by "
                "FROM public.pollution_incident WHERE id = %s",
                (incident_created["incident_id"],),
            )
            resolved_row = cursor.fetchone()
            if resolved_row != (
                "resolved", True, "Synthetic cleanup", resolution_date, operator_id,
            ):
                raise AssertionError(f"unexpected resolved incident fields: {resolved_row}")
            cursor.execute(
                "SELECT kokonut_security.resolve_location_pollution_incident(%s, %s, %s, %s, %s)",
                (
                    location_id, incident_created["incident_id"],
                    incident_resolution_request_id, resolution_date, "Synthetic cleanup",
                ),
            )
            resolution_replay = cursor.fetchone()[0]
            if resolution_replay["replayed"] is not True:
                raise AssertionError("incident exact resolution retry did not replay")
        connection.commit()
        checks.append("separate review grant resolves only the scoped incident, attributes the reviewer, and retries exactly")

        expect_denied(
            connection,
            "SELECT kokonut_security.resolve_location_pollution_incident(%s, %s, %s, %s, %s)",
            (
                location_id, incident_created["incident_id"],
                incident_resolution_request_id, resolution_date, "Changed cleanup",
            ),
            "23505",
        )
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_runtime', 'public.pollution_incident', 'INSERT'), "
                "has_column_privilege('kokonut_runtime', 'public.pollution_incident', 'id', 'INSERT'), "
                "has_table_privilege('kokonut_runtime', 'public.pollution_incident', 'UPDATE'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.pollution_incident', 'INSERT'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.pollution_incident', 'UPDATE'), "
                "has_table_privilege('kokonut_runtime', 'public.pollution_incident_operation_receipt', 'SELECT'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.pollution_incident_operation_receipt', 'SELECT'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_pollution_incident(uuid,uuid,date,text,text,text,text,text,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_pollution_incident(uuid,uuid,date,text,text,text,text,text,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.resolve_location_pollution_incident(uuid,uuid,uuid,date,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.resolve_location_pollution_incident(uuid,uuid,uuid,date,text)', 'EXECUTE')"
            )
            privileges = cursor.fetchone()
            if (
                any(privileges[:7])
                or not privileges[7]
                or privileges[8]
                or not privileges[9]
                or privileges[10]
            ):
                raise AssertionError("incident direct-write, receipt, or function privileges are incorrect")
            cursor.execute(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = "
                "'kokonut_security.create_location_pollution_incident(uuid,uuid,date,text,text,text,text,text,text,text)'::regprocedure"
            )
            if cursor.fetchone()[0] != "kokonut_incident_capture_writer":
                raise AssertionError("incident capture function owner is not isolated")
            cursor.execute(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = "
                "'kokonut_security.resolve_location_pollution_incident(uuid,uuid,uuid,date,text)'::regprocedure"
            )
            if cursor.fetchone()[0] != "kokonut_incident_resolution_writer":
                raise AssertionError("incident resolution function owner is not isolated")
        checks.append("runtime and Directus cannot write incidents or read private receipts; function owners are isolated")

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
                "has_table_privilege('kokonut_runtime', 'public.composting_capture_receipt', 'SELECT'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.composting_capture_receipt', 'SELECT'), "
                "has_table_privilege('kokonut_runtime', 'public.recycling_capture_receipt', 'SELECT'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.recycling_capture_receipt', 'SELECT'), "
                "has_table_privilege('kokonut_runtime', 'public.recycling_log', 'INSERT'), "
                "has_column_privilege('kokonut_runtime', 'public.recycling_log', 'id', 'INSERT'), "
                "has_table_privilege('kokonut_directus_runtime', 'public.recycling_log', 'INSERT'), "
                "has_column_privilege('kokonut_directus_runtime', 'public.recycling_log', 'id', 'INSERT'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_waste_stream_record(uuid,uuid,text,text,numeric,date,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_waste_stream_record(uuid,uuid,text,text,numeric,date,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_composting_record(uuid,uuid,date,text,text,numeric,text,text,numeric,numeric,integer,numeric,numeric,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_composting_record(uuid,uuid,date,text,text,numeric,text,text,numeric,numeric,integer,numeric,numeric,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.create_location_recycling_record(uuid,uuid,date,text,text,numeric,text,numeric,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.create_location_recycling_record(uuid,uuid,date,text,text,numeric,text,numeric,text)', 'EXECUTE'), "
                "pg_get_userbyid((SELECT proowner FROM pg_proc WHERE oid = "
                "'kokonut_security.create_location_waste_stream_record(uuid,uuid,text,text,numeric,date,text,text)'::regprocedure))"
            )
            (
                runtime_select, directus_select, compost_runtime_select,
                compost_directus_select, recycling_runtime_select,
                recycling_directus_select, runtime_recycling_insert,
                runtime_recycling_column_insert, directus_recycling_insert,
                directus_recycling_column_insert, runtime_execute, directus_execute,
                compost_runtime_execute, compost_directus_execute,
                recycling_runtime_execute, recycling_directus_execute, owner,
            ) = cursor.fetchone()
            if (
                runtime_select or directus_select or compost_runtime_select
                or compost_directus_select or recycling_runtime_select
                or recycling_directus_select or runtime_recycling_insert
                or runtime_recycling_column_insert or directus_recycling_insert
                or directus_recycling_column_insert or not runtime_execute or directus_execute
                or not compost_runtime_execute or compost_directus_execute
                or not recycling_runtime_execute or recycling_directus_execute
                or owner != "kokonut_waste_stream_writer"
            ):
                raise AssertionError("capture receipt or function owner privilege boundary is incorrect")
            cursor.execute(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = "
                "'kokonut_security.create_location_composting_record(uuid,uuid,date,text,text,numeric,text,text,numeric,numeric,integer,numeric,numeric,text)'::regprocedure"
            )
            if cursor.fetchone()[0] != "kokonut_composting_capture_writer":
                raise AssertionError("composting writer function owner is not isolated")
            cursor.execute(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = "
                "'kokonut_security.create_location_recycling_record(uuid,uuid,date,text,text,numeric,text,numeric,text)'::regprocedure"
            )
            if cursor.fetchone()[0] != "kokonut_recycling_capture_writer":
                raise AssertionError("recycling writer function owner is not isolated")
        checks.append("runtime cannot write recycling rows or read private receipts; Directus cannot write/read receipts/execute; all function owners are isolated")

        evidence = {
            "status": "passed",
            "postgres_image": IMAGE,
            "platform": PLATFORM or "native",
            "migrations": [
                BASE_MIGRATION.name, MIGRATION.name, COMPOSTING_MIGRATION.name,
                RECYCLING_MIGRATION.name,
                INCIDENT_MIGRATION.name,
            ],
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
