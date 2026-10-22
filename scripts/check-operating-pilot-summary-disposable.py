#!/usr/bin/env python3
"""Exercise operating-pilot projections, drafts, and review reads on disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
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
CAPACITY_MIGRATION = ROOT / "schemas/postgres/480_location_operating_pilot_capacity_periods.sql"
WORK_CLAIMS_MIGRATION = ROOT / "schemas/postgres/526_location_operating_pilot_work_claims.sql"
RESOURCE_CATEGORIES_MIGRATION = ROOT / "schemas/postgres/538_location_operating_pilot_resource_categories.sql"
DEMAND_DRAFT_MIGRATION = ROOT / "schemas/postgres/552_location_operating_pilot_demand_draft.sql"
CAPACITY_DRAFT_MIGRATION = ROOT / "schemas/postgres/553_location_operating_pilot_capacity_draft.sql"
OWN_CAPACITY_MIGRATION = ROOT / "schemas/postgres/554_location_own_operating_pilot_capacity.sql"
CAPACITY_REVISION_MIGRATION = ROOT / "schemas/postgres/555_location_operating_pilot_capacity_draft_revision.sql"
CAPACITY_SUBMISSION_MIGRATION = ROOT / "schemas/postgres/556_location_operating_pilot_capacity_draft_submission.sql"
CAPACITY_REVIEW_MIGRATION = ROOT / "schemas/postgres/557_location_operating_pilot_capacity_review_queue.sql"
CAPACITY_REVIEW_DECISION_MIGRATION = ROOT / "schemas/postgres/558_location_operating_pilot_capacity_review_decision.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-22-recovery/cap-037-capacity-review-decisions-disposable.json"
spec = importlib.util.spec_from_file_location(
    "sequential_decision_summary_disposable",
    ROOT / "scripts/check-sequential-decision-summary-disposable.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
run = helper.run
wait_ready = helper.wait_ready


def psql(docker: str, container: str, sql: str) -> str:
    result = subprocess.run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"PostgreSQL acceptance failed: {detail[:1600]}")
    return result.stdout.strip()


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE SCHEMA kokonut_security;
CREATE TABLE public.party (
    id uuid PRIMARY KEY, party_type text NOT NULL DEFAULT 'person',
    status text NOT NULL DEFAULT 'active', display_name text NOT NULL DEFAULT 'Synthetic person'
);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY, enabled boolean NOT NULL);
CREATE TABLE public.operator_governance_party_binding (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, party_id uuid NOT NULL, revoked_at timestamptz
);
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
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), scope_type text NOT NULL, scope_id uuid NOT NULL,
    party_id uuid NOT NULL, period_start date NOT NULL, period_end date NOT NULL,
    status text NOT NULL, source text NOT NULL DEFAULT 'self_reported',
    available_hours numeric NOT NULL, committed_hours numeric NOT NULL, protected_hours numeric NOT NULL,
    notes text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_test_capacity_profile_period
    ON public.operating_capacity_profile(scope_type, scope_id, party_id, period_start, period_end)
    WHERE status <> 'superseded';
GRANT INSERT, UPDATE, DELETE ON TABLE public.operating_capacity_profile
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (notes), UPDATE (status) ON TABLE public.operating_capacity_profile
    TO kokonut_runtime, kokonut_directus_runtime;
CREATE FUNCTION public.test_capacity_profile_metadata(requested_profile_id uuid)
RETURNS TABLE(profile_rows bigint, party_id uuid, source text, status text, notes text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT (SELECT count(*) FROM public.operating_capacity_profile AS profile
             WHERE profile.id = requested_profile_id),
           (SELECT profile.party_id FROM public.operating_capacity_profile AS profile
             WHERE profile.id = requested_profile_id LIMIT 1),
           (SELECT profile.source FROM public.operating_capacity_profile AS profile
             WHERE profile.id = requested_profile_id LIMIT 1),
           (SELECT profile.status FROM public.operating_capacity_profile AS profile
             WHERE profile.id = requested_profile_id LIMIT 1),
           (SELECT profile.notes FROM public.operating_capacity_profile AS profile
             WHERE profile.id = requested_profile_id LIMIT 1)
$$;
GRANT EXECUTE ON FUNCTION public.test_capacity_profile_metadata(uuid) TO kokonut_runtime;
CREATE TABLE public.operating_demand_signal (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type text NOT NULL, scope_id uuid NOT NULL,
    work_type text NOT NULL, period_start date NOT NULL, period_end date NOT NULL,
    required_hours numeric NOT NULL, priority text NOT NULL, source text NOT NULL,
    source_ref uuid, description text, status text NOT NULL,
    created_by_party_id uuid, created_at timestamptz NOT NULL DEFAULT now()
);
GRANT INSERT, UPDATE, DELETE ON TABLE public.operating_demand_signal
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (description), UPDATE (status) ON TABLE public.operating_demand_signal
    TO kokonut_runtime, kokonut_directus_runtime;
CREATE FUNCTION public.test_demand_signal_metadata(requested_signal_id uuid)
RETURNS TABLE(signal_rows bigint, creator_party_id uuid)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT (SELECT count(*) FROM public.operating_demand_signal AS signal
             WHERE signal.id = requested_signal_id),
           (SELECT signal.created_by_party_id
              FROM public.operating_demand_signal AS signal
             WHERE signal.id = requested_signal_id LIMIT 1)
$$;
GRANT EXECUTE ON FUNCTION public.test_demand_signal_metadata(uuid) TO kokonut_runtime;
CREATE TABLE public.work_item (
    id uuid PRIMARY KEY, location_id uuid, status text NOT NULL, allocation_status text NOT NULL,
    work_type text NOT NULL, title text, description text
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
    scope_id uuid NOT NULL, decision text NOT NULL, description text,
    resource_type text NOT NULL DEFAULT 'other', urgency text NOT NULL DEFAULT 'medium',
    requested_by date NOT NULL DEFAULT CURRENT_DATE, status text NOT NULL DEFAULT 'submitted'
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
 ('a1000000-0000-4000-8000-000000000003', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'create', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'read', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000004', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'read_own', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000005', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'edit_own', 'f0000000-0000-4000-8000-000000000001', NULL),
 ('a1000000-0000-4000-8000-000000000007', 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'operating_pilot', 'submit_own', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.party (id, party_type, status, display_name)
VALUES ('d8000000-0000-4000-8000-000000000001', 'person', 'active', 'Synthetic operator party');
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('d8000000-0000-4000-8000-000000000002',
        'a0000000-0000-4000-8000-000000000001',
        'd8000000-0000-4000-8000-000000000001', NULL);
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
     available_hours, committed_hours, protected_hours, notes)
VALUES
 ('d0000000-0000-4000-8000-000000000001', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000001', CURRENT_DATE - 2, CURRENT_DATE + 2, 'submitted', 16, 8, 2, 'PRIVATE other operator capacity note'),
 ('d0000000-0000-4000-8000-000000000002', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000002', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 8, 3, 1, NULL),
 ('d0000000-0000-4000-8000-000000000005', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000003', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 6, 1, 1, NULL),
 ('d0000000-0000-4000-8000-000000000003', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'd1000000-0000-4000-8000-000000000004', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 80, 4, 4, 'PRIVATE other farm capacity note'),
 ('d0000000-0000-4000-8000-000000000004', 'internal', 'f0000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000005', CURRENT_DATE - 2, CURRENT_DATE + 2, 'approved', 100, 10, 10, 'PRIVATE internal capacity note'),
 ('d0000000-0000-4000-8000-000000000006', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000001', CURRENT_DATE + 3, CURRENT_DATE + 9, 'approved', 500, 10, 10, NULL);
INSERT INTO public.operating_demand_signal
    (id, scope_type, scope_id, work_type, period_start, period_end, required_hours,
     priority, source, source_ref, description, status, created_by_party_id, created_at)
VALUES
 ('d1000000-0000-4000-8000-000000000001', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'harvest', CURRENT_DATE - 2, CURRENT_DATE + 2, 12, 'high', 'planning', 'd2000000-0000-4000-8000-000000000001', 'PRIVATE demand narrative', 'submitted', 'd3000000-0000-4000-8000-000000000001', '2026-10-01 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000002', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'irrigation', CURRENT_DATE - 2, CURRENT_DATE + 2, 8, 'medium', 'planning', 'd2000000-0000-4000-8000-000000000002', 'PRIVATE demand narrative', 'approved', 'd3000000-0000-4000-8000-000000000002', '2026-10-02 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000003', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'other-farm', CURRENT_DATE - 2, CURRENT_DATE + 2, 50, 'critical', 'planning', 'd2000000-0000-4000-8000-000000000003', 'PRIVATE other farm', 'approved', 'd3000000-0000-4000-8000-000000000003', '2026-10-03 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000004', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'tree-care', CURRENT_DATE + 3, CURRENT_DATE + 9, 900, 'low', 'planning', 'd2000000-0000-4000-8000-000000000004', 'PRIVATE future narrative', 'draft', 'd3000000-0000-4000-8000-000000000004', '2026-10-03 00:00:00+00'),
 ('d1000000-0000-4000-8000-000000000005', 'internal', 'f0000000-0000-4000-8000-000000000001', 'internal-only', CURRENT_DATE - 2, CURRENT_DATE + 2, 1000, 'critical', 'planning', 'd2000000-0000-4000-8000-000000000005', 'PRIVATE internal narrative', 'approved', 'd3000000-0000-4000-8000-000000000005', '2026-10-04 00:00:00+00');
INSERT INTO public.work_item (id, location_id, status, allocation_status, work_type) VALUES
 ('e0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'assigned', 'open', 'harvest'),
 ('e0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'in_progress', 'claimed', 'harvest'),
 ('e0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000002', 'assigned', 'open', 'harvest'),
 ('e0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000001', 'assigned', 'open', 'PRIVATE custom category');
INSERT INTO public.work_item_claim (id, work_item_id, claimant_party_id, status) VALUES
 ('e1000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'e2000000-0000-4000-8000-000000000001', 'proposed'),
 ('e1000000-0000-4000-8000-000000000002', 'e0000000-0000-4000-8000-000000000002', 'e2000000-0000-4000-8000-000000000002', 'accepted'),
 ('e1000000-0000-4000-8000-000000000004', 'e0000000-0000-4000-8000-000000000002', 'e2000000-0000-4000-8000-000000000003', 'rejected'),
 ('e1000000-0000-4000-8000-000000000003', 'e0000000-0000-4000-8000-000000000003', 'e2000000-0000-4000-8000-000000000004', 'proposed'),
 ('e1000000-0000-4000-8000-000000000005', 'e0000000-0000-4000-8000-000000000004', 'e2000000-0000-4000-8000-000000000005', 'proposed'),
 ('e1000000-0000-4000-8000-000000000006', 'e0000000-0000-4000-8000-000000000004', 'e2000000-0000-4000-8000-000000000006', 'withdrawn');
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
    (id, requested_by_party_id, scope_type, scope_id, decision, resource_type, description)
VALUES
 ('f2000000-0000-4000-8000-000000000001', 'f2000000-0000-4000-8000-000000000011', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending', 'equipment', 'PRIVATE request narrative'),
 ('f2000000-0000-4000-8000-000000000002', 'f2000000-0000-4000-8000-000000000012', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending', 'machinery', 'PRIVATE request narrative'),
 ('f2000000-0000-4000-8000-000000000003', 'f2000000-0000-4000-8000-000000000013', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending', ' Equipment ', 'PRIVATE request narrative'),
 ('f2000000-0000-4000-8000-000000000004', 'f2000000-0000-4000-8000-000000000015', 'adelphi', 'e9000000-0000-4000-8000-000000000001', 'pending', 'PRIVATE unique material request', 'PRIVATE unique narrative'),
 ('f2000000-0000-4000-8000-000000000005', 'f2000000-0000-4000-8000-000000000014', 'adelphi', 'e9000000-0000-4000-8000-000000000002', 'approved', 'water_system', 'PRIVATE other farm'),
 ('f2000000-0000-4000-8000-000000000006', 'f2000000-0000-4000-8000-000000000016', 'internal', 'f0000000-0000-4000-8000-000000000001', 'pending', 'funding', 'PRIVATE internal narrative');
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
        capacity_first jsonb; capacity_second jsonb;
        own_capacity_first jsonb; own_capacity_second jsonb;
        claims_first jsonb; claims_second jsonb;
        resources_first jsonb; resources_second jsonb;
        draft_result jsonb; draft_replay jsonb; created_signal_id uuid;
        capacity_draft jsonb; capacity_draft_replay jsonb; capacity_profile_id uuid;
        denied boolean := false; invalid_page boolean := false;
        invalid_capacity_page boolean := false;
        invalid_claims_page boolean := false;
        invalid_resources_page boolean := false;
        draft_collision boolean := false; invalid_draft boolean := false;
        capacity_collision boolean := false; capacity_period_conflict boolean := false;
        invalid_capacity_draft boolean := false;
        own_read_denied boolean := false; own_scope_denied boolean := false;
        invalid_own_capacity_page boolean := false;
BEGIN
    summary := kokonut_security.location_operating_pilot_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF (summary->'work_claims'->>'proposed')::int <> 2
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
       OR (summary->'work_items'->>'total')::int <> 3
       OR (summary->'work_items'->>'open')::int <> 2
       OR (summary->'work_claims'->>'proposed')::int <> 2
       OR (summary->'work_claims'->>'accepted')::int <> 1
       OR (summary->'work_claims'->>'rejected')::int <> 1
       OR (summary->'competency_reviews'->>'submitted')::int <> 1
       OR (summary->'competency_reviews'->>'verified')::int <> 2
       OR (summary->'competency_reviews'->>'open_gap')::int <> 2
       OR (summary->'learning_plans'->>'active')::int <> 3
       OR (summary->'resource_requests'->>'pending')::int <> 4
       OR (summary->'aggregate_only_coaching_sessions'->>'count')::int <> 3 THEN
        RAISE EXCEPTION 'operating pilot aggregate or exact scope mismatch: %', summary;
    END IF;
    IF summary::text ~* '(claimant|coachee|PRIVATE|notes|evidence|party_id)' THEN
        RAISE EXCEPTION 'aggregate projection leaked private operating records';
    END IF;
    draft_result := kokonut_security.create_location_operating_pilot_demand_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9000000-0000-4000-8000-000000000001',
        'soil preparation', CURRENT_DATE + 10, CURRENT_DATE + 20,
        18.50, 'high', 'PRIVATE synthetic draft note'
    );
    draft_replay := kokonut_security.create_location_operating_pilot_demand_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9000000-0000-4000-8000-000000000001',
        'soil preparation', CURRENT_DATE + 10, CURRENT_DATE + 20,
        18.50, 'high', 'PRIVATE synthetic draft note'
    );
    created_signal_id := (draft_result->>'signal_id')::uuid;
    IF created_signal_id IS NULL
       OR created_signal_id = 'd9000000-0000-4000-8000-000000000001'
       OR draft_result->>'status' <> 'draft'
       OR draft_result->>'replayed' <> 'false'
       OR draft_replay->>'replayed' <> 'true'
       OR (SELECT signal_rows FROM public.test_demand_signal_metadata(created_signal_id)) <> 1
       OR (SELECT creator_party_id FROM public.test_demand_signal_metadata(created_signal_id))
            <> 'd8000000-0000-4000-8000-000000000001'
       OR draft_result::text ~* '(PRIVATE|party_id|created_by)' THEN
        RAISE EXCEPTION 'demand draft mismatch result %, replay %, signal %, rows %, creator %, payload leaked %',
            draft_result, draft_replay, created_signal_id,
            (SELECT signal_rows FROM public.test_demand_signal_metadata(created_signal_id)),
            (SELECT creator_party_id FROM public.test_demand_signal_metadata(created_signal_id)),
            draft_result::text ~* '(PRIVATE|party_id|created_by)';
    END IF;
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_demand_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9000000-0000-4000-8000-000000000001',
            'different work', CURRENT_DATE + 10, CURRENT_DATE + 20,
            18.50, 'high', 'PRIVATE synthetic draft note'
        );
    EXCEPTION WHEN unique_violation THEN draft_collision := true;
    END;
    IF NOT draft_collision THEN RAISE EXCEPTION 'demand request ID accepted different input'; END IF;
    capacity_draft := kokonut_security.create_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9100000-0000-4000-8000-000000000001',
        CURRENT_DATE + 40, CURRENT_DATE + 60, 40.25, 18.50, 2.25,
        'PRIVATE synthetic capacity note'
    );
    capacity_draft_replay := kokonut_security.create_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9100000-0000-4000-8000-000000000001',
        CURRENT_DATE + 40, CURRENT_DATE + 60, 40.25, 18.50, 2.25,
        'PRIVATE synthetic capacity note'
    );
    capacity_profile_id := (capacity_draft->>'profile_id')::uuid;
    IF capacity_profile_id IS NULL
       OR capacity_profile_id = 'd9100000-0000-4000-8000-000000000001'
       OR capacity_draft->>'status' <> 'draft'
       OR capacity_draft->>'replayed' <> 'false'
       OR capacity_draft_replay->>'profile_id' <> capacity_draft->>'profile_id'
       OR capacity_draft_replay->>'replayed' <> 'true'
       OR (SELECT profile_rows FROM public.test_capacity_profile_metadata(capacity_profile_id)) <> 1
       OR (SELECT party_id FROM public.test_capacity_profile_metadata(capacity_profile_id))
            <> 'd8000000-0000-4000-8000-000000000001'
       OR (SELECT source FROM public.test_capacity_profile_metadata(capacity_profile_id)) <> 'self_reported'
       OR (SELECT status FROM public.test_capacity_profile_metadata(capacity_profile_id)) <> 'draft'
       OR (SELECT notes FROM public.test_capacity_profile_metadata(capacity_profile_id))
            <> 'PRIVATE synthetic capacity note'
       OR capacity_draft::text ~* '(PRIVATE|party_id|notes|available_hours)' THEN
        RAISE EXCEPTION 'capacity draft mismatch result %, replay %, profile %, rows %, party %, source %, status %, note leaked %',
            capacity_draft, capacity_draft_replay, capacity_profile_id,
            (SELECT profile_rows FROM public.test_capacity_profile_metadata(capacity_profile_id)),
            (SELECT party_id FROM public.test_capacity_profile_metadata(capacity_profile_id)),
            (SELECT source FROM public.test_capacity_profile_metadata(capacity_profile_id)),
            (SELECT status FROM public.test_capacity_profile_metadata(capacity_profile_id)),
            capacity_draft::text ~* '(PRIVATE|party_id|notes|available_hours)';
    END IF;
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9100000-0000-4000-8000-000000000001',
            CURRENT_DATE + 40, CURRENT_DATE + 60, 39.25, 18.50, 2.25, NULL
        );
    EXCEPTION WHEN unique_violation THEN capacity_collision := true;
    END;
    IF NOT capacity_collision THEN RAISE EXCEPTION 'capacity request ID accepted changed input'; END IF;
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9100000-0000-4000-8000-000000000002',
            CURRENT_DATE + 40, CURRENT_DATE + 60, 40.25, 18.50, 2.25, NULL
        );
    EXCEPTION WHEN unique_violation THEN capacity_period_conflict := true;
    END;
    IF NOT capacity_period_conflict THEN RAISE EXCEPTION 'duplicate person and capacity period was accepted'; END IF;
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9100000-0000-4000-8000-000000000003',
            CURRENT_DATE + 70, CURRENT_DATE + 80, 20, 18, 3, NULL
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_capacity_draft := true;
    END;
    IF NOT invalid_capacity_draft THEN RAISE EXCEPTION 'overcommitted capacity draft was accepted'; END IF;
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_demand_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9000000-0000-4000-8000-000000000002',
            'soil preparation', CURRENT_DATE + 10, CURRENT_DATE + 20,
            0, 'high', NULL
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_draft := true;
    END;
    IF NOT invalid_draft THEN RAISE EXCEPTION 'invalid demand draft was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9100000-0000-4000-8000-000000000004',
            CURRENT_DATE + 70, CURRENT_DATE + 80, 20, 18, 3, NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'read-only capacity grant created a draft'; END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_own_capacity_profiles(
            'b0000000-0000-4000-8000-000000000001', 25, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN own_read_denied := true;
    END;
    IF NOT own_read_denied THEN
        RAISE EXCEPTION 'generic location read grant also authorized private own-capacity access';
    END IF;
    denied := false;
    BEGIN
        PERFORM kokonut_security.create_location_operating_pilot_demand_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd9000000-0000-4000-8000-000000000003',
            'soil preparation', CURRENT_DATE + 10, CURRENT_DATE + 20,
            18.50, 'high', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'read-only demand grant created a draft'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    PERFORM kokonut_security.create_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9100000-0000-4000-8000-000000000005',
        CURRENT_DATE + 80, CURRENT_DATE + 90, 30, 8, 2,
        'PRIVATE second synthetic capacity note'
    );
    own_capacity_first := kokonut_security.location_operating_pilot_own_capacity_profiles(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    own_capacity_second := kokonut_security.location_operating_pilot_own_capacity_profiles(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF jsonb_array_length(own_capacity_first->'items') <> 1
       OR own_capacity_first->>'has_more' <> 'true'
       OR (own_capacity_first->>'next_offset')::int <> 1
       OR jsonb_array_length(own_capacity_second->'items') <> 1
       OR own_capacity_second->>'has_more' <> 'false'
       OR own_capacity_second->'next_offset' <> 'null'::jsonb
       OR (SELECT count(*) FROM jsonb_object_keys(own_capacity_first->'items'->0)) <> 11
       OR (own_capacity_first::text || own_capacity_second::text) !~
          '(PRIVATE synthetic capacity note|PRIVATE second synthetic capacity note)'
       OR (own_capacity_first::text || own_capacity_second::text) ~*
          '(party_id|d1000000|other farm|internal|PRIVATE other operator capacity note)' THEN
        RAISE EXCEPTION 'own-capacity data, privacy filter, or deterministic paging mismatch: %, %',
            own_capacity_first, own_capacity_second;
    END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_own_capacity_profiles(
            'b0000000-0000-4000-8000-000000000002', 25, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN own_scope_denied := true;
    END;
    IF NOT own_scope_denied THEN
        RAISE EXCEPTION 'own-capacity projection accepted a location outside signed context';
    END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_own_capacity_profiles(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_own_capacity_page := true;
    END;
    IF NOT invalid_own_capacity_page THEN
        RAISE EXCEPTION 'unbounded own-capacity page was accepted';
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
       OR jsonb_array_length(demand_second->'items') <> 2
       OR demand_second->>'has_more' <> 'false'
       OR demand_second->'next_offset' <> 'null'::jsonb
       OR demand_second->'items'->0->>'work_type' <> 'tree-care'
       OR demand_second->'items'->1->>'work_type' <> 'soil preparation' THEN
        RAISE EXCEPTION 'demand page, ordering, or active farm scope mismatch: %, %',
            demand_first, demand_second;
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(demand_first->'items'->0)) <> 6
       OR (demand_first::text || demand_second::text) ~*
          '(PRIVATE|demand narrative|source_ref|created_by_party_id|party_id|d1000000|d2000000|d3000000)' THEN
        RAISE EXCEPTION 'demand page exposed non-allowlisted operating data';
    END IF;
    capacity_first := kokonut_security.location_operating_pilot_capacity_periods(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    capacity_second := kokonut_security.location_operating_pilot_capacity_periods(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF capacity_first->>'scope_configured' <> 'true'
       OR (capacity_first->>'limit')::int <> 1
       OR (capacity_first->>'offset')::int <> 0
       OR jsonb_array_length(capacity_first->'items') <> 1
       OR capacity_first->>'has_more' <> 'true'
       OR (capacity_first->>'next_offset')::int <> 1
       OR capacity_first->'items'->0->>'period_start' <> (CURRENT_DATE - 2)::text
       OR capacity_first->'items'->0->>'period_end' <> (CURRENT_DATE + 2)::text
       OR capacity_first->'items'->0->>'suppressed' <> 'false'
       OR (capacity_first->'items'->0->>'available_hours')::numeric <> 30
       OR (capacity_first->'items'->0->>'committed_hours')::numeric <> 12
       OR (capacity_first->'items'->0->>'protected_hours')::numeric <> 4
       OR capacity_second->'items'->0->>'suppressed' <> 'true'
       OR capacity_second->'items'->0->'available_hours' <> 'null'::jsonb
       OR capacity_second->'items'->0->'committed_hours' <> 'null'::jsonb
       OR capacity_second->'items'->0->'protected_hours' <> 'null'::jsonb
       OR capacity_second->'items'->0->>'period_start' <> (CURRENT_DATE + 3)::text
       OR capacity_second->'items'->0->>'period_end' <> (CURRENT_DATE + 9)::text
       OR (SELECT count(*) FROM jsonb_object_keys(capacity_second->'items'->0)) <> 6
       OR capacity_second->>'has_more' <> 'false'
       OR capacity_second->'next_offset' <> 'null'::jsonb THEN
        RAISE EXCEPTION 'capacity aggregate, suppression, or paging mismatch: %, %',
            capacity_first, capacity_second;
    END IF;
    IF (capacity_first::text || capacity_second::text) ~*
       '(party_id|notes|self_reported|d0000000-0000-4000-8000-00000000000[1-6])' THEN
        RAISE EXCEPTION 'capacity page exposed private profile, identity, or out-of-scope rows';
    END IF;
    claims_first := kokonut_security.location_operating_pilot_work_claims(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    claims_second := kokonut_security.location_operating_pilot_work_claims(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF claims_first->>'scope_configured' <> 'true'
       OR claims_first->>'limit' <> '1'
       OR claims_first->>'offset' <> '0'
       OR jsonb_array_length(claims_first->'items') <> 1
       OR claims_first->>'has_more' <> 'true'
       OR claims_first->>'next_offset' <> '1'
       OR claims_first->'items'->0->>'work_type' <> 'harvest'
       OR claims_first->'items'->0->>'suppressed' <> 'false'
       OR claims_first->'items'->0->>'claim_count' <> '3'
       OR claims_second->'items'->0->>'work_type' <> 'other'
       OR claims_second->'items'->0->>'suppressed' <> 'true'
       OR claims_second->'items'->0->'claim_count' <> 'null'::jsonb
       OR claims_second->>'has_more' <> 'false'
       OR claims_second->'next_offset' <> 'null'::jsonb THEN
        RAISE EXCEPTION 'work-claim aggregation, small-cohort suppression, or paging mismatch: %, %',
            claims_first, claims_second;
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(claims_first->'items'->0)) <> 3
       OR (claims_first::text || claims_second::text) ~*
          '(claimant|party_id|PRIVATE|custom category|e0000000|e1000000|e2000000|accepted|rejected|withdrawn)' THEN
        RAISE EXCEPTION 'work-claim page exposed an ID, free-text category, claim state, or identity: %, %',
            claims_first, claims_second;
    END IF;
    resources_first := kokonut_security.location_operating_pilot_resource_categories(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    resources_second := kokonut_security.location_operating_pilot_resource_categories(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF resources_first->>'scope_configured' <> 'true'
       OR resources_first->>'limit' <> '1'
       OR resources_first->>'offset' <> '0'
       OR jsonb_array_length(resources_first->'items') <> 1
       OR resources_first->>'has_more' <> 'true'
       OR resources_first->>'next_offset' <> '1'
       OR resources_first->'items'->0->>'resource_category' <> 'equipment'
       OR resources_first->'items'->0->>'suppressed' <> 'false'
       OR resources_first->'items'->0->>'request_count' <> '3'
       OR resources_second->'items'->0->>'resource_category' <> 'other'
       OR resources_second->'items'->0->>'suppressed' <> 'true'
       OR resources_second->'items'->0->'request_count' <> 'null'::jsonb
       OR resources_second->>'has_more' <> 'false'
       OR resources_second->'next_offset' <> 'null'::jsonb THEN
        RAISE EXCEPTION 'resource category mapping, suppression, or paging mismatch: %, %',
            resources_first, resources_second;
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(resources_first->'items'->0)) <> 3
       OR (resources_first::text || resources_second::text) ~*
          '(PRIVATE|narrative|description|urgency|decision|status|party_id|f2000000)' THEN
        RAISE EXCEPTION 'resource category page exposed IDs, free text, or lifecycle fields: %, %',
            resources_first, resources_second;
    END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_resource_categories(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_resources_page := true;
    END;
    IF NOT invalid_resources_page THEN
        RAISE EXCEPTION 'unbounded resource-category page was accepted';
    END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_work_claims(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_claims_page := true;
    END;
    IF NOT invalid_claims_page THEN
        RAISE EXCEPTION 'unbounded work-claim page was accepted';
    END IF;
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_capacity_periods(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN invalid_capacity_page := true;
    END;
    IF NOT invalid_capacity_page THEN
        RAISE EXCEPTION 'unbounded capacity page was accepted';
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
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_capacity_periods(
        'b0000000-0000-4000-8000-000000000002', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location capacity context was accepted'; END IF;
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_work_claims(
        'b0000000-0000-4000-8000-000000000002', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location work-claim context was accepted'; END IF;
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_resource_categories(
        'b0000000-0000-4000-8000-000000000002', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location resource context was accepted'; END IF;
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
    BEGIN PERFORM kokonut_security.location_operating_pilot_capacity_periods(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without tenant membership read capacity'; END IF;
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_work_claims(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without tenant membership read work claims'; END IF;
    denied := false;
    BEGIN PERFORM kokonut_security.location_operating_pilot_resource_categories(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without tenant membership read resource categories'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.operating_capacity_profile;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read operating capacity directly'; END IF;
    denied := false;
    BEGIN
        PERFORM 1 FROM public.operating_capacity_draft_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read capacity draft receipts'; END IF;
    denied := false;
    BEGIN
        INSERT INTO public.operating_capacity_draft_receipt (
            operator_id, request_id, location_id, profile_id, input_digest
        ) VALUES (
            'a0000000-0000-4000-8000-000000000001',
            'd9100000-0000-4000-8000-000000000010',
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000001', decode(repeat('00', 32), 'hex')
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can write capacity draft receipts directly'; END IF;
    denied := false;
    BEGIN
        INSERT INTO public.operating_capacity_profile (
            scope_type, scope_id, party_id, period_start, period_end, status,
            available_hours, committed_hours, protected_hours, notes, source
        ) VALUES (
            'adelphi', 'e9000000-0000-4000-8000-000000000001',
            'd8000000-0000-4000-8000-000000000001', CURRENT_DATE + 70,
            CURRENT_DATE + 80, 'draft', 20, 0, 0, 'direct write', 'self_reported'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can insert capacity directly'; END IF;
    denied := false;
    BEGIN
        UPDATE public.operating_capacity_profile SET status = 'approved'
         WHERE id = 'd0000000-0000-4000-8000-000000000001';
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can update capacity lifecycle directly'; END IF;
    denied := false;
    BEGIN
        DELETE FROM public.operating_capacity_profile
         WHERE id = 'd0000000-0000-4000-8000-000000000001';
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can delete capacity directly'; END IF;
    denied := false;
    BEGIN
        INSERT INTO public.operating_demand_signal (
            scope_type, scope_id, work_type, period_start, period_end,
            required_hours, priority, source, status
        ) VALUES (
            'adelphi', 'e9000000-0000-4000-8000-000000000001', 'direct-write',
            CURRENT_DATE, CURRENT_DATE, 1, 'low', 'planning', 'draft'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can insert demand directly'; END IF;
    denied := false;
    BEGIN
        UPDATE public.operating_demand_signal SET status = 'approved'
         WHERE id = 'd1000000-0000-4000-8000-000000000001';
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can update demand lifecycle directly'; END IF;
    denied := false;
    BEGIN
        DELETE FROM public.operating_demand_signal
         WHERE id = 'd1000000-0000-4000-8000-000000000001';
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can delete demand directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_operating_pilot_summary(uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.location_operating_pilot_demand_signals(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.location_operating_pilot_capacity_periods(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.location_operating_pilot_work_claims(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.location_operating_pilot_resource_categories(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.create_location_operating_pilot_demand_draft(uuid,uuid,text,date,date,numeric,text,text)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.create_location_operating_pilot_capacity_draft(uuid,uuid,date,date,numeric,numeric,numeric,text)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.location_operating_pilot_own_capacity_profiles(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.revise_location_operating_pilot_capacity_draft(uuid,uuid,uuid,date,date,numeric,numeric,numeric,text)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.submit_location_operating_pilot_capacity_draft(uuid,uuid,uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_signal', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_signal', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_signal', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_signal', 'DELETE')
       OR has_column_privilege('kokonut_runtime', 'public.operating_demand_signal', 'description', 'INSERT')
       OR has_column_privilege('kokonut_runtime', 'public.operating_demand_signal', 'status', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'DELETE')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'notes', 'INSERT')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'status', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_draft_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_demand_draft_receipt', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_draft_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_draft_receipt', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_draft_revision_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_draft_revision_receipt', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_draft_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_draft_submission_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_demand_signal', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_demand_signal', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_demand_signal', 'DELETE')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_demand_signal', 'description', 'INSERT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_demand_signal', 'status', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'DELETE')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'notes', 'INSERT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'status', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_demand_draft_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_demand_draft_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_draft_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_draft_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_draft_revision_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_draft_revision_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_draft_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_draft_submission_receipt', 'INSERT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_summary(uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_demand_signals(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_capacity_periods(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_work_claims(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_resource_categories(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_operating_pilot_own_capacity_profiles(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.revise_location_operating_pilot_capacity_draft(uuid,uuid,uuid,date,date,numeric,numeric,numeric,text)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.submit_location_operating_pilot_capacity_draft(uuid,uuid,uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime/Directus operating pilot privilege boundary failed';
    END IF;
    IF has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.create_location_operating_pilot_demand_draft(uuid,uuid,text,date,date,numeric,text,text)', 'EXECUTE') THEN
        RAISE EXCEPTION 'Directus can invoke the operator demand-draft writer';
    END IF;
    IF has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.create_location_operating_pilot_capacity_draft(uuid,uuid,date,date,numeric,numeric,numeric,text)', 'EXECUTE') THEN
        RAISE EXCEPTION 'Directus can invoke the operator capacity-draft writer';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.revise_location_operating_pilot_capacity_draft(uuid,uuid,uuid,date,date,numeric,numeric,numeric,text)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.revise_location_operating_pilot_capacity_draft(uuid,uuid,uuid,date,date,numeric,numeric,numeric,text)', 'EXECUTE') THEN
        RAISE EXCEPTION 'capacity revision function execute grants are not minimal';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.submit_location_operating_pilot_capacity_draft(uuid,uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.submit_location_operating_pilot_capacity_draft(uuid,uuid,uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'capacity submission function execute grants are not minimal';
    END IF;
    IF has_table_privilege('kokonut_operating_pilot_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.work_item', 'INSERT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.work_item', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.work_item', 'DELETE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.work_item_claim', 'INSERT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.work_item_claim', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.work_item_claim', 'DELETE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_signal', 'DELETE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_draft_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_demand_draft_receipt', 'DELETE') THEN
        RAISE EXCEPTION 'operating pilot reader has identity or mutation privileges';
    END IF;
    IF NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'id', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'location_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'status', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.farm', 'name', 'SELECT') THEN
        RAISE EXCEPTION 'farm mapping grants exceed required ID/location/status columns';
    END IF;
    IF has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_competency_profile', 'evidence', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_resource_request', 'description', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_resource_request', 'urgency', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_resource_request', 'status', 'SELECT')
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
    IF NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.work_item', 'work_type', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.work_item', 'title', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.work_item', 'description', 'SELECT')
       OR has_column_privilege('kokonut_runtime', 'public.work_item', 'work_type', 'SELECT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.work_item', 'work_type', 'SELECT') THEN
        RAISE EXCEPTION 'work-claim reader column grants exceed or miss the projection boundary';
    END IF;
    IF NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_resource_request', 'resource_type', 'SELECT')
       OR has_column_privilege('kokonut_runtime', 'public.operating_resource_request', 'resource_type', 'SELECT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_resource_request', 'resource_type', 'SELECT') THEN
        RAISE EXCEPTION 'resource reader column grants exceed or miss the projection boundary';
    END IF;
    IF NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'period_start', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'period_end', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'available_hours', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'committed_hours', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'protected_hours', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'notes', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'source', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'updated_at', 'SELECT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'SELECT')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'notes', 'SELECT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'notes', 'SELECT') THEN
        RAISE EXCEPTION 'own-capacity function has broad table access or lacks required private columns';
    END IF;
    IF has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'DELETE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_receipt', 'DELETE')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_receipt', 'input_digest', 'SELECT') = false
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_receipt', 'input_digest', 'INSERT') = false
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'notes', 'INSERT') = false
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'status', 'INSERT') = false
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'status', 'UPDATE') = false
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_profile', 'available_hours', 'UPDATE')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'status', 'UPDATE')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'status', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_revision_receipt', 'SELECT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_revision_receipt', 'INSERT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_revision_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_revision_receipt', 'DELETE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'DELETE')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_revision_receipt', 'input_digest', 'SELECT') = false
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_revision_receipt', 'input_digest', 'INSERT') = false
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'INSERT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'profile_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'profile_id', 'INSERT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'created_at', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_draft_submission_receipt', 'created_at', 'INSERT') THEN
        RAISE EXCEPTION 'capacity writer role lacks minimal receipt/insert privileges or has mutation access';
    END IF;
END $$;
"""

