#!/usr/bin/env python3
"""Exercise operating-pilot summary and demand migrations on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_MIGRATION = ROOT / "schemas/postgres/461_location_scoped_operating_pilot_summary.sql"
DEMAND_MIGRATION = ROOT / "schemas/postgres/479_location_operating_pilot_demand_signals.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-037-operating-pilot-demand-disposable.json"
spec = importlib.util.spec_from_file_location(
    "sequential_decision_summary_disposable",
    ROOT / "scripts/check-sequential-decision-summary-disposable.py",
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
CREATE TABLE public.farm (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, status text NOT NULL, name text NOT NULL
);
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
CREATE TABLE public.governance_circle (id uuid PRIMARY KEY);
CREATE TABLE public.governance_role (id uuid PRIMARY KEY, circle_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE public.operating_pilot_scope (
    id uuid PRIMARY KEY, scope_type text NOT NULL, scope_id uuid NOT NULL,
    governance_circle_id uuid, status text NOT NULL
);
CREATE TABLE public.operating_capacity_profile (
    id uuid PRIMARY KEY, scope_type text NOT NULL, scope_id uuid NOT NULL,
    party_id uuid NOT NULL, period_start date NOT NULL, period_end date NOT NULL,
    status text NOT NULL,
    available_hours numeric NOT NULL, committed_hours numeric NOT NULL, protected_hours numeric NOT NULL,
    notes text
);
CREATE TABLE public.operating_demand_signal (
    id uuid PRIMARY KEY, scope_type text NOT NULL, scope_id uuid NOT NULL,
    work_type text NOT NULL, period_start date NOT NULL, period_end date NOT NULL,
    required_hours numeric NOT NULL, priority text NOT NULL, source text NOT NULL,
    source_ref uuid, description text, status text NOT NULL,
    created_by_party_id uuid, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.work_item (
    id uuid PRIMARY KEY, location_id uuid, status text NOT NULL, allocation_status text NOT NULL
);
CREATE TABLE public.work_item_claim (
    id uuid PRIMARY KEY, work_item_id uuid NOT NULL, claimant_party_id uuid NOT NULL,
    status text NOT NULL, decision_reason text
);
CREATE TABLE public.operating_competency_profile (
    id uuid PRIMARY KEY, party_id uuid NOT NULL, governance_role_id uuid, status text NOT NULL,
    current_level numeric NOT NULL, target_level numeric NOT NULL, evidence jsonb
);
CREATE TABLE public.operating_learning_plan (
    id uuid PRIMARY KEY, party_id uuid NOT NULL, scope_type text NOT NULL, scope_id uuid NOT NULL, status text NOT NULL
);
CREATE TABLE public.operating_resource_request (
    id uuid PRIMARY KEY, requested_by_party_id uuid NOT NULL, scope_type text NOT NULL,
    scope_id uuid NOT NULL, decision text NOT NULL, description text
);
CREATE TABLE public.operating_coaching_session (
    id uuid PRIMARY KEY, coachee_party_id uuid NOT NULL, scope_type text NOT NULL,
    scope_id uuid NOT NULL, privacy_level text NOT NULL, notes text
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
INSERT INTO public.farm VALUES
 ('e9000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'active', 'Synthetic Adelphi'),
 ('e9000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'active', 'Synthetic other farm');
INSERT INTO public.operator_scope_grant VALUES
 ('a1000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'read', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'read', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_organization_membership VALUES
 ('a2000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.location_tenant_owner_verification VALUES
 ('a3000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.governance_circle VALUES ('c0000000-0000-4000-8000-000000000001');
INSERT INTO public.governance_role VALUES
 ('c1000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'active');
INSERT INTO public.operating_pilot_scope VALUES
 ('c2000000-0000-4000-8000-000000000001', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'active'),
 ('c2000000-0000-4000-8000-000000000002', 'internal', 'f0000000-0000-4000-8000-000000000001', NULL, 'active');
INSERT INTO public.operating_capacity_profile
    (id, scope_type, scope_id, party_id, period_start, period_end, status,
     available_hours, committed_hours, protected_hours)
VALUES
 ('d0000000-0000-4000-8000-000000000001', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000001', CURRENT_DATE - 2, CURRENT_DATE + 2, 'submitted', 16, 8, 2),
 ('d0000000-0000-4000-8000-000000000002', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000002', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 8, 3, 1),
 ('d0000000-0000-4000-8000-000000000005', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000003', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 6, 1, 1),
 ('d0000000-0000-4000-8000-000000000003', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'd1000000-0000-4000-8000-000000000004', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 80, 4, 4),
 ('d0000000-0000-4000-8000-000000000004', 'internal', 'f0000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000005', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 100, 10, 10),
 ('d0000000-0000-4000-8000-000000000006', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000001', CURRENT_DATE + 3, CURRENT_DATE + 9, 'approved', 500, 10, 10);
INSERT INTO public.operating_demand_signal
    (id, scope_type, scope_id, work_type, period_start, period_end, required_hours,
     priority, source, source_ref, description, status, created_by_party_id, created_at)
VALUES
 ('d1000000-0000-4000-8000-000000000001', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'harvest', CURRENT_DATE - 2, CURRENT_DATE + 2, 12, 'high', 'planning', 'd2000000-0000-4000-8000-000000000001', 'PRIVATE demand narrative', 'submitted', 'd3000000-0000-4000-8000-000000000001', '2026-10-01 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000002', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'irrigation', CURRENT_DATE - 2, CURRENT_DATE + 2, 8, 'medium', 'planning', 'd2000000-0000-4000-8000-000000000002', 'PRIVATE demand narrative', 'approved', 'd3000000-0000-4000-8000-000000000002', '2026-10-02 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000003', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'other-farm', CURRENT_DATE - 2, CURRENT_DATE + 2, 50, 'critical', 'planning', 'd2000000-0000-4000-8000-000000000003', 'PRIVATE other farm', 'approved', 'd3000000-0000-4000-8000-000000000003', '2026-10-03 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000004', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'tree-care', CURRENT_DATE + 3, CURRENT_DATE + 9, 900, 'low', 'planning', 'd2000000-0000-4000-8000-000000000004', 'PRIVATE future narrative', 'draft', 'd3000000-0000-4000-8000-000000000004', '2026-10-03 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000005', 'internal', 'f0000000-0000-4000-8000-000000000001', 'internal-only', CURRENT_DATE - 2, CURRENT_DATE + 2, 1000, 'critical', 'planning', 'd2000000-0000-4000-8000-000000000005', 'PRIVATE internal narrative', 'approved', 'd3000000-0000-4000-8000-000000000005', '2026-10-04 00:00:00+00');
INSERT INTO public.work_item VALUES
 ('e0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'assigned', 'open'),
 ('e0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'in_progress', 'claimed'),
 ('e0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000002', 'assigned', 'open');
INSERT INTO public.work_item_claim (id, work_item_id, claimant_party_id, status) VALUES
 ('e1000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'e2000000-0000-4000-8000-000000000001', 'proposed'),
 ('e1000000-0000-4000-8000-000000000002', 'e0000000-0000-4000-8000-000000000002', 'e2000000-0000-4000-8000-000000000002', 'accepted'),
 ('e1000000-0000-4000-8000-000000000004', 'e0000000-0000-4000-8000-000000000002', 'e2000000-0000-4000-8000-000000000003', 'rejected'),
 ('e1000000-0000-4000-8000-000000000003', 'e0000000-0000-4000-8000-000000000003', 'e2000000-0000-4000-8000-000000000004', 'proposed');
INSERT INTO public.operating_competency_profile
    (id, party_id, governance_role_id, status, current_level, target_level)
VALUES
 ('f0000000-0000-4000-8000-000000000001', 'f1000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'submitted', 2, 3),
 ('f0000000-0000-4000-8000-000000000002', 'f1000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 'verified', 3, 3),
 ('f0000000-0000-4000-8000-000000000003', 'f1000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000001', 'verified', 1, 4);
INSERT INTO public.operating_learning_plan VALUES
 ('f1100000-0000-4000-8000-000000000001', 'f1000000-0000-4000-8000-000000000011', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'active'),
 ('f1100000-0000-4000-8000-000000000002', 'f1000000-0000-4000-8000-000000000012', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'active'),
 ('f1100000-0000-4000-8000-000000000003', 'f1000000-0000-4000-8000-000000000013', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'active'),
 ('f1100000-0000-4000-8000-000000000004', 'f1000000-0000-4000-8000-000000000014', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'active');
INSERT INTO public.operating_resource_request
    (id, requested_by_party_id, scope_type, scope_id, decision)
VALUES
 ('f2000000-0000-4000-8000-000000000001', 'f2000000-0000-4000-8000-000000000011', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending'),
 ('f2000000-0000-4000-8000-000000000002', 'f2000000-0000-4000-8000-000000000012', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending'),
 ('f2000000-0000-4000-8000-000000000003', 'f2000000-0000-4000-8000-000000000013', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending'),
 ('f2000000-0000-4000-8000-000000000004', 'f2000000-0000-4000-8000-000000000014', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'approved');
INSERT INTO public.operating_coaching_session
    (id, coachee_party_id, scope_type, scope_id, privacy_level)
VALUES
 ('f3000000-0000-4000-8000-000000000001', 'f3000000-0000-4000-8000-000000000011', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'aggregate_only'),
 ('f3000000-0000-4000-8000-000000000002', 'f3000000-0000-4000-8000-000000000012', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'aggregate_only'),
 ('f3000000-0000-4000-8000-000000000003', 'f3000000-0000-4000-8000-000000000013', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'aggregate_only'),
 ('f3000000-0000-4000-8000-000000000004', 'f3000000-0000-4000-8000-000000000014', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'private');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE summary jsonb; demand_first jsonb; demand_second jsonb;
        denied boolean := false; invalid_page boolean := false;
BEGIN
    summary := kokonut_security.location_operating_pilot_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF (summary->'work_claims'->>'proposed')::int <> 1
       OR (summary->'work_claims'->>'accepted')::int <> 1
       OR (summary->'work_claims'->>'rejected')::int <> 1 THEN
        RAISE EXCEPTION 'work claim aggregate mismatch: %', summary->'work_claims';
    END IF;
    IF summary->>'scope_configured' <> 'true'
       OR (summary->'capacity_profiles'->>'as_of_date')::date <> CURRENT_DATE
       OR (summary->'capacity_profiles'->>'submitted')::int <> 1
       OR (summary->'capacity_profiles'->>'approved')::int <> 2
       OR (summary->'capacity_profiles'->>'suppressed')::boolean
       OR (summary->'capacity_profiles'->>'available_hours')::numeric <> 30
       OR (summary->'capacity_profiles'->>'committed_hours')::numeric <> 12
       OR (summary->'demand_signals'->>'as_of_date')::date <> CURRENT_DATE
       OR (summary->'demand_signals'->>'required_hours')::numeric <> 20
       OR (summary->'work_items'->>'total')::int <> 2
       OR (summary->'work_claims'->>'proposed')::int <> 1
       OR (summary->'work_claims'->>'accepted')::int <> 1
       OR (summary->'work_claims'->>'rejected')::int <> 1
       OR (summary->'competency_reviews'->>'submitted')::int <> 1
       OR (summary->'competency_reviews'->>'verified')::int <> 2
       OR (summary->'competency_reviews'->>'open_gap')::int <> 2
       OR (summary->'learning_plans'->>'active')::int <> 3
       OR (summary->'resource_requests'->>'pending')::int <> 3
       OR (summary->'aggregate_only_coaching_sessions'->>'count')::int <> 3 THEN
        RAISE EXCEPTION 'operating pilot aggregate or exact scope mismatch: %', summary;
    END IF;
    IF summary::text ~* '(claimant|coachee|PRIVATE|notes|evidence|party_id)' THEN
        RAISE EXCEPTION 'aggregate projection leaked private operating records';
    END IF;
    demand_first := kokonut_security.location_operating_pilot_demand_signals(
        'b0000000-0000-4000-8000-000000000001', 2, 0
    );
    demand_second := kokonut_security.location_operating_pilot_demand_signals(
        'b0000000-0000-4000-8000-000000000001', 2, 2
    );
    IF demand_first->>'scope_configured' <> 'true'
       OR (demand_first->>'limit')::int <> 2
       OR (demand_first->>'offset')::int <> 0
       OR jsonb_array_length(demand_first->'items') <> 2
       OR demand_first->>'has_more' <> 'true'
       OR (demand_first->>'next_offset')::int <> 2
       OR demand_first->'items'->0->>'work_type' <> 'harvest'
       OR demand_first->'items'->1->>'work_type' <> 'irrigation'
       OR jsonb_array_length(demand_second->'items') <> 1
       OR demand_second->>'has_more' <> 'false'
       OR demand_second->'next_offset' <> 'null'::jsonb
       OR demand_second->'items'->0->>'work_type' <> 'tree-care' THEN
        RAISE EXCEPTION 'demand page, ordering, or active farm scope mismatch: %, %',
            demand_first, demand_second;
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(demand_first->'items'->0)) <> 6
       OR (demand_first::text || demand_second::text) ~*
          '(PRIVATE|demand narrative|source_ref|created_by_party_id|party_id|d1000000|d2000000|d3000000)' THEN
        RAISE EXCEPTION 'demand page exposed non-allowlisted operating data';
    END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_demand_signals(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_page := true;
    END;
    IF NOT invalid_page THEN RAISE EXCEPTION 'unbounded demand page was accepted'; END IF;
    BEGIN PERFORM kokonut_security.location_operating_pilot_summary(
        'b0000000-0000-4000-8000-000000000002'
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_demand_signals(
        'b0000000-0000-4000-8000-000000000002', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location demand context was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_summary(
        'b0000000-0000-4000-8000-000000000001'
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without tenant membership was accepted'; END IF;
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_demand_signals(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without tenant membership read demand'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.operating_capacity_profile;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read operating capacity directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_operating_pilot_summary(uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.location_operating_pilot_demand_signals(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_signal', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_summary(uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_demand_signals(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime/Directus operating pilot privilege boundary failed';
    END IF;
    IF has_table_privilege('kokonut_operating_pilot_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'UPDATE') THEN
        RAISE EXCEPTION 'operating pilot reader has identity or mutation privileges';
    END IF;
    IF NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'id', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'location_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'status', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'name', 'SELECT') THEN
        RAISE EXCEPTION 'farm mapping grants exceed required ID/location/status columns';
    END IF;
    IF has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'notes', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_competency_profile', 'evidence', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_resource_request', 'description', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_coaching_session', 'notes', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.work_item_claim', 'decision_reason', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'description', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'source_ref', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'source', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'created_by_party_id', 'SELECT') THEN
        RAISE EXCEPTION 'reader has access to private operating-pilot content';
    END IF;
    IF NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'work_type', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'priority', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'created_at', 'SELECT') THEN
        RAISE EXCEPTION 'reader is missing only the demand fields needed for the projection';
    END IF;
END $$;
"""

