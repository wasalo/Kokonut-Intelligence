#!/usr/bin/env python3
"""Exercise migration 453 against a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load disposable PostgreSQL helper: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_identity = _load_script("identity_disposable", "check-stakeholder-identity-disposable.py")
_strategy = _load_script("strategy_disposable", "check-strategy-kernel-read-disposable.py")
run = _identity.run
psql = _identity.psql
wait_ready = _identity.wait_ready
FIXTURE = _identity.FIXTURE
MIGRATION = ROOT / "schemas/postgres/453_location_scoped_competitive_landscape_read.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-029-competitive-landscape-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def competitive_fixture() -> str:
    return r"""
CREATE TABLE public.competitive_landscape (
    id uuid PRIMARY KEY, strategy_plan_id uuid NOT NULL, scope_type text NOT NULL,
    scope_id uuid NOT NULL, industry text, geography text, period_start date NOT NULL,
    period_end date NOT NULL, status text NOT NULL, confidence text, summary text,
    created_by_party_id uuid, verified_by_party_id uuid, verified_at timestamptz,
    updated_at timestamptz NOT NULL
);
CREATE TABLE public.competitive_actor (
    id uuid PRIMARY KEY, landscape_id uuid NOT NULL, party_id uuid NOT NULL,
    actor_type text NOT NULL, position_summary text, threat_level text, evidence jsonb NOT NULL
);
CREATE TABLE public.competitive_force_observation (
    id uuid PRIMARY KEY, landscape_id uuid NOT NULL, pressure_score numeric NOT NULL,
    trend text NOT NULL, rationale text NOT NULL, evidence jsonb NOT NULL
);
CREATE TABLE public.competitive_signal (
    id uuid PRIMARY KEY, landscape_id uuid NOT NULL, materiality text NOT NULL,
    content text NOT NULL, source_ref text, reviewed_at timestamptz, evidence jsonb NOT NULL
);
CREATE TABLE public.strategy_advantage (
    id uuid PRIMARY KEY, strategy_plan_id uuid NOT NULL, name text NOT NULL,
    statement text NOT NULL, status text NOT NULL, defensibility_score numeric,
    evidence jsonb NOT NULL
);
CREATE TABLE public.strategy_advantage_outcome (
    id uuid PRIMARY KEY, advantage_id uuid NOT NULL, period_end date NOT NULL,
    status text NOT NULL, actual_value numeric, baseline_value numeric, evidence jsonb NOT NULL
);

