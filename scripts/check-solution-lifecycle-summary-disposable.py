#!/usr/bin/env python3
"""Exercise migration 459 on a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/459_location_scoped_solution_lifecycle_summary.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json"
spec = importlib.util.spec_from_file_location(
    "coordination_summary_disposable", ROOT / "scripts/check-coordination-summary-disposable.py"
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
CREATE TABLE public.party (id uuid PRIMARY KEY, display_name text NOT NULL);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY, enabled boolean NOT NULL);
CREATE TABLE public.location (id uuid PRIMARY KEY, organization_id uuid);
CREATE TABLE public.location_tenant_owner_verification (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, organization_id uuid NOT NULL,
    revoked_at timestamptz
);
CREATE TABLE public.location_organization_share (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, organization_id uuid NOT NULL,
    revoked_at timestamptz, expires_at timestamptz
);
CREATE TABLE public.operator_organization_membership (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, organization_id uuid NOT NULL,
    revoked_at timestamptz
);
CREATE TABLE public.organization (id uuid PRIMARY KEY, status text NOT NULL);
CREATE TABLE public.operator_scope_grant (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, organization_id uuid, revoked_at timestamptz
);
CREATE TABLE public.solution (
    id uuid PRIMARY KEY, originating_scope_type text, originating_scope_id uuid,
    current_stage text NOT NULL, status text NOT NULL
);
CREATE TABLE public.solution_link (
    id uuid PRIMARY KEY, solution_id uuid NOT NULL, entity_type text NOT NULL
        CHECK (entity_type IN ('opportunity', 'strategy_plan', 'strategy_choice', 'strategy_investment',
        'technology_alternative', 'experiment', 'funding_case', 'pilot', 'adoption_program',
        'scale_gate', 'artifact', 'evidence')),
    entity_id uuid NOT NULL
);
CREATE TABLE public.solution_stage_gate (id uuid PRIMARY KEY, solution_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.solution_gate_evaluation (
    id uuid PRIMARY KEY, gate_id uuid NOT NULL, passed boolean NOT NULL, evaluated_at timestamptz NOT NULL
);
CREATE TABLE public.solution_experiment (id uuid PRIMARY KEY, solution_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.solution_experiment_result (id uuid PRIMARY KEY, experiment_id uuid NOT NULL, outcome text NOT NULL);
CREATE TABLE public.solution_replication (id uuid PRIMARY KEY, solution_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.solution_funding_case (id uuid PRIMARY KEY, solution_id uuid NOT NULL, decision_status text NOT NULL);
CREATE TABLE public.solution_funding_tranche (id uuid PRIMARY KEY, funding_case_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.solution_adoption_program (
    id uuid PRIMARY KEY, solution_id uuid NOT NULL, target_scope_type text NOT NULL,
    target_scope_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.solution_configuration (
    id uuid PRIMARY KEY, solution_id uuid NOT NULL, scope_type text NOT NULL,
    scope_id uuid NOT NULL, approval_status text NOT NULL
);
CREATE TABLE public.solution_adopter_readiness (
    id uuid PRIMARY KEY, solution_id uuid NOT NULL, adopter_scope_type text NOT NULL,
    adopter_scope_id uuid NOT NULL, readiness_status text NOT NULL
);
CREATE TABLE public.solution_scale_gate (
    id uuid PRIMARY KEY, solution_id uuid NOT NULL, scope_type text NOT NULL,
    scope_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.solution_learning_record (id uuid PRIMARY KEY, solution_id uuid NOT NULL, decision_status text NOT NULL);
CREATE TABLE public.solution_retirement (id uuid PRIMARY KEY, solution_id uuid NOT NULL, status text NOT NULL);
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
         JOIN public.operator_identity AS identity
           ON identity.id = grant_row.operator_id AND identity.enabled
         JOIN public.location AS loc ON loc.id = grant_row.location_id
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
           AND (
               grant_row.organization_id IS NULL
               OR (
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
                          AND (
                              owner.organization_id = grant_row.organization_id
                              OR EXISTS (
                                  SELECT 1 FROM public.location_organization_share AS share
                                   WHERE share.location_id = loc.id
                                     AND share.organization_id = grant_row.organization_id
                                     AND share.revoked_at IS NULL
                                     AND (share.expires_at IS NULL OR share.expires_at > NOW())
                              )
                          )
                   )
               )
           )
    )
$$;
GRANT USAGE ON SCHEMA public TO PUBLIC;
"""

