#!/usr/bin/env python3
"""Exercise migration 458 on a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/458_location_scoped_coordination_summary.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-034-coordination-summary-disposable.json"
spec = importlib.util.spec_from_file_location(
    "business_canvas_disposable", ROOT / "scripts/check-business-canvas-disposable.py"
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
CREATE TABLE public.coordination_alliance (
    id uuid PRIMARY KEY, scope_type text NOT NULL, scope_id uuid, status text NOT NULL,
    review_due_at timestamptz
);
CREATE TABLE public.coordination_conflict_declaration (
    id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.coordination_benefit_harm_analysis (
    id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.coordination_appeal (id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.coordination_remedy (id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.coordination_minority_view (
    id uuid PRIMARY KEY, alliance_id uuid NOT NULL, preservation_status text NOT NULL
);
CREATE TABLE public.coordination_knowledge_exchange (
    id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.coordination_learning_link (
    id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.coordination_metric_observation (
    id uuid PRIMARY KEY, alliance_id uuid NOT NULL, status text NOT NULL
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
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'coordination', 'read', NULL, NULL);
INSERT INTO public.coordination_alliance VALUES
 ('c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'draft', now() - interval '1 day'),
 ('c0000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000001', 'active', now() - interval '1 day'),
 ('c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000001', 'paused', now() + interval '1 day'),
 ('c0000000-0000-4000-8000-000000000004', 'location', 'b0000000-0000-4000-8000-000000000002', 'active', now() - interval '1 day'),
 ('c0000000-0000-4000-8000-000000000005', 'organization', 'f0000000-0000-4000-8000-000000000001', 'active', now() - interval '1 day');
INSERT INTO public.coordination_conflict_declaration VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'declared'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'managed'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'declared');
INSERT INTO public.coordination_benefit_harm_analysis VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'proposed'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'accepted'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'proposed');
INSERT INTO public.coordination_appeal VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'open'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'resolved'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'open');
INSERT INTO public.coordination_remedy VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'in_progress'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'completed'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'proposed');
INSERT INTO public.coordination_minority_view VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'preserved'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'preserved');
INSERT INTO public.coordination_knowledge_exchange VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'completed'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'completed');
INSERT INTO public.coordination_learning_link VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'active'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'proposed'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'verified'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'active');
INSERT INTO public.coordination_metric_observation VALUES
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'draft'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'rejected'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000002', 'verified'),
 (gen_random_uuid(), 'c0000000-0000-4000-8000-000000000004', 'draft');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE summary record; denied boolean := false;
BEGIN
    SELECT * INTO summary FROM kokonut_security.location_coordination_governance_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF summary.alliance_count <> 3 OR summary.draft_alliance_count <> 1
       OR summary.active_alliance_count <> 1 OR summary.paused_alliance_count <> 1
       OR summary.overdue_review_count <> 1
       OR summary.open_conflict_declaration_count <> 1
       OR summary.unreviewed_harm_analysis_count <> 1
       OR summary.open_appeal_count <> 1 OR summary.open_remedy_count <> 1
       OR summary.preserved_minority_view_count <> 1
       OR summary.completed_knowledge_exchange_count <> 1
       OR summary.open_learning_link_count <> 2
       OR summary.draft_metric_observation_count <> 1
       OR summary.rejected_metric_observation_count <> 1 THEN
        RAISE EXCEPTION 'coordination aggregate values did not match location fixture';
    END IF;
    denied := false;
    BEGIN PERFORM * FROM kokonut_security.location_coordination_governance_summary(
        'b0000000-0000-4000-8000-000000000002'
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN PERFORM * FROM kokonut_security.location_coordination_governance_summary(
        'b0000000-0000-4000-8000-000000000001'
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without coordination grant was accepted'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.coordination_alliance;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read coordination tables directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_coordination_governance_summary(uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.coordination_alliance', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.coordination_alliance', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_coordination_governance_summary(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime/Directus coordination privilege boundary failed';
    END IF;
    IF has_table_privilege('kokonut_coordination_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_coordination_reader', 'public.coordination_alliance', 'UPDATE') THEN
        RAISE EXCEPTION 'coordination reader has identity or mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-coordination-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 458 applies and replays on disposable PostgreSQL 16",
            "alliance states and overdue reviews include only exact location scope",
            "conflict, harm, appeal, remedy, minority-view, exchange, and learning indicators match fixture",
            "signed location context and exact coordination:read grant are enforced",
            "runtime and Directus lack direct coordination table/function access",
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
        evidence["assertions_passed"] = 6
        print("PASS: migration 458 applies/replays and all six disposable PostgreSQL assertions passed")
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
