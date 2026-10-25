#!/usr/bin/env python3
"""Replay and exercise consent-bound Delphi report submission in disposable PostgreSQL."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_scope_path = ROOT / "scripts/check-delphi-consent-scopes-disposable.py"
_scope_spec = importlib.util.spec_from_file_location("delphi_consent_scopes", _scope_path)
if _scope_spec is None or _scope_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_scope = importlib.util.module_from_spec(_scope_spec)
_scope_spec.loader.exec_module(_scope)
_review = _scope._review
_draft = _scope._draft
_lifecycle = _scope._lifecycle
_items = _scope._items
_readiness = _scope._readiness
_consent = _scope._consent
_invites = _scope._invites
_participant = _scope._participant

MIGRATION_642 = ROOT / "schemas/postgres/642_location_scoped_delphi_minority_report_submission.sql"
MIGRATIONS_637_639 = (
    ROOT / "schemas/postgres/637_location_scoped_delphi_participant_workspace.sql",
    ROOT / "schemas/postgres/638_location_scoped_delphi_invite_inventory.sql",
    ROOT / "schemas/postgres/639_location_scoped_delphi_stopping_evaluation.sql",
)
MIGRATION_640 = ROOT / "schemas/postgres/640_location_scoped_delphi_minority_report_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-minority-report-submission-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
run = _scope.run
psql = _scope.psql
wait_ready = _scope.wait_ready


SCOPE_ONLY_ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE notice RECORD;
    reviewed RECORD;
    issued RECORD;
    preview RECORD;
    accepted RECORD;
BEGIN
    SELECT * INTO notice FROM kokonut_security.submit_location_delphi_consent_notice_scoped(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 'v4-questionnaire-only',
        'This notice covers questionnaire responses only.',
        ARRAY['questionnaire_responses']::TEXT[],
        'd9000000-0000-4000-8000-000000000011'
    );
    IF notice.status <> 'submitted' THEN RAISE EXCEPTION 'questionnaire-only notice was not submitted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    SELECT * INTO reviewed FROM kokonut_security.decide_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001', notice.notice_id, 'approve',
        'd9000000-0000-4000-8000-000000000012',
        'approved_after_independent_review'
    );
    IF reviewed.resulting_status <> 'approved' THEN
        RAISE EXCEPTION 'questionnaire-only notice was not approved';
    END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    SELECT * INTO issued FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'd9000000-0000-4000-8000-000000000013'
    );
    SELECT * INTO preview FROM kokonut_security.preview_location_delphi_participant_invite_scoped(
        issued.invite_token
    );
    IF preview.collection_scopes IS DISTINCT FROM ARRAY['questionnaire_responses']::TEXT[] THEN
        RAISE EXCEPTION 'questionnaire-only invite scope was altered';
    END IF;
    SELECT * INTO accepted FROM kokonut_security.accept_location_delphi_participant_invite(
        issued.invite_token, preview.notice_digest, repeat('aa', 32), repeat('bb', 32),
        'd9000000-0000-4000-8000-000000000014', TRUE
    );
    IF accepted.status <> 'accepted' THEN RAISE EXCEPTION 'questionnaire-only participant was not accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;
"""


ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE scoped_workspace JSONB;
    submitted RECORD;
    retry RECORD;
    denied BOOLEAN := FALSE;
    request_value UUID := 'd9000000-0000-4000-8000-000000000001';
    location_value UUID := 'b0000000-0000-4000-8000-000000000001';
    study_value UUID := 'e6000000-0000-4000-8000-000000000001';
    item_value UUID := 'd7000000-0000-4000-8000-000000000001';
