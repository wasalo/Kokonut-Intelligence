#!/usr/bin/env python3
"""Replay and exercise migration 639 on isolated PostgreSQL 16."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_source = ROOT / "scripts/check-delphi-study-open-readiness-disposable.py"
_spec = importlib.util.spec_from_file_location("delphi_readiness_disposable", _source)
if _spec is None or _spec.loader is None:
    raise RuntimeError("could not load Delphi disposable PostgreSQL helpers")
_readiness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_readiness)
_items = _readiness._items
_lifecycle = _readiness._lifecycle
_draft = _readiness._draft
_review = _readiness._review

MIGRATIONS = [
    _draft.MIGRATION_449,
    _draft.MIGRATION_450,
    _draft.MIGRATION_451,
    _draft.MIGRATION_630,
    _lifecycle.MIGRATION_631,
    _items.MIGRATION_632,
    _readiness.MIGRATION_633,
    ROOT / "schemas/postgres/634_location_delphi_consent_notice_review.sql",
    ROOT / "schemas/postgres/635_location_scoped_delphi_participant_invites.sql",
    ROOT / "schemas/postgres/636_location_scoped_delphi_participant_acceptance.sql",
    ROOT / "schemas/postgres/637_location_scoped_delphi_participant_workspace.sql",
    ROOT / "schemas/postgres/638_location_scoped_delphi_invite_inventory.sql",
    ROOT / "schemas/postgres/639_location_scoped_delphi_stopping_evaluation.sql",
]
OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/cap-027-delphi-stopping-evaluation-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
psql = _review.psql
wait_ready = _review.wait_ready


def fixture_sql() -> str:
    return r"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'evaluate_stopping', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.delphi_study
    (id, location_id, title, description, variation, status, stopping_criteria,
     opened_at, created_at, updated_at, created_by, facilitator_type)
VALUES
    ('e6000000-0000-4000-8000-000000000001',
     'b0000000-0000-4000-8000-000000000001', 'Synthetic stopping study',
     'Disposable fixture', 'real_time', 'open',
     '{"max_duration_hours":24,"stability_pct":5,"min_participants":3,"iqr_threshold":0.4}',
     clock_timestamp() - interval '1 hour', clock_timestamp(), clock_timestamp(),
     'a0000000-0000-4000-8000-000000000002', 'human');
INSERT INTO public.delphi_item (id, study_id, item_type, label, scale, min_value, max_value)
VALUES
    ('d6000000-0000-4000-8000-000000000001', 'e6000000-0000-4000-8000-000000000001', 'issue', 'Synthetic item one', 'desirability', -1, 1),
    ('d6000000-0000-4000-8000-000000000002', 'e6000000-0000-4000-8000-000000000001', 'issue', 'Synthetic item two', 'desirability', -1, 1);
INSERT INTO public.delphi_panel_member
    (id, study_id, display_token, consent_status, expert_weight)
VALUES
    ('d6100000-0000-4000-8000-000000000001', 'e6000000-0000-4000-8000-000000000001', 'synthetic-1', 'granted', 1),
    ('d6100000-0000-4000-8000-000000000002', 'e6000000-0000-4000-8000-000000000001', 'synthetic-2', 'granted', 1),
    ('d6100000-0000-4000-8000-000000000003', 'e6000000-0000-4000-8000-000000000001', 'synthetic-3', 'granted', 1),
    ('d6100000-0000-4000-8000-000000000004', 'e6000000-0000-4000-8000-000000000001', 'synthetic-4', 'withdrawn', 1);
INSERT INTO public.delphi_contribution
    (id, study_id, item_id, panel_member_id, score, reasoning)
VALUES
    ('d6200000-0000-4000-8000-000000000001', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000001', 'd6100000-0000-4000-8000-000000000001', 0.1, 'private synthetic'),
    ('d6200000-0000-4000-8000-000000000002', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000001', 'd6100000-0000-4000-8000-000000000002', 0.2, 'private synthetic'),
    ('d6200000-0000-4000-8000-000000000003', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000001', 'd6100000-0000-4000-8000-000000000003', 0.3, 'private synthetic'),
    ('d6200000-0000-4000-8000-000000000004', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000002', 'd6100000-0000-4000-8000-000000000001', 0.2, 'private synthetic'),
    ('d6200000-0000-4000-8000-000000000005', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000002', 'd6100000-0000-4000-8000-000000000002', 0.3, 'private synthetic'),
    ('d6200000-0000-4000-8000-000000000006', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000002', 'd6100000-0000-4000-8000-000000000004', 0.4, 'withdrawn synthetic');

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE result JSONB;
    replay JSONB;
    denied BOOLEAN := FALSE;
BEGIN
    result := kokonut_security.evaluate_location_delphi_stopping(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001',
        'c6000000-0000-4000-8000-000000000001'
    );
    IF result ->> 'should_stop' <> 'false'
       OR result ->> 'outcome' <> 'insufficient_participation'
       OR result -> 'items' -> 0 ->> 'outcome' <> 'consensus_reached'
       OR result -> 'items' -> 1 ->> 'outcome' <> 'insufficient_participation'
       OR result ? 'participant_count'
       OR result::TEXT LIKE '%private synthetic%' THEN
        RAISE EXCEPTION 'evaluation did not suppress withdrawn answers or expose an unsafe result';
    END IF;
    replay := kokonut_security.evaluate_location_delphi_stopping(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001',
        'c6000000-0000-4000-8000-000000000001'
    );
    IF replay ->> 'replayed' <> 'true' OR replay ->> 'outcome' <> result ->> 'outcome' THEN
        RAISE EXCEPTION 'exact retry did not return the immutable evaluation';
    END IF;
    BEGIN
        PERFORM kokonut_security.evaluate_location_delphi_stopping(
            'b0000000-0000-4000-8000-000000000002',
            'e6000000-0000-4000-8000-000000000001',
            'c6000000-0000-4000-8000-000000000002'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location stopping evaluation was allowed'; END IF;
    BEGIN
        PERFORM * FROM public.delphi_stopping_evaluation;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read private stopping evaluations'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.delphi_stopping_evaluation_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read stopping request receipts'; END IF;
END $$;
COMMIT;
RESET ROLE;

INSERT INTO public.delphi_contribution
    (id, study_id, item_id, panel_member_id, score, reasoning)
VALUES
    ('d6200000-0000-4000-8000-000000000007', 'e6000000-0000-4000-8000-000000000001', 'd6000000-0000-4000-8000-000000000002', 'd6100000-0000-4000-8000-000000000003', 0.4, 'private synthetic');
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE result JSONB;
    denied BOOLEAN := FALSE;
BEGIN
    result := kokonut_security.evaluate_location_delphi_stopping(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001',
        'c6000000-0000-4000-8000-000000000002'
    );
    IF result ->> 'should_stop' <> 'true'
       OR result ->> 'outcome' <> 'consensus_reached'
       OR result ? 'participant_count' THEN
        RAISE EXCEPTION 'current consented participation did not meet stopping rule';
    END IF;
    IF has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.evaluate_location_delphi_stopping(uuid,uuid,uuid)', 'EXECUTE'
    ) IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'runtime cannot call the bounded evaluator';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime')
       AND has_function_privilege(
           'kokonut_directus_runtime',
           'kokonut_security.evaluate_location_delphi_stopping(uuid,uuid,uuid)', 'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'Directus can invoke Delphi stopping evaluation';
    END IF;
    BEGIN
        UPDATE public.delphi_stopping_evaluation SET outcome = 'continue';
    EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can mutate stopping evaluations'; END IF;
END $$;
COMMIT;
RESET ROLE;

UPDATE public.delphi_contribution
   SET score = CASE panel_member_id
       WHEN 'd6100000-0000-4000-8000-000000000001' THEN -0.8
       WHEN 'd6100000-0000-4000-8000-000000000002' THEN 0
       WHEN 'd6100000-0000-4000-8000-000000000003' THEN 0.8
       ELSE score END
 WHERE item_id = 'd6000000-0000-4000-8000-000000000002';
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE first_check JSONB;
    stable_check JSONB;
    denied BOOLEAN := FALSE;
BEGIN
    first_check := kokonut_security.evaluate_location_delphi_stopping(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001',
        'c6000000-0000-4000-8000-000000000003'
    );
    IF first_check ->> 'should_stop' <> 'false'
       OR first_check -> 'items' -> 1 ->> 'outcome' <> 'continue' THEN
        RAISE EXCEPTION 'unstable wide dispersion was treated as a stopping condition';
    END IF;
    stable_check := kokonut_security.evaluate_location_delphi_stopping(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001',
        'c6000000-0000-4000-8000-000000000004'
    );
    IF stable_check ->> 'should_stop' <> 'true'
       OR stable_check ->> 'outcome' <> 'stable_without_consensus'
       OR stable_check -> 'items' -> 1 ->> 'outcome' <> 'stable_without_consensus' THEN
        RAISE EXCEPTION 'stable repeat evaluation did not meet the configured stability rule';
    END IF;
    BEGIN
        PERFORM kokonut_security.evaluate_location_delphi_stopping(
            'b0000000-0000-4000-8000-000000000001',
            'e6000000-0000-4000-8000-000000000099',
            'c6000000-0000-4000-8000-000000000001'
        );
    EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'request ID reuse with changed study scope was accepted'; END IF;
END $$;
COMMIT;
RESET ROLE;

UPDATE public.delphi_panel_member
   SET consent_status = 'withdrawn'
 WHERE id = 'd6100000-0000-4000-8000-000000000003';
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE result JSONB;
BEGIN
    result := kokonut_security.evaluate_location_delphi_stopping(
        'b0000000-0000-4000-8000-000000000001',
        'e6000000-0000-4000-8000-000000000001',
        'c6000000-0000-4000-8000-000000000005'
    );
    IF result ->> 'should_stop' <> 'false'
       OR result -> 'items' -> 0 ->> 'outcome' <> 'insufficient_participation'
       OR result -> 'items' -> 1 ->> 'outcome' <> 'insufficient_participation' THEN
        RAISE EXCEPTION 'withdrawn participant response remained eligible for stopping';
    END IF;
END $$;
COMMIT;
RESET ROLE;
DO $$
BEGIN
    IF (SELECT status FROM public.delphi_study
         WHERE id = 'e6000000-0000-4000-8000-000000000001') <> 'open' THEN
        RAISE EXCEPTION 'stopping evaluation changed the study lifecycle state';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-stopping-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATIONS[-1].name,
        "database_target": "new disposable PostgreSQL 16 container",
        "network_mode": "none",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 449–451 and 630–639 apply and replay in order",
            "stopping evaluation uses the signed exact-location evaluate_stopping grant",
            "current withdrawn consent is excluded from per-item aggregates",
            "stability uses prior consent-filtered evaluations and insufficient current participation blocks stopping",
            "consensus, insufficient participation, and advisory study results are bounded",
            "exact retries replay and cross-location scope fails closed",
            "runtime cannot read or mutate evaluation rows or receipts; Directus cannot execute the function",
        ],
    }
    stage = "container_start"
    try:
        subprocess.run(
            [docker, "run", "--rm", "--detach", "--name", container,
             "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE],
            check=True, capture_output=True, text=True,
        )
        wait_ready(container, docker)
        psql(docker, container, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        psql(docker, container, _review.FIXTURE)
        psql(docker, container, _review.delphi_fixture())
        psql(
            docker,
            container,
            "ALTER TABLE public.delphi_study ADD COLUMN created_by uuid; "
            "ALTER TABLE public.delphi_study ADD COLUMN facilitator_type varchar(20) NOT NULL DEFAULT 'agent'; "
            "ALTER TABLE public.delphi_study ALTER COLUMN created_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_study ALTER COLUMN updated_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN participant_ref_type varchar(30) NOT NULL DEFAULT 'agent'; "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN role varchar(20) NOT NULL DEFAULT 'expert'; "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN is_anonymous boolean NOT NULL DEFAULT true; "
            "ALTER TABLE public.delphi_panel_member ADD COLUMN joined_at timestamptz NOT NULL DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_item ALTER COLUMN created_at SET DEFAULT clock_timestamp(); "
            "ALTER TABLE public.delphi_contribution ALTER COLUMN updated_at SET DEFAULT clock_timestamp();",
        )
        psql(
            docker,
            container,
            """CREATE TABLE public.delphi_consensus (
                   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                   study_id uuid NOT NULL REFERENCES public.delphi_study(id),
                   item_id uuid NOT NULL UNIQUE REFERENCES public.delphi_item(id),
                   median numeric(10,4), mean numeric(10,4), iqr numeric(10,4),
                   stddev numeric(10,4), cv numeric(10,4), participant_count integer DEFAULT 0,
                   weighted_median numeric(10,4), consensus_reached boolean DEFAULT false,
                   computed_at timestamptz DEFAULT now()
               );
               CREATE TABLE public.delphi_consensus_history (
                   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                   study_id uuid NOT NULL REFERENCES public.delphi_study(id),
                   item_id uuid NOT NULL REFERENCES public.delphi_item(id),
                   median numeric(10,4), iqr numeric(10,4), participant_count integer DEFAULT 0,
                   computed_at timestamptz DEFAULT now()
               );
               CREATE TABLE public.delphi_stopping_evaluation (
                   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                   study_id uuid NOT NULL REFERENCES public.delphi_study(id),
                   item_id uuid REFERENCES public.delphi_item(id),
                   scope varchar(10) NOT NULL CHECK (scope IN ('item','study')),
                   outcome varchar(40) NOT NULL CHECK (outcome IN (
                       'continue','consensus_reached','stable_without_consensus',
                       'time_limit_with_consensus','time_limit_without_consensus',
                       'insufficient_participation','insufficient_stability_history',
                       'incomplete_items','administratively_terminated')),
                   consensus_met boolean NOT NULL, participation_met boolean NOT NULL,
                   stability_met boolean NOT NULL, duration_exceeded boolean NOT NULL,
                   completion_met boolean NOT NULL, normalized_iqr numeric(10,6),
                   median_shift numeric(10,6), detail jsonb NOT NULL DEFAULT '{}'::jsonb,
                   evaluated_at timestamptz NOT NULL DEFAULT now(),
                   CHECK ((scope = 'item' AND item_id IS NOT NULL)
                       OR (scope = 'study' AND item_id IS NULL))
               );""",
        )
        for migration in MIGRATIONS:
            stage = f"migration_{migration.name}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        stage = "consented_stopping_acceptance"
        psql(docker, container, fixture_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(evidence["checks"])
    except Exception as exc:  # noqa: BLE001 - synthetic-only failure evidence
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:1200]
    finally:
        subprocess.run([docker, "rm", "--force", container], check=False, capture_output=True, text=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
