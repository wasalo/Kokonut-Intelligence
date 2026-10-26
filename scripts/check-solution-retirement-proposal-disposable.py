#!/usr/bin/env python3
"""Exercise migration 476's location-scoped retirement proposal workflow."""

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
MIGRATION = ROOT / "schemas/postgres/476_location_solution_retirement_proposal.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/solution-retirement-proposal-disposable.json"
spec = importlib.util.spec_from_file_location("solution_retirement_proposal_disposable", APPROVAL_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior disposable retirement fixtures")
approval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval)
wait_ready = approval.retirement_check.wait_ready


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} {command[1]}: {details}")
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )

PROPOSAL_FIXTURE = r"""
INSERT INTO public.party (id, display_name, party_type, status)
VALUES ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'Synthetic proposer', 'person', 'active');
INSERT INTO public.operator_identity (id, enabled)
VALUES ('a0000000-0000-4000-8000-000000000005', true);
INSERT INTO public.operator_governance_party_binding
    (id, operator_id, party_id, revoked_at)
VALUES
    ('a5000000-0000-4000-8000-000000000005',
     'a0000000-0000-4000-8000-000000000005',
     'dddddddd-dddd-4ddd-8ddd-dddddddddddd', NULL);
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000005',
     'a0000000-0000-4000-8000-000000000005',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000006',
     'a0000000-0000-4000-8000-000000000003',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000007',
     'a0000000-0000-4000-8000-000000000004',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'create', NULL, NULL);
"""

PROPOSAL_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    result record;
    event_id UUID;
    retirement_id UUID;
    denied BOOLEAN;
