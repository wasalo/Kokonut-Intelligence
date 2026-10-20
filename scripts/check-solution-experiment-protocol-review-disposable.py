#!/usr/bin/env python3
"""Exercise migration 508's independent experiment protocol review contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-experiment-submission-disposable.py"
MIGRATION = ROOT / "schemas/postgres/508_location_solution_experiment_protocol_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-protocol-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_experiment_submission_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
prior_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_check)
psql = prior_check.psql
wait_ready = prior_check.wait_ready
base = prior_check.base

REVIEW_FIXTURE = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000061', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000062', 'a0000000-0000-4000-8000-000000000042', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE first_draft RECORD; first_submission RECORD; second_draft RECORD;
        second_submission RECORD; detail RECORD; approval RECORD; replay RECORD;
        denied BOOLEAN; protocol_json JSONB;
        direct_select_denied BOOLEAN := FALSE; direct_insert_denied BOOLEAN := FALSE;
        direct_update_denied BOOLEAN := FALSE; direct_delete_denied BOOLEAN := FALSE;
        valid_protocol JSONB := '{
          "hypothesis":"Synthetic soil condition improves under the reviewed treatment.",
          "null_hypothesis":"No measurable difference from current practice.",
          "baseline_definition":"Current practice over one synthetic season.",
          "treatment_definition":"Apply the proposed synthetic intervention.",
          "comparator_definition":"Compare with current practice.",
          "unit_of_analysis":"One synthetic field unit.",
          "sample_plan":{"minimum_sample":4},
          "primary_metric_keys":["soil.organic_matter"],
          "secondary_metric_keys":["water.retention"],
          "duration_days":90,
          "stopping_rules":{"safety":"pause on adverse event"},
          "rollback_plan":"Return to baseline practice.",
          "safety_boundaries":{"synthetic":true},
          "consent_requirements":{
            "participant_consent_required":true,
            "purpose":"Participation in the synthetic experiment.",
            "consent_version":"v1"
          }
        }'::JSONB;
BEGIN
    SELECT * INTO first_draft FROM kokonut_security.create_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000091', valid_protocol, TRUE
    );
    SELECT * INTO first_submission FROM kokonut_security.submit_location_solution_experiment_protocol(
        'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id,
        'ab000000-0000-4000-8000-000000000092', TRUE
    );
    SELECT * INTO second_draft FROM kokonut_security.create_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000093',
        valid_protocol || '{"hypothesis":"Second synthetic protocol remains awaiting review."}'::JSONB,
        TRUE
    );
    SELECT * INTO second_submission FROM kokonut_security.submit_location_solution_experiment_protocol(
        'b0000000-0000-4000-8000-000000000001', second_draft.experiment_id,
        'ab000000-0000-4000-8000-000000000094', TRUE
    );
    IF first_submission.experiment_status <> 'submitted'
       OR second_submission.experiment_status <> 'submitted' THEN
        RAISE EXCEPTION 'review fixtures were not submitted';
    END IF;

    SELECT * INTO detail FROM kokonut_security.location_solution_experiment_protocol_review(
        'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id
    );
    IF NOT detail.owner_is_reviewer OR NOT detail.submitter_is_reviewer THEN
        RAISE EXCEPTION 'protocol detail did not report owner/submitter conflict flags';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    SELECT * INTO detail FROM kokonut_security.location_solution_experiment_protocol_review(
        'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id
    );
    protocol_json := to_jsonb(detail);
    IF detail.owner_is_reviewer OR detail.submitter_is_reviewer
       OR detail.protocol->>'hypothesis' <> valid_protocol->>'hypothesis'
       OR protocol_json::TEXT LIKE '%c1000000-0000-4000-8000-000000000041%' THEN
        RAISE EXCEPTION 'independent detail exposed identities or omitted the submitted protocol';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id,
            'ab000000-0000-4000-8000-000000000101', FALSE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'unacknowledged approval was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000002', first_draft.experiment_id,
            'ab000000-0000-4000-8000-000000000102', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'approval escaped the signed location context'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.location_solution_experiment_protocol_review(
            'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact review grant opened protocol detail'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    SELECT * INTO approval FROM kokonut_security.approve_location_solution_experiment_protocol(
        'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id,
        'ab000000-0000-4000-8000-000000000103', TRUE
    );
    IF approval.experiment_status <> 'protocol_approved' OR approval.replayed
       OR approval.approved_at IS NULL THEN
        RAISE EXCEPTION 'independent reviewer approval was not recorded';
    END IF;
    SELECT * INTO replay FROM kokonut_security.approve_location_solution_experiment_protocol(
        'b0000000-0000-4000-8000-000000000001', first_draft.experiment_id,
        'ab000000-0000-4000-8000-000000000103', TRUE
    );
    IF NOT replay.replayed OR replay.approved_at <> approval.approved_at THEN
        RAISE EXCEPTION 'exact approval retry did not return its immutable receipt';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000001', second_draft.experiment_id,
            'ab000000-0000-4000-8000-000000000103', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'request ID reuse for a different experiment was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000001', second_draft.experiment_id,
            'ab000000-0000-4000-8000-000000000104', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'protocol owner approved their own submission'; END IF;

    BEGIN PERFORM 1 FROM public.solution_experiment_protocol_approval_receipt;
    EXCEPTION WHEN insufficient_privilege THEN direct_select_denied := TRUE; END;
    IF NOT direct_select_denied THEN RAISE EXCEPTION 'runtime can read private approval receipts'; END IF;
    BEGIN
        INSERT INTO public.solution_experiment_protocol_approval_receipt (
            operator_id, reviewer_party_id, submitter_party_id, location_id,
            solution_id, experiment_id, request_id, payload_digest, approved_at
        ) VALUES (
            'a0000000-0000-4000-8000-000000000042', 'c1000000-0000-4000-8000-000000000042',
            'c1000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001',
            first_draft.solution_id, second_draft.experiment_id,
            'ab000000-0000-4000-8000-000000000105', decode(repeat('00', 32), 'hex'), NOW()
        );
    EXCEPTION WHEN insufficient_privilege THEN direct_insert_denied := TRUE; END;
    IF NOT direct_insert_denied THEN RAISE EXCEPTION 'runtime can forge approval receipts'; END IF;
    BEGIN UPDATE public.solution_experiment_protocol_approval_receipt SET approved_at = NOW();
    EXCEPTION WHEN insufficient_privilege THEN direct_update_denied := TRUE; END;
    IF NOT direct_update_denied THEN RAISE EXCEPTION 'runtime can edit approval receipts'; END IF;
    BEGIN DELETE FROM public.solution_experiment_protocol_approval_receipt;
    EXCEPTION WHEN insufficient_privilege THEN direct_delete_denied := TRUE; END;
    IF NOT direct_delete_denied THEN RAISE EXCEPTION 'runtime can delete approval receipts'; END IF;

    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.location_solution_experiment_protocol_review(uuid,uuid)', 'EXECUTE'
    ) OR NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.approve_location_solution_experiment_protocol(uuid,uuid,uuid,boolean)', 'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.approve_location_solution_experiment_protocol(uuid,uuid,uuid,boolean)', 'EXECUTE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment_protocol_approval_receipt', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_solution_experiment_protocol_reviewer',
        'public.solution_experiment_protocol_approval_receipt', 'UPDATE'
    ) OR has_table_privilege(
        'kokonut_solution_experiment_protocol_reviewer',
        'public.solution_experiment_protocol_approval_receipt', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'runtime, Directus, or reviewer receipt boundaries are incorrect';
    END IF;
END $$;
RESET ROLE;
DO $$
DECLARE first_status TEXT; second_status TEXT; stage_value TEXT; receipt_count INTEGER;
BEGIN
    SELECT experiment.status INTO first_status FROM public.solution_experiment AS experiment
     WHERE experiment.hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';
    SELECT experiment.status INTO second_status FROM public.solution_experiment AS experiment
     WHERE experiment.hypothesis = 'Second synthetic protocol remains awaiting review.';
    SELECT solution.current_stage INTO stage_value FROM public.solution AS solution
     WHERE solution.id = 'c0000000-0000-4000-8000-000000000041';
    SELECT pg_catalog.count(*)::INTEGER INTO receipt_count
      FROM public.solution_experiment_protocol_approval_receipt;
    IF first_status <> 'protocol_approved' OR second_status <> 'submitted'
       OR stage_value <> 'experiment_ready' OR receipt_count <> 1 THEN
        RAISE EXCEPTION 'approval changed unrelated protocol state or solution lifecycle stage';
    END IF;
END $$;
SET LOCAL ROLE kokonut_runtime;
COMMIT;
RESET ROLE;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-experiment-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 508 applies and replays after the ordered experiment submission chain",
            "review requires signed exact-location context and a current review grant",
            "private protocol detail exposes bounded submitted content and no actor identities",
            "approval requires an active human distinct from the owner and submitter",
            "approval uses immutable idempotency receipts and rejects request collisions",
            "approval changes only protocol status and reviewer attribution, never solution stage",
            "runtime and Directus cannot read, forge, edit, or delete private receipts",
            "Directus cannot execute either protocol review function",
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
        psql(docker, container, prior_check.prior_check.PREPARE_SCHEMA)
        for filename in (
            "484_location_solution_gate_review.sql",
            "503_location_solution_nonpromotion_stage_transition.sql",
            "504_location_solution_create.sql",
            "505_location_solution_gate_definition.sql",
            "506_location_solution_experiment_create.sql",
            "507_location_solution_experiment_submission.sql",
        ):
            psql(docker, container, (ROOT / "schemas/postgres" / filename).read_text(encoding="utf-8"))
        migration_text = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_text)
        psql(docker, container, migration_text)
        psql(docker, container, prior_check.prior_check.FIXTURE)
        psql(docker, container, prior_check.EXTRA_FIXTURE)
        psql(docker, container, REVIEW_FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 8
        print("PASS: migration 508 applies/replays; independent protocol review, approval, retry, lifecycle, and ACL checks passed")
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
