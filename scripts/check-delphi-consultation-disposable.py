#!/usr/bin/env python3
"""Exercise migration 449 on a disposable local PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_base_script = ROOT / "scripts/check-stakeholder-identity-disposable.py"
_base_spec = importlib.util.spec_from_file_location(
    "check_stakeholder_identity_disposable", _base_script
)
if _base_spec is None or _base_spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_base_module = importlib.util.module_from_spec(_base_spec)
_base_spec.loader.exec_module(_base_module)
FIXTURE = _base_module.FIXTURE
wait_ready = _base_module.wait_ready

MIGRATION = ROOT / "schemas/postgres/449_location_scoped_delphi_consultation_read.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-027-delphi-consultation-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        lines = (result.stderr or result.stdout).strip().splitlines()
        diagnostics = [
            line.strip() for line in lines
            if line.lstrip().startswith(("ERROR:", "DETAIL:", "HINT:", "CONTEXT:"))
        ]
        summary = " | ".join(diagnostics[-6:] or lines[-6:])
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]}: {summary[:1200]}"
        )
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=sql,
    )


def delphi_fixture_sql() -> str:
    location = "b0000000-0000-4000-8000-000000000001"
    other_location = "b0000000-0000-4000-8000-000000000002"
    operator = "a0000000-0000-4000-8000-000000000002"
    ungranted_operator = "a0000000-0000-4000-8000-000000000003"
    tenant = "f0000000-0000-4000-8000-000000000001"
    return f"""
CREATE TABLE public.delphi_study (
    id uuid PRIMARY KEY,
    location_id uuid,
    title text NOT NULL,
    description text,
    variation text NOT NULL,
    status text NOT NULL,
    stopping_criteria jsonb NOT NULL,
    opened_at timestamptz,
    closed_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE TABLE public.delphi_item (
    id uuid PRIMARY KEY,
    study_id uuid NOT NULL,
    item_type text NOT NULL,
    label text NOT NULL,
    description text,
    scale text NOT NULL,
    min_value numeric,
    max_value numeric,
    created_at timestamptz NOT NULL
);
CREATE TABLE public.delphi_panel_member (
    id uuid PRIMARY KEY,
    study_id uuid NOT NULL,
    participant_ref_id uuid,
    display_token text NOT NULL,
    consent_status text NOT NULL,
    expert_weight numeric NOT NULL
);
CREATE TABLE public.delphi_contribution (
    id uuid PRIMARY KEY,
    study_id uuid NOT NULL,
    item_id uuid NOT NULL,
    panel_member_id uuid NOT NULL,
    score numeric NOT NULL,
    reasoning text,
    updated_at timestamptz NOT NULL
);
CREATE TABLE public.delphi_recommendation (
    id uuid PRIMARY KEY,
    study_id uuid NOT NULL,
    recommendation_text text NOT NULL
);
CREATE TABLE public.delphi_minority_report (
    id uuid PRIMARY KEY,
    study_id uuid NOT NULL,
    rationale text NOT NULL
);
INSERT INTO public.operator_identity VALUES ('{operator}', true), ('{ungranted_operator}', true);
INSERT INTO public.location VALUES ('{location}', '{tenant}', 'active'), ('{other_location}', '{tenant}', 'active');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), '{operator}', '{location}', 'delphi', 'read', '{tenant}', NULL);
INSERT INTO public.delphi_study VALUES
 ('d0000000-0000-4000-8000-000000000001', '{location}', 'Synthetic Soil Priorities', 'Non-sensitive fixture', 'real_time', 'open', '{{"min_participants":2,"iqr_threshold":1.0}}', NULL, NULL, clock_timestamp(), clock_timestamp()),
 ('d0000000-0000-4000-8000-000000000002', '{other_location}', 'Other Location Study', NULL, 'real_time', 'open', '{{"min_participants":3}}', NULL, NULL, clock_timestamp(), clock_timestamp()),
 ('d0000000-0000-4000-8000-000000000003', NULL, 'Unassigned Legacy Study', NULL, 'real_time', 'open', '{{"min_participants":3}}', NULL, NULL, clock_timestamp(), clock_timestamp());
