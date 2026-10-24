#!/usr/bin/env python3
"""Exercise migration 509's signed exact-location experiment-start contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-experiment-protocol-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/509_location_solution_experiment_start.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-experiment-start-disposable.json"
spec = importlib.util.spec_from_file_location("solution_experiment_protocol_review_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
previous_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous_check)
psql = previous_check.psql
wait_ready = previous_check.wait_ready
base = previous_check.base

START_FIXTURE = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000071', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'transition', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000072', 'a0000000-0000-4000-8000-000000000042', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'transition', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

# This compact disposable predecessor omits the legacy observation relation.
# Keep a minimal side-effect sentinel so acceptance proves that starting the
# experiment does not create observations.
SIDE_EFFECT_SENTINELS = r"""
CREATE TABLE IF NOT EXISTS public.solution_experiment_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES public.solution_experiment(id)
);
CREATE TABLE IF NOT EXISTS public.stakeholder_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL
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
DECLARE approved_experiment_id UUID; pending_experiment_id UUID;
        started RECORD; replay RECORD; denied BOOLEAN;
        receipt_select_denied BOOLEAN := FALSE; receipt_insert_denied BOOLEAN := FALSE;
        receipt_update_denied BOOLEAN := FALSE; receipt_delete_denied BOOLEAN := FALSE;
        direct_lifecycle_update_denied BOOLEAN := FALSE;
