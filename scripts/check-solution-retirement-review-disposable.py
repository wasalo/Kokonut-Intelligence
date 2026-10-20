#!/usr/bin/env python3
"""Exercise migration 482 retirement review reads and replacement scope guard."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_CHECK = ROOT / "scripts/check-solution-retirement-approval-disposable.py"
MIGRATION = ROOT / "schemas/postgres/482_location_solution_retirement_review_queue.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-retirement-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_retirement_approval_disposable", APPROVAL_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable retirement approval fixtures")
approval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval)

run = approval.run
psql = approval.psql
wait_ready = approval.wait_ready

REVIEW_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    item record;
    detail record;
    seen integer := 0;
    denied boolean := false;
    result_signature text;
BEGIN
    FOR item IN SELECT * FROM kokonut_security.list_location_solution_retirement_review_queue(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF item.retirement_id NOT IN (
            'fa000000-0000-4000-8000-000000000012',
            'fa000000-0000-4000-8000-000000000013',
            'fa000000-0000-4000-8000-000000000014',
            'fa000000-0000-4000-8000-000000000015'
        ) THEN
            RAISE EXCEPTION 'review queue included unexpected retirement % for solution %',
                item.retirement_id, item.solution_id;
        END IF;
        IF item.solution_id <> 'c0000000-0000-4000-8000-000000000001'
           OR item.retirement_status NOT IN ('proposed', 'impact_review')
           OR NOT item.proposer_attributed THEN
            RAISE EXCEPTION 'review queue row % does not match the fixed location proposal contract (solution %, status %, attributed %)',
                item.retirement_id, item.solution_id, item.retirement_status,
                item.proposer_attributed;
        END IF;
        IF item.retirement_id = 'fa000000-0000-4000-8000-000000000012'
           AND NOT item.is_self_authored THEN
            RAISE EXCEPTION 'self-authored proposal was not identified';
        END IF;
    END LOOP;
    IF seen <> 4 THEN RAISE EXCEPTION 'expected four pending exact-origin proposals, got %', seen; END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_retirement_review_queue(
        'b0000000-0000-4000-8000-000000000001', 2, 0
    );
    IF seen <> 2 THEN RAISE EXCEPTION 'review queue page bound was not enforced'; END IF;

    SELECT * INTO detail FROM kokonut_security.get_location_solution_retirement_review_detail(
        'b0000000-0000-4000-8000-000000000001',
        'fa000000-0000-4000-8000-000000000012'
    );
    IF detail.trigger_reason <> 'private reason'
       OR detail.migration_plan <> 'private migration plan'
       OR detail.solution_name <> 'Synthetic solution'
       OR detail.retirement_status <> 'proposed'
       OR NOT detail.is_self_authored
       OR NOT detail.proposer_attributed
       OR jsonb_array_length(detail.evidence_refs) <> 1 THEN
        RAISE EXCEPTION 'review detail omitted or corrupted the scoped proposal evidence';
    END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_retirement_review_queue(uuid,integer,integer)'::regprocedure
    ) || pg_catalog.pg_get_function_result(
        'kokonut_security.get_location_solution_retirement_review_detail(uuid,uuid)'::regprocedure
    ) INTO result_signature;
    IF result_signature ~* '(created_by_party_id|reviewer_party_id|operator_id|proposer_party_id)' THEN
        RAISE EXCEPTION 'review projection signature exposes party or operator identity';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_review_queue(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed review location was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_review_queue(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact review grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_review_queue(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'review queue allowed an operator without active human binding'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.get_location_solution_retirement_review_detail(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000011'
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'approved retirement was returned in pending detail'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.get_location_solution_retirement_review_detail(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000016'
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location retirement detail was returned'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_review_queue(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded review queue page was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.solution_retirement;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private retirement details'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_retirement_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.get_location_solution_retirement_review_detail(uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_retirement_review_queue(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.get_location_solution_retirement_review_detail(uuid,uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_solution_reviewer', 'public.solution_retirement', 'UPDATE')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'trigger_reason', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'evidence_refs', 'SELECT') THEN
        RAISE EXCEPTION 'review function, reader/reviewer separation, or runtime/Directus boundary failed';
    END IF;
END $$;

DO $$
DECLARE denied boolean := false; resulting_status text;
BEGIN
    BEGIN
        UPDATE public.solution_retirement
           SET replacement_solution_id = 'c0000000-0000-4000-8000-000000000003',
               status = 'approved',
               approved_by_party_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
               approved_at = clock_timestamp()
         WHERE id = 'fa000000-0000-4000-8000-000000000015';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location superseded replacement was approved'; END IF;
    SELECT status INTO resulting_status FROM public.solution_retirement
     WHERE id = 'fa000000-0000-4000-8000-000000000015';
    IF resulting_status <> 'proposed' THEN RAISE EXCEPTION 'rejected replacement update was not atomic'; END IF;

    UPDATE public.solution_retirement
       SET replacement_solution_id = 'c0000000-0000-4000-8000-000000000005',
           status = 'approved',
           approved_by_party_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
           approved_at = clock_timestamp()
     WHERE id = 'fa000000-0000-4000-8000-000000000015';
    SELECT status INTO resulting_status FROM public.solution_retirement
     WHERE id = 'fa000000-0000-4000-8000-000000000015';
    IF resulting_status <> 'approved' THEN RAISE EXCEPTION 'same-location replacement approval was blocked'; END IF;
END $$;
"""

