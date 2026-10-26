#!/usr/bin/env python3
"""Exercise migration 472 with location-targeted reviewed-learning fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLICATION_CHECK = ROOT / "scripts/check-solution-lifecycle-replications-disposable.py"
MIGRATION = ROOT / "schemas/postgres/472_location_scoped_solution_learning.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-learning-disposable.json"
spec = importlib.util.spec_from_file_location("solution_replications_disposable", REPLICATION_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
replication_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replication_check)
scale_check = replication_check.scale_check
adoption_check = scale_check.adoption_check
funding_check = adoption_check.helper
experiment_check = funding_check.helper
gate_check = experiment_check.helper
run = replication_check.run
psql = replication_check.psql
wait_ready = replication_check.wait_ready

LEARNING_SOURCE = r"""
ALTER TABLE public.solution_learning_record
    ADD COLUMN source_experiment_id uuid,
    ADD COLUMN source_replication_id uuid,
    ADD COLUMN lesson_type text NOT NULL DEFAULT 'implementation',
    ADD COLUMN finding text NOT NULL DEFAULT 'private lesson text',
    ADD COLUMN confidence text NOT NULL DEFAULT 'moderate',
    ADD COLUMN transferability text NOT NULL DEFAULT 'unknown',
    ADD COLUMN affected_assumptions jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN affected_metrics jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN recommended_action text NOT NULL DEFAULT 'private recommendation',
    ADD COLUMN applied_to_version text,
    ADD COLUMN owner_party_id uuid,
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00';
INSERT INTO public.solution_learning_record
    (id, solution_id, source_replication_id, lesson_type, finding, confidence,
     transferability, affected_assumptions, affected_metrics, recommended_action,
     decision_status, owner_party_id, evidence, created_at)
VALUES
    ('f8100000-0000-4000-8000-000000000001',
     'c0000000-0000-4000-8000-000000000001',
     'e2000000-0000-4000-8000-000000000001', 'validated_assumption',
     'private finding', 'high', 'medium', '[{"secret": "assumption"}]',
     '[{"secret": "metric"}]', 'private action', 'accepted',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '[{"secret": "evidence"}]',
     '2026-10-18 00:00:00+00'),
    ('f8100000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000001',
     'e2000000-0000-4000-8000-000000000002', 'safety',
     'unreviewed source lesson', 'low', 'unknown', '[]', '[]', 'private action',
     'proposed', NULL, '[]', '2026-10-17 00:00:00+00'),
    ('f8100000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000003',
     'e2000000-0000-4000-8000-000000000003', 'context_transfer',
     'other location lesson', 'moderate', 'medium', '[]', '[]', 'private action',
     'applied', NULL, '[]', '2026-10-16 00:00:00+00'),
    ('f8100000-0000-4000-8000-000000000004',
     'c0000000-0000-4000-8000-000000000001',
     'e2000000-0000-4000-8000-000000000004', 'economic',
     'network lesson', 'moderate', 'high', '[]', '[]', 'private action',
     'rejected', NULL, '[]', '2026-10-15 00:00:00+00'),
    ('f8100000-0000-4000-8000-000000000005',
     'c0000000-0000-4000-8000-000000000001', NULL, 'implementation',
     'experiment-only lesson', 'high', 'high', '[]', '[]', 'private action',
     'accepted', NULL, '[]', '2026-10-14 00:00:00+00'),
    ('f8100000-0000-4000-8000-000000000006',
     'c0000000-0000-4000-8000-000000000002',
     'e2000000-0000-4000-8000-000000000001', 'equity',
     'mismatched source solution', 'high', 'high', '[]', '[]', 'private action',
     'accepted', NULL, '[]', '2026-10-13 00:00:00+00'),
    ('f8100000-0000-4000-8000-000000000007',
     'c0000000-0000-4000-8000-000000000004',
     'e2000000-0000-4000-8000-000000000006', 'adoption',
     'unlinked solution lesson', 'high', 'high', '[]', '[]', 'private action',
     'proposed', NULL, '[]', '2026-10-12 00:00:00+00');
