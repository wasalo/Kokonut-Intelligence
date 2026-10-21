#!/usr/bin/env python3
"""Replay and check signed-worker AI-summary drafts on disposable PostgreSQL."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/check-ai-summary-review-disposable.py"
WORKER_FIXTURE = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
AI_SUMMARY_FIXTURE = ROOT / "tests/fixtures/agent_worker_ai_summary_disposable.sql"
MIGRATIONS = [
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/419_private_worker_context_functions.sql",
    ROOT / "schemas/postgres/521_location_scoped_ai_summary_review.sql",
    ROOT / "schemas/postgres/522_authenticated_ai_summary_drafts.sql",
    ROOT / "schemas/postgres/529_signed_agent_ai_summary_drafts.sql",
]
OUTPUT = ROOT / "docs/refactor/builds/2026-10-21-recovery/cap-038-agent-worker-draft-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
REQUEST_ID = "d0000000-0000-4000-8000-000000000901"
RAW_CREDENTIAL = "synthetic-agent-summary-worker-credential-2026-10-21"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


def _load_base():
    spec = importlib.util.spec_from_file_location("ai_summary_review_disposable", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the disposable PostgreSQL helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _worker_acceptance() -> str:
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{WORKER_ID}', 'agent-summary-draft');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'draft', 'synthetic acceptance fixture'
    );

    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE created RECORD;
            replayed RECORD;
            looked_up RECORD;
            denied BOOLEAN;
    BEGIN
        SELECT * INTO created
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'wellbeing', 'Worker-produced synthetic draft.',
              ARRAY['harvest_event', 'crop_cycle'], 'agent-v2', '{REQUEST_ID}'
          );
        IF created.summary_id IS NULL OR created.replayed
           OR created.resulting_status <> 'draft' THEN
            RAISE EXCEPTION 'first worker request did not create one draft';
        END IF;

        SELECT * INTO replayed
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'wellbeing', 'Changed generated text is ignored on exact request retry.',
              ARRAY['harvest_event', 'crop_cycle'], 'agent-v3', '{REQUEST_ID}'
          );
        IF replayed.summary_id IS DISTINCT FROM created.summary_id
           OR NOT replayed.replayed
           OR replayed.content IS DISTINCT FROM created.content THEN
            RAISE EXCEPTION 'exact request retry did not replay the original draft';
        END IF;

        SELECT * INTO looked_up
          FROM kokonut_security.get_location_ai_summary_worker_draft_request(
              '{LOCATION_ID}', 'wellbeing', '{REQUEST_ID}'
          );
        IF looked_up.summary_id IS DISTINCT FROM created.summary_id
           OR looked_up.content IS DISTINCT FROM created.content THEN
            RAISE EXCEPTION 'bounded retry lookup did not return the original draft';
        END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{LOCATION_ID}', 'operations', 'Conflicting intent.',
                ARRAY['harvest_event'], 'agent-v2', '{REQUEST_ID}'
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'request ID reuse for another intent was accepted'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{OTHER_LOCATION_ID}', 'wellbeing', 'Wrong location.',
                ARRAY['harvest_event'], 'agent-v2', 'd0000000-0000-4000-8000-000000000902'
            );
        EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker grant crossed its location boundary'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{LOCATION_ID}', 'wellbeing', 'Duplicate source metadata.',
                ARRAY['harvest_event', 'harvest_event'], 'agent-v2',
                'd0000000-0000-4000-8000-000000000903'
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'duplicate source metadata was accepted'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM count(*) FROM public.ai_summary_agent_draft_request;
        EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker execution role can read private receipts directly'; END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    INSERT INTO public.agent_worker_ai_summary_test_result (summary_id)
    SELECT summary_id
      FROM public.ai_summary_agent_draft_request
     WHERE worker_id = '{WORKER_ID}' AND request_id = '{REQUEST_ID}';
    """


def _review_context_fixture() -> str:
    return r"""
    CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
    RETURNS TABLE(tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
        SELECT NULLIF(current_setting('kokonut.tenant_id', TRUE), '')::UUID,
               NULLIF(current_setting('kokonut.location_id', TRUE), '')::UUID,
               NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID,
               NULLIF(current_setting('kokonut.actor_type', TRUE), '')::TEXT
    $$;
    """


