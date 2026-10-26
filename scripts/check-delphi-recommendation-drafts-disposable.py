#!/usr/bin/env python3
"""Exercise migration 451 on a new disposable local PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_review_path = ROOT / "scripts/check-delphi-recommendation-review-disposable.py"
_review_spec = importlib.util.spec_from_file_location("delphi_review_disposable", _review_path)
if _review_spec is None or _review_spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_review = importlib.util.module_from_spec(_review_spec)
_review_spec.loader.exec_module(_review)

MIGRATION_449 = ROOT / "schemas/postgres/449_location_scoped_delphi_consultation_read.sql"
MIGRATION_450 = ROOT / "schemas/postgres/450_location_scoped_delphi_recommendation_review.sql"
MIGRATION_451 = ROOT / "schemas/postgres/451_location_scoped_delphi_recommendation_drafts.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-027-delphi-recommendation-drafts-disposable.json"
IMAGE = "postgis/postgis:16-3.4"

run = _review.run
psql = _review.psql
wait_ready = _review.wait_ready


def draft_fixture() -> str:
    return _review.delphi_fixture() + r"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'delphi', 'draft', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.delphi_study VALUES
 ('d0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000001', 'Open draftable study', NULL, 'real_time', 'open', '{}', NULL, NULL, clock_timestamp(), clock_timestamp()),
 ('d0000000-0000-4000-8000-000000000006', 'b0000000-0000-4000-8000-000000000001', 'Draft status is not eligible', NULL, 'real_time', 'draft', '{}', NULL, NULL, clock_timestamp(), clock_timestamp());
"""


def acceptance_sql() -> str:
    return r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    eligible_count INTEGER;
    has_open BOOLEAN;
    has_draft_status BOOLEAN;
    created RECORD;
    retry RECORD;
    second_draft RECORD;
    denied BOOLEAN;
BEGIN
    SELECT count(*), bool_or(status = 'open'), bool_or(status = 'draft')
      INTO eligible_count, has_open, has_draft_status
      FROM kokonut_security.list_location_delphi_draftable_studies(
          'b0000000-0000-4000-8000-000000000001', 51, 0
      );
    IF eligible_count <> 4 OR NOT has_open OR has_draft_status THEN
        RAISE EXCEPTION 'study picker leaked status or location scope';
    END IF;

    SELECT * INTO created
      FROM kokonut_security.create_location_delphi_recommendation_draft(
          'b0000000-0000-4000-8000-000000000001',
          'd0000000-0000-4000-8000-000000000001',
          'a1000000-0000-4000-8000-000000000001',
          'Synthetic summary', 'Synthetic draft recommendation'
      );
    SELECT * INTO retry
      FROM kokonut_security.create_location_delphi_recommendation_draft(
          'b0000000-0000-4000-8000-000000000001',
          'd0000000-0000-4000-8000-000000000001',
          'a1000000-0000-4000-8000-000000000001',
          'Synthetic summary', 'Synthetic draft recommendation'
      );
    IF created.recommendation_id IS DISTINCT FROM retry.recommendation_id
       OR created.status <> 'draft' OR retry.status <> 'draft' THEN
        RAISE EXCEPTION 'exact draft retry was not idempotent or changed lifecycle state';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_recommendation_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000001',
            'a1000000-0000-4000-8000-000000000001',
            'Changed summary', 'Synthetic draft recommendation'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'request ID collision with changed content was accepted'; END IF;

    SELECT * INTO second_draft
      FROM kokonut_security.create_location_delphi_recommendation_draft(
          'b0000000-0000-4000-8000-000000000001',
          'd0000000-0000-4000-8000-000000000005',
          'a1000000-0000-4000-8000-000000000002',
          NULL, 'Synthetic open-study draft'
      );
    IF second_draft.status <> 'draft' THEN
        RAISE EXCEPTION 'open study draft did not remain a draft';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_recommendation_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000006',
            'a1000000-0000-4000-8000-000000000003', NULL, 'Not eligible'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'non-open/non-closed study accepted a draft'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_recommendation_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000004',
            'a1000000-0000-4000-8000-000000000004', NULL, 'Cross-location draft'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location study accepted a draft'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_recommendation_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000001',
            'a1000000-0000-4000-8000-000000000005', NULL, repeat('x', 20001)
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'oversized draft text was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_recommendation_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000001',
            'a1000000-0000-4000-8000-000000000006', repeat('s', 4001), 'Summary too large'
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'oversized summary was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_delphi_draftable_studies(
            'b0000000-0000-4000-8000-000000000001', 52, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'out-of-range study page was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM kokonut_security.list_location_delphi_draftable_studies(
            'b0000000-0000-4000-8000-000000000002', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'mismatched signed location context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.delphi_recommendation_draft_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private draft request ledger directly'; END IF;
END $$;
COMMIT;
RESET ROLE;