UPDATE public.solution_learning_record
   SET source_replication_id = 'e2000000-0000-4000-8000-000000000001',
       lesson_type = 'validated_assumption', finding = 'pre-existing private text',
       confidence = 'high', transferability = 'medium',
       recommended_action = 'pre-existing private action', created_at = '2026-10-11 00:00:00+00'
 WHERE id = 'f8000000-0000-4000-8000-000000000001';
"""

LEARNING_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    learning_row record;
    seen integer := 0;
    denied boolean := false;
    function_result text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'learning_decision_counts' IS NULL THEN
        RAISE EXCEPTION 'existing migration-459 learning summary was broken by narrowed grants';
    END IF;

    FOR learning_row IN SELECT * FROM kokonut_security.list_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF learning_row.solution_id <> 'c0000000-0000-4000-8000-000000000001' THEN
            RAISE EXCEPTION 'learning projection included a solution outside exact location lineage';
        END IF;
        IF learning_row.learning_record_id NOT IN (
            'f8000000-0000-4000-8000-000000000001',
            'f8100000-0000-4000-8000-000000000001'
        ) THEN
            RAISE EXCEPTION 'learning projection included unreviewed, cross-location, network, or unlinked source';
        END IF;
        IF learning_row.learning_record_id = 'f8100000-0000-4000-8000-000000000001'
           AND (learning_row.lesson_type <> 'validated_assumption'
                OR learning_row.confidence <> 'high'
                OR learning_row.transferability <> 'medium'
                OR learning_row.decision_status <> 'accepted'
                OR learning_row.created_at <> '2026-10-18'::timestamptz) THEN
            RAISE EXCEPTION 'reviewed location learning status mapping mismatch';
        END IF;
    END LOOP;
    IF seen <> 2 THEN RAISE EXCEPTION 'expected two reviewed location learning rows, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_learning(uuid,integer,integer)'::regprocedure
    ) INTO function_result;
    IF function_result ~* '(source_replication_id|source_experiment_id|finding|recommended_action|affected_assumptions|affected_metrics|evidence|party_id|applied_to_version)' THEN
        RAISE EXCEPTION 'learning projection signature exposes lesson content, evidence, source IDs, or identity';
    END IF;
    IF (SELECT procedure.provolatile
          FROM pg_catalog.pg_proc AS procedure
         WHERE procedure.oid = 'kokonut_security.list_location_solution_learning(uuid,integer,integer)'::regprocedure
       ) <> 's' THEN
        RAISE EXCEPTION 'learning projection is not stable/read-only';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded learning pagination failed'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_learning(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched learning location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded learning page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_learning_record;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read learning source table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_learning(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_learning(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_learning_record', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_learning_record', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'UPDATE')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'finding', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'recommended_action', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'affected_assumptions', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'affected_metrics', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'evidence', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'owner_party_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'solution_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'decision_status', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_learning_record', 'source_replication_id', 'SELECT') THEN
        RAISE EXCEPTION 'learning function or least-privilege column boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-learning-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459 and 466–472 apply; migration 472 replays",
            "only learning linked to a reviewed replication targeting the exact location is returned",
            "solution origin/location links and replication solution lineage must both match",
            "lesson text, recommendations, affected metrics, evidence, source IDs, and identities are omitted",
            "pagination, signed context, exact grant, stable read-only behavior, and runtime boundaries are enforced",
            "migration-459 aggregate access continues after source columns are narrowed",
            "runtime can execute the function, while runtime and Directus cannot read the source table",
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
        psql(docker, container, LEARNING_SOURCE)
        migration_472 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_472)
        psql(docker, container, migration_472)
        psql(docker, container, LEARNING_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 8
        print("PASS: migrations 459 and 466–472 apply, migration 472 replays, and eight grouped PostgreSQL checks passed")
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
