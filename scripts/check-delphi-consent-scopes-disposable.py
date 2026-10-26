#!/usr/bin/env python3
"""Replay Delphi activity-scope migration 641 on disposable PostgreSQL 16."""

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
_prior_spec = importlib.util.spec_from_file_location("delphi_participant_acceptance", _prior_path)
if _prior_spec is None or _prior_spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL setup")
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

MIGRATION_641 = ROOT / "schemas/postgres/641_location_delphi_consent_activity_scopes.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-consent-scopes-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE submitted RECORD;
    retry RECORD;
    preview RECORD;
    issued RECORD;
    accepted RECORD;
    denied BOOLEAN := FALSE;
    notice_id_value UUID;
    session_value TEXT := repeat('e7', 32);
    csrf_value TEXT := repeat('f8', 32);
    expected_digest BYTEA;
BEGIN
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_consent_notice(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 'v-legacy-call',
            'Text only', 'c8000000-0000-4000-8000-000000000211'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'text-only submit function remains executable'; END IF;

    SELECT * INTO submitted FROM kokonut_security.submit_location_delphi_consent_notice_scoped(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 'v3',
        'Participants may submit questionnaire responses and, if chosen, a minority report.',
        ARRAY['minority_reports', 'questionnaire_responses']::TEXT[],
        'c8000000-0000-4000-8000-000000000212'
    );
    IF submitted.status <> 'submitted' OR submitted.replayed THEN
        RAISE EXCEPTION 'scoped notice was not submitted';
    END IF;
    notice_id_value := submitted.notice_id;
    PERFORM set_config('test.delphi_consent_scoped_notice_id', notice_id_value::TEXT, false);

    SELECT * INTO retry FROM kokonut_security.submit_location_delphi_consent_notice_scoped(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 'v3',
        'Participants may submit questionnaire responses and, if chosen, a minority report.',
        ARRAY['questionnaire_responses', 'minority_reports']::TEXT[],
        'c8000000-0000-4000-8000-000000000212'
    );
    IF retry.notice_id IS DISTINCT FROM submitted.notice_id OR NOT retry.replayed THEN
        RAISE EXCEPTION 'scope-order-independent retry was not stable';
    END IF;
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_consent_notice_scoped(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 'v3',
            'Participants may submit questionnaire responses and, if chosen, a minority report.',
            ARRAY['questionnaire_responses']::TEXT[],
            'c8000000-0000-4000-8000-000000000212'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed scope request ID reuse was accepted'; END IF;

    SELECT public.digest(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
        'notice_text', 'Participants may submit questionnaire responses and, if chosen, a minority report.',
        'collection_scopes', ARRAY['questionnaire_responses', 'minority_reports']::TEXT[]
    )::TEXT, 'UTF8'), 'sha256') INTO expected_digest;
    IF pg_catalog.decode(submitted.notice_digest, 'hex') IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'notice digest did not bind text and canonical activity scope';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.submit_location_delphi_consent_notice_scoped(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 'v4',
            'Invalid scope fixture', ARRAY['minority_reports']::TEXT[],
            'c8000000-0000-4000-8000-000000000213'
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'scope without required questionnaire activity was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.decide_location_delphi_consent_notice(
            'b0000000-0000-4000-8000-000000000001',
            'cc000000-0000-4000-8000-000000000001', 'approve',
            'c8000000-0000-4000-8000-000000000218',
            'approved_after_independent_review'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unscoped legacy pending notice was approved'; END IF;
    PERFORM * FROM kokonut_security.decide_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001',
        'cc000000-0000-4000-8000-000000000001', 'reject',
        'c8000000-0000-4000-8000-000000000219', 'privacy_scope_incomplete'
    );
    SELECT * INTO preview FROM kokonut_security.list_location_delphi_consent_notices_scoped(
        'b0000000-0000-4000-8000-000000000001', 51, 0
    ) WHERE notice_id = notice_id_value;
    IF preview.collection_scopes IS DISTINCT FROM
       ARRAY['questionnaire_responses', 'minority_reports']::TEXT[] THEN
        RAISE EXCEPTION 'independent review did not receive structured scope';
    END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := FALSE;
    BEGIN
        PERFORM * FROM kokonut_security.issue_location_delphi_participant_invite(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 86400,
            'c8000000-0000-4000-8000-000000000217'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'unscoped legacy approval issued a new invite'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    PERFORM * FROM kokonut_security.decide_location_delphi_consent_notice(
        'b0000000-0000-4000-8000-000000000001', notice_id_value, 'approve',
        'c8000000-0000-4000-8000-000000000214',
        'approved_after_independent_review'
    );

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    SELECT * INTO issued FROM kokonut_security.issue_location_delphi_participant_invite(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 86400,
        'c8000000-0000-4000-8000-000000000215'
    );
    SELECT * INTO preview FROM kokonut_security.preview_location_delphi_participant_invite_scoped(
        issued.invite_token
    );
    IF preview.collection_scopes IS DISTINCT FROM
       ARRAY['questionnaire_responses', 'minority_reports']::TEXT[]
       OR preview.notice_digest IS DISTINCT FROM issued.consent_notice_digest THEN
        RAISE EXCEPTION 'participant preview omitted or changed the invite-bound activity scope';
    END IF;
    SELECT * INTO accepted FROM kokonut_security.accept_location_delphi_participant_invite(
        issued.invite_token, preview.notice_digest, session_value, csrf_value,
        'c8000000-0000-4000-8000-000000000216', TRUE
    );
    IF accepted.status <> 'accepted' OR accepted.notice_digest IS DISTINCT FROM preview.notice_digest THEN
        RAISE EXCEPTION 'participant acceptance did not bind the scoped notice digest';
    END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE denied BOOLEAN := FALSE;
    notice_id_value UUID := current_setting('test.delphi_consent_scoped_notice_id')::UUID;
BEGIN
    IF has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.submit_location_delphi_consent_notice(uuid,uuid,text,text,uuid)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.list_location_delphi_consent_notices(uuid,integer,integer)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.preview_location_delphi_participant_invite(text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'runtime retains a text-only consent or preview entry point';
    END IF;
    IF has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.submit_location_delphi_consent_notice_scoped(uuid,uuid,text,text,text[],uuid)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.preview_location_delphi_participant_invite_scoped(text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'Directus can call the consent-scope functions';
    END IF;
    BEGIN
        UPDATE kokonut_security.delphi_consent_notice
           SET collection_scopes = ARRAY['questionnaire_responses']::TEXT[]
         WHERE id = notice_id_value;
    EXCEPTION WHEN raise_exception THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'approved notice activity scope was mutable'; END IF;

END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-scopes-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 641 applies and replays after the Delphi consent and participant chain",
        "new notice scopes are allowlisted, canonicalized, required, and immutable",
        "notice and idempotency digests bind the exact text plus structured activity scopes",
        "text-only runtime entry points are revoked while legacy notice rows remain readable",
        "independent review receives scope and cannot approve unscoped pending legacy notices",
        "new invites require a scoped approved notice and preview returns the exact bound scope",
        "participant acceptance records the digest that includes the reviewed scope",
        "Directus cannot call scoped notice or participant preview functions",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_641.name,
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
            ("635", _invites.MIGRATION_635),
        ("636", _prior.MIGRATION_636),
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
        stage = "migration_641_apply_and_replay"
        sql = MIGRATION_641.read_text(encoding="utf-8")
        psql(docker, container, sql)
        psql(docker, container, sql)
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
        stage = "migration_641_legacy_acceptance"
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
