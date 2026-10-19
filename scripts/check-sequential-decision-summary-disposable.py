#!/usr/bin/env python3
"""Exercise migration 460 on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/460_location_scoped_sequential_decision_summary.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-036-sequential-decision-disposable.json"
spec = importlib.util.spec_from_file_location(
    "solution_lifecycle_summary_disposable",
    ROOT / "scripts/check-solution-lifecycle-summary-disposable.py",
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
CREATE TABLE public.organization (id uuid PRIMARY KEY, status text NOT NULL);
CREATE TABLE public.operator_scope_grant (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, organization_id uuid, revoked_at timestamptz
);
CREATE TABLE public.location_tenant_owner_verification (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, organization_id uuid NOT NULL, revoked_at timestamptz
);
CREATE TABLE public.location_organization_share (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, organization_id uuid NOT NULL,
    revoked_at timestamptz, expires_at timestamptz
);
CREATE TABLE public.operator_organization_membership (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, organization_id uuid NOT NULL, revoked_at timestamptz
);
CREATE TABLE public.strategy_plan (
    id uuid PRIMARY KEY, scope_type text NOT NULL, scope_id uuid NOT NULL
);
CREATE TABLE public.threat (id uuid PRIMARY KEY, location_id uuid NOT NULL);
CREATE TABLE public.solution (
    id uuid PRIMARY KEY, originating_scope_type text, originating_scope_id uuid
);
CREATE TABLE public.solution_link (
    id uuid PRIMARY KEY, solution_id uuid NOT NULL, entity_type text NOT NULL, entity_id uuid NOT NULL
);
CREATE TABLE public.decision_hypothesis (
    id uuid PRIMARY KEY, subject_type text NOT NULL, subject_id uuid NOT NULL, status text NOT NULL,
    statement text, alternative_statement text
);
CREATE TABLE public.decision_evidence_event (
    id uuid PRIMARY KEY, hypothesis_id uuid NOT NULL, quality_status text NOT NULL,
    source_ref text, value jsonb, likelihood_hypothesis numeric, likelihood_alternative numeric
);
CREATE TABLE public.decision_posterior_update (
    id uuid PRIMARY KEY, hypothesis_id uuid NOT NULL, evidence_event_id uuid NOT NULL
);
CREATE TABLE public.decision_threshold_evaluation (
    id uuid PRIMARY KEY, hypothesis_id uuid NOT NULL, action text NOT NULL, evaluated_at timestamptz NOT NULL
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
                          AND (owner.organization_id = grant_row.organization_id OR EXISTS (
                              SELECT 1 FROM public.location_organization_share AS share
                               WHERE share.location_id = loc.id
                                 AND share.organization_id = grant_row.organization_id
                                 AND share.revoked_at IS NULL
                                 AND (share.expires_at IS NULL OR share.expires_at > NOW())
                          ))
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
INSERT INTO public.organization VALUES ('f0000000-0000-4000-8000-000000000001', 'active');
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001'),
 ('b0000000-0000-4000-8000-000000000002', NULL);
INSERT INTO public.operator_scope_grant VALUES
 ('a1000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'sequential_evidence', 'read', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'sequential_evidence', 'read', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_organization_membership VALUES
 ('a2000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.location_tenant_owner_verification VALUES
 ('a3000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.strategy_plan VALUES
 ('c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001'),
 ('c0000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000002');
INSERT INTO public.threat VALUES
 ('c1000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001'),
 ('c1000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002');
INSERT INTO public.solution VALUES
 ('c2000000-0000-4000-8000-000000000001', NULL, NULL),
 ('c2000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000002');
INSERT INTO public.solution_link VALUES
 ('c3000000-0000-4000-8000-000000000001', 'c2000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001'),
 ('c3000000-0000-4000-8000-000000000002', 'c2000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000002');
INSERT INTO public.decision_hypothesis VALUES
 ('d0000000-0000-4000-8000-000000000001', 'strategy_plan', 'c0000000-0000-4000-8000-000000000001', 'active', 'SECRET CLAIM', 'SECRET ALTERNATIVE'),
 ('d0000000-0000-4000-8000-000000000002', 'threat', 'c1000000-0000-4000-8000-000000000001', 'resolved', 'PRIVATE THREAT CLAIM', 'PRIVATE THREAT ALTERNATIVE'),
 ('d0000000-0000-4000-8000-000000000003', 'solution', 'c2000000-0000-4000-8000-000000000001', 'draft', 'PRIVATE SOLUTION CLAIM', 'PRIVATE SOLUTION ALTERNATIVE'),
 ('d0000000-0000-4000-8000-000000000004', 'strategy_plan', 'c0000000-0000-4000-8000-000000000002', 'active', 'OTHER LOCATION', 'OTHER LOCATION ALT'),
 ('d0000000-0000-4000-8000-000000000005', 'unscoped', 'c0000000-0000-4000-8000-000000000001', 'active', 'UNSCOPED', 'UNSCOPED ALT');
INSERT INTO public.decision_evidence_event VALUES
 ('e0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'verified', 'PRIVATE REF', '{"secret":"PRIVATE VALUE"}', 0.9, 0.1),
 ('e0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'rejected', 'PRIVATE REF 2', '{}', NULL, NULL),
 ('e0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000002', 'provisional', 'PRIVATE REF 3', '{}', NULL, NULL),
 ('e0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000004', 'verified', 'OTHER LOCATION', '{}', NULL, NULL),
 ('e0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000005', 'verified', 'UNSCOPED', '{}', NULL, NULL);
INSERT INTO public.decision_posterior_update VALUES
 ('e1000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001'),
 ('e1000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000002', 'e0000000-0000-4000-8000-000000000003'),
 ('e1000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000004', 'e0000000-0000-4000-8000-000000000004');
INSERT INTO public.decision_threshold_evaluation VALUES
 ('e2000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'act', '2026-10-01'),
 ('e2000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'continue', '2026-10-02'),
 ('e2000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000002', 'insufficient_evidence', '2026-10-03'),
 ('e2000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000004', 'act', '2026-10-04');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE summary jsonb; denied boolean := false;
BEGIN
    summary := kokonut_security.location_sequential_decision_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF (summary->>'hypothesis_count')::int <> 3
       OR (summary->'hypothesis_status_counts'->>'active')::int <> 1
       OR (summary->'hypothesis_status_counts'->>'resolved')::int <> 1
       OR (summary->'hypothesis_status_counts'->>'draft')::int <> 1
       OR (summary->>'evidence_event_count')::int <> 3
       OR (summary->'evidence_quality_counts'->>'verified')::int <> 1
       OR (summary->'evidence_quality_counts'->>'provisional')::int <> 1
       OR (summary->'evidence_quality_counts'->>'rejected')::int <> 1
       OR (summary->>'applied_evidence_event_count')::int <> 2
       OR (summary->>'posterior_update_count')::int <> 2
       OR (summary->'latest_decision_action_counts'->>'continue')::int <> 1
       OR (summary->'latest_decision_action_counts'->>'insufficient_evidence')::int <> 1 THEN
        RAISE EXCEPTION 'sequential decision aggregate or location lineage mismatch: %', summary;
    END IF;
    IF summary::text ~* '(SECRET|PRIVATE|UNSCOPED|OTHER LOCATION)' THEN
        RAISE EXCEPTION 'projection leaked a narrative, source reference, or unscoped record';
    END IF;
    BEGIN PERFORM kokonut_security.location_sequential_decision_summary(
        'b0000000-0000-4000-8000-000000000002'
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN PERFORM kokonut_security.location_sequential_decision_summary(
        'b0000000-0000-4000-8000-000000000001'
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without tenant membership was accepted'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.decision_hypothesis;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read decision hypotheses directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_sequential_decision_summary(uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.decision_hypothesis', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.decision_hypothesis', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_sequential_decision_summary(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime/Directus sequential decision privilege boundary failed';
    END IF;
    IF has_table_privilege('kokonut_sequential_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_sequential_reader', 'public.decision_hypothesis', 'UPDATE') THEN
        RAISE EXCEPTION 'sequential reader has identity or mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-sequential-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 460 applies and replays on disposable PostgreSQL 16",
            "strategy, threat, and solution hypotheses include only exact location lineage",
            "evidence quality, posterior updates, and latest decisions match fixtures",
            "signed tenant context and exact sequential_evidence:read are enforced",
            "private statement, source, value, likelihood, and unscoped records are omitted",
            "runtime and Directus lack direct ledger access; reader has no write or identity access",
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
        print("PASS: migration 460 applies/replays and all six disposable PostgreSQL assertions passed")
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
