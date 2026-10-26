#!/usr/bin/env python3
"""Apply/replay migration 521 and check AI-summary review boundaries on disposable PostgreSQL."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/521_location_scoped_ai_summary_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-038-ai-summary-review-disposable.json"
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
            line.strip()
            for line in lines
            if line.lstrip().startswith(("ERROR:", "DETAIL:", "HINT:", "CONTEXT:"))
        ]
        summary = " | ".join(diagnostics[-12:] or lines[-12:])
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


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not become ready")


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE directus NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE SCHEMA kokonut_security;
CREATE TABLE public.location (id uuid PRIMARY KEY);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY);
CREATE TABLE public.operator_scope_grant (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, revoked_at timestamptz
);
CREATE TABLE public.ai_summary (
    id uuid PRIMARY KEY, subject_type text NOT NULL, subject_id uuid NOT NULL,
    summary_type text, content text NOT NULL, source_tables text[],
    model_version text, status text NOT NULL DEFAULT 'draft', reviewed_by uuid,
    reviewed_at timestamptz, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by uuid,
    CONSTRAINT chk_ai_summary_agent_draft_only CHECK (
        created_by IS NULL OR status IN ('draft', 'submitted', 'rejected')
    )
);
CREATE TABLE public.lifecycle_transition (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), entity_type text NOT NULL,
    entity_id uuid NOT NULL, from_status text, to_status text NOT NULL,
    transitioned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor_id uuid, actor_type text
);
CREATE OR REPLACE FUNCTION public.fn_record_lifecycle_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IS NOT DISTINCT FROM NEW.status THEN RETURN NEW; END IF;
    INSERT INTO public.lifecycle_transition(entity_type, entity_id, from_status, to_status,
                                             actor_id, actor_type)
    VALUES (TG_TABLE_NAME, NEW.id, OLD.status, NEW.status,
            NULLIF(current_setting('kokonut.actor_id', true), '')::uuid,
            NULLIF(current_setting('kokonut.actor_type', true), ''));
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_lt_ai_summary AFTER UPDATE OF status ON public.ai_summary
FOR EACH ROW EXECUTE FUNCTION public.fn_record_lifecycle_transition();
CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(actor_id uuid, location_id uuid, actor_type text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT NULLIF(current_setting('kokonut.actor_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.location_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.actor_type', true), '')::text
$$;
CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id uuid, requested_resource text,
    requested_action text, requested_location_id uuid
) RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.operator_scope_grant AS grant_row
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
    )
$$;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime, directus;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
GRANT SELECT, UPDATE ON public.ai_summary TO kokonut_runtime, directus;
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001'),
 ('b0000000-0000-4000-8000-000000000002');
INSERT INTO public.operator_identity VALUES
 ('a0000000-0000-4000-8000-000000000001'),
 ('a0000000-0000-4000-8000-000000000002'),
 ('a0000000-0000-4000-8000-000000000003');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'ai_summary', 'review', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'ai_summary', 'read', NULL);
INSERT INTO public.ai_summary(id, subject_type, subject_id, summary_type, content,
                              source_tables, model_version, status, created_by)
VALUES
 ('c0000000-0000-4000-8000-000000000001', 'location', 'b0000000-0000-4000-8000-000000000001', 'operations', 'A valid reviewable summary.', ARRAY['farm_activity'], 'test-v1', 'draft', NULL),
 ('c0000000-0000-4000-8000-000000000002', 'location', 'b0000000-0000-4000-8000-000000000001', 'operations', '   ', ARRAY['farm_activity'], 'test-v1', 'draft', NULL),
 ('c0000000-0000-4000-8000-000000000003', 'location', 'b0000000-0000-4000-8000-000000000001', 'operations', 'No source lineage.', NULL, 'test-v1', 'draft', NULL),
 ('c0000000-0000-4000-8000-000000000004', 'location', 'b0000000-0000-4000-8000-000000000001', 'operations', repeat('x', 20001), ARRAY['farm_activity'], 'test-v1', 'draft', NULL),
 ('c0000000-0000-4000-8000-000000000005', 'location', 'b0000000-0000-4000-8000-000000000002', 'operations', 'Other location.', ARRAY['farm_activity'], 'test-v1', 'draft', NULL),
 ('c0000000-0000-4000-8000-000000000006', 'location', 'b0000000-0000-4000-8000-000000000001', 'operations', 'Attributed summary.', ARRAY['farm_activity'], 'test-v1', 'draft', 'a0000000-0000-4000-8000-000000000003'),
 ('c0000000-0000-4000-8000-000000000007', 'location', 'b0000000-0000-4000-8000-000000000001', 'operations', 'Submitted summary.', ARRAY['farm_activity'], 'test-v1', 'submitted', NULL);
"""


ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    queued integer;
    ready_count integer;
    blocked_empty boolean;
    blocked_lineage boolean;
    blocked_size boolean;
    approved record;
    retried record;
    denied boolean;