REVIEW_FIXTURE_CLEANUP = r"""
-- Earlier predecessor checks create synthetic retirement rows that are not
-- part of the review-queue fixture; remove only those exact disposable IDs.
DELETE FROM public.solution_retirement
 WHERE id IN (
    'fa000000-0000-4000-8000-000000000001',
    'fa000000-0000-4000-8000-000000000003',
    'f9000000-0000-4000-8000-000000000001'
 );
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-retirement-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "review queue and detail require exact signed review scope and active human attribution",
            "only pending exact-origin proposals appear; reviewer identity remains private and self-authorship is a boolean",
            "review detail is available only through the separate reviewer function owner; runtime table access and Directus execution are denied",
            "approved, cross-location, mismatched, ungranted, unbound, and unbounded reads fail closed",
            "location-origin superseded retirement approval rejects a cross-location replacement atomically and accepts a same-location replacement",
            "migration 482 applies and replays after the required solution lifecycle predecessors",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        gate = approval.gate_check
        psql(docker, container, gate.FIXTURE)
        psql(docker, container, gate.helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, gate.ACCEPTANCE)
        migration = gate.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        psql(docker, container, gate.GATE_ACCEPTANCE)
        psql(docker, container, approval.experiment_check.EXPERIMENT_SOURCE)
        psql(docker, container, approval.experiment_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, approval.funding_check.FUNDING_SOURCE)
        psql(docker, container, approval.funding_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, approval.adoption_check.ADOPTION_SOURCE)
        psql(docker, container, approval.adoption_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, approval.scale_check.SCALE_SOURCE)
        psql(docker, container, approval.scale_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, approval.replication_check.REPLICATION_SOURCE)
        replication_migration = approval.replication_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, replication_migration)
        psql(docker, container, replication_migration)
        psql(docker, container, approval.learning_check.LEARNING_SOURCE)
        learning_migration = approval.learning_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, learning_migration)
        psql(docker, container, learning_migration)
        psql(docker, container, approval.learning_check.LEARNING_ACCEPTANCE)
        psql(docker, container, approval.retirement_check.RETIREMENT_SOURCE)
        retirement_migration = approval.retirement_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, retirement_migration)
        psql(docker, container, retirement_migration)
        psql(docker, container, approval.retirement_check.RETIREMENT_ACCEPTANCE)
        independent = approval.prior.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, independent)
        psql(docker, container, independent)
        psql(docker, container, approval.prior.INDEPENDENT_REVIEW_ACCEPTANCE)
        psql(docker, container, approval.REVIEW_FIXTURE)
        approval_migration = approval.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, approval_migration)
        psql(docker, container, approval_migration)
        psql(docker, container, approval.APPROVAL_ACCEPTANCE)
        psql(docker, container, REVIEW_FIXTURE_CLEANUP)
        psql(docker, container, (ROOT / "schemas/postgres/476_location_solution_retirement_proposal.sql").read_text(encoding="utf-8"))
        psql(docker, container, (ROOT / "schemas/postgres/477_location_solution_learning_proposal.sql").read_text(encoding="utf-8"))
        candidate_migration = (ROOT / "schemas/postgres/481_location_solution_retirement_candidates.sql").read_text(encoding="utf-8")
        psql(docker, container, candidate_migration)
        psql(docker, container, candidate_migration)
        review_migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, review_migration)
        psql(docker, container, review_migration)
        psql(docker, container, REVIEW_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 7
        print("PASS: migrations 474–477, 481, and 482 apply; migrations 475, 481, and 482 replay; seven grouped reviewer/trigger acceptance checks passed")
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
