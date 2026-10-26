#!/usr/bin/env python3
"""Exercise migration 630 on a disposable local PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_review_path = ROOT / "scripts/check-delphi-recommendation-review-disposable.py"
_review_spec = importlib.util.spec_from_file_location("delphi_review_disposable", _review_path)
if _review_spec is None or _review_spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_review = importlib.util.module_from_spec(_review_spec)
_review_spec.loader.exec_module(_review)

MIGRATION_449 = ROOT / "schemas/postgres/449_location_scoped_delphi_consultation_read.sql"
MIGRATION_450 = ROOT / "schemas/postgres/450_location_scoped_delphi_recommendation_review.sql"
MIGRATION_451 = ROOT / "schemas/postgres/451_location_scoped_delphi_recommendation_drafts.sql"
MIGRATION_630 = ROOT / "schemas/postgres/630_location_scoped_delphi_study_drafts.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-study-drafts-disposable.json"
IMAGE = "postgis/postgis:16-3.4"

run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'draft', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'read', 'f0000000-0000-4000-8000-000000000001', NULL);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE created RECORD;
    retry RECORD;
    denied BOOLEAN;
    criteria JSONB := '{"max_duration_hours":720,"stability_pct":5,"min_participants":3,"iqr_threshold":1}'::jsonb;
BEGIN
    SELECT * INTO created
      FROM kokonut_security.create_location_delphi_study_draft(
        'b0000000-0000-4000-8000-000000000001', 'Drought resilience',
        'Synthetic draft', 'real_time', 'agent', criteria,
        'c0000000-0000-4000-8000-000000000001'
      );
    IF created.status <> 'draft' OR created.replayed
       OR created.title <> 'Drought resilience' OR created.study_id IS NULL THEN
        RAISE EXCEPTION 'new study was not returned as a private draft';
    END IF;

    SELECT * INTO retry
      FROM kokonut_security.create_location_delphi_study_draft(
        'b0000000-0000-4000-8000-000000000001', 'Drought resilience',
        'Synthetic draft', 'real_time', 'agent', criteria,
        'c0000000-0000-4000-8000-000000000001'
      );
    IF retry.study_id IS DISTINCT FROM created.study_id OR NOT retry.replayed THEN
        RAISE EXCEPTION 'exact request retry did not return the original study';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_draft(
            'b0000000-0000-4000-8000-000000000001', 'Changed title',
            'Synthetic draft', 'real_time', 'agent', criteria,
            'c0000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-content request collision was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_draft(
            'b0000000-0000-4000-8000-000000000002', 'Cross-location',
            NULL, 'real_time', 'agent', criteria,
            'c0000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_draft(
            'b0000000-0000-4000-8000-000000000001', 'Invalid criteria',
            NULL, 'real_time', 'agent', '[]'::jsonb,
            'c0000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'non-object criteria were accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_study_draft_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private retry ledger directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
SET LOCAL ROLE kokonut_runtime;
DO $$
DECLARE denied BOOLEAN := false;
BEGIN
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_draft(
            'b0000000-0000-4000-8000-000000000001', 'Read-only operator',
            NULL, 'real_time', 'agent',
            '{"max_duration_hours":720,"stability_pct":5,"min_participants":3,"iqr_threshold":1}'::jsonb,
            'c0000000-0000-4000-8000-000000000004'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'delphi:read was accepted for draft creation'; END IF;
END $$;
ROLLBACK;
RESET ROLE;

DO $$
DECLARE denied BOOLEAN := false;
BEGIN
    IF (SELECT count(*) FROM public.delphi_study WHERE created_by IS NOT NULL) <> 1
       OR (SELECT count(*) FROM kokonut_security.delphi_study_draft_request) <> 1 THEN
        RAISE EXCEPTION 'retry created duplicate or unexpected Delphi study rows';
    END IF;
    IF EXISTS (SELECT 1 FROM public.delphi_study
                WHERE created_by IS NOT NULL
                  AND (status <> 'draft'
                       OR created_by <> 'a0000000-0000-4000-8000-000000000002')) THEN
        RAISE EXCEPTION 'draft creator or lifecycle status was not preserved';
    END IF;
    BEGIN
        UPDATE kokonut_security.delphi_study_draft_request
           SET payload_digest = pg_catalog.sha256('\x00'::bytea);
    EXCEPTION WHEN raise_exception THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'private request ledger permits update'; END IF;
    denied := false;
    BEGIN
        DELETE FROM kokonut_security.delphi_study_draft_request;
    EXCEPTION WHEN raise_exception THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'private request ledger permits delete'; END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'kokonut_security'
           AND table_name = 'delphi_study_draft_request'
           AND column_name IN ('request_payload', 'title', 'description')
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'kokonut_security'
           AND table_name = 'delphi_study_draft_request'
           AND column_name = 'payload_digest'
    ) THEN
        RAISE EXCEPTION 'private retry ledger stores request content rather than a digest';
    END IF;
END $$;

DO $$
DECLARE role_name TEXT;
    privilege_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        FOREACH privilege_name IN ARRAY ARRAY[
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
        ] LOOP
            IF has_table_privilege(
                role_name,
                'kokonut_security.delphi_study_draft_request',
                privilege_name
            ) THEN
                RAISE EXCEPTION '% has unexpected % access to private request ledger',
                    role_name, privilege_name;
            END IF;
        END LOOP;
    END LOOP;
    IF has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_delphi_study_draft(uuid,text,text,text,text,jsonb,uuid)',
        'EXECUTE'
    ) OR NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_delphi_study_draft(uuid,text,text,text,text,jsonb,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'bounded draft function role access is incorrect';
    END IF;
    IF (SELECT pg_get_userbyid(proc.proowner)
          FROM pg_catalog.pg_proc AS proc
         WHERE proc.oid = 'kokonut_security.create_location_delphi_study_draft(uuid,text,text,text,text,jsonb,uuid)'::regprocedure)
       <> 'kokonut_delphi_recommendation_drafter' THEN
        RAISE EXCEPTION 'function does not use its dedicated non-login owner';
    END IF;
    IF has_column_privilege(
        'kokonut_delphi_recommendation_drafter', 'public.delphi_study', 'status', 'UPDATE'
    ) OR NOT has_column_privilege(
        'kokonut_delphi_recommendation_drafter', 'public.delphi_study', 'status', 'INSERT'
    ) THEN
        RAISE EXCEPTION 'draft role can mutate lifecycle status after insert';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-study-drafts-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451 and 630 apply and replay on disposable PostgreSQL 16",
        "exact signed location and delphi:draft grant create only draft lifecycle state",
        "exact request retries return the same study and changed-content collisions fail closed",
        "mismatched location, read-only grant, and malformed criteria are rejected",
        "private retry records are append-only and inaccessible to runtime and Directus",
        "the bounded function is owned by the dedicated non-login drafter role",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_630.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    stage = "container_start"
    try:
        run([
            docker, "run", "--rm", "--detach", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ])
        wait_ready(container, docker)
        stage = "base_fixture"
        psql(docker, container, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        psql(docker, container, _review.FIXTURE)
        psql(docker, container, _review.delphi_fixture())
        psql(
            docker,
            container,
            "ALTER TABLE public.delphi_study ADD COLUMN created_by uuid; "
            "ALTER TABLE public.delphi_study ADD COLUMN facilitator_type varchar(20) NOT NULL DEFAULT 'agent'; "
            "ALTER TABLE public.delphi_study ALTER COLUMN created_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_study ALTER COLUMN updated_at SET DEFAULT clock_timestamp();",
        )
        for version, migration in (
            ("449", MIGRATION_449),
            ("450", MIGRATION_450),
            ("451", MIGRATION_451),
            ("630", MIGRATION_630),
        ):
            stage = f"migration_{version}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        stage = "acceptance"
        psql(docker, container, acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - synthetic-only failure evidence
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:1200]
    finally:
        subprocess.run(
            [docker, "rm", "--force", container], text=True, capture_output=True, check=False
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
