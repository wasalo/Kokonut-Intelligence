#!/usr/bin/env python3
"""Replay and exercise migration 636 on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_previous_path = ROOT / "scripts/check-delphi-participant-invite-disposable.py"
_previous_spec = importlib.util.spec_from_file_location("delphi_invite_disposable", _previous_path)
if _previous_spec is None or _previous_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_previous = importlib.util.module_from_spec(_previous_spec)
_previous_spec.loader.exec_module(_previous)
_review = _previous._review
_draft = _previous._draft
_lifecycle = _previous._lifecycle
_items = _previous._items
_readiness = _previous._readiness
_consent = _previous._previous

MIGRATION_636 = ROOT / "schemas/postgres/636_location_scoped_delphi_participant_acceptance.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-participant-acceptance-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.operator_scope_grant
    (id, operator_id, location_id, resource, action, organization_id, revoked_at)
VALUES
    ('c7000000-0000-4000-8000-000000000001',
     'a0000000-0000-4000-8000-000000000002',
     'b0000000-0000-4000-8000-000000000001',
     'delphi', 'invite', 'f0000000-0000-4000-8000-000000000001', NULL);

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
    retried RECORD;
    withdrawn RECORD;
    withdrawal_retry RECORD;
    denied BOOLEAN := FALSE;
    session_value TEXT := repeat('c3', 32);
    csrf_value TEXT := repeat('d4', 32);
BEGIN
    SELECT * INTO issued FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'c6000000-0000-4000-8000-000000000201'
    );
    IF issued.status IS DISTINCT FROM 'pending' OR issued.invite_token IS NULL THEN
        RAISE EXCEPTION 'test invite was not issued';
    END IF;
    PERFORM set_config('test.delphi_participant_invite_token', issued.invite_token, false);

    SELECT * INTO preview FROM kokonut_security.preview_location_delphi_participant_invite(
        issued.invite_token
    );
    IF preview.study_title IS DISTINCT FROM 'Consent notice review'
       OR preview.notice_version IS DISTINCT FROM 'v2'
       OR preview.notice_digest IS DISTINCT FROM issued.consent_notice_digest
       OR preview.notice_text IS NULL THEN
        RAISE EXCEPTION 'preview did not return the invite-bound current notice';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.accept_location_delphi_participant_invite(
            issued.invite_token, issued.consent_notice_digest, session_value, csrf_value,
            'c6000000-0000-4000-8000-000000000202', FALSE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'negative or absent acceptance was allowed'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.accept_location_delphi_participant_invite(
            issued.invite_token, issued.consent_notice_digest, session_value, session_value,
            'c6000000-0000-4000-8000-000000000206', TRUE
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'session token was reused as the readable CSRF token'; END IF;

    SELECT * INTO accepted FROM kokonut_security.accept_location_delphi_participant_invite(
        issued.invite_token, issued.consent_notice_digest, session_value, csrf_value,
        'c6000000-0000-4000-8000-000000000202', TRUE
    );
    IF accepted.status IS DISTINCT FROM 'accepted' OR accepted.replayed
       OR accepted.notice_version IS DISTINCT FROM 'v2'
       OR accepted.session_expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'consent acceptance did not create a live participant session';
    END IF;

    SELECT * INTO retried FROM kokonut_security.accept_location_delphi_participant_invite(
        issued.invite_token, issued.consent_notice_digest, session_value, csrf_value,
        'c6000000-0000-4000-8000-000000000202', TRUE
    );
    IF NOT retried.replayed OR retried.status IS DISTINCT FROM 'accepted'
       OR retried.accepted_at IS DISTINCT FROM accepted.accepted_at THEN
        RAISE EXCEPTION 'exact acceptance retry was not stable';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.accept_location_delphi_participant_invite(
            issued.invite_token, issued.consent_notice_digest, repeat('e5', 32), csrf_value,
            'c6000000-0000-4000-8000-000000000202', TRUE
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed acceptance credentials were accepted on retry'; END IF;

    SELECT * INTO withdrawn FROM kokonut_security.withdraw_location_delphi_participant(
        session_value, csrf_value, 'c6000000-0000-4000-8000-000000000203'
    );
    IF withdrawn.status IS DISTINCT FROM 'withdrawn' OR withdrawn.replayed THEN
        RAISE EXCEPTION 'withdrawal did not revoke the participant session';
    END IF;

    SELECT * INTO withdrawal_retry FROM kokonut_security.withdraw_location_delphi_participant(
        session_value, csrf_value, 'c6000000-0000-4000-8000-000000000203'
    );
    IF withdrawal_retry.status IS DISTINCT FROM 'withdrawn' OR NOT withdrawal_retry.replayed
       OR withdrawal_retry.withdrawn_at IS DISTINCT FROM withdrawn.withdrawn_at THEN
        RAISE EXCEPTION 'exact withdrawal retry was not stable';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.withdraw_location_delphi_participant(
            session_value, csrf_value, 'c6000000-0000-4000-8000-000000000204'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed withdrawal retry was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.withdraw_location_delphi_participant(
            session_value, repeat('e5', 32), 'c6000000-0000-4000-8000-000000000205'
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched CSRF token was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_participant_session;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read participant sessions'; END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_participant_consent_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private consent events'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE member_record RECORD;
    session_record RECORD;
    invite_record RECORD;
    invite_token_value TEXT := current_setting('test.delphi_participant_invite_token');
    session_digest BYTEA := public.digest(convert_to(repeat('c3', 32), 'UTF8'), 'sha256');
    csrf_digest BYTEA := public.digest(convert_to(repeat('d4', 32), 'UTF8'), 'sha256');
    denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO invite_record FROM kokonut_security.delphi_participant_invite
     WHERE token_digest = public.digest(convert_to(
        invite_token_value, 'UTF8'), 'sha256');
    IF invite_record.status IS DISTINCT FROM 'accepted'
       OR invite_record.accepted_at IS NULL THEN
        RAISE EXCEPTION 'invite did not enter accepted state';
    END IF;
    SELECT * INTO session_record FROM kokonut_security.delphi_participant_session
     WHERE session_token_digest = session_digest;
    IF session_record.invite_id IS DISTINCT FROM invite_record.id
       OR session_record.csrf_token_digest IS DISTINCT FROM csrf_digest
       OR session_record.status IS DISTINCT FROM 'revoked'
       OR session_record.revoked_at IS NULL THEN
        RAISE EXCEPTION 'only digest credentials were not stored or session was not revoked';
    END IF;
    SELECT * INTO member_record FROM public.delphi_panel_member
     WHERE id = session_record.panel_member_id;
    IF member_record.participant_ref_type IS DISTINCT FROM 'pseudonymous_participant'
       OR member_record.participant_ref_id IS NOT NULL
       OR member_record.is_anonymous IS DISTINCT FROM TRUE
       OR member_record.consent_status IS DISTINCT FROM 'withdrawn' THEN
        RAISE EXCEPTION 'participant was not anonymous, unlinked, or withdrawn';
    END IF;
    IF (SELECT count(*) FROM public.delphi_panel_member
         WHERE study_id = 'e6000000-0000-4000-8000-000000000001'
           AND participant_ref_type = 'pseudonymous_participant') <> 1 THEN
        RAISE EXCEPTION 'exact acceptance retry created a duplicate panel member';
    END IF;
    IF (SELECT count(*) FROM kokonut_security.delphi_participant_consent_event
         WHERE invite_id = invite_record.id AND event_type IN ('accepted', 'withdrawn')) <> 2 THEN
        RAISE EXCEPTION 'acceptance and withdrawal event history is incomplete';
    END IF;
    denied := FALSE;
    BEGIN
        UPDATE kokonut_security.delphi_participant_consent_event
           SET created_at = clock_timestamp()
         WHERE invite_id = invite_record.id AND event_type = 'accepted';
    EXCEPTION WHEN raise_exception THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'participant consent events are mutable'; END IF;
    denied := FALSE;
    BEGIN
        UPDATE kokonut_security.delphi_participant_acceptance_request
           SET payload_digest = public.digest('changed', 'sha256')
         WHERE invite_id = invite_record.id;
    EXCEPTION WHEN raise_exception THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'acceptance request receipts are mutable'; END IF;
    denied := FALSE;
    BEGIN
        DELETE FROM kokonut_security.delphi_participant_withdrawal
         WHERE session_id = session_record.id;
    EXCEPTION WHEN raise_exception THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'withdrawal receipts are deletable'; END IF;
    denied := FALSE;
    BEGIN
        DELETE FROM kokonut_security.delphi_participant_session
         WHERE id = session_record.id;
    EXCEPTION WHEN raise_exception THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'participant sessions are deletable'; END IF;
    IF has_table_privilege(
        'kokonut_directus_runtime', 'kokonut_security.delphi_participant_session', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'kokonut_security.delphi_participant_consent_event', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'Directus can read participant credential or consent history';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.accept_location_delphi_participant_invite(text,text,text,text,uuid,boolean)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.accept_location_delphi_participant_invite(text,text,text,text,uuid,boolean)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'acceptance function execution boundary is incorrect';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.withdraw_location_delphi_participant(text,text,uuid)', 'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.withdraw_location_delphi_participant(text,text,uuid)', 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'withdrawal function execution boundary is incorrect';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-participant-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 636 applies and replays on disposable PostgreSQL 16",
        "preview exposes only the study title and exact currently approved notice",
        "acceptance requires explicit true consent and the invite-bound notice digest",
        "one-time acceptance creates an anonymous panel member with no party reference",
        "session and CSRF credentials are stored only as digests",
        "exact acceptance retries are idempotent and changed credentials are rejected",
        "withdrawal revokes the session and changes consent to withdrawn",
        "exact withdrawal retry is stable and changed requests or CSRF tokens are rejected",
        "acceptance and withdrawal histories are append-only and complete",
        "runtime and Directus cannot directly read or mutate credential and consent ledgers",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_636.name,
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
        migrations = (
            ("449", _draft.MIGRATION_449),
            ("450", _draft.MIGRATION_450),
            ("451", _draft.MIGRATION_451),
            ("630", _draft.MIGRATION_630),
            ("631", _lifecycle.MIGRATION_631),
            ("632", _items.MIGRATION_632),
            ("633", _readiness.MIGRATION_633),
            ("634", _consent.MIGRATION_634),
            ("635", _previous.MIGRATION_635),
            ("636", MIGRATION_636),
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
        psql(docker, container, _previous.acceptance_sql())
        stage = "participant_acceptance"
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
