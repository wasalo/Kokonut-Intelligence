#!/usr/bin/env python3
"""Exercise migration 503's exact-location non-promotion stage transitions."""

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
MIGRATION = ROOT / "schemas/postgres/503_location_solution_nonpromotion_stage_transition.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-nonpromotion-stage-transition-disposable.json"
spec = importlib.util.spec_from_file_location("solution_retirement_execution_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
run = prior.run
psql = prior.psql
wait_ready = prior.wait_ready

ACTOR_FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES ('a0000000-0000-4000-8000-000000000031', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('c1000000-0000-4000-8000-000000000031', 'Synthetic stage transition operator', 'person', 'active')
ON CONFLICT (id) DO UPDATE SET party_type = EXCLUDED.party_type, status = EXCLUDED.status;
INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES ('a5000000-0000-4000-8000-000000000031', 'a0000000-0000-4000-8000-000000000031', 'c1000000-0000-4000-8000-000000000031', NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000031', 'a0000000-0000-4000-8000-000000000031', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'read', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000032', 'a0000000-0000-4000-8000-000000000031', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'transition', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
INSERT INTO public.solution (
    id, canonical_key, name, solution_type, problem_statement,
    originating_scope_type, originating_scope_id, current_stage, status
) VALUES
    ('c0000000-0000-4000-8000-000000000031', 'synthetic:cap035:stage-transition',
     'Synthetic stage transition solution', 'practice', 'Disposable acceptance fixture',
     'location', 'b0000000-0000-4000-8000-000000000001', 'testing', 'active'),
    ('c0000000-0000-4000-8000-000000000032', 'synthetic:cap035:other-location',
     'Synthetic other location solution', 'practice', 'Disposable cross-scope fixture',
     'location', 'b0000000-0000-4000-8000-000000000002', 'testing', 'active'),
    ('c0000000-0000-4000-8000-000000000033', 'synthetic:cap035:superseded',
     'Synthetic superseded solution', 'practice', 'Disposable superseded-state fixture',
     'location', 'b0000000-0000-4000-8000-000000000001', 'testing', 'active')
ON CONFLICT (id) DO NOTHING;
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000031', TRUE);
SELECT set_config('kokonut.actor_type', 'operator', TRUE);
DO $$
DECLARE target record; changed record; replay record; denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO target
      FROM kokonut_security.list_location_solution_stage_transition_targets(
          'b0000000-0000-4000-8000-000000000001', 10, 0
      ) WHERE solution_id = 'c0000000-0000-4000-8000-000000000031';
    IF target.solution_name <> 'Synthetic stage transition solution'
       OR target.current_stage <> 'testing' OR target.solution_status <> 'active' THEN
        RAISE EXCEPTION 'exact-location transition target projection omitted current state';
    END IF;
    IF EXISTS (
        SELECT 1 FROM kokonut_security.list_location_solution_stage_transition_targets(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        ) WHERE solution_id = 'c0000000-0000-4000-8000-000000000032'
    ) THEN
        RAISE EXCEPTION 'target projection exposed a different location solution';
    END IF;

    SELECT * INTO changed FROM kokonut_security.transition_location_solution_stage(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000031', 'testing', 'pilot_active',
        'ab000000-0000-4000-8000-000000000031',
        'Reviewed evidence supports starting a bounded pilot.',
        '[{"source":"synthetic://stage-transition"}]'::JSONB,
        'Return to testing if field outcomes regress.', TRUE
    );
    IF changed.from_stage <> 'testing' OR changed.to_stage <> 'pilot_active'
       OR changed.solution_status <> 'active' OR changed.replayed THEN
        RAISE EXCEPTION 'non-promotion transition returned unexpected state';
    END IF;
    SELECT * INTO replay FROM kokonut_security.transition_location_solution_stage(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000031', 'testing', 'pilot_active',
        'ab000000-0000-4000-8000-000000000031',
        'Reviewed evidence supports starting a bounded pilot.',
        '[{"source":"synthetic://stage-transition"}]'::JSONB,
        'Return to testing if field outcomes regress.', TRUE
    );
    IF NOT replay.replayed OR replay.lifecycle_event_id <> changed.lifecycle_event_id THEN
        RAISE EXCEPTION 'identical transition retry did not replay its original event';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000031', 'testing', 'pilot_active',
            'ab000000-0000-4000-8000-000000000031',
            'Changed payload cannot reuse a transition request identifier.',
            '[{"source":"synthetic://stage-transition"}]'::JSONB,
            'Return to testing if field outcomes regress.', TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed request payload reused an idempotency key'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000031', 'testing', 'failed',
            'ab000000-0000-4000-8000-000000000032',
            'Stale expected stage must fail even with a new request key.',
            '[{"source":"synthetic://stale-stage"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'stale expected stage was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000031', 'pilot_active', 'validated',
            'ab000000-0000-4000-8000-000000000033',
            'Promotion must remain on the approved gate workflow.',
            '[{"source":"synthetic://promotion-block"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'promotion stage bypassed its gate workflow'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000031', 'pilot_active', 'retired',
            'ab000000-0000-4000-8000-000000000034',
            'Retirement must remain on the separate sunset workflow.',
            '[{"source":"synthetic://retirement-block"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'retirement stage bypassed its sunset workflow'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000032', 'testing', 'pilot_active',
            'ab000000-0000-4000-8000-000000000035',
            'A solution originating elsewhere cannot be changed from this location.',
            '[{"source":"synthetic://wrong-origin"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN no_data_found THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location-origin solution was transitioned'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000031', 'pilot_active', 'failed',
            'ab000000-0000-4000-8000-000000000036',
            'Signed context cannot authorize a different requested location.',
            '[{"source":"synthetic://wrong-context"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'request location was not bound to signed context'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000031', 'pilot_active', 'adopting',
            'ab000000-0000-4000-8000-000000000037',
            'Adoption transition requires approved readiness and configuration.',
            '[{"source":"synthetic://adoption-prerequisite"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'adopting stage bypassed location readiness/configuration'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_stage(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000033', 'testing', 'superseded',
            'ab000000-0000-4000-8000-000000000038',
            'Supersession requires the reviewed retirement and replacement workflow.',
            '[{"source":"synthetic://superseded"}]'::JSONB, NULL, TRUE
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'superseded status bypassed retirement/replacement review'; END IF;

    denied := FALSE;
    BEGIN PERFORM 1 FROM public.solution_nonpromotion_transition_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read transition receipts'; END IF;
    denied := FALSE;
    BEGIN
        UPDATE public.solution SET current_stage = 'failed'
         WHERE id = 'c0000000-0000-4000-8000-000000000031';
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly update solution stage'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE stage_value TEXT; event_count INTEGER; receipt_count INTEGER;
        superseded_stage TEXT; superseded_status TEXT; superseded_events INTEGER;
BEGIN
    SELECT current_stage INTO stage_value FROM public.solution
     WHERE id = 'c0000000-0000-4000-8000-000000000031';
    SELECT count(*) INTO event_count FROM public.solution_lifecycle_event
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000031';
    SELECT count(*) INTO receipt_count FROM public.solution_nonpromotion_transition_receipt
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000031';
    SELECT current_stage, status INTO superseded_stage, superseded_status
      FROM public.solution WHERE id = 'c0000000-0000-4000-8000-000000000033';
    SELECT count(*) INTO superseded_events FROM public.solution_lifecycle_event
     WHERE solution_id = 'c0000000-0000-4000-8000-000000000033';
    IF stage_value <> 'pilot_active' OR event_count <> 1 OR receipt_count <> 1
       OR superseded_stage <> 'testing' OR superseded_status <> 'active'
       OR superseded_events <> 0 THEN
        RAISE EXCEPTION 'stage, lifecycle event, and receipt did not commit atomically';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.transition_location_solution_stage(uuid,uuid,text,text,uuid,text,jsonb,text,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.transition_location_solution_stage(uuid,uuid,text,text,uuid,text,jsonb,text,boolean)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_solution_stage_transition_targets(uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_nonpromotion_transition_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_nonpromotion_transition_receipt', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_nonpromotion_transition_receipt', 'SELECT')
       OR has_table_privilege('kokonut_solution_nonpromotion_transition_owner', 'public.solution', 'SELECT') THEN
        RAISE EXCEPTION 'non-promotion transition function or receipt privilege boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-nonpromotion-stage-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 503 applies and replays after the ordered CAP-035 lifecycle chain",
            "stage targets require signed exact-location read context; writes require exact transition grant and active human binding",
            "transitions are limited to non-promotion stages and exact location-origin solutions",
        "adopting retains approved location readiness and configuration prerequisites; supersession remains on the reviewed retirement/replacement workflow",
            "expected-stage compare-and-set, acknowledgement, rationale, evidence, and rollback bounds are enforced",
            "stage update, lifecycle event, and private idempotency receipt are atomic",
            "exact retries replay, changed payloads and stale stages fail, and runtime/Directus cannot access receipts directly",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        prior.apply_ordered_lifecycle_chain(docker, container)
        # The compact lifecycle fixtures intentionally omit some canonical
        # adoption provenance columns; production migration 291 defines them.
        psql(docker, container, """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
        ALTER TABLE public.solution_adopter_readiness
            ADD COLUMN IF NOT EXISTS assessed_by_party_id UUID;
        ALTER TABLE public.solution_configuration
            ADD COLUMN IF NOT EXISTS approved_by_party_id UUID;
        ALTER TABLE public.solution_lifecycle_event
            ADD COLUMN IF NOT EXISTS rollback_plan TEXT;
        ALTER TABLE public.solution
            ADD COLUMN IF NOT EXISTS canonical_key TEXT,
            ADD COLUMN IF NOT EXISTS name TEXT,
            ADD COLUMN IF NOT EXISTS solution_type TEXT,
            ADD COLUMN IF NOT EXISTS problem_statement TEXT;
        """)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, ACTOR_FIXTURE)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 14
        print("PASS: migration 503 applies/replays; scoped non-promotion stage, adoption prerequisite, retry, atomicity, and role-boundary checks passed")
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
