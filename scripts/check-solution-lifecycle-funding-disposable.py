#!/usr/bin/env python3
"""Exercise migration 468 with location-scoped solution funding fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_CHECK = ROOT / "scripts/check-solution-lifecycle-experiments-disposable.py"
MIGRATION = ROOT / "schemas/postgres/468_location_scoped_solution_funding.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-funding-disposable.json"
spec = importlib.util.spec_from_file_location("solution_experiments_disposable", EXPERIMENT_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
gate_check = helper.helper
run = gate_check.run
psql = gate_check.psql
wait_ready = gate_check.wait_ready

FUNDING_SOURCE = r"""
ALTER TABLE public.solution_funding_case
    ADD COLUMN capital_stage text NOT NULL DEFAULT 'pilot',
    ADD COLUMN funding_instrument text NOT NULL DEFAULT 'grant',
    ADD COLUMN currency text NOT NULL DEFAULT 'USD',
    ADD COLUMN requested_amount numeric(15,2) NOT NULL DEFAULT 1000,
    ADD COLUMN rationale text NOT NULL DEFAULT 'private funding rationale',
    ADD COLUMN evidence jsonb NOT NULL DEFAULT '[{"private": "evidence"}]',
    ADD COLUMN submitted_by_party_id uuid,
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT '2026-10-01 00:00:00+00',
    ADD COLUMN approved_at timestamptz;
UPDATE public.solution_funding_case
   SET decision_status = 'submitted', created_at = '2026-10-01 00:00:00+00'
 WHERE id = 'f3000000-0000-4000-8000-000000000001';
INSERT INTO public.solution_funding_case
    (id, solution_id, decision_status, capital_stage, funding_instrument, currency,
     requested_amount, rationale, evidence, submitted_by_party_id,
     approved_by_party_id, created_at, approved_at)
VALUES
    ('f3000000-0000-4000-8000-000000000002',
     'c0000000-0000-4000-8000-000000000002', 'approved', 'scale',
     'community_fund', 'USD', 987654.32, 'private linked rationale',
     '[{"private": "case evidence"}]',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '2026-10-05 00:00:00+00', '2026-10-12 00:00:00+00'),
    ('f3000000-0000-4000-8000-000000000003',
     'c0000000-0000-4000-8000-000000000003', 'approved', 'pilot',
     'grant', 'DOP', 555.00, 'other location private rationale',
     '[{"private": "other evidence"}]',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     '2026-10-18 00:00:00+00', '2026-10-19 00:00:00+00');

ALTER TABLE public.solution_funding_tranche
    ADD COLUMN tranche_number integer,
    ADD COLUMN amount numeric(15,2) NOT NULL DEFAULT 0,
    ADD COLUMN milestone_conditions jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN approved_by_party_id uuid,
    ADD COLUMN approved_at timestamptz,
    ADD COLUMN released_at timestamptz,
    ADD COLUMN released_by_party_id uuid;
INSERT INTO public.solution_funding_tranche
    (id, funding_case_id, tranche_number, amount, milestone_conditions, status,
     approved_by_party_id, approved_at, released_at, released_by_party_id)
