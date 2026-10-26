#!/usr/bin/env python3
"""Replay and exercise migration 631 on disposable local PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_draft_path = ROOT / "scripts/check-delphi-study-drafts-disposable.py"
_draft_spec = importlib.util.spec_from_file_location("delphi_drafts_disposable", _draft_path)
if _draft_spec is None or _draft_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_draft = importlib.util.module_from_spec(_draft_spec)
_draft_spec.loader.exec_module(_draft)
_review = _draft._review

MIGRATION_631 = ROOT / "schemas/postgres/631_location_scoped_delphi_study_lifecycle.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-study-lifecycle-disposable.json"
IMAGE = "postgis/postgis:16-3.4"

run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'open', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'close', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.delphi_study
    (id, location_id, title, description, variation, status, stopping_criteria,
     opened_at, closed_at, created_at, updated_at, created_by, facilitator_type)
VALUES
    ('e1000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001', 'Lifecycle preparation',
     'Synthetic lifecycle test', 'real_time', 'draft',
     '{"max_duration_hours":720,"stability_pct":5,"min_participants":3,"iqr_threshold":1}',
     NULL, NULL, clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE study UUID := 'e1000000-0000-4000-8000-000000000001';
    denied BOOLEAN := false;
BEGIN
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_delphi_study(
            'b0000000-0000-4000-8000-000000000001', study, 'open',
            'd0000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unprepared study opened'; END IF;
END $$;
COMMIT;
RESET ROLE;
DO $$
BEGIN
    IF (SELECT status FROM public.delphi_study
         WHERE id = 'e1000000-0000-4000-8000-000000000001') <> 'draft' THEN
        RAISE EXCEPTION 'failed open changed study state';
    END IF;
END $$;

DO $$
BEGIN
    INSERT INTO public.delphi_item
        (id, study_id, item_type, label, scale, min_value, max_value, created_at)
    VALUES ('d1000000-0000-4000-8000-000000000001',
            'e1000000-0000-4000-8000-000000000001', 'issue',
            'Water resilience', 'desirability', -1, 1, clock_timestamp());
    INSERT INTO public.delphi_panel_member
        (id, study_id, display_token, consent_status, expert_weight)
    VALUES
        ('d2000000-0000-4000-8000-000000000001',
         'e1000000-0000-4000-8000-000000000001', 'anon-1', 'granted', 1),
        ('d2000000-0000-4000-8000-000000000002',
         'e1000000-0000-4000-8000-000000000001', 'anon-2', 'granted', 1);
END $$;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE denied BOOLEAN := false;
BEGIN
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_delphi_study(
            'b0000000-0000-4000-8000-000000000001',
            'e1000000-0000-4000-8000-000000000001', 'open',
            'd0000000-0000-4000-8000-000000000005'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'undersized consented panel opened'; END IF;
END $$;
COMMIT;
RESET ROLE;

INSERT INTO public.delphi_panel_member
    (id, study_id, display_token, consent_status, expert_weight)
VALUES
    ('d2000000-0000-4000-8000-000000000003',
     'e1000000-0000-4000-8000-000000000001', 'anon-3', 'granted', 1),
    ('d2000000-0000-4000-8000-000000000004',
     'e1000000-0000-4000-8000-000000000001', 'anon-4', 'withdrawn', 1);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE opened RECORD;
    replay RECORD;
    closed RECORD;
    close_replay RECORD;
    study UUID := 'e1000000-0000-4000-8000-000000000001';
    denied BOOLEAN := false;
BEGIN
    SELECT * INTO opened FROM kokonut_security.transition_location_delphi_study(
        'b0000000-0000-4000-8000-000000000001', study, 'open',
        'd0000000-0000-4000-8000-000000000002'
    );
    IF opened.status <> 'open' OR opened.opened_at IS NULL OR opened.closed_at IS NOT NULL
       OR opened.replayed THEN
        RAISE EXCEPTION 'prepared study did not open with correct timestamps';
    END IF;
    SELECT * INTO replay FROM kokonut_security.transition_location_delphi_study(
        'b0000000-0000-4000-8000-000000000001', study, 'open',
        'd0000000-0000-4000-8000-000000000002'
    );
    IF NOT replay.replayed OR replay.opened_at IS DISTINCT FROM opened.opened_at THEN
        RAISE EXCEPTION 'open retry did not replay the original result';
    END IF;

    BEGIN
        PERFORM * FROM kokonut_security.transition_location_delphi_study(
            'b0000000-0000-4000-8000-000000000001', study, 'close',
            'd0000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'request id collision changed action'; END IF;

    SELECT * INTO closed FROM kokonut_security.transition_location_delphi_study(
        'b0000000-0000-4000-8000-000000000001', study, 'close',
        'd0000000-0000-4000-8000-000000000003'
    );
    IF closed.status <> 'closed' OR closed.opened_at IS DISTINCT FROM opened.opened_at
       OR closed.closed_at IS NULL OR closed.replayed THEN
        RAISE EXCEPTION 'open study did not close with lifecycle timestamps preserved';
    END IF;
    SELECT * INTO close_replay FROM kokonut_security.transition_location_delphi_study(
        'b0000000-0000-4000-8000-000000000001', study, 'close',
        'd0000000-0000-4000-8000-000000000003'
    );
    IF NOT close_replay.replayed
       OR close_replay.closed_at IS DISTINCT FROM closed.closed_at THEN
        RAISE EXCEPTION 'close retry did not replay the original result';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.transition_location_delphi_study(
            'b0000000-0000-4000-8000-000000000001', study, 'open',
            'd0000000-0000-4000-8000-000000000004'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'closed study was reopened'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_study_lifecycle_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private lifecycle receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE role_name TEXT;
    privilege_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        FOREACH privilege_name IN ARRAY ARRAY[
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
        ] LOOP
            IF has_table_privilege(
                role_name, 'kokonut_security.delphi_study_lifecycle_request', privilege_name
            ) THEN
                RAISE EXCEPTION '% has unexpected % access to lifecycle receipts',
                    role_name, privilege_name;
            END IF;
        END LOOP;
    END LOOP;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.transition_location_delphi_study(uuid,uuid,text,uuid)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.transition_location_delphi_study(uuid,uuid,text,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'bounded lifecycle function role access is incorrect';
    END IF;
    IF (SELECT pg_catalog.pg_get_userbyid(proc.proowner)
          FROM pg_catalog.pg_proc AS proc
         WHERE proc.oid = 'kokonut_security.transition_location_delphi_study(uuid,uuid,text,uuid)'::regprocedure)
       <> 'kokonut_delphi_study_lifecycle' THEN
        RAISE EXCEPTION 'lifecycle function does not use dedicated non-login owner';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-lifecycle-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451, 630, and 631 apply and replay on disposable PostgreSQL 16",
        "an unprepared draft cannot open and a failed attempt leaves its state unchanged",
        "opening requires a question and enough currently consented panel members",
        "open and close transitions preserve timestamps and exact retries replay",
        "request-ID action collisions and reopening closed studies fail closed",
        "runtime and Directus cannot access private lifecycle receipts; only runtime executes the bounded function",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_631.name,
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
            ("631", MIGRATION_631),
        )
        for version, migration in migrations:
            stage = f"migration_{version}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        stage = "study_draft_acceptance"
        psql(docker, container, _draft.acceptance_sql())
        stage = "lifecycle_acceptance"
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
