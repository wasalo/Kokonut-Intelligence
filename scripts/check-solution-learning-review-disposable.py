#!/usr/bin/env python3
"""Exercise migration 499 with isolated CAP-035 learning fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPLETION_CHECK = ROOT / "scripts/check-solution-replication-completion-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/499_location_solution_learning_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-learning-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_replication_completion_review_disposable", COMPLETION_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior CAP-035 replication fixtures")
completion_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion_check)

review_check = completion_check.review_check
activation_check = completion_check.activation_check
replication_check = completion_check.completion_check
run = completion_check.run
psql = completion_check.psql
wait_ready = completion_check.wait_ready

REVIEWER_FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES ('a0000000-0000-4000-8000-000000000006', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('fffffff0-ffff-4fff-8fff-fffffffffff0', 'Synthetic learning reviewer', 'person', 'active')
ON CONFLICT (id) DO UPDATE SET party_type = EXCLUDED.party_type, status = EXCLUDED.status;
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000006',
        'a0000000-0000-4000-8000-000000000006',
        'fffffff0-ffff-4fff-8fff-fffffffffff0', NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES ('a6000000-0000-4000-8000-000000000012',
        'a0000000-0000-4000-8000-000000000006',
        'b0000000-0000-4000-8000-000000000001',
        'solution_lifecycle', 'review', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES ('a6000000-0000-4000-8000-000000000013',
        'a0000000-0000-4000-8000-000000000001',
        'b0000000-0000-4000-8000-000000000001',
        'solution_lifecycle', 'create', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

PROPOSE_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_learning_replication',
    (SELECT replication_id::TEXT FROM public.solution_replication_completion_proposal
      WHERE request_id = 'ab970000-0000-4000-8000-000000000009'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE proposal record;
BEGIN
    SELECT * INTO proposal FROM kokonut_security.propose_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001',
        pg_catalog.current_setting('kokonut.test_learning_replication')::UUID,
        'ab990000-0000-4000-8000-000000000001',
        'context_transfer',
        'A locally tailored training schedule improved participation.',
        'high', 'medium', '[{"assumption":"seasonal availability"}]'::JSONB,
        '[{"metric":"attendance_rate"}]'::JSONB,
        'Adapt the training calendar to local planting cycles.',
        '[{"evidence_ref":"synthetic://learning/1"}]'::JSONB
    );
    IF proposal.learning_status <> 'proposed' OR proposal.replayed THEN
        RAISE EXCEPTION 'learning proposal was not created as proposed';
    END IF;
END $$;
COMMIT;
RESET ROLE;
"""

REVIEW_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_learning_id',
    (SELECT learning_record_id::TEXT FROM public.solution_learning_proposal_event
      WHERE request_id = 'ab990000-0000-4000-8000-000000000001'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE item record; detail record; denied boolean := FALSE;
BEGIN
    SELECT * INTO item FROM kokonut_security.list_location_solution_learning_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    );
    IF item.learning_record_id IS DISTINCT FROM
         pg_catalog.current_setting('kokonut.test_learning_id')::UUID
       OR item.is_self_authored IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'proposer queue row did not retain self-authorship flag';
    END IF;
    SELECT * INTO detail FROM kokonut_security.get_location_solution_learning_review_detail(
        'b0000000-0000-4000-8000-000000000001', item.learning_record_id
    );
    IF detail.finding <> 'A locally tailored training schedule improved participation.'
       OR detail.evidence <> '[{"evidence_ref":"synthetic://learning/1"}]'::JSONB
       OR detail.source_is_current IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'private lesson review detail was incomplete or stale';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
            'ab9a0000-0000-4000-8000-000000000001', 'accepted', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'learning proposer reviewed their own proposal'; END IF;

    denied := FALSE;
    BEGIN
        UPDATE public.solution_learning_record SET decision_status = 'accepted',
            reviewed_by_party_id = 'fffffff0-ffff-4fff-8fff-fffffffffff0',
            reviewed_at = pg_catalog.clock_timestamp()
         WHERE id = item.learning_record_id;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime accepted a proposed lesson without the reviewer function'; END IF;

    denied := FALSE;
    BEGIN
        UPDATE public.solution_learning_record SET decision_status = 'applied',
            applied_to_version = 'bypass', owner_party_id = 'fffffff0-ffff-4fff-8fff-fffffffffff0'
         WHERE id = item.learning_record_id;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime applied a proposed learning record'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000005', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
            'ab9a0000-0000-4000-8000-000000000002', 'accepted', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'completion reviewer reviewed the learning record'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000006', TRUE);
    SELECT * INTO item FROM kokonut_security.list_location_solution_learning_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    );
    IF item.learning_record_id IS NULL
       OR item.is_self_authored OR item.is_self_starter OR item.is_initial_approver
       OR item.is_completion_reviewer OR item.is_source_owner OR item.is_source_approver
       OR item.is_source_result_reviewer THEN
        RAISE EXCEPTION 'independent reviewer was incorrectly conflicted';
    END IF;

    SELECT * INTO detail FROM kokonut_security.review_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
        'ab9a0000-0000-4000-8000-000000000003', 'accepted',
        'Reviewed the source evidence and transfer limits.', TRUE
    );
    IF detail.decision <> 'accepted' OR detail.replayed THEN
        RAISE EXCEPTION 'independent learning acceptance did not persist';
    END IF;
    SELECT * INTO detail FROM kokonut_security.review_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
        'ab9a0000-0000-4000-8000-000000000003', 'accepted',
        'Reviewed the source evidence and transfer limits.', TRUE
    );
    IF NOT detail.replayed THEN RAISE EXCEPTION 'exact learning retry did not replay'; END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
            'ab9a0000-0000-4000-8000-000000000003', 'rejected',
            'Reviewed the source evidence and transfer limits.', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed decision reused a learning review request id'; END IF;

    UPDATE public.solution_learning_record SET decision_status = 'applied',
        applied_to_version = 'reviewed-v2', owner_party_id = 'fffffff0-ffff-4fff-8fff-fffffffffff0'
     WHERE id = item.learning_record_id;
    IF (SELECT decision_status FROM public.solution_learning_record
         WHERE id = item.learning_record_id) <> 'applied' THEN
        RAISE EXCEPTION 'reviewed accepted learning could not be applied through the legacy service boundary';
    END IF;
    denied := FALSE;
    BEGIN SELECT 1 FROM public.solution_learning_review_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private learning review receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    reviewed_learning_id UUID := pg_catalog.current_setting('kokonut.test_learning_id')::UUID;
    reviewed_solution_id UUID;
