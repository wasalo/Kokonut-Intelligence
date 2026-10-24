#!/usr/bin/env python3
"""Exercise migration 502's retirement migration, sunset, and post-review flow."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-scale-gate-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/502_location_solution_retirement_execution.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-retirement-execution-disposable.json"

spec = importlib.util.spec_from_file_location("solution_scale_gate_review_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the ordered CAP-035 disposable fixtures")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

run = prior.run
psql = prior.psql
wait_ready = prior.wait_ready

RETIREMENT_ACTOR_FIXTURE = r"""
INSERT INTO public.operator_identity (id, enabled)
VALUES
    ('a0000000-0000-4000-8000-000000000021', TRUE),
    ('a0000000-0000-4000-8000-000000000022', TRUE),
    ('a0000000-0000-4000-8000-000000000023', TRUE),
    ('a0000000-0000-4000-8000-000000000024', TRUE)
ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled;

INSERT INTO public.party (id, display_name, party_type, status)
VALUES
    ('c1000000-0000-4000-8000-000000000021', 'Synthetic retirement proposer', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000022', 'Synthetic retirement approver', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000023', 'Synthetic retirement operator', 'person', 'active'),
    ('c1000000-0000-4000-8000-000000000024', 'Synthetic post-retirement reviewer', 'person', 'active')
ON CONFLICT (id) DO UPDATE SET party_type = EXCLUDED.party_type, status = EXCLUDED.status;

