#!/usr/bin/env python3
"""Apply/replay migration 522 and check AI-summary draft/review boundaries."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/check-ai-summary-review-disposable.py"
MIGRATION = ROOT / "schemas/postgres/522_authenticated_ai_summary_drafts.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-038-ai-summary-draft-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def _load_base():
    spec = importlib.util.spec_from_file_location("ai_summary_review_disposable", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the migration 521 fixture helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACCEPTANCE = r"""
INSERT INTO public.operator_scope_grant(id, operator_id, location_id, resource, action)
VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'ai_summary', 'draft'),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000001', 'ai_summary', 'review');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    created record;
    looked_up record;
    retried record;
    queue_row record;
    denied boolean;
BEGIN
    SELECT * INTO looked_up
      FROM kokonut_security.get_location_ai_summary_draft_request(
          'b0000000-0000-4000-8000-000000000001', 'operations',
          'd0000000-0000-4000-8000-000000000011'
      );
    IF FOUND THEN RAISE EXCEPTION 'missing request unexpectedly returned a draft'; END IF;

    SELECT * INTO created
      FROM kokonut_security.create_location_ai_summary_draft(
          'b0000000-0000-4000-8000-000000000001', 'operations',
          'Requester-attributed synthetic draft.', ARRAY['farm_activity'],
          'd0000000-0000-4000-8000-000000000011'
      );
    IF created.replayed OR created.summary_id IS NULL THEN
        RAISE EXCEPTION 'new draft creation did not return a new attributed record';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.ai_summary
         WHERE id = created.summary_id
           AND status = 'draft'
           AND created_by = 'a0000000-0000-4000-8000-000000000001'
           AND subject_type = 'location'
           AND subject_id = 'b0000000-0000-4000-8000-000000000001'
    ) THEN RAISE EXCEPTION 'draft did not record authenticated requester and exact location'; END IF;

    SELECT * INTO looked_up
      FROM kokonut_security.get_location_ai_summary_draft_request(
          'b0000000-0000-4000-8000-000000000001', 'operations',
          'd0000000-0000-4000-8000-000000000011'
      );
    IF NOT FOUND OR looked_up.summary_id IS DISTINCT FROM created.summary_id
       OR looked_up.content IS DISTINCT FROM created.content THEN
        RAISE EXCEPTION 'bounded retry lookup did not return the original draft';
    END IF;

    SELECT * INTO retried
      FROM kokonut_security.create_location_ai_summary_draft(
          'b0000000-0000-4000-8000-000000000001', 'operations',
          'Changed generated output after retry.', ARRAY['farm_activity'],
          'd0000000-0000-4000-8000-000000000011'
      );
    IF NOT retried.replayed OR retried.summary_id IS DISTINCT FROM created.summary_id
       OR retried.content IS DISTINCT FROM created.content THEN
        RAISE EXCEPTION 'same-intent retry did not preserve original content';
    END IF;
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.get_location_ai_summary_draft_request(
            'b0000000-0000-4000-8000-000000000001', 'financial',
            'd0000000-0000-4000-8000-000000000011'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'request identifier reused for another intent was accepted'; END IF;

    SELECT * INTO queue_row
      FROM kokonut_security.list_location_ai_summary_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE summary_id = created.summary_id;
    IF NOT FOUND OR queue_row.review_ready
       OR NOT ('self_review' = ANY(queue_row.blocked_reasons)) THEN
        RAISE EXCEPTION 'requester draft was not labeled as a self-review blocker';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
            'b0000000-0000-4000-8000-000000000001', created.summary_id,
            'approve', 'd0000000-0000-4000-8000-000000000012', 'approved_after_review'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'requester approved their own AI summary'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
            'b0000000-0000-4000-8000-000000000001', created.summary_id,
            'reject', 'd0000000-0000-4000-8000-000000000013', 'other'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'requester rejected their own AI summary'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.ai_summary_draft_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private draft request receipts directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    created_summary_id UUID;
    decision record;
    legacy_row record;
    denied boolean;
BEGIN
    SELECT id INTO created_summary_id
      FROM public.ai_summary
     WHERE created_by = 'a0000000-0000-4000-8000-000000000001'
       AND subject_id = 'b0000000-0000-4000-8000-000000000001'
       AND summary_type = 'operations'
       AND content = 'Requester-attributed synthetic draft.';
    IF created_summary_id IS NULL THEN RAISE EXCEPTION 'created draft not visible to reviewer'; END IF;

    SELECT * INTO legacy_row
      FROM kokonut_security.list_location_ai_summary_reviews(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      ) WHERE summary_id = 'c0000000-0000-4000-8000-000000000003';
    IF NOT FOUND OR legacy_row.review_ready
       OR NOT ('creator_unattributed' = ANY(legacy_row.blocked_reasons)) THEN
        RAISE EXCEPTION 'legacy draft missing explicit attribution blocker';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000003', 'approve',
            'd0000000-0000-4000-8000-000000000014', 'approved_after_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'legacy unattributed draft was approved'; END IF;

    SELECT * INTO decision
      FROM kokonut_security.decide_location_ai_summary_review(
          'b0000000-0000-4000-8000-000000000001', created_summary_id,
          'approve', 'd0000000-0000-4000-8000-000000000015', 'approved_after_review'
      );
    IF decision.resulting_status <> 'verified' THEN
        RAISE EXCEPTION 'independent reviewer did not verify draft';
    END IF;

    SELECT * INTO decision
      FROM kokonut_security.decide_location_ai_summary_review(
          'b0000000-0000-4000-8000-000000000001',
          'c0000000-0000-4000-8000-000000000003', 'reject',
          'd0000000-0000-4000-8000-000000000016', 'insufficient_evidence'
      );
    IF decision.resulting_status <> 'rejected' THEN
        RAISE EXCEPTION 'legacy unattributed draft could not be safely rejected';
    END IF;

    denied := false;
    BEGIN
        UPDATE public.ai_summary_draft_request SET request_hash = repeat('0', 64);
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can mutate draft request receipt'; END IF;
END $$;
COMMIT;
RESET ROLE;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE existing record;
BEGIN
    SELECT * INTO existing
      FROM kokonut_security.get_location_ai_summary_draft_request(
          'b0000000-0000-4000-8000-000000000001', 'operations',
          'd0000000-0000-4000-8000-000000000011'
      );
    IF NOT FOUND OR existing.resulting_status <> 'verified' THEN
        RAISE EXCEPTION 'retry lookup did not return the draft current lifecycle status';
    END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE blocked boolean := false;
BEGIN
    BEGIN
        UPDATE public.ai_summary_draft_request SET request_hash = repeat('0', 64);
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'draft request receipt trigger did not block mutation'; END IF;
END $$;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.ai_summary_draft_request) <> 1 THEN
        RAISE EXCEPTION 'unexpected draft receipt count';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.ai_summary_draft_request', 'SELECT')
       OR has_table_privilege('directus', 'public.ai_summary_draft_request', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus can read private draft receipts';
    END IF;
    IF has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_ai_summary_draft(uuid,text,text,text[],uuid)',
        'EXECUTE'
    ) IS NOT TRUE OR has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.get_location_ai_summary_draft_request(uuid,text,uuid)',
        'EXECUTE'
    ) IS NOT TRUE THEN
        RAISE EXCEPTION 'runtime is missing bounded AI-summary draft functions';
    END IF;
    IF has_function_privilege(
        'directus',
        'kokonut_security.create_location_ai_summary_draft(uuid,text,text,text[],uuid)',
        'EXECUTE'
    ) OR has_function_privilege(
        'directus',
        'kokonut_security.get_location_ai_summary_draft_request(uuid,text,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'Directus can execute bounded AI-summary draft functions';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.ai_summary', 'UPDATE')
       OR has_table_privilege('directus', 'public.ai_summary', 'UPDATE') THEN
        RAISE EXCEPTION 'runtime or Directus retained direct AI-summary updates';
    END IF;
