#!/usr/bin/env python3
"""Exercise migration 456 on a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/456_location_scoped_business_architecture_read.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-032-business-architecture-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip().splitlines()
        summary = " | ".join(line[:180] for line in details[-8:]) or "no command output"
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]}: {summary}"
        )
    return result.stdout.strip()


def wait_ready(container: str, docker: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL 16 did not become ready")


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE SCHEMA kokonut_security;
CREATE TABLE public.location (id uuid PRIMARY KEY, organization_id uuid, status text NOT NULL);
CREATE TABLE public.organization (id uuid PRIMARY KEY, status text NOT NULL);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY, enabled boolean NOT NULL);
CREATE TABLE public.operator_scope_grant (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, organization_id uuid,
    revoked_at timestamptz
);
CREATE TABLE public.operator_organization_membership (id uuid PRIMARY KEY);
CREATE TABLE public.location_tenant_owner_verification (id uuid PRIMARY KEY);
CREATE TABLE public.location_organization_share (id uuid PRIMARY KEY);
CREATE TABLE public.party (id uuid PRIMARY KEY, display_name text NOT NULL);
CREATE TABLE public.vision_mission (
    id uuid PRIMARY KEY, entity_type text NOT NULL, entity_id uuid,
    statement_type text NOT NULL, statement_text text NOT NULL,
    effective_date date, review_date date, status text NOT NULL,
    approved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.technology_roadmap (
    id uuid PRIMARY KEY, name text NOT NULL, entity_type text NOT NULL, entity_id uuid,
    planning_horizon_start date, planning_horizon_end date, status text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.technology_roadmap_requirement (
    id uuid PRIMARY KEY, roadmap_id uuid NOT NULL, title text NOT NULL,
    description text, need_type text NOT NULL, priority smallint NOT NULL,
    strategy_map_id uuid, capability_id uuid, value_stream_id uuid,
    status text NOT NULL, evidence jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE TABLE public.business_capability (
    id uuid PRIMARY KEY, name text NOT NULL, description text,
    owner_role text, metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE public.value_stream_definition (
    id uuid PRIMARY KEY, name text NOT NULL, description text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE public.strategy_map (
    id uuid PRIMARY KEY, entity_type text NOT NULL, entity_id uuid,
    perspective text NOT NULL, statement text NOT NULL
);
CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(tenant_id uuid, location_id uuid, actor_id uuid, actor_type text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT NULLIF(current_setting('kokonut.tenant_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.location_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.actor_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.actor_type', true), '')::text
$$;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id uuid, requested_resource text,
    requested_action text, requested_location_id uuid
) RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.operator_scope_grant AS grant_row
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
    )
$$;
GRANT USAGE ON SCHEMA public TO PUBLIC;
"""


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.operator_identity VALUES
 ('a0000000-0000-4000-8000-000000000001', true),
 ('a0000000-0000-4000-8000-000000000002', true);
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001', NULL, 'active'),
 ('b0000000-0000-4000-8000-000000000002', NULL, 'active');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'business_architecture', 'read', NULL, NULL);
INSERT INTO public.business_capability VALUES
 ('c0000000-0000-4000-8000-000000000001', 'Soil stewardship', 'PRIVATE-CAPABILITY-DESCRIPTION', 'PRIVATE-CAPABILITY-OWNER', '{}');
INSERT INTO public.value_stream_definition VALUES
 ('d0000000-0000-4000-8000-000000000001', 'Regenerative production', 'PRIVATE-STREAM-DESCRIPTION', '{}');
