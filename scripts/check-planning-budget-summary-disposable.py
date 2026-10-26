#!/usr/bin/env python3
"""Exercise migration 455 against a fresh disposable PostgreSQL 16 container."""

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
MIGRATION = ROOT / "schemas/postgres/455_location_scoped_budget_summary.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-031-budget-summary-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def planning_fixture() -> str:
    return r"""
INSERT INTO public.organization VALUES
 ('b1000000-0000-4000-8000-000000000001', 'active'),
 ('b1000000-0000-4000-8000-000000000002', 'active');
INSERT INTO public.location (id, organization_id, status) VALUES
 ('b0000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000001', 'active'),
 ('b0000000-0000-4000-8000-000000000002', 'b1000000-0000-4000-8000-000000000002', 'active');

CREATE TABLE public.financial_plan (
    id uuid PRIMARY KEY, organization_id uuid NOT NULL, objective_id uuid,
    name text NOT NULL, period_start date NOT NULL, period_end date NOT NULL,
    currency text, status text NOT NULL, updated_at timestamptz NOT NULL
);
CREATE TABLE public.budget_line (
    id uuid PRIMARY KEY, plan_id uuid NOT NULL, category text NOT NULL,
    location_id uuid, amount numeric NOT NULL, notes text
);
CREATE TABLE public.planning_scenario (
    id uuid PRIMARY KEY, plan_id uuid NOT NULL, name text NOT NULL,
    assumptions jsonb NOT NULL
);
CREATE TABLE public.expense_event (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, expense_date date NOT NULL,
    category text NOT NULL, amount numeric NOT NULL, currency text,
    status text NOT NULL, description text, vendor text, notes text, evidence_urls text[]
);

INSERT INTO public.financial_plan VALUES
 ('c1000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000001', 'd1000000-0000-4000-8000-000000000001', 'PRIVATE-PLAN-NAME', '2026-01-01', '2026-12-31', 'USD', 'active', clock_timestamp()),
 ('c1000000-0000-4000-8000-000000000002', 'b1000000-0000-4000-8000-000000000001', NULL, 'PRIVATE-PLAN-NAME-OLDER', '2025-01-01', '2025-12-31', 'EUR', 'approved', clock_timestamp() - interval '1 day'),
 ('c1000000-0000-4000-8000-000000000003', 'b1000000-0000-4000-8000-000000000001', NULL, 'PRIVATE-ORG-LINE-ONLY', '2026-01-01', '2026-12-31', 'USD', 'active', clock_timestamp()),
 ('c1000000-0000-4000-8000-000000000004', 'b1000000-0000-4000-8000-000000000002', NULL, 'PRIVATE-OTHER-ORG', '2026-01-01', '2026-12-31', 'USD', 'active', clock_timestamp());
INSERT INTO public.budget_line VALUES
 ('e1000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'fertilizer', 'b0000000-0000-4000-8000-000000000001', 1000, 'PRIVATE-BUDGET-NOTE'),
 ('e1000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 'labor', 'b0000000-0000-4000-8000-000000000001', 200, 'PRIVATE-BUDGET-NOTE'),
 ('e1000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000001', 'general', NULL, 9999, 'PRIVATE-ORG-LEVEL-LINE'),
 ('e1000000-0000-4000-8000-000000000004', 'c1000000-0000-4000-8000-000000000002', 'seed', 'b0000000-0000-4000-8000-000000000001', 50, 'PRIVATE-BUDGET-NOTE'),
 ('e1000000-0000-4000-8000-000000000005', 'c1000000-0000-4000-8000-000000000003', 'general', NULL, 8000, 'PRIVATE-ORG-LEVEL-LINE'),
 ('e1000000-0000-4000-8000-000000000006', 'c1000000-0000-4000-8000-000000000004', 'fertilizer', 'b0000000-0000-4000-8000-000000000001', 7000, 'PRIVATE-OTHER-ORG-LINE');
INSERT INTO public.planning_scenario VALUES
 ('f1000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 'PRIVATE-SCENARIO-NAME', '{"secret":"PRIVATE-ASSUMPTION"}'),
 ('f1000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 'PRIVATE-SCENARIO-NAME', '{"secret":"PRIVATE-ASSUMPTION"}');
INSERT INTO public.expense_event VALUES
 ('a1000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', '2026-04-01', 'fertilizer', 400, 'USD', 'verified', 'PRIVATE-EXPENSE-DESCRIPTION', 'PRIVATE-VENDOR', 'PRIVATE-EXPENSE-NOTE', ARRAY['PRIVATE-EVIDENCE']),
 ('a1000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', '2026-05-01', 'labor', 75.25, 'USD', 'verified', 'PRIVATE-EXPENSE-DESCRIPTION', 'PRIVATE-VENDOR', 'PRIVATE-EXPENSE-NOTE', ARRAY['PRIVATE-EVIDENCE']),
 ('a1000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000001', '2026-06-01', 'labor', 20, 'EUR', 'verified', 'PRIVATE-EXPENSE-DESCRIPTION', 'PRIVATE-VENDOR', 'PRIVATE-EXPENSE-NOTE', ARRAY['PRIVATE-EVIDENCE']),
 ('a1000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000001', '2026-06-01', 'fertilizer', 300, 'USD', 'draft', 'PRIVATE-DRAFT-EXPENSE', 'PRIVATE-VENDOR', 'PRIVATE-EXPENSE-NOTE', ARRAY[]::text[]),
 ('a1000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000002', '2026-06-01', 'fertilizer', 5000, 'USD', 'verified', 'PRIVATE-OTHER-LOCATION', 'PRIVATE-VENDOR', 'PRIVATE-EXPENSE-NOTE', ARRAY[]::text[]);
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'planning_budget', 'read', NULL, NULL);
"""


