#!/usr/bin/env python3
"""Exercise migration 501 scale-gate assessment and independent review."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-learning-application-disposable.py"
MIGRATION = ROOT / "schemas/postgres/501_location_solution_scale_gate_evaluation_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-scale-gate-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_learning_application_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior CAP-035 disposable fixtures")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

review_check = prior.review_check
activation_check = prior.activation_check
replication_check = prior.replication_check
completion_check = prior.completion_check
learning_check = prior.learning_check
run = prior.run
psql = prior.psql
wait_ready = prior.wait_ready

SCALE_GATE_FIXTURE = r"""
INSERT INTO public.solution_scale_gate (
    id, solution_id, scope_type, scope_id, gate_type, requirement,
    threshold, metric_key, comparison_operator, threshold_numeric,
    unit, minimum_sample, status
) VALUES
    ('ab510000-0000-4000-8000-000000000001',
     'c0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'safety',
     'Synthetic typed threshold', 'At least five units', 'test_metric',
     'gte', 5, 'units', 2, 'pending'),
    ('ab510000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'equity',
     'Synthetic human-reviewed threshold', 'Review the cited evidence',
     NULL, NULL, NULL, NULL, NULL, 'pending');
"""

SCALE_GATE_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_solution_stage_before',
    (SELECT current_stage::TEXT FROM public.solution
      WHERE id = 'c0000000-0000-4000-8000-000000000001'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE target record; submitted record; replay record; detail record; item record;
        result record; second record; denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO target FROM kokonut_security.list_location_solution_scale_gate_assessment_targets(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) WHERE scale_gate_id = 'ab510000-0000-4000-8000-000000000001';
    IF target.requirement <> 'Synthetic typed threshold'
       OR target.comparison_operator <> 'gte' OR target.threshold_numeric <> 5
       OR target.minimum_sample <> 2 THEN
        RAISE EXCEPTION 'creator assessment target omitted the typed contract';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_scale_gate_assessment(
            'b0000000-0000-4000-8000-000000000001',
            'ab510000-0000-4000-8000-000000000001',
            'ab520000-0000-4000-8000-000000000001', '5.1', 1, NULL,
            '[{"source":"synthetic://scale/low-sample"}]'::JSONB
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'typed assessment below minimum sample was accepted'; END IF;

    SELECT * INTO submitted FROM kokonut_security.submit_location_solution_scale_gate_assessment(
        'b0000000-0000-4000-8000-000000000001',
        'ab510000-0000-4000-8000-000000000001',
        'ab520000-0000-4000-8000-000000000002', '5.1', 2, NULL,
        '[{"source":"synthetic://scale/typed"}]'::JSONB
    );
    IF submitted.assessment_status <> 'pending' OR submitted.passed IS DISTINCT FROM TRUE
       OR submitted.replayed THEN
        RAISE EXCEPTION 'typed comparator did not derive a pending passing assessment';
    END IF;
    SELECT * INTO replay FROM kokonut_security.submit_location_solution_scale_gate_assessment(
        'b0000000-0000-4000-8000-000000000001',
        'ab510000-0000-4000-8000-000000000001',
        'ab520000-0000-4000-8000-000000000002', '5.1', 2, NULL,
        '[{"source":"synthetic://scale/typed"}]'::JSONB
    );
    IF NOT replay.replayed OR replay.assessment_id <> submitted.assessment_id THEN
        RAISE EXCEPTION 'exact assessment retry did not replay';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_solution_scale_gate_assessment(
            'b0000000-0000-4000-8000-000000000001',
            'ab510000-0000-4000-8000-000000000001',
            'ab520000-0000-4000-8000-000000000002', '5.2', 2, NULL,
            '[{"source":"synthetic://scale/typed"}]'::JSONB
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed assessment reused an idempotency key'; END IF;

    SELECT * INTO item FROM kokonut_security.list_location_solution_scale_gate_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) WHERE assessment_id = submitted.assessment_id;
    IF item.evaluator_conflict IS DISTINCT FROM TRUE OR item.passed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'review queue omitted evaluator conflict or derived result';
    END IF;
    SELECT * INTO detail FROM kokonut_security.get_location_solution_scale_gate_review_detail(
        'b0000000-0000-4000-8000-000000000001', submitted.assessment_id
    );
    IF detail.measured_numeric <> 5.1
       OR detail.evidence_refs <> '[{"source":"synthetic://scale/typed"}]'::JSONB
       OR detail.evaluator_conflict IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'private assessment review detail did not match the submission';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_scale_gate_assessment(
            'b0000000-0000-4000-8000-000000000001', submitted.assessment_id,
            'ab530000-0000-4000-8000-000000000001', 'accepted', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'evaluator reviewed their own scale-gate assessment'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000006', TRUE);
    SELECT * INTO item FROM kokonut_security.list_location_solution_scale_gate_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) WHERE assessment_id = submitted.assessment_id;
    IF item.evaluator_conflict IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'independent reviewer was marked as conflicted';
    END IF;
    SELECT * INTO result FROM kokonut_security.review_location_solution_scale_gate_assessment(
        'b0000000-0000-4000-8000-000000000001', submitted.assessment_id,
        'ab530000-0000-4000-8000-000000000002', 'accepted', 'Independent evidence review'
    );
    IF result.assessment_status <> 'approved' OR result.gate_status <> 'passed'
       OR result.replayed THEN
        RAISE EXCEPTION 'independent reviewer did not accept the typed assessment';
    END IF;
    SELECT * INTO replay FROM kokonut_security.review_location_solution_scale_gate_assessment(
        'b0000000-0000-4000-8000-000000000001', submitted.assessment_id,
        'ab530000-0000-4000-8000-000000000002', 'accepted', 'Independent evidence review'
    );
    IF NOT replay.replayed OR replay.assessment_id <> submitted.assessment_id THEN
        RAISE EXCEPTION 'exact review retry did not replay';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', TRUE);
    SELECT * INTO second FROM kokonut_security.submit_location_solution_scale_gate_assessment(
        'b0000000-0000-4000-8000-000000000001',
        'ab510000-0000-4000-8000-000000000002',
        'ab520000-0000-4000-8000-000000000003', 'observed concern', 1, FALSE,
        '[{"source":"synthetic://scale/untyped"}]'::JSONB
    );
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000006', TRUE);
    SELECT * INTO result FROM kokonut_security.review_location_solution_scale_gate_assessment(
        'b0000000-0000-4000-8000-000000000001', second.assessment_id,
        'ab530000-0000-4000-8000-000000000003', 'rejected',
        'Evidence does not support this proposed result'
    );
    IF result.assessment_status <> 'rejected' OR result.gate_status <> 'pending'
    THEN
        RAISE EXCEPTION 'rejected evaluation changed the current scale gate';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', TRUE);
    denied := FALSE;
    BEGIN SELECT * FROM public.solution_scale_gate; EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read scale-gate rows directly'; END IF;
    denied := FALSE;
    BEGIN SELECT * FROM public.solution_scale_gate_assessment; EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read assessment history directly'; END IF;
    denied := FALSE;
    BEGIN UPDATE public.solution_scale_gate SET status = 'passed'; EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly mutate scale gates'; END IF;
    denied := FALSE;
    BEGIN SELECT * FROM kokonut_security.list_location_solution_scale_gate_review_queue(
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 10, 0
    ); EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'review queue accepted a mismatched location context'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE stage_after TEXT;
BEGIN
    SELECT current_stage INTO stage_after FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000001';
    IF stage_after IS DISTINCT FROM current_setting('kokonut.test_solution_stage_before') THEN
        RAISE EXCEPTION 'scale-gate review advanced the solution stage';
    END IF;
    IF (SELECT status FROM public.solution_scale_gate
         WHERE id = 'ab510000-0000-4000-8000-000000000001') <> 'passed'
       OR (SELECT approved_by_party_id FROM public.solution_scale_gate
            WHERE id = 'ab510000-0000-4000-8000-000000000001')
          <> 'fffffff0-ffff-4fff-8fff-fffffffffff0'
       OR (SELECT status FROM public.solution_scale_gate
            WHERE id = 'ab510000-0000-4000-8000-000000000002') <> 'pending'
       OR (SELECT status FROM public.solution_scale_gate_assessment
            WHERE id = 'ab520000-0000-4000-8000-000000000003') <> 'rejected' THEN
        RAISE EXCEPTION 'review decision did not preserve the expected gate and assessment states';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.solution_scale_gate', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_scale_gate', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_scale_gate_assessment', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_scale_gate_assessment', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.submit_location_solution_scale_gate_assessment(uuid,uuid,uuid,text,integer,boolean,jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.review_location_solution_scale_gate_assessment(uuid,uuid,uuid,text,text)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.submit_location_solution_scale_gate_assessment(uuid,uuid,uuid,text,integer,boolean,jsonb)', 'EXECUTE') THEN
        RAISE EXCEPTION 'scale-gate role boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-scale-gate-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 501 applies and replays after the ordered CAP-035 lifecycle migrations",
            "assessment targets and submissions require signed exact-location create scope",
            "typed threshold outcomes and minimum sample sizes are enforced in PostgreSQL",
            "pending assessments are private, append-only, evidence-backed, and idempotent",
            "review queue and detail require exact location review scope and active human identity",
            "evaluator self-review is rejected; independent review is idempotent",
            "rejection preserves current gate state; acceptance updates only the gate result",
            "assessment acceptance does not change solution stage",
            "runtime cannot directly read/write scale gates or assessment history; Directus is denied",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        review_check.apply_predecessors(docker, container)
        # The compact lifecycle fixture starts near migration 459, so replay the
        # original typed scale-gate column migration before testing migration 501.
        psql(docker, container, (ROOT / "schemas/postgres/293_sequential_gate_integrity.sql").read_text(encoding="utf-8"))
        psql(docker, container, review_check.REVIEW_FIXTURE)
        psql(docker, container, review_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, review_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, review_check.REVIEW_ACCEPTANCE)
        psql(docker, container, activation_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, activation_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, activation_check.ACTIVATION_FIXTURE)
        psql(docker, container, replication_check.COMPLETION_FIXTURE)
        psql(docker, container, replication_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, replication_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, replication_check.COMPLETION_ACCEPTANCE)
        psql(docker, container, completion_check.REVIEW_FIXTURE)
        psql(docker, container, completion_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, completion_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, completion_check.REVIEW_ACCEPTANCE)
        psql(docker, container, learning_check.REVIEWER_FIXTURE)
        psql(docker, container, learning_check.PROPOSE_ACCEPTANCE)
        psql(docker, container, learning_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.REVIEW_ACCEPTANCE)
        psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, SCALE_GATE_FIXTURE)
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, SCALE_GATE_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: migrations through 501 apply and replay; nine scale-gate acceptance groups passed")
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