BEGIN
    scoped_workspace := kokonut_security.get_location_delphi_participant_scoped_workspace(
        repeat('e7', 32), 50, 0
    );
    IF scoped_workspace -> 'collection_scopes' IS DISTINCT FROM
       '["questionnaire_responses", "minority_reports"]'::JSONB THEN
        RAISE EXCEPTION 'participant workspace omitted accepted activity scopes';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_minority_report(
            repeat('00', 32), repeat('f8', 32), NULL,
            'Invalid session', 'Must fail before report creation.',
            'Must fail before report creation.', NULL,
            'd9000000-0000-4000-8000-000000000010'
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unknown participant session was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_minority_report(
            repeat('e7', 32), repeat('f8', 32),
            'd0000000-0000-4000-8000-000000000099',
            'Cross-study item', 'Must fail before report creation.',
            'Must fail before report creation.', NULL,
            'd9000000-0000-4000-8000-000000000011'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-study item reference was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_minority_report(
            repeat('e7', 32), repeat('f8', 32), NULL,
            repeat('x', 256), 'Must fail before report creation.',
            'Must fail before report creation.', NULL,
            'd9000000-0000-4000-8000-000000000012'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'overlong report text was accepted'; END IF;

    SELECT * INTO submitted FROM kokonut_security.submit_location_delphi_participant_minority_report(
        repeat('e7', 32), repeat('f8', 32), item_value,
        'A different position', 'This is the participant position.',
        'The participant rationale.', 'A bounded implication.', request_value
    );
    IF submitted.status IS DISTINCT FROM 'submitted' OR submitted.replayed
       OR submitted.report_id IS NULL OR submitted.submitted_at IS NULL THEN
        RAISE EXCEPTION 'consented participant report was not submitted';
    END IF;
    PERFORM set_config('test.delphi_participant_report_id', submitted.report_id::TEXT, false);
    SELECT * INTO retry FROM kokonut_security.submit_location_delphi_participant_minority_report(
        repeat('e7', 32), repeat('f8', 32), item_value,
        'A different position', 'This is the participant position.',
        'The participant rationale.', 'A bounded implication.', request_value
    );
    IF retry.report_id IS DISTINCT FROM submitted.report_id OR NOT retry.replayed
       OR retry.submitted_at IS DISTINCT FROM submitted.submitted_at THEN
        RAISE EXCEPTION 'exact participant report retry was not stable';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_minority_report(
            repeat('e7', 32), repeat('f8', 32), item_value,
            'Changed title', 'This is the participant position.',
            'The participant rationale.', 'A bounded implication.', request_value
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed report reused the same request ID'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_minority_report(
            repeat('aa', 32), repeat('bb', 32), NULL,
            'No scope', 'This participant did not consent to reports.',
            'This must not be stored.', NULL,
            'd9000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'questionnaire-only participant submitted a minority report'; END IF;

    IF has_table_privilege('kokonut_runtime', 'public.delphi_minority_report', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_minority_report', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_minority_report', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_minority_report', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_minority_report', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_minority_report', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_minority_report', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_minority_report', 'DELETE') THEN
        RAISE EXCEPTION 'shared runtime or Directus retains direct minority-report writes';
    END IF;
    IF has_table_privilege('kokonut_runtime',
        'kokonut_security.delphi_participant_minority_report_request', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime',
        'kokonut_security.delphi_participant_minority_report_request', 'SELECT') THEN
        RAISE EXCEPTION 'shared runtime or Directus can inspect private report retry receipts';
    END IF;
    IF has_function_privilege('kokonut_directus_runtime',
        'kokonut_security.submit_location_delphi_participant_minority_report(text,text,uuid,text,text,text,text,uuid)',
        'EXECUTE') THEN
        RAISE EXCEPTION 'Directus can execute participant report submission';
    END IF;
    denied := FALSE;
    BEGIN
        INSERT INTO public.delphi_minority_report (study_id, title, position_summary, rationale)
        VALUES (study_value, 'Direct write', 'Should fail', 'Should fail');
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime direct report insert succeeded'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE report_id_value UUID := current_setting('test.delphi_participant_report_id')::UUID;
BEGIN
    IF (SELECT pg_catalog.count(*) FROM public.delphi_minority_report
         WHERE id = report_id_value AND status = 'submitted'
           AND created_by_panel_member_id IS NOT NULL
           AND evidence_refs = '[]'::JSONB) <> 1 THEN
        RAISE EXCEPTION 'report was not one private submitted row without arbitrary evidence';
    END IF;
END $$;

-- Withdrawal revokes the same session used for report writes; the private
-- submitted row stays in place for disposition, but no further report is allowed.
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE denied BOOLEAN := FALSE;
    report_id_value UUID := current_setting('test.delphi_participant_report_id')::UUID;
BEGIN
    PERFORM * FROM kokonut_security.withdraw_location_delphi_participant(
        repeat('e7', 32), repeat('f8', 32), 'd9000000-0000-4000-8000-000000000003'
    );
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_minority_report(
            repeat('e7', 32), repeat('f8', 32), NULL,
            'After withdrawal', 'Must not be stored.', 'Must not be stored.', NULL,
            'd9000000-0000-4000-8000-000000000004'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'withdrawn participant submitted another report'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE report_id_value UUID := current_setting('test.delphi_participant_report_id')::UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.delphi_minority_report
         WHERE id = report_id_value AND status = 'submitted'
    ) THEN RAISE EXCEPTION 'withdrawal erased or changed the submitted report'; END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-minority-submit-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 642 applies and replays after the consent-scoped participant chain",
        "workspace returns only the exact collection scopes bound to accepted consent",
        "minority-report submission requires a live session, CSRF token, and accepted minority_reports scope",
        "report item references are study-scoped and report text is bounded",
        "submitted report content and participant attribution are persisted once without arbitrary evidence references",
        "exact retries replay and changed-content request-ID reuse is rejected",
        "withdrawal serializes with report writes and leaves submitted content for private disposition",
        "runtime and Directus cannot directly write reports or read private retry receipts",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_642.name,
        "database_target": "new disposable PostgreSQL 16 container with networking disabled",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    stage = "container_start"
    try:
        run([
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
        ])
        wait_ready(container, docker)
        stage = "base_fixture"
        psql(docker, container, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        psql(docker, container, _review.FIXTURE)
        psql(docker, container, _review.delphi_fixture())
        psql(
            docker,
            container,
            "ALTER TABLE public.delphi_panel_member "
            "ADD COLUMN participant_ref_type varchar(30) NOT NULL DEFAULT 'agent' "
            "CHECK (participant_ref_type IN ('farmer_identity','stakeholder_group','guild_contributor','agent')); "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN is_anonymous boolean NOT NULL DEFAULT true; "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN role varchar(20) NOT NULL DEFAULT 'expert'; "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN joined_at timestamptz NOT NULL DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_study ADD COLUMN created_by uuid; "
            "ALTER TABLE public.delphi_study ADD COLUMN facilitator_type varchar(20) NOT NULL DEFAULT 'agent'; "
            "ALTER TABLE public.delphi_study ALTER COLUMN created_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_study ALTER COLUMN updated_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_item ALTER COLUMN created_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_contribution ALTER COLUMN updated_at SET DEFAULT clock_timestamp();",
        )
        psql(
            docker,
            container,
            "CREATE TABLE public.delphi_consensus ("
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), study_id uuid NOT NULL, "
            "item_id uuid NOT NULL UNIQUE, median numeric, mean numeric, iqr numeric, "
            "stddev numeric, cv numeric, participant_count integer NOT NULL DEFAULT 0, "
            "weighted_median numeric, consensus_reached boolean NOT NULL DEFAULT false, "
            "computed_at timestamptz NOT NULL DEFAULT clock_timestamp()); "
            "CREATE TABLE public.delphi_consensus_history ("
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), study_id uuid NOT NULL, "
            "item_id uuid NOT NULL, median numeric, iqr numeric, "
            "participant_count integer NOT NULL DEFAULT 0, "
            "computed_at timestamptz NOT NULL DEFAULT clock_timestamp()); "
            "CREATE TABLE public.delphi_stopping_evaluation ("
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), study_id uuid NOT NULL, "
            "item_id uuid, scope varchar(10) NOT NULL CHECK (scope IN ('item','study')), "
            "outcome varchar(40) NOT NULL, consensus_met boolean NOT NULL, "
            "participation_met boolean NOT NULL, stability_met boolean NOT NULL, "
            "duration_exceeded boolean NOT NULL, completion_met boolean NOT NULL, "
            "normalized_iqr numeric(10,6), median_shift numeric(10,6), "
            "detail jsonb NOT NULL DEFAULT '{}'::jsonb, evaluated_at timestamptz NOT NULL DEFAULT now()); "
            "ALTER TABLE public.delphi_contribution ADD CONSTRAINT "
            "delphi_contribution_item_panel_unique UNIQUE (item_id, panel_member_id)",
        )
        migrations = (
            ("449", _draft.MIGRATION_449),
            ("450", _draft.MIGRATION_450),
            ("451", _draft.MIGRATION_451),
            ("630", _draft.MIGRATION_630),
            ("631", _lifecycle.MIGRATION_631),
            ("632", _items.MIGRATION_632),
            ("633", _readiness.MIGRATION_633),
            ("634", _consent.MIGRATION_634),
            ("635", _invites.MIGRATION_635),
            ("636", _participant.MIGRATION_636),
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
        psql(docker, container, _consent.acceptance_sql())
        psql(docker, container, _invites.acceptance_sql())
        psql(docker, container, _participant.acceptance_sql())
        for migration in MIGRATIONS_637_639:
            stage = f"migration_{migration.name[:3]}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        # This shared recommendation-review fixture predates the production
        # minority-report shape. Extend it before migration 640 so both the
        # reviewer projection and migration 642 exercise the canonical columns.
        psql(
            docker,
            container,
            "ALTER TABLE public.delphi_minority_report "
            "ADD COLUMN IF NOT EXISTS item_id UUID, "
            "ADD COLUMN IF NOT EXISTS title VARCHAR(255) NOT NULL DEFAULT 'Legacy report', "
            "ADD COLUMN IF NOT EXISTS position_summary TEXT NOT NULL DEFAULT 'Legacy position', "
            "ADD COLUMN IF NOT EXISTS evidence_refs JSONB NOT NULL DEFAULT '[]'::JSONB, "
            "ADD COLUMN IF NOT EXISTS implications TEXT, "
            "ADD COLUMN IF NOT EXISTS created_by_panel_member_id UUID, "
            "ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ, "
            "ADD COLUMN IF NOT EXISTS verified_by UUID, "
            "ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ, "
            "ADD COLUMN IF NOT EXISTS verification_notes TEXT, "
            "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(), "
            "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()",
        )
        stage = "migration_640_apply_and_replay"
        migration_640 = MIGRATION_640.read_text(encoding="utf-8")
        psql(docker, container, migration_640)
        psql(docker, container, migration_640)
        stage = "migration_641_apply_and_replay"
        migration_641 = _scope.MIGRATION_641.read_text(encoding="utf-8")
        psql(docker, container, migration_641)
        psql(docker, container, migration_641)
        psql(
            docker,
            container,
            "INSERT INTO kokonut_security.delphi_consent_notice ("
            "id, location_id, study_id, version, notice_text, notice_digest, "
            "collection_scopes, status, created_by) VALUES ("
            "'cc000000-0000-4000-8000-000000000001', "
            "'b0000000-0000-4000-8000-000000000001', "
            "'e6000000-0000-4000-8000-000000000001', 'legacy-unscoped-pending', "
            "'A legacy pending notice.', public.digest('A legacy pending notice.', 'sha256'), "
            "ARRAY[]::TEXT[], 'submitted', 'a0000000-0000-4000-8000-000000000002')",
        )
        psql(docker, container, _scope.ACCEPTANCE)
        stage = "questionnaire_only_participant_acceptance"
        psql(docker, container, SCOPE_ONLY_ACCEPTANCE)
        psql(
            docker,
            container,
            "INSERT INTO public.delphi_item "
            "(id, study_id, item_type, label, description, scale, min_value, max_value, created_at) VALUES ("
            "'d7000000-0000-4000-8000-000000000001', "
            "'e6000000-0000-4000-8000-000000000001', 'issue', 'Synthetic question', "
            "'Disposable participant report question.', 'desirability', 0, 100, clock_timestamp())",
        )
        stage = "migration_642_apply_and_replay"
        migration_642 = MIGRATION_642.read_text(encoding="utf-8")
        psql(docker, container, migration_642)
        psql(docker, container, migration_642)
        stage = "open_synthetic_study_fixture"
        psql(
            docker,
            container,
            "INSERT INTO public.delphi_item (id, study_id, item_type, label, scale, created_at) "
            "VALUES ('d0000000-0000-4000-8000-000000000099', "
            "'d0000000-0000-4000-8000-000000000004', 'issue', 'Foreign item', 'desirability', clock_timestamp()); "
            "UPDATE public.delphi_study SET status = 'open', "
            "opened_at = clock_timestamp() "
            "WHERE id = 'e6000000-0000-4000-8000-000000000001'",
        )
        stage = "submission_acceptance"
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - no credentials or DSNs are included
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
