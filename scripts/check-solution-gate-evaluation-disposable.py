#!/usr/bin/env python3
"""Exercise migrations 483–487 on isolated PostgreSQL 16 fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_CHECK = ROOT / "scripts/check-solution-lifecycle-gates-disposable.py"
MIGRATION = ROOT / "schemas/postgres/483_location_solution_gate_evaluation.sql"
REVIEW_MIGRATION = ROOT / "schemas/postgres/484_location_solution_gate_review.sql"
COMPATIBILITY_MIGRATION = ROOT / "schemas/postgres/485_solution_gate_nonhuman_approval_compatibility.sql"
TRANSITION_MIGRATION = ROOT / "schemas/postgres/486_location_solution_gate_transition.sql"
EXPERIMENT_REVIEW_MIGRATION = ROOT / "schemas/postgres/487_location_solution_experiment_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_gates_disposable", GATE_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution gate fixtures")
gate_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate_check)
summary_check = gate_check.helper
wait_ready = gate_check.wait_ready


def psql(docker: str, container: str, sql: str) -> str:
    command = [
        docker, "exec", "-i", container, "psql", "-X", "-q",
        "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ]
    result = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if result.returncode:
        lines = (result.stderr or result.stdout).strip().splitlines()
        errors = [
            line.strip() for line in lines
            if any(marker in line for marker in ("ERROR:", "DETAIL:", "CONTEXT:", "HINT:"))
        ]
        summary = " | ".join(errors or lines[-5:])
        raise RuntimeError(f"psql failed ({result.returncode}): {summary[:1200]}")
    return result.stdout.strip()

EVALUATOR_FIXTURE = r"""
ALTER TABLE public.party
    ADD COLUMN party_type text NOT NULL DEFAULT 'person',
    ADD COLUMN status text NOT NULL DEFAULT 'active';
CREATE TABLE public.operator_governance_party_binding (
    id uuid PRIMARY KEY,
    operator_id uuid NOT NULL REFERENCES public.operator_identity(id),
    party_id uuid NOT NULL REFERENCES public.party(id),
    revoked_at timestamptz
);
ALTER TABLE public.solution_gate_evaluation
    ADD COLUMN observed jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN evaluated_by_party_id uuid;
ALTER TABLE public.solution_gate_evaluation
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN evaluated_at SET DEFAULT now();
ALTER TABLE public.solution_stage_gate
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN approved_at timestamptz,
    ADD COLUMN minimum_evaluation_count integer NOT NULL DEFAULT 1
        CHECK (minimum_evaluation_count > 0);
