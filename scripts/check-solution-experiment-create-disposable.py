#!/usr/bin/env python3
"""Exercise migration 506's exact-location experiment protocol draft contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-gate-create-disposable.py"
MIGRATION = ROOT / "schemas/postgres/506_location_solution_experiment_create.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-create-disposable.json"
spec = importlib.util.spec_from_file_location("solution_gate_create_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
prior_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_check)
psql = prior_check.psql
wait_ready = prior_check.wait_ready
base = prior_check.prior

PREPARE_SCHEMA = r"""
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
ALTER TABLE public.solution_adopter_readiness ADD COLUMN IF NOT EXISTS assessed_by_party_id UUID;
ALTER TABLE public.solution_configuration ADD COLUMN IF NOT EXISTS approved_by_party_id UUID;
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
ALTER TABLE public.solution_experiment
    ADD COLUMN IF NOT EXISTS null_hypothesis TEXT,
    ADD COLUMN IF NOT EXISTS protocol_version VARCHAR(40) NOT NULL DEFAULT 'v1',
    ADD COLUMN IF NOT EXISTS baseline_definition TEXT NOT NULL DEFAULT 'synthetic baseline',
    ADD COLUMN IF NOT EXISTS treatment_definition TEXT NOT NULL DEFAULT 'synthetic treatment',
    ADD COLUMN IF NOT EXISTS comparator_definition TEXT,
    ADD COLUMN IF NOT EXISTS unit_of_analysis TEXT NOT NULL DEFAULT 'synthetic unit',
    ADD COLUMN IF NOT EXISTS sample_plan JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS primary_metric_keys JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS secondary_metric_keys JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS minimum_detectable_effect NUMERIC,
    ADD COLUMN IF NOT EXISTS confidence_target NUMERIC,
    ADD COLUMN IF NOT EXISTS duration_days INTEGER,
    ADD COLUMN IF NOT EXISTS stopping_rules JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS rollback_plan TEXT NOT NULL DEFAULT 'synthetic rollback',
    ADD COLUMN IF NOT EXISTS safety_boundaries JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS consent_requirements JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS owner_party_id UUID,
    ADD COLUMN IF NOT EXISTS approved_by_party_id UUID,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE public.solution_experiment ALTER COLUMN id SET DEFAULT gen_random_uuid();
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT;
    END IF;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.solution_experiment TO kokonut_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.solution_experiment TO kokonut_directus_runtime;
    GRANT INSERT (hypothesis, status), UPDATE (hypothesis, status)
        ON TABLE public.solution_experiment TO kokonut_runtime;
    GRANT INSERT (hypothesis, status), UPDATE (hypothesis, status)
        ON TABLE public.solution_experiment TO kokonut_directus_runtime;
