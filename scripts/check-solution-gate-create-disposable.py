#!/usr/bin/env python3
"""Exercise migration 505's exact-location draft solution gate contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_CHECK = ROOT / "scripts/check-solution-create-disposable.py"
MIGRATION_503 = ROOT / "schemas/postgres/503_location_solution_nonpromotion_stage_transition.sql"
MIGRATION_504 = ROOT / "schemas/postgres/504_location_solution_create.sql"
MIGRATION_484 = ROOT / "schemas/postgres/484_location_solution_gate_review.sql"
MIGRATION_505 = ROOT / "schemas/postgres/505_location_solution_gate_definition.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-gate-create-disposable.json"
spec = importlib.util.spec_from_file_location("solution_create_disposable", BASE_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load ordered CAP-035 disposable migration helpers")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
prior = base.prior
psql = prior.psql
wait_ready = prior.wait_ready

ACTOR_FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES
    ('a0000000-0000-4000-8000-000000000041', TRUE),
    ('a0000000-0000-4000-8000-000000000042', TRUE),
    ('a0000000-0000-4000-8000-000000000043', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES
    ('c1000000-0000-4000-8000-000000000041', 'Synthetic gate creator', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000042', 'Synthetic no-grant operator', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000043', 'Synthetic unbound operator', 'person', 'active')
ON CONFLICT (id) DO UPDATE SET party_type = EXCLUDED.party_type, status = EXCLUDED.status;
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000041',
        'a0000000-0000-4000-8000-000000000041',
        'c1000000-0000-4000-8000-000000000041', NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000041', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'create', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000042', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'read', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000043', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000044', 'a0000000-0000-4000-8000-000000000043', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'create', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.solution (
    id, canonical_key, name, solution_type, problem_statement,
    originating_scope_type, originating_scope_id, current_stage, status
) VALUES
    ('c0000000-0000-4000-8000-000000000041', 'synthetic:cap035:gate-origin',
     'Synthetic exact-origin gate solution', 'practice', 'Disposable gate fixture',
     'location', 'b0000000-0000-4000-8000-000000000001', 'testing', 'active'),
    ('c0000000-0000-4000-8000-000000000042', 'synthetic:cap035:gate-other-origin',
     'Synthetic linked other-origin solution', 'practice', 'Disposable cross-scope fixture',
     'location', 'b0000000-0000-4000-8000-000000000002', 'testing', 'active')
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.solution_link (solution_id, entity_type, entity_id, relationship)
SELECT 'c0000000-0000-4000-8000-000000000042', 'location',
       'b0000000-0000-4000-8000-000000000001', 'supports'
 WHERE NOT EXISTS (
       SELECT 1 FROM public.solution_link
        WHERE solution_id = 'c0000000-0000-4000-8000-000000000042'
          AND entity_type = 'location'
          AND entity_id = 'b0000000-0000-4000-8000-000000000001'
          AND relationship = 'supports'
 );
INSERT INTO public.solution_stage_gate (
    solution_id, from_stage, to_stage, required_evidence_maturity,
    required_experiment_count, minimum_evaluation_count,
    requires_human_approval, requirements, status
) VALUES (
    'c0000000-0000-4000-8000-000000000042', 'testing', 'validated', 3,
    1, 1, TRUE, '{"criterion":"Cross-origin criterion stays private."}'::JSONB, 'draft'
)
ON CONFLICT (solution_id, from_stage, to_stage) DO NOTHING;
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE created RECORD; replay RECORD; denied BOOLEAN := FALSE;
        wrong_stage_denied BOOLEAN := FALSE; other_origin_denied BOOLEAN := FALSE;
        other_location_denied BOOLEAN := FALSE; no_grant_denied BOOLEAN := FALSE;
        no_binding_denied BOOLEAN := FALSE;
        criterion_value TEXT; external_criterion TEXT;
        changed_retry_denied BOOLEAN := FALSE; duplicate_denied BOOLEAN := FALSE;
        direct_select_denied BOOLEAN := FALSE; direct_insert_denied BOOLEAN := FALSE;
        direct_update_denied BOOLEAN := FALSE; direct_delete_denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000051', 'validated',
        'Independent field measurements support the expected outcome.', 4, 2, TRUE
    );
    IF created.gate_id IS NULL OR created.gate_status <> 'draft'
       OR created.from_stage <> 'testing' OR created.to_stage <> 'validated'
       OR created.required_evidence_maturity <> 4
       OR created.required_experiment_count <> 2
       OR created.minimum_evaluation_count <> 1
       OR NOT created.requires_human_approval OR created.replayed THEN
        RAISE EXCEPTION 'gate was not created as a bounded, independent-review draft';
    END IF;
    SELECT * INTO replay FROM kokonut_security.create_location_solution_gate(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000051', 'validated',
        'Independent field measurements support the expected outcome.', 4, 2, TRUE
    );
    IF NOT replay.replayed OR replay.gate_id <> created.gate_id THEN
        RAISE EXCEPTION 'exact retry did not return the immutable original gate';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000051', 'validated',
            'Changed criterion for the same idempotency key.', 4, 2, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN changed_retry_denied := TRUE; END;
    IF NOT changed_retry_denied THEN RAISE EXCEPTION 'changed request reused an existing gate request ID'; END IF;

    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000052', 'validated',
            'Another gate definition for the same promotion.', 4, 2, TRUE
        );
    EXCEPTION WHEN unique_violation THEN duplicate_denied := TRUE; END;
    IF NOT duplicate_denied THEN RAISE EXCEPTION 'a second gate version bypassed immutable unique stage pair'; END IF;

    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000053', 'funded',
            'A target must match the current supported promotion.', 4, 2, TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN wrong_stage_denied := TRUE; END;
    IF NOT wrong_stage_denied THEN RAISE EXCEPTION 'a non-current promotion target was accepted'; END IF;

    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000042',
            'ab000000-0000-4000-8000-000000000054', 'validated',
            'A linked solution must not be re-authored by this location.', 4, 2, TRUE
        );
    EXCEPTION WHEN no_data_found THEN other_origin_denied := TRUE; END;
    IF NOT other_origin_denied THEN RAISE EXCEPTION 'linked cross-origin solution accepted gate authoring'; END IF;

    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000055', 'validated',
            'Signed tenant location must exactly match request location.', 4, 2, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN other_location_denied := TRUE; END;
    IF NOT other_location_denied THEN RAISE EXCEPTION 'request location differed from signed context'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000056', 'validated',
            'An operator without a create grant must fail closed.', 4, 2, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN no_grant_denied := TRUE; END;
    IF NOT no_grant_denied THEN RAISE EXCEPTION 'operator without create grant created a gate'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_gate(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000057', 'validated',
            'An operator without an active human binding must fail closed.', 4, 2, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN no_binding_denied := TRUE; END;
    IF NOT no_binding_denied THEN RAISE EXCEPTION 'operator without human binding created a gate'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
    SELECT gate_criterion INTO criterion_value
      FROM kokonut_security.list_location_solution_gates(
          'b0000000-0000-4000-8000-000000000001', 50, 0
      ) WHERE gate_id = created.gate_id;
    IF criterion_value <> 'Independent field measurements support the expected outcome.' THEN
        RAISE EXCEPTION 'exact-origin read did not return the gate criterion';
    END IF;
    SELECT gate_criterion INTO external_criterion
      FROM kokonut_security.list_location_solution_gates(
          'b0000000-0000-4000-8000-000000000001', 50, 0
      ) WHERE solution_id = 'c0000000-0000-4000-8000-000000000042';
    IF external_criterion IS NOT NULL THEN
        RAISE EXCEPTION 'linked solution leaked its other-location gate criterion';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM kokonut_security.location_solution_gate_review(
            'b0000000-0000-4000-8000-000000000001', created.gate_id
        ) WHERE gate_criterion = 'Independent field measurements support the expected outcome.'
          AND evaluation_passed IS NULL
    ) THEN
        RAISE EXCEPTION 'independent reviewer cannot see the exact-origin criterion or pending state';
    END IF;

    denied := FALSE;
    BEGIN PERFORM 1 FROM public.solution_gate_definition_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read gate-definition receipts'; END IF;
    denied := FALSE;
    BEGIN PERFORM 1 FROM public.solution_stage_gate LIMIT 1;
    EXCEPTION WHEN insufficient_privilege THEN direct_select_denied := TRUE; END;
    IF NOT direct_select_denied THEN RAISE EXCEPTION 'runtime can directly read solution stage gates'; END IF;
    denied := FALSE;
    BEGIN
        INSERT INTO public.solution_stage_gate (solution_id, from_stage, to_stage)
        VALUES ('c0000000-0000-4000-8000-000000000041', 'testing', 'validated');
    EXCEPTION WHEN insufficient_privilege THEN direct_insert_denied := TRUE; END;
    IF NOT direct_insert_denied THEN RAISE EXCEPTION 'runtime can directly insert solution stage gates'; END IF;
    BEGIN UPDATE public.solution_stage_gate SET requirements = '{}' WHERE FALSE;
    EXCEPTION WHEN insufficient_privilege THEN direct_update_denied := TRUE; END;
    IF NOT direct_update_denied THEN RAISE EXCEPTION 'runtime can directly change immutable gate definitions'; END IF;
    BEGIN DELETE FROM public.solution_stage_gate WHERE FALSE;
    EXCEPTION WHEN insufficient_privilege THEN direct_delete_denied := TRUE; END;
    IF NOT direct_delete_denied THEN RAISE EXCEPTION 'runtime can directly delete solution stage gates'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE current_stage_value TEXT; gate_status_value TEXT;
        approved_party UUID; receipt_count INTEGER; eval_count INTEGER;
BEGIN
    SELECT current_stage INTO current_stage_value FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000041';
    SELECT status, approved_by_party_id INTO gate_status_value, approved_party
      FROM public.solution_stage_gate
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000041';
    SELECT count(*) INTO eval_count FROM public.solution_gate_evaluation
     WHERE gate_id = (SELECT id FROM public.solution_stage_gate
                       WHERE solution_id = 'c0000000-0000-4000-8000-000000000041');
    IF current_stage_value <> 'testing' OR gate_status_value <> 'draft'
       OR approved_party IS NOT NULL OR eval_count <> 0 THEN
        RAISE EXCEPTION 'creation evaluated, approved, or transitioned the solution';
    END IF;
    UPDATE public.solution SET current_stage = 'validated'
     WHERE id = 'c0000000-0000-4000-8000-000000000041';
END $$;
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
SELECT * FROM kokonut_security.create_location_solution_gate(
    'b0000000-0000-4000-8000-000000000001',
    'c0000000-0000-4000-8000-000000000041',
    'ab000000-0000-4000-8000-000000000051', 'validated',
    'Independent field measurements support the expected outcome.', 4, 2, TRUE
);
COMMIT;
RESET ROLE;
DO $$
DECLARE current_stage_value TEXT; gate_status_value TEXT;
        approved_party UUID; receipt_count INTEGER; eval_count INTEGER;
BEGIN
    SELECT current_stage INTO current_stage_value FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000041';
    SELECT status, approved_by_party_id INTO gate_status_value, approved_party
      FROM public.solution_stage_gate
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000041';
    SELECT count(*) INTO receipt_count FROM public.solution_gate_definition_receipt
     WHERE request_id = 'ab000000-0000-4000-8000-000000000051';
    SELECT count(*) INTO eval_count FROM public.solution_gate_evaluation
     WHERE gate_id = (SELECT gate_id FROM public.solution_gate_definition_receipt
                      WHERE request_id = 'ab000000-0000-4000-8000-000000000051');
    IF current_stage_value <> 'validated' OR gate_status_value <> 'draft'
       OR approved_party IS NOT NULL OR receipt_count <> 1 OR eval_count <> 0 THEN
        RAISE EXCEPTION 'retry after a later stage change did not replay without mutating lifecycle';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_solution_gate(uuid,uuid,uuid,text,text,integer,integer,boolean)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_solution_gate(uuid,uuid,uuid,text,text,integer,integer,boolean)',
        'EXECUTE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_gate_definition_receipt', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'INSERT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'UPDATE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'DELETE'
    ) OR has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'requirements', 'SELECT'
    ) OR has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'requirements', 'INSERT'
    ) OR has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'requirements', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_stage_gate', 'status', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_stage_gate', 'requirements', 'SELECT'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_stage_gate', 'requirements', 'INSERT'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_stage_gate', 'requirements', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_stage_gate', 'status', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Runtime/Directus gate-definition or direct-table boundaries are incorrect';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-gate-create-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_505.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 505 applies and replays after ordered migrations 503 and 504",
            "gate creation requires exact signed location context, active human, and create grant",
            "only a matching supported promotion for an active exact-origin solution can be created",
            "gate criterion and thresholds are immutable and start draft with one evaluation required",
            "retries are exact and safe after later lifecycle state changes; collisions cannot overwrite a gate",
            "creation does not evaluate, approve, or transition a solution",
            "criteria are visible to authorized readers/reviewers only for their location-origin solution",
            "runtime and Directus have no direct gate-table access; runtime uses bounded functions and neither role can read private receipts",
        ],
    }
    try:
        subprocess.run(
            [docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"],
            text=True, capture_output=True, check=True,
        )
        wait_ready(container, docker)
        prior.apply_ordered_lifecycle_chain(docker, container)
        psql(docker, container, """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
        ALTER TABLE public.solution ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE public.solution
            ADD COLUMN IF NOT EXISTS canonical_key TEXT,
            ADD COLUMN IF NOT EXISTS name TEXT,
            ADD COLUMN IF NOT EXISTS solution_type TEXT,
            ADD COLUMN IF NOT EXISTS problem_statement TEXT,
            ADD COLUMN IF NOT EXISTS theory_of_change TEXT,
            ADD COLUMN IF NOT EXISTS baseline_alternative TEXT,
            ADD COLUMN IF NOT EXISTS originating_scope_type TEXT,
            ADD COLUMN IF NOT EXISTS originating_scope_id UUID,
            ADD COLUMN IF NOT EXISTS created_by_party_id UUID,
            ADD COLUMN IF NOT EXISTS risk_class TEXT,
            ADD COLUMN IF NOT EXISTS reversibility TEXT,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE public.solution_adopter_readiness
            ADD COLUMN IF NOT EXISTS assessed_by_party_id UUID;
        ALTER TABLE public.solution_configuration
            ADD COLUMN IF NOT EXISTS approved_by_party_id UUID;
        ALTER TABLE public.solution_stage_gate
            ADD COLUMN IF NOT EXISTS requirements JSONB NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS approved_by_party_id UUID,
            ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS minimum_evaluation_count INTEGER NOT NULL DEFAULT 1
                CHECK (minimum_evaluation_count > 0);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_kokonut_solution_gate_stage_fixture
            ON public.solution_stage_gate (solution_id, from_stage, to_stage);
        ALTER TABLE public.solution_stage_gate ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE public.solution_gate_evaluation
            ADD COLUMN IF NOT EXISTS observed JSONB NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '[]',
            ADD COLUMN IF NOT EXISTS evaluated_by_party_id UUID;
        ALTER TABLE public.solution_link
            ADD COLUMN IF NOT EXISTS relationship TEXT NOT NULL DEFAULT 'supports';
        ALTER TABLE public.solution_link ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE public.solution_lifecycle_event
            ADD COLUMN IF NOT EXISTS from_stage TEXT,
            ADD COLUMN IF NOT EXISTS to_stage TEXT,
            ADD COLUMN IF NOT EXISTS rationale TEXT,
            ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::JSONB,
            ADD COLUMN IF NOT EXISTS actor_party_id UUID,
            ADD COLUMN IF NOT EXISTS rollback_plan TEXT;
        """)
        psql(docker, container, MIGRATION_484.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_503.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_504.read_text(encoding="utf-8"))
        psql(docker, container, """
        DO $$
        DECLARE target_role TEXT;
        BEGIN
            FOREACH target_role IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
                IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
                    EXECUTE pg_catalog.format(
                        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.solution_stage_gate TO %I',
                        target_role
                    );
                    EXECUTE pg_catalog.format(
                        'GRANT SELECT (requirements), INSERT (requirements), UPDATE (requirements), SELECT (status), UPDATE (status) ON TABLE public.solution_stage_gate TO %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END $$;
        """)
        psql(docker, container, MIGRATION_505.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_505.read_text(encoding="utf-8"))
        psql(docker, container, ACTOR_FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 10
        print("PASS: migration 505 applies/replays; draft gate authorization, immutable criteria, idempotency, location isolation, and privilege checks passed")
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
