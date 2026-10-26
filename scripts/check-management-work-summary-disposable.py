#!/usr/bin/env python3
"""Exercise migration 454 against a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "identity_disposable", ROOT / "scripts/check-stakeholder-identity-disposable.py"
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_identity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_identity)
run = _identity.run
psql = _identity.psql
wait_ready = _identity.wait_ready
FIXTURE = _identity.FIXTURE
MIGRATION = ROOT / "schemas/postgres/454_location_scoped_management_work_summary.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-030-management-work-summary-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def management_fixture() -> str:
    return r"""
CREATE TABLE public.work_item (
    id uuid PRIMARY KEY, organization_id uuid NOT NULL, location_id uuid,
    status text NOT NULL, priority text NOT NULL, due_at timestamptz,
    sla_at timestamptz, assignee_id uuid, title text, description text
);
CREATE TABLE public.work_item_event (
    id uuid PRIMARY KEY, work_item_id uuid NOT NULL, actor_id uuid,
    note text, created_at timestamptz NOT NULL
);
CREATE TABLE public.work_item_claim (
    id uuid PRIMARY KEY, work_item_id uuid NOT NULL, claimant_party_id uuid,
    status text NOT NULL, decision_reason text
);
CREATE TABLE public.process_escalation (
    id uuid PRIMARY KEY, entity_type text NOT NULL, entity_id uuid NOT NULL,
    work_item_id uuid, resolved_at timestamptz, reason text
);

INSERT INTO public.work_item VALUES
 ('21000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000101', 'b0000000-0000-4000-8000-000000000001', 'assigned', 'high', CURRENT_TIMESTAMP - interval '2 days', CURRENT_TIMESTAMP - interval '1 day', 'a1000000-0000-4000-8000-000000000001', 'PRIVATE-WORK-TITLE', 'PRIVATE-WORK-DESCRIPTION'),
 ('21000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000101', 'b0000000-0000-4000-8000-000000000001', 'in_progress', 'critical', CURRENT_TIMESTAMP + interval '1 day', CURRENT_TIMESTAMP - interval '1 hour', 'a1000000-0000-4000-8000-000000000002', 'PRIVATE-WORK-TITLE', 'PRIVATE-WORK-DESCRIPTION'),
 ('21000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000101', 'b0000000-0000-4000-8000-000000000001', 'blocked', 'medium', NULL, NULL, 'a1000000-0000-4000-8000-000000000003', 'PRIVATE-WORK-TITLE', 'PRIVATE-WORK-DESCRIPTION'),
 ('21000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000101', 'b0000000-0000-4000-8000-000000000001', 'done', 'critical', CURRENT_TIMESTAMP - interval '5 days', CURRENT_TIMESTAMP - interval '4 days', 'a1000000-0000-4000-8000-000000000004', 'PRIVATE-WORK-TITLE', 'PRIVATE-WORK-DESCRIPTION'),
 ('21000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000101', 'b0000000-0000-4000-8000-000000000001', 'cancelled', 'high', CURRENT_TIMESTAMP - interval '5 days', CURRENT_TIMESTAMP - interval '4 days', NULL, 'PRIVATE-WORK-TITLE', 'PRIVATE-WORK-DESCRIPTION'),
 ('21000000-0000-4000-8000-000000000006', 'b0000000-0000-4000-8000-000000000101', 'b0000000-0000-4000-8000-000000000001', 'draft', 'medium', NULL, NULL, NULL, 'PRIVATE-WORK-TITLE', 'PRIVATE-WORK-DESCRIPTION'),
 ('21000000-0000-4000-8000-000000000007', 'b0000000-0000-4000-8000-000000000102', 'b0000000-0000-4000-8000-000000000002', 'assigned', 'critical', CURRENT_TIMESTAMP - interval '3 days', CURRENT_TIMESTAMP - interval '2 days', 'a1000000-0000-4000-8000-000000000007', 'PRIVATE-OTHER-LOCATION', 'PRIVATE-OTHER-DESCRIPTION');
INSERT INTO public.work_item_event VALUES
 ('22000000-0000-4000-8000-000000000001', '21000000-0000-4000-8000-000000000001', 'a1000000-0000-4000-8000-000000000001', 'PRIVATE-AUDIT-NOTE', '2026-10-17 12:00:00+00'),
 ('22000000-0000-4000-8000-000000000002', '21000000-0000-4000-8000-000000000002', 'a1000000-0000-4000-8000-000000000002', 'PRIVATE-AUDIT-NOTE', '2026-10-18 12:00:00+00'),
 ('22000000-0000-4000-8000-000000000003', '21000000-0000-4000-8000-000000000007', 'a1000000-0000-4000-8000-000000000007', 'PRIVATE-OTHER-AUDIT', '2026-10-19 12:00:00+00');
