#!/usr/bin/env python3
"""Apply/replay migration 640 and exercise its private review boundary on disposable PG16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_helper_path = ROOT / "scripts/check-stakeholder-identity-disposable.py"
_helper_spec = importlib.util.spec_from_file_location("identity_disposable", _helper_path)
if _helper_spec is None or _helper_spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_helper = importlib.util.module_from_spec(_helper_spec)
_helper_spec.loader.exec_module(_helper)
wait_ready = _helper.wait_ready

MIGRATION = ROOT / "schemas/postgres/640_location_scoped_delphi_minority_report_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-minority-review-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        lines = (result.stderr or result.stdout).strip().splitlines()
        detail = " | ".join(line.strip() for line in lines if line.startswith(("ERROR:", "DETAIL:", "HINT:", "CONTEXT:")))
        raise RuntimeError(f"command failed ({result.returncode}): {detail[:1200] or 'see command output'}")
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_delphi_recommendation_reviewer NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA kokonut_security;
CREATE TABLE public.location (id uuid PRIMARY KEY);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY);
CREATE TABLE public.operator_scope_grant (
  id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
  resource text NOT NULL, action text NOT NULL, revoked_at timestamptz
);
CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(tenant_id uuid, location_id uuid, actor_id uuid, actor_type text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
  SELECT NULLIF(current_setting('kokonut.tenant_id', true), '')::uuid,
         NULLIF(current_setting('kokonut.location_id', true), '')::uuid,
         NULLIF(current_setting('kokonut.actor_id', true), '')::uuid,
         NULLIF(current_setting('kokonut.actor_type', true), '')::text
$$;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
  requested_operator_id uuid, requested_resource text, requested_action text,
  requested_location_id uuid
) RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER AS $$
  SELECT EXISTS (SELECT 1 FROM public.operator_scope_grant AS grant_row
    WHERE grant_row.operator_id = requested_operator_id
      AND grant_row.resource = requested_resource
      AND grant_row.action = requested_action
      AND grant_row.location_id = requested_location_id
      AND grant_row.revoked_at IS NULL)
$$;
CREATE TABLE public.delphi_study (
  id uuid PRIMARY KEY, location_id uuid NOT NULL REFERENCES public.location(id), title text NOT NULL
);
CREATE TABLE public.delphi_item (
  id uuid PRIMARY KEY, study_id uuid NOT NULL REFERENCES public.delphi_study(id), label text NOT NULL
);
CREATE TABLE public.delphi_panel_member (
  id uuid PRIMARY KEY, study_id uuid NOT NULL REFERENCES public.delphi_study(id),
  consent_status text NOT NULL
);
CREATE TABLE public.delphi_minority_report (
  id uuid PRIMARY KEY, study_id uuid NOT NULL REFERENCES public.delphi_study(id),
  item_id uuid REFERENCES public.delphi_item(id), title text NOT NULL,
  position_summary text NOT NULL, rationale text NOT NULL, implications text,
  status text NOT NULL CHECK (status IN ('draft','submitted','verified','published','rejected')),
  created_by_panel_member_id uuid REFERENCES public.delphi_panel_member(id),
  submitted_at timestamptz, verified_by uuid, verified_at timestamptz,
  verification_notes text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001'),
 ('b0000000-0000-4000-8000-000000000002');
INSERT INTO public.operator_identity VALUES ('a0000000-0000-4000-8000-000000000001');
INSERT INTO public.operator_scope_grant VALUES
 ('c0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001',
  'b0000000-0000-4000-8000-000000000001', 'delphi', 'review', NULL);
INSERT INTO public.delphi_study VALUES
 ('d0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'Review study'),
 ('d0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'Other location study');
INSERT INTO public.delphi_item VALUES
 ('e0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'Water');
INSERT INTO public.delphi_panel_member VALUES
 ('f0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'granted'),
 ('f0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'withdrawn'),
 ('f0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000002', 'granted');
INSERT INTO public.delphi_minority_report
 (id, study_id, item_id, title, position_summary, rationale, implications, status,
  created_by_panel_member_id, submitted_at)
VALUES
 ('90000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001',
  'e0000000-0000-4000-8000-000000000001', 'Active report', 'Position A', 'Evidence A',
  'Implications A', 'submitted', 'f0000000-0000-4000-8000-000000000001', clock_timestamp()),
 ('90000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001',
  NULL, 'Withdrawn report', 'Position B', 'Evidence B', 'Implications B', 'submitted',
  'f0000000-0000-4000-8000-000000000002', clock_timestamp()),
 ('90000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000002',
  NULL, 'Other location report', 'Position C', 'Evidence C', 'Implications C', 'submitted',
  'f0000000-0000-4000-8000-000000000003', clock_timestamp()),
 ('90000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001',
  NULL, 'Active rejection report', 'Position D', 'Evidence D', 'Implications D', 'submitted',
  'f0000000-0000-4000-8000-000000000001', clock_timestamp()),
 ('90000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000001',
  NULL, 'Unlinked report', 'Position E', 'Evidence E', 'Implications E', 'submitted',
  NULL, clock_timestamp());
"""


ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'b0000000-0000-4000-8000-000000000000', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE count_visible integer; row_result record; retry_result record; denied boolean;
BEGIN
  SELECT count(*) INTO count_visible FROM kokonut_security.list_location_delphi_minority_reports(
    'b0000000-0000-4000-8000-000000000001', 51, 0);
  IF count_visible <> 2 THEN RAISE EXCEPTION 'queue did not filter withdrawn, unlinked, or cross-location reports'; END IF;
  SELECT * INTO row_result FROM kokonut_security.list_location_delphi_minority_reports(
    'b0000000-0000-4000-8000-000000000001', 51, 0);
  IF row_result.report_id <> '90000000-0000-4000-8000-000000000001'
     OR row_result.study_title <> 'Review study' THEN RAISE EXCEPTION 'wrong report returned'; END IF;
  SELECT * INTO row_result FROM kokonut_security.decide_location_delphi_minority_report(
    'b0000000-0000-4000-8000-000000000001', '90000000-0000-4000-8000-000000000001',
    'verified', 'a1000000-0000-4000-8000-000000000001', 'evidence_considered');
  SELECT * INTO retry_result FROM kokonut_security.decide_location_delphi_minority_report(
    'b0000000-0000-4000-8000-000000000001', '90000000-0000-4000-8000-000000000001',
    'verified', 'a1000000-0000-4000-8000-000000000001', 'evidence_considered');
  IF row_result.review_id IS DISTINCT FROM retry_result.review_id
     OR row_result.resulting_status <> 'verified' THEN RAISE EXCEPTION 'retry changed decision'; END IF;
  SELECT * INTO row_result FROM kokonut_security.decide_location_delphi_minority_report(
    'b0000000-0000-4000-8000-000000000001', '90000000-0000-4000-8000-000000000004',
    'rejected', 'a1000000-0000-4000-8000-000000000004', 'out_of_scope');
  IF row_result.resulting_status <> 'rejected' THEN RAISE EXCEPTION 'rejection status mismatch'; END IF;
  denied := false;
  BEGIN
    PERFORM * FROM kokonut_security.decide_location_delphi_minority_report(
      'b0000000-0000-4000-8000-000000000001', '90000000-0000-4000-8000-000000000001',
      'rejected', 'a1000000-0000-4000-8000-000000000001', 'other');
  EXCEPTION WHEN SQLSTATE '22023' THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'request-key collision accepted'; END IF;
  denied := false;
  BEGIN
    PERFORM * FROM kokonut_security.decide_location_delphi_minority_report(
      'b0000000-0000-4000-8000-000000000002', '90000000-0000-4000-8000-000000000003',
      'verified', 'a1000000-0000-4000-8000-000000000002', 'evidence_considered');
  EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'cross-location context was accepted'; END IF;
  PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000009', true);
  denied := false;
  BEGIN
    PERFORM * FROM kokonut_security.list_location_delphi_minority_reports(
      'b0000000-0000-4000-8000-000000000001', 51, 0);
  EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'operator without a review grant was accepted'; END IF;
  PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
  denied := false;
  BEGIN
    PERFORM * FROM kokonut_security.decide_location_delphi_minority_report(
      'b0000000-0000-4000-8000-000000000001', '90000000-0000-4000-8000-000000000002',
      'verified', 'a1000000-0000-4000-8000-000000000003', 'evidence_considered');
  EXCEPTION WHEN SQLSTATE '55000' THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'withdrawn participant report was reviewable'; END IF;
  denied := false;
  BEGIN SELECT 1 FROM public.delphi_minority_report_review_decision;
  EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'runtime can read private review ledger directly'; END IF;