ALTER TABLE public.solution
    ADD COLUMN evidence_maturity integer,
    ADD COLUMN retired_at timestamptz,
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.solution_adopter_readiness ADD COLUMN assessed_by_party_id uuid;
ALTER TABLE public.solution_configuration ADD COLUMN approved_by_party_id uuid;
ALTER TABLE public.solution_scale_gate ADD COLUMN approved_by_party_id uuid;
ALTER TABLE public.solution_funding_case ADD COLUMN approved_by_party_id uuid;
CREATE TABLE public.solution_lifecycle_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id uuid NOT NULL REFERENCES public.solution(id),
    from_stage text,
    to_stage text NOT NULL,
    rationale text NOT NULL,
    evidence jsonb NOT NULL DEFAULT '[]',
    rollback_plan text,
    actor_party_id uuid REFERENCES public.party(id),
    approved_by_party_id uuid REFERENCES public.party(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
UPDATE public.location
   SET organization_id = 'f0000000-0000-4000-8000-000000000001'
 WHERE id = 'b0000000-0000-4000-8000-000000000002';
INSERT INTO public.location_tenant_owner_verification
    (id, location_id, organization_id, revoked_at)
VALUES ('a3000000-0000-4000-8000-000000000002',
        'b0000000-0000-4000-8000-000000000002',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_identity (id, enabled)
VALUES ('a0000000-0000-4000-8000-000000000003', true);
INSERT INTO public.operator_organization_membership
    (id, operator_id, organization_id, revoked_at)
VALUES ('a2000000-0000-4000-8000-000000000003',
        'a0000000-0000-4000-8000-000000000003',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_organization_membership
    (id, operator_id, organization_id, revoked_at)
VALUES ('a2000000-0000-4000-8000-000000000004',
        'a0000000-0000-4000-8000-000000000002',
        'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a1000000-0000-4000-8000-000000000003',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', 'f0000000-0000-4000-8000-000000000001', NULL),
    ('a1000000-0000-4000-8000-000000000004',
     'a0000000-0000-4000-8000-000000000003',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', 'f0000000-0000-4000-8000-000000000001', NULL),
    ('a1000000-0000-4000-8000-000000000005',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000002',
     'solution_lifecycle', 'create', 'f0000000-0000-4000-8000-000000000001', NULL),
    ('a1000000-0000-4000-8000-000000000006',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
    ('a1000000-0000-4000-8000-000000000007',
     'a0000000-0000-4000-8000-000000000002',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
    ('a1000000-0000-4000-8000-000000000008',
     'a0000000-0000-4000-8000-000000000002',
     'b0000000-0000-4000-8000-000000000002',
     'solution_lifecycle', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
    ('a1000000-0000-4000-8000-000000000009',
     'a0000000-0000-4000-8000-000000000002',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'transition', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Synthetic evaluator', 'person', 'active'),
       ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Synthetic independent reviewer', 'person', 'active');
INSERT INTO public.operator_governance_party_binding
    (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000001',
        'a0000000-0000-4000-8000-000000000001',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', NULL),
       ('a5000000-0000-4000-8000-000000000002',
        'a0000000-0000-4000-8000-000000000002',
        'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', NULL);
UPDATE public.solution_stage_gate
   SET status = 'draft'
 WHERE id = 'e0000000-0000-4000-8000-000000000001';
INSERT INTO public.solution_stage_gate
    (id, solution_id, status, from_stage, to_stage,
     requires_human_approval, created_at)
VALUES ('e0000000-0000-4000-8000-000000000003',
        'c0000000-0000-4000-8000-000000000001',
        'draft', 'testing', 'validated', true, now()),
       ('e0000000-0000-4000-8000-000000000004',
        'c0000000-0000-4000-8000-000000000001',
        'draft', 'testing', 'validated', true, now()),
       ('e0000000-0000-4000-8000-000000000005',
        'c0000000-0000-4000-8000-000000000001',
        'draft', 'testing', 'validated', false, now());
INSERT INTO public.solution_gate_evaluation
    (id, gate_id, passed, evaluated_at, observed, evidence,
     evaluated_by_party_id)
VALUES ('e1000000-0000-4000-8000-000000000004',
        'e0000000-0000-4000-8000-000000000004', false,
        '2026-10-04', '{"reviewed_experiments":1}',
        '[{"source":"failed-review-fixture"}]',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
       ('e1000000-0000-4000-8000-000000000005',
        'e0000000-0000-4000-8000-000000000005', true,
        '2026-10-05', '{"reviewed_experiments":2}',
        '[{"source":"not-required-fixture"}]',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
"""

EVALUATION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    first_result record;
    retry_result record;
    second_result record;
    denied boolean := false;
BEGIN
    SELECT * INTO first_result FROM kokonut_security.record_location_solution_gate_evaluation(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000001',
        true,
        '{"validated_experiments":2}'::jsonb,
        '[{"source":"reviewed-field-record"}]'::jsonb
    );
    IF first_result.replayed OR NOT first_result.passed OR first_result.evaluated_at IS NULL THEN
        RAISE EXCEPTION 'first gate evaluation did not return its attributed result';
    END IF;

    SELECT * INTO retry_result FROM kokonut_security.record_location_solution_gate_evaluation(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000001',
        true,
        '{"validated_experiments":2}'::jsonb,
        '[{"source":"reviewed-field-record"}]'::jsonb
    );
    IF NOT retry_result.replayed OR retry_result.evaluation_id <> first_result.evaluation_id THEN
        RAISE EXCEPTION 'identical evaluation retry did not return its original result';
    END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000002',
            'e0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000001',
            true,
            '{"validated_experiments":2}'::jsonb,
            '[{"source":"reviewed-field-record"}]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'evaluation request replayed from a different location'; END IF;
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000001',
            false,
            '{"validated_experiments":2}'::jsonb,
            '[{"source":"reviewed-field-record"}]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed payload reused an evaluation request ID'; END IF;

    SELECT * INTO second_result FROM kokonut_security.record_location_solution_gate_evaluation(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000002',
        false,
        '{"validated_experiments":1}'::jsonb,
        '[{"source":"reviewed-field-record-2"}]'::jsonb
    );
    IF second_result.replayed OR second_result.passed THEN
        RAISE EXCEPTION 'independent failed evaluation was not appended';
    END IF;

    PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000003',
        'ab000000-0000-4000-8000-000000000008',
        true,
        '{"reviewed_experiments":2}'::jsonb,
        '[{"source":"independent-gate-review-fixture"}]'::jsonb
    );
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000002',
            'e0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000003',
            true, '{}'::jsonb, '[{"source":"x"}]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000004',
            true, '{}'::jsonb, '[{"source":"x"}]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without active human binding was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000005',
            true, '{}'::jsonb, '[{"source":"x"}]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact create grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000002',
            'ab000000-0000-4000-8000-000000000006',
            true, '{}'::jsonb, '[{"source":"x"}]'::jsonb
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'location-linked but non-origin solution gate was writable'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.record_location_solution_gate_evaluation(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000007',
            true, '[]'::jsonb, '[{"source":"x"}]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'non-object observed values were accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_gate_evaluation;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read gate evaluations'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_gate_evaluation_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read evaluation receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.record_location_solution_gate_evaluation(uuid,uuid,uuid,boolean,jsonb,jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.record_location_solution_gate_evaluation(uuid,uuid,uuid,boolean,jsonb,jsonb)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_gate_evaluation_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_gate_evaluation_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_gate_evaluator', 'public.solution_gate_evaluation_submission_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_gate_evaluator', 'public.solution_gate_evaluation_submission_receipt', 'DELETE')
       OR has_column_privilege('kokonut_solution_gate_evaluator', 'public.solution_gate_evaluation_submission_receipt', 'id', 'UPDATE')
       OR has_table_privilege('kokonut_solution_gate_evaluator', 'public.solution_gate_evaluation', 'UPDATE')
       OR has_column_privilege('kokonut_solution_gate_evaluator', 'public.solution_stage_gate', 'status', 'UPDATE') THEN
        RAISE EXCEPTION 'evaluator function or append-only role boundary failed';
    END IF;
END $$;
"""

TRANSITION_PREP = r"""
UPDATE public.solution_gate_evaluation
   SET passed = true
 WHERE id = 'e1000000-0000-4000-8000-000000000004';
UPDATE public.solution_stage_gate
   SET status = 'approved',
       approved_by_party_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
 WHERE id = 'e0000000-0000-4000-8000-000000000004';
"""

NONHUMAN_TRANSITION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE result record;
BEGIN
    SELECT * INTO result FROM kokonut_security.transition_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000005',
        'ad000000-0000-4000-8000-000000000005',
        'Legacy-compatible approved gate transition',
        '[{"source":"reviewed-evidence"}]'::jsonb,
        NULL
    );
    IF result.replayed OR result.to_stage <> 'validated' THEN
        RAISE EXCEPTION 'non-human-review gate did not retain its approved transition behavior';
    END IF;
END $$;
ROLLBACK;
RESET ROLE;
"""

TRANSITION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    result record;
    retry_result record;
    denied boolean := false;
BEGIN
    -- A gate approved by its own evaluator cannot be used to advance a stage.
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000004',
            'ad000000-0000-4000-8000-000000000004',
            'Attempt a self-approved transition',
            '[{"source":"reviewed-evidence"}]'::jsonb,
            NULL
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'self-approved human gate advanced a solution'; END IF;

    SELECT * INTO result FROM kokonut_security.transition_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000003',
        'ad000000-0000-4000-8000-000000000003',
        'Evidence supports the validated stage',
        '[{"source":"reviewed-field-record"}]'::jsonb,
        'Return to testing if outcomes regress'
    );
    IF result.replayed OR result.from_stage <> 'testing'
       OR result.to_stage <> 'validated' OR result.solution_status <> 'active'
       OR result.lifecycle_event_id IS NULL OR result.transitioned_at IS NULL THEN
        RAISE EXCEPTION 'first approved gate transition returned the wrong lifecycle result';
    END IF;

    SELECT * INTO retry_result FROM kokonut_security.transition_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000003',
        'ad000000-0000-4000-8000-000000000003',
        'Evidence supports the validated stage',
        '[{"source":"reviewed-field-record"}]'::jsonb,
        'Return to testing if outcomes regress'
    );
    IF NOT retry_result.replayed
       OR retry_result.lifecycle_event_id <> result.lifecycle_event_id THEN
        RAISE EXCEPTION 'identical transition retry did not return the original lifecycle event';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000003',
            'ad000000-0000-4000-8000-000000000003',
            'Changed rationale for the same request',
            '[{"source":"reviewed-field-record"}]'::jsonb,
            'Return to testing if outcomes regress'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed transition payload reused a request ID'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_gate(
            'b0000000-0000-4000-8000-000000000002',
            'e0000000-0000-4000-8000-000000000003',
            'ad000000-0000-4000-8000-000000000006',
            'Evidence supports the validated stage',
            '[{"source":"reviewed-field-record"}]'::jsonb,
            NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched tenant context advanced a location solution'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_gate_transition_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read transition receipts'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_lifecycle_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read lifecycle event evidence'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE event_count integer; receipt_count integer; current_stage text;
BEGIN
    SELECT solution.current_stage INTO current_stage
      FROM public.solution AS solution
     WHERE solution.id = 'c0000000-0000-4000-8000-000000000001';
    SELECT count(*) INTO event_count FROM public.solution_lifecycle_event
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000001';
    SELECT count(*) INTO receipt_count FROM public.solution_gate_transition_submission_receipt
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000001';
    IF current_stage <> 'validated' OR event_count <> 1 OR receipt_count <> 1 THEN
        RAISE EXCEPTION 'stage, lifecycle event, and idempotency receipt were not atomic';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.transition_location_solution_gate(uuid,uuid,uuid,text,jsonb,text)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.transition_location_solution_gate(uuid,uuid,uuid,text,jsonb,text)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_gate_transition_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_gate_transition_submission_receipt', 'SELECT')
       OR has_column_privilege('kokonut_solution_gate_transitioner', 'public.solution_stage_gate', 'status', 'UPDATE')
       OR has_column_privilege('kokonut_solution_gate_transitioner', 'public.solution_gate_transition_submission_receipt', 'payload_digest', 'UPDATE')
       OR has_table_privilege('kokonut_solution_gate_transitioner', 'public.solution_lifecycle_event', 'DELETE') THEN
        RAISE EXCEPTION 'transition function or least-privilege role boundary failed';
    END IF;
END $$;
"""

GATE_REVIEW_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    review_row record;
    first_approval record;
    retry_approval record;
    denied boolean := false;
    row_count integer;
BEGIN
    SELECT * INTO review_row
      FROM kokonut_security.location_solution_gate_review(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000003'
      );
    IF NOT FOUND OR review_row.evaluation_passed IS DISTINCT FROM TRUE
       OR review_row.observed <> '{"reviewed_experiments":2}'::jsonb
       OR review_row.evidence <> '[{"source":"independent-gate-review-fixture"}]'::jsonb THEN
        RAISE EXCEPTION 'review detail did not return the latest scoped evaluation evidence';
    END IF;
    IF pg_catalog.pg_get_function_result(
        'kokonut_security.location_solution_gate_review(uuid,uuid)'::regprocedure
    ) ~* 'evaluated_by_party_id|reviewer_party_id' THEN
        RAISE EXCEPTION 'review projection exposes an evaluator or reviewer identity';
    END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    SELECT count(*) INTO row_count FROM kokonut_security.location_solution_gate_review(
        'b0000000-0000-4000-8000-000000000002',
        'e0000000-0000-4000-8000-000000000003'
    );
    IF row_count <> 0 THEN RAISE EXCEPTION 'cross-location gate detail was returned'; END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.location_solution_gate_review(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without review grant read private gate evidence'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000003',
            'ac000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'gate evaluator approved their own evaluation'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'e0000000-0000-4000-8000-000000000004',
            'ac000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'gate with a failed latest evaluation was approved'; END IF;

    SELECT * INTO first_approval FROM kokonut_security.approve_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000003',
        'ac000000-0000-4000-8000-000000000003'
    );
    IF first_approval.replayed OR first_approval.gate_status <> 'approved'
       OR first_approval.approved_at IS NULL THEN
        RAISE EXCEPTION 'independent gate approval did not update status and attribution';
    END IF;
    SELECT * INTO retry_approval FROM kokonut_security.approve_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000003',
        'ac000000-0000-4000-8000-000000000003'
    );
    IF NOT retry_approval.replayed
       OR retry_approval.approved_at <> first_approval.approved_at THEN
        RAISE EXCEPTION 'identical approval retry did not return the saved result';
    END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_gate(
            'b0000000-0000-4000-8000-000000000002',
            'e0000000-0000-4000-8000-000000000003',
            'ac000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'approval request ID replayed across locations'; END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    SELECT * INTO first_approval FROM kokonut_security.approve_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000005',
        'ac000000-0000-4000-8000-000000000005'
    );
    IF first_approval.replayed OR first_approval.gate_status <> 'approved' THEN
        RAISE EXCEPTION 'gate without independent-review requirement did not preserve legacy approval behavior';
    END IF;
    SELECT * INTO retry_approval FROM kokonut_security.approve_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'e0000000-0000-4000-8000-000000000005',
        'ac000000-0000-4000-8000-000000000005'
    );
    IF NOT retry_approval.replayed THEN
        RAISE EXCEPTION 'gate without independent-review requirement did not preserve approval retry';
    END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_gate_approval_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read gate approval receipts'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_gate_evaluation;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read gate evaluation evidence'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_solution_gate_review(uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.approve_location_solution_gate(uuid,uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.location_solution_gate_review(uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.approve_location_solution_gate(uuid,uuid,uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_gate_approval_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_gate_approval_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_gate_reviewer', 'public.solution_stage_gate', 'UPDATE')
       OR has_column_privilege('kokonut_solution_gate_approver', 'public.solution_stage_gate', 'from_stage', 'UPDATE')
       OR has_column_privilege('kokonut_solution_gate_approver', 'public.solution_gate_approval_submission_receipt', 'id', 'UPDATE') THEN
        RAISE EXCEPTION 'gate review/approval role or function boundary failed';
    END IF;
END $$;
"""

EXPERIMENT_REVIEW_FIXTURE = r"""
ALTER TABLE public.solution_experiment
    ADD COLUMN hypothesis text NOT NULL DEFAULT 'Synthetic hypothesis',
    ADD COLUMN null_hypothesis text,
    ADD COLUMN protocol_version text NOT NULL DEFAULT 'v1',
    ADD COLUMN baseline_definition text NOT NULL DEFAULT 'Synthetic baseline',
    ADD COLUMN treatment_definition text NOT NULL DEFAULT 'Synthetic treatment',
    ADD COLUMN comparator_definition text,
    ADD COLUMN unit_of_analysis text NOT NULL DEFAULT 'plot',
    ADD COLUMN sample_plan jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN primary_metric_keys jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN secondary_metric_keys jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN stopping_rules jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN rollback_plan text NOT NULL DEFAULT 'Restore prior practice',
    ADD COLUMN safety_boundaries jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN consent_requirements jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN owner_party_id uuid,
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN approved_at timestamptz,
    ADD COLUMN started_at timestamptz,
    ADD COLUMN completed_at timestamptz,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.solution_experiment_result
    ADD COLUMN primary_results jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN secondary_results jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN limitations text,
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN reviewed_by_party_id uuid,
    ADD COLUMN reviewed_at timestamptz,
    ADD CONSTRAINT solution_experiment_result_experiment_unique UNIQUE (experiment_id);
ALTER TABLE public.solution_experiment_result
    ALTER COLUMN id SET DEFAULT gen_random_uuid();
CREATE TABLE public.solution_experiment_observation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id uuid NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    unit_ref text,
    metric_key text NOT NULL,
    value numeric,
    arm text NOT NULL,
    adverse_event boolean NOT NULL DEFAULT false,
    evidence jsonb NOT NULL DEFAULT '{}',
    recorded_by_party_id uuid
);
CREATE TABLE public.solution_experiment_analysis_run (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id uuid NOT NULL,
    metric_key text NOT NULL,
    baseline_count integer NOT NULL DEFAULT 0,
    treatment_count integer NOT NULL DEFAULT 0,
    baseline_mean numeric,
    treatment_mean numeric,
    effect_estimate numeric,
    standard_error numeric,
    lower_bound numeric,
    upper_bound numeric,
    posterior_probability_benefit numeric,
    adverse_event_count integer NOT NULL DEFAULT 0,
    decision text NOT NULL,
    stopping_reason text NOT NULL,
    analysis_version text NOT NULL DEFAULT 'sequential-v1',
    created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.solution_experiment (
    id, solution_id, status, hypothesis, null_hypothesis, protocol_version,
    baseline_definition, treatment_definition, comparator_definition,
    unit_of_analysis, sample_plan, primary_metric_keys, secondary_metric_keys,
    stopping_rules, rollback_plan, safety_boundaries, consent_requirements,
    owner_party_id, approved_by_party_id, approved_at, started_at, completed_at
) VALUES
    ('f0000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000001', 'completed',
     'Soil health improves under treatment', 'There is no material change', 'v2',
     'Baseline soil sample', 'Cover crop treatment', 'Adjacent untreated plot',
     'plot', '{"plots":4}', '["soil_organic_matter"]', '["water_retention"]',
     '{"stop_on_adverse_event":true}', 'Restore the prior crop plan',
     '{"max_slope_change":0.1}', '{"participant_consent":true}',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     now(), now() - interval '14 days', now()),
    ('f0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000001', 'completed',
     'Synthetic owner-authored review case', NULL, 'v1', 'Baseline', 'Treatment', NULL,
     'plot', '{}', '[]', '[]', '{}', 'Rollback', '{}', '{}',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     now(), now() - interval '14 days', now()),
    ('f0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000001', 'completed',
     'Synthetic protocol-approver review case', NULL, 'v1', 'Baseline', 'Treatment', NULL,
     'plot', '{}', '[]', '[]', '{}', 'Rollback', '{}', '{}',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     now(), now() - interval '14 days', now()),
    ('f0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000003', 'completed',
     'Synthetic second-location review case', NULL, 'v1', 'Baseline', 'Treatment', NULL,
     'plot', '{}', '[]', '[]', '{}', 'Rollback', '{}', '{}',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     now(), now() - interval '14 days', now());
INSERT INTO public.solution_experiment_observation (
    id, experiment_id, observed_at, unit_ref, metric_key, value, arm,
    adverse_event, evidence, recorded_by_party_id
) VALUES
    ('f0100000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000003',
     now() - interval '2 days', 'private-unit-reference', 'soil_organic_matter', 3.2,
     'treatment', false, '{"source":"field-evidence:sample-1"}',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f0100000-0000-4000-8000-000000000002', 'f0000000-0000-4000-8000-000000000003',
     now() - interval '1 day', 'private-unit-reference-2', 'soil_organic_matter', 2.8,
     'baseline', false, '{"source":"field-evidence:sample-2"}',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
INSERT INTO public.solution_experiment_analysis_run (
    id, experiment_id, metric_key, baseline_count, treatment_count, baseline_mean,
    treatment_mean, effect_estimate, standard_error, lower_bound, upper_bound,
    posterior_probability_benefit, adverse_event_count, decision, stopping_reason,
    analysis_version, created_at
) VALUES (
    'f0200000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000003',
    'soil_organic_matter', 1, 1, 2.8, 3.2, 0.4, 0.1, 0.2, 0.6,
    0.99, 0, 'benefit', 'posterior threshold reached', 'sequential-v2', now()
);
UPDATE public.solution_experiment
   SET status = 'completed'
 WHERE id = 'f0000000-0000-4000-8000-000000000001';
"""

EXPERIMENT_REVIEW_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    detail record;
    first_result record;
    retry_result record;
    denied boolean := false;
    rows_seen integer;
BEGIN
    SELECT * INTO detail FROM kokonut_security.location_solution_experiment_review(
        'b0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000003'
    );
    IF NOT FOUND OR detail.experiment_id <> 'f0000000-0000-4000-8000-000000000003'
       OR detail.protocol->>'hypothesis' <> 'Soil health improves under treatment'
       OR detail.latest_analysis->>'decision' <> 'benefit'
       OR jsonb_array_length(detail.observations) <> 2
       OR detail.observation_count <> 2
       OR detail.observations_truncated THEN
        RAISE EXCEPTION 'private experiment review detail did not return the bounded exact-origin fixture';
    END IF;
    IF detail.observations::text LIKE '%private-unit-reference%'
       OR pg_catalog.pg_get_function_result(
           'kokonut_security.location_solution_experiment_review(uuid,uuid)'::regprocedure
       ) ~* '(reviewed_by_party_id|recorded_by_party_id|unit_ref)' THEN
        RAISE EXCEPTION 'private experiment review leaked observation-unit or party identities';
    END IF;

    SELECT * INTO first_result FROM kokonut_security.review_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000003',
        'ab000000-0000-4000-8000-000000000101',
        'validated', '{"yield_delta":0.2}'::jsonb, '{}'::jsonb,
        'Small synthetic sample', '[{"source":"field-review:run-1"}]'::jsonb
    );
    IF first_result.replayed OR first_result.outcome <> 'validated'
       OR first_result.reviewed_at IS NULL THEN
        RAISE EXCEPTION 'independent experiment result was not recorded';
    END IF;
    SELECT * INTO retry_result FROM kokonut_security.review_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000003',
        'ab000000-0000-4000-8000-000000000101',
        'validated', '{"yield_delta":0.2}'::jsonb, '{}'::jsonb,
        'Small synthetic sample', '[{"source":"field-review:run-1"}]'::jsonb
    );
    IF NOT retry_result.replayed OR retry_result.reviewed_at <> first_result.reviewed_at THEN
        RAISE EXCEPTION 'identical experiment review retry did not return its first receipt';
    END IF;
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'ab000000-0000-4000-8000-000000000101',
            'invalidated', '{"yield_delta":0.2}'::jsonb, '{}'::jsonb,
            'Small synthetic sample', '[{"source":"field-review:run-1"}]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed result reused the same review request ID'; END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000002',
            'f0000000-0000-4000-8000-000000000003',
            'ab000000-0000-4000-8000-000000000101',
            'validated', '{"yield_delta":0.2}'::jsonb, '{}'::jsonb,
            'Small synthetic sample', '[{"source":"field-review:run-1"}]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'experiment review receipt replayed across locations'; END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.location_solution_experiment_review(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000006'
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location experiment review detail was returned'; END IF;
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000006',
            'ab000000-0000-4000-8000-000000000102',
            'validated', '{}'::jsonb, '{}'::jsonb, NULL, '[]'::jsonb
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location experiment result was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.location_solution_experiment_review(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without review grant accessed experiment evidence'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.location_solution_experiment_review(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'experiment with an existing result remained in the review detail'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000105',
            'validated', '{}'::jsonb, '{}'::jsonb, NULL, '[]'::jsonb
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'a second experiment result was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000004',
            'ab000000-0000-4000-8000-000000000103',
            'validated', '{}'::jsonb, '{}'::jsonb, NULL, '[]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'experiment owner reviewed their own result'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000005',
            'ab000000-0000-4000-8000-000000000104',
            'validated', '{}'::jsonb, '{}'::jsonb, NULL, '[]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'protocol approver reviewed their own experiment result'; END IF;

    denied := false;
    BEGIN
        PERFORM hypothesis FROM public.solution_experiment;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read experiment protocol directly'; END IF;
    denied := false;
    BEGIN
        PERFORM 1 FROM public.solution_experiment_review_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read experiment review receipts directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_solution_experiment_review(uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.review_location_solution_experiment(uuid,uuid,uuid,text,jsonb,jsonb,text,jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.location_solution_experiment_review(uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.review_location_solution_experiment(uuid,uuid,uuid,text,jsonb,jsonb,text,jsonb)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_experiment_review_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_experiment_review_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_experiment_reviewer', 'public.solution_experiment_review_submission_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_experiment_reviewer', 'public.solution_experiment_review_submission_receipt', 'DELETE')
       OR has_column_privilege('kokonut_solution_experiment_reviewer', 'public.solution_experiment_review_submission_receipt', 'payload', 'UPDATE')
       OR has_table_privilege('kokonut_solution_experiment_reviewer', 'public.solution_experiment_observation', 'UPDATE')
       OR has_column_privilege('kokonut_solution_experiment_reviewer', 'public.solution_experiment', 'hypothesis', 'UPDATE') THEN
        RAISE EXCEPTION 'experiment review function or non-login role boundary failed';
    END IF;
END $$;
"""

EXPERIMENT_REVIEW_FINAL_ACCEPTANCE = r"""
DO $$
DECLARE
    experiment_status text;
    solution_stage text;
    receipt_count integer;
    result_count integer;
BEGIN
    SELECT status INTO experiment_status
      FROM public.solution_experiment
     WHERE id = 'f0000000-0000-4000-8000-000000000003';
    SELECT current_stage INTO solution_stage
      FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000001';
    SELECT count(*) INTO receipt_count
      FROM public.solution_experiment_review_submission_receipt
     WHERE experiment_id = 'f0000000-0000-4000-8000-000000000003';
    SELECT count(*) INTO result_count
      FROM public.solution_experiment_result
     WHERE experiment_id = 'f0000000-0000-4000-8000-000000000003'
       AND outcome = 'validated'
       AND reviewed_by_party_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
       AND primary_results = '{"yield_delta":0.2}'::jsonb;
    IF experiment_status <> 'validated' OR solution_stage <> 'validated'
       OR receipt_count <> 1 OR result_count <> 1 THEN
        RAISE EXCEPTION 'experiment review did not update only its own outcome with one attributed receipt';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-gate-eval-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": EXPERIMENT_REVIEW_MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 483 through 487 apply and replay after the location-scoped gate read",
            "signed exact location context, create grant, active human attribution, and exact-origin gate lineage are enforced",
            "bounded pass/fail observations and evidence are appended under a non-login evaluator owner",
            "same request retries return the original result while changed input collisions fail closed",
            "runtime cannot read idempotency receipts directly and Directus cannot execute the function",
            "evaluation receipts are append-only and the action does not approve the gate",
            "private evaluation evidence is visible only under exact review scope and an active human binding",
            "migration 484 exposes bounded private review detail without evaluator identity",
            "gates requiring human approval require a latest passing evaluation and a distinct active human reviewer",
            "gates without an independent-review requirement preserve their legacy approval and retry path",
            "gate approval leaves solution stage transition separate",
            "approval retries are atomic and idempotent, with exact scope, grant, and non-login role boundaries",
            "approval receipts are atomic/idempotent and runtime/Directus cannot access source or receipt tables directly",
            "only an approved passing promotion gate advances the exact location-origin solution after legacy prerequisites pass",
            "human-required gate approval remains distinct from the latest evaluator at transition time",
            "stage update, attributed lifecycle event, and immutable idempotency receipt are atomic and retries return the original event",
            "non-human-review gates preserve their compatibility path and Directus/runtime cannot access private source or receipt tables directly",
            "private experiment protocol, latest analysis, and at most 100 observations require active exact-location review scope",
            "location-origin experiment result review requires an active human distinct from both owner and protocol approver",
            "review result, experiment status update, and private idempotency receipt are atomic and identical retries return the original result",
            "changed-payload and cross-location request reuse, linked-origin access, missing review grants, and existing results fail closed",
            "runtime/Directus cannot access experiment review receipts or invoke the scoped review functions directly",
        ],
    }
    try:
        subprocess.run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ], check=True, text=True, capture_output=True)
        wait_ready(container, docker)
        psql(docker, container, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        psql(docker, container, gate_check.FIXTURE)
        psql(docker, container, summary_check.MIGRATION.read_text(encoding="utf-8"))
        # The gate acceptance fixture includes the summary acceptance seed rows
        # plus the gate-specific columns and records; apply it only once.
        psql(docker, container, gate_check.ACCEPTANCE)
        gate_migration = gate_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, gate_migration)
        psql(docker, container, gate_migration)
        psql(docker, container, gate_check.GATE_ACCEPTANCE)
        psql(docker, container, EVALUATOR_FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        psql(docker, container, EVALUATION_ACCEPTANCE)
        review_migration = REVIEW_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, review_migration)
        psql(docker, container, review_migration)
        compatibility_migration = COMPATIBILITY_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, compatibility_migration)
        psql(docker, container, compatibility_migration)
        psql(docker, container, GATE_REVIEW_ACCEPTANCE)
        psql(docker, container, TRANSITION_PREP)
        transition_migration = TRANSITION_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, transition_migration)
        psql(docker, container, transition_migration)
        psql(docker, container, NONHUMAN_TRANSITION_ACCEPTANCE)
        psql(docker, container, TRANSITION_ACCEPTANCE)
        psql(docker, container, EXPERIMENT_REVIEW_FIXTURE)
        experiment_review_migration = EXPERIMENT_REVIEW_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, experiment_review_migration)
        psql(docker, container, experiment_review_migration)
        psql(docker, container, EXPERIMENT_REVIEW_ACCEPTANCE)
        psql(docker, container, EXPERIMENT_REVIEW_FINAL_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 8
        evidence["approval_acceptance_groups_passed"] = 7
        evidence["transition_acceptance_groups_passed"] = 7
        evidence["experiment_review_acceptance_groups_passed"] = 10
        print("PASS: migrations 459, 466, and 483–487 apply; 466 and 483–487 replay; gate evaluation, independent review, lifecycle transition, and experiment result review acceptance passed")
        result = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        result = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
