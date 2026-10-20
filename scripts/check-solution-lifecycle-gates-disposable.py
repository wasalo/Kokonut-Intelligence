#!/usr/bin/env python3
"""Exercise migration 466 with location-scoped solution gate fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_CHECK = ROOT / "scripts/check-solution-lifecycle-summary-disposable.py"
MIGRATION = ROOT / "schemas/postgres/466_location_scoped_solution_gates.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-gates-disposable.json"
spec = importlib.util.spec_from_file_location("solution_summary_disposable", SUMMARY_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
run = helper.run
psql = helper.psql
wait_ready = helper.wait_ready

FIXTURE = helper.FIXTURE + r"""
ALTER TABLE public.solution
    ADD COLUMN name text NOT NULL DEFAULT 'Synthetic solution',
    ADD COLUMN solution_type text NOT NULL DEFAULT 'practice';
ALTER TABLE public.solution_stage_gate
    ADD COLUMN from_stage text NOT NULL DEFAULT 'discovered',
    ADD COLUMN to_stage text NOT NULL DEFAULT 'testing',
    ADD COLUMN required_evidence_maturity integer,
    ADD COLUMN required_experiment_count integer NOT NULL DEFAULT 0,
    ADD COLUMN requires_human_approval boolean NOT NULL DEFAULT true,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
"""
ACCEPTANCE = helper.ACCEPTANCE.replace(
    "INSERT INTO public.solution_stage_gate VALUES\n",
    "INSERT INTO public.solution_stage_gate (id, solution_id, status) VALUES\n",
)
if ACCEPTANCE == helper.ACCEPTANCE:
    raise RuntimeError("could not adapt the solution gate fixture insert")
ACCEPTANCE += r"""
UPDATE public.solution_stage_gate
   SET from_stage = 'testing', to_stage = 'validated',
       required_evidence_maturity = 3, required_experiment_count = 2
 WHERE id = 'e0000000-0000-4000-8000-000000000001';
"""

GATE_ACCEPTANCE = r"""
INSERT INTO public.solution_gate_evaluation
    (id, gate_id, passed, evaluated_at)
VALUES
    ('e1000000-0000-4000-8000-000000000003',
     'e0000000-0000-4000-8000-000000000001', false, '2026-10-03');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    gate_row record;
    seen integer := 0;
    denied boolean := false;
    result_signature text;
BEGIN
    FOR gate_row IN SELECT * FROM kokonut_security.list_location_solution_gates(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF gate_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'gate projection included a solution outside exact location scope';
        END IF;
        IF gate_row.gate_id = 'e0000000-0000-4000-8000-000000000001'
           AND (gate_row.latest_evaluation_passed IS DISTINCT FROM false
                OR gate_row.latest_evaluated_at <> '2026-10-03'::timestamptz
                OR gate_row.from_stage <> 'testing'
                OR gate_row.to_stage <> 'validated'
                OR NOT gate_row.requires_human_approval) THEN
            RAISE EXCEPTION 'gate one latest evaluation or allowlisted fields mismatch';
        END IF;
        IF gate_row.gate_id = 'e0000000-0000-4000-8000-000000000002'
           AND gate_row.latest_evaluation_passed IS DISTINCT FROM false THEN
            RAISE EXCEPTION 'gate two latest evaluation mismatch';
        END IF;
    END LOOP;
    IF seen <> 2 THEN RAISE EXCEPTION 'expected two exact-location gates, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_gates(uuid,integer,integer)'::regprocedure
    ) INTO result_signature;
    IF result_signature ~* '(evidence jsonb|observed jsonb|party_id|rationale|problem_statement)' THEN
        RAISE EXCEPTION 'gate result signature exposes a private payload field';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_gates(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded gate pagination did not return one row'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_gates(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_gates(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded gate page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_gates(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_stage_gate;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read solution gate tables'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_gates(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_gates(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_stage_gate', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_stage_gate', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_stage_gate', 'UPDATE') THEN
        RAISE EXCEPTION 'solution gate function or reader privilege boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-gates-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459 and 466 apply, and migration 466 replays",
            "solution and gate rows are returned only for exact origin or explicit location links",
            "latest evaluation wins with stable timestamp/id ordering and no reviewer identity",
            "page bounds, signed context, and exact location solution_lifecycle:read are enforced",
            "the projection omits evidence, observations, narratives, and party identifiers",
            "runtime can call the bounded function but cannot read source tables; Directus cannot call it",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        migration_459 = helper.MIGRATION.read_text(encoding="utf-8")
        migration_466 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_459)
        psql(docker, container, ACCEPTANCE)
        psql(docker, container, migration_466)
        psql(docker, container, migration_466)
        psql(docker, container, GATE_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 6
        print("PASS: migration 466 applies/replays and all six disposable PostgreSQL assertions passed")
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