INSERT INTO public.strategy_map VALUES
 ('e0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'internal_process', 'PRIVATE-LOCATION-STRATEGY'),
 ('e0000000-0000-4000-8000-000000000002', 'organization', 'f0000000-0000-4000-8000-000000000001', 'financial', 'PRIVATE-ORG-STRATEGY');
INSERT INTO public.technology_roadmap VALUES
 ('f1000000-0000-4000-8000-000000000001', 'Location operating model', 'location', 'b0000000-0000-4000-8000-000000000001', '2026-01-01', '2026-12-31', 'active', now()),
 ('f1000000-0000-4000-8000-000000000002', 'Private draft roadmap', 'location', 'b0000000-0000-4000-8000-000000000001', NULL, NULL, 'draft', now()),
 ('f1000000-0000-4000-8000-000000000003', 'Other location roadmap', 'location', 'b0000000-0000-4000-8000-000000000002', NULL, NULL, 'active', now());
INSERT INTO public.technology_roadmap_requirement VALUES
 ('f2000000-0000-4000-8000-000000000001', 'f1000000-0000-4000-8000-000000000001', 'Protect soil and water', 'PRIVATE-REQUIREMENT-DESCRIPTION', 'sustainability', 1, 'e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'validated', '["PRIVATE-REQUIREMENT-EVIDENCE"]'),
 ('f2000000-0000-4000-8000-000000000002', 'f1000000-0000-4000-8000-000000000001', 'Keep cross-scope strategy hidden', NULL, 'business', 2, 'e0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'proposed', '[]'),
 ('f2000000-0000-4000-8000-000000000003', 'f1000000-0000-4000-8000-000000000001', 'Retired requirement', NULL, 'business', 4, NULL, NULL, NULL, 'retired', '[]'),
 ('f2000000-0000-4000-8000-000000000004', 'f1000000-0000-4000-8000-000000000002', 'Draft roadmap requirement', NULL, 'business', 3, NULL, NULL, NULL, 'validated', '[]'),
 ('f2000000-0000-4000-8000-000000000005', 'f1000000-0000-4000-8000-000000000003', 'Other location requirement', NULL, 'business', 3, NULL, NULL, NULL, 'validated', '[]');
INSERT INTO public.vision_mission VALUES
 ('f3000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'mission', 'PRIVATE-OLD-MISSION', '2025-01-01', NULL, 'approved', '2025-01-02', '2025-01-01'),
 ('f3000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000001', 'mission', 'Restore living soils with our community.', '2026-01-01', '2027-01-01', 'approved', '2026-01-02', '2026-01-01'),
 ('f3000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000001', 'vision', 'PRIVATE-DRAFT-VISION', '2026-01-01', NULL, 'draft', NULL, '2026-01-01'),
 ('f3000000-0000-4000-8000-000000000004', 'organization', 'f0000000-0000-4000-8000-000000000001', 'mission', 'PRIVATE-ORG-MISSION', '2026-01-01', NULL, 'approved', '2026-01-02', '2026-01-01'),
 ('f3000000-0000-4000-8000-000000000005', 'location', 'b0000000-0000-4000-8000-000000000002', 'values', 'PRIVATE-OTHER-MISSION', '2026-01-01', NULL, 'approved', '2026-01-02', '2026-01-01');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    mapping_count integer;
    current_mission text;
    output_text text;
    denied boolean := false;
    cross_scope_perspective text;
BEGIN
    SELECT count(*) INTO mapping_count
      FROM kokonut_security.list_location_business_architecture_mappings(
        'b0000000-0000-4000-8000-000000000001', 50, 0
      );
    IF mapping_count <> 2 THEN
        RAISE EXCEPTION 'location mapping count did not exclude drafts, retired rows, or other locations';
    END IF;
    SELECT strategy_perspective INTO cross_scope_perspective
      FROM kokonut_security.list_location_business_architecture_mappings(
        'b0000000-0000-4000-8000-000000000001', 50, 0
      ) WHERE requirement_id = 'f2000000-0000-4000-8000-000000000002';
    IF cross_scope_perspective IS NOT NULL THEN
        RAISE EXCEPTION 'organization strategy link escaped its own scope';
    END IF;
    SELECT statement_text INTO current_mission
      FROM kokonut_security.list_location_business_architecture_missions(
        'b0000000-0000-4000-8000-000000000001'
      ) WHERE statement_type = 'mission';
    IF current_mission <> 'Restore living soils with our community.' THEN
        RAISE EXCEPTION 'latest approved location mission was not selected';
    END IF;
    SELECT COALESCE(
        (SELECT string_agg(row_to_json(mapping)::text, '|')
           FROM kokonut_security.list_location_business_architecture_mappings(
             'b0000000-0000-4000-8000-000000000001', 50, 0
           ) AS mapping), '') || '|' ||
        COALESCE((SELECT string_agg(row_to_json(mission)::text, '|')
           FROM kokonut_security.list_location_business_architecture_missions(
             'b0000000-0000-4000-8000-000000000001'
           ) AS mission), '') INTO output_text;
    IF output_text LIKE ANY (ARRAY[
        '%PRIVATE-%', '%description%', '%evidence%', '%owner_role%', '%metadata%',
        '%PRIVATE-ORG-STRATEGY%', '%PRIVATE-DRAFT-VISION%', '%PRIVATE-OLD-MISSION%'
    ]) THEN
        RAISE EXCEPTION 'business architecture projection contains excluded material';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_business_architecture_mappings(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_business_architecture_missions(
            'b0000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without business architecture grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.technology_roadmap;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read roadmap tables directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
        'kokonut_security.list_location_business_architecture_mappings(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
        'kokonut_security.list_location_business_architecture_missions(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime is missing projection execution privilege';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.technology_roadmap', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.vision_mission', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.technology_roadmap', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.list_location_business_architecture_missions(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime or Directus has unexpected business architecture access';
    END IF;
    IF has_table_privilege('kokonut_business_architecture_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_business_architecture_reader', 'public.technology_roadmap', 'UPDATE')
       OR has_table_privilege('kokonut_business_architecture_reader', 'public.vision_mission', 'INSERT') THEN
        RAISE EXCEPTION 'reader role has identity or mutation privileges';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc AS proc
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(proc.proacl, pg_catalog.acldefault('f', proc.proowner))
          ) AS privilege
         WHERE proc.oid = 'kokonut_security.list_location_business_architecture_missions(uuid)'::regprocedure
           AND privilege.grantee = 0
           AND privilege.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'projection function is executable by PUBLIC';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-business-architecture-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 456 applies and replays on disposable PostgreSQL 16",
        "only approved roadmaps and non-retired requirements from the exact location are returned",
        "only the latest approved exact-location mission statement is returned",
        "cross-scope strategy links and private narratives/evidence are excluded",
        "signed location context and exact business_architecture:read grant are enforced",
        "runtime and Directus have no direct table or Directus function access",
        "dedicated reader role is non-login, read-only, and has no party identity access",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", IMAGE])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        psql(docker, container, MIGRATION.read_text())
        psql(docker, container, MIGRATION.read_text())
        psql(docker, container, acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 7
        print("PASS: migration 456 applies/replays and all seven disposable PostgreSQL assertions passed")
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return_code = 1
    else:
        return_code = 0
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
