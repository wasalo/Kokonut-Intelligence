#!/usr/bin/env python3
"""Exercise migration 702 on a disposable PostGIS/PostgreSQL 16 container."""

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
MIGRATION = ROOT / "schemas/postgres/702_location_landscape_capture.sql"
IMAGE = os.environ.get("LANDSCAPE_CAPTURE_TEST_IMAGE", "postgis/postgis:16-3.4")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} …\n{details}")
    return result.stdout.strip()


def call_capture(connection, operator_id, location_id, record_type, request_id, content, reason="Synthetic test"):
    statement = """SELECT kokonut_security.create_location_landscape_record(
        %s::uuid, %s::text, %s::uuid, %s::jsonb, %s::text
    )"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_runtime")
            cursor.execute("SELECT set_config('kokonut.actor_id', %s, true)", (str(operator_id),))
            cursor.execute("SELECT set_config('kokonut.location_id', %s, true)", (str(location_id),))
            cursor.execute("SELECT set_config('kokonut.actor_type', 'operator', true)")
            cursor.execute(statement, (str(location_id), record_type, str(request_id), json.dumps(content), reason))
            result = cursor.fetchone()[0]
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-landscape-capture-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    connection = None
    checks: list[str] = []
    operator_id, other_operator_id = uuid.uuid4(), uuid.uuid4()
    location_id, other_location_id = uuid.uuid4(), uuid.uuid4()
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "--env", f"POSTGRES_PASSWORD={password}", "--publish", "127.0.0.1::5432", IMAGE,
        ])
        started = True
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            ready = subprocess.run(
                [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
                text=True, capture_output=True, check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("disposable PostgreSQL/PostGIS did not become ready")

        architecture = run([docker, "exec", container, "uname", "-m"])
        mapping = json.loads(run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container]))
        port = int(mapping["5432/tcp"][0]["HostPort"])
        connection = psycopg2.connect(
            host="127.0.0.1", port=port, dbname="postgres", user="postgres",
            password=password, connect_timeout=5,
        )
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            cursor.execute("CREATE ROLE kokonut_runtime NOLOGIN")
            cursor.execute("CREATE ROLE kokonut_directus_runtime NOLOGIN")
            cursor.execute("CREATE SCHEMA kokonut_security")
            cursor.execute("CREATE TABLE organization (id UUID PRIMARY KEY, status TEXT NOT NULL)")
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, organization_id UUID, boundary geometry(POLYGON, 4326))")
            cursor.execute("CREATE TABLE operator_identity (id UUID PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT TRUE, secret_label TEXT)")
            cursor.execute(
                "CREATE TABLE operator_scope_grant (operator_id UUID, location_id UUID, organization_id UUID, resource TEXT, action TEXT, revoked_at TIMESTAMPTZ)"
            )
            cursor.execute("CREATE TABLE operator_organization_membership (operator_id UUID, organization_id UUID, revoked_at TIMESTAMPTZ)")
            cursor.execute("CREATE TABLE location_tenant_owner_verification (location_id UUID, organization_id UUID, revoked_at TIMESTAMPTZ)")
            cursor.execute("CREATE TABLE location_organization_share (location_id UUID, organization_id UUID, revoked_at TIMESTAMPTZ, expires_at TIMESTAMPTZ)")
            cursor.execute("""CREATE TABLE habitat_zone (
                id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
                zone_name VARCHAR(200) NOT NULL, habitat_type VARCHAR(100) NOT NULL,
                area_ha NUMERIC(8,2), perimeter_m NUMERIC(10,2), description TEXT,
                biodiversity_value VARCHAR(20), gps_boundary geometry, status VARCHAR(50) NOT NULL,
                metadata JSONB DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            cursor.execute("""CREATE TABLE wildlife_corridor (
                id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
                corridor_name VARCHAR(200) NOT NULL, source_habitat_id UUID REFERENCES habitat_zone(id),
                target_habitat_id UUID REFERENCES habitat_zone(id), width_m NUMERIC(8,2),
                length_m NUMERIC(10,2), vegetation_type VARCHAR(100), condition VARCHAR(50),
                last_survey_date DATE, notes TEXT, status VARCHAR(50) NOT NULL,
                metadata JSONB DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            cursor.execute("""CREATE TABLE hedgerow_record (
                id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
                hedgerow_name VARCHAR(200), species_mix JSONB DEFAULT '[]', length_m NUMERIC(10,2),
                height_m NUMERIC(5,2), age_years INTEGER, planting_date DATE, last_maintenance DATE,
                condition VARCHAR(50), purpose JSONB DEFAULT '[]', notes TEXT, status VARCHAR(50) NOT NULL,
                metadata JSONB DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            cursor.execute("""CREATE TABLE buffer_zone_monitoring (
                id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
                habitat_zone_id UUID REFERENCES habitat_zone(id), check_date DATE NOT NULL,
                buffer_width_m NUMERIC(8,2), minimum_required_m NUMERIC(8,2), compliant BOOLEAN,
                vegetation_coverage_pct NUMERIC(5,2), erosion_observed BOOLEAN DEFAULT FALSE,
                notes TEXT, status VARCHAR(50) NOT NULL, metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            cursor.execute("""CREATE TABLE landscape_biodiversity_score (
                id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
                assessment_date DATE NOT NULL, species_richness INTEGER, shannon_index NUMERIC(5,3),
                habitat_diversity_index NUMERIC(5,3), connectivity_score NUMERIC(5,2),
                overall_score NUMERIC(5,2), assessor VARCHAR(200), notes TEXT,
                status VARCHAR(50) NOT NULL, metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            cursor.execute("""CREATE FUNCTION kokonut_security.current_tenant_context()
                RETURNS TABLE(actor_id UUID, location_id UUID, actor_type TEXT)
                LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
                AS $$ SELECT nullif(current_setting('kokonut.actor_id', true), '')::uuid,
                                 nullif(current_setting('kokonut.location_id', true), '')::uuid,
                                 nullif(current_setting('kokonut.actor_type', true), '') $$""")
            cursor.execute("""CREATE FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
                RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = pg_catalog
                AS $$ SELECT EXISTS (
                    SELECT 1 FROM public.operator_scope_grant AS g
                     JOIN public.operator_identity AS identity
                       ON identity.id = g.operator_id AND identity.enabled
                     JOIN public.location AS loc ON loc.id = g.location_id
                     WHERE g.operator_id = $1 AND g.resource = $2 AND g.action = $3
                       AND g.location_id = $4 AND g.revoked_at IS NULL
                       AND (g.organization_id IS NULL OR (
                           EXISTS (
                               SELECT 1
                                 FROM public.operator_organization_membership AS membership
                                 JOIN public.organization AS tenant
                                   ON tenant.id = membership.organization_id
                                  AND tenant.status = 'active'
                                WHERE membership.operator_id = g.operator_id
                                  AND membership.organization_id = g.organization_id
                                  AND membership.revoked_at IS NULL
                           )
                           AND EXISTS (
                               SELECT 1
                                 FROM public.location_tenant_owner_verification AS owner
                                WHERE owner.location_id = loc.id
                                  AND owner.organization_id = loc.organization_id
                                  AND owner.revoked_at IS NULL
                                  AND (owner.organization_id = g.organization_id OR EXISTS (
                                      SELECT 1
                                        FROM public.location_organization_share AS share
                                       WHERE share.location_id = loc.id
                                         AND share.organization_id = g.organization_id
                                         AND share.revoked_at IS NULL
                                         AND (share.expires_at IS NULL OR share.expires_at > NOW())
                                  ))
                           )
                       ))
                ) $$""")
            cursor.execute("GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON location, habitat_zone, wildlife_corridor, hedgerow_record, buffer_zone_monitoring, landscape_biodiversity_score TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("""INSERT INTO location (id, boundary) VALUES
                (%s, public.ST_GeomFromText('POLYGON((0 0,10 0,10 10,0 10,0 0))', 4326)),
                (%s, public.ST_GeomFromText('POLYGON((20 20,30 20,30 30,20 30,20 20))', 4326))""", (str(location_id), str(other_location_id)))
            cursor.execute("INSERT INTO operator_identity VALUES (%s), (%s)", (str(operator_id), str(other_operator_id)))
            cursor.execute("INSERT INTO operator_scope_grant VALUES (%s,%s,NULL,'landscape_conservation','create',NULL)", (str(operator_id), str(location_id)))
            cursor.execute(MIGRATION.read_text())
            cursor.execute(MIGRATION.read_text())
        checks.append("migration 702 applies and replays on a disposable PostGIS/PostgreSQL 16 database")

        connection.autocommit = False
        base = {"metadata": {"synthetic": True}}
        habitat_request = uuid.uuid4()
        habitat_content = {
            **base, "zone_name": "Synthetic riparian strip", "habitat_type": "riparian",
            "area_ha": 2.5, "biodiversity_value": "medium", "perimeter_m": 600,
            "description": "Synthetic fixture", "gps_boundary_wkt": "POLYGON((1 1,2 1,2 2,1 2,1 1))",
        }
        habitat = call_capture(connection, operator_id, location_id, "habitat_zone", habitat_request, habitat_content)
        assert habitat["status"] == "active" and habitat["replayed"] is False
        habitat_id = habitat["record_id"]
        replay = call_capture(connection, operator_id, location_id, "habitat_zone", habitat_request, habitat_content)
        assert replay["record_id"] == habitat_id and replay["replayed"] is True
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM habitat_zone")
            assert cursor.fetchone()[0] == 1
        checks.append("habitat capture is active, replay-idempotent, and creates one source row")

        changed_habitat = dict(habitat_content, zone_name="Changed payload")
        try:
            call_capture(connection, operator_id, location_id, "habitat_zone", habitat_request, changed_habitat)
        except psycopg2.Error as exc:
            if exc.pgcode != "23505":
                raise
        else:
            raise AssertionError("changed-input request replay was not rejected")
        checks.append("request ID reuse with changed input is rejected")

        outside = dict(habitat_content, gps_boundary_wkt="POLYGON((21 21,22 21,22 22,21 22,21 21))")
        # Invoke through the authenticated role so the denial tests reach geometry validation.
        try:
            call_capture(connection, operator_id, location_id, "habitat_zone", uuid.uuid4(), outside)
        except psycopg2.Error as exc:
            if exc.pgcode != "22023":
                raise AssertionError(f"outside geometry expected 22023, got {exc.pgcode}") from exc
        else:
            raise AssertionError("geometry outside location boundary was accepted")
        invalid_geometry = dict(habitat_content, gps_boundary_wkt="POLYGON((1 1,2 2,2 1,1 2,1 1))")
        try:
            call_capture(connection, operator_id, location_id, "habitat_zone", uuid.uuid4(), invalid_geometry)
        except psycopg2.Error as exc:
            if exc.pgcode != "22023":
                raise AssertionError(f"invalid geometry expected 22023, got {exc.pgcode}") from exc
        else:
            raise AssertionError("invalid geometry was accepted")
        checks.append("habitat geometry must be valid WGS84 polygon contained by the location boundary")

        corridor_content = {
            **base, "corridor_name": "Synthetic corridor", "source_habitat_id": habitat_id,
            "target_habitat_id": None, "width_m": 12, "length_m": 100,
            "vegetation_type": "native", "notes": "Synthetic",
        }
        corridor = call_capture(connection, operator_id, location_id, "wildlife_corridor", uuid.uuid4(), corridor_content)
        with connection.cursor() as cursor:
            cursor.execute("SELECT condition, status, source_habitat_id FROM wildlife_corridor WHERE id=%s", (corridor["record_id"],))
            assert cursor.fetchone() == ("fair", "active", habitat_id)
        checks.append("corridor defaults to fair/active and accepts same-location habitat links")

        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO habitat_zone (id, location_id, zone_name, habitat_type, status) VALUES (%s,%s,'foreign','other','active')", (str(uuid.uuid4()), str(other_location_id)))
            cursor.execute("SELECT id FROM habitat_zone WHERE location_id=%s", (str(other_location_id),))
            other_habitat = cursor.fetchone()[0]
        cross_content = dict(corridor_content, source_habitat_id=str(other_habitat))
        try:
            call_capture(connection, operator_id, location_id, "wildlife_corridor", uuid.uuid4(), cross_content)
        except psycopg2.Error as exc:
            if exc.pgcode != "23514":
                raise AssertionError(f"cross-location habitat expected 23514, got {exc.pgcode}") from exc
        else:
            raise AssertionError("cross-location habitat reference was accepted")
        checks.append("corridor capture rejects habitat references belonging to another location")

        hedgerow_content = {
            **base, "hedgerow_name": "Native border", "species_mix": ["Moringa", "Buttonwood"],
            "length_m": 80, "height_m": 2.5, "age_years": 3, "planting_date": None,
            "purpose": ["windbreak"], "notes": "Synthetic",
        }
        hedgerow = call_capture(connection, operator_id, location_id, "hedgerow_record", uuid.uuid4(), hedgerow_content)
        with connection.cursor() as cursor:
            cursor.execute("SELECT condition, status FROM hedgerow_record WHERE id=%s", (hedgerow["record_id"],))
            assert cursor.fetchone() == ("fair", "active")
        checks.append("hedgerow defaults to fair/active with bounded array data")

        buffer_content = {
            **base, "habitat_zone_id": habitat_id, "check_date": None, "buffer_width_m": 3,
            "minimum_required_m": None, "vegetation_coverage_pct": 60,
            "erosion_observed": False, "notes": None,
        }
        buffer_result = call_capture(connection, operator_id, location_id, "buffer_zone_monitoring", uuid.uuid4(), buffer_content)
        with connection.cursor() as cursor:
            cursor.execute("SELECT check_date = CURRENT_DATE, compliant, status FROM buffer_zone_monitoring WHERE id=%s", (buffer_result["record_id"],))
            assert cursor.fetchone() == (True, None, "recorded")
        compliant_content = dict(buffer_content, buffer_width_m=5, minimum_required_m=3)
        compliant_result = call_capture(connection, operator_id, location_id, "buffer_zone_monitoring", uuid.uuid4(), compliant_content)
        with connection.cursor() as cursor:
            cursor.execute("SELECT compliant FROM buffer_zone_monitoring WHERE id=%s", (compliant_result["record_id"],))
            assert cursor.fetchone()[0] is True
        checks.append("buffer date defaults to current date and compliance is derived only from both widths")

        assessment_content = {
            **base, "assessment_date": None, "species_richness": 10, "shannon_index": 1.25,
            "habitat_diversity_index": 2.0, "connectivity_score": 80, "overall_score": 85,
            "assessor": "Synthetic assessor", "notes": "Synthetic",
        }
        assessment = call_capture(connection, operator_id, location_id, "landscape_biodiversity_score", uuid.uuid4(), assessment_content)
        with connection.cursor() as cursor:
            cursor.execute("SELECT assessment_date = CURRENT_DATE, status FROM landscape_biodiversity_score WHERE id=%s", (assessment["record_id"],))
            assert cursor.fetchone() == (True, "recorded")
        checks.append("biodiversity assessment date defaults to current date and remains recorded")

        unsupported = dict(assessment_content, status="published")
        try:
            call_capture(connection, operator_id, location_id, "landscape_biodiversity_score", uuid.uuid4(), unsupported)
        except psycopg2.Error as exc:
            if exc.pgcode != "22023":
                raise
        else:
            raise AssertionError("caller-supplied lifecycle field was accepted")
        checks.append("caller cannot select a lifecycle status or create verified/published records")

        try:
            call_capture(connection, other_operator_id, location_id, "habitat_zone", uuid.uuid4(), habitat_content)
        except psycopg2.Error as exc:
            if exc.pgcode != "42501":
                raise AssertionError(f"ungranted operator expected 42501, got {exc.pgcode}") from exc
        else:
            raise AssertionError("ungranted operator capture was accepted")
        checks.append("ungranted operator is denied before write")

        with connection.cursor() as cursor:
            cursor.execute("SELECT has_function_privilege('kokonut_runtime', 'kokonut_security.create_location_landscape_record(uuid,text,uuid,jsonb,text)', 'EXECUTE'), has_function_privilege('kokonut_directus_runtime', 'kokonut_security.create_location_landscape_record(uuid,text,uuid,jsonb,text)', 'EXECUTE')")
            assert cursor.fetchone() == (True, False)
            cursor.execute("SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_roles WHERE rolname='kokonut_landscape_capture_writer'")
            assert cursor.fetchone() == (False, False, False)
            cursor.execute("""SELECT
                has_column_privilege('kokonut_landscape_capture_writer', 'public.operator_identity', 'enabled', 'SELECT'),
                NOT has_column_privilege('kokonut_landscape_capture_writer', 'public.operator_identity', 'secret_label', 'SELECT'),
                has_column_privilege('kokonut_landscape_capture_writer', 'public.operator_scope_grant', 'organization_id', 'SELECT'),
                has_column_privilege('kokonut_landscape_capture_writer', 'public.location', 'organization_id', 'SELECT')""")
            assert cursor.fetchone() == (True, True, True, True)
            cursor.execute("SET ROLE kokonut_directus_runtime")
        connection.commit()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT kokonut_security.create_location_landscape_record(%s,'habitat_zone',%s,%s::jsonb,'denied')", (str(location_id), str(uuid.uuid4()), json.dumps(habitat_content)))
        except psycopg2.Error as exc:
            connection.rollback()
            if exc.pgcode != "42501":
                raise
        else:
            raise AssertionError("Directus runtime executed the Gateway capture function")
        checks.append("runtime alone can call the function; Directus cannot; writer owner is isolated and has only required authorization columns")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "disposable PostgreSQL 16 with PostGIS",
            "architecture": architecture,
            "migration": MIGRATION.name,
            "migration_replayed": True,
            "checks": checks,
            "assertions_passed": len(checks),
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "production_database_touched": False,
        }
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
    except Exception as exc:  # noqa: BLE001 - show acceptance failure.
        print(f"landscape capture disposable check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
