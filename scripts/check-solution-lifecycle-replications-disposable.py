#!/usr/bin/env python3
"""Exercise migration 471 with location-targeted replication fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCALE_CHECK = ROOT / "scripts/check-solution-lifecycle-scale-gates-disposable.py"
MIGRATION = ROOT / "schemas/postgres/471_location_scoped_solution_replications.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-replications-disposable.json"
spec = importlib.util.spec_from_file_location("solution_scale_gates_disposable", SCALE_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
scale_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scale_check)
adoption_check = scale_check.adoption_check
funding_check = adoption_check.helper
experiment_check = funding_check.helper
gate_check = experiment_check.helper
run = scale_check.run
psql = scale_check.psql
wait_ready = scale_check.wait_ready

REPLICATION_SOURCE = r"""
ALTER TABLE public.solution_replication
    ADD COLUMN source_experiment_id uuid,
    ADD COLUMN target_scope_type text NOT NULL DEFAULT 'legacy_unknown',
    ADD COLUMN target_scope_id uuid NOT NULL DEFAULT 'b0000000-0000-4000-8000-000000000002',
    ADD COLUMN target_context text NOT NULL DEFAULT 'private target context',
    ADD COLUMN context_similarity numeric,
    ADD COLUMN adaptation_required text,
    ADD COLUMN replication_protocol jsonb NOT NULL DEFAULT '{"private": true}',
    ADD COLUMN result text,
    ADD COLUMN evidence_maturity integer,
    ADD COLUMN reviewed_by_party_id uuid,
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[{"private": true}]',
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN completed_at timestamptz;
INSERT INTO public.solution_replication
    (id, solution_id, status, source_experiment_id, target_scope_type,
     target_scope_id, target_context, context_similarity, adaptation_required,
     replication_protocol, result, evidence_maturity, reviewed_by_party_id,
     evidence, created_at, completed_at)
VALUES
    ('e2000000-0000-4000-8000-000000000001',
     'c0000000-0000-4000-8000-000000000001', 'completed',
     'f0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'private exact target context',
     0.875, 'private adaptation plan', '{"private": "protocol"}',
     'successful', 3, 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '[{"private": "evidence"}]', '2026-10-10 00:00:00+00', '2026-10-19 00:00:00+00'),
    ('e2000000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000002', 'active',
     'f0000000-0000-4000-8000-000000000003', 'location',
     'b0000000-0000-4000-8000-000000000001', 'private active target',
     NULL, 'private active adaptation', '{"secret": "protocol"}',
     NULL, NULL, NULL, '[{"secret": "evidence"}]',
     '2026-10-11 00:00:00+00', NULL),
    ('e2000000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000003', 'completed',
     'f0000000-0000-4000-8000-000000000002', 'location',
     'b0000000-0000-4000-8000-000000000002', 'other location',
     0.900, 'other plan', '{}', 'successful', 4,
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '[]',
     '2026-10-12 00:00:00+00', '2026-10-18 00:00:00+00'),
    ('e2000000-0000-4000-8000-000000000004',
     'c0000000-0000-4000-8000-000000000001', 'completed',
     'f0000000-0000-4000-8000-000000000001', 'network',
     'b0000000-0000-4000-8000-000000000001', 'network replication',
     0.800, 'network plan', '{}', 'mixed', 2,
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '[]',
     '2026-10-13 00:00:00+00', '2026-10-19 00:00:00+00'),
    ('e2000000-0000-4000-8000-000000000005',
     'c0000000-0000-4000-8000-000000000002', 'approved',
     'f0000000-0000-4000-8000-000000000003', 'organization',
     'f0000000-0000-4000-8000-000000000001', 'organization target',
     0.700, 'organization plan', '{}', NULL, 1,
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '[]',
     '2026-10-14 00:00:00+00', NULL),
    ('e2000000-0000-4000-8000-000000000006',
     'c0000000-0000-4000-8000-000000000004', 'active',
     'f0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'unlinked global solution',
     0.600, 'global plan', '{}', 'inconclusive', 1,
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '[]',
     '2026-10-15 00:00:00+00', NULL);
"""

REPLICATION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    replication_row record;
    seen integer := 0;
    denied boolean := false;
    function_result text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'replication_status_counts'->>'proposed' <> '1'
       OR lifecycle_summary->'replication_status_counts'->>'completed' <> '2' THEN
        RAISE EXCEPTION 'migration-459 replication aggregate failed after column grants narrowed: %',
            lifecycle_summary->'replication_status_counts';
    END IF;

    FOR replication_row IN SELECT * FROM kokonut_security.list_location_solution_replications(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF replication_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'replication projection included a solution outside exact location lineage';
        END IF;
        IF replication_row.replication_id = 'e2000000-0000-4000-8000-000000000001'
           AND (replication_row.replication_status <> 'completed'
                OR replication_row.replication_result <> 'successful'
                OR replication_row.evidence_maturity <> 3
                OR NOT replication_row.has_review
                OR replication_row.completed_at <> '2026-10-19'::timestamptz) THEN
            RAISE EXCEPTION 'reviewed completed replication projection mismatch';
        END IF;
        IF replication_row.replication_id = 'e2000000-0000-4000-8000-000000000002'
           AND (replication_row.replication_status <> 'active'
                OR replication_row.replication_result IS NOT NULL
                OR replication_row.evidence_maturity IS NOT NULL
                OR replication_row.has_review
                OR replication_row.completed_at IS NOT NULL) THEN
            RAISE EXCEPTION 'active unreviewed replication was misreported';
        END IF;
    END LOOP;
    IF seen <> 2 THEN RAISE EXCEPTION 'expected two exact-location replications, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_replications(uuid,integer,integer)'::regprocedure
    ) INTO function_result;
    IF function_result ~* '(source_experiment_id|target_context|context_similarity|adaptation_required|replication_protocol|evidence[[:space:]]|reviewed_by_party_id)' THEN
        RAISE EXCEPTION 'replication projection exposes source linkage, target plans, evidence, or reviewer identity';
    END IF;
    IF (SELECT procedure.provolatile
          FROM pg_catalog.pg_proc AS procedure
         WHERE procedure.oid = 'kokonut_security.list_location_solution_replications(uuid,integer,integer)'::regprocedure
       ) <> 's' THEN
        RAISE EXCEPTION 'replication projection is not stable/read-only';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_replications(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded replication pagination failed'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_replications(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched replication location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_replications(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded replication page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_replications(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_replication;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read replication source table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_replications(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_replications(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_replication', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_replication', 'UPDATE')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'source_experiment_id', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'target_context', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'context_similarity', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'adaptation_required', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'replication_protocol', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'evidence', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'solution_id', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'status', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_replication', 'reviewed_by_party_id', 'SELECT') THEN
        RAISE EXCEPTION 'replication function or least-privilege column boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-replications-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459, 466, 467, 468, 469, 470, and 471 apply; migration 471 replays",
            "only location-targeted replication rows for exact origin/link solutions are returned",
            "status, result, evidence maturity, review presence, and timestamps are mapped",
            "source IDs, target narratives, adaptation plans, protocol, evidence, and reviewer identities are omitted",
            "pagination, signed context, exact grant, and stable read-only function are enforced",
            "the migration-459 aggregate continues to work after source columns are narrowed",
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
        psql(docker, container, REPLICATION_SOURCE)
        migration_471 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_471)
        psql(docker, container, migration_471)
        psql(docker, container, REPLICATION_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 7
        print("PASS: migrations 459 and 466–471 apply, migration 471 replays, and seven grouped PostgreSQL checks passed")
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