CAPACITY_REVISION_ACCEPTANCE = r"""
BEGIN;
INSERT INTO public.party (id, party_type, status, display_name)
VALUES ('d8000000-0000-4000-8000-000000000003', 'person', 'active', 'Synthetic second operator');
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('d8000000-0000-4000-8000-000000000004',
        'a0000000-0000-4000-8000-000000000002',
        'd8000000-0000-4000-8000-000000000003', NULL);
INSERT INTO public.operator_organization_membership
VALUES ('a2000000-0000-4000-8000-000000000002',
        'a0000000-0000-4000-8000-000000000002',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_scope_grant
VALUES ('a1000000-0000-4000-8000-000000000006',
        'a0000000-0000-4000-8000-000000000002',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'edit_own',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operating_capacity_profile (
    id, scope_type, scope_id, party_id, period_start, period_end,
    status, source, available_hours, committed_hours, protected_hours, notes
) VALUES (
    'd0000000-0000-4000-8000-000000000010', 'adelphi',
    'e9000000-0000-4000-8000-000000000001',
    'd8000000-0000-4000-8000-000000000001',
    CURRENT_DATE + 200, CURRENT_DATE + 220, 'submitted', 'self_reported', 40, 10, 2,
    'PRIVATE submitted profile must remain immutable'
);
SET LOCAL ROLE kokonut_runtime;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE original_id uuid; replacement_id uuid; target_id uuid; competing_id uuid;
        revised jsonb; replay jsonb; denied boolean := false;
        changed_retry_denied boolean := false; collision_denied boolean := false;
BEGIN
    original_id := (kokonut_security.create_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9200000-0000-4000-8000-000000000001',
        CURRENT_DATE + 100, CURRENT_DATE + 120, 40.25, 18.50, 2.25,
        'PRIVATE original capacity note'
    )->>'profile_id')::uuid;
    revised := kokonut_security.revise_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001', original_id,
        'd9200000-0000-4000-8000-000000000002',
        CURRENT_DATE + 100, CURRENT_DATE + 120, 50.25, 20.50, 2.25,
        'PRIVATE revised capacity note'
    );
    replay := kokonut_security.revise_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001', original_id,
        'd9200000-0000-4000-8000-000000000002',
        CURRENT_DATE + 100, CURRENT_DATE + 120, 50.25, 20.50, 2.25,
        'PRIVATE revised capacity note'
    );
    replacement_id := (revised->>'profile_id')::uuid;
    IF replacement_id IS NULL OR replacement_id = original_id
       OR revised->>'replaced_profile_id' <> original_id::text
       OR revised->>'status' <> 'draft' OR revised->>'replayed' <> 'false'
       OR replay->>'profile_id' <> replacement_id::text OR replay->>'replayed' <> 'true'
       OR (SELECT status FROM public.test_capacity_profile_metadata(original_id)) <> 'superseded'
       OR (SELECT notes FROM public.test_capacity_profile_metadata(original_id))
            <> 'PRIVATE original capacity note'
       OR (SELECT status FROM public.test_capacity_profile_metadata(replacement_id)) <> 'draft'
       OR (SELECT notes FROM public.test_capacity_profile_metadata(replacement_id))
            <> 'PRIVATE revised capacity note'
       OR revised::text ~* '(PRIVATE|party_id|notes|available_hours)' THEN
        RAISE EXCEPTION 'revision failed to preserve the prior private draft or return a draft: %, %', revised, replay;
    END IF;
    BEGIN
        PERFORM kokonut_security.revise_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', original_id,
            'd9200000-0000-4000-8000-000000000002',
            CURRENT_DATE + 100, CURRENT_DATE + 120, 51.25, 20.50, 2.25,
            'PRIVATE changed retry note'
        );
    EXCEPTION WHEN unique_violation THEN changed_retry_denied := true;
    END;
    IF NOT changed_retry_denied THEN RAISE EXCEPTION 'changed revision retry was accepted'; END IF;
    BEGIN
        PERFORM kokonut_security.revise_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000010',
            'd9200000-0000-4000-8000-000000000003',
            CURRENT_DATE + 200, CURRENT_DATE + 220, 40, 10, 2, NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'submitted profile was revisable'; END IF;
    target_id := (kokonut_security.create_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9200000-0000-4000-8000-000000000004',
        CURRENT_DATE + 130, CURRENT_DATE + 140, 30, 5, 2, NULL
    )->>'profile_id')::uuid;
    competing_id := (kokonut_security.create_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001',
        'd9200000-0000-4000-8000-000000000005',
        CURRENT_DATE + 150, CURRENT_DATE + 160, 35, 5, 2, NULL
    )->>'profile_id')::uuid;
    BEGIN
        PERFORM kokonut_security.revise_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', target_id,
            'd9200000-0000-4000-8000-000000000006',
            CURRENT_DATE + 150, CURRENT_DATE + 160, 35, 5, 2, NULL
        );
    EXCEPTION WHEN unique_violation THEN collision_denied := true;
    END;
    IF NOT collision_denied
       OR (SELECT status FROM public.test_capacity_profile_metadata(target_id)) <> 'draft'
       OR (SELECT profile_rows FROM public.test_capacity_profile_metadata(competing_id)) <> 1 THEN
        RAISE EXCEPTION 'period collision was not rejected atomically';
    END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM kokonut_security.revise_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', replacement_id,
            'd9200000-0000-4000-8000-000000000007',
            CURRENT_DATE + 100, CURRENT_DATE + 120, 51, 20, 2,
            'PRIVATE cross-party attempt'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'edit-own grant crossed human-party boundary'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM kokonut_security.revise_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', replacement_id,
            'd9200000-0000-4000-8000-000000000008',
            CURRENT_DATE + 100, CURRENT_DATE + 120, 51, 20, 2, NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'revision accepted a location outside signed context'; END IF;
END $$;
ROLLBACK;
RESET ROLE;
"""

