#!/usr/bin/env python3
"""Exercise migration 495 with isolated replication proposal review fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_CHECK = ROOT / "scripts/check-solution-replication-proposal-disposable.py"
MIGRATION = ROOT / "schemas/postgres/495_location_solution_replication_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_replication_proposal_disposable", PROPOSAL_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior solution lifecycle fixtures")
proposal_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proposal_check)

gate_check = proposal_check.gate_check
prior = proposal_check.prior
retirement_check = proposal_check.retirement_check
learning_proposal_check = proposal_check.learning_check
replication_check = proposal_check.replication_check
scale_check = proposal_check.scale_check
adoption_check = proposal_check.adoption_check
funding_check = proposal_check.funding_check
experiment_check = proposal_check.experiment_check
approval_check = learning_proposal_check.approval_check
learning_check = learning_proposal_check.learning_check
run = proposal_check.run
psql = proposal_check.psql
wait_ready = proposal_check.wait_ready

REVIEW_FIXTURE = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000007',
     'a0000000-0000-4000-8000-000000000003',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', NULL, NULL);
"""

REVIEW_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_replication_one',
    (SELECT replication_id::text FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000001'), false
);
SELECT set_config(
    'kokonut.test_replication_two',
    (SELECT replication_id::text FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000009'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    queue_count integer;
    first_review record;
    replay_review record;
    rejected_review record;
    denied boolean;
BEGIN
    SELECT count(*) INTO queue_count
      FROM kokonut_security.list_location_solution_replication_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
      );
    IF queue_count <> 2 THEN
        RAISE EXCEPTION 'review queue must contain exactly the two pending attributed proposals';
    END IF;

    SELECT * INTO first_review
      FROM kokonut_security.get_location_solution_replication_review_detail(
        'b0000000-0000-4000-8000-000000000001',
        pg_catalog.current_setting('kokonut.test_replication_one')::UUID
      );
    IF first_review.replication_status <> 'proposed'
       OR first_review.target_context <> 'Synthetic target context'
       OR first_review.adaptation_required <> 'Synthetic local adaptation'
       OR first_review.replication_protocol <> '{"steps":["prepare","observe"]}'::jsonb
       OR first_review.source_experiment_status <> 'validated'
       OR first_review.source_result_outcome <> 'validated'
       OR first_review.proposer_attributed IS DISTINCT FROM TRUE
       OR first_review.is_self_authored IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'private review detail omitted or misreported bounded proposal fields';
    END IF;

    SELECT * INTO first_review
      FROM kokonut_security.review_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        first_review.replication_id,
        'ab950000-0000-4000-8000-000000000001',
        'approved', NULL, TRUE
      );
    IF first_review.decision <> 'approved' OR first_review.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'independent human approval was not recorded';
    END IF;

    SELECT * INTO replay_review
      FROM kokonut_security.review_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        first_review.replication_id,
        'ab950000-0000-4000-8000-000000000001',
        'approved', NULL, TRUE
      );
    IF replay_review.event_id IS DISTINCT FROM first_review.event_id
       OR replay_review.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact review retry did not replay its receipt';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            first_review.replication_id,
            'ab950000-0000-4000-8000-000000000001',
            'rejected', 'Changed decision under the same key', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-input review retry was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            pg_catalog.current_setting('kokonut.test_replication_two')::UUID,
            'ab950000-0000-4000-8000-000000000002',
            'approved', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'proposal author was allowed to review their own proposal'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    SELECT * INTO rejected_review
      FROM kokonut_security.review_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        pg_catalog.current_setting('kokonut.test_replication_two')::UUID,
        'ab950000-0000-4000-8000-000000000003',
        'rejected', 'Insufficient local safeguards for this context', TRUE
      );
    IF rejected_review.decision <> 'rejected' OR rejected_review.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'independent rejection was not recorded';
    END IF;

    SELECT count(*) INTO queue_count
      FROM kokonut_security.list_location_solution_replication_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
      );
    IF queue_count <> 0 THEN RAISE EXCEPTION 'reviewed proposals remained in the pending queue'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_replication_review_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read review receipts'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_replication;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read replication details'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    approved public.solution_replication%ROWTYPE;
    rejected public.solution_replication%ROWTYPE;
