#!/usr/bin/env python3
"""Exercise migration 494 with isolated solution-replication proposal fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING_CHECK = ROOT / "scripts/check-solution-learning-proposal-disposable.py"
MIGRATION = ROOT / "schemas/postgres/494_location_solution_replication_proposal.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-proposal-disposable.json"
spec = importlib.util.spec_from_file_location("solution_learning_proposal_disposable", LEARNING_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior disposable solution lifecycle fixtures")
learning_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learning_check)

gate_check = learning_check.gate_check
prior = learning_check.prior
retirement_check = learning_check.retirement_check
learning_proposal_check = learning_check.learning_check
replication_check = learning_check.replication_check
scale_check = learning_check.scale_check
adoption_check = learning_check.adoption_check
funding_check = learning_check.funding_check
experiment_check = learning_check.experiment_check
run = learning_check.run
psql = learning_check.psql
wait_ready = learning_check.wait_ready

SOURCE_FIXTURE = r"""
ALTER TABLE public.solution_experiment
    ADD COLUMN approved_by_party_id uuid;
UPDATE public.solution_experiment
   SET status = 'validated'
 WHERE id = 'f0000000-0000-4000-8000-000000000003';
UPDATE public.solution_experiment
   SET status = 'validated',
       owner_party_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
       approved_by_party_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
 WHERE id = 'f0000000-0000-4000-8000-000000000001';
UPDATE public.solution_experiment_result
   SET outcome = 'validated',
       reviewed_by_party_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
       reviewed_at = '2026-10-20 00:00:00+00'
 WHERE experiment_id = 'f0000000-0000-4000-8000-000000000001';
INSERT INTO public.solution_experiment
    (id, solution_id, status, owner_party_id, approved_by_party_id)
VALUES
    ('f0000000-0000-4000-8000-000000000004',
     'c0000000-0000-4000-8000-000000000002', 'validated',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
INSERT INTO public.solution_experiment_result
    (id, experiment_id, outcome, reviewed_by_party_id, reviewed_at)
VALUES
    ('f1000000-0000-4000-8000-000000000004',
     'f0000000-0000-4000-8000-000000000004', 'validated',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '2026-10-20 00:00:00+00');
"""

ACCEPTANCE = r"""
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
    same_location_result record;
    denied boolean;
BEGIN
    SELECT * INTO first_result
      FROM kokonut_security.propose_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000003',
        'ab940000-0000-4000-8000-000000000001',
        'Synthetic target context',
        'Synthetic local adaptation',
        '{"steps":["prepare","observe"]}'::jsonb
      );
    IF first_result.event_id IS NULL OR first_result.replication_id IS NULL
       OR first_result.replication_status <> 'proposed'
       OR first_result.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'validated reviewed source did not create a draft replication';
    END IF;

    SELECT * INTO replay_result
      FROM kokonut_security.propose_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000003',
        'ab940000-0000-4000-8000-000000000001',
        'Synthetic target context',
        'Synthetic local adaptation',
        '{"steps":["prepare","observe"]}'::jsonb
      );
    IF replay_result.event_id IS DISTINCT FROM first_result.event_id
       OR replay_result.replication_id IS DISTINCT FROM first_result.replication_id
       OR replay_result.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact retry did not return the original proposal receipt';
    END IF;

    SELECT * INTO same_location_result
      FROM kokonut_security.propose_location_solution_replication(
        'b0000000-0000-4000-8000-000000000001',
        'f0000000-0000-4000-8000-000000000001',
        'ab940000-0000-4000-8000-000000000009',
        'Separate block within the same farm', NULL, '{"steps":["observe"]}'::jsonb
      );
    IF same_location_result.event_id IS NULL
       OR same_location_result.replication_status <> 'proposed'
       OR same_location_result.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'same-location source with a distinct target context was rejected';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'ab940000-0000-4000-8000-000000000001',
            'Changed target context', 'Synthetic local adaptation',
            '{"steps":["prepare","observe"]}'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-input retry collision was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000002',
            'ab940000-0000-4000-8000-000000000003',
            'Synthetic target context', NULL, '{}'::jsonb
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'source without an exact target location link was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000004',
            'ab940000-0000-4000-8000-000000000007',
            'Synthetic target context', NULL, '{}'::jsonb
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'source result reviewed by its experiment owner was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'ab940000-0000-4000-8000-000000000004',
            'Synthetic target context', NULL, '[]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'non-object replication protocol was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'ab940000-0000-4000-8000-000000000005',
            'Synthetic target context', NULL, '{}'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without an exact create grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'ab940000-0000-4000-8000-000000000008',
            'Synthetic target context', NULL, '{}'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location context was accepted'; END IF;
    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000004', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication(
            'b0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000003',
            'ab940000-0000-4000-8000-000000000006',
            'Synthetic target context', NULL, '{}'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator bound to an inactive party was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_replication_proposal_receipt;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read proposal receipts'; END IF;
    denied := false;
    BEGIN PERFORM 1 FROM public.solution_replication;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read replication source rows'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    replication_record record;
    receipt_count integer;
