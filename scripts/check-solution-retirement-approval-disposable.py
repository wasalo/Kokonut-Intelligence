#!/usr/bin/env python3
"""Exercise migration 475's location-scoped retirement approval workflow."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR_CHECK = ROOT / "scripts/check-solution-retirement-independent-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/475_location_solution_retirement_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/solution-retirement-approval-disposable.json"
spec = importlib.util.spec_from_file_location("solution_retirement_review_disposable", PRIOR_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load prior disposable retirement fixtures")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
run = prior.retirement_check.run
psql = prior.retirement_check.psql
wait_ready = prior.retirement_check.wait_ready
gate_check = prior.gate_check
experiment_check = prior.experiment_check
funding_check = prior.funding_check
adoption_check = prior.adoption_check
scale_check = prior.scale_check
replication_check = prior.replication_check
learning_check = prior.learning_check
retirement_check = prior.retirement_check

REVIEW_FIXTURE = r"""
ALTER TABLE public.party
    ADD COLUMN party_type text NOT NULL DEFAULT 'person',
    ADD COLUMN status text NOT NULL DEFAULT 'active';
CREATE TABLE public.operator_governance_party_binding (
    id uuid PRIMARY KEY,
    operator_id uuid NOT NULL REFERENCES public.operator_identity(id),
    party_id uuid NOT NULL REFERENCES public.party(id),
    revoked_at timestamptz
);
INSERT INTO public.party (id, display_name) VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Synthetic proposer'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Synthetic reviewer'),
    ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'Synthetic inactive reviewer');
UPDATE public.party SET status = 'inactive'
 WHERE id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
INSERT INTO public.operator_identity (id, enabled)
VALUES ('a0000000-0000-4000-8000-000000000003', true),
       ('a0000000-0000-4000-8000-000000000004', true);
INSERT INTO public.operator_governance_party_binding
    (id, operator_id, party_id, revoked_at)