BEGIN
    SELECT count(*), count(*) FILTER (WHERE review_ready)
      INTO queued, ready_count
      FROM kokonut_security.list_location_ai_summary_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      );
    IF queued <> 5 OR ready_count <> 2 THEN
        RAISE EXCEPTION 'queue scope/readiness mismatch: %, %', queued, ready_count;
    END IF;
    SELECT 'empty_content' = ANY(blocked_reasons) INTO blocked_empty
      FROM kokonut_security.list_location_ai_summary_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE summary_id = 'c0000000-0000-4000-8000-000000000002';
    SELECT 'missing_source_lineage' = ANY(blocked_reasons) INTO blocked_lineage
      FROM kokonut_security.list_location_ai_summary_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE summary_id = 'c0000000-0000-4000-8000-000000000003';
    SELECT 'content_exceeds_review_limit' = ANY(blocked_reasons) INTO blocked_size
      FROM kokonut_security.list_location_ai_summary_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE summary_id = 'c0000000-0000-4000-8000-000000000004';
    IF NOT blocked_empty OR NOT blocked_lineage OR NOT blocked_size THEN
        RAISE EXCEPTION 'queue did not report all review blockers';
    END IF;

    SELECT * INTO approved
      FROM kokonut_security.decide_location_ai_summary_review(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001', 'approve',
        'd0000000-0000-4000-8000-000000000001', 'approved_after_review'
      );
    SELECT * INTO retried
      FROM kokonut_security.decide_location_ai_summary_review(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001', 'approve',
        'd0000000-0000-4000-8000-000000000001', 'approved_after_review'
      );
    IF approved.review_id IS DISTINCT FROM retried.review_id
       OR approved.resulting_status <> 'verified' THEN
        RAISE EXCEPTION 'exact approval retry was not idempotent';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001', 'reject',
            'd0000000-0000-4000-8000-000000000001', 'other'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-payload retry collision was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000002', 'approve',
            'd0000000-0000-4000-8000-000000000002', 'approved_after_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'blocked empty summary was approved'; END IF;

    SELECT * INTO approved
      FROM kokonut_security.decide_location_ai_summary_review(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000002', 'reject',
        'd0000000-0000-4000-8000-000000000003', 'insufficient_evidence'
      );
    IF approved.resulting_status <> 'rejected' THEN
        RAISE EXCEPTION 'rejection did not move the draft to rejected';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_ai_summary_reviews(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_ai_summary_reviews(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'read-only grant was accepted as reviewer'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.ai_summary_review_decision;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read review history directly'; END IF;

    denied := false;
    BEGIN
        UPDATE public.ai_summary SET status = 'verified'
         WHERE id = 'c0000000-0000-4000-8000-000000000007';
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can bypass the review function'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE blocked boolean := false;
BEGIN
    IF (SELECT count(*) FROM public.ai_summary_review_decision) <> 2 THEN
        RAISE EXCEPTION 'retry duplicated decision or final decision count is wrong';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.ai_summary
         WHERE id = 'c0000000-0000-4000-8000-000000000001'
           AND status = 'verified'
           AND reviewed_by = 'a0000000-0000-4000-8000-000000000001'
           AND reviewed_at IS NOT NULL
    ) THEN RAISE EXCEPTION 'verified decision attribution was not stored'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.lifecycle_transition
         WHERE entity_type = 'ai_summary'
           AND entity_id = 'c0000000-0000-4000-8000-000000000001'
           AND from_status = 'draft' AND to_status = 'verified'
           AND actor_id = 'a0000000-0000-4000-8000-000000000001'
           AND actor_type = 'operator'
    ) THEN RAISE EXCEPTION 'lifecycle transition did not record reviewer identity'; END IF;
    BEGIN
        UPDATE public.ai_summary_review_decision SET reason_code = 'other';
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'decision history can be updated'; END IF;
    blocked := false;
    BEGIN
        DELETE FROM public.ai_summary_review_decision;
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'decision history can be deleted'; END IF;
    IF has_table_privilege('kokonut_runtime', 'public.ai_summary', 'UPDATE')
       OR has_table_privilege('directus', 'public.ai_summary', 'UPDATE') THEN
        RAISE EXCEPTION 'runtime or Directus retains direct summary updates';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.ai_summary_review_decision', 'SELECT')
       OR has_table_privilege('directus', 'public.ai_summary_review_decision', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus can read private review history';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.decide_location_ai_summary_review(uuid,uuid,text,uuid,text)',
        'EXECUTE'
    ) THEN RAISE EXCEPTION 'runtime cannot execute bounded review function'; END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-ai-summary-review-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 521 applies and replays transactionally on disposable PostgreSQL 16",
        "queue is exact-location scoped and reports empty, missing-lineage, and over-limit blockers",
        "only signed operators with exact ai_summary:review grants can read and decide",
        "approval verifies but never publishes and records reviewer/lifecycle attribution",
        "rejection is recorded; blocked drafts cannot be approved",
        "exact retries replay and request-key payload collisions fail closed",
        "review history is append-only and inaccessible through direct runtime or Directus SQL",
        "runtime and Directus cannot bypass the bounded review function with direct summary UPDATE",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "synthetic_context_note": "SQL acceptance injects operator context directly in a no-network disposable fixture; Python regressions verify production service uses the signed context setter.",
        "checks": checks,
    }
    stage = "container_start"
    try:
        run(
            [
                docker,
                "run",
                "--rm",
                "--detach",
                "--name",
                container,
                "--network",
                "none",
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                IMAGE,
            ]
        )
        wait_ready(docker, container)
        stage = "fixture"
        psql(docker, container, FIXTURE)
        stage = "migration_apply_and_replay"
        sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, sql)
        psql(docker, container, sql)
        stage = "acceptance"
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - evidence records no credentials or connection strings
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