BEGIN
    SELECT replication.*, receipt.id AS proposal_event_id
      INTO replication_record
      FROM public.solution_replication AS replication
      JOIN public.solution_replication_proposal_receipt AS receipt
        ON receipt.replication_id = replication.id
     WHERE receipt.operator_id = 'a0000000-0000-4000-8000-000000000003'
       AND receipt.request_id = 'ab940000-0000-4000-8000-000000000001';
    SELECT count(*) INTO receipt_count FROM public.solution_replication_proposal_receipt;
    IF receipt_count <> 2
       OR replication_record.proposal_event_id IS NULL
       OR replication_record.solution_id <> 'c0000000-0000-4000-8000-000000000002'
       OR replication_record.source_experiment_id <> 'f0000000-0000-4000-8000-000000000003'
       OR replication_record.target_scope_type <> 'location'
       OR replication_record.target_scope_id <> 'b0000000-0000-4000-8000-000000000001'
       OR replication_record.target_context <> 'Synthetic target context'
       OR replication_record.adaptation_required <> 'Synthetic local adaptation'
       OR replication_record.replication_protocol <> '{"steps":["prepare","observe"]}'::jsonb
       OR replication_record.status <> 'proposed'
       OR replication_record.result IS NOT NULL
       OR replication_record.evidence_maturity IS NOT NULL
       OR replication_record.reviewed_by_party_id IS NOT NULL
       OR replication_record.evidence <> '[]'::jsonb
       OR (SELECT current_stage FROM public.solution
            WHERE id = replication_record.solution_id) <> 'validated' THEN
        RAISE EXCEPTION 'proposal content, attribution, draft state, or unchanged lifecycle stage is incorrect';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.propose_location_solution_replication(uuid,uuid,uuid,text,text,jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.propose_location_solution_replication(uuid,uuid,uuid,text,text,jsonb)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication_proposal_receipt', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_replication', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_replication', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_replication', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.solution_replication_proposal_receipt', 'INSERT')
       OR has_table_privilege('kokonut_solution_replication_proposer', 'public.solution_replication_proposal_receipt', 'UPDATE')
       OR has_table_privilege('kokonut_solution_replication_proposer', 'public.solution_replication_proposal_receipt', 'DELETE')
       OR has_column_privilege('kokonut_solution_replication_proposer', 'public.solution_replication', 'status', 'UPDATE')
       OR has_column_privilege('kokonut_solution_replication_proposer', 'public.solution_replication', 'reviewed_by_party_id', 'UPDATE')
       OR NOT has_column_privilege('kokonut_solution_replication_proposer', 'public.solution_replication', 'target_context', 'INSERT')
       OR NOT has_column_privilege('kokonut_solution_replication_proposer', 'public.solution_replication', 'replication_protocol', 'INSERT') THEN
        RAISE EXCEPTION 'replication proposal privilege boundary failed';
    END IF;
    IF (SELECT owner.rolcanlogin OR owner.rolsuper OR owner.rolinherit OR owner.rolbypassrls
          FROM pg_catalog.pg_roles AS owner
         WHERE owner.rolname = 'kokonut_solution_replication_proposer') THEN
        RAISE EXCEPTION 'replication proposer role is not a constrained non-login role';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
        WHERE granted_role.rolname = 'kokonut_solution_replication_proposer'
           OR member_role.rolname = 'kokonut_solution_replication_proposer'
    ) THEN
        RAISE EXCEPTION 'replication proposer role has unexpected membership';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-replication-proposal-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "solution lifecycle migrations through 477 apply before migration 494, which replays",
            "active solutions visible by exact location origin or explicit location link can be proposed from a validated, independently reviewed experiment",
            "a distinct deployment context can be proposed within the source location",
            "signed operator location context, exact create grant, and active OIDC-to-person attribution are enforced",
            "proposal receipt is immutable and request-idempotent; changed-input retries fail closed",
            "proposal remains proposed without review, result, evidence, maturity, or lifecycle-stage mutation",
            "runtime can invoke only the bounded function and cannot read source or receipt rows; Directus cannot execute the function",
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
        replication_migration = replication_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, replication_migration)
        psql(docker, container, replication_migration)
        psql(docker, container, learning_proposal_check.LEARNING_SOURCE)
        learning_migration = learning_proposal_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, learning_migration)
        psql(docker, container, learning_migration)
        psql(docker, container, retirement_check.RETIREMENT_SOURCE)
        psql(docker, container, retirement_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.approval_check.REVIEW_FIXTURE)
        retirement_review = prior.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, retirement_review)
        psql(docker, container, prior.INDEPENDENT_REVIEW_ACCEPTANCE)
        psql(docker, container, learning_check.approval_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.RETIREMENT_PROPOSAL.read_text(encoding="utf-8"))
        proposal_migration = learning_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, proposal_migration)
        psql(docker, container, proposal_migration)
        psql(docker, container, learning_check.CREATE_GRANTS)
        psql(docker, container, learning_check.LEARNING_ACCEPTANCE)
        psql(docker, container, SOURCE_FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 9
        print("PASS: solution lifecycle migrations through 494 apply, migration 494 replays, and nine grouped PostgreSQL checks passed")
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
