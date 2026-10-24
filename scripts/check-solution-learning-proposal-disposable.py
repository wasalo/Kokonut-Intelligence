#!/usr/bin/env python3
"""Exercise migration 477 with isolated location-learning proposal fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_CHECK = ROOT / "scripts/check-solution-retirement-approval-disposable.py"
RETIREMENT_PROPOSAL = ROOT / "schemas/postgres/476_location_solution_retirement_proposal.sql"
MIGRATION = ROOT / "schemas/postgres/477_location_solution_learning_proposal.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-035-solution-learning-proposal-disposable.json"
spec = importlib.util.spec_from_file_location("solution_retirement_approval_disposable", APPROVAL_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior disposable solution lifecycle fixtures")
approval_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval_check)

prior = approval_check.prior
retirement_check = approval_check.retirement_check
learning_check = approval_check.learning_check
replication_check = approval_check.replication_check
scale_check = approval_check.scale_check
adoption_check = approval_check.adoption_check
funding_check = approval_check.funding_check
experiment_check = approval_check.experiment_check
gate_check = approval_check.gate_check
run = approval_check.run
psql = approval_check.psql
wait_ready = approval_check.wait_ready

CREATE_GRANTS = r"""
INSERT INTO public.operator_governance_party_binding
    (id, operator_id, party_id, revoked_at)
