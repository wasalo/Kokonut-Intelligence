#!/usr/bin/env python3
"""Exercise exact-location adoption-program and consent workflows through migration 520."""

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
PROGRAM_REVIEW_MIGRATION = ROOT / "schemas/postgres/518_location_solution_adoption_program_review.sql"
PROGRAM_REVISION_MIGRATION = ROOT / "schemas/postgres/519_location_solution_adoption_program_revision.sql"
ADOPTION_CONSENT_MIGRATION = ROOT / "schemas/postgres/520_location_solution_adoption_consent_events.sql"
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
CREATE ROLE kokonut_solution_reader NOLOGIN;

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
    name TEXT NOT NULL DEFAULT 'Synthetic solution',
    solution_type TEXT NOT NULL DEFAULT 'practice',
    originating_scope_type TEXT NOT NULL,
    originating_scope_id UUID NOT NULL,
    current_stage TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE public.solution_link (
    solution_id UUID NOT NULL REFERENCES public.solution(id),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL
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
CREATE TABLE public.solution_adoption_cohort (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES public.solution_adoption_program(id),
    cohort_key TEXT NOT NULL
);
CREATE TABLE public.solution_adoption_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES public.solution_adoption_program(id),
    cohort_id UUID REFERENCES public.solution_adoption_cohort(id),
    adopter_ref TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'aware', 'interested', 'eligible', 'committed', 'onboarded',
        'first_use', 'repeat_use', 'habitual_use', 'advocating', 'paused', 'abandoned'
    )),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fidelity_score NUMERIC(8,3),
    support_required TEXT,
    outcome JSONB NOT NULL DEFAULT '{}'::JSONB,
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    recorded_by_party_id UUID REFERENCES public.party(id),
    CHECK (consent_checked = TRUE OR event_type IN ('aware', 'interested'))
);
CREATE TABLE public.mobile_participant_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_ref_hash CHAR(64) NOT NULL UNIQUE,
    party_id UUID NOT NULL REFERENCES public.party(id),
    location_id UUID NOT NULL REFERENCES public.location(id),
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.stakeholder_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES public.party(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('grant', 'withdraw', 'deny', 'expire')),
    data_category TEXT NOT NULL,
    purpose TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id UUID,
    recipient_party_id UUID REFERENCES public.party(id),
    recipient_type TEXT NOT NULL DEFAULT 'system',
    consent_version TEXT NOT NULL DEFAULT '1.0',
    effective_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT,
    CHECK (event_type = 'grant' OR NULLIF(BTRIM(COALESCE(reason, '')), '') IS NOT NULL)
);
CREATE TABLE public.test_adoption_program_ids (
    test_key TEXT PRIMARY KEY,
    program_id UUID NOT NULL
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
GRANT SELECT, INSERT, UPDATE ON public.test_adoption_program_ids TO kokonut_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON public.solution_adopter_readiness, public.solution_configuration
    TO PUBLIC, kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT (id, solution_id, target_scope_type, target_scope_id, status,
              created_at, updated_at) ON public.solution_adoption_program
    TO kokonut_solution_reader;
GRANT SELECT (solution_id, entity_type, entity_id) ON public.solution_link
    TO kokonut_solution_reader;
GRANT SELECT (program_id, adopter_ref, consent_checked)
    ON public.solution_adoption_event TO kokonut_solution_reader;
GRANT SELECT (id, party_type, status) ON public.party TO kokonut_solution_reader;
GRANT SELECT (id, party_id, location_id, revoked_at)
    ON public.mobile_participant_link TO kokonut_solution_reader;
GRANT SELECT (id, party_id, event_type, data_category, purpose, scope_type,
              scope_id, recipient_party_id, recipient_type, consent_version,
              effective_at, expires_at, created_at)
    ON public.stakeholder_consent TO kokonut_solution_reader;

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
    ('c1000000-0000-4000-8000-000000000043', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000045', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000046', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000047', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000048', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000049', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000050', 'person', 'active');
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
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'read',
     'b0000000-0000-4000-8000-000000000001'),
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'submit',
     'b0000000-0000-4000-8000-000000000001'),
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'review',
     'b0000000-0000-4000-8000-000000000001'),
    ('a0000000-0000-4000-8000-000000000041', 'solution_lifecycle', 'collect',
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
    INSERT INTO public.test_adoption_program_ids (test_key, program_id)
    VALUES ('eligible', created.program_id), ('pilot', pilot_created.program_id);

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

PROGRAM_REVIEW_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE first_program UUID; second_program UUID; submitted RECORD; replay RECORD;
        own_draft RECORD; own_queue BIGINT; caught BOOLEAN := FALSE; draft_count BIGINT;
        policy RECORD; policy_replay RECORD; policy_collision BOOLEAN := FALSE;
BEGIN
    SELECT program_id INTO first_program FROM public.test_adoption_program_ids WHERE test_key = 'eligible';
    SELECT program_id INTO second_program FROM public.test_adoption_program_ids WHERE test_key = 'pilot';
    SELECT * INTO policy FROM kokonut_security.configure_location_solution_adoption_consent_policy(
        'b0000000-0000-4000-8000-000000000001', first_program,
        'ab000000-0000-4000-8000-000000000101',
        'Track voluntary participation in the synthetic adoption program', '1.0', TRUE
    );
    SELECT * INTO policy_replay FROM kokonut_security.configure_location_solution_adoption_consent_policy(
        'b0000000-0000-4000-8000-000000000001', first_program,
        'ab000000-0000-4000-8000-000000000101',
        'Track voluntary participation in the synthetic adoption program', '1.0', TRUE
    );
    IF policy.program_id <> first_program OR policy_replay.replayed IS DISTINCT FROM TRUE
       OR policy_replay.consent_version <> '1.0' THEN
        RAISE EXCEPTION 'consent policy creation or exact retry was not stable';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.configure_location_solution_adoption_consent_policy(
            'b0000000-0000-4000-8000-000000000001', first_program,
            'ab000000-0000-4000-8000-000000000101',
            'Changed purpose on retry', '1.0', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN policy_collision := TRUE;
    END;
    IF NOT policy_collision THEN RAISE EXCEPTION 'changed consent-policy retry was accepted'; END IF;
    PERFORM * FROM kokonut_security.configure_location_solution_adoption_consent_policy(
        'b0000000-0000-4000-8000-000000000001', second_program,
        'ab000000-0000-4000-8000-000000000102',
        'Track voluntary participation in the synthetic pilot program', '1.0', TRUE
    );
    SELECT * INTO own_draft FROM kokonut_security.location_solution_adoption_program_drafts_with_consent(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    ) WHERE program_id = first_program;
    IF own_draft.consent_data_category <> 'solution_adoption_participation'
       OR own_draft.consent_purpose <> 'Track voluntary participation in the synthetic adoption program'
       OR own_draft.consent_version <> '1.0' THEN
        RAISE EXCEPTION 'creator did not see the exact immutable consent policy';
    END IF;
    SELECT count(*) INTO draft_count FROM kokonut_security.location_solution_adoption_program_drafts(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF draft_count <> 2 THEN RAISE EXCEPTION 'creator draft list did not return only the two own drafts'; END IF;

    SELECT * INTO submitted FROM kokonut_security.submit_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', first_program,
        'ab000000-0000-4000-8000-000000000081', TRUE
    );
    IF submitted.program_status <> 'community_review' OR submitted.replayed THEN
        RAISE EXCEPTION 'submission did not enter community review';
    END IF;
    SELECT * INTO replay FROM kokonut_security.submit_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', first_program,
        'ab000000-0000-4000-8000-000000000081', TRUE
    );
    IF NOT replay.replayed OR replay.submitted_at <> submitted.submitted_at THEN
        RAISE EXCEPTION 'exact program submission retry did not replay';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_adoption_program(
            'b0000000-0000-4000-8000-000000000001', first_program,
            'ab000000-0000-4000-8000-000000000081', FALSE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed submission retry was accepted'; END IF;

    SELECT * INTO submitted FROM kokonut_security.submit_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', second_program,
        'ab000000-0000-4000-8000-000000000082', TRUE
    );
    IF submitted.program_status <> 'community_review' THEN
        RAISE EXCEPTION 'second program did not enter community review';
    END IF;
    SELECT count(*) INTO draft_count FROM kokonut_security.location_solution_adoption_program_drafts(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF draft_count <> 0 THEN RAISE EXCEPTION 'submitted programs remained in creator draft list'; END IF;
    SELECT count(*) INTO own_queue FROM kokonut_security.location_solution_adoption_program_review_queue(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF own_queue <> 0 THEN RAISE EXCEPTION 'proposal creator saw their own programs in review queue'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_adoption_program(
            'b0000000-0000-4000-8000-000000000001', first_program,
            'ab000000-0000-4000-8000-000000000083', 'enablement_ready', 'Self review.', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'proposal creator self-review was accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;

-- Even the narrowly privileged function owner cannot change the lifecycle state
-- without a receipt from the matching independent review function.
SET ROLE kokonut_solution_adoption_program_manager;
BEGIN;
DO $$
DECLARE caught BOOLEAN := FALSE; metadata_caught BOOLEAN := FALSE;
BEGIN
    BEGIN
        UPDATE public.solution_adoption_program SET status = 'enablement_ready'
         WHERE solution_id = 'c0000000-0000-4000-8000-000000000041'
           AND status = 'community_review';
    EXCEPTION WHEN check_violation THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'manager role bypassed independent review receipt'; END IF;
    BEGIN
        UPDATE public.solution_adoption_program SET submitted_at = pg_catalog.clock_timestamp()
         WHERE solution_id = 'c0000000-0000-4000-8000-000000000041'
           AND status = 'community_review';
    EXCEPTION WHEN check_violation THEN metadata_caught := TRUE;
    END;
    IF NOT metadata_caught THEN RAISE EXCEPTION 'manager role changed immutable submission metadata'; END IF;
END $$;
ROLLBACK;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE first_program UUID; second_program UUID; queued RECORD; approved RECORD;
        approved_retry RECORD; redesigned RECORD; queue_count BIGINT; caught BOOLEAN := FALSE;
        submit_read_denied BOOLEAN := FALSE; review_read_denied BOOLEAN := FALSE;
BEGIN
    SELECT program_id INTO first_program FROM public.test_adoption_program_ids WHERE test_key = 'eligible';
    SELECT program_id INTO second_program FROM public.test_adoption_program_ids WHERE test_key = 'pilot';
    SELECT * INTO queued FROM kokonut_security.location_solution_adoption_program_review_queue_with_consent(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF queued.program_id IS NULL OR queued.adoption_pathway <> 'Community-led training and field support'
       OR queued.local_adaptation_policy <> 'Preserve safety invariants.'
       OR queued.consent_data_category <> 'solution_adoption_participation'
       OR queued.consent_purpose <> 'Track voluntary participation in the synthetic adoption program'
       OR queued.consent_version <> '1.0' THEN
        RAISE EXCEPTION 'review queue did not return safe program detail';
    END IF;
    SELECT count(*) INTO queue_count FROM kokonut_security.location_solution_adoption_program_review_queue_with_consent(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF queue_count <> 2 THEN RAISE EXCEPTION 'review queue omitted an eligible proposal'; END IF;

    SELECT * INTO approved FROM kokonut_security.review_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', first_program,
        'ab000000-0000-4000-8000-000000000084', 'enablement_ready',
        'Pathway preserves the safety invariants.', TRUE
    );
    IF approved.program_status <> 'enablement_ready' OR approved.replayed THEN
        RAISE EXCEPTION 'independent approval did not set enablement_ready';
    END IF;
    SELECT * INTO approved_retry FROM kokonut_security.review_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', first_program,
        'ab000000-0000-4000-8000-000000000084', 'enablement_ready',
        'Pathway preserves the safety invariants.', TRUE
    );
    IF NOT approved_retry.replayed OR approved_retry.reviewed_at <> approved.reviewed_at THEN
        RAISE EXCEPTION 'exact decision retry did not replay';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_adoption_program(
            'b0000000-0000-4000-8000-000000000001', first_program,
            'ab000000-0000-4000-8000-000000000084', 'enablement_ready',
            'Changed review note.', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed decision request reuse was accepted'; END IF;

    SELECT * INTO redesigned FROM kokonut_security.review_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', second_program,
        'ab000000-0000-4000-8000-000000000085', 'redesign',
        'Add explicit maintenance and support responsibilities.', TRUE
    );
    IF redesigned.program_status <> 'redesign' OR redesigned.replayed THEN
        RAISE EXCEPTION 'redesign decision did not preserve the program for follow-up';
    END IF;
    SELECT count(*) INTO queue_count FROM kokonut_security.location_solution_adoption_program_review_queue_with_consent(
        'b0000000-0000-4000-8000-000000000001', 26, 0
    );
    IF queue_count <> 0 THEN RAISE EXCEPTION 'decided programs remained in review queue'; END IF;
    BEGIN PERFORM 1 FROM public.solution_adoption_program_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN submit_read_denied := TRUE; END;
    BEGIN PERFORM 1 FROM public.solution_adoption_program_review_receipt;
    EXCEPTION WHEN insufficient_privilege THEN review_read_denied := TRUE; END;
    IF NOT submit_read_denied OR NOT review_read_denied THEN
        RAISE EXCEPTION 'runtime can read private program workflow receipts';
    END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF (SELECT current_stage FROM public.solution
         WHERE id = 'c0000000-0000-4000-8000-000000000041') <> 'adoption_ready'
       OR (SELECT current_stage FROM public.solution
         WHERE id = 'c0000000-0000-4000-8000-000000000043') <> 'pilot_active' THEN
        RAISE EXCEPTION 'program decision changed a solution lifecycle stage';
    END IF;
    IF pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_adoption_program_review_receipt', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adoption_program_review_receipt', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus retains private review-receipt access';
    END IF;
    IF pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.review_location_solution_adoption_program(UUID,UUID,UUID,TEXT,TEXT,BOOLEAN)',
        'EXECUTE') OR pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.capture_location_solution_adoption_event(UUID,UUID,UUID,TEXT,TEXT,NUMERIC,BOOLEAN)',
        'EXECUTE') OR pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.configure_location_solution_adoption_consent_policy(UUID,UUID,UUID,TEXT,TEXT,BOOLEAN)',
        'EXECUTE') OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adoption_program_consent_policy', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adoption_event', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adoption_event_capture_receipt', 'SELECT') THEN
        RAISE EXCEPTION 'Directus can execute private adoption policy/review paths or read private event data';
    END IF;
END $$;
"""

CONSENT_POLICY_GUARD_ACCEPTANCE = r"""
INSERT INTO public.solution_adoption_program (
    id, solution_id, target_scope_type, target_scope_id, adoption_pathway,
    created_by_party_id
) VALUES (
    'f0000000-0000-4000-8000-000000000001',
    'c0000000-0000-4000-8000-000000000041', 'location',
    'b0000000-0000-4000-8000-000000000001',
    'Synthetic draft without a consent policy',
    'c1000000-0000-4000-8000-000000000041'
);
DO $$
DECLARE policy_guarded BOOLEAN := FALSE;
BEGIN
    BEGIN
        UPDATE public.solution_adoption_program
           SET status = 'community_review'
         WHERE id = 'f0000000-0000-4000-8000-000000000001';
    EXCEPTION WHEN SQLSTATE '23514' THEN
        policy_guarded := SQLERRM LIKE '%immutable reviewed participant consent policy%';
    END;
    IF NOT policy_guarded THEN
        RAISE EXCEPTION 'program without a reviewed consent policy entered community review';
    END IF;
END $$;
"""

PROGRAM_REVISION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE prior_program UUID; created RECORD; replay RECORD; listed RECORD;
        caught BOOLEAN := FALSE; visible_count BIGINT;
BEGIN
    SELECT program_id INTO prior_program FROM public.test_adoption_program_ids
     WHERE test_key = 'pilot';
    SELECT count(*) INTO visible_count
      FROM kokonut_security.location_solution_adoption_program_redesigns(
          'b0000000-0000-4000-8000-000000000001', 25, 0
      );
    IF visible_count <> 1 THEN
        RAISE EXCEPTION 'eligible reviewed redesign was not listed for revision';
    END IF;
    SELECT * INTO listed FROM kokonut_security.location_solution_adoption_program_redesigns(
        'b0000000-0000-4000-8000-000000000001', 25, 0
    );
    IF listed.program_id <> prior_program OR listed.next_revision_number <> 2
       OR listed.adoption_pathway <> 'Prepare transition from the active pilot' THEN
        RAISE EXCEPTION 'redesign revision listing omitted safe prior pathway context';
    END IF;

    SELECT * INTO created FROM kokonut_security.revise_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', prior_program,
        'ab000000-0000-4000-8000-000000000091',
        'Add a maintenance cooperative and seasonal support rotation.',
        'Preserve the safety invariants and define escalation ownership.', TRUE
    );
    PERFORM * FROM kokonut_security.configure_location_solution_adoption_consent_policy(
        'b0000000-0000-4000-8000-000000000001', created.program_id,
        'ab000000-0000-4000-8000-000000000091',
        'Track voluntary participation in the revised synthetic program', '2.0', TRUE
    );
    IF created.program_status <> 'draft' OR created.replayed
       OR created.revision_number <> 2 OR created.prior_program_id <> prior_program THEN
        RAISE EXCEPTION 'reviewed redesign did not create a linked second draft';
    END IF;
    SELECT * INTO replay FROM kokonut_security.revise_location_solution_adoption_program(
        'b0000000-0000-4000-8000-000000000001', prior_program,
        'ab000000-0000-4000-8000-000000000091',
        'Add a maintenance cooperative and seasonal support rotation.',
        'Preserve the safety invariants and define escalation ownership.', TRUE
    );
    IF NOT replay.replayed OR replay.program_id <> created.program_id
       OR replay.revision_number <> created.revision_number THEN
        RAISE EXCEPTION 'exact revision retry did not replay the original draft';
    END IF;
    BEGIN
        caught := FALSE;
        PERFORM * FROM kokonut_security.revise_location_solution_adoption_program(
            'b0000000-0000-4000-8000-000000000001', prior_program,
            'ab000000-0000-4000-8000-000000000091',
            'Changed pathway on retry.', NULL, TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed revision request reuse was accepted'; END IF;

    SELECT count(*) INTO visible_count
      FROM kokonut_security.location_solution_adoption_program_redesigns(
          'b0000000-0000-4000-8000-000000000001', 25, 0
      );
    IF visible_count <> 0 THEN RAISE EXCEPTION 'redesign with an existing child remained revisable'; END IF;

    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.revise_location_solution_adoption_program(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000092', 'Invalid source', NULL, TRUE
        );
    EXCEPTION WHEN SQLSTATE 'P0002' THEN caught := TRUE;
             WHEN SQLSTATE '55000' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'non-program source was accepted as a revision'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    prior_status TEXT;
    prior_program UUID;
    revision_program UUID;
    target_population JSONB;
BEGIN
    SELECT program_id INTO prior_program FROM public.test_adoption_program_ids
     WHERE test_key = 'pilot';
    SELECT revision_program_id INTO revision_program
      FROM public.solution_adoption_program_revision
     WHERE prior_program_id = prior_program
       AND solution_id = 'c0000000-0000-4000-8000-000000000043'
       AND revision_number = 2;
    SELECT status INTO prior_status FROM public.solution_adoption_program
     WHERE id = prior_program;
    SELECT program.target_population INTO target_population
      FROM public.solution_adoption_program AS program
     WHERE program.id = revision_program;
    IF prior_status <> 'redesign' OR revision_program IS NULL THEN
        RAISE EXCEPTION 'revision overwrote the old review or failed to preserve lineage';
    END IF;
    IF target_population <> '{}'::JSONB THEN
        RAISE EXCEPTION 'revision copied uncontrolled target population';
    END IF;
END $$;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_adoption_program_revision', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_runtime',
        'public.solution_adoption_program_revision_receipt', 'SELECT')
       OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adoption_program_revision_receipt', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus can read private revision lineage/receipts';
    END IF;
    IF pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.revise_location_solution_adoption_program(UUID,UUID,UUID,TEXT,TEXT,BOOLEAN)',
        'EXECUTE') OR pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.location_solution_adoption_program_redesigns(UUID,INTEGER,INTEGER)',
        'EXECUTE') THEN
        RAISE EXCEPTION 'Directus can execute Kernel revision functions';
    END IF;
END $$;
"""

CONSENT_EVENT_FIXTURES = r"""
DO $$
DECLARE program_id UUID;
BEGIN
    SELECT test.program_id INTO program_id
      FROM public.test_adoption_program_ids AS test
     WHERE test.test_key = 'eligible';
    INSERT INTO public.mobile_participant_link (
        id, participant_ref_hash, party_id, location_id
    ) VALUES
        ('d1000000-0000-4000-8000-000000000045',
         pg_catalog.encode(public.digest(pg_catalog.convert_to(
             'synthetic-participant-reference-opaque-001', 'UTF8'), 'sha256'), 'hex'),
         'c1000000-0000-4000-8000-000000000045',
         'b0000000-0000-4000-8000-000000000001'),
        ('d1000000-0000-4000-8000-000000000046',
         pg_catalog.encode(public.digest(pg_catalog.convert_to(
             'synthetic-participant-reference-opaque-002', 'UTF8'), 'sha256'), 'hex'),
         'c1000000-0000-4000-8000-000000000046',
         'b0000000-0000-4000-8000-000000000001');
    INSERT INTO public.mobile_participant_link (
        id, participant_ref_hash, party_id, location_id
    )
    SELECT ('d1000000-0000-4000-8000-' || pg_catalog.lpad(party_suffix::TEXT, 12, '0'))::UUID,
           pg_catalog.encode(public.digest(pg_catalog.convert_to(
               'synthetic-participant-reference-opaque-' || pg_catalog.lpad((party_suffix - 44)::TEXT, 3, '0'),
               'UTF8'), 'sha256'), 'hex'),
           ('c1000000-0000-4000-8000-' || pg_catalog.lpad(party_suffix::TEXT, 12, '0'))::UUID,
           'b0000000-0000-4000-8000-000000000001'
      FROM pg_catalog.generate_series(47, 50) AS party_suffix;
    INSERT INTO public.stakeholder_consent (
        party_id, event_type, data_category, purpose, scope_type, scope_id,
        recipient_party_id, recipient_type, consent_version, effective_at
    ) VALUES
      ('c1000000-0000-4000-8000-000000000045', 'grant',
        'solution_adoption_participation',
        'Track voluntary participation in the synthetic adoption program',
        'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system',
        '1.0', pg_catalog.clock_timestamp()),
      ('c1000000-0000-4000-8000-000000000046', 'grant',
        'solution_adoption_participation',
        'Track voluntary participation in the synthetic adoption program',
        'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system',
        '1.0', pg_catalog.clock_timestamp()),
      ('c1000000-0000-4000-8000-000000000047', 'grant',
        'solution_adoption_participation',
        'Track voluntary participation in the synthetic adoption program',
        'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system',
        '1.0', pg_catalog.clock_timestamp()),
      ('c1000000-0000-4000-8000-000000000048', 'grant',
        'solution_adoption_participation',
        'Track voluntary participation in the synthetic adoption program',
        'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system',
        '1.0', pg_catalog.clock_timestamp()),
      ('c1000000-0000-4000-8000-000000000049', 'grant',
        'solution_adoption_participation',
        'Track voluntary participation in the synthetic adoption program',
        'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system',
        '1.0', pg_catalog.clock_timestamp());
END $$;
"""

CONSENT_EVENT_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE program_id UUID; captured RECORD; replay RECORD; summary RECORD;
        loop_idx INTEGER; adoption_page RECORD;
        caught BOOLEAN := FALSE; direct_select_denied BOOLEAN := FALSE;
        direct_insert_denied BOOLEAN := FALSE; receipt_denied BOOLEAN := FALSE;
BEGIN
    SELECT test.program_id INTO program_id FROM public.test_adoption_program_ids AS test
     WHERE test.test_key = 'eligible';
    SELECT * INTO captured FROM kokonut_security.capture_location_solution_adoption_event(
        'b0000000-0000-4000-8000-000000000001', program_id,
        'ab000000-0000-4000-8000-000000000111',
        pg_catalog.encode(public.digest(pg_catalog.convert_to(
            'synthetic-participant-reference-opaque-001', 'UTF8'), 'sha256'), 'hex'),
        'aware', 72.5, TRUE
    );
    IF captured.event_id IS NULL OR captured.replayed THEN
        RAISE EXCEPTION 'consent-aware event capture did not create one event';
    END IF;
    SELECT * INTO replay FROM kokonut_security.capture_location_solution_adoption_event(
        'b0000000-0000-4000-8000-000000000001', program_id,
        'ab000000-0000-4000-8000-000000000111',
        pg_catalog.encode(public.digest(pg_catalog.convert_to(
            'synthetic-participant-reference-opaque-001', 'UTF8'), 'sha256'), 'hex'),
        'aware', 72.5, TRUE
    );
    IF NOT replay.replayed OR replay.event_id <> captured.event_id THEN
        RAISE EXCEPTION 'exact adoption-event retry did not replay';
    END IF;
    FOR loop_idx IN 2..5 LOOP
        SELECT * INTO replay FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000001', program_id,
            ('ab000000-0000-4000-8000-' || pg_catalog.lpad((200 + loop_idx)::TEXT, 12, '0'))::UUID,
            pg_catalog.encode(public.digest(pg_catalog.convert_to(
                'synthetic-participant-reference-opaque-' || pg_catalog.lpad(loop_idx::TEXT, 3, '0'),
                'UTF8'), 'sha256'), 'hex'),
            'aware', NULL, TRUE
        );
        IF replay.event_id IS NULL OR replay.replayed THEN
            RAISE EXCEPTION 'consented participant % was not captured once', loop_idx;
        END IF;
    END LOOP;
    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000001', program_id,
            'ab000000-0000-4000-8000-000000000111',
            pg_catalog.encode(public.digest(pg_catalog.convert_to(
                'synthetic-participant-reference-opaque-001', 'UTF8'), 'sha256'), 'hex'),
            'interested', 72.5, TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'changed event retry reused the same request ID'; END IF;

    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000002', program_id,
            'ab000000-0000-4000-8000-000000000112', repeat('a', 64), 'aware', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'event escaped signed exact-location context'; END IF;

    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000001', program_id,
            'ab000000-0000-4000-8000-000000000113', repeat('a', 64), 'aware', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'unknown participant reference was accepted'; END IF;

    caught := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000001', program_id,
            'ab000000-0000-4000-8000-000000000114',
            pg_catalog.encode(public.digest(pg_catalog.convert_to(
                'synthetic-participant-reference-opaque-006', 'UTF8'), 'sha256'), 'hex'),
            'aware', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'participant without exact consent was accepted'; END IF;

    SELECT * INTO summary FROM kokonut_security.get_location_solution_adoption_event_summary(
        'b0000000-0000-4000-8000-000000000001', program_id
    );
    IF summary.breakdown_suppressed IS DISTINCT FROM FALSE
       OR summary.engagement_reference_count <> 5 THEN
        RAISE EXCEPTION 'five current-consent participants did not pass the disclosure threshold';
    END IF;
    SELECT adoption.* INTO adoption_page FROM kokonut_security.list_location_solution_adoption(
        'b0000000-0000-4000-8000-000000000001', 25, 0
    ) AS adoption WHERE adoption.program_status = 'enablement_ready';
    IF adoption_page.consented_adopter_reference_count <> 5 THEN
        RAISE EXCEPTION 'adoption list did not return only the safe aggregate count';
    END IF;

    BEGIN
        PERFORM 1 FROM public.solution_adoption_event;
    EXCEPTION WHEN insufficient_privilege THEN direct_select_denied := TRUE;
    END;
    BEGIN
        INSERT INTO public.solution_adoption_event (program_id, adopter_ref, event_type)
        VALUES (program_id, 'forged', 'aware');
    EXCEPTION WHEN insufficient_privilege THEN direct_insert_denied := TRUE;
    END;
    BEGIN
        PERFORM 1 FROM public.solution_adoption_event_capture_receipt;
    EXCEPTION WHEN insufficient_privilege THEN receipt_denied := TRUE;
    END;
    IF NOT direct_select_denied OR NOT direct_insert_denied OR NOT receipt_denied THEN
        RAISE EXCEPTION 'runtime retained direct event or receipt access';
    END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.solution_adoption_event AS event
         WHERE event.consent_validation_status <> 'granted'
            OR event.consent_checked IS DISTINCT FROM TRUE
            OR event.adopter_ref IS NOT NULL
            OR event.participant_link_id IS NULL
            OR event.consent_event_id IS NULL
    ) THEN
        RAISE EXCEPTION 'captured events retained a raw reference or omitted consent provenance';
    END IF;