PRIVACY_SUPPRESSION = r"""
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE summary jsonb;
BEGIN
    DELETE FROM public.operating_capacity_profile
     WHERE id IN ('d0000000-0000-4000-8000-000000000002',
                  'd0000000-0000-4000-8000-000000000005');
    DELETE FROM public.work_item_claim
     WHERE id IN ('e1000000-0000-4000-8000-000000000002',
                  'e1000000-0000-4000-8000-000000000004');
    DELETE FROM public.operating_competency_profile
     WHERE id IN ('f0000000-0000-4000-8000-000000000002',
                  'f0000000-0000-4000-8000-000000000003');
    DELETE FROM public.operating_learning_plan
     WHERE id IN ('f1100000-0000-4000-8000-000000000002',
                  'f1100000-0000-4000-8000-000000000003');
    DELETE FROM public.operating_resource_request
     WHERE id IN ('f2000000-0000-4000-8000-000000000002',
                  'f2000000-0000-4000-8000-000000000003');
    DELETE FROM public.operating_coaching_session
     WHERE id IN ('f3000000-0000-4000-8000-000000000002',
                  'f3000000-0000-4000-8000-000000000003');
    summary := kokonut_security.location_operating_pilot_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF summary->'capacity_profiles'->>'suppressed' <> 'true'
       OR summary->'capacity_profiles'->'available_hours' <> 'null'::jsonb
       OR summary->'work_claims'->>'suppressed' <> 'true'
       OR summary->'work_claims'->'proposed' <> 'null'::jsonb
       OR summary->'competency_reviews'->>'suppressed' <> 'true'
       OR summary->'competency_reviews'->'verified' <> 'null'::jsonb
       OR summary->'learning_plans'->>'suppressed' <> 'true'
       OR summary->'learning_plans'->'active' <> 'null'::jsonb
       OR summary->'resource_requests'->>'suppressed' <> 'true'
       OR summary->'resource_requests'->'pending' <> 'null'::jsonb
       OR summary->'aggregate_only_coaching_sessions'->>'suppressed' <> 'true'
       OR summary->'aggregate_only_coaching_sessions'->'count' <> 'null'::jsonb THEN
        RAISE EXCEPTION 'small sensitive cohorts were not suppressed: %', summary;
    END IF;
END $$;
ROLLBACK;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-operating-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migrations": [SUMMARY_MIGRATION.name, DEMAND_MIGRATION.name],
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 461 and 479 apply and replay on disposable PostgreSQL 16",
            "active Adelphi farm scope maps through farm.location_id and gates exact location data",
            "work, claims, learning, competency, resource, and aggregate-only coaching counts match fixtures",
            "signed tenant context and exact operating_pilot:read are enforced",
            "other locations/internal scope and private coaching are excluded; small sensitive cohorts are suppressed",
            "demand pages are bounded and exclude IDs, narratives, source references, creators, other farms, and internal scope",
            "clean role fixture confirms no direct runtime/Directus table grants are introduced; reader has only required columns and no identity, private-content, or write access",
        ],
    }
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        summary_migration = SUMMARY_MIGRATION.read_text(encoding="utf-8")
        demand_migration = DEMAND_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, summary_migration)
        psql(docker, container, summary_migration)
        psql(docker, container, demand_migration)
        psql(docker, container, demand_migration)
        psql(docker, container, ACCEPTANCE)
        psql(docker, container, PRIVACY_SUPPRESSION)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 11
        evidence["preexisting_runtime_or_directus_grants_assessed"] = False
        print("PASS: migrations 461/479 apply/replay and all eleven disposable PostgreSQL assertions passed")
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