END $$;
COMMIT;
RESET ROLE;
DO $$ DECLARE denied boolean := false; BEGIN
  IF (SELECT count(*) FROM public.delphi_minority_report_review_decision) <> 2 THEN
    RAISE EXCEPTION 'idempotent retry duplicated review ledger or rejection was not recorded';
  END IF;
  IF (SELECT verified_by FROM public.delphi_minority_report
       WHERE id = '90000000-0000-4000-8000-000000000004') IS NOT NULL
     OR (SELECT status FROM public.delphi_minority_report
          WHERE id = '90000000-0000-4000-8000-000000000004') <> 'rejected' THEN
    RAISE EXCEPTION 'rejection was recorded as a positive verification';
  END IF;
  BEGIN UPDATE public.delphi_minority_report_review_decision SET reason_code = 'other';
  EXCEPTION WHEN raise_exception THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'decision ledger allows update'; END IF;
  denied := false;
  BEGIN DELETE FROM public.delphi_minority_report_review_decision;
  EXCEPTION WHEN raise_exception THEN denied := true; END;
  IF NOT denied THEN RAISE EXCEPTION 'decision ledger allows delete'; END IF;
  IF has_table_privilege('kokonut_runtime', 'public.delphi_minority_report_review_decision', 'SELECT')
     OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_minority_report_review_decision', 'SELECT')
     OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.decide_location_delphi_minority_report(uuid,uuid,text,uuid,text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'runtime or Directus has an unsafe direct boundary';
  END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-minority-check-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 640 applies and replays on a disposable PostgreSQL 16 database",
        "queue returns only submitted reports with active participant consent in the exact location",
        "signed operator scope, verified decision, and exact retry are enforced",
        "request collisions, cross-location access, and withdrawn-report decisions fail closed",
        "review ledger is append-only and inaccessible to runtime and Directus roles",
    ]
    evidence: dict[str, object] = {
        "result": "failed", "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False, "checks": checks,
    }
    stage = "container_start"
    try:
        run([docker, "run", "--rm", "--detach", "--name", container, "--network", "none",
             "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE])
        wait_ready(container, docker)
        stage = "fixture"
        psql(docker, container, FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        stage = "migration_apply_and_replay"
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        stage = "acceptance"
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - evidence excludes credentials and DSNs
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:1200]
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
