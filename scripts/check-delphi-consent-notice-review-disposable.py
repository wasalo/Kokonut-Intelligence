#!/usr/bin/env python3
"""Replay and exercise migration 634 on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_readiness_path = ROOT / "scripts/check-delphi-study-open-readiness-disposable.py"
_readiness_spec = importlib.util.spec_from_file_location("delphi_readiness_disposable", _readiness_path)
if _readiness_spec is None or _readiness_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_readiness = importlib.util.module_from_spec(_readiness_spec)
_readiness_spec.loader.exec_module(_readiness)
_items = _readiness._items
_lifecycle = _items._lifecycle
_draft = _items._draft
_review = _items._review

MIGRATION_634 = ROOT / "schemas/postgres/634_location_delphi_consent_notice_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-consent-notice-review-disposable.json"
IMAGE = "postgis/postgis:16-3.4"

run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'consent_draft', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'consent_review', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'consent_review', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.delphi_study
    (id, location_id, title, description, variation, status, stopping_criteria,
     opened_at, closed_at, created_at, updated_at, created_by, facilitator_type)
VALUES
    ('e6000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001', 'Consent notice review',
     'Synthetic consent notice fixture', 'real_time', 'draft',
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
DECLARE submitted RECORD;
    replay RECORD;
    queue_row RECORD;
    decision_row RECORD;
    decision_retry RECORD;
    second_notice RECORD;
    second_decision RECORD;
    denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO submitted FROM kokonut_security.submit_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 'v1',
        'This synthetic notice is voluntary and data is used only for this study.',
        'c6000000-0000-4000-8000-000000000001'
    );
    IF submitted.status <> 'submitted' OR submitted.replayed
       OR submitted.version <> 'v1' OR length(submitted.notice_digest) <> 64 THEN
        RAISE EXCEPTION 'consent notice was not submitted with a SHA-256 digest';
    END IF;
    SELECT * INTO replay FROM kokonut_security.submit_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 'v1',
        'This synthetic notice is voluntary and data is used only for this study.',
        'c6000000-0000-4000-8000-000000000001'
    );
    IF replay.notice_id IS DISTINCT FROM submitted.notice_id OR NOT replay.replayed THEN
        RAISE EXCEPTION 'exact notice submission retry did not replay';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_consent_notice(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 'v1', 'Changed notice',
            'c6000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed notice request ID reuse was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_delphi_consent_notices(
            'b0000000-0000-4000-8000-000000000001', NULL, 0
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'NULL review page bound was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_consent_notice(
            'b0000000-0000-4000-8000-000000000001', submitted.notice_id, NULL,
            'c6000000-0000-4000-8000-000000000007', NULL
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'NULL decision fields were accepted'; END IF;

    SELECT * INTO queue_row FROM kokonut_security.list_location_delphi_consent_notices(
        'b0000000-0000-4000-8000-000000000001', 51, 0
    ) WHERE notice_id = submitted.notice_id;
    IF queue_row.review_ready IS DISTINCT FROM FALSE
       OR queue_row.blocked_reasons IS DISTINCT FROM ARRAY['self_review']::TEXT[] THEN
        RAISE EXCEPTION 'notice author was not blocked from reviewing own notice';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_consent_notice(
            'b0000000-0000-4000-8000-000000000001', submitted.notice_id, 'approve',
            'c6000000-0000-4000-8000-000000000002',
            'approved_after_independent_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'author self-approved consent notice'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    SELECT * INTO queue_row FROM kokonut_security.list_location_delphi_consent_notices(
        'b0000000-0000-4000-8000-000000000001', 51, 0
    ) WHERE notice_id = submitted.notice_id;
    IF queue_row.review_ready IS DISTINCT FROM TRUE
       OR cardinality(queue_row.blocked_reasons) <> 0
       OR queue_row.notice_text NOT LIKE 'This synthetic notice%' THEN
        RAISE EXCEPTION 'independent reviewer did not receive bounded notice text';
    END IF;
    SELECT * INTO decision_row FROM kokonut_security.decide_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001', submitted.notice_id, 'approve',
        'c6000000-0000-4000-8000-000000000003',
        'approved_after_independent_review'
    );
    SELECT * INTO decision_retry FROM kokonut_security.decide_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001', submitted.notice_id, 'approve',
        'c6000000-0000-4000-8000-000000000003',
        'approved_after_independent_review'
    );
    IF decision_row.resulting_status <> 'approved' OR decision_row.replayed
       OR NOT decision_retry.replayed
       OR decision_retry.decision_id IS DISTINCT FROM decision_row.decision_id THEN
        RAISE EXCEPTION 'independent approval or exact decision replay failed';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_consent_notice(
            'b0000000-0000-4000-8000-000000000001', submitted.notice_id, 'approve',
            'c6000000-0000-4000-8000-000000000004',
            'approved_after_independent_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'notice was decided twice under a new key'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    SELECT * INTO second_notice FROM kokonut_security.submit_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 'v2',
        'This replacement synthetic notice includes updated terms.',
        'c6000000-0000-4000-8000-000000000005'
    );
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    SELECT * INTO second_decision FROM kokonut_security.decide_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001', second_notice.notice_id, 'approve',
        'c6000000-0000-4000-8000-000000000006',
        'approved_after_independent_review'
    );
    IF second_decision.resulting_status <> 'approved' THEN
        RAISE EXCEPTION 'replacement notice approval failed';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_consent_notice;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private notice text'; END IF;
    denied := FALSE;
    BEGIN
        UPDATE kokonut_security.delphi_consent_notice
           SET notice_text = 'tampered'
         WHERE id = second_notice.notice_id;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly alter notice content'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE denied BOOLEAN := FALSE;
BEGIN
    BEGIN
        INSERT INTO kokonut_security.delphi_consent_notice (
            location_id, study_id, version, notice_text, notice_digest,
            status, created_by, reviewed_by, reviewed_at, review_reason_code
        ) VALUES (
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 'invalid-null-reason',
            'Invalid test notice', public.digest('Invalid test notice', 'sha256'),
            'rejected', 'a0000000-0000-4000-8000-000000000002',
            'a0000000-0000-4000-8000-000000000003', clock_timestamp(), NULL
        );
    EXCEPTION WHEN check_violation THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'rejected notice without a reason was accepted'; END IF;

    denied := FALSE;
    BEGIN
        UPDATE kokonut_security.delphi_consent_notice
           SET notice_text = 'tampered'
         WHERE study_id = 'e6000000-0000-4000-8000-000000000001'
           AND version = 'v2';
    EXCEPTION WHEN raise_exception THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'notice text was mutable after submission'; END IF;

    IF (SELECT status FROM kokonut_security.delphi_consent_notice
         WHERE study_id = 'e6000000-0000-4000-8000-000000000001'
           AND version = 'v1') <> 'superseded'
       OR (SELECT count(*) FROM kokonut_security.delphi_consent_notice
            WHERE study_id = 'e6000000-0000-4000-8000-000000000001'
              AND status = 'approved') <> 1 THEN
        RAISE EXCEPTION 'replacement notice did not supersede the previous approval';
    END IF;
END $$;

DO $$
DECLARE function_name TEXT;
BEGIN
    FOREACH function_name IN ARRAY ARRAY[
        'kokonut_security.submit_location_delphi_consent_notice(uuid,uuid,text,text,uuid)',
        'kokonut_security.list_location_delphi_consent_notices(uuid,integer,integer)',
        'kokonut_security.decide_location_delphi_consent_notice(uuid,uuid,text,uuid,text)'
    ] LOOP
        IF NOT has_function_privilege('kokonut_runtime', function_name, 'EXECUTE') THEN
            RAISE EXCEPTION 'runtime cannot call bounded consent notice function %', function_name;
        END IF;
        IF has_function_privilege('kokonut_directus_runtime', function_name, 'EXECUTE') THEN
            RAISE EXCEPTION 'Directus can call consent notice function %', function_name;
        END IF;
    END LOOP;
    IF has_table_privilege(
        'kokonut_directus_runtime', 'kokonut_security.delphi_consent_notice', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'Directus can read private consent notice text';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-notice-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451 and 630–634 apply and replay on disposable PostgreSQL 16",
        "notice text is immutable, versioned, digest-backed, and submitted only for a draft study",
        "review-state constraints reject missing reasons and content edits",
        "NULL paging and decision values fail closed",
        "exact submission retries replay and changed-content request-ID reuse fails",
        "authors cannot review their own notices; reviewers see a bounded self-review blocker",
        "independent decisions are reason-coded, append-only, and exact-retry safe",
        "approving a replacement supersedes the prior approved version for the study",
        "runtime can call bounded functions but cannot read/write notices; Directus is denied",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_634.name,
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
            ("633", _readiness.MIGRATION_633),
            ("634", MIGRATION_634),
        )
        for version, migration in migrations:
            stage = f"migration_{version}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        stage = "prior_delphi_acceptance"
        psql(docker, container, _draft.acceptance_sql())
        psql(docker, container, _lifecycle.acceptance_sql())
        psql(docker, container, _items.acceptance_sql())
        psql(docker, container, _readiness.acceptance_sql())
        stage = "notice_review_acceptance"
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
