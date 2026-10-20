#!/usr/bin/env python3
"""Exercise migration 500 with isolated CAP-035 learning lifecycle fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-learning-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/500_location_solution_learning_application.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-learning-application-disposable.json"
spec = importlib.util.spec_from_file_location("solution_learning_review_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior CAP-035 learning fixtures")
learning_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learning_check)

completion_check = learning_check.completion_check
review_check = learning_check.review_check
activation_check = learning_check.activation_check
replication_check = learning_check.replication_check
run = learning_check.run
psql = learning_check.psql
wait_ready = learning_check.wait_ready

APPLICATION_GRANTS = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000014',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'apply', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000015',
     'a0000000-0000-4000-8000-000000000006',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'apply', NULL, NULL);
"""

APPLICATION_REVIEW = r"""
SELECT set_config(
    'kokonut.test_learning_application_record',
    (SELECT learning_record_id::TEXT FROM public.solution_learning_proposal_event
      WHERE request_id = 'ab990000-0000-4000-8000-000000000002'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000006', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE item record;
BEGIN
    SELECT * INTO item FROM kokonut_security.review_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001',
        pg_catalog.current_setting('kokonut.test_learning_application_record')::UUID,
        'ab9a0000-0000-4000-8000-000000000004',
        'accepted', 'Independent review for application fixture.', TRUE
    );
    IF item.decision <> 'accepted' OR item.replayed THEN
        RAISE EXCEPTION 'application fixture was not independently accepted';
    END IF;
END $$;
COMMIT;
RESET ROLE;
"""

APPLICATION_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_learning_application_record',
    (SELECT learning_record_id::TEXT FROM public.solution_learning_proposal_event
      WHERE request_id = 'ab990000-0000-4000-8000-000000000002'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE item record; result record; replay record; denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO item FROM kokonut_security.list_location_solution_learning_applications(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    );
    IF item.learning_record_id IS DISTINCT FROM
         pg_catalog.current_setting('kokonut.test_learning_application_record')::UUID
       OR item.is_reviewed_by_current_actor IS DISTINCT FROM FALSE
       OR item.finding <> 'A locally tailored training schedule improved participation.' THEN
        RAISE EXCEPTION 'application queue omitted current accepted learning or exposed the wrong actor flag';
    END IF;

    denied := FALSE;
    BEGIN
        UPDATE public.solution_learning_record SET decision_status = 'applied',
            applied_to_version = 'bypass', owner_party_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
         WHERE id = item.learning_record_id;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly update a learning record'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000006', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.apply_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
            'aba00000-0000-4000-8000-000000000001', 'handbook-v2', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'independent reviewer applied the learning record'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', TRUE);
    SELECT * INTO result FROM kokonut_security.apply_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
        'aba00000-0000-4000-8000-000000000002', 'handbook-v2', TRUE
    );
    IF result.decision_status <> 'applied' OR result.applied_to_version <> 'handbook-v2'
       OR result.applied_by_party_id <> 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
       OR result.replayed THEN
        RAISE EXCEPTION 'accepted learning was not applied with authenticated human attribution';
    END IF;
    SELECT * INTO replay FROM kokonut_security.apply_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
        'aba00000-0000-4000-8000-000000000002', 'handbook-v2', TRUE
    );
    IF NOT replay.replayed OR replay.application_id <> result.application_id THEN
        RAISE EXCEPTION 'exact application retry did not replay its immutable receipt';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.apply_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', item.learning_record_id,
            'aba00000-0000-4000-8000-000000000002', 'different-version', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed application reused an idempotency key'; END IF;

    denied := FALSE;
    BEGIN SELECT 1 FROM public.solution_learning_application_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private learning application receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    learning_id UUID := pg_catalog.current_setting('kokonut.test_learning_application_record')::UUID;
    source_solution_id UUID;
BEGIN
    SELECT record_row.solution_id INTO source_solution_id
      FROM public.solution_learning_record AS record_row WHERE record_row.id = learning_id;
    IF (SELECT decision_status FROM public.solution_learning_record WHERE id = learning_id) <> 'applied'
       OR (SELECT applied_to_version FROM public.solution_learning_record WHERE id = learning_id) <> 'handbook-v2'
       OR (SELECT current_stage FROM public.solution WHERE id = source_solution_id) <> 'validated' THEN
        RAISE EXCEPTION 'application did not persist or changed the solution stage';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.solution_learning_record', 'UPDATE')
       OR has_column_privilege('kokonut_runtime', 'public.solution_learning_record', 'decision_status', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_learning_application_receipt', 'SELECT')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.list_location_solution_learning_applications(uuid,integer,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.apply_location_solution_learning(uuid,uuid,uuid,text,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.apply_location_solution_learning(uuid,uuid,uuid,text,boolean)', 'EXECUTE') THEN
        RAISE EXCEPTION 'bounded learning application role boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-learning-apply-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 500 applies and replays after migration 499",
            "application queue requires exact signed apply scope and active human identity",
            "runtime cannot directly update learning records or read application receipts",
            "only accepted learning with current source lineage can be applied at the exact location",
            "the applying human must differ from the independent reviewer",
            "application stores the responsible human and target version atomically",
            "exact retries replay and changed request reuse is rejected",
            "application records do not change the solution lifecycle stage",
            "runtime has bounded-function access and Directus cannot execute application functions",
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
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, APPLICATION_GRANTS)
        second_proposal = learning_check.PROPOSE_ACCEPTANCE.replace(
            "ab990000-0000-4000-8000-000000000001",
            "ab990000-0000-4000-8000-000000000002",
        )
        psql(docker, container, second_proposal)
        psql(docker, container, APPLICATION_REVIEW)
        psql(docker, container, APPLICATION_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: migrations through 500 apply and replay, and nine learning application groups passed")
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
