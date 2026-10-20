#!/usr/bin/env python3
"""Exercise migration 483 on isolated PostgreSQL 16 fixtures."""

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
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-gate-evaluation-disposable.json"
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
     'solution_lifecycle', 'create', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Synthetic evaluator', 'person', 'active');
INSERT INTO public.operator_governance_party_binding
    (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000001',
        'a0000000-0000-4000-8000-000000000001',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', NULL);
UPDATE public.solution_stage_gate
   SET status = 'draft'
 WHERE id = 'e0000000-0000-4000-8000-000000000001';
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


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-gate-eval-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 483 applies and replays after the location-scoped gate read",
            "signed exact location context, create grant, active human attribution, and exact-origin gate lineage are enforced",
            "bounded pass/fail observations and evidence are appended under a non-login evaluator owner",
            "same request retries return the original result while changed input collisions fail closed",
            "runtime cannot read idempotency receipts directly and Directus cannot execute the function",
            "evaluation receipts are append-only and the action does not approve the gate",
        ],
    }
    try:
        subprocess.run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ], check=True, text=True, capture_output=True)
        wait_ready(container, docker)
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
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 8
        print("PASS: migrations 459, 466, and 483 apply; 466 and 483 replay; eight gate-evaluation acceptance groups passed")
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
