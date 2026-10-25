#!/usr/bin/env python3
"""Replay and exercise migration 638 invite inventory on disposable PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_workspace_path = ROOT / "scripts/check-delphi-participant-workspace-disposable.py"
_workspace_spec = importlib.util.spec_from_file_location("delphi_workspace_disposable", _workspace_path)
if _workspace_spec is None or _workspace_spec.loader is None:
    raise RuntimeError("could not load Delphi workspace disposable PostgreSQL helpers")
_workspace = importlib.util.module_from_spec(_workspace_spec)
_workspace_spec.loader.exec_module(_workspace)
_review = _workspace._review
_draft = _workspace._draft
_lifecycle = _workspace._lifecycle
_items = _workspace._items
_readiness = _workspace._readiness
_consent = _workspace._consent
_invites = _workspace._invites
_participant = _workspace._participant

MIGRATION_638 = ROOT / "schemas/postgres/638_location_scoped_delphi_invite_inventory.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-participant-invite-console-disposable.json"
IMAGE = _workspace.IMAGE
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
DECLARE first_page JSONB;
    second_page JSONB;
    denied BOOLEAN := FALSE;
BEGIN
    first_page := kokonut_security.list_location_delphi_participant_invites(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 1, 0
    );
    IF first_page ->> 'location_id' <> 'b0000000-0000-4000-8000-000000000001'
       OR first_page ->> 'study_id' <> 'e6000000-0000-4000-8000-000000000001'
       OR jsonb_array_length(first_page -> 'invites') <> 1
       OR first_page ->> 'has_more' <> 'true' THEN
        RAISE EXCEPTION 'invite inventory first page scope or bounds are incorrect';
    END IF;
    IF first_page::TEXT LIKE '%invite_token%'
       OR first_page::TEXT LIKE '%token_digest%'
       OR first_page::TEXT LIKE '%consent_notice_digest%'
       OR first_page::TEXT LIKE '%created_by%' THEN
        RAISE EXCEPTION 'invite inventory disclosed a secret or operator identity';
    END IF;

    second_page := kokonut_security.list_location_delphi_participant_invites(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001', 1, 1
    );
    IF jsonb_array_length(second_page -> 'invites') <> 1
       OR second_page ->> 'has_more' <> 'false'
       OR first_page #>> '{invites,0,invite_id}' = second_page #>> '{invites,0,invite_id}' THEN
        RAISE EXCEPTION 'invite inventory paging duplicated or lost an invite';
    END IF;

    denied := FALSE;
    BEGIN
        PERFORM kokonut_security.list_location_delphi_participant_invites(
            'b0000000-0000-4000-8000-000000000099',
            'e6000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invite inventory accepted a mismatched location'; END IF;

    denied := FALSE;
    BEGIN
        PERFORM kokonut_security.list_location_delphi_participant_invites(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 51, 0
        );
    EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invite inventory accepted an unbounded page'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000003', true);
    denied := FALSE;
    BEGIN
        PERFORM kokonut_security.list_location_delphi_participant_invites(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'invite inventory accepted an operator without invite grant'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.list_location_delphi_participant_invites(uuid,uuid,integer,integer)',
        'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.list_location_delphi_participant_invites(uuid,uuid,integer,integer)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'invite inventory function grants are incorrect';
    END IF;
    IF has_table_privilege(
        'kokonut_runtime', 'kokonut_security.delphi_participant_invite', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_directus_runtime', 'kokonut_security.delphi_participant_invite', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'runtime role has direct invite table access';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-invite-queue-{uuid.uuid4().hex[:8]}"
    checks = [
        "migration 638 applies and replays after Delphi invite and participant migrations",
        "invite inventory returns bounded status metadata with no tokens, digests, or operator IDs",
        "pagination returns disjoint invite rows and an accurate has_more flag",
        "cross-location context, absent invite grant, and invalid page bounds are denied",
        "runtime may execute the projection while Runtime/Directus cannot read invite tables",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_638.name,
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
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), study_id uuid NOT NULL, "
            "item_id uuid NOT NULL UNIQUE, median numeric, mean numeric, iqr numeric, stddev numeric, "
            "cv numeric, participant_count integer NOT NULL DEFAULT 0, weighted_median numeric, "
            "consensus_reached boolean NOT NULL DEFAULT false, computed_at timestamptz NOT NULL DEFAULT clock_timestamp()); "
            "CREATE TABLE public.delphi_consensus_history ("
            "id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(), study_id uuid NOT NULL, "
            "item_id uuid NOT NULL, median numeric, iqr numeric, participant_count integer NOT NULL DEFAULT 0, "
            "computed_at timestamptz NOT NULL DEFAULT clock_timestamp()); "
            "ALTER TABLE public.delphi_contribution ADD CONSTRAINT "
            "delphi_contribution_item_panel_unique UNIQUE (item_id, panel_member_id); "
            "ALTER TABLE public.delphi_contribution ALTER COLUMN updated_at SET DEFAULT clock_timestamp();",
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
            ("637", _workspace.MIGRATION_637),
            ("638", MIGRATION_638),
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
        stage = "invite_inventory_acceptance"
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