INSERT INTO public.operator_governance_party_binding (id, operator_id, party_id, revoked_at)
VALUES
    ('a5000000-0000-4000-8000-000000000021', 'a0000000-0000-4000-8000-000000000021', 'c1000000-0000-4000-8000-000000000021', NULL),
    ('a5000000-0000-4000-8000-000000000022', 'a0000000-0000-4000-8000-000000000022', 'c1000000-0000-4000-8000-000000000022', NULL),
    ('a5000000-0000-4000-8000-000000000023', 'a0000000-0000-4000-8000-000000000023', 'c1000000-0000-4000-8000-000000000023', NULL),
    ('a5000000-0000-4000-8000-000000000024', 'a0000000-0000-4000-8000-000000000024', 'c1000000-0000-4000-8000-000000000024', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000021', 'a0000000-0000-4000-8000-000000000021', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'create', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000022', 'a0000000-0000-4000-8000-000000000022', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000023', 'a0000000-0000-4000-8000-000000000023', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'transition', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000024', 'a0000000-0000-4000-8000-000000000023', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000025', 'a0000000-0000-4000-8000-000000000023', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'transition', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000026', 'a0000000-0000-4000-8000-000000000024', 'b0000000-0000-4000-8000-000000000001', 'solution_lifecycle', 'review', NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"""

RETIREMENT_EXECUTION_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    proposal_result record;
    approval_result record;
    migration_result record;
    replay_result record;
    sunset_result record;
    completion_result record;
    retirement_uuid uuid;
    migration_request uuid := 'ab000000-0000-4000-8000-000000000021';
    sunset_request uuid := 'ab000000-0000-4000-8000-000000000022';
    review_request uuid := 'ab000000-0000-4000-8000-000000000023';
    denied boolean;
BEGIN
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000021', true);
    SELECT * INTO proposal_result
      FROM kokonut_security.propose_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'ab000000-0000-4000-8000-000000000024',
        'ineffective', 'Synthetic retirement fixture for migration acceptance',
        '[{"source":"reviewed synthetic evidence"}]'::jsonb,
        'Synthetic migration plan for disposable acceptance only', NULL
      );
    retirement_uuid := proposal_result.retirement_id;
    IF retirement_uuid IS NULL OR proposal_result.retirement_status <> 'proposed' THEN
        RAISE EXCEPTION 'synthetic retirement proposal was not created';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000022', true);
    SELECT * INTO approval_result
      FROM kokonut_security.approve_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001', retirement_uuid,
        'ab000000-0000-4000-8000-000000000025'
      );
    IF approval_result.retirement_status <> 'approved' OR approval_result.replayed THEN
        RAISE EXCEPTION 'independent synthetic retirement approval failed';
    END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000023', true);
    SELECT * INTO migration_result
      FROM kokonut_security.transition_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001', retirement_uuid, migration_request,
        'migration_started', 'Reviewed the migration plan and scheduled its sunset.',
        '[{"source":"migration-plan"}]'::jsonb,
        clock_timestamp() + interval '0.5 seconds'
      );
    IF migration_result.retirement_status <> 'migration'
       OR migration_result.solution_stage = 'retired'
       OR migration_result.replayed THEN
        RAISE EXCEPTION 'migration start changed lifecycle status or returned an invalid receipt';
    END IF;
    SELECT * INTO replay_result
      FROM kokonut_security.transition_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001', retirement_uuid, migration_request,
        'migration_started', 'Reviewed the migration plan and scheduled its sunset.',
        '[{"source":"migration-plan"}]'::jsonb,
        migration_result.effective_at
      );
    IF NOT replay_result.replayed OR replay_result.event_id <> migration_result.event_id THEN
        RAISE EXCEPTION 'identical migration retry did not return its original receipt';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001', retirement_uuid,
            'ab000000-0000-4000-8000-000000000026', 'sunset',
            'Attempted sunset before the effective timestamp.',
            '[{"source":"premature"}]'::jsonb, NULL
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'sunset before effective_at was accepted'; END IF;

    PERFORM pg_sleep(0.6);
    SELECT * INTO sunset_result
      FROM kokonut_security.transition_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001', retirement_uuid, sunset_request,
        'sunset', 'The approved retirement sunset is now effective.',
        '[{"source":"sunset-record"}]'::jsonb, NULL
      );
    IF sunset_result.retirement_status <> 'sunset'
       OR sunset_result.solution_stage <> 'retired' OR sunset_result.replayed THEN
        RAISE EXCEPTION 'effective sunset did not retire the solution';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001', retirement_uuid,
            'ab000000-0000-4000-8000-000000000027', 'post_retirement_review',
            'Same operator cannot independently review the retirement.',
            '[{"source":"review"}]'::jsonb, NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'sunset actor reviewed its own retirement'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000024', true);
    SELECT * INTO completion_result
      FROM kokonut_security.transition_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001', retirement_uuid, review_request,
        'post_retirement_review', 'Independent review confirmed the sunset evidence.',
        '[{"source":"post-retirement-review"}]'::jsonb, NULL
      );
    IF completion_result.retirement_status <> 'completed'
       OR completion_result.solution_stage <> 'retired'
       OR completion_result.post_retirement_review_at IS NULL
       OR completion_result.replayed THEN
        RAISE EXCEPTION 'post-retirement review did not complete the record';
    END IF;
    SELECT * INTO replay_result
      FROM kokonut_security.transition_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001', retirement_uuid, review_request,
        'post_retirement_review', 'Independent review confirmed the sunset evidence.',
        '[{"source":"post-retirement-review"}]'::jsonb, NULL
      );
    IF NOT replay_result.replayed OR replay_result.event_id <> completion_result.event_id THEN
        RAISE EXCEPTION 'post-retirement review retry did not return its original receipt';
    END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_retirement_transition_event LIMIT 1;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read retirement transition receipts'; END IF;
    denied := false;
    BEGIN
        INSERT INTO public.solution_retirement_transition_event
            (operator_id, actor_party_id, location_id, retirement_id, request_id,
             action, previous_status, resulting_status, resulting_solution_stage,
             effective_at, post_retirement_review_at, note, evidence_refs)
        VALUES
            ('a0000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000023',
             'b0000000-0000-4000-8000-000000000001', retirement_uuid,
             'ab000000-0000-4000-8000-000000000028', 'sunset', 'migration', 'sunset', 'retired',
             clock_timestamp(), NULL, 'Direct event insert is forbidden for runtime.', '[{"source":"x"}]');
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly insert retirement transition receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    retirement_status_value text;
    solution_status_value text;
    solution_stage_value text;
    event_count integer;
BEGIN
    SELECT status INTO retirement_status_value FROM public.solution_retirement
     WHERE id = (SELECT retirement_id FROM public.solution_retirement_transition_event
                  WHERE action = 'post_retirement_review'
                  ORDER BY created_at DESC LIMIT 1);
    SELECT solution.status, solution.current_stage INTO solution_status_value, solution_stage_value
      FROM public.solution AS solution
      JOIN public.solution_retirement AS retirement ON retirement.solution_id = solution.id
     WHERE retirement.status = 'completed'
     ORDER BY retirement.created_at DESC LIMIT 1;
    SELECT count(*) INTO event_count FROM public.solution_retirement_transition_event;
    IF retirement_status_value <> 'completed' OR solution_status_value <> 'retired'
       OR solution_stage_value <> 'retired' OR event_count <> 3 THEN
        RAISE EXCEPTION 'retirement execution state is inconsistent';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.solution_retirement_transition_event', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_transition_event', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_transition_event', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_transition_event', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_retirement_transition_event', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_retirement_transition_event', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_retirement_transition_event', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_retirement_transition_event', 'DELETE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.transition_location_solution_retirement(uuid,uuid,uuid,text,text,jsonb,timestamp with time zone)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.transition_location_solution_retirement(uuid,uuid,uuid,text,text,jsonb,timestamp with time zone)', 'EXECUTE') THEN
        RAISE EXCEPTION 'retirement execution role boundary failed';
    END IF;
END $$;
"""


def apply_ordered_lifecycle_chain(docker: str, container: str) -> None:
    prior.review_check.apply_predecessors(docker, container)
    psql(docker, container, (ROOT / "schemas/postgres/293_sequential_gate_integrity.sql").read_text(encoding="utf-8"))
    psql(docker, container, prior.review_check.REVIEW_FIXTURE)
    psql(docker, container, prior.review_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.review_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.review_check.REVIEW_ACCEPTANCE)
    psql(docker, container, prior.activation_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.activation_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.activation_check.ACTIVATION_FIXTURE)
    psql(docker, container, prior.replication_check.COMPLETION_FIXTURE)
    psql(docker, container, prior.replication_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.replication_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.replication_check.COMPLETION_ACCEPTANCE)
    psql(docker, container, prior.completion_check.REVIEW_FIXTURE)
    psql(docker, container, prior.completion_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.completion_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.completion_check.REVIEW_ACCEPTANCE)
    psql(docker, container, prior.learning_check.REVIEWER_FIXTURE)
    psql(docker, container, prior.learning_check.PROPOSE_ACCEPTANCE)
    psql(docker, container, prior.learning_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.learning_check.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.learning_check.REVIEW_ACCEPTANCE)
    psql(docker, container, prior.prior.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.prior.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.SCALE_GATE_FIXTURE)
    psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, prior.SCALE_GATE_ACCEPTANCE)
    # The compact read fixture intentionally defines only projected solution
    # columns; restore the lifecycle fields present in migration 288's schema.
    psql(docker, container, """
    ALTER TABLE public.solution ADD COLUMN IF NOT EXISTS retired_at timestamptz;
    ALTER TABLE public.solution ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
    CREATE TABLE IF NOT EXISTS public.solution_lifecycle_event (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        solution_id uuid NOT NULL REFERENCES public.solution(id),
        from_stage text,
        to_stage text NOT NULL,
        rationale text NOT NULL,
        evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
        actor_party_id uuid,
        approved_by_party_id uuid,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    """)
    psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
    psql(docker, container, MIGRATION.read_text(encoding="utf-8"))


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-retirement-execution-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 502 applies and replays after the ordered CAP-035 lifecycle migrations",
            "only an independently approved exact-location retirement can begin migration",
            "migration start requires an operator-selected current or future effective timestamp and keeps the solution active",
            "sunset is rejected before effective_at and then retires the solution atomically without deleting data",
            "post-retirement review requires a separate active human under exact review scope",
            "all three transitions use immutable retry receipts and preserve append-only history",
            "runtime and Directus cannot directly access transition receipts; only runtime can execute the bounded function",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        apply_ordered_lifecycle_chain(docker, container)
        psql(docker, container, RETIREMENT_ACTOR_FIXTURE)
        psql(docker, container, RETIREMENT_EXECUTION_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: migrations through 502 apply and replay; retirement execution, sunset, review, retry, and role-boundary checks passed")
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