def _review_acceptance() -> str:
    reviewer_id = "a0000000-0000-0000-0000-000000000902"
    return f"""
    SET ROLE kokonut_runtime;
    BEGIN;
    SELECT set_config('kokonut.tenant_id', '{TENANT_ID}', TRUE);
    SELECT set_config('kokonut.location_id', '{LOCATION_ID}', TRUE);
    SELECT set_config('kokonut.actor_id', '{reviewer_id}', TRUE);
    SELECT set_config('kokonut.actor_type', 'operator', TRUE);
    DO $$
    DECLARE queue_row RECORD;
            decision_row RECORD;
            worker_summary_id UUID;
            denied BOOLEAN;
    BEGIN
        SELECT summary_id INTO STRICT worker_summary_id
          FROM public.agent_worker_ai_summary_test_result;
        SELECT * INTO queue_row
          FROM kokonut_security.list_location_ai_summary_reviews('{LOCATION_ID}', 51, 0)
         WHERE summary_id = worker_summary_id;
        IF NOT FOUND OR NOT queue_row.review_ready
           OR 'creator_unattributed' = ANY(queue_row.blocked_reasons) THEN
            RAISE EXCEPTION 'worker-attributed draft was not reviewable';
        END IF;

        SELECT * INTO queue_row
          FROM kokonut_security.list_location_ai_summary_reviews('{LOCATION_ID}', 51, 0)
         WHERE summary_id = 'c0000000-0000-4000-8000-000000000099';
        IF NOT FOUND OR queue_row.review_ready
           OR NOT ('creator_unattributed' = ANY(queue_row.blocked_reasons)) THEN
            RAISE EXCEPTION 'legacy unattributed draft was not blocked';
        END IF;

        SELECT * INTO decision_row
          FROM kokonut_security.decide_location_ai_summary_review(
              '{LOCATION_ID}', worker_summary_id, 'approve',
              'd0000000-0000-4000-8000-000000000904', 'approved_after_review'
          );
        IF decision_row.resulting_status <> 'verified' THEN
            RAISE EXCEPTION 'human review did not stop at verified';
        END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
                '{LOCATION_ID}', 'c0000000-0000-4000-8000-000000000099', 'approve',
                'd0000000-0000-4000-8000-000000000905', 'approved_after_review'
            );
        EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'unattributed legacy draft was approved'; END IF;
    END;
    $$;
    COMMIT;

    RESET ROLE;
    DO $$
    DECLARE worker_summary_id UUID;
            denied BOOLEAN;
    BEGIN
        SELECT summary_id INTO STRICT worker_summary_id
          FROM public.agent_worker_ai_summary_test_result;
        IF NOT EXISTS (
            SELECT 1 FROM public.ai_summary
             WHERE id = worker_summary_id AND status = 'verified'
               AND reviewed_by = '{reviewer_id}' AND reviewed_at IS NOT NULL
               AND created_by IS NULL
               AND created_by_worker_id = '{WORKER_ID}'
        ) THEN RAISE EXCEPTION 'worker attribution or independent review was not persisted'; END IF;
        IF (SELECT count(*) FROM public.lifecycle_transition
             WHERE entity_id = worker_summary_id
               AND to_status = 'verified' AND actor_type = 'operator') <> 1 THEN
            RAISE EXCEPTION 'human lifecycle transition was not independently attributed';
        END IF;
        IF has_table_privilege('kokonut_worker_execution',
                               'public.ai_summary', 'INSERT')
           OR has_table_privilege('kokonut_agent_summary_draft_login',
                                  'public.ai_summary', 'INSERT')
           OR has_table_privilege('kokonut_runtime', 'public.ai_summary', 'UPDATE')
           OR has_table_privilege('directus', 'public.ai_summary', 'UPDATE') THEN
            RAISE EXCEPTION 'worker roles retained direct summary or review-update privileges';
        END IF;
        IF has_table_privilege('kokonut_runtime',
                               'public.ai_summary_agent_draft_request', 'SELECT')
           OR has_table_privilege('directus',
                                  'public.ai_summary_agent_draft_request', 'SELECT') THEN
            RAISE EXCEPTION 'runtime or Directus can read private worker receipts';
        END IF;
        IF has_function_privilege('kokonut_runtime',
            'kokonut_security.create_location_ai_summary_worker_draft(uuid,text,text,text[],text,uuid)',
            'EXECUTE') OR has_function_privilege('directus',
            'kokonut_security.create_location_ai_summary_worker_draft(uuid,text,text,text[],text,uuid)',
            'EXECUTE') THEN
            RAISE EXCEPTION 'runtime or Directus can execute the worker draft function';
        END IF;
        IF NOT has_function_privilege('kokonut_worker_execution',
            'kokonut_security.create_location_ai_summary_worker_draft(uuid,text,text,text[],text,uuid)',
            'EXECUTE') THEN
            RAISE EXCEPTION 'worker execution role lacks bounded draft function';
        END IF;

        denied := FALSE;
        BEGIN
            UPDATE public.ai_summary_agent_draft_request
               SET summary_type = 'tampered'
             WHERE worker_id = '{WORKER_ID}' AND request_id = '{REQUEST_ID}';
        EXCEPTION WHEN raise_exception THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker retry receipt update was accepted'; END IF;

        denied := FALSE;
        BEGIN
            DELETE FROM public.ai_summary_agent_draft_request
             WHERE worker_id = '{WORKER_ID}' AND request_id = '{REQUEST_ID}';
        EXCEPTION WHEN raise_exception THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker retry receipt deletion was accepted'; END IF;
    END $$;
    """


