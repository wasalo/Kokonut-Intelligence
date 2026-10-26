#!/usr/bin/env python3
"""Exercise migration 473 with exact-origin retirement fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING_CHECK = ROOT / "scripts/check-solution-lifecycle-learning-disposable.py"
MIGRATION = ROOT / "schemas/postgres/473_location_scoped_solution_retirements.sql"
CANDIDATE_MIGRATION = ROOT / "schemas/postgres/481_location_solution_retirement_candidates.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-retirement-candidates-disposable.json"
spec = importlib.util.spec_from_file_location("solution_learning_disposable", LEARNING_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
learning_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learning_check)
replication_check = learning_check.replication_check
scale_check = learning_check.scale_check
adoption_check = scale_check.adoption_check
funding_check = adoption_check.helper
experiment_check = funding_check.helper
gate_check = experiment_check.helper
run = learning_check.run
psql = learning_check.psql
wait_ready = learning_check.wait_ready

RETIREMENT_SOURCE = r"""
ALTER TABLE public.solution_retirement
    ADD COLUMN retirement_type text NOT NULL DEFAULT 'superseded',
    ADD COLUMN trigger_reason text NOT NULL DEFAULT 'private trigger reason',
    ADD COLUMN evidence_refs jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN affected_users jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN dependent_solutions jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN replacement_solution_id uuid,
    ADD COLUMN migration_plan text DEFAULT 'private migration plan',
    ADD COLUMN residual_risk text DEFAULT 'private residual risk',
    ADD COLUMN data_preservation_plan text DEFAULT 'private preservation plan',
    ADD COLUMN compensation_or_remedy_plan text DEFAULT 'private remedy plan',
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN approved_at timestamptz,
    ADD COLUMN effective_at timestamptz,
    ADD COLUMN post_retirement_review_at date,
    ADD COLUMN created_by_party_id uuid,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00';
UPDATE public.solution_retirement
   SET retirement_type = 'superseded', trigger_reason = 'pre-existing private reason',
       approved_by_party_id = NULL, approved_at = NULL,
       effective_at = NULL, created_at = '2026-10-11 00:00:00+00'
 WHERE id = 'f9000000-0000-4000-8000-000000000001';
INSERT INTO public.solution_retirement
    (id, solution_id, status, retirement_type, trigger_reason, evidence_refs,
     affected_users, dependent_solutions, replacement_solution_id, migration_plan,
     residual_risk, data_preservation_plan, compensation_or_remedy_plan,
     approved_by_party_id, approved_at, effective_at, post_retirement_review_at,
     created_by_party_id, created_at)
