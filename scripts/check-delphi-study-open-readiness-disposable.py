#!/usr/bin/env python3
"""Replay and exercise migration 633 on disposable local PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_items_path = ROOT / "scripts/check-delphi-study-items-disposable.py"
_items_spec = importlib.util.spec_from_file_location("delphi_items_disposable", _items_path)
if _items_spec is None or _items_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_items = importlib.util.module_from_spec(_items_spec)
_items_spec.loader.exec_module(_items)
_lifecycle = _items._lifecycle
_draft = _items._draft
_review = _items._review

MIGRATION_633 = ROOT / "schemas/postgres/633_location_delphi_study_open_readiness.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-study-open-readiness-disposable.json"
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
    ('e5000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001', 'Readiness valid draft',
     'Synthetic readiness fixture', 'real_time', 'draft',
     '{"max_duration_hours":720,"stability_pct":5,"min_participants":3,"iqr_threshold":1}',
     NULL, NULL, clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human'),
    ('e5000000-0000-4000-8000-000000000002',
     'b0000000-0000-4000-8000-000000000001', 'Readiness invalid rule',
     'Synthetic invalid-rule fixture', 'real_time', 'draft',
     '{"min_participants":2}', NULL, NULL, clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human'),
    ('e5000000-0000-4000-8000-000000000003',
     'b0000000-0000-4000-8000-000000000001', 'Readiness non-draft',
     'Synthetic state fixture', 'real_time', 'open',
     '{"min_participants":3}', clock_timestamp(), NULL,
     clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human'),
    ('e5000000-0000-4000-8000-000000000004',
     'b0000000-0000-4000-8000-000000000001', 'Readiness missing question',
     'Synthetic missing-question fixture', 'real_time', 'draft',
     '{"min_participants":3}', NULL, NULL,
     clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human');

INSERT INTO public.delphi_item
    (id, study_id, item_type, label, scale, min_value, max_value, created_at)
VALUES
    ('d5000000-0000-4000-8000-000000000001',
     'e5000000-0000-4000-8000-000000000001', 'issue',
     'Water resilience', 'desirability', -1, 1, clock_timestamp());
INSERT INTO public.delphi_panel_member
    (id, study_id, display_token, consent_status, expert_weight)
VALUES
    ('d5100000-0000-4000-8000-000000000001',
     'e5000000-0000-4000-8000-000000000001', 'private-1', 'granted', 1),
    ('d5100000-0000-4000-8000-000000000002',
     'e5000000-0000-4000-8000-000000000001', 'private-2', 'granted', 1),
    ('d5100000-0000-4000-8000-000000000003',
     'e5000000-0000-4000-8000-000000000001', 'private-3', 'withdrawn', 1);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE result RECORD;
    denied BOOLEAN := false;
BEGIN
    SELECT * INTO result FROM kokonut_security.get_location_delphi_study_open_readiness(
        'b0000000-0000-4000-8000-000000000001',
        'e5000000-0000-4000-8000-000000000001'
    );
    IF result.has_question IS DISTINCT FROM TRUE
       OR result.minimum_policy_valid IS DISTINCT FROM TRUE
       OR result.consent_minimum_met IS DISTINCT FROM FALSE
       OR result.eligible_to_open IS DISTINCT FROM FALSE
       OR result.blocker_codes IS DISTINCT FROM ARRAY['consented_panel_below_minimum']::TEXT[] THEN
        RAISE EXCEPTION 'readiness did not honor current consent or returned incorrect blockers';
    END IF;

    SELECT * INTO result FROM kokonut_security.get_location_delphi_study_open_readiness(
        'b0000000-0000-4000-8000-000000000001',
        'e5000000-0000-4000-8000-000000000002'
    );
    IF result.minimum_policy_valid IS DISTINCT FROM FALSE
       OR result.eligible_to_open IS DISTINCT FROM FALSE
       OR NOT ('minimum_participants_invalid' = ANY(result.blocker_codes)) THEN
        RAISE EXCEPTION 'invalid minimum participant rule was not reported as blocked';
    END IF;

    SELECT * INTO result FROM kokonut_security.get_location_delphi_study_open_readiness(
        'b0000000-0000-4000-8000-000000000001',
        'e5000000-0000-4000-8000-000000000003'
    );
    IF result.eligible_to_open IS DISTINCT FROM FALSE
       OR NOT ('study_not_draft' = ANY(result.blocker_codes)) THEN
        RAISE EXCEPTION 'non-draft study did not remain blocked';
    END IF;

    SELECT * INTO result FROM kokonut_security.get_location_delphi_study_open_readiness(
        'b0000000-0000-4000-8000-000000000001',
        'e5000000-0000-4000-8000-000000000004'
    );
    IF result.has_question IS DISTINCT FROM FALSE
       OR result.eligible_to_open IS DISTINCT FROM FALSE
       OR NOT ('question_required' = ANY(result.blocker_codes)) THEN
        RAISE EXCEPTION 'study without a question did not remain blocked';
    END IF;

    BEGIN
        PERFORM * FROM kokonut_security.get_location_delphi_study_open_readiness(
            'b0000000-0000-4000-8000-000000000002',
            'e5000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location readiness read was allowed'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM public.delphi_panel_member;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read Delphi panel members'; END IF;
END $$;
COMMIT;
RESET ROLE;

INSERT INTO public.delphi_panel_member
    (id, study_id, display_token, consent_status, expert_weight)
VALUES
    ('d5100000-0000-4000-8000-000000000004',
     'e5000000-0000-4000-8000-000000000001', 'private-4', 'granted', 1);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE result RECORD;
    denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO result FROM kokonut_security.get_location_delphi_study_open_readiness(
        'b0000000-0000-4000-8000-000000000001',
        'e5000000-0000-4000-8000-000000000001'
    );
    IF result.has_question IS DISTINCT FROM TRUE
       OR result.minimum_policy_valid IS DISTINCT FROM TRUE
       OR result.consent_minimum_met IS DISTINCT FROM TRUE
       OR result.eligible_to_open IS DISTINCT FROM TRUE
       OR cardinality(result.blocker_codes) <> 0 THEN
        RAISE EXCEPTION 'consented threshold did not produce ready response';
    END IF;
    IF has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.get_location_delphi_study_open_readiness(uuid,uuid)', 'EXECUTE'
    ) IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'runtime cannot execute bounded readiness function';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime')
       AND has_function_privilege(
           'kokonut_directus_runtime',
           'kokonut_security.get_location_delphi_study_open_readiness(uuid,uuid)', 'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'Directus can execute the bounded readiness function';
    END IF;
END $$;
COMMIT;
RESET ROLE;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-readiness-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451 and 630–633 apply and replay on disposable PostgreSQL 16",
        "readiness requires signed exact-location operator context and current delphi:open grant",
        "question, minimum rule, consent threshold, and draft state produce fixed blocker codes",
        "withdrawn and pending panel members do not count toward readiness",
        "readiness exposes no participant or count fields and runtime cannot read panel rows directly",
        "runtime can execute the bounded function while Directus cannot",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_633.name,
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
            ("632", _items.MIGRATION_632),
            ("633", MIGRATION_633),
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
        psql(docker, container, _items.acceptance_sql())
        stage = "readiness_acceptance"
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
