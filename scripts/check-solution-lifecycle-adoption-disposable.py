#!/usr/bin/env python3
"""Exercise migration 469 with consent-aware location adoption fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNDING_CHECK = ROOT / "scripts/check-solution-lifecycle-funding-disposable.py"
MIGRATION = ROOT / "schemas/postgres/469_location_scoped_solution_adoption.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-adoption-disposable.json"
spec = importlib.util.spec_from_file_location("solution_funding_disposable", FUNDING_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution funding fixtures")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
experiment_check = helper.helper
gate_check = helper.gate_check
run = helper.run
psql = helper.psql
wait_ready = helper.wait_ready

ADOPTION_SOURCE = r"""
ALTER TABLE public.solution_adoption_program
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN target_population jsonb NOT NULL DEFAULT '{"private": "cohort"}',
    ADD COLUMN adoption_pathway text NOT NULL DEFAULT 'private program pathway',
    ADD COLUMN champion_party_id uuid;
UPDATE public.solution_adoption_program
   SET created_at = '2026-10-01 00:00:00+00', updated_at = '2026-10-04 00:00:00+00'
 WHERE id = 'f4000000-0000-4000-8000-000000000001';
INSERT INTO public.solution_adoption_program
    (id, solution_id, target_scope_type, target_scope_id, status, created_at, updated_at,
     target_population, adoption_pathway, champion_party_id)
VALUES
    ('f4000000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000002', 'location',
     'b0000000-0000-4000-8000-000000000001', 'active',
     '2026-10-05 00:00:00+00', '2026-10-19 00:00:00+00',
     '{"private": "cohort population"}', 'private pathway',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4000000-0000-4000-8000-000000000004',
     'c0000000-0000-4000-8000-000000000002', 'location',
     'b0000000-0000-4000-8000-000000000001', 'active',
     '2026-10-06 00:00:00+00', '2026-10-19 00:00:00+00',
     '{"private": "single adopter"}', 'private pathway',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');

CREATE TABLE public.solution_adoption_event (
    id uuid PRIMARY KEY,
    program_id uuid NOT NULL,
    cohort_id uuid,
    adopter_ref text NOT NULL,
    event_type text NOT NULL,
    observed_at timestamptz NOT NULL,
    fidelity_score numeric,
    support_required text,
    outcome jsonb NOT NULL DEFAULT '{}',
    consent_checked boolean NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}',
    recorded_by_party_id uuid
);
INSERT INTO public.solution_adoption_event
    (id, program_id, adopter_ref, event_type, observed_at, fidelity_score,
     support_required, outcome, consent_checked, evidence, recorded_by_party_id)