CAPACITY_SUBMISSION_ACCEPTANCE = r"""
BEGIN;
INSERT INTO public.party (id, party_type, status, display_name)
VALUES ('d8000000-0000-4000-8000-000000000003', 'person', 'active', 'Synthetic second operator'),
       ('d8000000-0000-4000-8000-000000000005', 'person', 'active', 'Synthetic ungranted operator');
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('d8000000-0000-4000-8000-000000000004',
        'a0000000-0000-4000-8000-000000000002',
        'd8000000-0000-4000-8000-000000000003', NULL),
       ('d8000000-0000-4000-8000-000000000006',
        'a0000000-0000-4000-8000-000000000003',
        'd8000000-0000-4000-8000-000000000005', NULL);
INSERT INTO public.operator_identity VALUES ('a0000000-0000-4000-8000-000000000003', true);
INSERT INTO public.operator_organization_membership
VALUES ('a2000000-0000-4000-8000-000000000002',
        'a0000000-0000-4000-8000-000000000002',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_scope_grant
VALUES ('a1000000-0000-4000-8000-000000000008',
        'a0000000-0000-4000-8000-000000000002',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'submit_own',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operating_capacity_profile (
    id, scope_type, scope_id, party_id, period_start, period_end,
    status, source, available_hours, committed_hours, protected_hours, notes
) VALUES (
    'd0000000-0000-4000-8000-000000000020', 'adelphi',
    'e9000000-0000-4000-8000-000000000001',
    'd8000000-0000-4000-8000-000000000001',
    CURRENT_DATE + 200, CURRENT_DATE + 220, 'draft', 'self_reported', 40, 10, 2,
    'PRIVATE submitted profile note'
);
INSERT INTO public.operating_capacity_profile (
    id, scope_type, scope_id, party_id, period_start, period_end,
    status, source, available_hours, committed_hours, protected_hours, notes
) VALUES (
    'd0000000-0000-4000-8000-000000000021', 'adelphi',
    'e9000000-0000-4000-8000-000000000001',
    'd8000000-0000-4000-8000-000000000001',
    CURRENT_DATE + 230, CURRENT_DATE + 250, 'draft', 'self_reported', 35, 8, 2,
    'PRIVATE second capacity draft'
);
SET LOCAL ROLE kokonut_runtime;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE profile_id uuid := 'd0000000-0000-4000-8000-000000000020';
        other_profile_id uuid := 'd0000000-0000-4000-8000-000000000021';
        submitted jsonb; replay jsonb; denied boolean := false;
        changed_retry_denied boolean := false; foreign_owner_denied boolean := false;
        no_grant_denied boolean := false; signed_location_denied boolean := false;
BEGIN
    submitted := kokonut_security.submit_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001', profile_id,
        'd9200000-0000-4000-8000-000000000020'
    );
    replay := kokonut_security.submit_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001', profile_id,
        'd9200000-0000-4000-8000-000000000020'
    );
    IF submitted->>'profile_id' <> profile_id::text
       OR submitted->>'status' <> 'submitted' OR submitted->>'replayed' <> 'false'
       OR replay->>'profile_id' <> profile_id::text
       OR replay->>'status' <> 'submitted' OR replay->>'replayed' <> 'true'
       OR (SELECT status FROM public.test_capacity_profile_metadata(profile_id)) <> 'submitted'
       OR submitted::text ~* '(PRIVATE|party_id|notes|available_hours)' THEN
        RAISE EXCEPTION 'capacity submission or exact retry failed: %, %', submitted, replay;
    END IF;
    BEGIN
        PERFORM kokonut_security.submit_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', other_profile_id,
            'd9200000-0000-4000-8000-000000000020'
        );
    EXCEPTION WHEN unique_violation THEN changed_retry_denied := true;
    END;
    IF NOT changed_retry_denied THEN RAISE EXCEPTION 'changed submission retry was accepted'; END IF;
    BEGIN
        PERFORM kokonut_security.submit_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', profile_id,
            'd9200000-0000-4000-8000-000000000021'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'already submitted profile was re-submitted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    BEGIN
        PERFORM kokonut_security.submit_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', other_profile_id,
            'd9200000-0000-4000-8000-000000000022'
        );
    EXCEPTION WHEN insufficient_privilege THEN foreign_owner_denied := true;
    END;
    IF NOT foreign_owner_denied THEN RAISE EXCEPTION 'submit-own grant crossed human-party boundary'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    BEGIN
        PERFORM kokonut_security.submit_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', other_profile_id,
            'd9200000-0000-4000-8000-000000000023'
        );
    EXCEPTION WHEN insufficient_privilege THEN no_grant_denied := true;
    END;
    IF NOT no_grant_denied THEN RAISE EXCEPTION 'submission succeeded without active submit-own grant'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    BEGIN
        PERFORM kokonut_security.submit_location_operating_pilot_capacity_draft(
            'b0000000-0000-4000-8000-000000000001', other_profile_id,
            'd9200000-0000-4000-8000-000000000024'
        );
    EXCEPTION WHEN insufficient_privilege THEN signed_location_denied := true;
    END;
    IF NOT signed_location_denied THEN RAISE EXCEPTION 'submission accepted a different signed location'; END IF;
END $$;
RESET ROLE;
ROLLBACK;
"""