BEGIN
    SELECT solution_id INTO reviewed_solution_id FROM public.solution_learning_record
     WHERE id = reviewed_learning_id;
    IF (SELECT decision_status FROM public.solution_learning_record
         WHERE id = reviewed_learning_id) <> 'applied'
       OR (SELECT current_stage FROM public.solution WHERE id = reviewed_solution_id) <> 'validated' THEN
        RAISE EXCEPTION 'reviewed accepted learning application changed decision or solution stage incorrectly';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.list_location_solution_learning_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.get_location_solution_learning_review_detail(uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.review_location_solution_learning(uuid,uuid,uuid,text,text,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.review_location_solution_learning(uuid,uuid,uuid,text,text,boolean)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_learning_review_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_learning_reviewer',
          'public.solution_learning_review_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_learning_reviewer',
          'public.solution_learning_review_receipt', 'DELETE')
       OR has_column_privilege('kokonut_runtime', 'public.solution_learning_record', 'decision_status', 'UPDATE') IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'learning review function or role boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-learning-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 499 applies and replays after migration 498",
            "queue and detail require exact signed location review scope and an active human identity",
            "learning proposals require current completed replication and accepted completion receipt lineage",
            "reviewer must differ from proposal author, starter, initial approver, completion reviewer, and source experiment decision makers",
            "accepted/rejected decisions are atomic, attributed, append-only, and idempotently replayable",
            "direct proposed-to-accepted/applied transitions are denied; accepted-only legacy apply preserves solution stage",
            "runtime uses bounded functions and Directus cannot execute review functions or read review receipts",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        review_check.apply_predecessors(docker, container)
        psql(docker, container, review_check.REVIEW_FIXTURE)
        migration_495 = review_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_495)
        psql(docker, container, migration_495)
        psql(docker, container, review_check.REVIEW_ACCEPTANCE)
        migration_496 = activation_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_496)
        psql(docker, container, migration_496)
        psql(docker, container, activation_check.ACTIVATION_FIXTURE)
        psql(docker, container, replication_check.COMPLETION_FIXTURE)
        migration_497 = replication_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_497)
        psql(docker, container, migration_497)
        psql(docker, container, replication_check.COMPLETION_ACCEPTANCE)
        psql(docker, container, completion_check.REVIEW_FIXTURE)
        migration_498 = completion_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_498)
        psql(docker, container, migration_498)
        psql(docker, container, completion_check.REVIEW_ACCEPTANCE)
        psql(docker, container, REVIEWER_FIXTURE)
        psql(docker, container, PROPOSE_ACCEPTANCE)
        migration_499 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_499)
        psql(docker, container, migration_499)
        psql(docker, container, REVIEW_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 11
        print("PASS: migrations through 499 apply and replay, and eleven learning review groups passed")
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