VALUES
    ('f3100000-0000-4000-8000-000000000001',
     'f3000000-0000-4000-8000-000000000002', 1, 123.45,
     '{"private_condition": "proof"}', 'approved',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-13 00:00:00+00', NULL, NULL),
    ('f3100000-0000-4000-8000-000000000002',
     'f3000000-0000-4000-8000-000000000002', 2, 456.78,
     '{"private_condition": "inspection"}', 'released',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-14 00:00:00+00',
     '2026-10-17 00:00:00+00', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('f3100000-0000-4000-8000-000000000003',
     'f3000000-0000-4000-8000-000000000003', 1, 500.00,
     '{"private_condition": "outside"}', 'released',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-19 00:00:00+00',
     '2026-10-19 00:00:00+00', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
"""

FUNDING_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    funding_row record;
    seen integer := 0;
    denied boolean := false;
    result_signature text;
    lifecycle_summary jsonb;
BEGIN
    lifecycle_summary := kokonut_security.location_solution_lifecycle_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF lifecycle_summary->'funding_decision_counts'->>'submitted' <> '1'
       OR lifecycle_summary->'funding_decision_counts'->>'approved' <> '1' THEN
        RAISE EXCEPTION 'existing aggregate summary failed after funding column grants were narrowed';
    END IF;

    FOR funding_row IN SELECT * FROM kokonut_security.list_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001', 10, 0
    ) LOOP
        seen := seen + 1;
        IF funding_row.solution_id NOT IN (
            'c0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002'
        ) THEN
            RAISE EXCEPTION 'funding projection included a solution outside exact location scope';
        END IF;
        IF funding_row.funding_case_id = 'f3000000-0000-4000-8000-000000000001'
           AND funding_row.tranche_id IS NOT NULL THEN
            RAISE EXCEPTION 'funding case without tranches was dropped or misprojected';
        END IF;
        IF funding_row.funding_case_id = 'f3000000-0000-4000-8000-000000000002'
           AND funding_row.tranche_number = 1
           AND (funding_row.capital_stage <> 'scale'
                OR funding_row.funding_instrument <> 'community_fund'
                OR funding_row.currency <> 'USD'
                OR funding_row.decision_status <> 'approved'
                OR funding_row.tranche_status <> 'approved'
                OR funding_row.tranche_approved_at <> '2026-10-13'::timestamptz
                OR funding_row.tranche_released_at IS NOT NULL) THEN
            RAISE EXCEPTION 'approved funding/tranche lifecycle projection mismatch';
        END IF;
        IF funding_row.funding_case_id = 'f3000000-0000-4000-8000-000000000002'
           AND funding_row.tranche_number = 2
           AND (funding_row.tranche_status <> 'released'
                OR funding_row.tranche_released_at <> '2026-10-17'::timestamptz) THEN
            RAISE EXCEPTION 'released tranche lifecycle projection mismatch';
        END IF;
    END LOOP;
    IF seen <> 3 THEN RAISE EXCEPTION 'expected three exact-location funding rows, got %', seen; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.list_location_solution_funding(uuid,integer,integer)'::regprocedure
    ) INTO result_signature;
    IF result_signature ~* '(amount|rationale|evidence|milestone_conditions|party_id|released_by|approved_by)' THEN
        RAISE EXCEPTION 'funding projection signature exposes sensitive values or identities';
    END IF;

    SELECT count(*) INTO seen FROM kokonut_security.list_location_solution_funding(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF seen <> 1 THEN RAISE EXCEPTION 'bounded funding pagination did not return one row'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unbounded funding page was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_solution_funding(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without solution_lifecycle:read grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_funding_case;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read funding case table'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_funding_tranche;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read funding tranche table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_solution_funding(uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_funding(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_funding_case', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_funding_tranche', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_funding_tranche', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'requested_amount', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'rationale', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'evidence', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'amount', 'SELECT')
       OR has_column_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'milestone_conditions', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_funding_case', 'decision_status', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'status', 'SELECT')
       OR has_table_privilege('kokonut_solution_reader', 'public.solution_funding_tranche', 'UPDATE') THEN
        RAISE EXCEPTION 'solution funding function or column privilege boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-funding-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 459, 466, 467, and 468 apply, and migration 468 replays",
            "funding cases and tranches are included only for exact origin or location-linked solutions",
            "cases without tranches remain visible and tranche states/timestamps preserve ordering",
            "amounts, milestone conditions, rationale, evidence, and party identities are omitted from function output and reader column grants",
            "the migration-459 aggregate summary continues to work with only its required funding columns",
            "page bounds, signed context, exact location grant, and read-only behavior are enforced",
            "runtime can call the bounded function but cannot read funding tables; Directus cannot call it",
        ],
    }
    try:
        docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
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
        psql(docker, container, helper.EXPERIMENT_SOURCE)
        psql(docker, container, helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, FUNDING_SOURCE)
        migration_468 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_468)
        psql(docker, container, migration_468)
        psql(docker, container, FUNDING_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 9
        print("PASS: migrations 459/466/467/468 apply, migration 468 replays, and nine disposable PostgreSQL assertions passed")
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
