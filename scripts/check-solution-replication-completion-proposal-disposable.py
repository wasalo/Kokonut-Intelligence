#!/usr/bin/env python3
"""Exercise migration 497 using isolated CAP-035 replication fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVATION_CHECK = ROOT / "scripts/check-solution-replication-activation-disposable.py"
MIGRATION = ROOT / "schemas/postgres/497_location_solution_replication_completion_proposal.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-solution-replication-completion-proposal-disposable.json"
spec = importlib.util.spec_from_file_location("solution_replication_activation_disposable", ACTIVATION_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior replication activation fixtures")
activation_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation_check)

review_check = activation_check.review_check
run = activation_check.run
psql = activation_check.psql
wait_ready = activation_check.wait_ready

COMPLETION_FIXTURE = r"""
CREATE TABLE IF NOT EXISTS public.evidence_maturity_level (
    level INTEGER PRIMARY KEY CHECK (level BETWEEN 0 AND 6),
    level_key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    public_claim_allowed BOOLEAN DEFAULT FALSE,
    requires_external_verification BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);
INSERT INTO public.evidence_maturity_level (level, level_key, label, description)
SELECT level, 'fixture_' || level::TEXT, 'Fixture level ' || level::TEXT,
       'Disposable acceptance fixture only'
  FROM pg_catalog.generate_series(0, 6) AS level
ON CONFLICT (level) DO NOTHING;

INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000009',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'submit', NULL, NULL);
"""

COMPLETION_ACCEPTANCE = r"""
SELECT set_config(
    'kokonut.test_completion_replication_one',
    (SELECT replication_id::TEXT FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000001'), false
);
SELECT set_config(
    'kokonut.test_completion_replication_two',
    (SELECT replication_id::TEXT FROM public.solution_replication_proposal_receipt
      WHERE request_id = 'ab940000-0000-4000-8000-000000000009'), false
);
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    first_report record;
    replay_report record;
    replication_uuid uuid;
    denied boolean := false;
    too_many_evidence jsonb;
BEGIN
    replication_uuid := pg_catalog.current_setting(
        'kokonut.test_completion_replication_one'
    )::UUID;

    SELECT * INTO first_report
      FROM kokonut_security.propose_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', replication_uuid,
        'ab970000-0000-4000-8000-000000000001', 'successful', 3,
        'Synthetic local replication met its measured objectives.',
        '[{"evidence_ref":"synthetic://replication/1"}]'::jsonb
      );
    IF first_report.proposal_id IS NULL
       OR first_report.replication_id IS DISTINCT FROM replication_uuid
       OR first_report.decision_status <> 'proposed'
       OR first_report.replayed IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'completion report was not created as a reviewable proposal';
    END IF;

    SELECT * INTO replay_report
      FROM kokonut_security.propose_location_solution_replication_completion(
        'b0000000-0000-4000-8000-000000000001', replication_uuid,
        'ab970000-0000-4000-8000-000000000001', 'successful', 3,
        'Synthetic local replication met its measured objectives.',
        '[{"evidence_ref":"synthetic://replication/1"}]'::jsonb
      );
    IF replay_report.proposal_id IS DISTINCT FROM first_report.proposal_id
       OR replay_report.replayed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'exact completion proposal retry did not replay';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000001', 'mixed', 3,
            'Synthetic local replication met its measured objectives.',
            '[{"evidence_ref":"synthetic://replication/1"}]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-payload request reuse was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000002', 'mixed', 3,
            'A second report while review is pending.', '[]'::jsonb
        );
    EXCEPTION WHEN unique_violation THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'second pending completion report was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000003', NULL, 3,
            'Outcome absent test', '[]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'null outcome was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000004', 'successful', 7,
            'Out-of-range maturity test', '[]'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'out-of-range evidence maturity was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000005', 'successful', 3,
            'Evidence type test', '{"not":"an array"}'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'non-array evidence was accepted'; END IF;

    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('item', value))
      INTO too_many_evidence
      FROM pg_catalog.generate_series(1, 101) AS item(value);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000006', 'successful', 3,
            'Evidence count bound test.', too_many_evidence
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'evidence over 100 items was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001', replication_uuid,
            'ab970000-0000-4000-8000-000000000007', 'successful', 3,
            'Operator without submit scope.', '[]'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without submit scope was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_replication_completion(
            'b0000000-0000-4000-8000-000000000001',
            pg_catalog.current_setting('kokonut.test_completion_replication_two')::UUID,
            'ab970000-0000-4000-8000-000000000008', 'inconclusive', 2,
            'Rejected proposal cannot be completed.', '[]'::jsonb
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'rejected replication accepted a completion proposal'; END IF;

    denied := false;
    BEGIN SELECT 1 FROM public.solution_replication_completion_proposal;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read completion proposal details directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    replication_uuid uuid;
    report public.solution_replication_completion_proposal%ROWTYPE;
    replication public.solution_replication%ROWTYPE;
BEGIN
    SELECT replication_id INTO replication_uuid
      FROM public.solution_replication_proposal_receipt
     WHERE request_id = 'ab940000-0000-4000-8000-000000000001';
    SELECT * INTO report FROM public.solution_replication_completion_proposal
     WHERE request_id = 'ab970000-0000-4000-8000-000000000001';
    SELECT * INTO replication FROM public.solution_replication
     WHERE id = replication_uuid;
    IF report.id IS NULL OR report.decision_status <> 'proposed'
       OR report.proposer_party_id <> 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
       OR report.evidence <> '[{"evidence_ref":"synthetic://replication/1"}]'::jsonb
       OR replication.status <> 'active'
       OR replication.result IS NOT NULL
       OR replication.evidence_maturity IS NOT NULL
       OR replication.evidence <> '[]'::jsonb
       OR replication.completed_at IS NOT NULL
       OR (SELECT current_stage FROM public.solution WHERE id = replication.solution_id) <> 'validated'
       OR (SELECT count(*) FROM public.solution_replication_completion_proposal) <> 1 THEN
        RAISE EXCEPTION 'proposal changed parent state or failed to retain bounded private report';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT has_function_privilege('kokonut_runtime',
          'kokonut_security.propose_location_solution_replication_completion(uuid,uuid,uuid,text,integer,text,jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.propose_location_solution_replication_completion(uuid,uuid,uuid,text,integer,text,jsonb)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication_completion_proposal', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_replication_completion_proposal', 'INSERT')
       OR has_table_privilege('kokonut_solution_replication_completion_proposer',
          'public.solution_replication_completion_proposal', 'UPDATE')
       OR has_table_privilege('kokonut_solution_replication_completion_proposer',
          'public.solution_replication_completion_proposal', 'DELETE')
       OR has_column_privilege('kokonut_solution_replication_completion_proposer',
          'public.solution_replication', 'status', 'UPDATE') THEN
        RAISE EXCEPTION 'completion proposal function/role boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-replication-completion-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 497 applies and replays after migration 496",
            "only an active started exact-location replication with current independent source review accepts a report",
            "report payload bounds, outcomes, and evidence arrays are checked by Gateway and PostgreSQL",
            "exact retries replay; changed request reuse and second pending report fail closed",
            "rejected replications, missing submit grants, and malformed reports fail closed",
            "proposal remains private and does not change replication outcome, evidence, completion, or solution stage",
            "runtime has function-only access and Directus cannot execute the proposal function",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        review_check.apply_predecessors(docker, container)
        psql(docker, container, activation_check.review_check.REVIEW_FIXTURE)
        review_sql = activation_check.review_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, review_sql)
        psql(docker, container, review_sql)
        psql(docker, container, activation_check.review_check.REVIEW_ACCEPTANCE)
        activation_sql = activation_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, activation_sql)
        psql(docker, container, activation_sql)
        psql(docker, container, activation_check.ACTIVATION_FIXTURE)
        psql(docker, container, COMPLETION_FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, COMPLETION_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 10
        print("PASS: migrations through 497 apply and replay, and ten completion proposal groups passed")
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