END $$;

INSERT INTO public.stakeholder_consent (
    party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at, reason
) VALUES (
    'c1000000-0000-4000-8000-000000000045', 'withdraw',
    'solution_adoption_participation',
    'Track voluntary participation in the synthetic adoption program',
    'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system',
    '1.0', pg_catalog.clock_timestamp(), 'Synthetic withdrawal acceptance'
);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE program_id UUID; summary RECORD; captured RECORD; caught BOOLEAN := FALSE;
        adoption_page RECORD;
BEGIN
    SELECT test.program_id INTO program_id FROM public.test_adoption_program_ids AS test
     WHERE test.test_key = 'eligible';
    SELECT * INTO summary FROM kokonut_security.get_location_solution_adoption_event_summary(
        'b0000000-0000-4000-8000-000000000001', program_id
    );
    IF summary.breakdown_suppressed IS DISTINCT FROM TRUE
       OR summary.engagement_reference_count IS NOT NULL THEN
        RAISE EXCEPTION 'withdrawal did not reduce the cohort to a suppressed count';
    END IF;
    SELECT adoption.* INTO adoption_page FROM kokonut_security.list_location_solution_adoption(
        'b0000000-0000-4000-8000-000000000001', 25, 0
    ) AS adoption WHERE adoption.program_status = 'enablement_ready';
    IF adoption_page.consented_adopter_reference_count IS NOT NULL THEN
        RAISE EXCEPTION 'withdrawn adopter remained in the location adoption projection';
    END IF;
    SELECT * INTO captured FROM kokonut_security.capture_location_solution_adoption_event(
        'b0000000-0000-4000-8000-000000000001', program_id,
        'ab000000-0000-4000-8000-000000000111',
        pg_catalog.encode(public.digest(pg_catalog.convert_to(
            'synthetic-participant-reference-opaque-001', 'UTF8'), 'sha256'), 'hex'),
        'aware', 72.5, TRUE
    );
    IF NOT captured.replayed THEN RAISE EXCEPTION 'retry after withdrawal did not replay the original event'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000001', program_id,
            'ab000000-0000-4000-8000-000000000115',
            pg_catalog.encode(public.digest(pg_catalog.convert_to(
                'synthetic-participant-reference-opaque-001', 'UTF8'), 'sha256'), 'hex'),
            'repeat_use', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'new event was accepted after consent withdrawal'; END IF;