BEGIN
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000005', true);

    SELECT * INTO result FROM kokonut_security.propose_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'ab100000-0000-4000-8000-000000000001',
        'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
        'private migration plan', NULL
    );
    IF result.retirement_status <> 'proposed' OR result.replayed
       OR result.event_id IS NULL OR result.retirement_id IS NULL
       OR result.created_at IS NULL THEN
        RAISE EXCEPTION 'proposal did not return a fresh bounded receipt';
    END IF;
    event_id := result.event_id;
    retirement_id := result.retirement_id;

    SELECT * INTO result FROM kokonut_security.propose_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'ab100000-0000-4000-8000-000000000001',
        'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
        'private migration plan', NULL
    );
    IF NOT result.replayed OR result.event_id <> event_id
       OR result.retirement_id <> retirement_id THEN
        RAISE EXCEPTION 'identical retry did not return original proposal receipt';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000001',
            'ineffective', 'changed trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'proposal request id collision with changed input was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002',
            'ab100000-0000-4000-8000-000000000002',
            'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN no_data_found THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'shared link-only solution was eligible for a location proposal'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000003',
            'ab100000-0000-4000-8000-000000000003',
            'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN no_data_found THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location solution was eligible for a proposal'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000004',
            'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000005',
            'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact create grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000006',
            'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without active party binding was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000004', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000007',
            'unsafe', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator bound to inactive party was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000005', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000008',
            'superseded', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', NULL
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'superseded proposal without replacement was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.propose_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'ab100000-0000-4000-8000-000000000009',
            'superseded', 'private trigger reason', '[{"source":"private evidence"}]'::jsonb,
            'private migration plan', 'c0000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location replacement solution was accepted'; END IF;

    denied := FALSE;
    BEGIN PERFORM 1 FROM public.solution_retirement;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read retirement source'; END IF;

    denied := FALSE;
    BEGIN PERFORM 1 FROM public.solution_retirement_proposal_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read proposal receipts'; END IF;

    denied := FALSE;
    BEGIN
        INSERT INTO public.solution_retirement_proposal_event
            (operator_id, proposer_party_id, location_id, retirement_id, request_id)
        VALUES
            ('a0000000-0000-4000-8000-000000000005', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
             'b0000000-0000-4000-8000-000000000001', 'fa000000-0000-4000-8000-000000000011',
             'ab100000-0000-4000-8000-000000000010');
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly insert proposal receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE event_count INTEGER; proposal_count INTEGER; approved_count INTEGER;
BEGIN
    SELECT count(*) INTO event_count FROM public.solution_retirement_proposal_event;
    SELECT count(*) INTO proposal_count FROM public.solution_retirement
     WHERE id IN (SELECT retirement_id FROM public.solution_retirement_proposal_event)
       AND status = 'proposed'
       AND created_by_party_id = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
    SELECT count(*) INTO approved_count FROM public.solution_retirement
     WHERE id IN (SELECT retirement_id FROM public.solution_retirement_review_event)
       AND status = 'approved';
    IF event_count <> 1 OR proposal_count <> 1 OR approved_count <> 1 THEN
        RAISE EXCEPTION 'proposal retry/denial was not atomic (events %, proposals %, approvals %)',
            event_count, proposal_count, approved_count;
    END IF;
    IF has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.propose_location_solution_retirement(uuid,uuid,uuid,text,text,jsonb,text,uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_proposal_event', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_proposal_event', 'INSERT')
       OR has_table_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement_proposal_event', 'UPDATE')
       OR has_table_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement_proposal_event', 'DELETE')
       OR has_column_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement', 'approved_by_party_id', 'INSERT')
       OR has_column_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement', 'approved_at', 'INSERT')
       OR has_column_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement', 'approved_by_party_id', 'UPDATE')
       OR has_column_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement', 'approved_at', 'UPDATE')
       OR has_column_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement', 'status', 'UPDATE')
       OR NOT has_column_privilege('kokonut_solution_proposal_owner', 'public.solution_retirement', 'evidence_refs', 'INSERT') THEN
        RAISE EXCEPTION 'proposal function or independent-review boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-retirement-proposal-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "ordered lifecycle migrations through 475 apply; migration 476 applies and replays",
            "exact origin, exact create grant, active operator-person binding, and location-visible replacements are enforced",
            "required proposal fields are bounded and malformed or superseded-without-replacement input fails closed",
            "proposal plus append-only receipt are atomic; same-input retries are idempotent and collisions are rejected",
            "runtime has no direct source/receipt access, Directus cannot execute the function, and the separate non-login proposal owner cannot update retirements or set approval attribution",
        ],
    }
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16",
        ])
        wait_ready(container, docker)
        # Reuse the exact ordered synthetic lifecycle setup that accepted migration 475.
        gate_check = approval.gate_check
        experiment_check = approval.experiment_check
        funding_check = approval.funding_check
        adoption_check = approval.adoption_check
        scale_check = approval.scale_check
        replication_check = approval.replication_check
        learning_check = approval.learning_check
        retirement_check = approval.retirement_check
        psql(docker, container, gate_check.FIXTURE)
        psql(docker, container, gate_check.helper.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, gate_check.ACCEPTANCE)
        psql(docker, container, gate_check.MIGRATION.read_text(encoding="utf-8"))
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
        replication_sql = replication_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, replication_sql)
        psql(docker, container, replication_sql)
        psql(docker, container, learning_check.LEARNING_SOURCE)
        learning_sql = learning_check.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, learning_sql)
        psql(docker, container, learning_sql)
        psql(docker, container, learning_check.LEARNING_ACCEPTANCE)
        psql(docker, container, retirement_check.RETIREMENT_SOURCE)
        psql(docker, container, retirement_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, retirement_check.RETIREMENT_ACCEPTANCE)
        psql(docker, container, approval.prior.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, approval.prior.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, approval.prior.INDEPENDENT_REVIEW_ACCEPTANCE)
        psql(docker, container, approval.REVIEW_FIXTURE)
        approval_sql = approval.MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, approval_sql)
        psql(docker, container, approval_sql)
        psql(docker, container, approval.APPROVAL_ACCEPTANCE)
        psql(docker, container, PROPOSAL_FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, PROPOSAL_ACCEPTANCE)
        evidence["acceptance_groups_passed"] = 5
        evidence["result"] = "passed"
        print("PASS: migrations 459 and 466–476 apply, migration 476 replays, and five proposal acceptance groups passed")
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