BEGIN
    SELECT experiment.id INTO approved_experiment_id
      FROM public.solution_experiment AS experiment
     WHERE experiment.hypothesis = 'Synthetic soil condition improves under the reviewed treatment.'
       AND experiment.status = 'protocol_approved';
    SELECT experiment.id INTO pending_experiment_id
      FROM public.solution_experiment AS experiment
     WHERE experiment.hypothesis = 'Second synthetic protocol remains awaiting review.'
       AND experiment.status = 'submitted';
    IF approved_experiment_id IS NULL OR pending_experiment_id IS NULL THEN
        RAISE EXCEPTION 'protocol review predecessor did not leave expected approved and submitted fixtures';
    END IF;

    SELECT * INTO started FROM kokonut_security.start_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001', approved_experiment_id,
        'ab000000-0000-4000-8000-000000000111', TRUE
    );
    IF started.experiment_status <> 'active' OR started.replayed OR started.started_at IS NULL THEN
        RAISE EXCEPTION 'approved experiment did not start with attributable receipt';
    END IF;
    SELECT * INTO replay FROM kokonut_security.start_location_solution_experiment(
        'b0000000-0000-4000-8000-000000000001', approved_experiment_id,
        'ab000000-0000-4000-8000-000000000111', TRUE
    );
    IF NOT replay.replayed OR replay.started_at <> started.started_at THEN
        RAISE EXCEPTION 'exact start retry did not replay its immutable receipt';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.start_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001', pending_experiment_id,
            'ab000000-0000-4000-8000-000000000111', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'start request ID collision across experiments was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.start_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001', pending_experiment_id,
            'ab000000-0000-4000-8000-000000000112', TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'protocol without independent approval started'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.start_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000002', approved_experiment_id,
            'ab000000-0000-4000-8000-000000000113', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'experiment start escaped signed location context'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000043', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.start_location_solution_experiment(
            'b0000000-0000-4000-8000-000000000001', pending_experiment_id,
            'ab000000-0000-4000-8000-000000000114', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without transition grant started an experiment'; END IF;

    BEGIN PERFORM 1 FROM public.solution_experiment_start_receipt;
    EXCEPTION WHEN insufficient_privilege THEN receipt_select_denied := TRUE; END;
    IF NOT receipt_select_denied THEN RAISE EXCEPTION 'runtime can read private start receipts'; END IF;
    BEGIN
        INSERT INTO public.solution_experiment_start_receipt (
            operator_id, actor_party_id, location_id, solution_id, experiment_id,
            request_id, payload_digest, started_at
        ) VALUES (
            'a0000000-0000-4000-8000-000000000041', 'c1000000-0000-4000-8000-000000000041',
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000041', pending_experiment_id,
            'ab000000-0000-4000-8000-000000000115', decode(repeat('00', 32), 'hex'), NOW()
        );
    EXCEPTION WHEN insufficient_privilege THEN receipt_insert_denied := TRUE; END;
    IF NOT receipt_insert_denied THEN RAISE EXCEPTION 'runtime can forge start receipts'; END IF;
    BEGIN UPDATE public.solution_experiment_start_receipt SET started_at = NOW();
    EXCEPTION WHEN insufficient_privilege THEN receipt_update_denied := TRUE; END;
    IF NOT receipt_update_denied THEN RAISE EXCEPTION 'runtime can edit start receipts'; END IF;
    BEGIN DELETE FROM public.solution_experiment_start_receipt;
    EXCEPTION WHEN insufficient_privilege THEN receipt_delete_denied := TRUE; END;
    IF NOT receipt_delete_denied THEN RAISE EXCEPTION 'runtime can delete start receipts'; END IF;

    BEGIN
        UPDATE public.solution_experiment
           SET status = 'completed'
         WHERE id = approved_experiment_id;
    EXCEPTION WHEN insufficient_privilege THEN
        direct_lifecycle_update_denied := TRUE;
    END;
    IF NOT direct_lifecycle_update_denied THEN
        RAISE EXCEPTION 'runtime can bypass the bounded experiment lifecycle functions';
    END IF;

    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.start_location_solution_experiment(uuid,uuid,uuid,boolean)', 'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.start_location_solution_experiment(uuid,uuid,uuid,boolean)', 'EXECUTE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment_start_receipt', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_solution_experiment_starter', 'public.solution_experiment_start_receipt', 'UPDATE'
    ) OR has_table_privilege(
        'kokonut_solution_experiment_starter', 'public.solution_experiment_start_receipt', 'DELETE'
    ) OR has_table_privilege(
        'kokonut_runtime', 'public.solution_experiment', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_experiment', 'status', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_experiment', 'approved_at', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_experiment', 'started_at', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.solution_experiment', 'completed_at', 'UPDATE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_experiment', 'status', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'runtime, Directus, or starter lifecycle role boundaries are incorrect';
    END IF;
END $$;
RESET ROLE;
DO $$
DECLARE stage_value TEXT; status_value TEXT; started_at_value TIMESTAMPTZ;
        observation_count BIGINT; consent_count BIGINT; receipt_count BIGINT;
BEGIN
    SELECT experiment.status, experiment.started_at INTO status_value, started_at_value
      FROM public.solution_experiment AS experiment
     WHERE experiment.hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';
    SELECT solution.current_stage INTO stage_value FROM public.solution AS solution
     WHERE solution.id = 'c0000000-0000-4000-8000-000000000041';
    SELECT count(*) INTO observation_count FROM public.solution_experiment_observation AS observation
     JOIN public.solution_experiment AS experiment ON experiment.id = observation.experiment_id
     WHERE experiment.hypothesis = 'Synthetic soil condition improves under the reviewed treatment.';
    SELECT count(*) INTO consent_count FROM public.stakeholder_consent AS consent
     WHERE consent.party_id = 'c1000000-0000-4000-8000-000000000041';
    SELECT count(*) INTO receipt_count FROM public.solution_experiment_start_receipt AS receipt
     WHERE receipt.experiment_id = (
         SELECT experiment.id FROM public.solution_experiment AS experiment
          WHERE experiment.hypothesis = 'Synthetic soil condition improves under the reviewed treatment.'
     );
    IF status_value <> 'active' OR started_at_value IS NULL
       OR stage_value <> 'experiment_ready' OR observation_count <> 0
       OR consent_count <> 0 OR receipt_count <> 1 THEN
        RAISE EXCEPTION 'start changed solution stage, asserted consent, collected observations, or lost receipt';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-experiment-start-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 509 applies and replays after the ordered experiment protocol approval chain",
            "start requires signed exact-location transition scope and an active human identity",
            "only an independently approved active-origin experiment at an eligible stage can start",
            "exact retries replay one immutable receipt and request collisions are rejected",
            "start does not collect observations, assert consent, or change solution stage",
            "runtime and Directus cannot read, forge, edit, or delete private start receipts",
            "Directus cannot execute the start function and runtime cannot bypass bounded lifecycle functions with direct updates",
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
        psql(docker, container, previous_check.prior_check.prior_check.PREPARE_SCHEMA)
        for filename in (
            "484_location_solution_gate_review.sql",
            "503_location_solution_nonpromotion_stage_transition.sql",
            "504_location_solution_create.sql",
            "505_location_solution_gate_definition.sql",
            "506_location_solution_experiment_create.sql",
            "507_location_solution_experiment_submission.sql",
            "508_location_solution_experiment_protocol_review.sql",
        ):
            psql(docker, container, (ROOT / "schemas/postgres" / filename).read_text(encoding="utf-8"))
        migration_text = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_text)
        psql(docker, container, migration_text)
        psql(docker, container, previous_check.prior_check.prior_check.FIXTURE)
        psql(docker, container, previous_check.prior_check.EXTRA_FIXTURE)
        psql(docker, container, previous_check.REVIEW_FIXTURE)
        psql(docker, container, previous_check.ACCEPTANCE)
        psql(docker, container, SIDE_EFFECT_SENTINELS)
        psql(docker, container, START_FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 7
        print("PASS: migration 509 applies/replays; approved experiment start, retries, consent separation, lifecycle, and ACL checks passed")
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
