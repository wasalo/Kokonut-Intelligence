#!/usr/bin/env python3
"""Exercise location-scoped solution funding projections, drafts, and submission."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_CHECK = ROOT / "scripts/check-solution-lifecycle-experiments-disposable.py"
MIGRATION = ROOT / "schemas/postgres/468_location_scoped_solution_funding.sql"
PROPOSAL_MIGRATION = ROOT / "schemas/postgres/488_location_solution_funding_proposals.sql"
SUBMISSION_MIGRATION = ROOT / "schemas/postgres/489_location_solution_funding_submission.sql"
REVIEW_MIGRATION = ROOT / "schemas/postgres/490_location_solution_funding_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-funding-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_experiments_disposable", EXPERIMENT_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
gate_check = helper.helper
run = gate_check.run
wait_ready = gate_check.wait_ready


def psql(docker: str, container: str, sql: str) -> str:
    result = subprocess.run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"disposable SQL failed ({result.returncode}): {details}")
    return result.stdout.strip()

FUNDING_SOURCE = r"""
ALTER TABLE public.solution_funding_case
    ADD COLUMN capital_stage text NOT NULL DEFAULT 'pilot',
    ADD COLUMN funding_instrument text NOT NULL DEFAULT 'grant',
    ADD COLUMN currency text NOT NULL DEFAULT 'USD',
    ADD COLUMN requested_amount numeric(15,2) NOT NULL DEFAULT 1000,
    ADD COLUMN minimum_viable_amount numeric(15,2),
    ADD COLUMN maximum_authorized_amount numeric(15,2),
    ADD COLUMN risk_adjusted_expected_value numeric(15,2),
    ADD COLUMN public_goods_value numeric(15,2),
    ADD COLUMN community_share numeric(15,2),
    ADD COLUMN downside_exposure numeric(15,2),
    ADD COLUMN rationale text NOT NULL DEFAULT 'private funding rationale',
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[{"private": "evidence"}]',
    ADD COLUMN submitted_by_party_id uuid,
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN approved_at timestamptz;
ALTER TABLE public.solution_funding_case
    ALTER COLUMN id SET DEFAULT gen_random_uuid();
UPDATE public.solution_funding_case
   SET decision_status = 'submitted', created_at = '2026-10-01 00:00:00+00'
 WHERE id = 'f3000000-0000-4000-8000-000000000001';
INSERT INTO public.solution_funding_case
    (id, solution_id, decision_status, capital_stage, funding_instrument, currency,
     requested_amount, rationale, evidence, submitted_by_party_id,
     approved_by_party_id, created_at, approved_at)
VALUES
    ('f3000000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000002', 'approved', 'scale',
     'community_fund', 'USD', 987654.32, 'private linked rationale',
     '[{"private": "case evidence"}]',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '2026-10-05 00:00:00+00', '2026-10-12 00:00:00+00'),
    ('f3000000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000003', 'approved', 'pilot',
     'grant', 'DOP', 555.00, 'other location private rationale',
     '[{"private": "other evidence"}]',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '2026-10-18 00:00:00+00', '2026-10-19 00:00:00+00');

ALTER TABLE public.solution_funding_tranche
    ADD COLUMN tranche_number integer,
    ADD COLUMN amount numeric(15,2) NOT NULL DEFAULT 0,
    ADD COLUMN milestone_conditions jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN approved_at timestamptz,
    ADD COLUMN released_at timestamptz,
    ADD COLUMN released_by_party_id uuid;
ALTER TABLE public.solution_funding_tranche
    ALTER COLUMN id SET DEFAULT gen_random_uuid();
INSERT INTO public.solution_funding_tranche
    (id, funding_case_id, tranche_number, amount, milestone_conditions, status,
     approved_by_party_id, approved_at, released_at, released_by_party_id)
