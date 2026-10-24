#!/usr/bin/env python3
"""Exercise migration 467 with location-scoped solution experiment fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_CHECK = ROOT / "scripts/check-solution-lifecycle-gates-disposable.py"
MIGRATION = ROOT / "schemas/postgres/467_location_scoped_solution_experiments.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-experiments-disposable.json"
spec = importlib.util.spec_from_file_location("solution_gates_disposable", GATE_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
run = helper.run
psql = helper.psql
wait_ready = helper.wait_ready

FIXTURE = helper.FIXTURE
ACCEPTANCE = helper.ACCEPTANCE
GATE_ACCEPTANCE = helper.GATE_ACCEPTANCE
EXPERIMENT_SOURCE = r"""
ALTER TABLE public.solution_experiment
    ADD COLUMN protocol_version text NOT NULL DEFAULT 'v1',
    ADD COLUMN duration_days integer,
    ADD COLUMN primary_metric_keys jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN secondary_metric_keys jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN started_at timestamptz,
    ADD COLUMN completed_at timestamptz,
    ADD COLUMN hypothesis text,
    ADD COLUMN baseline_definition text,
    ADD COLUMN treatment_definition text,
    ADD COLUMN owner_party_id uuid;
ALTER TABLE public.solution_experiment_result
    ADD COLUMN reviewed_at timestamptz,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-02 00:00:00+00',
    ADD COLUMN primary_results jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN adverse_events jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN reviewed_by_party_id uuid;

UPDATE public.solution_experiment
   SET protocol_version = 'v2', duration_days = 42,
       primary_metric_keys = '["soil_cover", "water_retention"]',
       secondary_metric_keys = '["labor_hours"]',
       started_at = '2026-10-03 00:00:00+00',
       completed_at = '2026-10-17 00:00:00+00'
 WHERE id = 'f0000000-0000-4000-8000-000000000001';

INSERT INTO public.solution_experiment
    (id, solution_id, status, protocol_version, duration_days,
     primary_metric_keys, secondary_metric_keys, created_at, updated_at,
     started_at, completed_at, hypothesis, baseline_definition,
     treatment_definition, owner_party_id)
VALUES
    ('f0000000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000002', 'completed', 'v1.3', 28,
     '["canopy_cover", "soil_moisture"]', '["input_cost"]',
     '2026-10-04 00:00:00+00', '2026-10-18 00:00:00+00',
     '2026-10-05 00:00:00+00', '2026-10-18 00:00:00+00',
     'private hypothesis', 'private baseline', 'private treatment',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');

INSERT INTO public.solution_experiment_result
    (id, experiment_id, outcome, primary_results, evidence, adverse_events,
     reviewed_by_party_id, reviewed_at, created_at)
VALUES
    ('f1000000-0000-4000-8000-000000000003',
     'f0000000-0000-4000-8000-000000000003', 'validated',
     '{"private_value": 99}', '[{"private": "evidence"}]',
     '[{"private": "event"}]', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '2026-10-19 00:00:00+00', '2026-10-19 00:00:00+00');
"""

EXPERIMENT_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    experiment_row record;
    seen integer := 0;
    denied boolean := false;
    result_signature text;
BEGIN
    FOR experiment_row IN SELECT * FROM kokonut_security.list_location_solution_experiments(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF experiment_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'experiment projection included a solution outside exact location scope';
        END IF;
        IF experiment_row.experiment_id = 'f0000000-0000-4000-8000-000000000003'
           AND (experiment_row.protocol_version <> 'v1.3'
                OR experiment_row.experiment_status <> 'completed'
                OR experiment_row.primary_metric_count <> 2
                OR experiment_row.secondary_metric_count <> 1
                OR experiment_row.latest_result_outcome <> 'validated'
                OR experiment_row.latest_result_reviewed_at <> '2026-10-19'::timestamptz
                OR experiment_row.completed_at <> '2026-10-18'::timestamptz) THEN
            RAISE EXCEPTION 'experiment projection omitted or misreported allowlisted status';
        END IF;
        IF experiment_row.experiment_id = 'f0000000-0000-4000-8000-000000000001'
           AND (experiment_row.latest_result_outcome IS NOT NULL
                OR experiment_row.latest_result_reviewed_at IS NOT NULL) THEN
            RAISE EXCEPTION 'unreviewed experiment result was exposed';
        END IF;
    END LOOP;
    IF seen <> 2 THEN RAISE EXCEPTION 'expected two exact-location experiments, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_experiments(uuid,integer,integer)'::regprocedure
    ) INTO result_signature;
    IF result_signature ~* '(evidence|observed|party_id|hypothesis|baseline_definition|treatment_definition|primary_results|adverse_events|owner_party_id|reviewed_by_party_id)' THEN
        RAISE EXCEPTION 'experiment result signature exposes a private payload field';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_experiments(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded experiment pagination did not return one row'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_experiments(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_experiments(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded experiment page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_experiments(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_experiment;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read solution experiment tables'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_experiments(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_experiments(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_experiment', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_experiment', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_experiment', 'UPDATE') THEN
        RAISE EXCEPTION 'solution experiment function or reader privilege boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-experiments-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459, 466, and 467 apply, and migration 467 replays",
            "experiments follow solution origin or an explicit location link only",
            "the projection includes protocol version, lifecycle state, metric counts, timestamps, and latest reviewed outcome",
            "unreviewed result rows are suppressed, and page bounds, signed context, exact location grant, and read-only behavior are enforced",
            "protocol narratives, raw metrics/results, observations, evidence, adverse events, and party identities are omitted",
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
        psql(docker, container, helper.helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, helper.ACCEPTANCE)
        psql(docker, container, helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, helper.GATE_ACCEPTANCE)
        psql(docker, container, EXPERIMENT_SOURCE)
        migration_467 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_467)
        psql(docker, container, migration_467)
        psql(docker, container, EXPERIMENT_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 8
        print("PASS: migrations 459/466/467 apply, migration 467 replays, and eight disposable PostgreSQL assertions passed")
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
