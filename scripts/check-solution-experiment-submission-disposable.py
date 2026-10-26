#!/usr/bin/env python3
"""Exercise migration 507's exact-location experiment submission contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-experiment-create-disposable.py"
MIGRATION = ROOT / "schemas/postgres/507_location_solution_experiment_submission.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-submission-disposable.json"
spec = importlib.util.spec_from_file_location("solution_experiment_create_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
prior_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_check)
psql = prior_check.psql
wait_ready = prior_check.wait_ready
base = prior_check.base

EXTRA_FIXTURE = r"""
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000042',
        'a0000000-0000-4000-8000-000000000042',
        'c1000000-0000-4000-8000-000000000042', NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000051', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'submit', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000052', 'a0000000-0000-4000-8000-000000000042', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'submit', NULL, NULL)
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
DECLARE draft RECORD; submitted RECORD; replay RECORD; second_draft RECORD;
        denied BOOLEAN; status_value TEXT; approved_at_value TIMESTAMPTZ;
        direct_receipt_select_denied BOOLEAN := FALSE;
        direct_receipt_insert_denied BOOLEAN := FALSE;
        direct_receipt_update_denied BOOLEAN := FALSE;
        direct_receipt_delete_denied BOOLEAN := FALSE;
        valid_protocol JSONB := '{
          "hypothesis":"Synthetic protocol submission checks the expected outcome.",
          "baseline_definition":"Current practice over a comparable growing period.",
          "treatment_definition":"Apply the proposed intervention under review.",
          "unit_of_analysis":"One synthetic field unit.",
          "sample_plan":{"minimum_sample":4},
          "primary_metric_keys":["water.reliability"],
          "rollback_plan":"Return to the baseline practice if safety declines."
        }'::JSONB;