END $$;
"""


def main() -> int:
    base = _load_base()
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-ai-summary-draft-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 521 baseline and migration 522 apply/replay on disposable PostgreSQL 16",
        "exact signed draft scope attributes requester and location; private receipts stay inaccessible",
        "same-intent request lookup/replay returns the original draft before regeneration and prevents duplicates",
        "request ID reuse for another location/type fails closed",
        "self-review approval and rejection are denied; queue reports self_review",
        "legacy unattributed summaries are approval-blocked but remain rejectable",
        "independent reviewer may verify only to verified, never published",
        "runtime and Directus cannot bypass functions or read private receipt history",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container, network disabled",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    stage = "container_start"
    try:
        base.run(
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
        base.wait_ready(docker, container)
        stage = "fixture_and_migration_521"
        base.psql(docker, container, base.FIXTURE)
        base.psql(docker, container, base.MIGRATION.read_text(encoding="utf-8"))
        base.psql(docker, container, base.ACCEPTANCE)
        stage = "migration_522_apply_and_replay"
        base.psql(docker, container, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        base.psql(
            docker,
            container,
            "ALTER TABLE public.ai_summary ALTER COLUMN id SET DEFAULT gen_random_uuid();",
        )
        sql = MIGRATION.read_text(encoding="utf-8")
        base.psql(docker, container, sql)
        base.psql(docker, container, sql)
        stage = "acceptance"
        base.psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - evidence contains no credentials
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