END $$;
COMMIT;
RESET ROLE;

UPDATE public.mobile_participant_link
   SET revoked_at = pg_catalog.clock_timestamp()
 WHERE party_id IN (
    'c1000000-0000-4000-8000-000000000046',
    'c1000000-0000-4000-8000-000000000047',
    'c1000000-0000-4000-8000-000000000048',
    'c1000000-0000-4000-8000-000000000049'
 );

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE program_id UUID; summary RECORD; caught BOOLEAN := FALSE;
BEGIN
    SELECT test.program_id INTO program_id FROM public.test_adoption_program_ids AS test
     WHERE test.test_key = 'eligible';
    SELECT * INTO summary FROM kokonut_security.get_location_solution_adoption_event_summary(
        'b0000000-0000-4000-8000-000000000001', program_id
    );
    IF summary.breakdown_suppressed IS DISTINCT FROM FALSE
       OR summary.engagement_reference_count <> 0 THEN
        RAISE EXCEPTION 'revoked participant links remained in consent-aware summary';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_adoption_event(
            'b0000000-0000-4000-8000-000000000001', program_id,
            'ab000000-0000-4000-8000-000000000206',
            pg_catalog.encode(public.digest(pg_catalog.convert_to(
                'synthetic-participant-reference-opaque-002', 'UTF8'), 'sha256'), 'hex'),
            'repeat_use', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'revoked participant link allowed a new capture'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF pg_catalog.has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.capture_location_solution_adoption_event(UUID,UUID,UUID,TEXT,TEXT,NUMERIC,BOOLEAN)',
        'EXECUTE') OR pg_catalog.has_table_privilege('kokonut_directus_runtime',
        'public.solution_adoption_program_consent_policy', 'SELECT') THEN
        RAISE EXCEPTION 'Directus can access adoption consent policy or event capture';
    END IF;
