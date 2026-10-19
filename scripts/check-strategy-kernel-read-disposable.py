#!/usr/bin/env python3
"""Exercise migration 452 against a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_base_path = ROOT / "scripts/check-stakeholder-identity-disposable.py"
_base_spec = importlib.util.spec_from_file_location("identity_disposable", _base_path)
if _base_spec is None or _base_spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_base = importlib.util.module_from_spec(_base_spec)
_base_spec.loader.exec_module(_base)

FIXTURE = _base.FIXTURE
run = _base.run
psql = _base.psql
wait_ready = _base.wait_ready
MIGRATION = ROOT / "schemas/postgres/452_location_scoped_strategy_plan_read.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-028-strategy-read-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def strategy_fixture() -> str:
    return r"""
ALTER TABLE public.operator_organization_membership
    ADD COLUMN operator_id uuid, ADD COLUMN organization_id uuid,
    ADD COLUMN revoked_at timestamptz;
ALTER TABLE public.location_tenant_owner_verification
    ADD COLUMN location_id uuid, ADD COLUMN organization_id uuid,
    ADD COLUMN revoked_at timestamptz;
ALTER TABLE public.location_organization_share
    ADD COLUMN location_id uuid, ADD COLUMN organization_id uuid,
    ADD COLUMN revoked_at timestamptz, ADD COLUMN expires_at timestamptz;

CREATE TABLE public.strategy_plan (
    id uuid PRIMARY KEY, scope_type text NOT NULL, scope_id uuid NOT NULL,
    name text NOT NULL, version integer NOT NULL, status text NOT NULL,
    visibility text NOT NULL, planning_horizon_start date NOT NULL,
    planning_horizon_end date NOT NULL, updated_at timestamptz NOT NULL,
    cascade_mode text NOT NULL, cascade_status text NOT NULL,
    parent_strategy_plan_id uuid, diagnosis_summary text NOT NULL,
    guiding_policy text NOT NULL, cascade_rationale text
);
CREATE TABLE public.strategy_review_task (
    id uuid PRIMARY KEY, strategy_plan_id uuid NOT NULL, status text NOT NULL,
    decision_note text
);
CREATE TABLE public.strategy_allocation_decision (
    id uuid PRIMARY KEY, strategy_plan_id uuid NOT NULL,
    decision_status text NOT NULL, rationale text NOT NULL
);
CREATE VIEW public.v_strategy_kernel_execution AS
SELECT plan.id AS strategy_plan_id,
       CASE WHEN plan.name = 'Location A active' THEN 4::bigint ELSE 1::bigint END AS objective_count,
       CASE WHEN plan.name = 'Location A active' THEN 6::bigint ELSE 0::bigint END AS initiative_count,
       CASE WHEN plan.name = 'Location A active' THEN 2::bigint ELSE 0::bigint END AS completed_initiative_count,
       CASE WHEN plan.name = 'Location A active' THEN 3::bigint ELSE 0::bigint END AS investment_case_count,
       CASE WHEN plan.name = 'Location A active' THEN 1::bigint ELSE 0::bigint END AS recommended_investment_count,
       CASE WHEN plan.name = 'Location A active' THEN 1::bigint ELSE 0::bigint END AS open_coherence_finding_count
  FROM public.strategy_plan AS plan;
CREATE VIEW public.v_strategy_gate_status AS
SELECT plan.id AS strategy_plan_id,
       CASE WHEN plan.name = 'Location A active' THEN 0::bigint ELSE 1::bigint END AS blocking_finding_count,
       CASE WHEN plan.name = 'Location A active' THEN 'ready'::text ELSE 'blocked'::text END AS gate_status
  FROM public.strategy_plan AS plan;

INSERT INTO public.location (id, organization_id, status) VALUES
 ('b0000000-0000-4000-8000-000000000001', NULL, 'active'),
 ('b0000000-0000-4000-8000-000000000002', NULL, 'active');
INSERT INTO public.operator_identity (id, enabled) VALUES
 ('a0000000-0000-4000-8000-000000000002', true),
 ('a0000000-0000-4000-8000-000000000003', true);
INSERT INTO public.operator_scope_grant
 (id, operator_id, location_id, resource, action, organization_id, revoked_at) VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'strategy', 'read', NULL, NULL);