INSERT INTO public.delphi_item VALUES
 ('e0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'goal', 'Tree cover priority', NULL, 'desirability', 0, 5, clock_timestamp()),
 ('e0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'goal', 'Water retention priority', NULL, 'desirability', 0, 5, clock_timestamp());
INSERT INTO public.delphi_panel_member VALUES
 ('c0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', gen_random_uuid(), 'PRIVATE-TOKEN-ALPHA', 'granted', 5.0),
 ('c0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', gen_random_uuid(), 'PRIVATE-TOKEN-BETA', 'granted', 1.0),
 ('c0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000001', gen_random_uuid(), 'PRIVATE-TOKEN-GAMMA', 'granted', 1.0),
 ('c0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001', gen_random_uuid(), 'PRIVATE-TOKEN-PENDING', 'pending', 1.0),
 ('c0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000001', gen_random_uuid(), 'PRIVATE-TOKEN-WITHDRAWN', 'withdrawn', 1.0);
INSERT INTO public.delphi_contribution VALUES
 ('f0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 1, 'RAW-REASONING-SECRET', clock_timestamp()),
 ('f0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000002', 2, 'RAW-REASONING-SECRET', clock_timestamp()),
 ('f0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000003', 3, 'RAW-REASONING-SECRET', clock_timestamp()),
 ('f0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000004', 5, 'PENDING-REASONING-SECRET', clock_timestamp()),
 ('f0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000005', 5, 'WITHDRAWN-REASONING-SECRET', clock_timestamp()),
 ('f0000000-0000-4000-8000-000000000006', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 1, 'SUPPRESSED-SECRET', clock_timestamp()),
 ('f0000000-0000-4000-8000-000000000007', 'd0000000-0000-4000-8000-000000000001', 'e0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000002', 2, 'SUPPRESSED-SECRET', clock_timestamp());
INSERT INTO public.delphi_recommendation VALUES
 ('90000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'PRIVATE-RECOMMENDATION');
INSERT INTO public.delphi_minority_report VALUES
 ('90000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'PRIVATE-MINORITY-REPORT');
"""


def acceptance_sql() -> str:
    operator = "a0000000-0000-4000-8000-000000000002"
    ungranted_operator = "a0000000-0000-4000-8000-000000000003"
    location = "b0000000-0000-4000-8000-000000000001"
    other_location = "b0000000-0000-4000-8000-000000000002"
    tenant = "f0000000-0000-4000-8000-000000000001"
    return f"""
SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{operator}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    result JSONB;
    study_rows INTEGER;
    item JSONB;
BEGIN
    SELECT jsonb_agg(to_jsonb(consultation)) INTO result
      FROM kokonut_security.list_location_delphi_consultations('{location}', 51, 0) AS consultation;
    IF jsonb_array_length(result) <> 1 THEN
        RAISE EXCEPTION 'projection returned a study outside the signed location';
    END IF;
    IF result::TEXT LIKE '%PRIVATE-TOKEN-%'
       OR result::TEXT LIKE '%RAW-REASONING-SECRET%'
       OR result::TEXT LIKE '%PENDING-REASONING-SECRET%'
       OR result::TEXT LIKE '%WITHDRAWN-REASONING-SECRET%'
       OR result::TEXT LIKE '%PRIVATE-RECOMMENDATION%'
       OR result::TEXT LIKE '%PRIVATE-MINORITY-REPORT%' THEN
        RAISE EXCEPTION 'projection exposed participant identity, reasoning, or draft content';
    END IF;
    SELECT item_value INTO item
      FROM jsonb_array_elements(result -> 0 -> 'items') AS item_rows(item_value)
     WHERE item_value ->> 'label' = 'Tree cover priority';
    IF item ->> 'results_available' <> 'true'
       OR item ->> 'participant_count' <> '3'
       OR (item ->> 'median')::NUMERIC <> 2
       OR (item ->> 'interquartile_range')::NUMERIC <> 1
       OR (item ->> 'mean')::NUMERIC <> 2
       OR (item ->> 'weighted_median')::NUMERIC <> 1 THEN
        RAISE EXCEPTION 'consent-aware aggregate included wrong participants or values';
    END IF;
    SELECT item_value INTO item
      FROM jsonb_array_elements(result -> 0 -> 'items') AS item_rows(item_value)
     WHERE item_value ->> 'label' = 'Water retention priority';
    IF item ->> 'results_available' <> 'false'
       OR item ? 'participant_count' AND item -> 'participant_count' <> 'null'::JSONB
       OR item ? 'median' AND item -> 'median' <> 'null'::JSONB THEN
        RAISE EXCEPTION 'small-group statistics were not suppressed';
    END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{ungranted_operator}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied BOOLEAN := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.list_location_delphi_consultations('{location}', 10, 0);
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'projection ignored its distinct location grant'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{other_location}', true);
SELECT set_config('kokonut.actor_id', '{operator}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied BOOLEAN := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.list_location_delphi_consultations('{location}', 10, 0);
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'projection accepted mismatched signed location'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{operator}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied BOOLEAN := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.list_location_delphi_consultations('{location}', 52, 0);
  EXCEPTION WHEN invalid_parameter_value THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'projection accepted an unbounded page size'; END IF;
  denied := false;
  BEGIN
    PERFORM * FROM kokonut_security.list_location_delphi_consultations('{location}', 10, 10001);
  EXCEPTION WHEN invalid_parameter_value THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'projection accepted an unbounded page offset'; END IF;
END $$;
COMMIT;

RESET ROLE;
DO $$ BEGIN
  IF has_table_privilege('kokonut_delphi_consultation_reader', 'public.delphi_recommendation', 'SELECT')
     OR has_table_privilege('kokonut_delphi_consultation_reader', 'public.delphi_minority_report', 'SELECT') THEN
    RAISE EXCEPTION 'reader role can select facilitator or minority-report content';
  END IF;
  IF EXISTS (
      SELECT 1
        FROM pg_catalog.pg_proc AS function_row,
             LATERAL aclexplode(coalesce(
                 function_row.proacl,
                 acldefault('f', function_row.proowner)
             )) AS privilege
       WHERE function_row.oid =
           'kokonut_security.list_location_delphi_consultations(uuid,integer,integer)'::regprocedure
         AND privilege.grantee = 0
         AND privilege.privilege_type = 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'projection function is executable by PUBLIC';
  END IF;
  IF has_table_privilege('kokonut_delphi_consultation_reader', 'public.delphi_study', 'INSERT')
     OR has_table_privilege('kokonut_delphi_consultation_reader', 'public.delphi_contribution', 'UPDATE')
     OR has_table_privilege('kokonut_delphi_consultation_reader', 'public.delphi_panel_member', 'DELETE') THEN
    RAISE EXCEPTION 'reader role has direct Delphi mutation privileges';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_proc
       WHERE oid = 'kokonut_security.list_location_delphi_consultations(uuid,integer,integer)'::regprocedure
         AND provolatile = 's'
  ) THEN
    RAISE EXCEPTION 'projection function is not marked STABLE';
  END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-delphi-disposable-{uuid.uuid4().hex[:10]}"
    checks = [
        "migration applies and replays cleanly",
        "only the signed location's studies are returned",
        "current consent filters pending and withdrawn panel members",
        "group statistics are suppressed below max(3, configured minimum)",
        "participant references, display tokens, reasoning, and drafts are excluded",
        "location grant and signed context are mandatory",
        "function page bounds are enforced and PUBLIC execute is revoked",
        "reader role is read-only and cannot select recommendations or minority reports",
        "projection function is STABLE",
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
        stage = "base_fixture"
        psql(docker, container, FIXTURE)
        stage = "delphi_fixture"
        psql(docker, container, delphi_fixture_sql())
        stage = "migration_apply"
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        stage = "migration_replay"
        psql(docker, container, migration_sql)
        stage = "acceptance"
        psql(docker, container, acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - evidence stores only safe failure metadata
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:1200]
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
