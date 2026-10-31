#!/usr/bin/env python3
"""Apply migrations 702/708 and verify landscape ACLs in isolated PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_MIGRATION = ROOT / "schemas/postgres/702_location_landscape_capture.sql"
BOUNDARY_MIGRATION = ROOT / "schemas/postgres/708_runtime_landscape_capture_only.sql"
IMAGE = os.environ.get("LANDSCAPE_RUNTIME_TEST_IMAGE", "postgis/postgis:16-3.4")
LOCATION = "a7080000-0000-4000-8000-000000000201"
OPERATOR = "a7080000-0000-4000-8000-000000000301"
REQUEST = "a7080000-0000-4000-8000-000000000401"
PROTECTED = (
    "habitat_zone",
    "wildlife_corridor",
    "hedgerow_record",
    "buffer_zone_monitoring",
    "landscape_biodiversity_score",
)


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]} …\n{details}"
        )
    return result


def docker_sql(container: str, statement: str, *, check: bool = True):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-A", "-t",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text="\\set VERBOSITY verbose\n" + statement,
        check=check,
    )


def last_line(result) -> str:
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise AssertionError("PostgreSQL returned no result row")
    return lines[-1]


FIXTURE = f"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
CREATE ROLE kokonut_maintenance_probe NOLOGIN;
CREATE SCHEMA kokonut_security;
CREATE TABLE organization (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE location (
    id UUID PRIMARY KEY, organization_id UUID,
    boundary geometry(POLYGON, 4326)
);
CREATE TABLE operator_identity (
    id UUID PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT TRUE, secret_label TEXT
);
CREATE TABLE operator_scope_grant (
    operator_id UUID, location_id UUID, organization_id UUID,
    resource TEXT, action TEXT, revoked_at TIMESTAMPTZ
);
CREATE TABLE operator_organization_membership (
    operator_id UUID, organization_id UUID, revoked_at TIMESTAMPTZ
);
CREATE TABLE location_tenant_owner_verification (
    location_id UUID, organization_id UUID, revoked_at TIMESTAMPTZ
);
CREATE TABLE location_organization_share (
    location_id UUID, organization_id UUID, revoked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
CREATE TABLE habitat_zone (
    id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
    zone_name VARCHAR(200) NOT NULL, habitat_type VARCHAR(100) NOT NULL,
    area_ha NUMERIC(8,2), perimeter_m NUMERIC(10,2), description TEXT,
    biodiversity_value VARCHAR(20), gps_boundary geometry, status VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{{}}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE wildlife_corridor (
    id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
    corridor_name VARCHAR(200) NOT NULL, source_habitat_id UUID REFERENCES habitat_zone(id),
    target_habitat_id UUID REFERENCES habitat_zone(id), width_m NUMERIC(8,2),
    length_m NUMERIC(10,2), vegetation_type VARCHAR(100), condition VARCHAR(50),
    last_survey_date DATE, notes TEXT, status VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{{}}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE hedgerow_record (
    id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
    hedgerow_name VARCHAR(200), species_mix JSONB DEFAULT '[]', length_m NUMERIC(10,2),
    height_m NUMERIC(5,2), age_years INTEGER, planting_date DATE, last_maintenance DATE,
    condition VARCHAR(50), purpose JSONB DEFAULT '[]', notes TEXT, status VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{{}}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE buffer_zone_monitoring (
    id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
    habitat_zone_id UUID REFERENCES habitat_zone(id), check_date DATE NOT NULL,
    buffer_width_m NUMERIC(8,2), minimum_required_m NUMERIC(8,2), compliant BOOLEAN,
    vegetation_coverage_pct NUMERIC(5,2), erosion_observed BOOLEAN DEFAULT FALSE,
    notes TEXT, status VARCHAR(50) NOT NULL, metadata JSONB DEFAULT '{{}}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE landscape_biodiversity_score (
    id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id),
    assessment_date DATE NOT NULL, species_richness INTEGER, shannon_index NUMERIC(5,3),
    habitat_diversity_index NUMERIC(5,3), connectivity_score NUMERIC(5,2),
    overall_score NUMERIC(5,2), assessor VARCHAR(200), notes TEXT,
    status VARCHAR(50) NOT NULL, metadata JSONB DEFAULT '{{}}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(actor_id UUID, location_id UUID, actor_type TEXT)
LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT nullif(current_setting('kokonut.actor_id', true), '')::uuid,
           nullif(current_setting('kokonut.location_id', true), '')::uuid,
           nullif(current_setting('kokonut.actor_type', true), '')
$$;
CREATE FUNCTION public.operator_scope_grant_allows(
    requested_operator UUID, requested_resource TEXT, requested_action TEXT,
    requested_location UUID
) RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.operator_scope_grant AS grant_row
        JOIN public.operator_identity AS identity
          ON identity.id = grant_row.operator_id AND identity.enabled
        JOIN public.location AS loc ON loc.id = grant_row.location_id
        WHERE grant_row.operator_id = requested_operator
          AND grant_row.resource = requested_resource
          AND grant_row.action = requested_action
          AND grant_row.location_id = requested_location
          AND grant_row.revoked_at IS NULL
          AND (grant_row.organization_id IS NULL OR (
            EXISTS (
                SELECT 1 FROM public.operator_organization_membership AS membership
                JOIN public.organization AS tenant
                  ON tenant.id = membership.organization_id AND tenant.status = 'active'
                WHERE membership.operator_id = grant_row.operator_id
                  AND membership.organization_id = grant_row.organization_id
                  AND membership.revoked_at IS NULL
            )
            AND EXISTS (
                SELECT 1 FROM public.location_tenant_owner_verification AS owner
                WHERE owner.location_id = loc.id
                  AND owner.organization_id = loc.organization_id
                  AND owner.revoked_at IS NULL
                  AND (owner.organization_id = grant_row.organization_id OR EXISTS (
                    SELECT 1 FROM public.location_organization_share AS share
                    WHERE share.location_id = loc.id
                      AND share.organization_id = grant_row.organization_id
                      AND share.revoked_at IS NULL
                      AND (share.expires_at IS NULL OR share.expires_at > now())
                  ))
            )
          ))
    )
$$;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON location, habitat_zone, wildlife_corridor, hedgerow_record,
       buffer_zone_monitoring, landscape_biodiversity_score
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT INSERT (id), UPDATE (zone_name), REFERENCES (id)
    ON habitat_zone TO kokonut_runtime;
GRANT INSERT (id), UPDATE (corridor_name), REFERENCES (id)
    ON wildlife_corridor TO kokonut_runtime;
GRANT INSERT (id), UPDATE (hedgerow_name), REFERENCES (id)
    ON hedgerow_record TO kokonut_runtime;
GRANT INSERT (id), UPDATE (notes), REFERENCES (id)
    ON buffer_zone_monitoring TO kokonut_runtime;
GRANT INSERT (id), UPDATE (notes), REFERENCES (id)
    ON landscape_biodiversity_score TO kokonut_runtime;
INSERT INTO location (id, boundary) VALUES ('{LOCATION}', NULL);
INSERT INTO operator_identity (id, enabled) VALUES ('{OPERATOR}', TRUE);
INSERT INTO operator_scope_grant
    (operator_id, location_id, resource, action)
VALUES ('{OPERATOR}', '{LOCATION}', 'landscape_conservation', 'create');
"""


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-landscape-runtime-{os.getpid()}-{secrets.token_hex(3)}"
    started = False
    checks: list[str] = []
    try:
        run([
            docker, "run", "--detach", "--rm", "--network", "none", "--name", container,
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
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
            time.sleep(0.25)
        else:
            raise RuntimeError("network-disabled PostgreSQL/PostGIS 16 did not become ready")

        docker_sql(container, FIXTURE)
        docker_sql(container, CAPTURE_MIGRATION.read_text(encoding="utf-8"))
        docker_sql(container, BOUNDARY_MIGRATION.read_text(encoding="utf-8"))
        docker_sql(container, BOUNDARY_MIGRATION.read_text(encoding="utf-8"))
        checks.append("migration 702 and migration 708 apply; migration 708 replay is safe")

        table_acl = last_line(docker_sql(container, f"""
            SELECT bool_and(
                has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'SELECT')
                AND NOT has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'INSERT')
                AND NOT has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'UPDATE')
                AND NOT has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'DELETE')
                AND NOT has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'TRUNCATE')
                AND NOT has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'REFERENCES')
                AND NOT has_table_privilege('kokonut_runtime', format('public.%I', relation_name), 'TRIGGER')
            ) FROM unnest(ARRAY[{', '.join(repr(name) for name in PROTECTED)}]) AS relation_name;
        """))
        if table_acl != "t":
            raise AssertionError(f"runtime table ACL did not preserve read-only access: {table_acl}")

        column_acl = last_line(docker_sql(container, f"""
            SELECT NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_attribute AS attribute
                JOIN pg_catalog.pg_class AS relation ON relation.oid = attribute.attrelid
                JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relname = ANY (ARRAY[{', '.join(repr(name) for name in PROTECTED)}])
                  AND attribute.attnum > 0 AND NOT attribute.attisdropped
                  AND (
                    has_column_privilege('kokonut_runtime', relation.oid, attribute.attnum, 'INSERT')
                    OR has_column_privilege('kokonut_runtime', relation.oid, attribute.attnum, 'UPDATE')
                    OR has_column_privilege('kokonut_runtime', relation.oid, attribute.attnum, 'REFERENCES')
                  )
            );
        """))
        if column_acl != "t":
            raise AssertionError("runtime retains column-level INSERT/UPDATE/REFERENCES")
        checks.append("runtime retains SELECT on all five source tables and has no table or column DML")

        preserved_acl = last_line(docker_sql(container, f"""
            SELECT bool_and(
                has_table_privilege('kokonut_directus_runtime', format('public.%I', relation_name), 'INSERT')
                AND has_table_privilege('kokonut_directus_runtime', format('public.%I', relation_name), 'UPDATE')
                AND has_table_privilege('kokonut_directus_runtime', format('public.%I', relation_name), 'DELETE')
                AND has_table_privilege('kokonut_maintenance_probe', format('public.%I', relation_name), 'INSERT')
                AND has_table_privilege('kokonut_maintenance_probe', format('public.%I', relation_name), 'UPDATE')
                AND has_table_privilege('kokonut_maintenance_probe', format('public.%I', relation_name), 'DELETE')
            ) FROM unnest(ARRAY[{', '.join(repr(name) for name in PROTECTED)}]) AS relation_name;
        """))
        if preserved_acl != "t":
            raise AssertionError("migration 708 changed Directus or maintenance DML grants")

        writer_acl = last_line(docker_sql(container, """
            SELECT has_column_privilege('kokonut_landscape_capture_writer', 'public.habitat_zone', 'id', 'INSERT')
               AND has_column_privilege('kokonut_landscape_capture_writer', 'public.wildlife_corridor', 'id', 'INSERT')
               AND has_column_privilege('kokonut_landscape_capture_writer', 'public.hedgerow_record', 'id', 'INSERT')
               AND has_column_privilege('kokonut_landscape_capture_writer', 'public.buffer_zone_monitoring', 'id', 'INSERT')
               AND has_column_privilege('kokonut_landscape_capture_writer', 'public.landscape_biodiversity_score', 'id', 'INSERT')
               AND has_column_privilege('kokonut_landscape_capture_writer', 'public.habitat_zone', 'id', 'UPDATE')
               AND NOT has_table_privilege('kokonut_landscape_capture_writer', 'public.habitat_zone', 'DELETE');
        """))
        if writer_acl != "t":
            raise AssertionError("migration-702 writer-owner privileges changed")
        checks.append("migration-702 bounded writer-owner insert/lock privileges remain intact")

        create_call = f"""
            BEGIN;
            SET LOCAL ROLE kokonut_runtime;
            SELECT set_config('kokonut.actor_id', '{OPERATOR}', TRUE);
            SELECT set_config('kokonut.location_id', '{LOCATION}', TRUE);
            SELECT set_config('kokonut.actor_type', 'operator', TRUE);
            SELECT kokonut_security.create_location_landscape_record(
                '{LOCATION}', 'habitat_zone', '{REQUEST}',
                '{{"zone_name":"Synthetic runtime acceptance","habitat_type":"riparian",'
                '"area_ha":1.25,"metadata":{{"synthetic":true}}}}'::jsonb,
                'Synthetic ACL acceptance'
            )::TEXT;
            COMMIT;
        """
        capture = json.loads(last_line(docker_sql(container, create_call)))
        if capture.get("status") != "active" or capture.get("replayed") is not False:
            raise AssertionError(f"Gateway capture function returned unexpected result: {capture!r}")
        replay = json.loads(last_line(docker_sql(container, create_call)))
        if replay.get("record_id") != capture.get("record_id") or replay.get("replayed") is not True:
            raise AssertionError("Gateway capture did not remain idempotent after migration 708")
        row_count = last_line(docker_sql(container, "SELECT count(*) FROM public.habitat_zone"))
        if row_count != "1":
            raise AssertionError("Gateway capture replay duplicated the source row")
        checks.append("runtime can still create and replay a signed, exact-location Gateway capture")

        report = {
            "result": "passed",
            "migration": BOUNDARY_MIGRATION.name,
            "database": "network-disabled disposable PostgreSQL 16/PostGIS container; no host port",
            "migration_702_applied": True,
            "migration_708_applied_and_replayed": True,
            "checks": checks,
            "assertions_passed": len(checks),
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "production_database_touched": False,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - disposable acceptance should expose failures.
        print(f"landscape runtime boundary check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1)