def acceptance_sql() -> str:
    return r"""
DO $$
DECLARE
    owner_organization uuid;
    eligible_plan_count integer;
BEGIN
    SELECT organization_id INTO owner_organization
      FROM public.location
     WHERE id = 'b0000000-0000-4000-8000-000000000001';
    IF owner_organization IS DISTINCT FROM 'b1000000-0000-4000-8000-000000000001'::uuid THEN
        RAISE EXCEPTION 'fixture location owner mapping is incorrect: %', owner_organization;
    END IF;
    SELECT count(DISTINCT plan.id) INTO eligible_plan_count
      FROM public.financial_plan AS plan
      JOIN public.location AS farm ON farm.organization_id = plan.organization_id
      JOIN public.budget_line AS line
        ON line.plan_id = plan.id AND line.location_id = farm.id
     WHERE farm.id = 'b0000000-0000-4000-8000-000000000001';
    IF eligible_plan_count <> 2 THEN
        RAISE EXCEPTION 'fixture expected two eligible plans before projection, found %', eligible_plan_count;
    END IF;
END $$;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    current_plan record;
    older_plan record;
    result_count integer;
    denied boolean := false;
    output_text text;
BEGIN
    SELECT * INTO current_plan FROM kokonut_security.list_location_budget_summaries(
        'b0000000-0000-4000-8000-000000000001', 51, 0
    ) WHERE financial_plan_id = 'c1000000-0000-4000-8000-000000000001';
    IF NOT FOUND THEN RAISE EXCEPTION 'active location budget plan was not projected'; END IF;
    IF current_plan.plan_status <> 'active'
       OR current_plan.currency <> 'USD'
       OR NOT current_plan.has_objective
       OR current_plan.budget_line_count <> 2
       OR current_plan.planned_amount <> 1200
       OR current_plan.verified_expense_amount <> 475.25
       OR current_plan.budget_variance <> 724.75
       OR current_plan.nonmatching_currency_expense_count <> 1
       OR current_plan.planning_scenario_count <> 2 THEN
        RAISE EXCEPTION 'location budget and same-currency verified actuals differ from fixture';
    END IF;
    SELECT * INTO older_plan FROM kokonut_security.list_location_budget_summaries(
        'b0000000-0000-4000-8000-000000000001', 1, 1
    );
    IF older_plan.financial_plan_id <> 'c1000000-0000-4000-8000-000000000002'::uuid THEN
        RAISE EXCEPTION 'budget summary pagination order is unstable';
    END IF;
    SELECT count(*), string_agg(financial_plan_id::text, ',')
      INTO result_count, output_text
      FROM kokonut_security.list_location_budget_summaries(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      );
    IF result_count <> 2 THEN
        RAISE EXCEPTION 'expected two location plans, got count % ids %', result_count, output_text;
    END IF;
    SELECT row_to_json(current_plan)::text INTO output_text;
    IF output_text LIKE ANY (ARRAY[
        '%PRIVATE-%', '%name%', '%objective_id%', '%category%', '%notes%',
        '%vendor%', '%assumption%', '%evidence%'
    ]) THEN RAISE EXCEPTION 'budget projection contains private plan or transaction detail'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_budget_summaries(
            'b0000000-0000-4000-8000-000000000002', 51, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_budget_summaries(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without planning_budget:read grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_budget_summaries(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invalid page bound was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.financial_plan;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read financial plans directly'; END IF;
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
     WHERE proc.oid = 'kokonut_security.list_location_budget_summaries(uuid,integer,integer)'::regprocedure;
    IF function_owner <> 'kokonut_planning_reader' OR NOT is_security_definer THEN
        RAISE EXCEPTION 'budget projection owner/security mode is incorrect';
    END IF;
    SELECT pg_get_function_result(
        'kokonut_security.list_location_budget_summaries(uuid,integer,integer)'::regprocedure
    ) INTO result_contract;
    IF result_contract LIKE ANY (ARRAY[
        '%name%', '%objective_id%', '%category%', '%notes%', '%vendor%',
        '%financial_transaction_id%', '%evidence_urls%', '%assumptions%'
    ]) THEN RAISE EXCEPTION 'budget projection signature contains private details'; END IF;
    IF has_table_privilege('kokonut_runtime', 'public.financial_plan', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.expense_event', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.financial_plan', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.list_location_budget_summaries(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime or Directus has unexpected direct budget access';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_budget_summaries(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime cannot execute the bounded budget projection';
    END IF;
    IF has_table_privilege('kokonut_planning_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_planning_reader', 'public.financial_plan', 'UPDATE')
       OR has_table_privilege('kokonut_planning_reader', 'public.expense_event', 'INSERT') THEN
        RAISE EXCEPTION 'planning reader role has identity or mutation privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-budget-read-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 455 applies and replays on disposable PostgreSQL 16",
        "only plans with location-assigned lines belonging to the location owner are returned",
        "planned totals, verified same-currency expense totals, variance, foreign-currency count, and scenarios match fixture",
        "organization-only lines and cross-organization/location plans are excluded",
        "exact signed location context, planning_budget:read, and bounded paging are enforced",
        "plan labels, categories, scenarios, and individual financial facts are excluded",
        "runtime and Directus receive no direct table reads; the reader role is non-login and read-only",
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
        stage = "base_budget_fixture"
        psql(docker, container, FIXTURE)
        psql(docker, container, planning_fixture())
        stage = "migration_455_apply_and_replay"
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        psql(docker, container, migration)
        stage = "authorization_scope_and_privilege_acceptance"
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
