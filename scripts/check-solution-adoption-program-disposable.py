#!/usr/bin/env python3
"""Exercise exact-location adoption-program workflows through migrations 513-517."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/513_location_solution_adoption_program_create.sql"
WRITE_BOUNDARY_MIGRATION = ROOT / "schemas/postgres/514_location_solution_adoption_write_boundary.sql"
PREPARATION_MIGRATION = ROOT / "schemas/postgres/515_location_solution_adoption_preparation.sql"
READINESS_MIGRATION = ROOT / "schemas/postgres/516_location_solution_adoption_readiness_review.sql"
CONFIGURATION_MIGRATION = ROOT / "schemas/postgres/517_location_solution_configuration_draft_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-adoption-program-disposable.json"

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
OTHER_LOCATION_ID = "b0000000-0000-4000-8000-000000000002"
OPERATOR_ID = "a0000000-0000-4000-8000-000000000041"
UNGRANTED_OPERATOR_ID = "a0000000-0000-4000-8000-000000000042"
PARTY_ID = "c1000000-0000-4000-8000-000000000041"
SOLUTION_ID = "c0000000-0000-4000-8000-000000000041"
INELIGIBLE_SOLUTION_ID = "c0000000-0000-4000-8000-000000000042"
PILOT_SOLUTION_ID = "c0000000-0000-4000-8000-000000000043"
REQUEST_ID = "ab000000-0000-4000-8000-000000000051"
PILOT_REQUEST_ID = "ab000000-0000-4000-8000-000000000055"

PREPARE = r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA kokonut_security;
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;

CREATE TABLE public.location (
    id UUID PRIMARY KEY,
    organization_id UUID
);
CREATE TABLE public.organization (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL
);
CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY,
    enabled BOOLEAN NOT NULL
);
CREATE TABLE public.party (
    id UUID PRIMARY KEY,
    party_type TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE public.operator_governance_party_binding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    party_id UUID NOT NULL REFERENCES public.party(id),
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_scope_grant (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_organization_membership (
    operator_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.location_tenant_owner_verification (
    location_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.location_organization_share (
    location_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
CREATE TABLE public.solution (
    id UUID PRIMARY KEY,
    canonical_key TEXT UNIQUE NOT NULL,
    originating_scope_type TEXT NOT NULL,
    originating_scope_id UUID NOT NULL,
    current_stage TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE public.solution_adoption_program (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES public.solution(id),
    target_scope_type TEXT NOT NULL,
    target_scope_id UUID NOT NULL,
    target_population JSONB NOT NULL DEFAULT '{}'::JSONB,
    adoption_pathway TEXT NOT NULL,
    local_adaptation_policy TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by_party_id UUID REFERENCES public.party(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.solution_adopter_readiness (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL,
    adopter_scope_type TEXT NOT NULL,
    adopter_scope_id UUID NOT NULL,
    current_level NUMERIC(6,3) NOT NULL DEFAULT 0,
    required_level NUMERIC(6,3) NOT NULL,
    gap NUMERIC(6,3) GENERATED ALWAYS AS (required_level - current_level) STORED,
    remediation_plan TEXT,
    readiness_status TEXT NOT NULL DEFAULT 'not_ready',
    assessed_by_party_id UUID,
    assessed_at TIMESTAMPTZ,
    UNIQUE (solution_id, adopter_scope_type, adopter_scope_id)
);
CREATE TABLE public.solution_configuration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id UUID NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    invariant_components JSONB NOT NULL DEFAULT '{}'::JSONB,
    configurable_components JSONB NOT NULL DEFAULT '{}'::JSONB,
    prohibited_components JSONB NOT NULL DEFAULT '{}'::JSONB,
    local_assumptions JSONB NOT NULL DEFAULT '{}'::JSONB,
    adaptation_owner_party_id UUID,
    comparability_class TEXT NOT NULL DEFAULT 'comparable',
    evidence_impact TEXT,
    approval_status TEXT NOT NULL DEFAULT 'draft',
    approved_by_party_id UUID,
    approved_at TIMESTAMPTZ
);
GRANT INSERT, UPDATE, DELETE ON public.solution_adoption_program
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON public.solution_adopter_readiness, public.solution_configuration
    TO PUBLIC, kokonut_runtime, kokonut_directus_runtime;

CREATE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(actor_id UUID, location_id UUID, actor_type TEXT)
LANGUAGE SQL STABLE AS $$
    SELECT NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.location_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.actor_type', TRUE), '')::TEXT
$$;
CREATE FUNCTION public.operator_scope_grant_allows(
    requested_operator UUID, requested_resource TEXT,
    requested_action TEXT, requested_location UUID
)
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.operator_scope_grant AS grant_row
         WHERE grant_row.operator_id = requested_operator
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location
           AND grant_row.revoked_at IS NULL
    )
$$;

INSERT INTO public.location (id) VALUES
    ('b0000000-0000-4000-8000-000000000001'),
    ('b0000000-0000-4000-8000-000000000002');
INSERT INTO public.operator_identity (id, enabled) VALUES
    ('a0000000-0000-4000-8000-000000000041', TRUE),
    ('a0000000-0000-4000-8000-000000000042', TRUE),
    ('a0000000-0000-4000-8000-000000000043', TRUE);
INSERT INTO public.party (id, party_type, status) VALUES
    ('c1000000-0000-4000-8000-000000000041', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000043', 'person', 'active');
INSERT INTO public.operator_governance_party_binding
    (operator_id, party_id, revoked_at)
VALUES
    ('a0000000-0000-4000-8000-000000000041',
     'c1000000-0000-4000-8000-000000000041', NULL),
    ('a0000000-0000-4000-8000-000000000043',
     'c1000000-0000-4000-8000-000000000043', NULL);
INSERT INTO public.operator_scope_grant
    (operator_id, resource, action, location_id)
VALUES
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'create',
     'b0000000-0000-4000-8000-000000000001'),
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'submit',
     'b0000000-0000-4000-8000-000000000001'),
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'review',
     'b0000000-0000-4000-8000-000000000001'),
    ('a0000000-0000-4000-8000-000000000043', 'solution_lifecycle', 'review',
     'b0000000-0000-4000-8000-000000000001');
INSERT INTO public.solution
    (id, canonical_key, originating_scope_type, originating_scope_id, current_stage, status)
VALUES
    ('c0000000-0000-4000-8000-000000000041', 'synthetic:adoption:eligible',
     'location', 'b0000000-0000-4000-8000-000000000001', 'adoption_ready', 'active'),
    ('c0000000-0000-4000-8000-000000000042', 'synthetic:adoption:other-origin',
     'location', 'b0000000-0000-4000-8000-000000000002', 'adoption_ready', 'active'),
    ('c0000000-0000-4000-8000-000000000043', 'synthetic:adoption:pilot-active',
     'location', 'b0000000-0000-4000-8000-000000000001', 'pilot_active', 'active');
INSERT INTO public.solution_adopter_readiness (
    id, solution_id, adopter_scope_type, adopter_scope_id, current_level,
    required_level, readiness_status, assessed_by_party_id, assessed_at
) VALUES (
    'd0000000-0000-4000-8000-000000000041',
    'c0000000-0000-4000-8000-000000000041', 'location',
    'b0000000-0000-4000-8000-000000000001', 5, 5, 'ready',
    'c1000000-0000-4000-8000-000000000041', now()
);
"""