BEGIN;
SET LOCAL kokonut.tenant_id = 'f0000000-0000-4000-8000-000000000001';
SET LOCAL kokonut.location_id = 'b0000000-0000-4000-8000-000000000001';
SET LOCAL kokonut.actor_id = 'a0000000-0000-4000-8000-000000000003';
SET LOCAL kokonut.actor_type = 'operator';
SET LOCAL ROLE kokonut_runtime;
DO $$
DECLARE denied BOOLEAN := false;
BEGIN
    BEGIN
        PERFORM * FROM kokonut_security.list_location_delphi_draftable_studies(
            'b0000000-0000-4000-8000-000000000001', 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'read-only operator grant accessed the draft study list'; END IF;
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_delphi_recommendation_draft(
            'b0000000-0000-4000-8000-000000000001',
            'd0000000-0000-4000-8000-000000000001',
            'a1000000-0000-4000-8000-000000000007', NULL, 'No draft grant'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'read-only operator grant created a draft'; END IF;
END $$;
ROLLBACK;
RESET ROLE;

DO $$
DECLARE blocked BOOLEAN := false;
BEGIN
    IF (SELECT count(*) FROM public.delphi_recommendation_draft_request) <> 2 THEN
        RAISE EXCEPTION 'exact retry created a duplicate private request record';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'delphi_recommendation_draft_request'
           AND column_name IN ('summary', 'recommendation_text', 'draft_text')
    ) THEN
        RAISE EXCEPTION 'private request ledger stores draft payload content';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.delphi_recommendation
         WHERE id IN (SELECT recommendation_id FROM public.delphi_recommendation_draft_request)
           AND (status <> 'draft' OR approved_by IS NOT NULL OR approved_at IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'draft path approved or changed a recommendation lifecycle state';
    END IF;
    BEGIN
        UPDATE public.delphi_recommendation_draft_request SET request_id = gen_random_uuid();
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'draft request history can be updated'; END IF;
    blocked := false;
    BEGIN
        DELETE FROM public.delphi_recommendation_draft_request;
    EXCEPTION WHEN raise_exception THEN blocked := true;
    END;
    IF NOT blocked THEN RAISE EXCEPTION 'draft request history can be deleted'; END IF;
END $$;

DO $$
BEGIN
    IF has_table_privilege('kokonut_runtime', 'public.delphi_recommendation_draft_request', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_recommendation_draft_request', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_recommendation_draft_request', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.delphi_recommendation_draft_request', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_recommendation_draft_request', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_recommendation_draft_request', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_recommendation_draft_request', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.delphi_recommendation_draft_request', 'DELETE') THEN
        RAISE EXCEPTION 'runtime or Directus has direct access to private draft request history';
    END IF;
    IF has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.create_location_delphi_recommendation_draft(uuid,uuid,uuid,text,text)',
        'EXECUTE'
    ) THEN RAISE EXCEPTION 'Directus can execute the Gateway draft function'; END IF;
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.create_location_delphi_recommendation_draft(uuid,uuid,uuid,text,text)',
        'EXECUTE'
    ) THEN RAISE EXCEPTION 'Gateway runtime cannot execute the bounded draft function'; END IF;
    IF (SELECT pg_get_userbyid(proc.proowner)
          FROM pg_catalog.pg_proc AS proc
         WHERE proc.oid = 'kokonut_security.create_location_delphi_recommendation_draft(uuid,uuid,uuid,text,text)'::regprocedure)
       <> 'kokonut_delphi_recommendation_drafter' THEN
        RAISE EXCEPTION 'draft function owner does not use the dedicated non-login role';
    END IF;
    IF NOT has_column_privilege(
        'kokonut_delphi_recommendation_drafter',
        'public.delphi_study', 'id', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_delphi_recommendation_drafter',
        'public.delphi_study', 'status', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'draft function owner has unsafe study lock privileges';
    END IF;
    IF (SELECT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
                 OR rolreplication OR rolbypassrls
          FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_drafter') THEN
        RAISE EXCEPTION 'draft function owner has unsafe role attributes';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
        WHERE granted_role.rolname = 'kokonut_delphi_recommendation_drafter'
           OR member_role.rolname = 'kokonut_delphi_recommendation_drafter'
    ) THEN RAISE EXCEPTION 'draft function owner has unexpected role membership'; END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-delphi-drafts-check-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 449–451 apply and replay on a new disposable PostgreSQL 16 database",
        "draft study listing requires signed location context and the exact delphi:draft grant",
        "study listing is location-scoped, bounded, and limited to open or closed studies",
        "draft creation only writes draft lifecycle state and exact request retries are idempotent",
        "changed-content collisions, ineligible studies, cross-location studies, and oversized text fail closed",
        "database function page/payload bounds and signed-context location matching are enforced",
        "operators with only delphi:read cannot list draftable studies or create drafts",
        "the private append-only request ledger contains no draft text and is inaccessible to runtime and Directus SQL",
        "Gateway runtime can execute bounded functions while Directus cannot",
        "the non-login draft owner has only the narrow study-row lock privilege needed to serialize study eligibility",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_451.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": checks,
    }
    stage = "container_start"
    try:
        run([
            docker, "run", "--rm", "--detach", "--name", container,
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "--publish", "127.0.0.1::5432", IMAGE,
        ])
        wait_ready(container, docker)
        stage = "base_fixture"
        psql(docker, container, _review.FIXTURE)
        psql(docker, container, draft_fixture())
        for version, migration in (
            ("449", MIGRATION_449),
            ("450", MIGRATION_450),
            ("451", MIGRATION_451),
        ):
            stage = f"migration_{version}_apply_and_replay"
            sql = migration.read_text(encoding="utf-8")
            psql(docker, container, sql)
            psql(docker, container, sql)
        stage = "acceptance"
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
