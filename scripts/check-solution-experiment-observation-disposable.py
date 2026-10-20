#!/usr/bin/env python3
"""Exercise migration 510's exact-location and current-consent capture contract."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-experiment-start-disposable.py"
MIGRATION = ROOT / "schemas/postgres/510_location_solution_experiment_observation_capture.sql"
ANALYSIS_MIGRATION = ROOT / "schemas/postgres/511_location_solution_experiment_sequential_analysis.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-observation-disposable.json"
spec = importlib.util.spec_from_file_location("solution_experiment_start_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
previous_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous_check)
psql = previous_check.psql
wait_ready = previous_check.wait_ready
base = previous_check.base

PREPARE_REVIEW_TABLES = r"""
CREATE TABLE IF NOT EXISTS public.solution_experiment_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES public.solution_experiment(id),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unit_ref TEXT,
    metric_key TEXT NOT NULL DEFAULT 'soil.organic_matter',
    value NUMERIC,
    arm TEXT NOT NULL DEFAULT 'treatment',
    adverse_event BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    recorded_by_party_id UUID REFERENCES public.party(id)
);
ALTER TABLE public.solution_experiment_observation
    ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS unit_ref TEXT,
    ADD COLUMN IF NOT EXISTS metric_key TEXT NOT NULL DEFAULT 'soil.organic_matter',
    ADD COLUMN IF NOT EXISTS value NUMERIC,
    ADD COLUMN IF NOT EXISTS arm TEXT NOT NULL DEFAULT 'treatment',
    ADD COLUMN IF NOT EXISTS adverse_event BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN IF NOT EXISTS recorded_by_party_id UUID REFERENCES public.party(id);
CREATE TABLE IF NOT EXISTS public.solution_experiment_analysis_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES public.solution_experiment(id),
    metric_key TEXT NOT NULL,
    baseline_count INTEGER NOT NULL DEFAULT 0,
    treatment_count INTEGER NOT NULL DEFAULT 0,
    baseline_mean NUMERIC,
    treatment_mean NUMERIC,
    effect_estimate NUMERIC,
    standard_error NUMERIC,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    posterior_probability_benefit NUMERIC,
    adverse_event_count INTEGER NOT NULL DEFAULT 0,
    decision TEXT NOT NULL,
    stopping_reason TEXT NOT NULL,
    analysis_version TEXT NOT NULL DEFAULT 'sequential-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE public.solution_experiment_result
    ADD COLUMN IF NOT EXISTS primary_results JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN IF NOT EXISTS secondary_results JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN IF NOT EXISTS limitations TEXT,
    ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS reviewed_by_party_id UUID,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.solution_experiment_observation
    TO kokonut_runtime, kokonut_directus_runtime;
"""

PREPARE_OBSERVATION_TABLES = r"""
CREATE TABLE IF NOT EXISTS public.mobile_participant_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_ref_hash CHAR(64) NOT NULL UNIQUE,
    party_id UUID NOT NULL REFERENCES public.party(id),
    location_id UUID NOT NULL REFERENCES public.location(id),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence JSONB NOT NULL CHECK (jsonb_typeof(evidence) = 'object' AND evidence <> '{}'::JSONB),
    revoked_by TEXT,
    revoked_at TIMESTAMPTZ,
    CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
);
ALTER TABLE public.stakeholder_consent
    ADD COLUMN IF NOT EXISTS event_type TEXT NOT NULL DEFAULT 'grant',
    ADD COLUMN IF NOT EXISTS data_category TEXT NOT NULL DEFAULT 'personal',
    ADD COLUMN IF NOT EXISTS purpose TEXT NOT NULL DEFAULT 'synthetic legacy',
    ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'network',
    ADD COLUMN IF NOT EXISTS scope_id UUID,
    ADD COLUMN IF NOT EXISTS recipient_party_id UUID,
    ADD COLUMN IF NOT EXISTS recipient_type TEXT NOT NULL DEFAULT 'system',
    ADD COLUMN IF NOT EXISTS consent_version TEXT NOT NULL DEFAULT 'v1',
    ADD COLUMN IF NOT EXISTS effective_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reason TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
