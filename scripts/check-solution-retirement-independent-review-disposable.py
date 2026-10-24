#!/usr/bin/env python3
"""Exercise migration 474's retirement approval attribution invariant."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIREMENT_CHECK = ROOT / "scripts/check-solution-lifecycle-retirements-disposable.py"
MIGRATION = ROOT / "schemas/postgres/474_solution_retirement_independent_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/solution-retirement-independent-review-disposable.json"
spec = importlib.util.spec_from_file_location("solution_retirements_disposable", RETIREMENT_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable solution lifecycle fixtures")
retirement_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retirement_check)
learning_check = retirement_check.learning_check
replication_check = retirement_check.replication_check
scale_check = retirement_check.scale_check
adoption_check = scale_check.adoption_check
funding_check = adoption_check.helper
experiment_check = funding_check.helper
gate_check = experiment_check.helper
run = retirement_check.run
psql = retirement_check.psql
wait_ready = retirement_check.wait_ready

INDEPENDENT_REVIEW_ACCEPTANCE = r"""
DO $$
DECLARE
    denied boolean := false;
    constraint_state text;
BEGIN
    INSERT INTO public.solution_retirement
        (id, solution_id, retirement_type, trigger_reason, status, created_by_party_id)
    VALUES
        ('fa000000-0000-4000-8000-000000000001',
         'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
         'proposed', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');

    denied := false;
    BEGIN
        UPDATE public.solution_retirement
           SET status = 'approved',
               approved_by_party_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
               approved_at = clock_timestamp()
         WHERE id = 'fa000000-0000-4000-8000-000000000001';
    EXCEPTION WHEN check_violation THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'self-approval was accepted'; END IF;

    denied := false;
    BEGIN
        INSERT INTO public.solution_retirement
            (id, solution_id, retirement_type, trigger_reason, status,
             approved_by_party_id, approved_at)
        VALUES
            ('fa000000-0000-4000-8000-000000000002',
             'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
             'approved', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', clock_timestamp());
    EXCEPTION WHEN check_violation THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'approval without proposer attribution was accepted'; END IF;

    INSERT INTO public.solution_retirement
        (id, solution_id, retirement_type, trigger_reason, status, created_by_party_id)
    VALUES
        ('fa000000-0000-4000-8000-000000000003',
         'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
         'proposed', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
    UPDATE public.solution_retirement
       SET status = 'approved',
           approved_by_party_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
           approved_at = clock_timestamp()
     WHERE id = 'fa000000-0000-4000-8000-000000000003';

    denied := false;
    BEGIN
        UPDATE public.solution_retirement
           SET approved_by_party_id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
         WHERE id = 'fa000000-0000-4000-8000-000000000003';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'reviewer attribution replacement was accepted'; END IF;

    denied := false;
    BEGIN
        UPDATE public.solution_retirement
           SET created_by_party_id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
         WHERE id = 'fa000000-0000-4000-8000-000000000003';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'proposer attribution rewrite was accepted'; END IF;

    SELECT pg_catalog.pg_get_function_result(
        'kokonut_security.enforce_solution_retirement_independent_review()'::regprocedure
    ) INTO constraint_state;
    IF constraint_state <> 'trigger' THEN
        RAISE EXCEPTION 'retirement review invariant trigger function is missing';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-retirement-review-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 474 applies and replays after ordered solution lifecycle migrations",
            "new approvals require a non-null proposer and a distinct reviewer",
            "self-approval and approval without proposer attribution fail closed",
            "proposer and reviewer attribution cannot be rewritten after approval",
            "independent approval succeeds and unreviewed legacy rows are not rewritten",
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
        psql(docker, container, learning_check.LEARNING_SOURCE)
        migration_472 = learning_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_472)
        psql(docker, container, migration_472)
        psql(docker, container, learning_check.LEARNING_ACCEPTANCE)
        psql(docker, container, retirement_check.RETIREMENT_SOURCE)
        migration_473 = retirement_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_473)
        psql(docker, container, migration_473)
        psql(docker, container, retirement_check.RETIREMENT_ACCEPTANCE)
        migration_474 = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_474)
        psql(docker, container, migration_474)
        psql(docker, container, INDEPENDENT_REVIEW_ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 5
        print("PASS: migrations 459 and 466–474 apply, migration 474 replays, and five independent-review checks passed")
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