END $$;
"""

FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES
    ('a0000000-0000-4000-8000-000000000041', TRUE),
    ('a0000000-0000-4000-8000-000000000042', TRUE),
    ('a0000000-0000-4000-8000-000000000043', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES
    ('c1000000-0000-4000-8000-000000000041', 'Synthetic experiment creator', 'person', 'active'),
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
    ('a6000000-0000-4000-8000-000000000041', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'create', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.solution (
    id, canonical_key, name, solution_type, problem_statement,
    originating_scope_type, originating_scope_id, current_stage, status
) VALUES
    ('c0000000-0000-4000-8000-000000000041', 'synthetic:cap035:experiment-origin',
     'Synthetic exact-origin experiment solution', 'practice', 'Disposable experiment fixture',
     'location', 'b0000000-0000-4000-8000-000000000001', 'experiment_ready', 'active'),
    ('c0000000-0000-4000-8000-000000000042', 'synthetic:cap035:experiment-other-origin',
     'Synthetic linked other-origin solution', 'practice', 'Disposable cross-scope fixture',
     'location', 'b0000000-0000-4000-8000-000000000002', 'experiment_ready', 'active'),
    ('c0000000-0000-4000-8000-000000000043', 'synthetic:cap035:experiment-wrong-stage',
     'Synthetic wrong-stage solution', 'practice', 'Disposable non-ready fixture',
     'location', 'b0000000-0000-4000-8000-000000000001', 'framed', 'active')
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
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE created RECORD; replay RECORD; denied BOOLEAN;
        direct_insert_denied BOOLEAN := FALSE; direct_protocol_update_denied BOOLEAN := FALSE;
        direct_delete_denied BOOLEAN := FALSE; direct_receipt_denied BOOLEAN := FALSE;
        protocol_value TEXT;
        valid_protocol JSONB := '{
          "hypothesis":"Synthetic treatment improves water reliability.",
          "baseline_definition":"Current practice over one growing season.",
          "treatment_definition":"Use the proposed retention practice.",
          "unit_of_analysis":"One synthetic field unit.",
          "sample_plan":{"minimum_sample":4},
          "primary_metric_keys":["water.reliability"],
          "secondary_metric_keys":["soil.moisture"],
          "confidence_target":0.95,
          "duration_days":90,
          "stopping_rules":{"safety":"pause if adverse event"},
          "rollback_plan":"Return to baseline practice after review.",
          "safety_boundaries":{"synthetic":true},
          "consent_requirements":{"review_required":true}
        }'::JSONB;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000061', valid_protocol, TRUE
    );
    IF created.experiment_id IS NULL OR created.experiment_status <> 'draft'
       OR created.protocol_version <> 'v1' OR created.replayed THEN
        RAISE EXCEPTION 'protocol was not created as a draft';
    END IF;
    SELECT * INTO replay FROM kokonut_security.create_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000061', valid_protocol, TRUE
    );
    IF NOT replay.replayed OR replay.experiment_id <> created.experiment_id THEN
        RAISE EXCEPTION 'exact retry did not return the original experiment';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000061',
            valid_protocol || '{"hypothesis":"Changed hypothesis."}'::JSONB, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed retry payload was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000062', valid_protocol, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'requested location bypassed signed tenant context'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000042',
            'ab000000-0000-4000-8000-000000000063', valid_protocol, TRUE
        );
    EXCEPTION WHEN no_data_found THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'linked cross-origin solution accepted experiment authoring'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000043',
            'ab000000-0000-4000-8000-000000000064', valid_protocol, TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'non-ready solution accepted protocol draft'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000065', valid_protocol, FALSE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'unacknowledged protocol draft was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000066',
            valid_protocol || '{"unreviewed_owner":"not allowed"}'::JSONB, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'unsupported protocol field was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041',
            'ab000000-0000-4000-8000-000000000067', valid_protocol, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without create grant created a protocol'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
    SELECT hypothesis INTO protocol_value FROM public.solution_experiment
     WHERE id = created.experiment_id;
    IF protocol_value <> 'Synthetic treatment improves water reliability.' THEN
        RAISE EXCEPTION 'created draft does not contain the requested protocol';
    END IF;
    denied := FALSE;
    BEGIN
        INSERT INTO public.solution_experiment (
            solution_id, hypothesis, baseline_definition, treatment_definition,
            unit_of_analysis, rollback_plan, owner_party_id
        ) VALUES (
            'c0000000-0000-4000-8000-000000000041', 'direct insert', 'baseline',
            'treatment', 'unit', 'rollback', 'c1000000-0000-4000-8000-000000000041'
        );
    EXCEPTION WHEN insufficient_privilege THEN direct_insert_denied := TRUE; END;
    IF NOT direct_insert_denied THEN RAISE EXCEPTION 'runtime can directly insert experiment protocols'; END IF;

    denied := FALSE;
    BEGIN
        UPDATE public.solution_experiment SET hypothesis = 'mutated definition'
         WHERE id = created.experiment_id;
    EXCEPTION WHEN insufficient_privilege THEN direct_protocol_update_denied := TRUE; END;
    IF NOT direct_protocol_update_denied THEN RAISE EXCEPTION 'runtime can mutate protocol definition'; END IF;
    UPDATE public.solution_experiment SET status = 'submitted'
     WHERE id = created.experiment_id AND status = 'draft';
    IF NOT FOUND THEN RAISE EXCEPTION 'legacy lifecycle status update was not preserved'; END IF;

    denied := FALSE;
    BEGIN DELETE FROM public.solution_experiment WHERE id = created.experiment_id;
    EXCEPTION WHEN insufficient_privilege THEN direct_delete_denied := TRUE; END;
    IF NOT direct_delete_denied THEN RAISE EXCEPTION 'runtime can directly delete protocol drafts'; END IF;
    denied := FALSE;
    BEGIN PERFORM 1 FROM public.solution_experiment_creation_receipt;
    EXCEPTION WHEN insufficient_privilege THEN direct_receipt_denied := TRUE; END;
    IF NOT direct_receipt_denied THEN RAISE EXCEPTION 'runtime can read private creation receipts'; END IF;

    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_solution_experiment(uuid,uuid,uuid,jsonb,boolean)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_solution_experiment(uuid,uuid,uuid,jsonb,boolean)',
        'EXECUTE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment', 'INSERT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment', 'UPDATE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment', 'DELETE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment_creation_receipt', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'runtime/Directus experiment creation boundaries are incorrect';
    END IF;
END $$;
RESET ROLE;
DO $$
BEGIN
    IF (SELECT current_stage FROM public.solution
         WHERE id = 'c0000000-0000-4000-8000-000000000041') <> 'experiment_ready' THEN
        RAISE EXCEPTION 'protocol drafting changed the solution lifecycle stage';
    END IF;
END $$;
SET LOCAL ROLE kokonut_runtime;
COMMIT;
RESET ROLE;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-experiment-create-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 506 applies and replays after the ordered CAP-035 lifecycle chain",
            "protocol creation requires signed exact-location create grant and active human binding",
            "only active exact-origin solutions at experiment_ready or testing can receive a draft",
            "protocol fields and JSON payload are bounded and immutable after creation",
            "exact retries replay; changed retries, cross-origin/location, wrong-stage, and missing-grant requests fail",
            "creation remains draft-only and leaves solution lifecycle stage unchanged",
            "runtime may update only lifecycle fields; runtime and Directus cannot insert/update definitions or delete drafts",
            "runtime can execute only the bounded function; Directus cannot execute or read private receipts",
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
        psql(docker, container, PREPARE_SCHEMA)
        psql(docker, container, prior_check.MIGRATION_484.read_text(encoding="utf-8"))
        psql(docker, container, prior_check.MIGRATION_503.read_text(encoding="utf-8"))
        psql(docker, container, prior_check.MIGRATION_504.read_text(encoding="utf-8"))
        psql(docker, container, prior_check.MIGRATION_505.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 11
        print("PASS: migration 506 applies/replays; experiment draft scope, retry, protocol immutability, lifecycle, and ACL checks passed")
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
