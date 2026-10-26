#!/usr/bin/env python3
"""Exercise migration 498 on isolated CAP-035 replication fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_CHECK = ROOT / "scripts/check-solution-replication-completion-proposal-disposable.py"
MIGRATION = ROOT / "schemas/postgres/498_location_solution_replication_completion_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-completion-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_replication_completion_proposal_disposable", PROPOSAL_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior replication completion fixtures")
completion_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion_check)

activation_check = completion_check.activation_check
review_check = completion_check.review_check
run = completion_check.run
psql = completion_check.psql
wait_ready = completion_check.wait_ready

REVIEW_FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES ('a0000000-0000-4000-8000-000000000005', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'Synthetic completion reviewer', 'person', 'active')
ON CONFLICT (id) DO UPDATE SET party_type = EXCLUDED.party_type, status = EXCLUDED.status;
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000005',
        'a0000000-0000-4000-8000-000000000005',
        'dddddddd-dddd-4ddd-8ddd-dddddddddddd', NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000010',
     'a0000000-0000-4000-8000-000000000005',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000011',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

REVIEW_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_completion_replication',
    (SELECT replication_id::TEXT FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000001'), false
);
SELECT set_config(
    'kokonut.test_completion_report_one',
    (SELECT id::TEXT FROM public.solution_replication_completion_proposal
      WHERE request_id = 'ab970000-0000-4000-8000-000000000001'), false
);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000005', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    first_item record;
    report_detail record;
    rejected record;
    replayed record;
    new_report record;
    accepted record;
    accepted_retry record;
    report_uuid UUID;
    denied boolean := FALSE;
BEGIN
    SELECT * INTO first_item
      FROM kokonut_security.list_location_solution_replication_completion_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
      );
    IF first_item.proposal_id IS NULL
       OR first_item.is_self_authored IS DISTINCT FROM FALSE
       OR first_item.is_self_started IS DISTINCT FROM FALSE
       OR first_item.is_initial_approver IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'completion review queue returned wrong scope or independence flags';
    END IF;

    SELECT * INTO report_detail
      FROM kokonut_security.get_location_solution_replication_completion_review_detail(
        'b0000000-0000-4000-8000-000000000001',
        first_item.replication_id, first_item.proposal_id
      );
    IF report_detail.outcome <> 'successful'
       OR report_detail.evidence_maturity <> 3
       OR report_detail.outcome_summary <> 'Synthetic local replication met its measured objectives.'
       OR report_detail.source_is_current IS DISTINCT FROM TRUE
       OR report_detail.is_source_owner IS DISTINCT FROM FALSE
       OR report_detail.is_source_approver IS DISTINCT FROM FALSE
       OR report_detail.is_source_result_reviewer IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'private completion detail omitted or misreported review fields';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', TRUE);
    report_uuid := pg_catalog.current_setting('kokonut.test_completion_report_one')::UUID;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
            report_uuid, 'ab980000-0000-4000-8000-000000000002',
            'accepted', NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'completion report proposer reviewed their own report'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000005', TRUE);

    SELECT * INTO rejected
      FROM kokonut_security.review_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
        first_item.proposal_id, 'ab980000-0000-4000-8000-000000000001',
        'rejected', 'The supplied evidence does not establish a safe completion.', TRUE
      );
    IF rejected.decision <> 'rejected'
       OR rejected.replication_status <> 'active'
       OR rejected.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'completion report rejection changed replication state';
    END IF;
    SELECT * INTO replayed
      FROM kokonut_security.review_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
        first_item.proposal_id, 'ab980000-0000-4000-8000-000000000001',
        'rejected', 'The supplied evidence does not establish a safe completion.', TRUE
      );
    IF replayed.event_id IS DISTINCT FROM rejected.event_id
       OR replayed.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact completion rejection retry did not replay';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.review_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
            first_item.proposal_id, 'ab980000-0000-4000-8000-000000000001',
            'accepted', NULL, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed decision reused a completion review key'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', TRUE);
    SELECT * INTO new_report
      FROM kokonut_security.propose_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
        'ab970000-0000-4000-8000-000000000009', 'mixed', 4,
        'Synthetic second report records mixed outcomes across the target plots.',
        '[{"evidence_ref":"synthetic://replication/2"}]'::JSONB
      );
    IF new_report.decision_status <> 'proposed'
       OR new_report.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'new report after a rejection was not available for independent review';
    END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000005', TRUE);
    SELECT * INTO accepted
      FROM kokonut_security.review_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
        new_report.proposal_id, 'ab980000-0000-4000-8000-000000000003',
        'accepted', NULL, TRUE
      );
    IF accepted.decision <> 'accepted'
       OR accepted.replication_status <> 'completed'
       OR accepted.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'accepted completion report did not complete replication';
    END IF;
    SELECT * INTO accepted_retry
      FROM kokonut_security.review_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', first_item.replication_id,
        new_report.proposal_id, 'ab980000-0000-4000-8000-000000000003',
        'accepted', NULL, TRUE
      );
    IF accepted_retry.event_id IS DISTINCT FROM accepted.event_id
       OR accepted_retry.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact completion acceptance retry did not replay';
    END IF;

    denied := FALSE;
    BEGIN SELECT 1 FROM public.solution_replication_completion_proposal;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private completion reports directly'; END IF;
    denied := FALSE;
    BEGIN SELECT 1 FROM public.solution_replication_completion_review_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private completion receipts directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    replication_id UUID := pg_catalog.current_setting('kokonut.test_completion_replication')::UUID;
    replication public.solution_replication%ROWTYPE;
    accepted_report public.solution_replication_completion_proposal%ROWTYPE;
    rejected_report public.solution_replication_completion_proposal%ROWTYPE;
BEGIN
    SELECT * INTO replication FROM public.solution_replication WHERE id = replication_id;
    SELECT * INTO accepted_report FROM public.solution_replication_completion_proposal
     WHERE request_id = 'ab970000-0000-4000-8000-000000000009';
    SELECT * INTO rejected_report FROM public.solution_replication_completion_proposal
     WHERE request_id = 'ab970000-0000-4000-8000-000000000001';
    IF replication.status <> 'completed'
       OR replication.result <> 'mixed'
       OR replication.evidence_maturity <> 4
       OR replication.evidence <> '[{"evidence_ref":"synthetic://replication/2"}]'::JSONB
       OR replication.completed_at IS NULL
       OR replication.completion_reviewed_by_party_id <> 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
       OR replication.completion_reviewed_at IS NULL
       OR accepted_report.decision_status <> 'accepted'
       OR accepted_report.reviewed_by_party_id <> 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
       OR rejected_report.decision_status <> 'rejected'
       OR (SELECT current_stage FROM public.solution WHERE id = replication.solution_id) <> 'validated'
       OR (SELECT count(*) FROM public.solution_replication_completion_review_receipt) <> 2 THEN
        RAISE EXCEPTION 'completion decision attribution, report evidence, or solution stage is incorrect';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.list_location_solution_replication_completion_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.get_location_solution_replication_completion_review_detail(uuid,uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.review_location_solution_replication_completion(uuid,uuid,uuid,uuid,text,text,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.review_location_solution_replication_completion(uuid,uuid,uuid,uuid,text,text,boolean)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication_completion_review_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_replication_completion_reviewer',
          'public.solution_replication_completion_review_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_replication_completion_reviewer',
          'public.solution_replication_completion_review_receipt', 'DELETE')
       OR has_column_privilege('kokonut_solution_replication_completion_reviewer',
          'public.solution_replication', 'status', 'UPDATE') IS DISTINCT FROM TRUE
       OR has_column_privilege('kokonut_solution_replication_completion_reviewer',
          'public.solution_replication', 'result', 'UPDATE') IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'completion review function or role boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-replication-completion-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 498 applies and replays after migration 497",
            "queue, private detail, and decision require exact review scope and active human binding",
            "completion reviewer is independent from report author, starter, initial approver, and source reviewers",
            "rejection preserves active replication state and permits a replacement report",
            "acceptance atomically records outcome/evidence, completion attribution, and immutable receipt",
            "exact retries replay; changed inputs and stale lineage fail closed",
            "runtime has bounded-function access only and Directus cannot execute review functions",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        review_check.apply_predecessors(docker, container)
        migration_495 = review_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, review_check.REVIEW_FIXTURE)
        psql(docker, container, migration_495)
        psql(docker, container, migration_495)
        psql(docker, container, review_check.REVIEW_ACCEPTANCE)
        migration_496 = activation_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_496)
        psql(docker, container, migration_496)
        psql(docker, container, activation_check.ACTIVATION_FIXTURE)
        psql(docker, container, completion_check.COMPLETION_FIXTURE)
        migration_497 = completion_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_497)
        psql(docker, container, migration_497)
        psql(docker, container, completion_check.COMPLETION_ACCEPTANCE)
        psql(docker, container, REVIEW_FIXTURE)
        migration_498 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_498)
        psql(docker, container, migration_498)
        psql(docker, container, REVIEW_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 12
        print("PASS: migrations through 498 apply and replay, and twelve completion review groups passed")
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
