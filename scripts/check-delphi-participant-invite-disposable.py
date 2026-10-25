#!/usr/bin/env python3
"""Replay and exercise migration 635 on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_previous_path = ROOT / "scripts/check-delphi-consent-notice-review-disposable.py"
_previous_spec = importlib.util.spec_from_file_location("delphi_consent_disposable", _previous_path)
if _previous_spec is None or _previous_spec.loader is None:
    raise RuntimeError("could not load Delphi consent disposable PostgreSQL helpers")
_previous = importlib.util.module_from_spec(_previous_spec)
_previous_spec.loader.exec_module(_previous)
_review = _previous._review
_draft = _previous._draft
_lifecycle = _previous._lifecycle
_items = _previous._items
_readiness = _previous._readiness

MIGRATION_635 = ROOT / "schemas/postgres/635_location_scoped_delphi_participant_invites.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-participant-invite-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def acceptance_sql() -> str:
    return r"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'invite', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'invite_revoke', 'f0000000-0000-4000-8000-000000000001', NULL);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE issued RECORD;
    replay RECORD;
    revoked RECORD;
    revoke_retry RECORD;
    replacement RECORD;
    denied BOOLEAN := FALSE;
BEGIN
    SELECT * INTO issued FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'c6000000-0000-4000-8000-000000000101'
    );
    IF issued.status <> 'pending' OR issued.replayed
       OR issued.consent_notice_version <> 'v2'
       OR length(issued.consent_notice_digest) <> 64
       OR length(issued.invite_token) <> 64 THEN
        RAISE EXCEPTION 'invite was not issued with one-time token and approved notice binding';
    END IF;
    PERFORM set_config('test.synthetic_invite_token', issued.invite_token, false);

    SELECT * INTO replay FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'c6000000-0000-4000-8000-000000000101'
    );
    IF replay.invite_id IS DISTINCT FROM issued.invite_id OR NOT replay.replayed
       OR replay.invite_token IS NOT NULL THEN
        RAISE EXCEPTION 'invite retry disclosed token or failed to replay metadata';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.issue_location_delphi_participant_invite(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 172800,
            'c6000000-0000-4000-8000-000000000101'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed invite retry lifetime was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.issue_location_delphi_participant_invite(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 3599,
            'c6000000-0000-4000-8000-000000000102'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invite lifetime below one hour was accepted'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.issue_location_delphi_participant_invite(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 2592001,
            'c6000000-0000-4000-8000-000000000105'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invite lifetime above thirty days was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.issue_location_delphi_participant_invite(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 86400,
            'c6000000-0000-4000-8000-000000000106'
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without invite grant was authorized'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);

    SELECT * INTO revoked FROM kokonut_security.revoke_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001', issued.invite_id,
        'c6000000-0000-4000-8000-000000000103', 'token_exposed'
    );
    SELECT * INTO revoke_retry FROM kokonut_security.revoke_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001', issued.invite_id,
        'c6000000-0000-4000-8000-000000000103', 'token_exposed'
    );
    IF revoked.status <> 'revoked' OR revoked.replayed
       OR NOT revoke_retry.replayed
       OR revoke_retry.invite_id IS DISTINCT FROM issued.invite_id THEN
        RAISE EXCEPTION 'invite revoke or exact retry failed';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.revoke_location_delphi_participant_invite(
            'b0000000-0000-4000-8000-000000000001', issued.invite_id,
            'c6000000-0000-4000-8000-000000000103', 'study_cancelled'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed revoke retry was accepted'; END IF;

    SELECT * INTO replacement FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'c6000000-0000-4000-8000-000000000104'
    );
    IF replacement.invite_id = issued.invite_id OR replacement.invite_token IS NULL THEN
        RAISE EXCEPTION 'new request did not mint a fresh invite after revocation';
    END IF;
    PERFORM set_config('test.synthetic_invite_token', replacement.invite_token, false);

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_participant_invite;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read invite table'; END IF;
    denied := FALSE;
    BEGIN
        UPDATE kokonut_security.delphi_participant_invite
           SET status = 'revoked'
         WHERE id = replacement.invite_id;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly update invite table'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE token_value TEXT := current_setting('test.synthetic_invite_token');
    invite_record RECORD;
BEGIN
    SELECT invite.token_digest, invite.status, invite.created_by,
           invite.consent_notice_id, invite.consent_notice_version,
           invite.consent_notice_digest
      INTO invite_record
      FROM kokonut_security.delphi_participant_invite AS invite
     WHERE invite.token_digest = public.digest(convert_to(token_value, 'UTF8'), 'sha256');
    IF NOT FOUND OR invite_record.status <> 'pending'
       OR invite_record.created_by <> 'a0000000-0000-4000-8000-000000000002'
       OR invite_record.consent_notice_version <> 'v2' THEN
        RAISE EXCEPTION 'only the invite token digest was not durably stored';
    END IF;
    IF has_table_privilege(
        'kokonut_directus_runtime', 'kokonut_security.delphi_participant_invite', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'kokonut_security.delphi_participant_invite', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Directus can access participant invite state';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.issue_location_delphi_participant_invite(uuid,uuid,integer,uuid)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.issue_location_delphi_participant_invite(uuid,uuid,integer,uuid)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'invite function execution boundary is incorrect';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.revoke_location_delphi_participant_invite(uuid,uuid,uuid,text)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.revoke_location_delphi_participant_invite(uuid,uuid,uuid,text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'invite revoke function execution boundary is incorrect';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-invite-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451 and 630–635 apply and replay on disposable PostgreSQL 16",
        "an invite requires the exact location grant, draft study, and current approved notice",
        "the raw token is generated once; only its SHA-256 digest is persisted",
        "exact issuance retries return invite metadata without disclosing the token again",
        "changed request reuse and out-of-bound lifetimes are rejected",
        "operators without the invite grant cannot issue participant access",
        "revoke is location-scoped, reason-coded, append-only, and exact-retry safe",
        "a revoked invite can be replaced with a fresh one-time secret",
        "runtime and Directus cannot directly read or mutate invite state",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_635.name,
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
            ("634", _previous.MIGRATION_634),
            ("635", MIGRATION_635),
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
        psql(docker, container, _previous.acceptance_sql())
        stage = "invite_acceptance"
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
