#!/usr/bin/env python3
"""Exercise migration 450 on a disposable local PostgreSQL 16 container."""

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
wait_ready = _base.wait_ready

MIGRATION_449 = ROOT / "schemas/postgres/449_location_scoped_delphi_consultation_read.sql"
MIGRATION_450 = ROOT / "schemas/postgres/450_location_scoped_delphi_recommendation_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-027-delphi-recommendation-review-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        lines = (result.stderr or result.stdout).strip().splitlines()
        diagnostics = [
            line.strip() for line in lines
            if line.lstrip().startswith(("ERROR:", "DETAIL:", "HINT:", "CONTEXT:"))
        ]
        summary = " | ".join(diagnostics[-14:] or lines[-14:])
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]}: {summary[:1200]}"
        )
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )


def delphi_fixture() -> str:
    return r"""
CREATE TABLE public.delphi_study (
    id uuid PRIMARY KEY, location_id uuid, title text NOT NULL, description text,
    variation text NOT NULL, status text NOT NULL, stopping_criteria jsonb NOT NULL,
    opened_at timestamptz, closed_at timestamptz,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL
);
CREATE TABLE public.delphi_item (
    id uuid PRIMARY KEY, study_id uuid NOT NULL, item_type text NOT NULL,
    label text NOT NULL, description text, scale text NOT NULL,
    min_value numeric, max_value numeric, created_at timestamptz NOT NULL
);
CREATE TABLE public.delphi_panel_member (
    id uuid PRIMARY KEY, study_id uuid NOT NULL, participant_ref_id uuid,
    display_token text NOT NULL, consent_status text NOT NULL, expert_weight numeric NOT NULL
);
CREATE TABLE public.delphi_contribution (
    id uuid PRIMARY KEY, study_id uuid NOT NULL, item_id uuid NOT NULL,
    panel_member_id uuid NOT NULL, score numeric NOT NULL, reasoning text,
    updated_at timestamptz NOT NULL
);
CREATE TABLE public.delphi_recommendation (
    id uuid PRIMARY KEY, study_id uuid NOT NULL, summary text,
    recommendation_text text NOT NULL, status text NOT NULL DEFAULT 'draft',
    created_by uuid, approved_by uuid, approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.delphi_diversity_assessment (
    id uuid PRIMARY KEY, study_id uuid NOT NULL
);
CREATE TABLE public.delphi_minority_report (
    id uuid PRIMARY KEY, study_id uuid NOT NULL, rationale text NOT NULL,
    status text NOT NULL
);

INSERT INTO public.operator_identity VALUES
 ('a0000000-0000-4000-8000-000000000002', true),
 ('a0000000-0000-4000-8000-000000000003', true);
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', 'active'),
 ('b0000000-0000-4000-8000-000000000002', 'f0000000-0000-4000-8000-000000000001', 'active');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'read', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'review', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'read', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.delphi_study VALUES
 ('d0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'Eligible study', NULL, 'real_time', 'closed', '{}', NULL, NULL, clock_timestamp(), clock_timestamp()),
 ('d0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'No assessment study', NULL, 'real_time', 'closed', '{}', NULL, NULL, clock_timestamp(), clock_timestamp()),
 ('d0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000001', 'Minority review study', NULL, 'real_time', 'closed', '{}', NULL, NULL, clock_timestamp(), clock_timestamp()),
 ('d0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000002', 'Other location study', NULL, 'real_time', 'closed', '{}', NULL, NULL, clock_timestamp(), clock_timestamp());
INSERT INTO public.delphi_diversity_assessment VALUES
 ('e0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001'),
 ('e0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000003');
INSERT INTO public.delphi_minority_report VALUES
 ('e0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', 'private minority evidence', 'submitted');
INSERT INTO public.delphi_recommendation
 (id, study_id, summary, recommendation_text, status, created_by)
VALUES
 ('90000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'eligible summary', 'eligible draft', 'draft', 'a0000000-0000-4000-8000-000000000003'),
 ('90000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', 'self summary', 'self draft', 'draft', 'a0000000-0000-4000-8000-000000000002'),
 ('90000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000002', 'assessment summary', 'no assessment draft', 'draft', 'a0000000-0000-4000-8000-000000000003'),
 ('90000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000003', 'minority summary', 'open minority draft', 'draft', 'a0000000-0000-4000-8000-000000000003'),
 ('90000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000004', 'other location', 'other location draft', 'draft', 'a0000000-0000-4000-8000-000000000003');
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
    queued INTEGER;
    ready_count INTEGER;
    blocked_self BOOLEAN;
    blocked_diversity BOOLEAN;
    blocked_minority BOOLEAN;
    result RECORD;
    retry RECORD;
    denied BOOLEAN;
BEGIN
    SELECT count(*), count(*) FILTER (WHERE review_ready)
      INTO queued, ready_count
      FROM kokonut_security.list_location_delphi_recommendation_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      );
    IF queued <> 4 OR ready_count <> 1 THEN
        RAISE EXCEPTION 'review queue leaked other locations or readiness gates';
    END IF;
    SELECT 'self_review' = ANY(blocked_reasons) INTO blocked_self
      FROM kokonut_security.list_location_delphi_recommendation_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE recommendation_id = '90000000-0000-4000-8000-000000000002';
    SELECT 'diversity_assessment_required' = ANY(blocked_reasons) INTO blocked_diversity
      FROM kokonut_security.list_location_delphi_recommendation_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE recommendation_id = '90000000-0000-4000-8000-000000000003';
    SELECT 'minority_report_review_required' = ANY(blocked_reasons) INTO blocked_minority
      FROM kokonut_security.list_location_delphi_recommendation_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE recommendation_id = '90000000-0000-4000-8000-000000000004';
    IF NOT blocked_self OR NOT blocked_diversity OR NOT blocked_minority THEN
        RAISE EXCEPTION 'review queue did not identify all blocked decision paths';
    END IF;

    SELECT * INTO result
      FROM kokonut_security.decide_location_delphi_recommendation(
          'b0000000-0000-4000-8000-000000000001',
          '90000000-0000-4000-8000-000000000001', 'approve',
          'a0000000-0000-4000-8000-000000000101', 'approved_after_review'
      );
    SELECT * INTO retry
      FROM kokonut_security.decide_location_delphi_recommendation(
          'b0000000-0000-4000-8000-000000000001',
          '90000000-0000-4000-8000-000000000001', 'approve',
          'a0000000-0000-4000-8000-000000000101', 'approved_after_review'
      );
    IF result.review_id IS DISTINCT FROM retry.review_id
       OR result.resulting_status <> 'approved' THEN
        RAISE EXCEPTION 'identical approval retry did not return its original decision';
    END IF;
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_recommendation(
            'b0000000-0000-4000-8000-000000000001',
            '90000000-0000-4000-8000-000000000001', 'reject',
            'a0000000-0000-4000-8000-000000000101', 'other'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'request-key collision with changed payload was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_recommendation(
            'b0000000-0000-4000-8000-000000000001',
            '90000000-0000-4000-8000-000000000002', 'reject',
            'a0000000-0000-4000-8000-000000000102', 'other'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'creator was allowed to review their own draft'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_recommendation(
            'b0000000-0000-4000-8000-000000000001',
            '90000000-0000-4000-8000-000000000003', 'approve',
            'a0000000-0000-4000-8000-000000000103', 'approved_after_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'approval bypassed the diversity assessment gate'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_recommendation(
            'b0000000-0000-4000-8000-000000000001',
            '90000000-0000-4000-8000-000000000004', 'approve',
            'a0000000-0000-4000-8000-000000000104', 'approved_after_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'approval bypassed pending minority-report review'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_recommendation(
            'b0000000-0000-4000-8000-000000000001',
            '90000000-0000-4000-8000-000000000005', 'reject',
            'a0000000-0000-4000-8000-000000000105', 'other'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location recommendation was accessible'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_delphi_recommendation_reviews(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'read-only operator grant was accepted as reviewer'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.delphi_recommendation_review_decision;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private review history directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE blocked BOOLEAN := false;
BEGIN
    IF (SELECT count(*) FROM public.delphi_recommendation_review_decision) <> 1 THEN
        RAISE EXCEPTION 'identical retry duplicated the append-only decision';
    END IF;
    BEGIN
        UPDATE public.delphi_recommendation_review_decision SET reason_code = 'other';
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'review decision history can be updated'; END IF;
    blocked := false;
    BEGIN
        DELETE FROM public.delphi_recommendation_review_decision;
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'review decision history can be deleted'; END IF;
END $$;

DO $$
BEGIN
    IF has_table_privilege('kokonut_runtime', 'public.delphi_recommendation_review_decision', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_recommendation_review_decision', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_recommendation_review_decision', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus has direct access to private review history';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.decide_location_delphi_recommendation(uuid,uuid,text,uuid,text)',
        'EXECUTE'
    ) THEN RAISE EXCEPTION 'Gateway runtime cannot execute the bounded decision function'; END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-review-check-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 450 applies and replays without modifying the candidate or legacy database",
        "review queue is location-scoped and reports self-review, diversity, and minority blockers",
        "only a signed operator with an exact delphi:review grant can read or decide",
        "self-review, cross-location access, and missing reviewer grants fail closed",
        "approval requires a diversity assessment and no pending minority report",
        "approval and rejection remain human decisions; request retries are idempotent and collisions fail",
        "decision audit is private, append-only, and inaccessible by direct runtime or Directus SQL",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_450.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    stage = "container_start"
    try:
        run([docker, "run", "--rm", "--detach", "--name", container,
             "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "--publish", "127.0.0.1::5432", IMAGE])
        wait_ready(container, docker)
        stage = "base_fixture"
        psql(docker, container, FIXTURE)
        psql(docker, container, delphi_fixture())
        stage = "migration_449_apply_and_replay"
        sql_449 = MIGRATION_449.read_text(encoding="utf-8")
        psql(docker, container, sql_449)
        psql(docker, container, sql_449)
        stage = "migration_450_apply_and_replay"
        sql_450 = MIGRATION_450.read_text(encoding="utf-8")
        psql(docker, container, sql_450)
        psql(docker, container, sql_450)
        stage = "migration_privilege_preflight"
        evidence["privilege_preflight"] = psql(
            docker,
            container,
            """SELECT pg_get_userbyid(proc.proowner), proc.prosecdef,
                      has_table_privilege('kokonut_delphi_recommendation_reviewer',
                                          'public.delphi_study', 'SELECT'),
                      has_table_privilege('kokonut_delphi_recommendation_reviewer',
                                          'public.delphi_recommendation', 'SELECT'),
                      has_table_privilege('kokonut_delphi_recommendation_reviewer',
                                          'public.operator_scope_grant', 'SELECT')
                 FROM pg_catalog.pg_proc AS proc
                WHERE proc.oid = 'kokonut_security.list_location_delphi_recommendation_reviews(uuid,integer,integer)'::regprocedure;""",
        )
        evidence["reviewer_role_direct_read"] = psql(
            docker,
            container,
            "SET ROLE kokonut_delphi_recommendation_reviewer; SELECT current_user, count(*) FROM public.delphi_study; RESET ROLE;",
        )
        stage = "acceptance"
        psql(docker, container, acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - evidence records no connection strings or credentials
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