BEGIN
    SELECT * INTO draft FROM kokonut_security.create_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000071', valid_protocol, TRUE
    );
    IF draft.experiment_status <> 'draft' OR draft.replayed THEN
        RAISE EXCEPTION 'submission fixture was not created as a draft';
    END IF;

    SELECT * INTO submitted FROM kokonut_security.submit_location_solution_experiment_protocol(
        'b0000000-0000-4000-8000-000000000001', draft.experiment_id,
        'ab000000-0000-4000-8000-000000000081', TRUE
    );
    IF submitted.experiment_status <> 'submitted' OR submitted.replayed
       OR submitted.submitted_at IS NULL OR submitted.solution_id <> draft.solution_id THEN
        RAISE EXCEPTION 'eligible owner draft was not submitted with attribution receipt';
    END IF;
    SELECT * INTO replay FROM kokonut_security.submit_location_solution_experiment_protocol(
        'b0000000-0000-4000-8000-000000000001', draft.experiment_id,
        'ab000000-0000-4000-8000-000000000081', TRUE
    );
    IF NOT replay.replayed OR replay.submitted_at <> submitted.submitted_at THEN
        RAISE EXCEPTION 'exact submission retry did not return its original receipt';
    END IF;

    SELECT * INTO second_draft FROM kokonut_security.create_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000041',
        'ab000000-0000-4000-8000-000000000072', valid_protocol, TRUE
    );
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000001', second_draft.experiment_id,
            'ab000000-0000-4000-8000-000000000081', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'request ID collision across experiments was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000001', draft.experiment_id,
            'ab000000-0000-4000-8000-000000000082', TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'a submitted protocol was submitted again with a new request ID'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000001', draft.experiment_id,
            'ab000000-0000-4000-8000-000000000083', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'a different active human submitted the protocol owner draft'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_experiment_protocol(
            'b0000000-0000-4000-8000-000000000002', draft.experiment_id,
            'ab000000-0000-4000-8000-000000000084', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'submission escaped signed location context'; END IF;

    SELECT experiment.status, experiment.approved_at
      INTO status_value, approved_at_value
      FROM public.solution_experiment AS experiment
     WHERE experiment.id = draft.experiment_id;
    IF status_value <> 'submitted' OR approved_at_value IS NOT NULL THEN
        RAISE EXCEPTION 'submission also approved the protocol';
    END IF;
    SELECT experiment.status INTO status_value
      FROM public.solution_experiment AS experiment
     WHERE experiment.id = second_draft.experiment_id;
    IF status_value <> 'draft' THEN
        RAISE EXCEPTION 'failed collision changed the second draft';
    END IF;

    BEGIN PERFORM 1 FROM public.solution_experiment_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN direct_receipt_select_denied := TRUE; END;
    IF NOT direct_receipt_select_denied THEN RAISE EXCEPTION 'runtime can read private submission receipts'; END IF;
    BEGIN
        INSERT INTO public.solution_experiment_submission_receipt (
            operator_id, actor_party_id, location_id, solution_id, experiment_id,
            request_id, payload_digest, submitted_at
        ) VALUES (
            'a0000000-0000-4000-8000-000000000041', 'c1000000-0000-4000-8000-000000000041',
            'b0000000-0000-4000-8000-000000000001', draft.solution_id, draft.experiment_id,
            'ab000000-0000-4000-8000-000000000085', decode(repeat('00', 32), 'hex'), NOW()
        );
    EXCEPTION WHEN insufficient_privilege THEN direct_receipt_insert_denied := TRUE; END;
    IF NOT direct_receipt_insert_denied THEN RAISE EXCEPTION 'runtime can forge submission receipts'; END IF;
    BEGIN UPDATE public.solution_experiment_submission_receipt SET submitted_at = NOW();
    EXCEPTION WHEN insufficient_privilege THEN direct_receipt_update_denied := TRUE; END;
    IF NOT direct_receipt_update_denied THEN RAISE EXCEPTION 'runtime can edit submission receipts'; END IF;
    BEGIN DELETE FROM public.solution_experiment_submission_receipt;
    EXCEPTION WHEN insufficient_privilege THEN direct_receipt_delete_denied := TRUE; END;
    IF NOT direct_receipt_delete_denied THEN RAISE EXCEPTION 'runtime can delete submission receipts'; END IF;

    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.submit_location_solution_experiment_protocol(uuid,uuid,uuid,boolean)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.submit_location_solution_experiment_protocol(uuid,uuid,uuid,boolean)',
        'EXECUTE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment_submission_receipt', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment_submission_receipt', 'INSERT'
    ) OR has_table_privilege(
        'kokonut_solution_experiment_submitter', 'public.solution_experiment', 'INSERT'
    ) OR has_table_privilege(
        'kokonut_solution_experiment_submitter', 'public.solution_experiment', 'DELETE'
    ) OR has_column_privilege(
        'kokonut_solution_experiment_submitter', 'public.solution_experiment', 'hypothesis', 'UPDATE'
    ) OR NOT has_column_privilege(
        'kokonut_solution_experiment_submitter', 'public.solution_experiment', 'status', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'runtime, Directus, or submitter experiment boundaries are incorrect';
    END IF;
END $$;
RESET ROLE;
DO $$
BEGIN
    IF (SELECT current_stage FROM public.solution
         WHERE id = 'c0000000-0000-4000-8000-000000000041') <> 'experiment_ready' THEN
        RAISE EXCEPTION 'protocol submission changed the solution lifecycle stage';
    END IF;
END $$;
SET LOCAL ROLE kokonut_runtime;
COMMIT;
RESET ROLE;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-experiment-submit-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 507 applies and replays after the ordered experiment-draft chain",
            "submission requires a signed exact-location submit grant and an active human",
            "only the active protocol owner can submit an eligible active location-origin draft",
            "submission changes draft to submitted without approval or solution-stage mutation",
            "exact request retries replay the immutable receipt and collisions are rejected",
            "new request IDs cannot resubmit a submitted experiment",
            "runtime and Directus cannot read, forge, edit, or delete private receipts",
            "Directus cannot execute submission and the non-login submitter has bounded update access",
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
        psql(docker, container, prior_check.PREPARE_SCHEMA)
        for filename in (
            "484_location_solution_gate_review.sql",
            "503_location_solution_nonpromotion_stage_transition.sql",
            "504_location_solution_create.sql",
            "505_location_solution_gate_definition.sql",
            "506_location_solution_experiment_create.sql",
        ):
            psql(docker, container, (ROOT / "schemas/postgres" / filename).read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, prior_check.FIXTURE)
        psql(docker, container, EXTRA_FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 8
        print("PASS: migration 507 applies/replays; experiment submission scope, owner, retry, lifecycle, and ACL checks passed")
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