ACCEPTANCE = r"""
INSERT INTO public.operator_identity VALUES
 ('a0000000-0000-4000-8000-000000000001', true),
 ('a0000000-0000-4000-8000-000000000002', true);
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001'),
 ('b0000000-0000-4000-8000-000000000002', NULL);
INSERT INTO public.organization VALUES
 ('f0000000-0000-4000-8000-000000000001', 'active');
INSERT INTO public.operator_scope_grant VALUES
 ('a1000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'read', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'read', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_organization_membership VALUES
 ('a2000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.location_tenant_owner_verification VALUES
 ('a3000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.solution VALUES
 ('c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'testing', 'active'),
 ('c0000000-0000-4000-8000-000000000002', NULL, NULL, 'validated', 'active'),
 ('c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000002', 'funded', 'active'),
 ('c0000000-0000-4000-8000-000000000004', 'organization', 'f0000000-0000-4000-8000-000000000001', 'discovered', 'active'),
 ('c0000000-0000-4000-8000-000000000005', 'location', 'b0000000-0000-4000-8000-000000000001', 'paused', 'paused');
INSERT INTO public.solution_link VALUES
 ('d0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000001'),
 ('d0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000002');
INSERT INTO public.solution_stage_gate VALUES
 ('e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'approved'),
 ('e0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000002', 'draft');
INSERT INTO public.solution_gate_evaluation VALUES
 ('e1000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', true, '2026-10-01'),
 ('e1000000-0000-4000-8000-000000000002', 'e0000000-0000-4000-8000-000000000002', false, '2026-10-02');
INSERT INTO public.solution_experiment VALUES
 ('f0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'active'),
 ('f0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', 'active');
INSERT INTO public.solution_experiment_result VALUES
 ('f1000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', 'validated'),
 ('f1000000-0000-4000-8000-000000000002', 'f0000000-0000-4000-8000-000000000002', 'validated');
INSERT INTO public.solution_replication VALUES
 ('f2000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'proposed');
INSERT INTO public.solution_funding_case VALUES
 ('f3000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'submitted');
INSERT INTO public.solution_adoption_program VALUES
 ('f4000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'active'),
 ('f4000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000002', 'active');
INSERT INTO public.solution_configuration VALUES
 ('f5000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'approved');
INSERT INTO public.solution_adopter_readiness VALUES
 ('f6000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'ready');
INSERT INTO public.solution_scale_gate VALUES
 ('f7000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'passed');
INSERT INTO public.solution_learning_record VALUES
 ('f8000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'accepted');
INSERT INTO public.solution_retirement VALUES
 ('f9000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'proposed');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE summary jsonb; denied boolean := false;
BEGIN
    summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF (summary->>'solution_count')::int <> 3
       OR (summary->'stage_counts'->>'testing')::int <> 1
       OR (summary->'stage_counts'->>'validated')::int <> 1
       OR (summary->'stage_counts'->>'paused')::int <> 1
       OR (summary->'stage_counts'->>'funded')::int <> 0
       OR (summary->'stage_gate_status_counts'->>'approved')::int <> 1
       OR (summary->'stage_gate_status_counts'->>'draft')::int <> 1
       OR (summary->'latest_gate_evaluation_counts'->>'passed')::int <> 1
       OR (summary->'latest_gate_evaluation_counts'->>'failed')::int <> 1
       OR (summary->'experiment_status_counts'->>'active')::int <> 1
       OR (summary->'experiment_result_counts'->>'validated')::int <> 1
       OR (summary->'funding_decision_counts'->>'submitted')::int <> 1
       OR (summary->'adoption_program_status_counts'->>'active')::int <> 1
       OR (summary->'configuration_approval_counts'->>'approved')::int <> 1
       OR (summary->'adopter_readiness_counts'->>'ready')::int <> 1
       OR (summary->'scale_gate_status_counts'->>'passed')::int <> 1
       OR (summary->'learning_decision_counts'->>'accepted')::int <> 1
       OR (summary->'retirement_status_counts'->>'proposed')::int <> 1 THEN
        RAISE EXCEPTION 'solution lifecycle aggregates or location scope mismatch: %', summary;
    END IF;
    IF summary::text ~* '(canonical_key|problem_statement|rationale|evidence|party_id|amount)' THEN
        RAISE EXCEPTION 'aggregate projection leaked private narrative, identity, evidence, or funding data';
    END IF;
    BEGIN
        PERFORM kokonut_security.location_solution_lifecycle_summary(
            'b0000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM kokonut_security.location_solution_lifecycle_summary(
            'b0000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read grant was accepted'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read solution tables directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_solution_lifecycle_summary(uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_solution_lifecycle_summary(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime/Directus solution privilege boundary failed';
    END IF;
    IF has_table_privilege('kokonut_solution_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution', 'UPDATE') THEN
        RAISE EXCEPTION 'solution reader has identity or mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solutions-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 459 applies and replays on disposable PostgreSQL 16",
            "location associations accept exact location links and exclude other scopes",
            "stage gates, evaluations, experiments, funding decisions, adoption, scale, learning, and retirement aggregates match fixtures",
            "signed location context and exact solution_lifecycle:read grant are enforced",
            "runtime and Directus lack direct solution table/function access",
            "reader role is non-login, read-only, and has no identity access",
        ],
    }
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 6
        print("PASS: migration 459 applies/replays and all six disposable PostgreSQL assertions passed")
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