def main() -> int:
    base = _load_base()
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-agent-summary-worker-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 405, 419, 521, 522, and 529 apply; migration 529 replays",
        "signed worker credential grants only ai_summary:draft for the exact owned location",
        "worker draft is attributed to a database worker principal and exact request retries replay once",
        "conflicting request intent, mismatched location, and duplicate source metadata fail closed",
        "worker login/execution cannot write summaries directly; runtime and Directus cannot bypass review with direct UPDATE",
        "independent operator review sees the worker attribution and can verify only to verified",
        "legacy unattributed drafts remain blocked from approval; lifecycle review is operator-attributed",
        "runtime and Directus cannot call worker draft functions or read private worker receipts",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migrations": [path.name for path in MIGRATIONS],
        "database_target": "new disposable PostgreSQL 16 container with network disabled",
        "candidate_or_legacy_modified": False,
        "credential_note": "only a synthetic high-entropy credential is hashed in the disposable fixture",
        "review_context_note": "operator review uses a synthetic context stub in the disposable SQL fixture; production worker code uses the database-signed context helper",
        "source_lineage_note": "table names remain worker-declared hints; this does not add source-record manifests for legacy/background agents",
        "checks": checks,
    }
    stage = "container_start"
    try:
        base.run([
            docker, "run", "--rm", "--detach", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ])
        base.wait_ready(docker, container)
        stage = "worker_fixture_and_migrations_405_419"
        base.psql(docker, container, WORKER_FIXTURE.read_text(encoding="utf-8"))
        for migration_path in MIGRATIONS[:2]:
            sql = migration_path.read_text(encoding="utf-8")
            base.psql(docker, container, sql)
            base.psql(docker, container, sql)
        stage = "ai_summary_fixture_and_migrations_521_522_529"
        base.psql(docker, container, AI_SUMMARY_FIXTURE.read_text(encoding="utf-8"))
        for migration_path in MIGRATIONS[2:]:
            sql = migration_path.read_text(encoding="utf-8")
            base.psql(docker, container, sql)
            if migration_path.name.startswith("529_"):
                base.psql(docker, container, sql)
        stage = "signed_worker_acceptance"
        base.psql(docker, container, _worker_acceptance())
        stage = "synthetic_operator_review_acceptance"
        base.psql(docker, container, _review_context_fixture())
        base.psql(docker, container, _review_acceptance())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - no credential or connection string is recorded
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