VALUES
    ('a5000000-0000-4000-8000-000000000003',
     'a0000000-0000-4000-8000-000000000003',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', NULL);
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000004',
     'a0000000-0000-4000-8000-000000000003',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000005',
     'a0000000-0000-4000-8000-000000000004',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', NULL, NULL);

UPDATE public.party
   SET status = 'inactive'
 WHERE id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';

INSERT INTO public.solution_replication
    (id, solution_id, status, source_experiment_id, target_scope_type,
     target_scope_id, target_context, context_similarity, adaptation_required,
     replication_protocol, result, evidence_maturity, reviewed_by_party_id,
     evidence, created_at, completed_at)
VALUES
    ('e2000000-0000-4000-8000-000000000007',
     'c0000000-0000-4000-8000-000000000001', 'completed',
     'f0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'inactive reviewer fixture',
     0.875, 'private adaptation', '{"private": true}', 'successful', 3,
     'cccccccc-cccc-4ccc-8ccc-cccccccccccc', '[{"private": true}]',
     '2026-10-16 00:00:00+00', '2026-10-19 00:00:00+00'),
    ('e2000000-0000-4000-8000-000000000008',
     'c0000000-0000-4000-8000-000000000004', 'completed',
     'f0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'unlinked solution fixture',
     0.875, 'private adaptation', '{"private": true}', 'successful', 3,
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '[{"private": true}]',
     '2026-10-17 00:00:00+00', '2026-10-19 00:00:00+00'),
    ('e2000000-0000-4000-8000-000000000009',
     'c0000000-0000-4000-8000-000000000001', 'completed',
     'f0000000-0000-4000-8000-000000000001', 'location',
     'b0000000-0000-4000-8000-000000000001', 'unreviewed fixture',
     0.875, 'private adaptation', '{"private": true}', 'successful', 3,
     NULL, '[{"private": true}]',
     '2026-10-18 00:00:00+00', '2026-10-19 00:00:00+00');
"""

LEARNING_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    first_result record;
    replay_result record;
    denied boolean;
    event_number integer;
BEGIN
    SELECT * INTO first_result
      FROM kokonut_security.propose_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001',
        'e2000000-0000-4000-8000-000000000001',
        'ab770000-0000-4000-8000-000000000001',
        'context_transfer',
        'A bounded synthetic learning finding',
        'moderate', 'unknown',
        '[{"assumption_id":"a1"}]', '[{"metric_id":"m1"}]',
        'A bounded synthetic next action', '[{"type":"replication","id":"e2000000-0000-4000-8000-000000000001"}]'
      );
    IF first_result.event_id IS NULL OR first_result.learning_record_id IS NULL
       OR first_result.learning_status <> 'proposed'
       OR first_result.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'valid reviewed location learning proposal was not created';
    END IF;

    SELECT * INTO replay_result
      FROM kokonut_security.propose_location_solution_learning(
        'b0000000-0000-4000-8000-000000000001',
        'e2000000-0000-4000-8000-000000000001',
        'ab770000-0000-4000-8000-000000000001',
        'context_transfer',
        'A bounded synthetic learning finding',
        'moderate', 'unknown',
        '[{"assumption_id":"a1"}]', '[{"metric_id":"m1"}]',
        'A bounded synthetic next action', '[{"type":"replication","id":"e2000000-0000-4000-8000-000000000001"}]'
      );
    IF replay_result.event_id IS DISTINCT FROM first_result.event_id
       OR replay_result.learning_record_id IS DISTINCT FROM first_result.learning_record_id
       OR replay_result.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact retry did not return the original proposal receipt';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000001',
            'context_transfer', 'changed finding', 'moderate', 'unknown',
            '[{"assumption_id":"a1"}]', '[{"metric_id":"m1"}]',
            'A bounded synthetic next action', '[{"type":"replication","id":"e2000000-0000-4000-8000-000000000001"}]'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'request id reuse with changed input was accepted'; END IF;

    FOREACH event_number IN ARRAY ARRAY[2, 3, 4, 5, 6, 7, 8, 9] LOOP
        denied := false;
        BEGIN
            PERFORM * FROM kokonut_security.propose_location_solution_learning(
                'b0000000-0000-4000-8000-000000000001',
                ('e2000000-0000-4000-8000-' || pg_catalog.lpad(event_number::text, 12, '0'))::uuid,
                ('ab770000-0000-4000-8000-' || pg_catalog.lpad((event_number + 10)::text, 12, '0'))::uuid,
                'context_transfer', 'A bounded synthetic learning finding',
                'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[{"ref":"synthetic"}]'
            );
        EXCEPTION WHEN no_data_found THEN denied := true; END;
        IF NOT denied THEN
            RAISE EXCEPTION 'replication fixture % was not rejected unless exactly completed/reviewed/location scoped', event_number;
        END IF;
    END LOOP;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000030',
            'unbounded_type', 'A bounded synthetic learning finding',
            'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[{"ref":"synthetic"}]'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'unknown lesson type was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000031',
            'context_transfer', pg_catalog.repeat('x', 4001),
            'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[{"ref":"synthetic"}]'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'oversized learning finding was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000032',
            'context_transfer', 'A bounded synthetic learning finding',
            'moderate', 'unknown', '{"not":"an array"}', '[]',
            'A bounded synthetic next action', '[{"ref":"synthetic"}]'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'non-array learning references were accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000033',
            'context_transfer', 'A bounded synthetic learning finding',
            'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[]'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'empty proposal evidence was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000002',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000020',
            'context_transfer', 'A bounded synthetic learning finding',
            'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[{"ref":"synthetic"}]'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000021',
            'context_transfer', 'A bounded synthetic learning finding',
            'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[{"ref":"synthetic"}]'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without an exact create grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000004', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_learning(
            'b0000000-0000-4000-8000-000000000001',
            'e2000000-0000-4000-8000-000000000001',
            'ab770000-0000-4000-8000-000000000022',
            'context_transfer', 'A bounded synthetic learning finding',
            'moderate', 'unknown', '[]', '[]', 'A bounded synthetic next action', '[{"ref":"synthetic"}]'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator bound to an inactive party was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_learning_record;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read learning records'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_learning_proposal_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read learning proposal receipts'; END IF;
    denied := false;
    BEGIN
        INSERT INTO public.solution_learning_proposal_event
            (operator_id, proposer_party_id, location_id, replication_id,
             learning_record_id, request_id)
        VALUES
            ('a0000000-0000-4000-8000-000000000003',
             'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
             'b0000000-0000-4000-8000-000000000001',
             'e2000000-0000-4000-8000-000000000001',
             first_result.learning_record_id,
             'ab770000-0000-4000-8000-000000000023');
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly insert a learning proposal receipt'; END IF;

END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE record_id uuid; event_count integer; learning_row record; total_events integer;
BEGIN
    SELECT proposal.learning_record_id, count(*)
      INTO record_id, event_count
      FROM public.solution_learning_proposal_event AS proposal
     WHERE proposal.request_id = 'ab770000-0000-4000-8000-000000000001'
     GROUP BY proposal.learning_record_id;
    SELECT * INTO learning_row FROM public.solution_learning_record WHERE id = record_id;
    SELECT count(*) INTO total_events FROM public.solution_learning_proposal_event;
    IF COALESCE(event_count, 0) <> 1 OR total_events <> 1
       OR learning_row.solution_id <> 'c0000000-0000-4000-8000-000000000001'
       OR learning_row.source_replication_id <> 'e2000000-0000-4000-8000-000000000001'
       OR learning_row.lesson_type <> 'context_transfer'
       OR learning_row.decision_status <> 'proposed'
       OR learning_row.owner_party_id IS NOT NULL THEN
        RAISE EXCEPTION 'proposal content, source linkage, draft state, or identity separation is incorrect';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.propose_location_solution_learning(uuid,uuid,uuid,text,text,text,text,jsonb,jsonb,text,jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.propose_location_solution_learning(uuid,uuid,uuid,text,text,text,text,jsonb,jsonb,text,jsonb)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_learning_record', 'SELECT')
       OR has_column_privilege('kokonut_runtime', 'public.solution_learning_record', 'finding', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_learning_record', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_learning_proposal_event', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_learning_proposal_event', 'INSERT')
       OR has_table_privilege('kokonut_solution_learning_proposal_owner', 'public.solution_learning_proposal_event', 'UPDATE')
       OR has_table_privilege('kokonut_solution_learning_proposal_owner', 'public.solution_learning_proposal_event', 'DELETE')
       OR has_column_privilege('kokonut_solution_learning_proposal_owner', 'public.solution_learning_record', 'finding', 'UPDATE')
       OR has_column_privilege('kokonut_solution_learning_proposal_owner', 'public.solution_learning_record', 'decision_status', 'UPDATE')
       OR NOT has_column_privilege('kokonut_solution_learning_proposal_owner', 'public.solution_learning_record', 'finding', 'INSERT') THEN
        RAISE EXCEPTION 'learning proposal privilege boundary failed';
    END IF;
    IF (SELECT owner.rolcanlogin OR owner.rolsuper OR owner.rolinherit OR owner.rolbypassrls
          FROM pg_catalog.pg_roles AS owner
         WHERE owner.rolname = 'kokonut_solution_learning_proposal_owner') THEN
        RAISE EXCEPTION 'learning proposal owner role is not a constrained non-login role';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
        WHERE granted_role.rolname = 'kokonut_solution_learning_proposal_owner'
           OR member_role.rolname = 'kokonut_solution_learning_proposal_owner'
    ) THEN
        RAISE EXCEPTION 'learning proposal owner role has unexpected membership';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-learning-proposal-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "solution lifecycle schema through migration 476 and learning proposal migration 477 apply; migration 477 replays",
            "only completed, actively reviewed replications targeting exact location lineage can seed a learning proposal",
            "signed operator location context, exact create grant, and active OIDC-to-person attribution are required",
            "proposal and append-only receipt are atomic, draft-only, and request-idempotent",
            "cross-location, network, unlinked, unreviewed, inactive-reviewer, and non-completed sources fail closed",
            "runtime can invoke the bounded function but cannot access learning records or receipts directly; Directus cannot invoke it",
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
        psql(docker, container, learning_check.LEARNING_SOURCE)
        migration_472 = learning_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_472)
        psql(docker, container, retirement_check.RETIREMENT_SOURCE)
        migration_473 = retirement_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_473)
        psql(docker, container, approval_check.REVIEW_FIXTURE)
        migration_474 = prior.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_474)
        psql(docker, container, prior.INDEPENDENT_REVIEW_ACCEPTANCE)
        migration_475 = approval_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_475)
        psql(docker, container, RETIREMENT_PROPOSAL.read_text(encoding="utf-8"))
        psql(docker, container, migration_477 := MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, migration_477)
        psql(docker, container, CREATE_GRANTS)
        psql(docker, container, LEARNING_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: solution lifecycle migrations through 477 apply, migration 477 replays, and nine acceptance groups passed")
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