"""

FIXTURE = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000081', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'collect', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000082', 'a0000000-0000-4000-8000-000000000042', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000083', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000084', 'a0000000-0000-4000-8000-000000000043', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'collect', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES
    ('c2000000-0000-4000-8000-000000000051', 'Synthetic participant one', 'person', 'active'),
    ('c2000000-0000-4000-8000-000000000052', 'Synthetic participant two', 'person', 'active'),
    ('c2000000-0000-4000-8000-000000000053', 'Synthetic participant three', 'person', 'active'),
    ('c2000000-0000-4000-8000-000000000054', 'Synthetic participant four', 'person', 'active'),
    ('c2000000-0000-4000-8000-000000000055', 'Synthetic participant five', 'person', 'active'),
    ('c2000000-0000-4000-8000-000000000056', 'Synthetic participant six', 'person', 'active')
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.mobile_participant_link (
    id, participant_ref_hash, party_id, location_id, created_by,
    evidence, revoked_by, revoked_at
)
VALUES
    ('d2000000-0000-4000-8000-000000000051', repeat('1', 64), 'c2000000-0000-4000-8000-000000000051', 'b0000000-0000-4000-8000-000000000001', 'synthetic-reviewer', '{"source":"disposable"}', NULL, NULL),
    ('d2000000-0000-4000-8000-000000000052', repeat('2', 64), 'c2000000-0000-4000-8000-000000000052', 'b0000000-0000-4000-8000-000000000001', 'synthetic-reviewer', '{"source":"disposable"}', NULL, NULL),
    ('d2000000-0000-4000-8000-000000000053', repeat('3', 64), 'c2000000-0000-4000-8000-000000000053', 'b0000000-0000-4000-8000-000000000001', 'synthetic-reviewer', '{"source":"disposable"}', NULL, NULL),
    ('d2000000-0000-4000-8000-000000000054', repeat('4', 64), 'c2000000-0000-4000-8000-000000000054', 'b0000000-0000-4000-8000-000000000001', 'synthetic-reviewer', '{"source":"disposable"}', NULL, NULL),
    ('d2000000-0000-4000-8000-000000000055', repeat('5', 64), 'c2000000-0000-4000-8000-000000000055', 'b0000000-0000-4000-8000-000000000001', 'synthetic-reviewer', '{"source":"disposable"}', 'synthetic-reviewer', NOW()),
    ('d2000000-0000-4000-8000-000000000056', repeat('6', 64), 'c2000000-0000-4000-8000-000000000056', 'b0000000-0000-4000-8000-000000000001', 'synthetic-reviewer', '{"source":"disposable"}', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.stakeholder_consent (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at,
    expires_at, created_at
)
VALUES
    ('e2000000-0000-4000-8000-000000000051', 'c2000000-0000-4000-8000-000000000051', 'grant', 'solution_experiment_participation', 'Participation in the synthetic experiment.', 'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v1', NOW() - INTERVAL '1 day', NULL, NOW() - INTERVAL '1 day'),
    ('e2000000-0000-4000-8000-000000000052', 'c2000000-0000-4000-8000-000000000052', 'grant', 'solution_experiment_participation', 'A different purpose.', 'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v1', NOW() - INTERVAL '1 day', NULL, NOW() - INTERVAL '1 day'),
    ('e2000000-0000-4000-8000-000000000053', 'c2000000-0000-4000-8000-000000000053', 'grant', 'solution_experiment_participation', 'Participation in the synthetic experiment.', 'location', 'b0000000-0000-4000-8000-000000000002', NULL, 'system', 'v1', NOW() - INTERVAL '1 day', NULL, NOW() - INTERVAL '1 day'),
    ('e2000000-0000-4000-8000-000000000054', 'c2000000-0000-4000-8000-000000000054', 'grant', 'solution_experiment_participation', 'Participation in the synthetic experiment.', 'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v1', NOW() - INTERVAL '2 days', NOW() - INTERVAL '1 day', NOW() - INTERVAL '2 days'),
    ('e2000000-0000-4000-8000-000000000056', 'c2000000-0000-4000-8000-000000000056', 'grant', 'solution_experiment_participation', 'Participation in the synthetic experiment.', 'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v2', NOW() - INTERVAL '1 day', NULL, NOW() - INTERVAL '1 day');
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE experiment_id UUID := '__EXPERIMENT_ID__'::UUID;
        captured RECORD; replay RECORD; denied BOOLEAN;
        direct_select_denied BOOLEAN := FALSE; direct_insert_denied BOOLEAN := FALSE;
        direct_update_denied BOOLEAN := FALSE; direct_delete_denied BOOLEAN := FALSE;
        payload JSONB := '{"evidence_refs":["synthetic-source"]}'::JSONB;
BEGIN
    SELECT * INTO captured FROM kokonut_security.capture_location_solution_experiment_observation(
        'b0000000-0000-4000-8000-000000000001', experiment_id,
        'ab000000-0000-4000-8000-000000000151', 'soil.organic_matter', 10.5,
        'treatment', NULL, FALSE, payload,
        'd2000000-0000-4000-8000-000000000051', TRUE
    );
    IF captured.observation_id IS NULL OR captured.replayed THEN
        RAISE EXCEPTION 'current exact-location consent did not capture an observation';
    END IF;
    SELECT * INTO replay FROM kokonut_security.capture_location_solution_experiment_observation(
        'b0000000-0000-4000-8000-000000000001', experiment_id,
        'ab000000-0000-4000-8000-000000000151', 'soil.organic_matter', 10.5,
        'treatment', NULL, FALSE, payload,
        'd2000000-0000-4000-8000-000000000051', TRUE
    );
    IF NOT replay.replayed OR replay.observation_id <> captured.observation_id THEN
        RAISE EXCEPTION 'exact observation retry did not replay one receipt';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000151', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed observation request payload was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000152', 'undeclared.metric', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'undeclared metric was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000153', 'soil.organic_matter', 11,
            'control', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'unrecognized observation arm was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000154', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload, NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'participant protocol accepted a missing link'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000155', 'soil.organic_matter', 11,
            'treatment', 'participant:raw', FALSE, payload,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'participant observation accepted an identifying unit reference'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000156', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000052', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'wrong-purpose consent was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000157', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000053', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'wrong-location consent was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000158', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000054', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'expired consent was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000159', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000055', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'revoked participant link was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000162', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000056', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'consent version mismatch was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000002', experiment_id,
            'ab000000-0000-4000-8000-000000000160', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'capture escaped signed location context'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000161', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, payload,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without collect grant captured an observation'; END IF;

    BEGIN PERFORM 1 FROM public.solution_experiment_observation;
    EXCEPTION WHEN insufficient_privilege THEN direct_select_denied := TRUE; END;
    BEGIN
        INSERT INTO public.solution_experiment_observation (experiment_id, metric_key, arm)
        VALUES (experiment_id, 'soil.organic_matter', 'treatment');
    EXCEPTION WHEN insufficient_privilege THEN direct_insert_denied := TRUE; END;
    BEGIN UPDATE public.solution_experiment_observation SET value = 99;
    EXCEPTION WHEN insufficient_privilege THEN direct_update_denied := TRUE; END;
    BEGIN DELETE FROM public.solution_experiment_observation;
    EXCEPTION WHEN insufficient_privilege THEN direct_delete_denied := TRUE; END;
    IF NOT direct_select_denied OR NOT direct_insert_denied
       OR NOT direct_update_denied OR NOT direct_delete_denied THEN
        RAISE EXCEPTION 'runtime can access observations outside the bounded function';
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_solution_experiment_reviewer;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE target_experiment_id UUID; reviewer_visible BIGINT;
BEGIN
    SELECT experiment.id INTO target_experiment_id FROM public.solution_experiment AS experiment
     WHERE hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';
    SELECT count(*) INTO reviewer_visible FROM public.solution_experiment_observation
     WHERE solution_experiment_observation.experiment_id = target_experiment_id;
    IF reviewer_visible <> 1 THEN RAISE EXCEPTION 'review projection omitted a currently consented observation'; END IF;
END $$;
COMMIT;
RESET ROLE;

INSERT INTO public.stakeholder_consent (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at,
    expires_at, reason, created_at
) VALUES (
    'e2000000-0000-4000-8000-000000000151',
    'c2000000-0000-4000-8000-000000000051', 'withdraw',
    'solution_experiment_participation', 'Participation in the synthetic experiment.',
    'location', 'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v2',
    NOW(), NULL, 'Synthetic withdrawal after capture', NOW()
);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE target_experiment_id UUID := '__EXPERIMENT_ID__'::UUID;
        denied BOOLEAN := FALSE;
BEGIN
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', target_experiment_id,
            'ab000000-0000-4000-8000-000000000163', 'soil.organic_matter', 11,
            'treatment', NULL, FALSE, '{"evidence_refs":["synthetic-source"]}'::JSONB,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'newer withdrawal under another version did not block capture'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_solution_experiment_reviewer;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE target_experiment_id UUID; reviewer_visible BIGINT;
BEGIN
    SELECT experiment.id INTO target_experiment_id FROM public.solution_experiment AS experiment
     WHERE hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';
    SELECT count(*) INTO reviewer_visible FROM public.solution_experiment_observation
     WHERE solution_experiment_observation.experiment_id = target_experiment_id;
    IF reviewer_visible <> 0 THEN RAISE EXCEPTION 'withdrawn consent remained visible to reviewers'; END IF;
END $$;
COMMIT;
RESET ROLE;

UPDATE public.solution_experiment
   SET consent_requirements = '{"participant_consent_required":false,"non_personal_basis":"environmental_measurement"}'::JSONB
 WHERE hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE experiment_id UUID := '__EXPERIMENT_ID__'::UUID;
        captured RECORD; denied BOOLEAN;
BEGIN
    SELECT * INTO captured FROM kokonut_security.capture_location_solution_experiment_observation(
        'b0000000-0000-4000-8000-000000000001', experiment_id,
        'ab000000-0000-4000-8000-000000000171', 'soil.organic_matter', 10.5,
        'baseline', NULL, FALSE, '{"evidence_refs":["synthetic-source"]}'::JSONB,
        NULL, TRUE
    );
    IF captured.observation_id IS NULL OR captured.replayed THEN
        RAISE EXCEPTION 'explicit non-personal basis did not allow observation';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001', experiment_id,
            'ab000000-0000-4000-8000-000000000172', 'soil.organic_matter', 10.5,
            'baseline', NULL, FALSE, '{"evidence_refs":["synthetic-source"]}'::JSONB,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'non-personal policy accepted a participant link'; END IF;
END $$;
COMMIT;
RESET ROLE;

INSERT INTO public.solution_experiment_observation (experiment_id, metric_key, arm)
SELECT experiment.id, 'soil.organic_matter', 'baseline'
  FROM public.solution_experiment AS experiment
 WHERE experiment.hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';

SET ROLE kokonut_solution_experiment_reviewer;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE legacy_id UUID; non_personal_count BIGINT;
BEGIN
    SELECT experiment.id INTO legacy_id FROM public.solution_experiment AS experiment
     WHERE hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';
    SELECT count(*) INTO non_personal_count FROM public.solution_experiment_observation
     WHERE solution_experiment_observation.experiment_id = legacy_id;
    IF non_personal_count <> 1 THEN RAISE EXCEPTION 'valid non-personal observation is not reviewable'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.capture_location_solution_experiment_observation(uuid,uuid,uuid,text,numeric,text,text,boolean,jsonb,uuid,boolean)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_experiment_observation_capture_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_experiment_observation_capture_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_experiment_observation', 'SELECT')
       OR has_table_privilege('kokonut_solution_experiment_observer', 'public.solution_experiment_observation_capture_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_experiment_observer', 'public.solution_experiment_observation_capture_receipt', 'DELETE') THEN
        RAISE EXCEPTION 'runtime, Directus, or observer role boundary is incorrect';
    END IF;
END $$;
"""

