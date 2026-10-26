#!/usr/bin/env python3
"""Replay and exercise migration 632 on disposable local PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_lifecycle_path = ROOT / "scripts/check-delphi-study-lifecycle-disposable.py"
_lifecycle_spec = importlib.util.spec_from_file_location("delphi_lifecycle_disposable", _lifecycle_path)
if _lifecycle_spec is None or _lifecycle_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_lifecycle = importlib.util.module_from_spec(_lifecycle_spec)
_lifecycle_spec.loader.exec_module(_lifecycle)
_draft = _lifecycle._draft
_review = _draft._review

MIGRATION_632 = ROOT / "schemas/postgres/632_location_scoped_delphi_study_items.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-study-items-disposable.json"
IMAGE = "postgis/postgis:16-3.4"

run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.delphi_study
    (id, location_id, title, description, variation, status, stopping_criteria,
     opened_at, closed_at, created_at, updated_at, created_by, facilitator_type)
VALUES
    ('e3000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001', 'Item draft fixture',
     'Synthetic draft item test', 'real_time', 'draft',
     '{"max_duration_hours":720,"stability_pct":5,"min_participants":3,"iqr_threshold":1}',
     NULL, NULL, clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human'),
    ('e3000000-0000-4000-8000-000000000002',
     'b0000000-0000-4000-8000-000000000001', 'Item open fixture',
     'Synthetic open item test', 'real_time', 'open',
     '{"max_duration_hours":720,"stability_pct":5,"min_participants":3,"iqr_threshold":1}',
     clock_timestamp(), NULL, clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE created RECORD;
    retry RECORD;
    denied BOOLEAN := false;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_delphi_study_item(
        'b0000000-0000-4000-8000-000000000001',
        'e3000000-0000-4000-8000-000000000001', 'issue',
        'Water resilience', 'Compare adaptation options', 'probability', 0, 100,
        'e4000000-0000-4000-8000-000000000001'
    );
    IF created.location_id <> 'b0000000-0000-4000-8000-000000000001'
       OR created.study_id <> 'e3000000-0000-4000-8000-000000000001'
       OR created.item_type <> 'issue'
       OR created.label <> 'Water resilience'
       OR created.scale <> 'probability'
       OR created.min_value <> 0 OR created.max_value <> 100
       OR created.created_at IS NULL OR created.replayed THEN
        RAISE EXCEPTION 'created item fields or draft scope are incorrect';
    END IF;
    SELECT * INTO retry FROM kokonut_security.create_location_delphi_study_item(
        'b0000000-0000-4000-8000-000000000001',
        'e3000000-0000-4000-8000-000000000001', 'issue',
        'Water resilience', 'Compare adaptation options', 'probability', 0, 100,
        'e4000000-0000-4000-8000-000000000001'
    );
    IF retry.item_id IS DISTINCT FROM created.item_id OR NOT retry.replayed THEN
        RAISE EXCEPTION 'exact item request retry did not replay';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_item(
            'b0000000-0000-4000-8000-000000000001',
            'e3000000-0000-4000-8000-000000000001', 'issue',
            'Changed label', 'Compare adaptation options', 'probability', 0, 100,
            'e4000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed request content was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_item(
            'b0000000-0000-4000-8000-000000000002',
            'e3000000-0000-4000-8000-000000000001', 'issue',
            'Cross-location item', NULL, 'probability', 0, 100,
            'e4000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_item(
            'b0000000-0000-4000-8000-000000000001',
            'e3000000-0000-4000-8000-000000000002', 'issue',
            'Late item', NULL, 'probability', 0, 100,
            'e4000000-0000-4000-8000-000000000003'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'item was added after study opening'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_study_item(
            'b0000000-0000-4000-8000-000000000001',
            'e3000000-0000-4000-8000-000000000001', 'unreviewed',
            'Invalid item type', NULL, 'probability', 0, 100,
            'e4000000-0000-4000-8000-000000000004'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unsupported item type was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_study_item_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private item request receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE denied BOOLEAN := false;
    role_name TEXT;
    privilege_name TEXT;
BEGIN
    IF (SELECT count(*) FROM public.delphi_item
         WHERE study_id = 'e3000000-0000-4000-8000-000000000001') <> 1
       OR (SELECT count(*) FROM kokonut_security.delphi_study_item_request) <> 1 THEN
        RAISE EXCEPTION 'exact retry created duplicate item or receipt';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.delphi_item
         WHERE study_id = 'e3000000-0000-4000-8000-000000000001'
           AND (label <> 'Water resilience' OR item_type <> 'issue'
                OR scale <> 'probability' OR min_value <> 0 OR max_value <> 100)
    ) THEN
        RAISE EXCEPTION 'persisted item did not preserve normalized fields';
    END IF;
    BEGIN
        UPDATE kokonut_security.delphi_study_item_request
           SET payload_digest = public.digest('\x00'::bytea, 'sha256');
    EXCEPTION WHEN raise_exception THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'item request receipts permit update'; END IF;
    denied := false;
    BEGIN
        DELETE FROM kokonut_security.delphi_study_item_request;
    EXCEPTION WHEN raise_exception THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'item request receipts permit delete'; END IF;

    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        FOREACH privilege_name IN ARRAY ARRAY[
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
        ] LOOP
            IF has_table_privilege(
                role_name, 'kokonut_security.delphi_study_item_request', privilege_name
            ) THEN
                RAISE EXCEPTION '% has unexpected % access to item request receipts',
                    role_name, privilege_name;
            END IF;
        END LOOP;
    END LOOP;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_delphi_study_item(uuid,uuid,text,text,text,text,numeric,numeric,uuid)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_delphi_study_item(uuid,uuid,text,text,text,text,numeric,numeric,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'bounded item function role access is incorrect';
    END IF;
    IF (SELECT pg_catalog.pg_get_userbyid(proc.proowner)
          FROM pg_catalog.pg_proc AS proc
         WHERE proc.oid = 'kokonut_security.create_location_delphi_study_item(uuid,uuid,text,text,text,text,numeric,numeric,uuid)'::regprocedure)
       <> 'kokonut_delphi_item_drafter' THEN
        RAISE EXCEPTION 'item function does not use dedicated non-login owner';
    END IF;
    IF has_column_privilege(
        'kokonut_delphi_item_drafter', 'public.delphi_item', 'id', 'UPDATE'
    ) OR NOT has_column_privilege(
        'kokonut_delphi_item_drafter', 'public.delphi_item', 'label', 'INSERT'
    ) THEN
        RAISE EXCEPTION 'item drafter has unsafe direct item privileges';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-items-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451 and 630–632 apply and replay on disposable PostgreSQL 16",
        "bounded item creation stores normalized questions only under a current location delphi:draft grant",
        "exact request retries replay and changed-content reuse is rejected without duplicate rows",
        "cross-location scope, non-draft study status, and unsupported item type fail closed",
        "runtime and Directus cannot access immutable receipts or invoke the bounded item function",
        "the dedicated drafter role has only the required question insert and eligibility-read privileges",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_632.name,
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
        migrations = (
            ("449", _draft.MIGRATION_449),
            ("450", _draft.MIGRATION_450),
            ("451", _draft.MIGRATION_451),
            ("630", _draft.MIGRATION_630),
            ("631", _lifecycle.MIGRATION_631),
            ("632", MIGRATION_632),
        )
        for version, migration in migrations:
            stage = f"migration_{version}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        stage = "study_draft_acceptance"
        psql(docker, container, _draft.acceptance_sql())
        stage = "study_lifecycle_acceptance"
        psql(docker, container, _lifecycle.acceptance_sql())
        stage = "item_acceptance"
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
