#!/usr/bin/env python3
"""Exercise migration 504's exact-location solution creation contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-retirement-execution-disposable.py"
PREVIOUS_MIGRATION = ROOT / "schemas/postgres/503_location_solution_nonpromotion_stage_transition.sql"
MIGRATION = ROOT / "schemas/postgres/504_location_solution_create.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-create-disposable.json"
spec = importlib.util.spec_from_file_location("solution_stage_transition_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
psql = prior.psql
wait_ready = prior.wait_ready

ACTOR_FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES
    ('a0000000-0000-4000-8000-000000000041', TRUE),
    ('a0000000-0000-4000-8000-000000000042', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES
    ('c1000000-0000-4000-8000-000000000041', 'Synthetic solution creator', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000042', 'Synthetic no-grant operator', 'person', 'active')
ON CONFLICT (id) DO UPDATE SET party_type = EXCLUDED.party_type, status = EXCLUDED.status;
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES
    ('a5000000-0000-4000-8000-000000000041', 'a0000000-0000-4000-8000-000000000041', 'c1000000-0000-4000-8000-000000000041', NULL),
    ('a5000000-0000-4000-8000-000000000042', 'a0000000-0000-4000-8000-000000000042', 'c1000000-0000-4000-8000-000000000042', NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000041', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'create', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000042', 'a0000000-0000-4000-8000-000000000041', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'read', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
DO $$
DECLARE created record; replay record; denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_solution(
        'b0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000041',
        'synthetic.water.harvesting.v1', 'Synthetic water harvesting', 'practice',
        'Disposable acceptance problem statement.', 'Slow runoff and improve infiltration.',
        'Current drainage practice.', 'medium', 'high',
        'Synthetic rationale for scoped creation acceptance.',
        '[{"source":"synthetic://solution-create"}]'::JSONB, TRUE
    );
    IF created.solution_id IS NULL OR created.lifecycle_event_id IS NULL
       OR created.current_stage <> 'discovered' OR created.solution_status <> 'active'
       OR created.replayed THEN
        RAISE EXCEPTION 'location solution was not created in discovered state';
    END IF;
    SELECT * INTO replay FROM kokonut_security.create_location_solution(
        'b0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000041',
        'synthetic.water.harvesting.v1', 'Synthetic water harvesting', 'practice',
        'Disposable acceptance problem statement.', 'Slow runoff and improve infiltration.',
        'Current drainage practice.', 'medium', 'high',
        'Synthetic rationale for scoped creation acceptance.',
        '[{"source":"synthetic://solution-create"}]'::JSONB, TRUE
    );
    IF NOT replay.replayed OR replay.solution_id <> created.solution_id
       OR replay.lifecycle_event_id <> created.lifecycle_event_id THEN
        RAISE EXCEPTION 'identical retry did not return the original solution and opening event';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution(
            'b0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000041',
            'synthetic.water.harvesting.v1', 'Changed title', 'practice',
            'Disposable acceptance problem statement.', 'Slow runoff and improve infiltration.',
            'Current drainage practice.', 'medium', 'high',
            'Synthetic rationale for scoped creation acceptance.',
            '[{"source":"synthetic://solution-create"}]'::JSONB, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed request payload reused the same request ID'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution(
            'b0000000-0000-4000-8000-000000000002',
            'ab000000-0000-4000-8000-000000000043',
            'synthetic.water.harvesting.other', 'Other location', 'practice',
            'Must not be created under another location.', NULL, NULL, 'medium', 'medium',
            'Signed context and exact grant must match the requested location.',
            '[]'::JSONB, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'different requested location bypassed signed scope'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000042', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution(
            'b0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000044',
            'synthetic.water.harvesting.no-grant', 'No grant', 'practice',
            'Must not be created without exact create permission.', NULL, NULL, 'medium', 'medium',
            'No create grant exists for this synthetic operator.', '[]'::JSONB, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without create grant created a solution'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000041', TRUE);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_solution(
            'b0000000-0000-4000-8000-000000000001',
            'ab000000-0000-4000-8000-000000000045',
            'Synthetic.MixedCase', 'Invalid key', 'practice',
            'Should fail validation before insert.', NULL, NULL, 'medium', 'medium',
            'Input validation must reject invalid canonical keys.', '[]'::JSONB, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'invalid canonical key was accepted'; END IF;

    denied := FALSE;
    BEGIN PERFORM 1 FROM public.location_solution_creation_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private creation receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE solution_origin_type TEXT; solution_origin_id UUID; creator UUID;
        initial_event_count INTEGER; receipt_count INTEGER;
BEGIN
    SELECT originating_scope_type, originating_scope_id, created_by_party_id
      INTO solution_origin_type, solution_origin_id, creator
      FROM public.solution WHERE canonical_key = 'synthetic.water.harvesting.v1';
    IF solution_origin_type <> 'location'
       OR solution_origin_id <> 'b0000000-0000-4000-8000-000000000001'
       OR creator <> 'c1000000-0000-4000-8000-000000000041' THEN
        RAISE EXCEPTION 'created solution origin or actor attribution was incorrect';
    END IF;
    SELECT count(*) INTO initial_event_count FROM public.solution_lifecycle_event
     WHERE solution_id = (SELECT id FROM public.solution WHERE canonical_key = 'synthetic.water.harvesting.v1')
       AND from_stage IS NULL AND to_stage = 'discovered'
       AND actor_party_id = 'c1000000-0000-4000-8000-000000000041';
    SELECT count(*) INTO receipt_count FROM public.location_solution_creation_receipt
     WHERE request_id = 'ab000000-0000-4000-8000-000000000041';
    IF initial_event_count <> 1 OR receipt_count <> 1 THEN
        RAISE EXCEPTION 'solution, opening event, or retry receipt was not atomic/exactly once';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_solution(uuid,uuid,text,text,text,text,text,text,text,text,text,jsonb,boolean)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'runtime cannot execute the bounded solution creation function';
    END IF;
    IF has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_solution(uuid,uuid,text,text,text,text,text,text,text,text,text,jsonb,boolean)',
        'EXECUTE'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.location_solution_creation_receipt', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'public.location_solution_creation_receipt', 'INSERT'
    ) THEN
        RAISE EXCEPTION 'Directus can execute solution creation or access private receipts';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-solution-create-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 504 applies and replays after the ordered CAP-035 lifecycle chain",
            "solution creation requires a signed exact-location create grant and active human binding",
            "created solutions carry a location origin and attributed discovered lifecycle event",
            "exact retries replay; changed requests, cross-location requests, missing grants, and invalid keys fail",
            "runtime can execute the bounded function but cannot read receipts; Directus cannot execute it or read receipts",
            "solution, opening event, and private retry receipt are atomic and exact-once",
        ],
    }
    try:
        subprocess.run(
            [docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"],
            text=True, capture_output=True, check=True,
        )
        wait_ready(container, docker)
        prior.apply_ordered_lifecycle_chain(docker, container)
        psql(docker, container, """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
        ALTER TABLE public.solution ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE public.solution
            ADD COLUMN IF NOT EXISTS canonical_key TEXT,
            ADD COLUMN IF NOT EXISTS name TEXT,
            ADD COLUMN IF NOT EXISTS solution_type TEXT,
            ADD COLUMN IF NOT EXISTS problem_statement TEXT,
            ADD COLUMN IF NOT EXISTS theory_of_change TEXT,
            ADD COLUMN IF NOT EXISTS baseline_alternative TEXT,
            ADD COLUMN IF NOT EXISTS originating_scope_type TEXT,
            ADD COLUMN IF NOT EXISTS originating_scope_id UUID,
            ADD COLUMN IF NOT EXISTS created_by_party_id UUID,
            ADD COLUMN IF NOT EXISTS risk_class TEXT,
            ADD COLUMN IF NOT EXISTS reversibility TEXT,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE public.solution_adopter_readiness
            ADD COLUMN IF NOT EXISTS assessed_by_party_id UUID;
        ALTER TABLE public.solution_configuration
            ADD COLUMN IF NOT EXISTS approved_by_party_id UUID;
        ALTER TABLE public.solution_lifecycle_event
            ADD COLUMN IF NOT EXISTS from_stage TEXT,
            ADD COLUMN IF NOT EXISTS to_stage TEXT,
            ADD COLUMN IF NOT EXISTS rationale TEXT,
            ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::JSONB,
            ADD COLUMN IF NOT EXISTS actor_party_id UUID,
            ADD COLUMN IF NOT EXISTS rollback_plan TEXT;
        """)
        previous_sql = PREVIOUS_MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, previous_sql)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, ACTOR_FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: migration 504 applies/replays; exact-location solution creation, opening event, retry, validation, and receipt-boundary checks passed")
        return 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