INSERT INTO public.work_item_claim VALUES
 ('23000000-0000-4000-8000-000000000001', '21000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'proposed', 'PRIVATE-CLAIM-REASON'),
 ('23000000-0000-4000-8000-000000000002', '21000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000002', 'accepted', 'PRIVATE-CLAIM-REASON'),
 ('23000000-0000-4000-8000-000000000003', '21000000-0000-4000-8000-000000000007', 'c1000000-0000-4000-8000-000000000007', 'proposed', 'PRIVATE-OTHER-CLAIM');
INSERT INTO public.process_escalation VALUES
 ('24000000-0000-4000-8000-000000000001', 'work_item', '21000000-0000-4000-8000-000000000001', NULL, '2026-10-18 12:00:00+00', 'PRIVATE-RESOLVED-ESCALATION'),
 ('24000000-0000-4000-8000-000000000002', 'work_item', '21000000-0000-4000-8000-000000000002', '21000000-0000-4000-8000-000000000002', NULL, 'PRIVATE-OPEN-ESCALATION'),
 ('24000000-0000-4000-8000-000000000003', 'work_item', '21000000-0000-4000-8000-000000000007', '21000000-0000-4000-8000-000000000007', NULL, 'PRIVATE-OTHER-ESCALATION');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'management_workflow', 'read', NULL, NULL);
"""


def acceptance_sql() -> str:
    return r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    summary record;
    denied boolean := false;
    output_text text;
BEGIN
    SELECT * INTO summary FROM kokonut_security.location_management_work_summary(
        'b0000000-0000-4000-8000-000000000001'
    );
    IF summary.work_item_count <> 6
       OR summary.open_work_item_count <> 4
       OR summary.draft_count <> 1
       OR summary.assigned_count <> 1
       OR summary.in_progress_count <> 1
       OR summary.blocked_count <> 1
       OR summary.done_count <> 1
       OR summary.cancelled_count <> 1
       OR summary.high_priority_open_count <> 1
       OR summary.critical_priority_open_count <> 1
       OR summary.overdue_count <> 1
       OR summary.sla_breached_count <> 2
       OR summary.pending_claim_count <> 1
       OR summary.accepted_claim_count <> 1
       OR summary.open_escalation_count <> 1
       OR summary.resolved_escalation_count <> 1
       OR summary.latest_work_event_at <> '2026-10-18 12:00:00+00'::timestamptz THEN
        RAISE EXCEPTION 'management work aggregates did not match scoped fixture';
    END IF;
    SELECT row_to_json(summary)::text INTO output_text;
    IF output_text LIKE ANY (ARRAY[
        '%PRIVATE-%', '%title%', '%description%', '%assignee_id%', '%actor_id%',
        '%claimant_party_id%', '%note%', '%decision_reason%'
    ]) THEN RAISE EXCEPTION 'management projection contains private work or identity detail'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.location_management_work_summary(
            'b0000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.location_management_work_summary(
            'b0000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without management read grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.work_item;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read work items directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    function_owner text;
    is_security_definer boolean;
    result_contract text;
BEGIN
    SELECT pg_get_userbyid(proc.proowner), proc.prosecdef
      INTO function_owner, is_security_definer
      FROM pg_catalog.pg_proc AS proc
     WHERE proc.oid = 'kokonut_security.location_management_work_summary(uuid)'::regprocedure;
    IF function_owner <> 'kokonut_management_reader' OR NOT is_security_definer THEN
        RAISE EXCEPTION 'management projection owner/security mode is incorrect';
    END IF;
    SELECT pg_get_function_result(
        'kokonut_security.location_management_work_summary(uuid)'::regprocedure
    ) INTO result_contract;
    IF result_contract LIKE ANY (ARRAY[
        '%title%', '%description%', '%assignee%', '%actor_id%', '%claimant_party_id%',
        '%note%', '%decision_reason%', '%estimated_effort%', '%skill_requirements%'
    ]) THEN RAISE EXCEPTION 'management projection signature contains private details'; END IF;
    IF has_table_privilege('kokonut_runtime', 'public.work_item', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.work_item_claim', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.work_item', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.location_management_work_summary(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime or Directus has unexpected direct management access';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.location_management_work_summary(uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime cannot execute bounded management projection';
    END IF;
    IF has_table_privilege('kokonut_management_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_management_reader', 'public.work_item', 'UPDATE')
       OR has_table_privilege('kokonut_management_reader', 'public.work_item_event', 'INSERT') THEN
        RAISE EXCEPTION 'management reader role has identity or mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-management-read-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 454 applies and replays on disposable PostgreSQL 16",
        "management work, lifecycle, priority, overdue, and SLA counts match a synthetic location fixture",
        "claim, escalation, and audit recency totals retain location scope",
        "task content, assignee/actor identifiers, and audit notes are excluded",
        "exact signed location context and management_workflow:read grant are required",
        "runtime/Directus direct table reads are denied and runtime receives function-only access",
        "dedicated management reader role is non-login, read-only, and narrowly scoped",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    stage = "container_start"
    try:
        run([
            docker, "run", "--rm", "--detach", "--name", container,
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
            "--publish", "127.0.0.1::5432", IMAGE,
        ])
        wait_ready(container, docker)
        stage = "base_management_fixture"
        psql(docker, container, FIXTURE)
        psql(docker, container, management_fixture())
        stage = "migration_454_apply_and_replay"
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        stage = "scope_aggregate_and_privilege_acceptance"
        psql(docker, container, acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - evidence retains only bounded safe diagnostics
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:800]
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