END $$;

DO $$
DECLARE caught BOOLEAN := FALSE;
BEGIN
    BEGIN
        UPDATE public.solution_adoption_program_consent_policy
           SET consent_version = '9.9';
    EXCEPTION WHEN SQLSTATE '23514' THEN caught := TRUE;
    END;
    IF NOT caught THEN RAISE EXCEPTION 'adoption consent policy was mutable'; END IF;
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
        "migrations": [MIGRATION.name, WRITE_BOUNDARY_MIGRATION.name, PREPARATION_MIGRATION.name, READINESS_MIGRATION.name, CONFIGURATION_MIGRATION.name, PROGRAM_REVIEW_MIGRATION.name, PROGRAM_REVISION_MIGRATION.name, ADOPTION_CONSENT_MIGRATION.name],
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 513 through 520 apply and replay idempotently in order",
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
            "migration 518 applies and replays idempotently",
            "only the draft creator can submit under exact location submit scope",
            "program submission is retry-safe and transitions only to community_review",
            "the creator sees only their own drafts and cannot self-review",
            "review queue returns bounded proposal details without proposer identity",
            "independent active human can approve enablement readiness or request redesign",
            "decision retries replay exactly and changed input reuse fails closed",
            "direct status transition fails without the matching immutable review receipt",
            "submission metadata cannot be edited outside its lifecycle transition",
            "runtime and Directus cannot access private submission or review receipts",
            "program decision does not change solution stage or launch adoption",
            "only reviewed redesign decisions can create a linked immutable new draft",
            "revision listing is exact-location, bounded, and excludes roots with an existing child",
            "revision retries replay exactly; changed payload reuse and branching fail closed",
            "the source redesign remains unchanged and direct runtime/Directus access to revision lineage and receipts is denied",
            "a program without an immutable consent policy cannot enter community review",
            "policy creation is creator-owned, exact-location, immutable, and idempotent; changed retries fail closed",
            "creator and independent reviewer queues receive the exact reviewed consent purpose and version",
            "event capture requires an active exact-location link and current policy consent, stores no raw participant reference, and replays exact retries",
            "the consent summary shows five participants only at the minimum disclosure threshold",
            "withdrawal removes one participant before the small-cohort suppression threshold and revoked links remove further counts",
            "direct runtime event/receipt access and all Directus event/policy paths are denied",
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
        program_review_text = PROGRAM_REVIEW_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, program_review_text)
        psql(docker, container, program_review_text)
        program_revision_text = PROGRAM_REVISION_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, program_revision_text)
        psql(docker, container, program_revision_text)
        adoption_consent_text = ADOPTION_CONSENT_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, adoption_consent_text)
        psql(docker, container, adoption_consent_text)
        psql(docker, container, ACCEPTANCE)
        psql(docker, container, READINESS_ACCEPTANCE)
        psql(docker, container, CONFIGURATION_ACCEPTANCE)
        psql(docker, container, PROGRAM_REVIEW_ACCEPTANCE)
        psql(docker, container, CONSENT_POLICY_GUARD_ACCEPTANCE)
        psql(docker, container, PROGRAM_REVISION_ACCEPTANCE)
        psql(docker, container, CONSENT_EVENT_FIXTURES)
        psql(docker, container, CONSENT_EVENT_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 51
        print("PASS: migrations 513–520 apply/replay, adoption preparation, immutable reviewed consent policies, participant event capture, withdrawal/link-revocation suppression, readiness, configuration, program review and revision lineage, retries, lifecycle, and privilege checks passed")
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