VALUES
    ('f9100000-0000-4000-8000-000000000001',
     'c0000000-0000-4000-8000-000000000001', 'approved', 'superseded',
     'private approved reason', '[{"secret": "evidence"}]',
     '[{"secret": "affected user"}]', '[{"secret": "dependent"}]',
     'c0000000-0000-4000-8000-000000000002', 'private migration',
     'private risk', 'private preservation', 'private remedy',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-16 00:00:00+00',
     '2026-10-20 00:00:00+00', '2027-01-20',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-15 00:00:00+00'),
    ('f9100000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000002', 'migration', 'unsafe',
     'linked solution global retirement', '[]', '[]', '[]', NULL, NULL,
     NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-10-14 00:00:00+00'),
    ('f9100000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000003', 'completed', 'mission_complete',
     'other location retirement', '[]', '[]', '[]', NULL, NULL,
     NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-10-13 00:00:00+00'),
    ('f9100000-0000-4000-8000-000000000004',
     'c0000000-0000-4000-8000-000000000004', 'proposed', 'ineffective',
     'unlinked network solution', '[]', '[]', '[]', NULL, NULL,
     NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-10-12 00:00:00+00');
"""

RETIREMENT_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    retirement_row record;
    seen integer := 0;
    denied boolean := false;
    function_result text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'retirement_status_counts' IS NULL THEN
        RAISE EXCEPTION 'existing migration-459 retirement summary was broken by narrowed grants';
    END IF;

    FOR retirement_row IN SELECT * FROM kokonut_security.list_location_solution_retirements(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF retirement_row.solution_id <> 'c0000000-0000-4000-8000-000000000001' THEN
            RAISE EXCEPTION 'retirement projection included non-originating location solution';
        END IF;
        IF retirement_row.retirement_id NOT IN (
            'f9000000-0000-4000-8000-000000000001',
            'f9100000-0000-4000-8000-000000000001'
        ) THEN
            RAISE EXCEPTION 'retirement projection included a linked, cross-location, or network retirement';
        END IF;
        IF retirement_row.retirement_id = 'f9100000-0000-4000-8000-000000000001'
           AND (retirement_row.retirement_type <> 'superseded'
                OR retirement_row.retirement_status <> 'approved'
                OR NOT retirement_row.has_human_approval
                OR retirement_row.approved_at <> '2026-10-16'::timestamptz
                OR retirement_row.effective_at <> '2026-10-20'::timestamptz
                OR retirement_row.post_retirement_review_at <> '2027-01-20'::date) THEN
            RAISE EXCEPTION 'approved location retirement status mapping mismatch';
        END IF;
        IF retirement_row.retirement_id = 'f9000000-0000-4000-8000-000000000001'
           AND (retirement_row.retirement_status <> 'proposed'
                OR retirement_row.has_human_approval
                OR retirement_row.approved_at IS NOT NULL) THEN
            RAISE EXCEPTION 'unapproved location retirement was misreported';
        END IF;
    END LOOP;
    IF seen <> 2 THEN RAISE EXCEPTION 'expected two exact-origin retirement rows, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_retirements(uuid,integer,integer)'::regprocedure
    ) INTO function_result;
    IF function_result ~* '(trigger_reason|evidence|affected_users|dependent_solutions|replacement_solution_id|migration_plan|residual_risk|data_preservation_plan|compensation_or_remedy_plan|party_id|created_by)' THEN
        RAISE EXCEPTION 'retirement projection signature exposes impact plans, evidence, or identity';
    END IF;
    IF (SELECT procedure.provolatile
          FROM pg_catalog.pg_proc AS procedure
         WHERE procedure.oid = 'kokonut_security.list_location_solution_retirements(uuid,integer,integer)'::regprocedure
       ) <> 's' THEN
        RAISE EXCEPTION 'retirement projection is not stable/read-only';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_retirements(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded retirement pagination failed'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirements(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched retirement location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirements(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded retirement page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirements(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_retirement;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read retirement source table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_retirements(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_retirements(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_retirement', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_retirement', 'UPDATE')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'trigger_reason', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'evidence_refs', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'affected_users', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'dependent_solutions', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'replacement_solution_id', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'migration_plan', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'residual_risk', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'data_preservation_plan', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'compensation_or_remedy_plan', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'approved_by_party_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'solution_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_retirement', 'status', 'SELECT') THEN
        RAISE EXCEPTION 'retirement function or least-privilege column boundary failed';
    END IF;
END $$;
"""

RETIREMENT_CANDIDATE_ACCEPTANCE = r"""
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
    seen integer := 0;
    function_result text;
    denied boolean := false;
BEGIN
    FOR item IN SELECT * FROM kokonut_security.list_location_solution_retirement_candidates(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF item.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000005'
        ) THEN
            RAISE EXCEPTION 'retirement candidates included a shared, cross-location, or organization solution';
        END IF;
        IF item.solution_name <> 'Synthetic solution'
           OR item.solution_type <> 'practice'
           OR item.current_stage NOT IN ('testing', 'paused')
           OR item.solution_status NOT IN ('active', 'paused') THEN
            RAISE EXCEPTION 'retirement candidate fixed projection mismatch';
        END IF;
    END LOOP;
    IF seen <> 2 THEN RAISE EXCEPTION 'expected two exact-origin retirement candidates, got %', seen; END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_retirement_candidates(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded retirement candidate pagination failed'; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_retirement_candidates(uuid,integer,integer)'::regprocedure
    ) INTO function_result;
    IF function_result ~* '(trigger_reason|evidence|party_id|retirement_id|replacement|migration_plan)' THEN
        RAISE EXCEPTION 'retirement candidate projection signature exposes private retirement details';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_candidates(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched retirement candidate location was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_candidates(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded retirement candidate page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_retirement_candidates(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'retirement candidate read without exact grant was accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_retirement_candidates(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_retirement_candidates(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution', 'UPDATE')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution', 'originating_scope_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution', 'name', 'SELECT') THEN
        RAISE EXCEPTION 'retirement candidate function or read-only owner boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-retirements-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": CANDIDATE_MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459 and 466–473 apply and migration 473 replays",
            "retirement records are returned only for solutions originated at the exact location",
            "status, approval presence, and effective/review timestamps are mapped",
            "trigger text, impact/dependency detail, plans, evidence, and identities are omitted",
            "pagination, signed context, exact grant, stable read-only behavior, and runtime boundaries are enforced",
            "migration-459 aggregate access continues after source columns are narrowed",
            "runtime can execute the function, while runtime and Directus cannot read the source table",
            "retirement proposal choices include only exact location-origin solutions, use fixed fields, and enforce signed context, grants, pagination, and runtime/Directus function boundaries",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
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
        migration_471 = replication_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_471)
        psql(docker, container, migration_471)
        psql(docker, container, learning_check.LEARNING_SOURCE)
        migration_472 = learning_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_472)
        psql(docker, container, migration_472)
        psql(docker, container, learning_check.LEARNING_ACCEPTANCE)
        psql(docker, container, RETIREMENT_SOURCE)
        migration_473 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_473)
        psql(docker, container, migration_473)
        psql(docker, container, RETIREMENT_ACCEPTANCE)
        candidate_migration = CANDIDATE_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, candidate_migration)
        psql(docker, container, candidate_migration)
        psql(docker, container, RETIREMENT_CANDIDATE_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: migrations 459, 466–473, and 481 apply; migrations 473 and 481 replay; nine grouped PostgreSQL checks passed")
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