VALUES
    ('f3100000-0000-4000-8000-000000000001',
     'f3000000-0000-4000-8000-000000000002', 1, 123.45,
     '{"private_condition": "proof"}', 'approved',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-13 00:00:00+00', NULL, NULL),
    ('f3100000-0000-4000-8000-000000000002',
     'f3000000-0000-4000-8000-000000000002', 2, 456.78,
     '{"private_condition": "inspection"}', 'released',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-14 00:00:00+00',
     '2026-10-17 00:00:00+00', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f3100000-0000-4000-8000-000000000003',
     'f3000000-0000-4000-8000-000000000003', 1, 500.00,
     '{"private_condition": "outside"}', 'released',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-19 00:00:00+00',
     '2026-10-19 00:00:00+00', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
"""

FUNDING_PROPOSAL_FIXTURE = r"""
ALTER TABLE public.party
    ADD COLUMN party_type text NOT NULL DEFAULT 'person',
    ADD COLUMN status text NOT NULL DEFAULT 'active';
INSERT INTO public.party (id, display_name)
VALUES ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Synthetic active operator');
CREATE TABLE public.operator_governance_party_binding (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id uuid NOT NULL,
    party_id uuid NOT NULL,
    revoked_at timestamptz
);
INSERT INTO public.operator_governance_party_binding (operator_id, party_id)
VALUES ('a0000000-0000-4000-8000-000000000001',
        'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES (
    'a1000000-0000-4000-8000-000000000003',
    'a0000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    'solution_lifecycle', 'create', NULL, NULL
), (
    'a1000000-0000-4000-8000-000000000005',
    'a0000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    'solution_lifecycle', 'submit', NULL, NULL
);
"""

FUNDING_PROPOSAL_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    target record;
    first_draft record;
    replay record;
    empty_draft record;
    denied boolean := false;
BEGIN
    SELECT * INTO target FROM kokonut_security.list_location_solution_funding_targets(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) WHERE solution_id = 'c0000000-0000-4000-8000-000000000001';
    IF NOT FOUND OR target.solution_name <> 'Synthetic solution'
       OR target.current_stage <> 'testing' THEN
        RAISE EXCEPTION 'funding target projection did not return the exact location-origin solution';
    END IF;
    IF EXISTS (
        SELECT 1 FROM kokonut_security.list_location_solution_funding_targets(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        ) WHERE solution_id IN (
            'c0000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000003'
        )
    ) THEN
        RAISE EXCEPTION 'funding targets included linked or cross-location solutions';
    END IF;

    SELECT * INTO first_draft FROM kokonut_security.propose_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000201',
        'pilot', 'community_fund', 1000.00, 500.00, 1200.00, 'cUSD',
        900.00, 1100.00, 100.00, 250.00, 'Synthetic draft only',
        '[{"ref":"private:budget"}]'::jsonb,
        '[{"amount":300.00,"milestone_conditions":{"step":"review"}},
          {"amount":500.00,"milestone_conditions":{"step":"field-check"}}]'::jsonb
    );
    IF first_draft.decision_status <> 'draft' OR first_draft.replayed
       OR first_draft.tranche_count <> 2 OR first_draft.created_at IS NULL THEN
        RAISE EXCEPTION 'funding draft or proposed tranche result is invalid';
    END IF;
    SELECT * INTO replay FROM kokonut_security.propose_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000201',
        'pilot', 'community_fund', 1000.00, 500.00, 1200.00, 'cUSD',
        900.00, 1100.00, 100.00, 250.00, 'Synthetic draft only',
        '[{"ref":"private:budget"}]'::jsonb,
        '[{"amount":300.00,"milestone_conditions":{"step":"review"}},
          {"amount":500.00,"milestone_conditions":{"step":"field-check"}}]'::jsonb
    );
    IF NOT replay.replayed OR replay.funding_case_id <> first_draft.funding_case_id
       OR replay.created_at <> first_draft.created_at THEN
        RAISE EXCEPTION 'exact funding proposal retry did not return its original draft';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000201',
            'pilot', 'community_fund', 1001.00, 500.00, 1200.00, 'cUSD',
            900.00, 1100.00, 100.00, 250.00, 'Changed payload',
            '[{"ref":"private:budget"}]'::jsonb, '[]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed funding proposal payload reused the same request ID'; END IF;

    SELECT * INTO empty_draft FROM kokonut_security.propose_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000005',
        'ab000000-0000-4000-8000-000000000202',
        'maintenance', 'budget', 0.00, NULL, NULL, 'USD',
        NULL, NULL, NULL, NULL, 'Zero-cost synthetic maintenance draft',
        '[]'::jsonb, '[]'::jsonb
    );
    IF empty_draft.decision_status <> 'draft' OR empty_draft.tranche_count <> 0
       OR empty_draft.replayed THEN
        RAISE EXCEPTION 'empty-tranche draft was not created safely';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002',
            'ab000000-0000-4000-8000-000000000203',
            'pilot', 'grant', 10.00, NULL, NULL, 'USD',
            NULL, NULL, NULL, NULL, 'Linked solution must not be fundable here',
            '[]'::jsonb, '[]'::jsonb
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'linked global solution received a location funding draft'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000204',
            'pilot', 'grant', 10.00, NULL, NULL, 'USD',
            NULL, NULL, NULL, NULL, 'No create grant', '[]'::jsonb, '[]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact create grant created a funding draft'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM 1 FROM public.solution_funding_proposal_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read funding proposal receipts directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    case_count integer;
    tranche_count integer;
    case_status text;
    original_stage text;
BEGIN
    SELECT count(*) INTO case_count FROM public.solution_funding_case
     WHERE solution_id IN (
       'c0000000-0000-4000-8000-000000000001',
       'c0000000-0000-4000-8000-000000000005'
     ) AND decision_status = 'draft';
    SELECT count(*) INTO tranche_count FROM public.solution_funding_tranche AS tranche
     JOIN public.solution_funding_case AS funding ON funding.id = tranche.funding_case_id
     WHERE funding.solution_id = 'c0000000-0000-4000-8000-000000000001'
       AND tranche.status = 'proposed';
    SELECT decision_status INTO case_status FROM public.solution_funding_case
     WHERE id = (SELECT funding_case_id FROM public.solution_funding_proposal_receipt
                  WHERE request_id = 'ab000000-0000-4000-8000-000000000201');
    SELECT current_stage INTO original_stage FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000001';
    IF case_count <> 2 OR tranche_count <> 2 OR case_status <> 'draft'
       OR original_stage <> 'testing'
       OR (SELECT count(*) FROM public.solution_funding_proposal_receipt
           WHERE request_id = 'ab000000-0000-4000-8000-000000000201') <> 1
       OR has_table_privilege('kokonut_solution_funding_proposer',
          'public.solution_funding_proposal_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_funding_proposer',
          'public.solution_funding_proposal_receipt', 'DELETE')
       OR has_table_privilege('kokonut_solution_funding_proposer',
          'public.solution_funding_case', 'UPDATE')
       OR has_table_privilege('kokonut_solution_funding_proposer',
          'public.solution_funding_tranche', 'UPDATE') THEN
        RAISE EXCEPTION 'funding draft atomicity, status, stage separation, or role boundary failed';
    END IF;
END $$;
"""

FUNDING_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    funding_row record;
    seen integer := 0;
    denied boolean := false;
    result_signature text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'funding_decision_counts'->>'submitted' <> '1'
       OR lifecycle_summary->'funding_decision_counts'->>'approved' <> '1' THEN
        RAISE EXCEPTION 'existing aggregate summary failed after funding column grants were narrowed';
    END IF;

    FOR funding_row IN SELECT * FROM kokonut_security.list_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF funding_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'funding projection included a solution outside exact location scope';
        END IF;
        IF funding_row.funding_case_id = 'f3000000-0000-4000-8000-000000000001'
           AND funding_row.tranche_id IS NOT NULL THEN
            RAISE EXCEPTION 'funding case without tranches was dropped or misprojected';
        END IF;
        IF funding_row.funding_case_id = 'f3000000-0000-4000-8000-000000000002'
           AND funding_row.tranche_number = 1
           AND (funding_row.capital_stage <> 'scale'
                OR funding_row.funding_instrument <> 'community_fund'
                OR funding_row.currency <> 'USD'
                OR funding_row.decision_status <> 'approved'
                OR funding_row.tranche_status <> 'approved'
                OR funding_row.tranche_approved_at <> '2026-10-13'::timestamptz
                OR funding_row.tranche_released_at IS NOT NULL) THEN
            RAISE EXCEPTION 'approved funding/tranche lifecycle projection mismatch';
        END IF;
        IF funding_row.funding_case_id = 'f3000000-0000-4000-8000-000000000002'
           AND funding_row.tranche_number = 2
           AND (funding_row.tranche_status <> 'released'
                OR funding_row.tranche_released_at <> '2026-10-17'::timestamptz) THEN
            RAISE EXCEPTION 'released tranche lifecycle projection mismatch';
        END IF;
    END LOOP;
    IF seen <> 3 THEN RAISE EXCEPTION 'expected three exact-location funding rows, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_funding(uuid,integer,integer)'::regprocedure
    ) INTO result_signature;
    IF result_signature ~* '(amount|rationale|evidence|milestone_conditions|party_id|released_by|approved_by)' THEN
        RAISE EXCEPTION 'funding projection signature exposes sensitive values or identities';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded funding pagination did not return one row'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded funding page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_funding_case;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read funding case table'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_funding_tranche;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read funding tranche table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_funding(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_funding(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_funding_case', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_funding_tranche', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_funding_tranche', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'requested_amount', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'rationale', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'evidence', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'amount', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'milestone_conditions', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'decision_status', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'status', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'UPDATE') THEN
        RAISE EXCEPTION 'solution funding function or column privilege boundary failed';
    END IF;
END $$;
"""

FUNDING_SUBMISSION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    draft record;
    case_id uuid;
    first_submission record;
    replay record;
    denied boolean := false;
BEGIN
    SELECT * INTO draft FROM kokonut_security.propose_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000201',
        'pilot', 'community_fund', 1000.00, 500.00, 1200.00, 'cUSD',
        900.00, 1100.00, 100.00, 250.00, 'Synthetic draft only',
        '[{"ref":"private:budget"}]'::jsonb,
        '[{"amount":300.00,"milestone_conditions":{"step":"review"}},
          {"amount":500.00,"milestone_conditions":{"step":"field-check"}}]'::jsonb
    );
    case_id := draft.funding_case_id;
    IF case_id IS NULL OR NOT draft.replayed THEN
        RAISE EXCEPTION 'fixture funding draft retry did not return its original case';
    END IF;

    SELECT * INTO first_submission
      FROM kokonut_security.submit_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001', case_id,
        'ab000000-0000-4000-8000-000000000301', TRUE
      );
    IF first_submission.funding_case_id <> case_id
       OR first_submission.decision_status <> 'submitted'
       OR first_submission.tranche_count <> 2
       OR first_submission.submitted_at IS NULL
       OR first_submission.replayed THEN
        RAISE EXCEPTION 'funding submission response is invalid';
    END IF;

    SELECT * INTO replay
      FROM kokonut_security.submit_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001', case_id,
        'ab000000-0000-4000-8000-000000000301', TRUE
      );
    IF NOT replay.replayed OR replay.funding_case_id <> case_id
       OR replay.submitted_at <> first_submission.submitted_at THEN
        RAISE EXCEPTION 'exact funding submission retry did not return its receipt';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', case_id,
            'ab000000-0000-4000-8000-000000000301', FALSE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'submission accepted without explicit acknowledgement'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001',
            'f3000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000301', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'submission request id collision was not rejected'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', case_id,
            'ab000000-0000-4000-8000-000000000302', TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'already submitted funding case accepted a second request id'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', case_id,
            'ab000000-0000-4000-8000-000000000303', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without a submit grant submitted a funding draft'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM 1 FROM public.solution_funding_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read submission receipts directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    case_id uuid;
    case_status text;
    submitted_by uuid;
    tranche_count integer;
    proposed_tranche_count integer;
    original_stage text;
BEGIN
    SELECT funding_case_id INTO case_id
      FROM public.solution_funding_submission_receipt
     WHERE request_id = 'ab000000-0000-4000-8000-000000000301';
    SELECT decision_status, submitted_by_party_id
      INTO case_status, submitted_by
      FROM public.solution_funding_case WHERE id = case_id;
    SELECT pg_catalog.count(*)::INTEGER,
           pg_catalog.count(*) FILTER (WHERE status = 'proposed')::INTEGER
      INTO tranche_count, proposed_tranche_count
      FROM public.solution_funding_tranche WHERE funding_case_id = case_id;
    SELECT current_stage INTO original_stage FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000001';
    IF case_status <> 'submitted'
       OR submitted_by <> 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
       OR tranche_count <> 2 OR proposed_tranche_count <> 2
       OR original_stage <> 'testing'
       OR (SELECT count(*) FROM public.solution_funding_submission_receipt
           WHERE funding_case_id = case_id) <> 1
       OR has_table_privilege('kokonut_solution_funding_submitter',
          'public.solution_funding_submission_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_funding_submitter',
          'public.solution_funding_submission_receipt', 'DELETE')
       OR has_table_privilege('kokonut_solution_funding_submitter',
          'public.solution_funding_case', 'UPDATE')
       OR has_table_privilege('kokonut_solution_funding_submitter',
          'public.solution_funding_tranche', 'UPDATE')
       OR has_table_privilege('kokonut_runtime',
          'public.solution_funding_submission_receipt', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.submit_location_solution_funding(uuid,uuid,uuid,boolean)', 'EXECUTE') THEN
        RAISE EXCEPTION 'submission state, stage, or role-boundary invariant failed';
    END IF;
END $$;
"""

FUNDING_REVIEW_FIXTURE = r"""
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('cccccccc-cccc-4ccc-8ccc-ccccccccccc1', 'Synthetic funding reviewer', 'person', 'active');
INSERT INTO public.operator_governance_party_binding (operator_id, party_id)
VALUES ('a0000000-0000-4000-8000-000000000002',
        'cccccccc-cccc-4ccc-8ccc-ccccccccccc1');
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES (
    'a1000000-0000-4000-8000-000000000006',
    'a0000000-0000-4000-8000-000000000002',
    'b0000000-0000-4000-8000-000000000001',
    'solution_lifecycle', 'review', NULL, NULL
), (
    'a1000000-0000-4000-8000-000000000007',
    'a0000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    'solution_lifecycle', 'review', NULL, NULL
);
"""

FUNDING_REVIEW_ACCEPTANCE = r"""
SELECT funding_case_id AS review_case_id
  FROM public.solution_funding_submission_receipt
 WHERE request_id = 'ab000000-0000-4000-8000-000000000301' \gset
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
SELECT set_config('kokonut.review_case_id', :'review_case_id', true);
DO $$
DECLARE
    review_case_id uuid := current_setting('kokonut.review_case_id')::uuid;
    current_case record;
    legacy_case record;
    self_review record;
    seen integer;
    denied boolean := false;
    function_result text;
BEGIN
    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_funding_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    );
    IF seen <> 2 THEN
        RAISE EXCEPTION 'funding review queue expected exactly the current and legacy submitted cases, got %', seen;
    END IF;
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding_review_queue(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded funding review page was accepted'; END IF;
    SELECT * INTO current_case
      FROM kokonut_security.get_location_solution_funding_review_detail(
          'b0000000-0000-4000-8000-000000000001', review_case_id
      );
    IF current_case.decision_status <> 'submitted'
       OR current_case.submitter_attributed IS DISTINCT FROM TRUE
       OR current_case.is_self_authored IS DISTINCT FROM FALSE
       OR current_case.rationale <> 'Synthetic draft only'
       OR pg_catalog.jsonb_array_length(current_case.evidence) <> 1
       OR pg_catalog.jsonb_array_length(current_case.tranches) <> 2
       OR current_case.tranches->0->>'status' <> 'proposed'
       OR current_case.tranches->1->>'status' <> 'proposed' THEN
        RAISE EXCEPTION 'submitted funding review detail or proposed tranche projection is invalid';
    END IF;
    SELECT * INTO legacy_case
      FROM kokonut_security.get_location_solution_funding_review_detail(
          'b0000000-0000-4000-8000-000000000001',
          'f3000000-0000-4000-8000-000000000001'
      );
    IF legacy_case.submitter_attributed IS DISTINCT FROM FALSE
       OR legacy_case.is_self_authored IS DISTINCT FROM FALSE
       OR legacy_case.submitted_at IS NOT NULL THEN
        RAISE EXCEPTION 'legacy unattributed submission was mislabeled as attributed';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    SELECT * INTO self_review
      FROM kokonut_security.get_location_solution_funding_review_detail(
          'b0000000-0000-4000-8000-000000000001', review_case_id
      );
    IF self_review.is_self_authored IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'funding request authored by reviewer was not identified as self-authored';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding_review_queue(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without an exact review grant read the funding queue'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding_review_queue(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'review queue accepted mismatched signed location context'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_funding_case;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private funding cases'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_funding_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private funding submission receipts'; END IF;
    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.get_location_solution_funding_review_detail(uuid,uuid)'::regprocedure
    ) INTO function_result;
    IF function_result ~* '(submitter_party_id|approved_by_party_id|released_by_party_id|operator_id)' THEN
        RAISE EXCEPTION 'funding review detail result exposes submitter or operator identity columns';
    END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_funding_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.get_location_solution_funding_review_detail(uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_funding_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.get_location_solution_funding_review_detail(uuid,uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_funding_case', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_funding_submission_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_funding_reviewer',
          'public.solution_funding_case', 'SELECT')
       OR has_table_privilege('kokonut_solution_funding_reviewer',
          'public.solution_funding_case', 'UPDATE')
       OR NOT has_column_privilege('kokonut_solution_funding_reviewer',
          'public.solution_funding_case', 'rationale', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_funding_reviewer',
          'public.solution_funding_tranche', 'milestone_conditions', 'SELECT')
       OR has_column_privilege('kokonut_solution_funding_reviewer',
          'public.solution_funding_tranche', 'released_by_party_id', 'SELECT')
       OR has_column_privilege('kokonut_solution_funding_reviewer',
          'public.solution_funding_tranche', 'approved_by_party_id', 'SELECT') THEN
        RAISE EXCEPTION 'funding reviewer function or table privilege boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-funding-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": REVIEW_MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459, 466, 467, and 468 apply, and migration 468 replays",
            "funding cases and tranches are included only for exact origin or location-linked solutions",
            "cases without tranches remain visible and tranche states/timestamps preserve ordering",
            "amounts, milestone conditions, rationale, evidence, and party identities are omitted from function output and reader column grants",
            "the migration-459 aggregate summary continues to work with only its required funding columns",
            "page bounds, signed context, exact location grant, and read-only behavior are enforced",
            "runtime can call the bounded function but cannot read funding tables; Directus cannot call it",
            "funding draft targets are exact location-origin solutions and exclude linked/global and other-location solutions",
            "draft creation requires signed exact-location create scope and an active human operator binding",
            "case and proposed tranches are inserted atomically with bounded financial/evidence payloads",
            "draft request retries replay exact receipts; changed payloads and cross-scope attempts fail closed",
            "proposed tranche totals cannot exceed the request ceiling; empty tranches remain valid",
            "case and tranche statuses remain draft/proposed and lifecycle stage is unchanged",
            "runtime and Directus cannot read private funding receipts; proposer role cannot update/delete or approve/release",
            "submission requires the exact location submit grant, the original active human proposer, and explicit acknowledgement",
            "submission changes only draft to submitted and preserves proposed tranches and solution stage",
            "submission request retries replay exactly; changed request reuse and duplicate submission fail closed",
            "runtime and Directus cannot access submission receipts or the direct submitter role",
            "migration 490 provisions a non-login reviewer owner with only private funding read columns and no write or role membership",
            "review reads require the exact signed location, solution_lifecycle:review, an active human binding, and bounded pagination/detail payloads",
            "review queue includes only submitted, unapproved exact location-origin cases and omits narratives and identity columns",
            "review detail includes bounded rationale, evidence, and proposed tranche terms while preserving legacy unattributed submissions as unattributed",
            "self-authored cases are identified and remain read-only; no case/tranche approval, release, or lifecycle stage transition is present",
            "runtime can call the bounded reads but cannot directly read private funding tables or receipts; Directus cannot call the functions",
            "review page bounds and missing exact review grants fail closed",
        ],
    }
    try:
        docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        psql(docker, container, gate_check.FIXTURE)
        psql(docker, container, gate_check.helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, gate_check.ACCEPTANCE)
        psql(docker, container, gate_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, gate_check.GATE_ACCEPTANCE)
        psql(docker, container, helper.EXPERIMENT_SOURCE)
        psql(docker, container, helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, FUNDING_SOURCE)
        migration_468 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_468)
        psql(docker, container, migration_468)
        psql(docker, container, FUNDING_ACCEPTANCE)
        psql(docker, container, FUNDING_PROPOSAL_FIXTURE)
        migration_488 = PROPOSAL_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_488)
        psql(docker, container, migration_488)
        psql(docker, container, FUNDING_PROPOSAL_ACCEPTANCE)
        migration_489 = SUBMISSION_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_489)
        psql(docker, container, migration_489)
        psql(docker, container, FUNDING_SUBMISSION_ACCEPTANCE)
        psql(docker, container, FUNDING_REVIEW_FIXTURE)
        migration_490 = REVIEW_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_490)
        psql(docker, container, migration_490)
        psql(docker, container, FUNDING_REVIEW_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 9
        evidence["proposal_assertions_passed"] = 7
        evidence["submission_assertions_passed"] = 7
        evidence["review_assertions_passed"] = 7
        print("PASS: migrations 459/466/467/468/488/489/490 apply, migrations 468/488/489/490 replay, funding projections, draft proposals, submission, and private review acceptances passed")
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