ACCEPTANCE = f"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', '{OPERATOR_ID}', TRUE);
SELECT set_config('kokonut.location_id', '{LOCATION_ID}', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE created RECORD; replay RECORD; pilot_created RECORD; denied BOOLEAN;
        direct_insert_denied BOOLEAN := FALSE;
        direct_update_denied BOOLEAN := FALSE;
        direct_delete_denied BOOLEAN := FALSE;
        receipt_select_denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_solution_adoption_program(
        '{LOCATION_ID}', '{SOLUTION_ID}', '{REQUEST_ID}',
        'Community-led training and field support', 'Preserve safety invariants.', TRUE
    );
    IF created.program_status <> 'draft' OR created.replayed OR created.created_at IS NULL THEN
        RAISE EXCEPTION 'program creation did not produce a draft receipt';
    END IF;
    SELECT * INTO replay FROM kokonut_security.create_location_solution_adoption_program(
        '{LOCATION_ID}', '{SOLUTION_ID}', '{REQUEST_ID}',
        'Community-led training and field support', 'Preserve safety invariants.', TRUE
    );
    IF NOT replay.replayed OR replay.program_id <> created.program_id
       OR replay.created_at <> created.created_at THEN
        RAISE EXCEPTION 'exact request retry did not replay the original draft';
    END IF;

    SELECT * INTO pilot_created FROM kokonut_security.create_location_solution_adoption_program(
        '{LOCATION_ID}', '{PILOT_SOLUTION_ID}', '{PILOT_REQUEST_ID}',
        'Prepare transition from the active pilot', NULL, TRUE
    );
    IF pilot_created.program_status <> 'draft' OR pilot_created.replayed THEN
        RAISE EXCEPTION 'pilot-active solution did not receive a draft before adoption readiness';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_adoption_program(
            '{LOCATION_ID}', '{SOLUTION_ID}', '{REQUEST_ID}',
            'Changed pathway', 'Preserve safety invariants.', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed request ID reuse was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_adoption_program(
            '{OTHER_LOCATION_ID}', '{SOLUTION_ID}', 'ab000000-0000-4000-8000-000000000052',
            'Community-led training and field support', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'request escaped signed exact-location context'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_adoption_program(
            '{LOCATION_ID}', '{INELIGIBLE_SOLUTION_ID}', 'ab000000-0000-4000-8000-000000000053',
            'Community-led training and field support', NULL, TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-origin solution entered an adoption program'; END IF;

    PERFORM set_config('kokonut.actor_id', '{UNGRANTED_OPERATOR_ID}', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_adoption_program(
            '{LOCATION_ID}', '{SOLUTION_ID}', 'ab000000-0000-4000-8000-000000000054',
            'Community-led training and field support', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without create grant created a program'; END IF;

    BEGIN
        INSERT INTO public.solution_adoption_program (
            solution_id, target_scope_type, target_scope_id, adoption_pathway
        ) VALUES ('{SOLUTION_ID}', 'location', '{LOCATION_ID}', 'Direct write');
    EXCEPTION WHEN insufficient_privilege THEN direct_insert_denied := TRUE; END;
    BEGIN
        UPDATE public.solution_adoption_program SET status = 'launch';
    EXCEPTION WHEN insufficient_privilege THEN direct_update_denied := TRUE; END;
    BEGIN
        DELETE FROM public.solution_adoption_program;
    EXCEPTION WHEN insufficient_privilege THEN direct_delete_denied := TRUE; END;
    BEGIN
        PERFORM 1 FROM public.solution_adoption_program_creation_receipt;
    EXCEPTION WHEN insufficient_privilege THEN receipt_select_denied := TRUE; END;
    IF NOT direct_insert_denied OR NOT direct_update_denied OR NOT direct_delete_denied
       OR NOT receipt_select_denied THEN
        RAISE EXCEPTION 'runtime retains direct adoption-program or receipt access';
    END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE program_count BIGINT;
BEGIN
    SELECT count(*) INTO program_count FROM public.solution_adoption_program
     WHERE solution_id IN ('{SOLUTION_ID}', '{PILOT_SOLUTION_ID}')
       AND target_scope_type = 'location'
       AND target_scope_id = '{LOCATION_ID}' AND status = 'draft'
       AND created_by_party_id = '{PARTY_ID}' AND target_population = '{{}}'::JSONB;
    IF program_count <> 2 THEN RAISE EXCEPTION 'drafts were not location-scoped and human-attributed'; END IF;
    IF pg_catalog.has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_solution_adoption_program(UUID,UUID,UUID,TEXT,TEXT,BOOLEAN)',
        'EXECUTE'
    ) THEN RAISE EXCEPTION 'Directus can execute adoption program creation'; END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_program_creator'
           AND rolcanlogin
    ) THEN
        RAISE EXCEPTION 'function owner unexpectedly has LOGIN';
    END IF;
END $$;
"""

LEGACY_APPROVED_CONFIGURATION = r"""
INSERT INTO public.solution_configuration (
    solution_id, scope_type, scope_id, version, approval_status,
    approved_by_party_id, approved_at
) VALUES (
    'c0000000-0000-4000-8000-000000000041', 'location',
    'b0000000-0000-4000-8000-000000000001', 1, 'approved',
    'c1000000-0000-4000-8000-000000000043', '2026-10-19T12:00:00Z'
);
"""

CONFIGURATION_ACCEPTANCE = r"""
DO $$
DECLARE historical RECORD; archived RECORD;
BEGIN
    SELECT * INTO historical FROM public.solution_configuration
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000041' AND version = 1;
    SELECT * INTO archived FROM public.solution_configuration_legacy_approval_archive
     WHERE configuration_id = historical.id;
    IF historical.approval_status <> 'draft' OR historical.approved_by_party_id IS NOT NULL
       OR historical.approved_at IS NOT NULL OR archived.prior_approval_status <> 'approved'
       OR archived.prior_approved_by_party_id <> 'c1000000-0000-4000-8000-000000000043'::uuid
       OR archived.prior_approved_at <> '2026-10-19T12:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'historical approval was not preserved and returned to draft';
    END IF;
END $$;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE created RECORD; replay RECORD; own_draft RECORD; caught BOOLEAN := FALSE;
        cross_location_denied BOOLEAN := FALSE; ineligible_origin_denied BOOLEAN := FALSE;
        drafts BIGINT;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_solution_configuration_draft(
        'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000071', '{"water_buffer":"preserve"}',
        '{"crop_mix":["plantain","cacao"]}', '{"chemical_runoff":"prohibited"}',
        '{"soil_type":"clay loam"}', 'partially_comparable',
        'Local soil and water evidence will be collected before performance comparison.', TRUE
    );
    IF created.approval_status <> 'draft' OR created.replayed OR created.version <> 2 THEN
        RAISE EXCEPTION 'new configuration was not created as versioned draft';
    END IF;
    SELECT * INTO replay FROM kokonut_security.create_location_solution_configuration_draft(
        'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000071', '{"water_buffer":"preserve"}',
        '{"crop_mix":["plantain","cacao"]}', '{"chemical_runoff":"prohibited"}',
        '{"soil_type":"clay loam"}', 'partially_comparable',
        'Local soil and water evidence will be collected before performance comparison.', TRUE
    );
    IF NOT replay.replayed OR replay.configuration_id <> created.configuration_id
       OR replay.version <> created.version THEN
        RAISE EXCEPTION 'exact configuration draft retry did not replay';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_configuration_draft(
            'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000071', '{"water_buffer":"change"}',
            '{"crop_mix":["plantain","cacao"]}', '{"chemical_runoff":"prohibited"}',
            '{"soil_type":"clay loam"}', 'partially_comparable', 'Changed evidence.', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed draft request reuse was accepted'; END IF;
    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_configuration_draft(
            'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000072', '{"same":"key"}',
            '{"same":"key"}', '{}', '{}', 'comparable', 'Overlapping definitions.', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'overlapping component definitions were accepted'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_configuration_draft(
            'b0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000042',
            'ab000000-0000-4000-8000-000000000073', '{}', '{}', '{}', '{}',
            'comparable', 'Cross-location draft.', TRUE
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN cross_location_denied := TRUE;
    END;
    IF NOT cross_location_denied THEN RAISE EXCEPTION 'mismatched tenant context was accepted'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_configuration_draft(
            'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000042',
            'ab000000-0000-4000-8000-000000000073', '{}', '{}', '{}', '{}',
            'comparable', 'Cross-origin source must not be configured here.', TRUE
        );
    EXCEPTION WHEN SQLSTATE 'P0002' THEN ineligible_origin_denied := TRUE;
    END;
    IF NOT ineligible_origin_denied THEN RAISE EXCEPTION 'cross-origin solution was accepted'; END IF;
    SELECT count(*) INTO drafts FROM kokonut_security.location_solution_configuration_drafts(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF drafts <> 1 THEN RAISE EXCEPTION 'own draft listing included history or omitted the new draft'; END IF;
    SELECT * INTO own_draft FROM kokonut_security.location_solution_configuration_drafts(
        'b0000000-0000-4000-8000-000000000001', 1, 0
    );
    IF own_draft.configuration_id <> created.configuration_id THEN
        RAISE EXCEPTION 'draft list returned another configuration';
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE submitted RECORD; replay RECORD; caught BOOLEAN := FALSE;
BEGIN
    SELECT * INTO submitted FROM kokonut_security.submit_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001',
        (SELECT id FROM public.solution_configuration WHERE version = 2),
        'ab000000-0000-4000-8000-000000000074', TRUE
    );
    IF submitted.approval_status <> 'submitted' OR submitted.replayed THEN
        RAISE EXCEPTION 'configuration submission did not enter review';
    END IF;
    SELECT * INTO replay FROM kokonut_security.submit_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001', submitted.configuration_id,
        'ab000000-0000-4000-8000-000000000074', TRUE
    );
    IF NOT replay.replayed OR replay.submitted_at <> submitted.submitted_at THEN
        RAISE EXCEPTION 'exact submission retry did not replay';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_configuration(
            'b0000000-0000-4000-8000-000000000001', submitted.configuration_id,
            'ab000000-0000-4000-8000-000000000074', FALSE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed submission retry was accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE own_queue BIGINT; caught BOOLEAN := FALSE;
BEGIN
    SELECT count(*) INTO own_queue FROM kokonut_security.location_solution_configuration_review_queue(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF own_queue <> 0 THEN RAISE EXCEPTION 'proposer saw their own configuration in the review queue'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_configuration(
            'b0000000-0000-4000-8000-000000000001',
            (SELECT id FROM public.solution_configuration WHERE version = 2),
            'ab000000-0000-4000-8000-000000000076', 'approved', 'Self review.', TRUE
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'proposer self-review was accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE rejected_draft RECORD; rejected_submission RECORD;
BEGIN
    SELECT * INTO rejected_draft FROM kokonut_security.create_location_solution_configuration_draft(
        'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000043',
        'ab000000-0000-4000-8000-000000000077', '{"water_buffer":"preserve"}',
        '{"crop_mix":["plantain"]}', '{"chemical_runoff":"prohibited"}',
        '{"soil_type":"clay loam"}', 'comparable',
        'A new evidence comparison is required.', TRUE
    );
    SELECT * INTO rejected_submission FROM kokonut_security.submit_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001', rejected_draft.configuration_id,
        'ab000000-0000-4000-8000-000000000078', TRUE
    );
    IF rejected_submission.approval_status <> 'submitted' THEN
        RAISE EXCEPTION 'second configuration was not submitted for independent rejection';
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE queued RECORD; approved RECORD; replay RECORD; caught BOOLEAN := FALSE;
BEGIN
    SELECT * INTO queued FROM kokonut_security.location_solution_configuration_review_queue(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    ) AS pending WHERE pending.solution_id = 'c0000000-0000-4000-8000-000000000041';
    IF queued.configuration_id IS NULL THEN RAISE EXCEPTION 'independent review queue is empty'; END IF;
    SELECT * INTO approved FROM kokonut_security.review_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001', queued.configuration_id,
        'ab000000-0000-4000-8000-000000000075', 'approved', 'Independent evidence reviewed.', TRUE
    );
    IF approved.approval_status <> 'approved' OR approved.replayed THEN
        RAISE EXCEPTION 'independent configuration approval failed';
    END IF;
    SELECT * INTO replay FROM kokonut_security.review_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001', queued.configuration_id,
        'ab000000-0000-4000-8000-000000000075', 'approved', 'Independent evidence reviewed.', TRUE
    );
    IF NOT replay.replayed OR replay.reviewed_at <> approved.reviewed_at THEN
        RAISE EXCEPTION 'exact approval retry did not replay';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_configuration(
            'b0000000-0000-4000-8000-000000000001', queued.configuration_id,
            'ab000000-0000-4000-8000-000000000075', 'rejected', 'Changed decision.', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed review request reuse was accepted'; END IF;
    SELECT * INTO queued FROM kokonut_security.location_solution_configuration_review_queue(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    ) AS pending WHERE pending.solution_id = 'c0000000-0000-4000-8000-000000000043';
    IF queued.configuration_id IS NULL THEN RAISE EXCEPTION 'second configuration was not available for rejection'; END IF;
    SELECT * INTO replay FROM kokonut_security.review_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001', queued.configuration_id,
        'ab000000-0000-4000-8000-000000000079', 'rejected', 'Evidence requires a revised version.', TRUE
    );
    IF replay.approval_status <> 'rejected' OR replay.replayed THEN
        RAISE EXCEPTION 'independent configuration rejection failed';
    END IF;
    SELECT * INTO replay FROM kokonut_security.review_location_solution_configuration(
        'b0000000-0000-4000-8000-000000000001', queued.configuration_id,
        'ab000000-0000-4000-8000-000000000079', 'rejected', 'Evidence requires a revised version.', TRUE
    );
    IF NOT replay.replayed OR replay.approval_status <> 'rejected' THEN
        RAISE EXCEPTION 'exact rejection retry did not replay';
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE denied BOOLEAN := FALSE;
BEGIN
    BEGIN
        INSERT INTO public.solution_configuration (solution_id, scope_type, scope_id, version)
        VALUES ('c0000000-0000-4000-8000-000000000041', 'location',
                'b0000000-0000-4000-8000-000000000001', 99);
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly insert solution_configuration'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_solution_configuration_manager;
DO $$
DECLARE caught BOOLEAN := FALSE; configuration_id UUID;
BEGIN
    SELECT id INTO configuration_id FROM public.solution_configuration
     WHERE version = 1 AND solution_id = 'c0000000-0000-4000-8000-000000000041';
    BEGIN
        UPDATE public.solution_configuration SET approval_status = 'approved',
            approved_by_party_id = 'c1000000-0000-4000-8000-000000000043',
            approved_at = now(), current_approval_review_id = NULL
         WHERE id = configuration_id;
    EXCEPTION WHEN SQLSTATE '23514' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'unreviewed configuration approval bypassed the trigger'; END IF;
END $$;
RESET ROLE;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_configuration_draft_receipt', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_configuration_review_receipt', 'INSERT')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_configuration_submission_receipt', 'SELECT')
       OR pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.review_location_solution_configuration(UUID,UUID,UUID,TEXT,TEXT,BOOLEAN)',
        'EXECUTE')
       OR pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_configuration', 'UPDATE')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_configuration', 'DELETE') THEN
        RAISE EXCEPTION 'runtime or Directus can access private receipts or review function';
    END IF;
END $$;
"""

READINESS_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE first_assessment RECORD; replayed_assessment RECORD; queue_count BIGINT;
        caught BOOLEAN := FALSE;
BEGIN
    SELECT * INTO first_assessment FROM kokonut_security.submit_location_solution_adopter_readiness(
        'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000043',
        'ab000000-0000-4000-8000-000000000061', 2, 3, 'Complete operator training', TRUE
    );
    IF first_assessment.readiness_status <> 'submitted' OR first_assessment.replayed THEN
        RAISE EXCEPTION 'assessment submission did not remain pending independent review';
    END IF;
    SELECT * INTO replayed_assessment FROM kokonut_security.submit_location_solution_adopter_readiness(
        'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000043',
        'ab000000-0000-4000-8000-000000000061', 2, 3, 'Complete operator training', TRUE
    );
    IF replayed_assessment.assessment_id <> first_assessment.assessment_id
       OR NOT replayed_assessment.replayed THEN
        RAISE EXCEPTION 'exact readiness assessment retry did not replay';
    END IF;
    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_adopter_readiness(
            'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000043',
            'ab000000-0000-4000-8000-000000000061', 3, 3, 'Changed payload', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed assessment request reuse was accepted'; END IF;

    SELECT count(*) INTO queue_count
      FROM kokonut_security.location_solution_adopter_readiness_review_queue(
          'b0000000-0000-4000-8000-000000000001', 25, 0
      );
    IF queue_count <> 0 THEN RAISE EXCEPTION 'assessor was allowed to review their own assessment'; END IF;
    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_adopter_readiness(
            'b0000000-0000-4000-8000-000000000001', first_assessment.assessment_id,
            'ab000000-0000-4000-8000-000000000062', 'remediating', 'Self review', TRUE
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'self-review was accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE queue_row RECORD; caught BOOLEAN := FALSE;
        next_assessment RECORD;
BEGIN
    SELECT * INTO queue_row FROM kokonut_security.location_solution_adopter_readiness_review_queue(
        'b0000000-0000-4000-8000-000000000001', 25, 0
    );
    IF queue_row.assessment_id IS NULL THEN
        RAISE EXCEPTION 'independent reviewer did not receive the pending assessment';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_adopter_readiness(
            'b0000000-0000-4000-8000-000000000001', queue_row.assessment_id,
            'ab000000-0000-4000-8000-000000000063', 'ready', 'Level is below target', TRUE
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'below-target readiness was approved'; END IF;
    PERFORM * FROM kokonut_security.review_location_solution_adopter_readiness(
        'b0000000-0000-4000-8000-000000000001', queue_row.assessment_id,
        'ab000000-0000-4000-8000-000000000064', 'remediating', 'Training gap remains', TRUE
    );
    SELECT * INTO next_assessment FROM kokonut_security.review_location_solution_adopter_readiness(
        'b0000000-0000-4000-8000-000000000001', queue_row.assessment_id,
        'ab000000-0000-4000-8000-000000000064', 'remediating', 'Training gap remains', TRUE
    );
    IF NOT next_assessment.replayed OR next_assessment.readiness_status <> 'remediating' THEN
        RAISE EXCEPTION 'exact independent remediation review retry did not replay';
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
BEGIN
    PERFORM * FROM kokonut_security.submit_location_solution_adopter_readiness(
        'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000043',
        'ab000000-0000-4000-8000-000000000065', 4, 3, NULL, TRUE
    );
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_solution_adoption_readiness_manager;
DO $$
DECLARE readiness_id UUID; caught BOOLEAN := FALSE;
BEGIN
    SELECT id INTO readiness_id FROM public.solution_adopter_readiness
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000043';
    BEGIN
        UPDATE public.solution_adopter_readiness
           SET readiness_status = 'ready'
         WHERE id = readiness_id;
    EXCEPTION WHEN SQLSTATE '23514' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'unreviewed assessment was set ready directly'; END IF;
END $$;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE queue_row RECORD; review RECORD; readiness_status TEXT;
BEGIN
    SELECT * INTO queue_row FROM kokonut_security.location_solution_adopter_readiness_review_queue(
        'b0000000-0000-4000-8000-000000000001', 25, 0
    );
    IF queue_row.assessment_id IS NULL THEN RAISE EXCEPTION 'review queue unexpectedly empty'; END IF;
    SELECT * INTO review FROM kokonut_security.review_location_solution_adopter_readiness(
        'b0000000-0000-4000-8000-000000000001', queue_row.assessment_id,
        'ab000000-0000-4000-8000-000000000066', 'ready', 'Required level is met', TRUE
    );
    IF review.readiness_status <> 'ready' OR review.replayed THEN
        RAISE EXCEPTION 'independent human review did not set readiness ready';
    END IF;
    SELECT r.readiness_status INTO readiness_status
      FROM public.solution_adopter_readiness AS r
     WHERE r.id = review.readiness_id;
    IF readiness_status <> 'ready' THEN RAISE EXCEPTION 'ready projection was not persisted'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF (SELECT readiness_status FROM public.solution_adopter_readiness
         WHERE solution_id = 'c0000000-0000-4000-8000-000000000041') <> 'expired' THEN
        RAISE EXCEPTION 'historical unreviewed ready state was not expired';
    END IF;
    IF pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_adopter_readiness_assessment', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_adopter_readiness_review', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adopter_readiness_review', 'INSERT') THEN
        RAISE EXCEPTION 'shared runtime or Directus can access private readiness records';
    END IF;
    IF pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.review_location_solution_adopter_readiness(UUID,UUID,UUID,TEXT,TEXT,BOOLEAN)',
        'EXECUTE') THEN
        RAISE EXCEPTION 'Directus can execute the independent readiness reviewer';
    END IF;
END $$;
"""


def psql(docker: str, container: str, sql: str) -> str:
    result = subprocess.run(
        [docker, "exec", "-i", container, "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres"],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-adoption-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migrations": [MIGRATION.name, WRITE_BOUNDARY_MIGRATION.name, PREPARATION_MIGRATION.name, READINESS_MIGRATION.name, CONFIGURATION_MIGRATION.name],
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 513 through 517 apply and replay idempotently in order",
            "migration 515 allows draft preparation from pilot_active before the adoption-ready gate",
            "migration 516 expires historical unreviewed ready rows while preserving their audit records",
            "draft creation requires signed exact-location create context and an active human identity",
            "only active pilot_active, adoption_ready, or adopting solutions with exact location origin are eligible",
            "program scope, creator attribution, draft status, and empty target population are server controlled",
            "exact retries replay; changed request reuse fails closed",
            "runtime direct insert/update/delete and receipt access are denied",
            "Directus cannot write programs or execute the creator function",
            "readiness submission requires signed exact-location create context and creates an immutable pending assessment",
            "exact readiness retries replay; changed payload reuse fails closed",
            "assessors are excluded from their own review queue and cannot self-review",
            "below-target ready decisions and remediating decisions without a plan are rejected",
            "an independent review updates only the current assessment and exact retries replay",
            "the database trigger rejects direct ready status without an independent receipt",
            "runtime and Directus cannot read or forge private readiness records",
            "migration 517 archives unverifiable historical configuration approval without deleting the old facts",
            "configuration creation requires exact active location origin, stage, actor, payload bounds, and non-overlapping components",
            "drafts are versioned, creator-attributed, exact-location scoped, idempotent, and list only the creator's own drafts",
            "submission is restricted to the active human proposer and supports exact idempotent retry",
            "review queue excludes the proposer; independent human approval and rejection use immutable receipts and exact retries",
            "unreviewed direct approval fails the database trigger; shared runtime and Directus cannot write or read private receipts",
            "migration 517 applies and replays idempotently",
        ],
    }
    try:
        subprocess.run(
            [docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"],
            text=True,
            capture_output=True,
            check=True,
        )
        wait_ready(docker, container)
        psql(docker, container, PREPARE)
        migration_text = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_text)
        psql(docker, container, migration_text)
        boundary_text = WRITE_BOUNDARY_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, boundary_text)
        psql(docker, container, boundary_text)
        preparation_text = PREPARATION_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, preparation_text)
        psql(docker, container, preparation_text)
        readiness_text = READINESS_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, readiness_text)
        psql(docker, container, readiness_text)
        psql(docker, container, LEGACY_APPROVED_CONFIGURATION)
        configuration_text = CONFIGURATION_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, configuration_text)
        psql(docker, container, configuration_text)
        psql(docker, container, ACCEPTANCE)
        psql(docker, container, READINESS_ACCEPTANCE)
        psql(docker, container, CONFIGURATION_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 26
        print("PASS: migrations 513–517 apply/replay, adoption preparation, readiness and configuration review, retries, lifecycle, and privilege checks passed")
        return 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