CAPACITY_REVIEW_ACCEPTANCE = r"""
BEGIN;
INSERT INTO public.party (id, party_type, status, display_name)
VALUES ('d8000000-0000-4000-8000-000000000003', 'person', 'active', 'Synthetic second operator');
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('d8000000-0000-4000-8000-000000000004',
        'a0000000-0000-4000-8000-000000000002',
        'd8000000-0000-4000-8000-000000000003', NULL);
INSERT INTO public.operator_organization_membership
VALUES ('a2000000-0000-4000-8000-000000000008',
        'a0000000-0000-4000-8000-000000000002',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_scope_grant
VALUES ('a1000000-0000-4000-8000-000000000009',
        'a0000000-0000-4000-8000-000000000001',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
       ('a1000000-0000-4000-8000-000000000010',
        'a0000000-0000-4000-8000-000000000002',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'review', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operating_capacity_profile (
    id, scope_type, scope_id, party_id, period_start, period_end,
    status, source, available_hours, committed_hours, protected_hours, notes
) VALUES
 ('d0000000-0000-4000-8000-000000000030', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000003',
  CURRENT_DATE + 300, CURRENT_DATE + 310, 'submitted', 'self_reported', 60, 20, 5,
  'PRIVATE second operator note'),
 ('d0000000-0000-4000-8000-000000000031', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000001',
  CURRENT_DATE + 320, CURRENT_DATE + 330, 'submitted', 'self_reported', 45, 15, 3,
  'PRIVATE reviewer own note'),
 ('d0000000-0000-4000-8000-000000000032', 'adelphi',
  'e9000000-0000-4000-8000-000000000002', 'd8000000-0000-4000-8000-000000000003',
  CURRENT_DATE + 340, CURRENT_DATE + 350, 'submitted', 'self_reported', 100, 20, 5,
  'PRIVATE other location note'),
 ('d0000000-0000-4000-8000-000000000033', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000003',
  CURRENT_DATE + 360, CURRENT_DATE + 370, 'draft', 'self_reported', 70, 20, 5,
  'PRIVATE draft note'),
 ('d0000000-0000-4000-8000-000000000034', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000003',
  CURRENT_DATE + 380, CURRENT_DATE + 390, 'submitted', 'manager_reviewed', 80, 20, 5,
  'PRIVATE non-self-reported note');
SET LOCAL ROLE kokonut_runtime;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE reviewer_page jsonb; reviewer_second_page jsonb; submitter_page jsonb; denied boolean := false;
        wrong_location_denied boolean := false; bounds_denied boolean := false;
BEGIN
    reviewer_page := kokonut_security.location_operating_pilot_capacity_review_queue(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    IF reviewer_page->>'total' <> '2'
       OR reviewer_page->>'has_more' <> 'true'
       OR reviewer_page->'items'->0->>'profile_id' <> 'd0000000-0000-4000-8000-000000000030'
       OR reviewer_page::text ~* '(PRIVATE|party_id|scope_id|notes|source)' THEN
        RAISE EXCEPTION 'review queue crossed self, location, lifecycle, source, or privacy boundary: %', reviewer_page;
    END IF;
    reviewer_second_page := kokonut_security.location_operating_pilot_capacity_review_queue(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF reviewer_second_page->>'total' <> '2'
       OR reviewer_second_page->>'has_more' <> 'false'
       OR reviewer_second_page->'items'->0->>'profile_id' <> 'd0000000-0000-4000-8000-000000000001'
       OR reviewer_second_page->'next_offset' IS DISTINCT FROM 'null'::jsonb THEN
        RAISE EXCEPTION 'review queue pagination was not deterministic: %', reviewer_second_page;
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    submitter_page := kokonut_security.location_operating_pilot_capacity_review_queue(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    IF submitter_page->>'total' <> '2'
       OR submitter_page->>'has_more' <> 'true'
       OR submitter_page->'items'->0->>'profile_id' <> 'd0000000-0000-4000-8000-000000000031'
       OR submitter_page::text ~* '(PRIVATE|party_id|scope_id|notes|source)' THEN
        RAISE EXCEPTION 'reviewer own-party submission was not excluded: %', submitter_page;
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_capacity_review_queue(
            'b0000000-0000-4000-8000-000000000001', 25, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'capacity queue succeeded without an exact review grant'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_capacity_review_queue(
            'b0000000-0000-4000-8000-000000000001', 25, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN wrong_location_denied := true;
    END;
    IF NOT wrong_location_denied THEN RAISE EXCEPTION 'capacity review accepted mismatched signed location'; END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
    BEGIN
        PERFORM kokonut_security.location_operating_pilot_capacity_review_queue(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN bounds_denied := true;
    END;
    IF NOT bounds_denied THEN RAISE EXCEPTION 'capacity review accepted an oversized page'; END IF;
END $$;
RESET ROLE;
DO $$
DECLARE function_oid regprocedure :=
    'kokonut_security.location_operating_pilot_capacity_review_queue(uuid,integer,integer)'::regprocedure;
BEGIN
    IF NOT has_function_privilege('kokonut_runtime', function_oid, 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime', function_oid, 'EXECUTE')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'notes', 'SELECT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'notes', 'SELECT')
       OR (SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = function_oid)
          <> 'kokonut_operating_pilot_reader' THEN
        RAISE EXCEPTION 'capacity review queue function or private-field role boundary is incorrect';
    END IF;
END $$;
ROLLBACK;
"""