VALUES
    ('a5000000-0000-4000-8000-000000000001',
     'a0000000-0000-4000-8000-000000000001',
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', NULL),
    ('a5000000-0000-4000-8000-000000000002',
     'a0000000-0000-4000-8000-000000000004',
     'cccccccc-cccc-4ccc-8ccc-cccccccccccc', NULL);
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('a6000000-0000-4000-8000-000000000001',
     'a0000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000002',
     'a0000000-0000-4000-8000-000000000003',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', NULL, NULL),
    ('a6000000-0000-4000-8000-000000000003',
     'a0000000-0000-4000-8000-000000000004',
     'b0000000-0000-4000-8000-000000000001',
     'solution_lifecycle', 'review', NULL, NULL);
INSERT INTO public.solution_retirement
    (id, solution_id, retirement_type, trigger_reason, status, evidence_refs,
     migration_plan, replacement_solution_id, created_by_party_id)
VALUES
    ('fa000000-0000-4000-8000-000000000011',
     'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
     'proposed', '[{"source":"review"}]', 'private migration plan', NULL,
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('fa000000-0000-4000-8000-000000000012',
     'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
     'proposed', '[{"source":"review"}]', 'private migration plan', NULL,
     'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
    ('fa000000-0000-4000-8000-000000000013',
     'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
     'proposed', '[]', 'private migration plan', NULL,
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('fa000000-0000-4000-8000-000000000014',
     'c0000000-0000-4000-8000-000000000001', 'unsafe', 'private reason',
     'proposed', '[{"source":"review"}]', NULL, NULL,
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('fa000000-0000-4000-8000-000000000015',
     'c0000000-0000-4000-8000-000000000001', 'superseded', 'private reason',
     'proposed', '[{"source":"review"}]', 'private migration plan', NULL,
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('fa000000-0000-4000-8000-000000000016',
     'c0000000-0000-4000-8000-000000000003', 'unsafe', 'private reason',
     'proposed', '[{"source":"review"}]', 'private migration plan', NULL,
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
"""

APPROVAL_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    result record;
    first_event uuid;
    denied boolean;
BEGIN
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000002',
            'fa000000-0000-4000-8000-000000000011',
            'ab000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000016',
            'ab000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN no_data_found THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location retirement was returned for review'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000012',
            'ab000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'self-review was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000013',
            'ab000000-0000-4000-8000-000000000004'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'retirement without evidence was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000014',
            'ab000000-0000-4000-8000-000000000005'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'retirement without a migration plan was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000015',
            'ab000000-0000-4000-8000-000000000006'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'superseded retirement without replacement was accepted'; END IF;

    SELECT * INTO result FROM kokonut_security.approve_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001',
        'fa000000-0000-4000-8000-000000000011',
        'ab000000-0000-4000-8000-000000000007'
    );
    IF result.retirement_status <> 'approved' OR result.replayed
       OR result.approved_at IS NULL OR result.event_id IS NULL THEN
        RAISE EXCEPTION 'approval did not produce a fresh result receipt';
    END IF;
    first_event := result.event_id;

    SELECT * INTO result FROM kokonut_security.approve_location_solution_retirement(
        'b0000000-0000-4000-8000-000000000001',
        'fa000000-0000-4000-8000-000000000011',
        'ab000000-0000-4000-8000-000000000007'
    );
    IF NOT result.replayed OR result.event_id <> first_event THEN
        RAISE EXCEPTION 'identical approval retry did not return the original receipt';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000012',
            'ab000000-0000-4000-8000-000000000007'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'request id reuse for a different retirement was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000011',
            'ab000000-0000-4000-8000-000000000008'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact review grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000011',
            'ab000000-0000-4000-8000-000000000009'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without active party binding was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000004', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.approve_location_solution_retirement(
            'b0000000-0000-4000-8000-000000000001',
            'fa000000-0000-4000-8000-000000000011',
            'ab000000-0000-4000-8000-000000000011'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator bound to inactive party was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_retirement;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read retirement source'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.solution_retirement_review_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read review receipts'; END IF;

    denied := false;
    BEGIN
        INSERT INTO public.solution_retirement_review_event
            (operator_id, reviewer_party_id, location_id, retirement_id, request_id,
             action, previous_status, resulting_status)
        VALUES
            ('a0000000-0000-4000-8000-000000000001',
             'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
             'b0000000-0000-4000-8000-000000000001',
             'fa000000-0000-4000-8000-000000000011',
             'ab000000-0000-4000-8000-000000000010', 'approved', 'proposed', 'approved');
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly write review receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE event_count integer; approved_count integer; proposed_count integer;
BEGIN
    SELECT count(*) INTO event_count FROM public.solution_retirement_review_event;
    SELECT count(*) INTO approved_count FROM public.solution_retirement
     WHERE status = 'approved' AND id = 'fa000000-0000-4000-8000-000000000011';
    SELECT count(*) INTO proposed_count FROM public.solution_retirement
     WHERE status = 'proposed' AND id IN (
       'fa000000-0000-4000-8000-000000000012',
       'fa000000-0000-4000-8000-000000000013',
       'fa000000-0000-4000-8000-000000000014',
       'fa000000-0000-4000-8000-000000000015',
       'fa000000-0000-4000-8000-000000000016'
     );
    IF event_count <> 1 OR approved_count <> 1 OR proposed_count <> 5 THEN
        RAISE EXCEPTION 'approval failure was not atomic (events %, approved %, proposed %)',
            event_count, approved_count, proposed_count;
    END IF;
    IF has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.approve_location_solution_retirement(uuid,uuid,uuid)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_review_event', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.solution_retirement_review_event', 'INSERT')
       OR has_table_privilege('kokonut_solution_action_owner', 'public.solution_retirement_review_event', 'UPDATE')
       OR has_table_privilege('kokonut_solution_action_owner', 'public.solution_retirement_review_event', 'DELETE')
       OR has_column_privilege('kokonut_solution_action_owner', 'public.solution_retirement', 'trigger_reason', 'SELECT')
       OR NOT has_column_privilege('kokonut_solution_action_owner', 'public.solution_retirement', 'evidence_refs', 'SELECT') THEN
        RAISE EXCEPTION 'retirement action boundary failed: directus execute %, runtime receipt select %, runtime receipt insert %, owner receipt update %, owner receipt delete %, trigger select %, evidence select %',
            has_function_privilege('kokonut_directus_runtime', 'kokonut_security.approve_location_solution_retirement(uuid,uuid,uuid)', 'EXECUTE'),
            has_table_privilege('kokonut_runtime', 'public.solution_retirement_review_event', 'SELECT'),
            has_table_privilege('kokonut_runtime', 'public.solution_retirement_review_event', 'INSERT'),
            has_table_privilege('kokonut_solution_action_owner', 'public.solution_retirement_review_event', 'UPDATE'),
            has_table_privilege('kokonut_solution_action_owner', 'public.solution_retirement_review_event', 'DELETE'),
            has_column_privilege('kokonut_solution_action_owner', 'public.solution_retirement', 'trigger_reason', 'SELECT'),
            has_column_privilege('kokonut_solution_action_owner', 'public.solution_retirement', 'evidence_refs', 'SELECT');
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-retirement-approval-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "ordered solution lifecycle migrations through 474 apply; migration 475 applies and replays",
            "signed location, exact solution origin, review grant, active OIDC-to-person binding, and independent reviewer are enforced",
            "evidence, migration plan, and superseded replacement prerequisites fail closed",
            "approval and append-only receipt commit atomically with idempotent retry and request collision denial",
            "runtime cannot access source or receipt tables directly; Directus cannot call the write function",
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
        for _ in range(2):
            psql(docker, container, replication_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.LEARNING_SOURCE)
        psql(docker, container, learning_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, learning_check.LEARNING_ACCEPTANCE)
        psql(docker, container, retirement_check.RETIREMENT_SOURCE)
        psql(docker, container, retirement_check.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, retirement_check.RETIREMENT_ACCEPTANCE)
        psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, prior.MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, prior.INDEPENDENT_REVIEW_ACCEPTANCE)
        psql(docker, container, REVIEW_FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        psql(docker, container, APPROVAL_ACCEPTANCE)
        evidence["acceptance_groups_passed"] = 5
        evidence["result"] = "passed"
        print("PASS: migrations 459 and 466–475 apply, migration 475 replays, and five approval acceptance groups passed")
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