ANALYSIS_GRANT = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000085', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'analyze', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

ANALYSIS_EXPERIMENT_ID = "ed000000-0000-4000-8000-000000000051"
ANALYSIS_EXPERIMENT_SETUP = r"""
INSERT INTO public.stakeholder_consent (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at, expires_at
) VALUES (
    'e2000000-0000-4000-8000-000000000057',
    'c2000000-0000-4000-8000-000000000051', 'grant',
    'solution_experiment_participation',
    'Participation in the synthetic experiment.', 'location',
    'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v1',
    pg_catalog.clock_timestamp(), NULL
);
INSERT INTO public.solution_experiment (
    id, solution_id, hypothesis, null_hypothesis, protocol_version,
    baseline_definition, treatment_definition, comparator_definition,
    unit_of_analysis, sample_plan, primary_metric_keys, secondary_metric_keys,
    stopping_rules, rollback_plan, safety_boundaries, consent_requirements,
    status, approved_at, started_at
) VALUES (
    '__EXPERIMENT_ID__', 'c0000000-0000-4000-8000-000000000041',
    'Synthetic consent-bound analysis improves soil condition.',
    'No measurable difference from current practice.', 'v1',
    'Synthetic baseline sample.', 'Synthetic treatment sample.',
    'Compare paired field units.', 'One synthetic field unit.',
    '{"minimum_sample":4}', '["soil.organic_matter"]', '["water.retention"]',
    '{"benefit_direction_by_metric":{"soil.organic_matter":"higher","water.retention":"lower"},"benefit_threshold":0,"posterior_threshold":0.9,"safety_event_limit":1}',
    'Return to baseline after review.', '{"synthetic":true}',
    '{"participant_consent_required":true,"purpose":"Participation in the synthetic experiment.","consent_version":"v1"}',
    'active', pg_catalog.clock_timestamp(), pg_catalog.clock_timestamp()
);
INSERT INTO public.solution_experiment_observation (
    experiment_id, metric_key, value, arm, adverse_event, evidence
) VALUES (
    '__EXPERIMENT_ID__', 'soil.organic_matter', 999, 'treatment', FALSE,
    '{"historical":"unassessed synthetic row"}'::JSONB
);
"""