INSERT INTO public.strategy_plan VALUES
 ('c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'Location A active', 2, 'active', 'limited', '2026-01-01', '2030-12-31', clock_timestamp(), 'adapted', 'aligned', 'd0000000-0000-4000-8000-000000000001', 'PRIVATE diagnosis text', 'PRIVATE policy text', 'PRIVATE cascade rationale'),
 ('c0000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000001', 'Location A draft', 1, 'draft', 'private', '2027-01-01', '2028-12-31', clock_timestamp() - interval '1 day', 'independent', 'not_applicable', NULL, 'PRIVATE draft diagnosis', 'PRIVATE draft policy', NULL),
 ('c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000002', 'Location B private', 1, 'active', 'private', '2026-01-01', '2028-12-31', clock_timestamp(), 'independent', 'not_applicable', NULL, 'PRIVATE B diagnosis', 'PRIVATE B policy', NULL),
 ('c0000000-0000-4000-8000-000000000004', 'organization', 'b0000000-0000-4000-8000-000000000001', 'Organization plan', 1, 'active', 'private', '2026-01-01', '2030-12-31', clock_timestamp(), 'independent', 'not_applicable', NULL, 'PRIVATE org diagnosis', 'PRIVATE org policy', NULL);
INSERT INTO public.strategy_review_task VALUES
 ('e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'pending', 'PRIVATE review note'),
 ('e0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 'completed', 'PRIVATE completed note'),
 ('e0000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000002', 'overdue', 'PRIVATE overdue note');
INSERT INTO public.strategy_allocation_decision VALUES
 ('f0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'submitted', 'PRIVATE submission rationale'),
 ('f0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 'approved', 'PRIVATE approval rationale');
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
    active_row record;
    draft_row record;
    denied boolean := false;
    page_count integer;
BEGIN
    SELECT * INTO active_row
      FROM kokonut_security.list_location_strategy_plan_summaries(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE plan_status = 'active';
    IF active_row.strategy_plan_id <> 'c0000000-0000-4000-8000-000000000001'::uuid
       OR active_row.plan_name <> 'Location A active'
       OR active_row.objective_count <> 4 OR active_row.initiative_count <> 6
       OR active_row.completed_initiative_count <> 2
       OR active_row.investment_case_count <> 3
       OR active_row.recommended_investment_count <> 1
       OR active_row.open_coherence_finding_count <> 1
       OR active_row.blocking_finding_count <> 0
       OR active_row.structural_gate_status <> 'ready'
       OR active_row.open_review_task_count <> 1
       OR active_row.submitted_allocation_count <> 1
       OR active_row.approved_allocation_count <> 1
       OR NOT active_row.has_parent_strategy THEN
        RAISE EXCEPTION 'location strategy projection lost plan/execution/cascade lineage';
    END IF;
    SELECT * INTO draft_row
      FROM kokonut_security.list_location_strategy_plan_summaries(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE strategy_plan_id = 'c0000000-0000-4000-8000-000000000002';
    IF draft_row.structural_gate_status <> 'blocked'
       OR draft_row.has_parent_strategy THEN
        RAISE EXCEPTION 'draft structural gate or independent cascade was misreported';
    END IF;
    SELECT count(*) INTO page_count
      FROM kokonut_security.list_location_strategy_plan_summaries(
          'b0000000-0000-4000-8000-000000000001', 1, 0
      );
    IF page_count <> 1 THEN RAISE EXCEPTION 'requested page bound was not enforced'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_strategy_plan_summaries(
            'b0000000-0000-4000-8000-000000000002', 51, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;

    PERFORM set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_strategy_plan_summaries(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without strategy:read grant was accepted'; END IF;
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
     WHERE proc.oid = 'kokonut_security.list_location_strategy_plan_summaries(uuid,integer,integer)'::regprocedure;
    IF function_owner <> 'kokonut_strategy_reader' OR NOT is_security_definer THEN
        RAISE EXCEPTION 'strategy projection function owner/security mode is incorrect';
    END IF;
    SELECT pg_get_function_result(
        'kokonut_security.list_location_strategy_plan_summaries(uuid,integer,integer)'::regprocedure
    ) INTO result_contract;
    IF result_contract LIKE ANY (ARRAY[
        '%diagnosis_summary%', '%guiding_policy%', '%cascade_rationale%',
        '%rationale%', '%decision_note%', '%party_id%', '%estimated_cost%',
        '%parent_strategy_plan_id%'
    ]) THEN
        RAISE EXCEPTION 'strategy projection signature includes private content or parent identity';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.strategy_plan', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.strategy_review_task', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.strategy_plan', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.list_location_strategy_plan_summaries(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime or Directus has unexpected direct strategy projection access';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_strategy_plan_summaries(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime cannot execute the bounded strategy projection';
    END IF;
    IF has_table_privilege('kokonut_strategy_reader', 'public.party', 'SELECT') THEN
        RAISE EXCEPTION 'reader role has broader access than the declared projection';
    END IF;
    IF has_table_privilege('kokonut_strategy_reader', 'public.strategy_plan', 'INSERT')
       OR has_table_privilege('kokonut_strategy_reader', 'public.strategy_plan', 'UPDATE')
       OR has_table_privilege('kokonut_strategy_reader', 'public.strategy_plan', 'DELETE') THEN
        RAISE EXCEPTION 'strategy reader role has mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-strategy-read-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 452 applies and replays on disposable PostgreSQL 16",
        "only location strategy plans are returned under matching operator context and exact grant",
        "bounded paging retains lifecycle, execution, allocation, review, cascade, and structural gate metadata",
        "organization-wide and cross-location plans are not exposed to a location grant",
        "reader role and SECURITY DEFINER function retain only the required read surface",
        "runtime can execute the projection but direct table reads and Directus execution are denied",
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
        stage = "base_and_strategy_fixture"
        psql(docker, container, FIXTURE)
        psql(docker, container, strategy_fixture())
        stage = "migration_452_apply_and_replay"
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        stage = "authorization_and_privilege_acceptance"
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
    sys.exit(main())