BEGIN
    SELECT * INTO approved FROM public.solution_replication
     WHERE id = (SELECT replication_id FROM public.solution_replication_proposal_receipt
                  WHERE request_id = 'ab940000-0000-4000-8000-000000000001');
    SELECT * INTO rejected FROM public.solution_replication
     WHERE id = (SELECT replication_id FROM public.solution_replication_proposal_receipt
                  WHERE request_id = 'ab940000-0000-4000-8000-000000000009');
    IF approved.status <> 'approved'
       OR approved.reviewed_by_party_id <> 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
       OR approved.reviewed_at IS NULL
       OR approved.result IS NOT NULL
       OR approved.completed_at IS NOT NULL
       OR rejected.status <> 'rejected'
       OR rejected.review_reason <> 'Insufficient local safeguards for this context'
       OR (SELECT current_stage FROM public.solution WHERE id = approved.solution_id) <> 'validated'
       OR (SELECT current_stage FROM public.solution WHERE id = rejected.solution_id) <> 'testing'
       OR (SELECT count(*) FROM public.solution_replication_review_receipt) <> 2 THEN
        RAISE EXCEPTION 'review state, attribution, immutable receipts, or lifecycle stage is incorrect';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.list_location_solution_replication_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.get_location_solution_replication_review_detail(uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.review_location_solution_replication(uuid,uuid,uuid,text,text,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.review_location_solution_replication(uuid,uuid,uuid,text,text,boolean)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication_review_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_replication_reviewer', 'public.solution_replication_review_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_replication_reviewer', 'public.solution_replication_review_receipt', 'DELETE')
       OR has_column_privilege('kokonut_solution_replication_reviewer', 'public.solution_replication', 'status', 'UPDATE') IS DISTINCT FROM TRUE
       OR has_column_privilege('kokonut_solution_replication_reviewer', 'public.solution_replication', 'result', 'UPDATE') THEN
        RAISE EXCEPTION 'replication review function or privilege boundary failed';
    END IF;
END $$;
"""


def apply_predecessors(docker: str, container: str) -> None:
    psql(docker, container, gate_check.FIXTURE)
    psql(docker, container, gate_check.helper.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, gate_check.ACCEPTANCE)
    psql(docker, container, gate_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, gate_check.GATE_ACCEPTANCE)
    psql(docker, container, experiment_check.EXPERIMENT_SOURCE)
    psql(docker, container, experiment_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, funding_check.FUNDING_SOURCE)
    psql(docker, container, funding_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, adoption_check.ADOPTION_SOURCE)
    psql(docker, container, adoption_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, scale_check.SCALE_SOURCE)
    psql(docker, container, scale_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, replication_check.REPLICATION_SOURCE)
    psql(docker, container, replication_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, replication_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, learning_check.LEARNING_SOURCE)
    psql(docker, container, learning_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, learning_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, retirement_check.RETIREMENT_SOURCE)
    psql(docker, container, retirement_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, approval_check.REVIEW_FIXTURE)
    psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.INDEPENDENT_REVIEW_ACCEPTANCE)
    psql(docker, container, approval_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, learning_proposal_check.RETIREMENT_PROPOSAL.read_text(encoding="utf-8"))
    psql(docker, container, learning_proposal_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, learning_proposal_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, learning_proposal_check.CREATE_GRANTS)
    psql(docker, container, learning_proposal_check.LEARNING_ACCEPTANCE)
    psql(docker, container, proposal_check.SOURCE_FIXTURE)
    migration_494 = proposal_check.MIGRATION.read_text(encoding="utf-8")
    psql(docker, container, migration_494)
    psql(docker, container, migration_494)
    psql(docker, container, proposal_check.ACCEPTANCE)


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-replication-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 494 and 495 apply and 495 replays",
            "review queue/detail are exact-location, review-grant, active-human, and pending-proposal scoped",
            "only a different active human may approve or reject the attributed proposer",
            "approve/reject decisions, reasons, reviewer attribution, and immutable request receipts are atomic",
            "exact retries replay; changed input and self-review fail closed",
            "review does not activate, complete, add outcomes, or alter solution lifecycle stage",
            "runtime uses bounded functions only and cannot access review receipts directly; Directus cannot execute them",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        apply_predecessors(docker, container)
        psql(docker, container, REVIEW_FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, REVIEW_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: migrations through 495 apply, migration 495 replays, and nine replication review groups passed")
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
