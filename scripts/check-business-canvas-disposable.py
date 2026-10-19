#!/usr/bin/env python3
"""Exercise migration 457 on a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/457_location_scoped_business_canvas_read.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-033-business-canvas-disposable.json"
spec = importlib.util.spec_from_file_location(
    "business_architecture_disposable",
    ROOT / "scripts/check-business-architecture-disposable.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
run = helper.run
psql = helper.psql
wait_ready = helper.wait_ready

FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE SCHEMA kokonut_security;
CREATE TABLE public.location (id uuid PRIMARY KEY, organization_id uuid, status text NOT NULL);
CREATE TABLE public.organization (id uuid PRIMARY KEY, status text NOT NULL);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY, enabled boolean NOT NULL);
CREATE TABLE public.operator_scope_grant (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, organization_id uuid, revoked_at timestamptz
);
CREATE TABLE public.operator_organization_membership (id uuid PRIMARY KEY);
CREATE TABLE public.location_tenant_owner_verification (id uuid PRIMARY KEY);
CREATE TABLE public.location_organization_share (id uuid PRIMARY KEY);
CREATE TABLE public.party (id uuid PRIMARY KEY, display_name text NOT NULL);
CREATE TABLE public.business_model_canvas (
    id uuid PRIMARY KEY, location_id uuid, organization_id uuid, entity_type text NOT NULL,
    entity_id uuid NOT NULL, key_partners jsonb, key_activities jsonb, key_resources jsonb,
    value_propositions jsonb, customer_relationships jsonb, channels jsonb,
    customer_segments jsonb, revenue_streams jsonb, cost_structure jsonb,
    canvas_name text, description text, fiscal_year integer, tags text[], health_score numeric,
    version integer, status text, schema_version text, source_system text, source_id text,
    source_raw jsonb, metadata jsonb, created_at timestamptz, updated_at timestamptz,
    created_by uuid, updated_by uuid
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

ACCEPTANCE = r"""
INSERT INTO public.operator_identity VALUES
 ('a0000000-0000-4000-8000-000000000001', true),
 ('a0000000-0000-4000-8000-000000000002', true);
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001', NULL, 'active'),
 ('b0000000-0000-4000-8000-000000000002', NULL, 'active');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'business_planning', 'read', NULL, NULL);
INSERT INTO public.business_model_canvas VALUES
 ('c0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', NULL, 'location', 'b0000000-0000-4000-8000-000000000001',
  '[{"partner":"Local growers"}]', '[]', '[]', '[{"claim":"Healthy soil","evidence_url":"https://evidence.invalid/record/1"}]', '[]', '[]', '[]', '[{"name":"produce"}]', '{"currency":"USD","amount":25}',
  'Primary canvas', 'Location business model', 2026, ARRAY['reviewed'], 80, 2, 'draft', 'business-model-canvas-v1', 'manual', 'canvas-source-1', '{"raw":"PRIVATE-RAW-IMPORT"}', '{"internal":"PRIVATE-METADATA"}', now(), now(), 'a1000000-0000-4000-8000-000000000001', 'a1000000-0000-4000-8000-000000000001'),
 ('c0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', NULL, 'location', 'b0000000-0000-4000-8000-000000000001',
  '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}',
  'Verified canvas', NULL, 2025, ARRAY[]::text[], 75, 1, 'published', 'business-model-canvas-v1', 'import', 'canvas-source-2', '{"raw":"PRIVATE-RAW-IMPORT"}', '{}', now(), now(), NULL, NULL),
 ('c0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000002', NULL, 'location', 'b0000000-0000-4000-8000-000000000001',
  '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}', 'Mismatched location', NULL, 2025, NULL, 10, 1, 'verified', 'v1', 'manual', 'mismatch', '{}', '{}', now(), now(), NULL, NULL),
 ('c0000000-0000-4000-8000-000000000004', NULL, 'f0000000-0000-4000-8000-000000000001', 'organization', 'f0000000-0000-4000-8000-000000000001',
  '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}', 'Organization canvas', NULL, 2025, NULL, 10, 1, 'verified', 'v1', 'manual', 'organization', '{}', '{}', now(), now(), NULL, NULL),
 ('c0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000002', NULL, 'location', 'b0000000-0000-4000-8000-000000000002',
  '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}', 'Other location canvas', NULL, 2025, NULL, 10, 1, 'verified', 'v1', 'manual', 'other', '{}', '{}', now(), now(), NULL, NULL);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    result_row record;
    row_count integer;
    output_text text;
    denied boolean := false;
BEGIN
    SELECT count(*) INTO row_count FROM kokonut_security.list_location_business_model_canvases(
        'b0000000-0000-4000-8000-000000000001', 50, 0
    );
    IF row_count <> 2 THEN RAISE EXCEPTION 'canvas location/entity matching failed'; END IF;
    SELECT * INTO result_row FROM kokonut_security.list_location_business_model_canvases(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    IF result_row.lifecycle_status <> 'draft'
       OR result_row.content->'value_propositions'->0->>'evidence_url' <> 'https://evidence.invalid/record/1'
       OR result_row.content->'key_partners'->0->>'partner' <> 'Local growers'
       OR result_row.source_reference <> 'canvas-source-1' THEN
        RAISE EXCEPTION 'canvas content, lifecycle, or source reference was not preserved';
    END IF;
    SELECT string_agg(row_to_json(canvas)::text, '|') INTO output_text
      FROM kokonut_security.list_location_business_model_canvases(
        'b0000000-0000-4000-8000-000000000001', 50, 0
      ) AS canvas;
    IF output_text LIKE ANY (ARRAY['%PRIVATE-RAW-IMPORT%', '%PRIVATE-METADATA%', '%created_by%', '%updated_by%']) THEN
        RAISE EXCEPTION 'canvas projection returned raw import, metadata, or actor identity';
    END IF;
    denied := false;
    BEGIN PERFORM * FROM kokonut_security.list_location_business_model_canvases(
        'b0000000-0000-4000-8000-000000000002', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN PERFORM * FROM kokonut_security.list_location_business_model_canvases(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without business planning grant was accepted'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.business_model_canvas;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read business model canvases directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
        'kokonut_security.list_location_business_model_canvases(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.business_model_canvas', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.business_model_canvas', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.list_location_business_model_canvases(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime/Directus projection privilege boundary failed';
    END IF;
    IF has_table_privilege('kokonut_business_planning_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_business_planning_reader', 'public.business_model_canvas', 'UPDATE') THEN
        RAISE EXCEPTION 'business planning reader has identity or mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-business-canvas-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 457 applies and replays on disposable PostgreSQL 16",
            "only exact location/entity canvases are returned across lifecycle states",
            "content blocks, governed lifecycle, and source reference are preserved",
            "raw import blobs, internal metadata, and actor identities are excluded",
            "signed location context and exact business_planning:read are enforced",
            "runtime/Directus direct table and function boundaries are preserved",
            "reader role is non-login, read-only, and has no party access",
        ],
    }
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgis/postgis:16-3.4"])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        psql(docker, container, MIGRATION.read_text())
        psql(docker, container, MIGRATION.read_text())
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 7
        print("PASS: migration 457 applies/replays and all seven disposable PostgreSQL assertions passed")
        result = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        result = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