ANALYSIS_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE i INTEGER; arm_value TEXT; measured NUMERIC; captured RECORD;
        first_run RECORD; replay RECORD; denied BOOLEAN := FALSE;
        direct_read_denied BOOLEAN := FALSE;
BEGIN
    FOR i IN 1..16 LOOP
        arm_value := CASE WHEN (i - 1) % 8 < 4 THEN 'baseline' ELSE 'treatment' END;
        IF i <= 8 THEN
            measured := CASE WHEN i <= 4 THEN 10 + i ELSE 96 + i END;
        ELSE
            measured := CASE WHEN i <= 12 THEN 80 + i ELSE 20 + i END;
        END IF;
        SELECT * INTO captured FROM kokonut_security.capture_location_solution_experiment_observation(
            'b0000000-0000-4000-8000-000000000001',
            '__EXPERIMENT_ID__'::UUID,
            ('ab000000-0000-4000-8000-' || pg_catalog.lpad((200 + i)::TEXT, 12, '0'))::UUID,
            CASE WHEN i <= 8 THEN 'soil.organic_matter' ELSE 'water.retention' END,
            measured, arm_value, NULL, FALSE,
            '{"evidence_refs":["synthetic-analysis"]}'::JSONB,
            'd2000000-0000-4000-8000-000000000051', TRUE
        );
        IF captured.observation_id IS NULL OR captured.replayed THEN
            RAISE EXCEPTION 'analysis fixture observation did not append';
        END IF;
    END LOOP;
    SELECT * INTO captured FROM kokonut_security.capture_location_solution_experiment_observation(
        'b0000000-0000-4000-8000-000000000001', '__EXPERIMENT_ID__'::UUID,
        'ab000000-0000-4000-8000-000000000217', 'water.retention', NULL,
        'treatment', NULL, TRUE,
        '{"evidence_refs":["synthetic-safety-event"]}'::JSONB,
        'd2000000-0000-4000-8000-000000000051', TRUE
    );

    SELECT * INTO first_run FROM kokonut_security.analyze_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        '__EXPERIMENT_ID__'::UUID,
        'ab000000-0000-4000-8000-000000000209',
        'soil.organic_matter', TRUE
    );
    IF first_run.analysis_run_id IS NULL OR first_run.replayed
       OR first_run.decision <> 'benefit'
       OR first_run.benefit_direction <> 'higher'
       OR first_run.minimum_sample <> 4
       OR first_run.baseline_count <> 4
       OR first_run.treatment_count < 4
       OR first_run.effect_estimate <= 0
       OR first_run.posterior_probability_benefit < first_run.posterior_threshold
       OR first_run.adverse_event_count <> 1
       OR first_run.safety_event_limit <> 1
       OR first_run.source_observation_count <> 9
       OR first_run.analysis_version <> 'sequential-v2-consent' THEN
        RAISE EXCEPTION 'protocol-bound analysis did not return the expected advisory benefit result';
    END IF;
    SELECT * INTO replay FROM kokonut_security.analyze_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        first_run.experiment_id,
        'ab000000-0000-4000-8000-000000000209',
        'soil.organic_matter', TRUE
    );
    IF NOT replay.replayed OR replay.analysis_run_id <> first_run.analysis_run_id THEN
        RAISE EXCEPTION 'analysis retry did not replay the same result';
    END IF;
    SELECT * INTO replay FROM kokonut_security.analyze_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001', first_run.experiment_id,
        'ab000000-0000-4000-8000-000000000210', 'water.retention', TRUE
    );
    IF replay.replayed OR replay.decision <> 'benefit'
       OR replay.benefit_direction <> 'lower'
       OR replay.effect_estimate >= 0
       OR replay.posterior_probability_benefit < replay.posterior_threshold
       OR replay.source_observation_count <> 9 THEN
        RAISE EXCEPTION 'lower-is-better protocol direction was not honored';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.analyze_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001', first_run.experiment_id,
            'ab000000-0000-4000-8000-000000000209', 'soil.moisture', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'analysis request collision was accepted'; END IF;

    BEGIN
        PERFORM count(*) FROM public.solution_experiment_analysis_run;
    EXCEPTION WHEN insufficient_privilege THEN direct_read_denied := TRUE; END;
    IF NOT direct_read_denied THEN RAISE EXCEPTION 'runtime direct analysis table read was allowed'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_solution_experiment_reviewer;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