VALUES
    ('f4100000-0000-4000-8000-000000000001', 'f4000000-0000-4000-8000-000000000001', 'private-a', 'onboarded', '2026-10-10', 0.8, 'private-support', '{"private":1}', true, '{"private":1}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000002', 'f4000000-0000-4000-8000-000000000001', 'private-b', 'repeat_use', '2026-10-11', 0.9, 'private-support', '{"private":2}', true, '{"private":2}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000003', 'f4000000-0000-4000-8000-000000000001', 'private-c', 'habitual_use', '2026-10-12', 0.7, 'private-support', '{"private":3}', true, '{"private":3}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000011', 'f4000000-0000-4000-8000-000000000001', '   ', 'repeat_use', '2026-10-12', 0.7, 'private-support', '{"private":11}', true, '{"private":11}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000004', 'f4000000-0000-4000-8000-000000000003', 'private-d', 'onboarded', '2026-10-13', 0.8, 'private-support', '{"private":4}', true, '{"private":4}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000005', 'f4000000-0000-4000-8000-000000000003', 'private-e', 'repeat_use', '2026-10-14', 0.8, 'private-support', '{"private":5}', true, '{"private":5}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000006', 'f4000000-0000-4000-8000-000000000003', 'private-f', 'habitual_use', '2026-10-15', 0.8, 'private-support', '{"private":6}', true, '{"private":6}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000007', 'f4000000-0000-4000-8000-000000000003', 'private-g', 'advocating', '2026-10-16', 0.8, 'private-support', '{"private":7}', true, '{"private":7}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000008', 'f4000000-0000-4000-8000-000000000003', 'private-h', 'advocating', '2026-10-17', 0.8, 'private-support', '{"private":8}', true, '{"private":8}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000009', 'f4000000-0000-4000-8000-000000000003', 'private-i', 'interested', '2026-10-18', 0.8, 'private-support', '{"private":9}', false, '{"private":9}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000010', 'f4000000-0000-4000-8000-000000000003', 'private-d', 'repeat_use', '2026-10-18', 0.8, 'private-support', '{"private":10}', true, '{"private":10}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f4100000-0000-4000-8000-000000000012', 'f4000000-0000-4000-8000-000000000003', ' PRIVATE-D ', 'repeat_use', '2026-10-18', 0.8, 'private-support', '{"private":12}', true, '{"private":12}', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');

-- Five events from one adopter must still be suppressed.
INSERT INTO public.solution_adoption_event
    (id, program_id, adopter_ref, event_type, observed_at, consent_checked)
SELECT ('f4300000-0000-4000-8000-' || pg_catalog.lpad(n::text, 12, '0'))::uuid,
       'f4000000-0000-4000-8000-000000000004', 'one-adopter',
       'repeat_use', '2026-10-18', true
  FROM generate_series(1, 5) AS n;

-- The other-location program has a large cohort but must remain outside the query.
INSERT INTO public.solution_adoption_event
    (id, program_id, adopter_ref, event_type, observed_at, consent_checked)
SELECT ('f4200000-0000-4000-8000-' || pg_catalog.lpad(n::text, 12, '0'))::uuid,
       'f4000000-0000-4000-8000-000000000002', 'outside-' || n,
       'onboarded', '2026-10-18', true
  FROM generate_series(1, 7) AS n;
"""

ADOPTION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    adoption_row record;
    seen integer := 0;
    denied boolean := false;
    result_signature text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'adoption_program_status_counts'->>'active' <> '3' THEN
        RAISE EXCEPTION 'existing aggregate summary failed after adoption column grants were narrowed';
    END IF;

    FOR adoption_row IN SELECT * FROM kokonut_security.list_location_solution_adoption(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF adoption_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'adoption projection included a solution outside exact location scope';
        END IF;
        IF adoption_row.program_id = 'f4000000-0000-4000-8000-000000000001'
           AND adoption_row.consented_adopter_reference_count IS NOT NULL THEN
            RAISE EXCEPTION 'fewer than five consented adopters were not suppressed';
        END IF;
        IF adoption_row.program_id = 'f4000000-0000-4000-8000-000000000003'
           AND adoption_row.consented_adopter_reference_count IS DISTINCT FROM 5 THEN
            RAISE EXCEPTION 'distinct consented adopter count or non-consented exclusion failed';
        END IF;
        IF adoption_row.program_id = 'f4000000-0000-4000-8000-000000000004'
           AND adoption_row.consented_adopter_reference_count IS NOT NULL THEN
            RAISE EXCEPTION 'repeated events from one adopter bypassed small-cohort suppression';
        END IF;
    END LOOP;
    IF seen <> 3 THEN RAISE EXCEPTION 'expected three exact-location adoption programs, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_adoption(uuid,integer,integer)'::regprocedure
    ) INTO result_signature;
    IF result_signature ~* '(adopter_ref[[:space:]]|event_type|observed_at|fidelity|support_required|outcome|evidence|party_id|cohort_id)' THEN
        RAISE EXCEPTION 'adoption projection signature exposes participant or event detail';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_adoption(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded adoption pagination did not return one row'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_adoption(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_adoption(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded adoption page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_adoption(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_adoption_program;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read adoption program table'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_adoption_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read adoption event table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_adoption(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime lacks adoption projection execute';
    END IF;
    IF has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_adoption(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'Directus can execute adoption projection';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.solution_adoption_program', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_adoption_event', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_adoption_program', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_adoption_event', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus can directly read adoption source tables';
    END IF;
    IF has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_program', 'target_population', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_program', 'adoption_pathway', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_program', 'champion_party_id', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_event', 'event_type', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_event', 'evidence', 'SELECT') THEN
        RAISE EXCEPTION 'reader can select private adoption payload columns';
    END IF;
    IF NOT has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_event', 'adopter_ref', 'SELECT')
       OR has_column_privilege('kokonut_runtime', 'public.solution_adoption_event', 'adopter_ref', 'SELECT')
       OR has_column_privilege('kokonut_directus_runtime', 'public.solution_adoption_event', 'adopter_ref', 'SELECT') THEN
        RAISE EXCEPTION 'distinct-adopter aggregate reader boundary failed';
    END IF;
    IF NOT has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_program', 'status', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_adoption_event', 'consent_checked', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_adoption_program', 'UPDATE') THEN
        RAISE EXCEPTION 'reader lacks required status fields or has write access';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-adoption-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459, 466, 467, 468, and 469 apply, and migration 469 replays",
            "adoption programs are scoped by both solution lineage and exact location target",
            "fewer than five distinct nonempty normalized consented adopter references are suppressed; repeated, blank, and non-consented events cannot bypass the threshold",
            "participant/event detail is omitted from output and reader column privileges",
            "page bounds, signed context, exact location grant, and read-only behavior are enforced",
            "the migration-459 aggregate summary still runs with the narrowed program columns",
            "runtime can call the bounded function but cannot read source tables; Directus cannot call it",
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
        psql(docker, container, helper.FUNDING_SOURCE)
        psql(docker, container, helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, ADOPTION_SOURCE)
        migration_469 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_469)
        psql(docker, container, migration_469)
        psql(docker, container, ADOPTION_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 7
        print("PASS: migrations 459/466/467/468/469 apply, migration 469 replays, and seven grouped PostgreSQL checks passed")
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