CAPACITY_REVIEW_DECISION_ACCEPTANCE = r"""
BEGIN;
INSERT INTO public.party (id, party_type, status, display_name)
VALUES ('d8000000-0000-4000-8000-000000000003', 'person', 'active', 'Synthetic second operator'),
       ('d8000000-0000-4000-8000-000000000005', 'person', 'active', 'Synthetic ungranted operator');
INSERT INTO public.operator_identity VALUES ('a0000000-0000-4000-8000-000000000003', true);
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('d8000000-0000-4000-8000-000000000004',
        'a0000000-0000-4000-8000-000000000002',
        'd8000000-0000-4000-8000-000000000003', NULL),
       ('d8000000-0000-4000-8000-000000000006',
        'a0000000-0000-4000-8000-000000000003',
        'd8000000-0000-4000-8000-000000000005', NULL);
INSERT INTO public.operator_organization_membership
VALUES ('a2000000-0000-4000-8000-000000000008',
        'a0000000-0000-4000-8000-000000000002',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_scope_grant
VALUES ('a1000000-0000-4000-8000-000000000020',
        'a0000000-0000-4000-8000-000000000001',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
       ('a1000000-0000-4000-8000-000000000021',
        'a0000000-0000-4000-8000-000000000002',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
       ('a1000000-0000-4000-8000-000000000022',
        'a0000000-0000-4000-8000-000000000002',
        'b0000000-0000-4000-8000-000000000001',
        'operating_pilot', 'edit_own', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operating_capacity_profile (
    id, scope_type, scope_id, party_id, period_start, period_end,
    status, source, available_hours, committed_hours, protected_hours, notes
) VALUES
 ('d0000000-0000-4000-8000-000000000030', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000003',
  CURRENT_DATE + 300, CURRENT_DATE + 310, 'submitted', 'self_reported', 60, 20, 5,
  'PRIVATE capacity to reject and revise'),
 ('d0000000-0000-4000-8000-000000000035', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000003',
  CURRENT_DATE + 320, CURRENT_DATE + 330, 'submitted', 'self_reported', 45, 15, 3,
  'PRIVATE capacity to approve'),
 ('d0000000-0000-4000-8000-000000000036', 'adelphi',
  'e9000000-0000-4000-8000-000000000001', 'd8000000-0000-4000-8000-000000000001',
  CURRENT_DATE + 340, CURRENT_DATE + 350, 'submitted', 'self_reported', 30, 10, 2,
  'PRIVATE reviewer own capacity');
SET LOCAL ROLE kokonut_runtime;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE approved jsonb; approved_replay jsonb; rejected jsonb; revision jsonb;
        changed_retry_denied boolean := false; missing_reason_denied boolean := false;
        whitespace_reason_denied boolean := false;
        self_review_denied boolean := false; missing_grant_denied boolean := false;
        location_denied boolean := false; approved_profile uuid := 'd0000000-0000-4000-8000-000000000035';
        rejected_profile uuid := 'd0000000-0000-4000-8000-000000000030';
        replacement_profile uuid;
BEGIN
    approved := kokonut_security.review_location_operating_pilot_capacity(
        'b0000000-0000-4000-8000-000000000001', approved_profile,
        'd9200000-0000-4000-8000-000000000030', 'approved', NULL
    );
    approved_replay := kokonut_security.review_location_operating_pilot_capacity(
        'b0000000-0000-4000-8000-000000000001', approved_profile,
        'd9200000-0000-4000-8000-000000000030', 'approved', NULL
    );
    IF approved->>'status' <> 'approved' OR approved->>'decision' <> 'approved'
       OR approved->>'replayed' <> 'false'
       OR approved_replay->>'replayed' <> 'true'
       OR approved_replay->>'decision' <> 'approved'
       OR approved::text ~* '(PRIVATE|party_id|reason|notes|hours)' THEN
        RAISE EXCEPTION 'approval or exact retry returned an invalid response: %, %', approved, approved_replay;
    END IF;
    BEGIN
        PERFORM kokonut_security.review_location_operating_pilot_capacity(
            'b0000000-0000-4000-8000-000000000001', approved_profile,
            'd9200000-0000-4000-8000-000000000030', 'rejected', 'changed decision'
        );
    EXCEPTION WHEN unique_violation THEN changed_retry_denied := true;
    END;
    IF NOT changed_retry_denied THEN RAISE EXCEPTION 'changed review retry reused the request ID'; END IF;

    BEGIN
        PERFORM kokonut_security.review_location_operating_pilot_capacity(
            'b0000000-0000-4000-8000-000000000001', rejected_profile,
            'd9200000-0000-4000-8000-000000000031', 'rejected', NULL
        );
    EXCEPTION WHEN invalid_parameter_value THEN missing_reason_denied := true;
    END;
    IF NOT missing_reason_denied THEN RAISE EXCEPTION 'rejection without a reason was accepted'; END IF;
    BEGIN
        PERFORM kokonut_security.review_location_operating_pilot_capacity(
            'b0000000-0000-4000-8000-000000000001', rejected_profile,
            'd9200000-0000-4000-8000-000000000036', 'rejected', E'\t\n'
        );
    EXCEPTION WHEN invalid_parameter_value THEN whitespace_reason_denied := true;
    END;
    IF NOT whitespace_reason_denied THEN RAISE EXCEPTION 'rejection with a whitespace-only reason was accepted'; END IF;
    rejected := kokonut_security.review_location_operating_pilot_capacity(
        'b0000000-0000-4000-8000-000000000001', rejected_profile,
        'd9200000-0000-4000-8000-000000000031', 'rejected', 'Please correct the period.'
    );
    IF rejected->>'status' <> 'rejected' OR rejected->>'decision' <> 'rejected'
       OR rejected->>'replayed' <> 'false'
       OR (SELECT status FROM public.test_capacity_profile_metadata(rejected_profile)) <> 'rejected' THEN
        RAISE EXCEPTION 'rejection was not stored with a private append-only receipt: %', rejected;
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    BEGIN
        PERFORM kokonut_security.review_location_operating_pilot_capacity(
            'b0000000-0000-4000-8000-000000000001', rejected_profile,
            'd9200000-0000-4000-8000-000000000032', 'approved', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN self_review_denied := true;
    END;
    IF NOT self_review_denied THEN RAISE EXCEPTION 'reviewer decided their own submission'; END IF;
    revision := kokonut_security.revise_location_operating_pilot_capacity_draft(
        'b0000000-0000-4000-8000-000000000001', rejected_profile,
        'd9200000-0000-4000-8000-000000000033',
        CURRENT_DATE + 300, CURRENT_DATE + 310, 70, 22, 5,
        'PRIVATE corrected capacity note'
    );
    replacement_profile := (revision->>'profile_id')::uuid;
    IF revision->>'status' <> 'draft' OR revision->>'replayed' <> 'false'
       OR replacement_profile IS NULL
       OR (SELECT status FROM public.test_capacity_profile_metadata(rejected_profile)) <> 'superseded'
       OR (SELECT status FROM public.test_capacity_profile_metadata(replacement_profile)) <> 'draft' THEN
        RAISE EXCEPTION 'rejected record was not revised while preserving decision history: %', revision;
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    BEGIN
        PERFORM kokonut_security.review_location_operating_pilot_capacity(
            'b0000000-0000-4000-8000-000000000001', approved_profile,
            'd9200000-0000-4000-8000-000000000034', 'approved', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN missing_grant_denied := true;
    END;
    IF NOT missing_grant_denied THEN RAISE EXCEPTION 'review succeeded without a review grant'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    BEGIN
        PERFORM kokonut_security.review_location_operating_pilot_capacity(
            'b0000000-0000-4000-8000-000000000001', approved_profile,
            'd9200000-0000-4000-8000-000000000035', 'approved', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN location_denied := true;
    END;
    IF NOT location_denied THEN RAISE EXCEPTION 'review accepted a mismatched signed location'; END IF;
END $$;
RESET ROLE;
DO $$
DECLARE review_function regprocedure :=
    'kokonut_security.review_location_operating_pilot_capacity(uuid,uuid,uuid,text,text)'::regprocedure;
BEGIN
    IF NOT has_function_privilege('kokonut_runtime', review_function, 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime', review_function, 'EXECUTE')
       OR (SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = review_function)
            <> 'kokonut_operating_pilot_reader'
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_review_decision', 'decision', 'SELECT')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_review_decision', 'decision', 'INSERT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_review_decision', 'decision', 'SELECT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_review_decision', 'decision', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.operating_capacity_review_decision', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.operating_capacity_review_decision', 'DELETE')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_review_decision', 'decision', 'UPDATE')
       OR has_table_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_review_decision', 'DELETE')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_review_decision', 'reason', 'SELECT')
       OR NOT has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_review_decision', 'reason', 'INSERT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_review_decision', 'created_at', 'SELECT')
       OR has_column_privilege('kokonut_operating_pilot_reader', 'public.operating_capacity_review_decision', 'created_at', 'INSERT')
       OR has_column_privilege('kokonut_runtime', 'public.operating_capacity_profile', 'status', 'UPDATE')
       OR has_column_privilege('kokonut_directus_runtime', 'public.operating_capacity_profile', 'status', 'UPDATE')
       OR (SELECT status FROM public.test_capacity_profile_metadata('d0000000-0000-4000-8000-000000000030'))
            <> 'superseded'
       OR (SELECT count(*) FROM public.operating_capacity_review_decision
            WHERE profile_id = 'd0000000-0000-4000-8000-000000000030'
              AND decision = 'rejected' AND reason = 'Please correct the period.') <> 1
       OR NOT EXISTS (
           SELECT 1 FROM public.operating_capacity_review_decision
            WHERE request_id = 'd9200000-0000-4000-8000-000000000030'
              AND profile_id = 'd0000000-0000-4000-8000-000000000035'
       ) THEN
        RAISE EXCEPTION 'capacity decision function, audit role boundary, or review receipt is incorrect';
    END IF;
END $$;
ROLLBACK;
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
                  'e1000000-0000-4000-8000-000000000004',
                  'e1000000-0000-4000-8000-000000000005',
                  'e1000000-0000-4000-8000-000000000006');
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        choices=("linux/amd64", "linux/arm64"),
        help="Run the disposable PostgreSQL container for this Docker platform",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Write JSON evidence to this path (default: the native evidence path)",
    )
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-operating-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migrations": [
            SUMMARY_MIGRATION.name,
            DEMAND_MIGRATION.name,
            CAPACITY_MIGRATION.name,
            WORK_CLAIMS_MIGRATION.name,
            RESOURCE_CATEGORIES_MIGRATION.name,
            DEMAND_DRAFT_MIGRATION.name,
            CAPACITY_DRAFT_MIGRATION.name,
            OWN_CAPACITY_MIGRATION.name,
            CAPACITY_REVISION_MIGRATION.name,
            CAPACITY_SUBMISSION_MIGRATION.name,
            CAPACITY_REVIEW_MIGRATION.name,
            CAPACITY_REVIEW_DECISION_MIGRATION.name,
        ],
        "database_target": "new disposable PostgreSQL 16 container",
        "container_platform": args.platform or "docker-default",
        "network_access": "disabled with Docker network mode none",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 461, 479, 480, 526, 538, 552, 553, 554, 555, 556, 557, and 558 apply and replay on disposable PostgreSQL 16",
            "active Adelphi farm scope maps through farm.location_id and gates exact location data",
            "work, claims, learning, competency, resource, and aggregate-only coaching counts match fixtures",
            "signed tenant context and exact operating_pilot:read are enforced",
            "other locations/internal scope and private coaching are excluded; small sensitive cohorts are suppressed",
            "demand pages are bounded and exclude IDs, narratives, source references, creators, other farms, and internal scope",
            "capacity periods aggregate only submitted/approved active-farm profiles, hide hours below three people, and exclude identities/notes/out-of-scope rows",
            "capacity pages enforce bounds, deterministic paging, exact tenant grant, and runtime-function-only access",
            "work-claim pages aggregate by fixed safe work-type bucket, suppress counts below three claimants, and exclude IDs, free text, claim states, and identities",
            "work-claim pages enforce bounded deterministic paging, exact tenant scope, and runtime-function-only access",
            "resource requests map free-text values to fixed categories, suppress counts below three requesters, and exclude identity, narrative, urgency, and lifecycle state",
            "resource-category pages enforce bounds, deterministic paging, exact tenant scope, and runtime-function-only access",
            "demand draft creation requires exact location context, create grant, active human-party binding, and active farm mapping",
            "demand drafts are private, attributed, draft-only, request-idempotent, and reject mismatched retries or invalid input",
            "runtime and Directus cannot insert or mutate demand rows or access private draft receipts directly",
            "synthetic pre-existing table-level and column-level runtime/Directus demand writes are revoked; reader has only required columns and no identity or private-content read access",
            "capacity draft creation requires signed exact location create context and an active human-party binding; it creates only the actor's attributed self-reported Adelphi draft",
            "capacity requests are bounded, idempotent on exact retry, reject changed retries and duplicate periods, and never return hours, party IDs, or private notes",
            "runtime/Directus stale table-level and column-level capacity writes are revoked; direct table and receipt access remains denied",
            "an exact operating_pilot:read_own grant is required independently from aggregate read and create",
            "own-capacity results are limited to the active human binding at the active Adelphi farm and include private notes only for that identity",
            "own-capacity results have deterministic bounded pagination and reject mismatched signed location or oversized pages",
            "only the runtime role can execute the own-capacity function; Directus and runtime cannot directly select capacity notes",
            "capacity draft revisions require a separate exact-location edit-own grant and active human binding",
            "a revision atomically preserves the old draft as superseded and creates a private self-reported replacement draft",
            "exact revision retries replay; changed retries, submitted profiles, cross-party edits, location mismatches, and duplicate person-period revisions fail closed",
            "runtime receives only execute on the revision function; Directus cannot execute it and neither role accesses revision receipts or capacity notes directly",
            "capacity submissions require the separate exact submit-own grant and preserve ownership, signed scope, and draft-only eligibility",
            "exact capacity submission retries replay; changed request reuse, missing grants, cross-party profiles, non-drafts, and location mismatch fail closed",
            "capacity submission receipt access is limited to the non-login function owner; runtime and Directus cannot read or write it directly",
            "capacity review queue requires an exact review grant, excludes the reviewer own human party, and returns only submitted self-reported Adelphi rows",
            "capacity review pages are bounded, location-scoped, deterministic, and omit notes, party IDs, scope IDs, and source metadata",
            "capacity review queue denies missing grants and signed-location mismatch; runtime can execute it while Directus cannot",
            "capacity decisions require exact review scope, active human binding, active Adelphi mapping, and independent submitter identity",
            "approval and rejection update only submitted self-reported rows; rejection requires a bounded reason and writes an append-only private receipt atomically",
            "review request IDs replay only for identical location, profile, decision, and reason; changed retries and repeat decisions fail closed",
            "rejected own records can be revised into new drafts while prior rejected versions and decision reasons remain in the audit history",
            "runtime can execute review but cannot access decision receipts directly; Directus cannot execute review or access receipt data",
            "runtime and Directus cannot change capacity lifecycle status directly; decision function owner has only required status and receipt columns",
        ],
    }
    try:
        container_command = [docker, "run"]
        if args.platform:
            container_command.extend(["--platform", args.platform])
        container_command.extend(
            [
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                "none",
                "-e",
                "POSTGRES_PASSWORD=local-only-disposable",
                "postgres:16",
            ]
        )
        run(container_command)
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        summary_migration = SUMMARY_MIGRATION.read_text(encoding="utf-8")
        demand_migration = DEMAND_MIGRATION.read_text(encoding="utf-8")
        capacity_migration = CAPACITY_MIGRATION.read_text(encoding="utf-8")
        work_claims_migration = WORK_CLAIMS_MIGRATION.read_text(encoding="utf-8")
        resource_categories_migration = RESOURCE_CATEGORIES_MIGRATION.read_text(encoding="utf-8")
        demand_draft_migration = DEMAND_DRAFT_MIGRATION.read_text(encoding="utf-8")
        capacity_draft_migration = CAPACITY_DRAFT_MIGRATION.read_text(encoding="utf-8")
        own_capacity_migration = OWN_CAPACITY_MIGRATION.read_text(encoding="utf-8")
        capacity_revision_migration = CAPACITY_REVISION_MIGRATION.read_text(encoding="utf-8")
        capacity_submission_migration = CAPACITY_SUBMISSION_MIGRATION.read_text(encoding="utf-8")
        capacity_review_migration = CAPACITY_REVIEW_MIGRATION.read_text(encoding="utf-8")
        capacity_review_decision_migration = CAPACITY_REVIEW_DECISION_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, summary_migration)
        psql(docker, container, summary_migration)
        psql(docker, container, demand_migration)
        psql(docker, container, demand_migration)
        psql(docker, container, capacity_migration)
        psql(docker, container, capacity_migration)
        psql(docker, container, work_claims_migration)
        psql(docker, container, work_claims_migration)
        psql(docker, container, resource_categories_migration)
        psql(docker, container, resource_categories_migration)
        psql(docker, container, demand_draft_migration)
        psql(docker, container, demand_draft_migration)
        psql(docker, container, capacity_draft_migration)
        psql(docker, container, capacity_draft_migration)
        psql(docker, container, own_capacity_migration)
        psql(docker, container, own_capacity_migration)
        psql(docker, container, capacity_revision_migration)
        psql(docker, container, capacity_revision_migration)
        psql(docker, container, capacity_submission_migration)
        psql(docker, container, capacity_submission_migration)
        psql(docker, container, capacity_review_migration)
        psql(docker, container, capacity_review_migration)
        psql(docker, container, capacity_review_decision_migration)
        psql(docker, container, capacity_review_decision_migration)
        psql(docker, container, ACCEPTANCE)
        psql(docker, container, CAPACITY_REVISION_ACCEPTANCE)
        psql(docker, container, CAPACITY_SUBMISSION_ACCEPTANCE)
        psql(docker, container, CAPACITY_REVIEW_ACCEPTANCE)
        psql(docker, container, CAPACITY_REVIEW_DECISION_ACCEPTANCE)
        psql(docker, container, PRIVACY_SUPPRESSION)
        evidence["result"] = "passed"
        evidence["assertion_groups_passed"] = 52
        evidence["preexisting_runtime_or_directus_grants_assessed"] = True
        print(
            "PASS: migrations 461/479/480/526/538/552/553/554/555/556/557/558 apply/replay and all fifty-two grouped PostgreSQL assertions passed"
        )
        result = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        result = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