DO $$
DECLARE visible_count INTEGER;
BEGIN
    SELECT count(*)::INTEGER INTO visible_count
      FROM public.solution_experiment_analysis_run
     WHERE metric_key = 'soil.organic_matter';
    IF visible_count <> 1 THEN
        RAISE EXCEPTION 'reviewer cannot see a current-consent exact-location analysis';
    END IF;
END $$;
COMMIT;
RESET ROLE;

INSERT INTO public.stakeholder_consent (
    party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at, expires_at, reason
) VALUES (
    'c2000000-0000-4000-8000-000000000051', 'withdraw',
    'solution_experiment_participation',
    'Participation in the synthetic experiment.', 'location',
    'b0000000-0000-4000-8000-000000000001', NULL, 'system', 'v1',
    pg_catalog.clock_timestamp(), NULL, 'Synthetic consent-withdrawal acceptance'
);

SET ROLE kokonut_solution_experiment_reviewer;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
DO $$
DECLARE visible_count INTEGER;
BEGIN
    SELECT count(*)::INTEGER INTO visible_count
      FROM public.solution_experiment_analysis_run
     WHERE metric_key = 'soil.organic_matter';
    IF visible_count <> 0 THEN
        RAISE EXCEPTION 'consent withdrawal did not hide the derived analysis';
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE denied BOOLEAN := FALSE; experiment_value UUID;
BEGIN
    experiment_value := '__EXPERIMENT_ID__'::UUID;
    BEGIN
        PERFORM * FROM kokonut_security.analyze_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001', experiment_value,
            'ab000000-0000-4000-8000-000000000209', 'soil.organic_matter', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'withdrawn analysis was replayed to the analyst'; END IF;
