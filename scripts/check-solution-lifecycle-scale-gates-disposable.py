#!/usr/bin/env python3
"""Exercise migration 470 with location-scoped scale-gate fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADOPTION_CHECK = ROOT / "scripts/check-solution-lifecycle-adoption-disposable.py"
MIGRATION = ROOT / "schemas/postgres/470_location_scoped_solution_scale_gates.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-scale-gates-disposable.json"
spec = importlib.util.spec_from_file_location("solution_adoption_disposable", ADOPTION_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
adoption_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adoption_check)
funding_check = adoption_check.helper
experiment_check = funding_check.helper
gate_check = experiment_check.helper
run = adoption_check.run
psql = adoption_check.psql
wait_ready = adoption_check.wait_ready

SCALE_SOURCE = r"""
ALTER TABLE public.solution_scale_gate
    ADD COLUMN gate_type text NOT NULL DEFAULT 'safety',
    ADD COLUMN requirement text NOT NULL DEFAULT 'private requirement',
    ADD COLUMN measured_value text,
    ADD COLUMN threshold text,
    ADD COLUMN evidence_refs jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN metric_key text,
    ADD COLUMN threshold_numeric numeric,
    ADD COLUMN unit text,
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN approved_at timestamptz;
INSERT INTO public.solution_scale_gate
    (id, solution_id, scope_type, scope_id, status, gate_type,
     approved_by_party_id, approved_at)
VALUES
    ('d1000000-0000-4000-8000-000000000001',
     'c0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'passed', 'safety',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-15 00:00:00+00'),
    ('d1000000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000002', 'location',
     'b0000000-0000-4000-8000-000000000001', 'passed', 'equity',
     NULL, NULL),
    ('d1000000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000002', 'location',
     'b0000000-0000-4000-8000-000000000001', 'failed', 'data_quality',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-18 00:00:00+00'),
    ('d1000000-0000-4000-8000-000000000004',
     'c0000000-0000-4000-8000-000000000003', 'location',
     'b0000000-0000-4000-8000-000000000002', 'passed', 'safety',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-18 00:00:00+00'),
    ('d1000000-0000-4000-8000-000000000005',
     'c0000000-0000-4000-8000-000000000001', 'network',
     'f0000000-0000-4000-8000-000000000001', 'passed', 'regulatory',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-18 00:00:00+00');
"""

SCALE_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    gate_row record;
    seen integer := 0;
    denied boolean := false;
    function_result text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'scale_gate_status_counts'->>'passed' <> '3'
       OR lifecycle_summary->'scale_gate_status_counts'->>'failed' <> '1' THEN
        RAISE EXCEPTION 'existing migration-459 scale summary mismatch after column grants narrowed: %',
            lifecycle_summary->'scale_gate_status_counts';
    END IF;

    FOR gate_row IN SELECT * FROM kokonut_security.list_location_solution_scale_gates(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF gate_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'scale-gate projection included a solution outside exact location scope';
        END IF;
        IF gate_row.scale_gate_id = 'd1000000-0000-4000-8000-000000000001'
           AND (gate_row.gate_type <> 'safety'
                OR gate_row.gate_status <> 'passed'
                OR NOT gate_row.has_human_approval
                OR gate_row.approved_at <> '2026-10-15'::timestamptz) THEN
            RAISE EXCEPTION 'approved scale gate status projection mismatch';
        END IF;
        IF gate_row.scale_gate_id = 'd1000000-0000-4000-8000-000000000002'
           AND (gate_row.gate_status <> 'passed'
                OR gate_row.has_human_approval
                OR gate_row.approved_at IS NOT NULL) THEN
            RAISE EXCEPTION 'unapproved passed gate was misreported';
        END IF;
        IF gate_row.scale_gate_id = 'f7000000-0000-4000-8000-000000000001'
           AND (gate_row.gate_status <> 'passed'
                OR gate_row.has_human_approval
                OR gate_row.approved_at IS NOT NULL) THEN
            RAISE EXCEPTION 'legacy unapproved scale gate was misreported';
        END IF;
    END LOOP;
    IF seen <> 4 THEN RAISE EXCEPTION 'expected four exact-location scale gates, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_scale_gates(uuid,integer,integer)'::regprocedure
    ) INTO function_result;
    IF function_result ~* '(requirement|threshold|measured_value|evidence|party_id|metric_key|unit)' THEN
        RAISE EXCEPTION 'scale-gate projection signature exposes threshold, measurement, evidence, or identity';
    END IF;
    IF (SELECT procedure.provolatile
          FROM pg_catalog.pg_proc AS procedure
         WHERE procedure.oid = 'kokonut_security.list_location_solution_scale_gates(uuid,integer,integer)'::regprocedure
       ) <> 's' THEN
        RAISE EXCEPTION 'scale-gate projection is not stable/read-only';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_scale_gates(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded scale-gate pagination failed'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_scale_gates(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched scale-gate location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_scale_gates(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded scale-gate page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_scale_gates(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_scale_gate;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read scale-gate source table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_scale_gates(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_scale_gates(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_scale_gate', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_scale_gate', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'UPDATE')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'requirement', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'threshold', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'threshold_numeric', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'measured_value', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'evidence_refs', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'metric_key', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'unit', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'scope_type', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'status', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_scale_gate', 'approved_by_party_id', 'SELECT') THEN
        RAISE EXCEPTION 'scale-gate function or least-privilege column boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-scale-gates-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459, 466, 467, 468, 469, and 470 apply; migration 470 replays",
            "only gates whose solution lineage and exact location scope match are returned",
            "gate type/status and approval presence are reported without reviewer identity",
            "requirements, thresholds, measurements, evidence, metrics, and identity are omitted",
            "pagination, signed location context, exact grant, and no-write function stability are enforced",
            "migration-459 scale aggregates continue to work with narrowed source columns",
            "runtime can execute the bounded function but runtime and Directus cannot read the source table",
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
        psql(docker, container, SCALE_SOURCE)
        migration_470 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_470)
        psql(docker, container, migration_470)
        psql(docker, container, SCALE_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 7
        print("PASS: migrations 459/466/467/468/469/470 apply, migration 470 replays, and seven grouped PostgreSQL checks passed")
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
