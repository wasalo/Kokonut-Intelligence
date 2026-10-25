#!/usr/bin/env python3
"""Replay and exercise Delphi participant workspace migration 637 on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_prior_path = ROOT / "scripts/check-delphi-participant-acceptance-disposable.py"
_prior_spec = importlib.util.spec_from_file_location("delphi_participant_acceptance_disposable", _prior_path)
if _prior_spec is None or _prior_spec.loader is None:
    raise RuntimeError("could not load Delphi participant disposable PostgreSQL helpers")
_prior = importlib.util.module_from_spec(_prior_spec)
_prior_spec.loader.exec_module(_prior)
_review = _prior._review
_draft = _prior._draft
_lifecycle = _prior._lifecycle
_items = _prior._items
_readiness = _prior._readiness
_consent = _prior._consent
_invites = _prior._previous
_participant = _prior

MIGRATION_637 = ROOT / "schemas/postgres/637_location_scoped_delphi_participant_workspace.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-participant-workspace-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE issued RECORD;
    preview RECORD;
    accepted RECORD;
    workspace JSONB;
    session_value TEXT := repeat('c3', 32);
    csrf_value TEXT := repeat('d4', 32);
BEGIN
    SELECT * INTO issued FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'c7000000-0000-4000-8000-000000000101'
    );
    SELECT * INTO preview FROM kokonut_security.preview_location_delphi_participant_invite(
        issued.invite_token
    );
    SELECT * INTO accepted FROM kokonut_security.accept_location_delphi_participant_invite(
        issued.invite_token, preview.notice_digest, session_value, csrf_value,
        'c7000000-0000-4000-8000-000000000102', TRUE
    );
    IF accepted.status IS DISTINCT FROM 'accepted' OR accepted.replayed THEN
        RAISE EXCEPTION 'synthetic participant did not accept study notice';
    END IF;
    workspace := kokonut_security.get_location_delphi_participant_workspace(
        session_value, 50, 0
    );
    IF workspace #>> '{study,status}' IS DISTINCT FROM 'draft'
       OR jsonb_array_length(workspace -> 'items') <> 0 THEN
        RAISE EXCEPTION 'draft workspace exposed questionnaire content';
    END IF;
END $$;
COMMIT;
RESET ROLE;
SELECT set_config('test.delphi_participant_session', repeat('c3', 32), false);
SELECT set_config('test.delphi_participant_csrf', repeat('d4', 32), false);
DO $$
DECLARE member_id UUID;
BEGIN
    SELECT session.panel_member_id INTO member_id
      FROM kokonut_security.delphi_participant_session AS session
     WHERE session.session_token_digest = public.digest(
        convert_to(current_setting('test.delphi_participant_session'), 'UTF8'), 'sha256'
     );
    IF member_id IS NULL THEN RAISE EXCEPTION 'accepted participant member was not found'; END IF;
    PERFORM set_config('test.delphi_participant_member_id', member_id::TEXT, false);
END $$;

INSERT INTO public.delphi_item (
    id, study_id, item_type, label, description, scale, min_value, max_value, created_at
) VALUES (
    'd7000000-0000-4000-8000-000000000001',
    'e6000000-0000-4000-8000-000000000001',
    'issue', 'Water resilience', 'Choose a score for this synthetic question.',
    'probability', 0, 100, clock_timestamp()
);
INSERT INTO public.delphi_item (
    id, study_id, item_type, label, description, scale, min_value, max_value, created_at
) VALUES (
    'd7000000-0000-4000-8000-000000000003',
    'e6000000-0000-4000-8000-000000000001',
    'goal', 'Soil resilience', 'A second synthetic question for page bounds.',
    'desirability', -1, 1, clock_timestamp()
);
INSERT INTO public.delphi_panel_member (
    id, study_id, participant_ref_type, participant_ref_id, display_token,
    is_anonymous, expert_weight, role, consent_status
) VALUES (
    'd8000000-0000-4000-8000-000000000001',
    'e6000000-0000-4000-8000-000000000001', 'pseudonymous_participant', NULL,
    'P-OTHER-PRIVATE', TRUE, 1.0, 'expert', 'granted'
);
INSERT INTO public.delphi_contribution (
    id, study_id, item_id, panel_member_id, score, reasoning
) VALUES (
    'd8000000-0000-4000-8000-000000000002',
    'e6000000-0000-4000-8000-000000000001',
    'd7000000-0000-4000-8000-000000000001',
    'd8000000-0000-4000-8000-000000000001', 10,
    'another participant private note'
);
UPDATE public.delphi_study
   SET status = 'open', opened_at = clock_timestamp(), updated_at = clock_timestamp()
 WHERE id = 'e6000000-0000-4000-8000-000000000001';
INSERT INTO public.delphi_study
    (id, location_id, title, variation, status, stopping_criteria, created_at, updated_at)
VALUES (
    'e7000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001', 'Foreign study', 'real_time', 'open',
    '{"min_participants":1,"iqr_threshold":1}', clock_timestamp(), clock_timestamp()
);
INSERT INTO public.delphi_item (
    id, study_id, item_type, label, scale, min_value, max_value, created_at
) VALUES (
    'd7000000-0000-4000-8000-000000000002',
    'e7000000-0000-4000-8000-000000000001', 'issue', 'Foreign item',
    'probability', 0, 100, clock_timestamp()
);

SET ROLE kokonut_runtime;
BEGIN;
DO $$
DECLARE workspace JSONB;
    first_saved RECORD;
    first_retry RECORD;
    updated RECORD;
    unchanged RECORD;
    denied BOOLEAN := FALSE;
    session_value TEXT := current_setting('test.delphi_participant_session');
    csrf_value TEXT := current_setting('test.delphi_participant_csrf');
    member_id UUID := current_setting('test.delphi_participant_member_id')::UUID;
    item UUID := 'd7000000-0000-4000-8000-000000000001';
    contribution UUID;
BEGIN
    SELECT * INTO first_saved
      FROM kokonut_security.submit_location_delphi_participant_contribution(
          session_value, csrf_value, item, 42.1250, 'My private reasoning',
          'c7000000-0000-4000-8000-000000000201'
      );
    IF first_saved.status <> 'submitted' OR first_saved.replayed
       OR first_saved.item_id <> item THEN
        RAISE EXCEPTION 'first participant answer was not saved';
    END IF;
    contribution := first_saved.contribution_id;
    SELECT * INTO first_retry
      FROM kokonut_security.submit_location_delphi_participant_contribution(
          session_value, csrf_value, item, 42.1250, 'My private reasoning',
          'c7000000-0000-4000-8000-000000000201'
      );
    IF NOT first_retry.replayed OR first_retry.contribution_id <> contribution THEN
        RAISE EXCEPTION 'exact answer retry was not idempotent';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_contribution(
            session_value, csrf_value, item, 45, 'Changed answer',
            'c7000000-0000-4000-8000-000000000201'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed request-ID reuse was accepted'; END IF;

    SELECT * INTO updated
      FROM kokonut_security.submit_location_delphi_participant_contribution(
          session_value, csrf_value, item, 45, 'Updated private reasoning',
          'c7000000-0000-4000-8000-000000000202'
      );
    IF updated.replayed OR updated.contribution_id <> contribution THEN
        RAISE EXCEPTION 'answer update did not preserve its contribution identity';
    END IF;
    SELECT * INTO unchanged
      FROM kokonut_security.submit_location_delphi_participant_contribution(
          session_value, csrf_value, item, 45, 'Updated private reasoning',
          'c7000000-0000-4000-8000-000000000203'
      );
    IF unchanged.replayed OR unchanged.contribution_id <> contribution THEN
        RAISE EXCEPTION 'unchanged answer was not accepted without replacing its row';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_contribution(
            session_value, csrf_value,
            'd7000000-0000-4000-8000-000000000002', 40, NULL,
            'c7000000-0000-4000-8000-000000000204'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'answer to another study item was accepted'; END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_contribution(
            session_value, csrf_value, item, 100.0001, NULL,
            'c7000000-0000-4000-8000-000000000205'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'answer above item range was accepted'; END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_contribution(
            session_value, repeat('e5', 32), item, 30, NULL,
            'c7000000-0000-4000-8000-000000000206'
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched participant CSRF digest was accepted'; END IF;

    workspace := kokonut_security.get_location_delphi_participant_workspace(
        session_value, 1, 0
    );
    IF workspace #>> '{study,status}' <> 'open'
       OR jsonb_array_length(workspace -> 'items') <> 1
       OR workspace ->> 'has_more' <> 'true'
       OR workspace #>> '{items,0,item_id}' <> item::TEXT
       OR workspace #>> '{items,0,my_reasoning}' <> 'Updated private reasoning'
       OR workspace #>> '{items,0,my_score}' <> '45.0000' THEN
        RAISE EXCEPTION 'participant workspace did not return only current own answer';
    END IF;
    IF workspace::TEXT LIKE '%another participant private note%' THEN
        RAISE EXCEPTION 'participant workspace returned another participant private answer';
    END IF;
    workspace := kokonut_security.get_location_delphi_participant_workspace(
        session_value, 1, 1
    );
    IF jsonb_array_length(workspace -> 'items') <> 1
       OR workspace ->> 'has_more' <> 'false'
       OR workspace #>> '{items,0,item_id}' <> 'd7000000-0000-4000-8000-000000000003' THEN
        RAISE EXCEPTION 'participant workspace page offset did not return the next question';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_participant_contribution_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private answer receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

UPDATE public.delphi_study
   SET status = 'closed', closed_at = clock_timestamp(), updated_at = clock_timestamp()
 WHERE id = 'e6000000-0000-4000-8000-000000000001';
SET ROLE kokonut_runtime;
BEGIN;
DO $$
DECLARE replayed RECORD;
    denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO replayed
      FROM kokonut_security.submit_location_delphi_participant_contribution(
          current_setting('test.delphi_participant_session'),
          current_setting('test.delphi_participant_csrf'),
          'd7000000-0000-4000-8000-000000000001', 42.1250, 'My private reasoning',
          'c7000000-0000-4000-8000-000000000201'
      );
    IF NOT replayed.replayed THEN
        RAISE EXCEPTION 'exact accepted request did not replay after study closure';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_contribution(
            current_setting('test.delphi_participant_session'),
            current_setting('test.delphi_participant_csrf'),
            'd7000000-0000-4000-8000-000000000001', 50, 'late answer',
            'c7000000-0000-4000-8000-000000000304'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'closed study accepted a new answer'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    item UUID := 'd7000000-0000-4000-8000-000000000001';
    member_id UUID := current_setting('test.delphi_participant_member_id')::UUID;
BEGIN
    IF (SELECT count(*) FROM public.delphi_contribution
         WHERE item_id = item AND panel_member_id = member_id) <> 1
       OR (SELECT count(*) FROM public.delphi_consensus_history
            WHERE item_id = item) <> 2
       OR (SELECT participant_count FROM public.delphi_consensus
            WHERE item_id = item) <> 2 THEN
        RAISE EXCEPTION 'answer upsert, live consensus, or history did not match writes';
    END IF;
END $$;

DO $$
DECLARE withdrawn RECORD;
    denied BOOLEAN := FALSE;
    session_value TEXT := current_setting('test.delphi_participant_session');
    csrf_value TEXT := current_setting('test.delphi_participant_csrf');
    member_id UUID := current_setting('test.delphi_participant_member_id')::UUID;
BEGIN
    SELECT * INTO withdrawn FROM kokonut_security.withdraw_location_delphi_participant(
        session_value, csrf_value, 'c7000000-0000-4000-8000-000000000301'
    );
    IF withdrawn.status <> 'withdrawn' OR withdrawn.replayed THEN
        RAISE EXCEPTION 'participant withdrawal did not complete';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.get_location_delphi_participant_workspace(
            session_value, 50, 0
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'withdrawn participant retained workspace access'; END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_participant_contribution(
            session_value, csrf_value,
            'd7000000-0000-4000-8000-000000000001', 50, 'after withdrawal',
            'c7000000-0000-4000-8000-000000000302'
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'withdrawn participant submitted another answer'; END IF;
    IF (SELECT consent_status FROM public.delphi_panel_member WHERE id = member_id) <> 'withdrawn'
       OR (SELECT count(*) FROM public.delphi_contribution
            WHERE panel_member_id = member_id) <> 1 THEN
        RAISE EXCEPTION 'withdrawal deleted or failed to withdraw prior private answer';
    END IF;
END $$;

DO $$
DECLARE role_name TEXT;
    denied BOOLEAN := FALSE;
BEGIN
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.get_location_delphi_participant_workspace(text,integer,integer)',
        'EXECUTE'
    ) OR NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.submit_location_delphi_participant_contribution(text,text,uuid,numeric,text,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'runtime cannot call the bounded participant functions';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF has_table_privilege(
            role_name, 'kokonut_security.delphi_participant_contribution_request', 'SELECT'
        ) OR has_table_privilege(
            role_name, 'kokonut_security.delphi_participant_contribution_request', 'INSERT'
        ) THEN
            RAISE EXCEPTION '% has direct access to participant answer receipts', role_name;
        END IF;
        IF has_function_privilege(
            role_name,
            'kokonut_security.submit_location_delphi_participant_contribution(text,text,uuid,numeric,text,uuid)',
            'EXECUTE'
        ) IS DISTINCT FROM (role_name = 'kokonut_runtime') THEN
            RAISE EXCEPTION '% has an unexpected participant writer grant', role_name;
        END IF;
    END LOOP;
    IF (SELECT pg_catalog.pg_get_userbyid(proc.proowner)
          FROM pg_catalog.pg_proc AS proc
         WHERE proc.oid = pg_catalog.to_regprocedure(
            'kokonut_security.submit_location_delphi_participant_contribution(text,text,uuid,numeric,text,uuid)'
         )) <> 'kokonut_delphi_participant' THEN
        RAISE EXCEPTION 'participant writer does not use the isolated function owner';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-workspace-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 637 applies and replays after the participant acceptance chain",
        "draft workspace hides all questionnaire items until study opening",
        "workspace shows only the current participant's answer and bounded question pages",
        "answer writes validate session, CSRF, consent, item/study, score range, and open state",
        "answer updates preserve one contribution row and refresh consensus plus history",
        "exact retries replay, changed request collisions fail, unchanged answers avoid duplicate history",
        "withdrawal serializes with contribution access and preserves prior answer data",
        "runtime and Directus lack direct answer-receipt access; writer is owned by isolated role",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_637.name,
        "database_target": "new disposable PostgreSQL 16 container with networking disabled",
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
            "ALTER TABLE public.delphi_panel_member "
            "ADD COLUMN participant_ref_type varchar(30) NOT NULL DEFAULT 'agent' "
            "CHECK (participant_ref_type IN ('farmer_identity','stakeholder_group','guild_contributor','agent')); "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN is_anonymous boolean NOT NULL DEFAULT true; "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN role varchar(20) NOT NULL DEFAULT 'expert'; "
            "ALTER TABLE public.delphi_study ADD COLUMN created_by uuid; "
            "ALTER TABLE public.delphi_study ADD COLUMN facilitator_type varchar(20) NOT NULL DEFAULT 'agent'; "
            "ALTER TABLE public.delphi_study ALTER COLUMN created_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_study ALTER COLUMN updated_at SET DEFAULT clock_timestamp();",
        )
        psql(
            docker,
            container,
            "CREATE TABLE public.delphi_consensus ("
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), "
            "study_id uuid NOT NULL, item_id uuid NOT NULL UNIQUE, median numeric, mean numeric, "
            "iqr numeric, stddev numeric, cv numeric, participant_count integer NOT NULL DEFAULT 0, "
            "weighted_median numeric, consensus_reached boolean NOT NULL DEFAULT false, "
            "computed_at timestamptz NOT NULL DEFAULT clock_timestamp()); "
            "CREATE TABLE public.delphi_consensus_history ("
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), study_id uuid NOT NULL, "
            "item_id uuid NOT NULL, median numeric, iqr numeric, "
            "participant_count integer NOT NULL DEFAULT 0, "
            "computed_at timestamptz NOT NULL DEFAULT clock_timestamp()); "
            "ALTER TABLE public.delphi_contribution ADD CONSTRAINT "
            "delphi_contribution_item_panel_unique UNIQUE (item_id, panel_member_id); "
            "ALTER TABLE public.delphi_contribution ALTER COLUMN updated_at "
            "SET DEFAULT clock_timestamp();",
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
            ("637", MIGRATION_637),
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
        stage = "participant_workspace_and_contributions"
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