END $$;
COMMIT;
RESET ROLE;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-experiment-observation-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "additional_migration": ANALYSIS_MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 510 applies and replays after the signed exact-location experiment lifecycle chain",
            "only active exact-origin experiments with declared metrics and arms accept observations",
            "participant observations require an active exact-location link and the latest matching canonical consent grant",
            "missing, wrong-purpose, wrong-location, expired, superseded-version, and revoked-link consent fail closed",
            "non-personal measurement requires an explicit approved basis and cannot carry a participant link",
            "request retries are idempotent and changed payload collisions are denied",
            "consent withdrawal immediately hides previously captured participant observations from reviewer RLS reads",
            "legacy unassessed observations remain hidden and direct runtime/Directus table access is denied",
            "migration 511 binds higher/lower analysis direction and stopping thresholds to the approved protocol",
            "analysis retries are idempotent and changed request payloads are rejected",
            "analysis source lineage uses only currently consent-eligible observations and exact location scope",
            "current consent withdrawal hides the derived analysis from reviewer and analyst reads",
            "runtime and Directus cannot read or mutate analysis runs, source maps, or receipts",
            "analysis remains advisory and leaves experiment and solution lifecycle state unchanged",
        ],
    }
    try:
        subprocess.run(
            [docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"],
            text=True, capture_output=True, check=True,
        )
        wait_ready(container, docker)
        base.apply_ordered_lifecycle_chain(docker, container)
        psql(docker, container, previous_check.previous_check.prior_check.prior_check.PREPARE_SCHEMA)
        psql(docker, container, PREPARE_REVIEW_TABLES)
        psql(docker, container, (ROOT / "schemas/postgres/484_location_solution_gate_review.sql").read_text(encoding="utf-8"))
        experiment_review_migration = (ROOT / "schemas/postgres/487_location_solution_experiment_review.sql").read_text(encoding="utf-8")
        psql(docker, container, experiment_review_migration)
        psql(docker, container, experiment_review_migration)
        for filename in (
            "503_location_solution_nonpromotion_stage_transition.sql",
            "504_location_solution_create.sql",
            "505_location_solution_gate_definition.sql",
            "506_location_solution_experiment_create.sql",
            "507_location_solution_experiment_submission.sql",
            "508_location_solution_experiment_protocol_review.sql",
        ):
            psql(docker, container, (ROOT / "schemas/postgres" / filename).read_text(encoding="utf-8"))
        start_migration_text = previous_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, start_migration_text)
        psql(docker, container, start_migration_text)
        psql(docker, container, previous_check.previous_check.prior_check.prior_check.FIXTURE)
        psql(docker, container, previous_check.previous_check.prior_check.EXTRA_FIXTURE)
        psql(docker, container, previous_check.previous_check.REVIEW_FIXTURE)
        psql(docker, container, previous_check.previous_check.ACCEPTANCE)
        psql(docker, container, previous_check.SIDE_EFFECT_SENTINELS)
        psql(docker, container, previous_check.START_FIXTURE)
        psql(docker, container, previous_check.ACCEPTANCE)
        experiment_id_output = psql(
            docker,
            container,
            "COPY (SELECT id::TEXT FROM public.solution_experiment "
            "WHERE hypothesis = 'Synthetic soil condition improves under the reviewed treatment.') TO STDOUT;",
        )
        experiment_ids = re.findall(
            r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            experiment_id_output,
        )
        if len(experiment_ids) != 1:
            raise RuntimeError("expected one approved synthetic experiment after migration 509")
        experiment_id = experiment_ids[0]
        uuid.UUID(experiment_id)
        psql(docker, container, f"""
        SET ROLE kokonut_runtime;
        BEGIN;
        SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
        SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
        SELECT set_config('kokonut.actor_type', 'operator', TRUE);
        SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
        SELECT * FROM kokonut_security.start_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001', '{experiment_id}'::UUID,
            'ab000000-0000-4000-8000-000000000111', TRUE
        );
        COMMIT;
        RESET ROLE;
        """)
        psql(docker, container, PREPARE_OBSERVATION_TABLES)
        migration_text = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_text)
        psql(docker, container, migration_text)
        psql(docker, container, FIXTURE)
        psql(docker, container, ACCEPTANCE.replace("__EXPERIMENT_ID__", experiment_id))
        psql(docker, container, ANALYSIS_GRANT)
        analysis_migration_text = ANALYSIS_MIGRATION.read_text(encoding="utf-8")
        psql(
            docker,
            container,
            ANALYSIS_EXPERIMENT_SETUP.replace("__EXPERIMENT_ID__", ANALYSIS_EXPERIMENT_ID),
        )
        psql(docker, container, analysis_migration_text)
        psql(docker, container, analysis_migration_text)
        psql(
            docker,
            container,
            ANALYSIS_ACCEPTANCE.replace("__EXPERIMENT_ID__", ANALYSIS_EXPERIMENT_ID),
        )
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 17
        print("PASS: migrations 510 and 511 apply/replay; consent-aware capture, directional analysis, source-lineage withdrawal, retry, and ACL checks passed")
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