INSERT INTO public.competitive_landscape VALUES
 ('11000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'Agroecology', 'Dominican Republic', '2026-01-01', '2026-12-31', 'verified', 'moderate', 'PRIVATE-LANDSCAPE-SUMMARY', NULL, NULL, NULL, clock_timestamp()),
 ('11000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'Agriculture', 'Dominican Republic', '2025-01-01', '2025-12-31', 'published', 'high', 'PRIVATE-OLDER-SUMMARY', NULL, NULL, NULL, clock_timestamp() - interval '1 year'),
 ('11000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000001', 'Cross-plan', 'Private', '2026-01-01', '2026-12-31', 'verified', 'high', 'PRIVATE-CROSS-PLAN', NULL, NULL, NULL, clock_timestamp()),
 ('11000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000004', 'organization', 'b0000000-0000-4000-8000-000000000001', 'Organization', 'Private', '2026-01-01', '2026-12-31', 'verified', 'high', 'PRIVATE-ORG-LANDSCAPE', NULL, NULL, NULL, clock_timestamp()),
 ('11000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000002', 'Other location', 'Private', '2026-01-01', '2026-12-31', 'verified', 'high', 'PRIVATE-OTHER-LOCATION', NULL, NULL, NULL, clock_timestamp());
INSERT INTO public.competitive_actor VALUES
 ('12000000-0000-4000-8000-000000000001', '11000000-0000-4000-8000-000000000001', '13000000-0000-4000-8000-000000000001', 'competitor', 'PRIVATE-ACTOR-NAME-ONE', 'critical', '[{"private":"actor evidence"}]'),
 ('12000000-0000-4000-8000-000000000002', '11000000-0000-4000-8000-000000000001', '13000000-0000-4000-8000-000000000002', 'supplier', 'PRIVATE-ACTOR-NAME-TWO', 'high', '[{"private":"actor evidence"}]'),
 ('12000000-0000-4000-8000-000000000003', '11000000-0000-4000-8000-000000000001', '13000000-0000-4000-8000-000000000003', 'partner', 'PRIVATE-ACTOR-NAME-THREE', 'low', '[]');
INSERT INTO public.competitive_force_observation VALUES
 ('14000000-0000-4000-8000-000000000001', '11000000-0000-4000-8000-000000000001', 80, 'worsening', 'PRIVATE-FORCE-RATIONALE', '[]'),
 ('14000000-0000-4000-8000-000000000002', '11000000-0000-4000-8000-000000000001', 60, 'stable', 'PRIVATE-FORCE-RATIONALE', '[]'),
 ('14000000-0000-4000-8000-000000000003', '11000000-0000-4000-8000-000000000001', 50, 'worsening', 'PRIVATE-FORCE-RATIONALE', '[]'),
 ('14000000-0000-4000-8000-000000000004', '11000000-0000-4000-8000-000000000001', 55, 'improving', 'PRIVATE-FORCE-RATIONALE', '[]');
INSERT INTO public.competitive_signal VALUES
 ('15000000-0000-4000-8000-000000000001', '11000000-0000-4000-8000-000000000001', 'critical', 'PRIVATE-SIGNAL-CONTENT', 'PRIVATE-SOURCE-REF', NULL, '[]'),
 ('15000000-0000-4000-8000-000000000002', '11000000-0000-4000-8000-000000000001', 'critical', 'PRIVATE-SIGNAL-CONTENT', 'PRIVATE-SOURCE-REF', clock_timestamp(), '[]'),
 ('15000000-0000-4000-8000-000000000003', '11000000-0000-4000-8000-000000000001', 'medium', 'PRIVATE-SIGNAL-CONTENT', 'PRIVATE-SOURCE-REF', NULL, '[]');
INSERT INTO public.strategy_advantage VALUES
 ('16000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'PRIVATE-ADVANTAGE-ONE', 'PRIVATE-ADVANTAGE-STATEMENT', 'verified', 80, '[]'),
 ('16000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 'PRIVATE-ADVANTAGE-TWO', 'PRIVATE-ADVANTAGE-STATEMENT', 'verified', 65, '[]'),
 ('16000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000001', 'PRIVATE-DRAFT-ADVANTAGE', 'PRIVATE-ADVANTAGE-STATEMENT', 'draft', 99, '[]');
INSERT INTO public.strategy_advantage_outcome VALUES
 ('17000000-0000-4000-8000-000000000001', '16000000-0000-4000-8000-000000000001', '2026-09-30', 'verified', 900.125, 500, '[{"private":"outcome evidence"}]'),
 ('17000000-0000-4000-8000-000000000002', '16000000-0000-4000-8000-000000000001', '2026-12-31', 'submitted', 1200, 500, '[]');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'competitive_landscape', 'read', NULL, NULL);
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
    current_row record;
    second_row record;
    row_count integer;
    denied boolean := false;
    private_output text;
BEGIN
    SELECT * INTO current_row
      FROM kokonut_security.list_location_competitive_landscape_summaries(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE landscape_id = '11000000-0000-4000-8000-000000000001';
    IF current_row.strategy_plan_id <> 'c0000000-0000-4000-8000-000000000001'::uuid
       OR current_row.industry <> 'Agroecology'
       OR current_row.landscape_status <> 'verified'
       OR current_row.actor_count <> 3
       OR current_row.high_or_critical_actor_count <> 2
       OR current_row.force_observation_count <> 4
       OR current_row.average_force_pressure <> 61.25
       OR current_row.worsening_force_count <> 2
       OR current_row.signal_count <> 3
       OR current_row.unreviewed_critical_signal_count <> 1
       OR current_row.verified_advantage_count <> 2
       OR current_row.average_verified_defensibility <> 72.5
       OR current_row.verified_advantage_outcome_count <> 1
       OR current_row.latest_verified_outcome_period_end <> '2026-09-30'::date THEN
        RAISE EXCEPTION 'competitive aggregate projection did not match scoped fixture';
    END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.list_location_competitive_landscape_summaries(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      );
    IF row_count <> 2 THEN RAISE EXCEPTION 'non-location, cross-plan, or cross-location rows leaked'; END IF;
    SELECT * INTO second_row
      FROM kokonut_security.list_location_competitive_landscape_summaries(
          'b0000000-0000-4000-8000-000000000001', 1, 1
      );
    IF second_row.landscape_id <> '11000000-0000-4000-8000-000000000002'::uuid THEN
        RAISE EXCEPTION 'competitive projection paging order is unstable';
    END IF;
    SELECT row_to_json(current_row)::text INTO private_output;
    IF private_output LIKE ANY (ARRAY[
        '%PRIVATE-%', '%party_id%', '%actual_value%', '%baseline_value%',
        '%position_summary%', '%rationale%', '%evidence%', '%source_ref%'
    ]) THEN RAISE EXCEPTION 'projection output contains private detail'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_competitive_landscape_summaries(
            'b0000000-0000-4000-8000-000000000002', 51, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_competitive_landscape_summaries(
            'b0000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without exact competitive read grant was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_competitive_landscape_summaries(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invalid page bound was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.competitive_landscape;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read competitive tables directly'; END IF;
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
     WHERE proc.oid = 'kokonut_security.list_location_competitive_landscape_summaries(uuid,integer,integer)'::regprocedure;
    IF function_owner <> 'kokonut_competitive_reader' OR NOT is_security_definer THEN
        RAISE EXCEPTION 'competitive projection owner/security mode is incorrect';
    END IF;
    SELECT pg_get_function_result(
        'kokonut_security.list_location_competitive_landscape_summaries(uuid,integer,integer)'::regprocedure
    ) INTO result_contract;
    IF result_contract LIKE ANY (ARRAY[
        '%party_id%', '%position_summary%', '%rationale%', '%evidence%', '%content%',
        '%source_ref%', '%actual_value%', '%baseline_value%', '%comparator_value%',
        '%statement%', '%owner_party_id%'
    ]) THEN RAISE EXCEPTION 'projection signature contains private details'; END IF;
    IF has_table_privilege('kokonut_runtime', 'public.competitive_landscape', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.competitive_actor', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.competitive_landscape', 'SELECT')
       OR has_function_privilege('kokonut_directus_runtime',
          'kokonut_security.list_location_competitive_landscape_summaries(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime or Directus has unexpected direct projection access';
    END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_competitive_landscape_summaries(uuid,integer,integer)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime cannot execute bounded competitive projection';
    END IF;
    IF has_table_privilege('kokonut_competitive_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_competitive_reader', 'public.strategy_advantage_outcome', 'INSERT')
       OR has_table_privilege('kokonut_competitive_reader', 'public.competitive_landscape', 'UPDATE') THEN
        RAISE EXCEPTION 'reader role has an unnecessary identity or mutation privilege';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-competitive-read-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 453 applies and replays on disposable PostgreSQL 16",
        "only same-location competitive landscapes and same-location strategy lineage are returned",
        "actor, Five Forces, signal, verified advantage, and verified outcome aggregates match synthetic fixture",
        "response excludes identity, evidence, narrative, and individual outcome values",
        "exact location grant, signed context, and bounded pagination are enforced",
        "runtime and Directus cannot read competitive tables directly or execute the projection through Directus",
        "dedicated reader role has only the function's declared read surface and no mutation privilege",
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
        stage = "base_strategy_and_competitive_fixture"
        psql(docker, container, FIXTURE)
        psql(docker, container, _strategy.strategy_fixture())
        psql(docker, container, competitive_fixture())
        stage = "migration_453_apply_and_replay"
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
