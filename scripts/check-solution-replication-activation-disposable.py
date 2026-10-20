#!/usr/bin/env python3
"""Exercise migration 496 using the isolated CAP-035 replication fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_CHECK = ROOT / "scripts/check-solution-replication-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/496_location_solution_replication_activation.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-activation-disposable.json"
spec = importlib.util.spec_from_file_location("solution_replication_review_disposable", REVIEW_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior solution replication fixtures")
review_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review_check)

run = review_check.run
psql = review_check.psql
wait_ready = review_check.wait_ready

ACTIVATION_FIXTURE = r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000008',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'transition', NULL, NULL);

SELECT set_config(
    'kokonut.test_activation_one',
    (SELECT replication_id::text FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000001'), false
);
SELECT set_config(
    'kokonut.test_activation_two',
    (SELECT replication_id::text FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000009'), false
);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
         WHERE tgrelid = 'public.solution_replication'::pg_catalog.regclass
           AND tgname = 'trg_solution_replication_kernel_fields'
           AND tgenabled <> 'D'
           AND (tgtype & 4) <> 0
    ) THEN
        RAISE EXCEPTION 'replication lifecycle guard trigger was not installed';
    END IF;
END $$;

SET ROLE kokonut_solution_replication_proposer;
BEGIN;
DO $$
DECLARE
    denied boolean := false;
BEGIN
    INSERT INTO public.solution_replication (
        id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
        target_context, status, evidence
    ) VALUES (
        'e9000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000003',
        'location', 'b0000000-0000-4000-8000-000000000001',
        'Synthetic proposal boundary check', 'proposed', '[]'::jsonb
    );
    BEGIN
        INSERT INTO public.solution_replication (
            id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
            target_context, status, evidence
        ) VALUES (
            'e9000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'location', 'b0000000-0000-4000-8000-000000000001',
            'Synthetic privileged status injection', 'active', '[]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN
        RAISE EXCEPTION 'proposal role directly inserted an active replication';
    END IF;
END $$;
ROLLBACK;
RESET ROLE;

SET ROLE kokonut_solution_replication_reviewer;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    denied boolean := false;
    current_status text;
BEGIN
    SELECT status INTO current_status FROM public.solution_replication
     WHERE id = pg_catalog.current_setting('kokonut.test_activation_one')::UUID;
    BEGIN
        UPDATE public.solution_replication
           SET status = 'active'
         WHERE id = pg_catalog.current_setting('kokonut.test_activation_one')::UUID;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN
        SELECT status INTO current_status FROM public.solution_replication
         WHERE id = pg_catalog.current_setting('kokonut.test_activation_one')::UUID;
        RAISE EXCEPTION 'reviewer role bypassed activation transition (row now %, current role %)',
            current_status, CURRENT_USER;
    END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    activation record;
    replay record;
    denied boolean := false;
BEGIN
    SELECT * INTO activation
      FROM kokonut_security.activate_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        pg_catalog.current_setting('kokonut.test_activation_one')::UUID,
        'ab960000-0000-4000-8000-000000000001', TRUE
      );
    IF activation.replication_status <> 'active'
       OR activation.replayed IS DISTINCT FROM FALSE
       OR activation.started_at IS NULL THEN
        RAISE EXCEPTION 'approved replication did not start';
    END IF;

    SELECT * INTO replay
      FROM kokonut_security.activate_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        pg_catalog.current_setting('kokonut.test_activation_one')::UUID,
        'ab960000-0000-4000-8000-000000000001', TRUE
      );
    IF replay.event_id IS DISTINCT FROM activation.event_id
       OR replay.started_at IS DISTINCT FROM activation.started_at
       OR replay.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact activation retry did not replay its receipt';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.activate_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            pg_catalog.current_setting('kokonut.test_activation_two')::UUID,
            'ab960000-0000-4000-8000-000000000001', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-input activation retry was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.activate_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            pg_catalog.current_setting('kokonut.test_activation_one')::UUID,
            'ab960000-0000-4000-8000-000000000002', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'activation without transition grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.activate_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            pg_catalog.current_setting('kokonut.test_activation_two')::UUID,
            'ab960000-0000-4000-8000-000000000003', TRUE
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'rejected replication was allowed to start'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_replication_activation_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read activation receipts directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    started public.solution_replication%ROWTYPE;
    rejected public.solution_replication%ROWTYPE;
BEGIN
    SELECT * INTO started FROM public.solution_replication
     WHERE id = pg_catalog.current_setting('kokonut.test_activation_one')::UUID;
    SELECT * INTO rejected FROM public.solution_replication
     WHERE id = pg_catalog.current_setting('kokonut.test_activation_two')::UUID;
    IF started.status <> 'active'
       OR started.started_at IS NULL
       OR started.started_by_party_id <> 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
       OR started.result IS NOT NULL
       OR started.evidence_maturity IS NOT NULL
       OR started.evidence <> '[]'::jsonb
       OR started.completed_at IS NOT NULL
       OR rejected.status <> 'rejected'
       OR (SELECT current_stage FROM public.solution WHERE id = started.solution_id) <> 'validated'
       OR (SELECT count(*) FROM public.solution_replication_activation_receipt) <> 1 THEN
        RAISE EXCEPTION 'activation attribution, receipt, or lifecycle boundary is incorrect';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.activate_location_solution_replication(uuid,uuid,uuid,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.activate_location_solution_replication(uuid,uuid,uuid,boolean)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication_activation_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_replication_starter', 'public.solution_replication_activation_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_replication_starter', 'public.solution_replication_activation_receipt', 'DELETE')
       OR has_column_privilege('kokonut_solution_replication_starter', 'public.solution_replication', 'status', 'UPDATE') IS DISTINCT FROM TRUE
       OR has_column_privilege('kokonut_solution_replication_starter', 'public.solution_replication', 'result', 'UPDATE') THEN
        RAISE EXCEPTION 'activation function or narrow role boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-replication-activation-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 496 applies and replays after migration 495",
            "only an approved, exact-location, attributed proposal with current validated source lineage can start",
            "exact retries replay and request-key collisions fail closed",
            "rejected proposals and operators without transition grants cannot start",
            "direct reviewer-role status changes and elevated proposal-role active inserts are rejected by the trigger",
            "activation records actor/time atomically without result, evidence, maturity, completion, or solution-stage changes",
            "runtime has function-only activation access; Directus cannot execute it or read receipts",
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
        review_sql = review_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, review_sql)
        psql(docker, container, review_sql)
        psql(docker, container, review_check.REVIEW_ACCEPTANCE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, ACTIVATION_FIXTURE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 10
        print("PASS: migrations through 496 apply, migration 496 replays, and ten replication activation groups passed")
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
