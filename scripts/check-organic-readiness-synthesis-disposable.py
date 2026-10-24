#!/usr/bin/env python3
"""Apply/replay migration 549 and verify signed-view source boundaries."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/549_signed_organic_readiness_synthesis_source.sql"
OUTPUT = Path(os.environ.get(
    "KOKONUT_ORGANIC_WORKER_TEST_OUTPUT",
    ROOT / "docs/refactor/builds/2026-10-22-recovery/cap-038-organic-readiness-source-disposable.json",
))
PLATFORM = os.environ.get("KOKONUT_ORGANIC_WORKER_TEST_PLATFORM", "")
if PLATFORM not in {"", "linux/amd64", "linux/arm64"}:
    raise SystemExit("KOKONUT_ORGANIC_WORKER_TEST_PLATFORM must be linux/amd64 or linux/arm64")
DEFAULT_IMAGE = "sogis/postgis:16-3.4" if PLATFORM == "linux/arm64" else "postgis/postgis:16-3.4"
IMAGE = os.environ.get("KOKONUT_ORGANIC_WORKER_TEST_IMAGE", DEFAULT_IMAGE)
LOCATION_ID = "a0000000-0000-4000-8000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-4000-8000-000000000002"

FIXTURE = f"""
CREATE ROLE kokonut_agent_summary_source_reader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_agent_summary_source_login
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_agent_summary_source_view_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_ai_summary_drafter
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA kokonut_security;
CREATE SCHEMA kokonut_agent_source;
CREATE TABLE public.ai_summary_agent_draft_request (
    summary_type TEXT NOT NULL CHECK (summary_type ~ '^[a-z][a-z0-9_]{{0,99}}$')
);
CREATE TABLE kokonut_security.ai_summary_source_manifest (
    source_table TEXT NOT NULL CONSTRAINT ai_summary_source_manifest_source_table_check
        CHECK (source_table IN ('harvest_event')),
    source_scope TEXT NOT NULL DEFAULT 'location'
);
CREATE TABLE kokonut_security.ai_summary_source_reference_view (
    source_table TEXT PRIMARY KEY,
    source_view_name TEXT NOT NULL,
    source_scope TEXT NOT NULL DEFAULT 'location',
    CHECK (source_view_name ~ '^v_public_[a-z0-9_]{{1,55}}$')
);
CREATE FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
RETURNS TABLE(location_id UUID)
LANGUAGE SQL STABLE AS $$
    SELECT NULLIF(current_setting('kokonut.test_location', TRUE), '')::UUID
     WHERE $1 = 'ai_summary' AND $2 = 'read'
       AND NULLIF(current_setting('kokonut.test_location', TRUE), '') IS NOT NULL
$$;
GRANT USAGE ON SCHEMA public, kokonut_security, kokonut_agent_source
    TO kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_view_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_view_owner;

CREATE TABLE public.organic_readiness_assessment (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, assessment_date DATE,
    standard TEXT, overall_score NUMERIC, transition_progress_pct NUMERIC,
    soil_health_score NUMERIC, input_compliance_pct NUMERIC,
    pest_management_score NUMERIC, biodiversity_score NUMERIC,
    buffer_zone_score NUMERIC, record_completeness_pct NUMERIC,
    training_completion_pct NUMERIC, harvest_segregation_score NUMERIC,
    barriers JSONB, recommendations JSONB, notes TEXT
);
INSERT INTO public.organic_readiness_assessment VALUES
('b0000000-0000-4000-8000-000000000101', '{LOCATION_ID}', CURRENT_DATE, 'IFOAM', 72, 50, 70, 90, 60, 75, 80, 70, 60, 80, '[]', '[]', 'private note'),
('b0000000-0000-4000-8000-000000000201', '{OTHER_LOCATION_ID}', CURRENT_DATE, 'IFOAM', 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, '[]', '[]', 'foreign note');
CREATE VIEW public.v_public_organic_readiness AS
SELECT id, location_id, assessment_date, standard, overall_score,
       transition_progress_pct, soil_health_score, input_compliance_pct,
       pest_management_score, biodiversity_score, buffer_zone_score,
       record_completeness_pct, training_completion_pct,
       harvest_segregation_score, barriers, recommendations
  FROM public.organic_readiness_assessment;

CREATE TABLE public.organic_transition_plan (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, standard TEXT,
    transition_start_date DATE, expected_certification_date DATE,
    current_year INTEGER, total_years_required INTEGER, status TEXT,
    prohibited_substance_free_date DATE, buffer_zone_established_date DATE,
    record_keeping_ready_date DATE, training_completed_date DATE,
    organic_management_plan_date DATE, readiness_score NUMERIC,
    barriers JSONB, notes TEXT
);
INSERT INTO public.organic_transition_plan VALUES
('b0000000-0000-4000-8000-000000000102', '{LOCATION_ID}', 'IFOAM', CURRENT_DATE, CURRENT_DATE, 1, 3, 'active', NULL, NULL, NULL, NULL, NULL, 40, '[]', 'private note'),
('b0000000-0000-4000-8000-000000000202', '{OTHER_LOCATION_ID}', 'IFOAM', CURRENT_DATE, CURRENT_DATE, 1, 3, 'active', NULL, NULL, NULL, NULL, NULL, 40, '[]', 'foreign note');
CREATE VIEW public.v_public_organic_transition AS
SELECT id, location_id, standard, transition_start_date,
       expected_certification_date, current_year, total_years_required, status,
       prohibited_substance_free_date, buffer_zone_established_date,
       record_keeping_ready_date, training_completed_date,
       organic_management_plan_date, readiness_score, barriers
  FROM public.organic_transition_plan;

CREATE TABLE public.organic_input_audit (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, application_date DATE,
    input_category TEXT, input_source TEXT, organic_certified BOOLEAN,
    is_prohibited BOOLEAN, supplier_name TEXT
);
INSERT INTO public.organic_input_audit VALUES
('b0000000-0000-4000-8000-000000000103', '{LOCATION_ID}', CURRENT_DATE, 'fertilizer', 'on_farm', TRUE, FALSE, 'private supplier'),
('b0000000-0000-4000-8000-000000000203', '{OTHER_LOCATION_ID}', CURRENT_DATE, 'fertilizer', 'on_farm', TRUE, FALSE, 'foreign supplier');
CREATE VIEW public.v_public_organic_input_audit AS
SELECT id, location_id, application_date, input_category, input_source,
       organic_certified, is_prohibited FROM public.organic_input_audit;

CREATE TABLE public.buffer_zone (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, buffer_name TEXT,
    buffer_type TEXT, width_m NUMERIC, length_m NUMERIC, area_m2 NUMERIC,
    adjacent_use TEXT, condition_status TEXT, establishment_date DATE,
    last_inspection_date DATE, notes TEXT
);
INSERT INTO public.buffer_zone VALUES
('b0000000-0000-4000-8000-000000000104', '{LOCATION_ID}', 'North', 'hedgerow', 4, 10, 40, 'wildland', 'adequate', CURRENT_DATE, CURRENT_DATE, 'private note'),
('b0000000-0000-4000-8000-000000000204', '{OTHER_LOCATION_ID}', 'South', 'hedgerow', 4, 10, 40, 'wildland', 'adequate', CURRENT_DATE, CURRENT_DATE, 'foreign note');
CREATE VIEW public.v_public_buffer_zone_status AS
SELECT id, location_id, buffer_name, buffer_type, width_m, length_m, area_m2,
       adjacent_use, condition_status, establishment_date, last_inspection_date
  FROM public.buffer_zone;

CREATE TABLE public.harvest_handling_record (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, organic_segregated BOOLEAN,
    equipment_cleaned BOOLEAN, temperature_controlled BOOLEAN,
    buyer_requirements_met BOOLEAN, contamination_risk TEXT,
    organic_lot_number TEXT, notes TEXT
);
INSERT INTO public.harvest_handling_record VALUES
('b0000000-0000-4000-8000-000000000105', '{LOCATION_ID}', TRUE, TRUE, TRUE, TRUE, 'low', 'lot-1', 'private note'),
('b0000000-0000-4000-8000-000000000205', '{OTHER_LOCATION_ID}', TRUE, TRUE, TRUE, TRUE, 'low', 'lot-2', 'foreign note');
CREATE VIEW public.v_public_harvest_segregation AS
SELECT id, location_id, organic_segregated, equipment_cleaned,
       temperature_controlled, buyer_requirements_met, contamination_risk,
       organic_lot_number FROM public.harvest_handling_record;

CREATE TABLE public.organic_certification_record (
    id UUID PRIMARY KEY, location_id UUID NOT NULL
);
INSERT INTO public.organic_certification_record VALUES
('b0000000-0000-4000-8000-000000000106', '{LOCATION_ID}'), ('b0000000-0000-4000-8000-000000000206', '{OTHER_LOCATION_ID}');
CREATE VIEW public.v_public_organic_certifications AS
SELECT id, location_id FROM public.organic_certification_record;

CREATE TABLE public.organic_compliance_checklist (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, findings TEXT, notes TEXT
);
INSERT INTO public.organic_compliance_checklist VALUES
('b0000000-0000-4000-8000-000000000107', '{LOCATION_ID}', 'private finding', 'private note'),
('b0000000-0000-4000-8000-000000000207', '{OTHER_LOCATION_ID}', 'foreign finding', 'foreign note');

CREATE TABLE public.prohibited_substance_record (
    id UUID PRIMARY KEY, location_id UUID NOT NULL,
    compliance_status TEXT, withdrawal_end_date DATE, notes TEXT
);
INSERT INTO public.prohibited_substance_record VALUES
('b0000000-0000-4000-8000-000000000108', '{LOCATION_ID}', 'cleared', CURRENT_DATE, 'private note'),
('b0000000-0000-4000-8000-000000000208', '{OTHER_LOCATION_ID}', 'violation', CURRENT_DATE, 'foreign note');
CREATE VIEW public.v_public_prohibited_substance_audit AS
SELECT id, location_id, compliance_status, withdrawal_end_date
  FROM public.prohibited_substance_record;
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        lines = (result.stderr or result.stdout).strip().splitlines()
        diagnostics = [
            line.strip() for line in lines
            if line.lstrip().startswith(("ERROR:", "DETAIL:", "HINT:", "CONTEXT:"))
        ]
        summary = " | ".join(diagnostics[-12:] or lines[-12:])
        raise RuntimeError(f"command failed ({result.returncode}): {summary[:1200]}")
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return run([
        docker, "exec", "-i", container, "psql", "-X", "-q",
        "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ], input_text=sql)


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker CLI is unavailable")
    container = f"kokonut-organic-source-{uuid.uuid4().hex[:10]}"
    evidence: dict[str, object] = {
        "check": "CAP-038 organic-readiness signed source migration 549",
        "image": IMAGE,
        "requested_platform": PLATFORM or "native",
        "candidate_or_legacy_modified": False,
        "real_credentials_used": False,
        "result": "failed",
        "assertions": [],
    }
    checks: list[str] = []
    try:
        docker_run = [
            docker, "run", "--rm", "--detach", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ]
        if PLATFORM:
            docker_run[2:2] = ["--platform", PLATFORM]
        run(docker_run)
        from time import monotonic, sleep
        deadline = monotonic() + 120
        while monotonic() < deadline:
            ready = subprocess.run(
                [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                text=True, capture_output=True, check=False,
            )
            if ready.returncode == 0:
                break
            sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        architecture = run([docker, "exec", container, "uname", "-m"])
        evidence["server_architecture"] = architecture
        expected_architecture = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(PLATFORM)
        if expected_architecture and architecture != expected_architecture:
            raise RuntimeError(
                f"disposable server architecture was {architecture}, expected {expected_architecture}"
            )

        psql(docker, container, FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration)
        checks.append("migration 549 applies on PostgreSQL 16")
        psql(docker, container, """
INSERT INTO public.ai_summary_agent_draft_request(summary_type)
VALUES ('organic_readiness');
DO $$ BEGIN
    IF (SELECT count(*) FROM kokonut_security.ai_summary_source_reference_view
         WHERE source_table IN (
             'organic_readiness_assessment', 'organic_transition_plan',
             'organic_input_audit', 'buffer_zone', 'harvest_handling_record',
             'organic_certification_record', 'prohibited_substance_record'
         )) <> 7 THEN
        RAISE EXCEPTION 'organic source-reference registry is incomplete';
    END IF;
END $$;
""")
        checks.extend([
            "organic_readiness is accepted by the worker receipt constraint",
            "all seven provenance views are registered",
        ])

        psql(docker, container, """
GRANT SELECT ON public.organic_readiness_assessment,
    public.v_public_organic_readiness TO kokonut_agent_summary_source_reader,
    kokonut_agent_summary_source_login;
GRANT INSERT ON kokonut_agent_source.organic_readiness_assessment
    TO kokonut_agent_summary_source_reader;
GRANT CREATE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_login,
       kokonut_agent_summary_source_view_owner;
""")
        psql(docker, container, migration)
        psql(docker, container, """
BEGIN;
SET LOCAL ROLE kokonut_agent_summary_source_reader;
DO $$ DECLARE visible_rows BIGINT;
BEGIN
    SELECT count(*) INTO visible_rows
      FROM kokonut_agent_source.organic_readiness_assessment;
    IF visible_rows <> 0 THEN
        RAISE EXCEPTION 'organic source rows were visible without location context';
    END IF;
END $$;
ROLLBACK;
""")
        checks.append("scoped views return no rows without context")

        psql(docker, container, f"""
BEGIN;
SELECT set_config('kokonut.test_location', '{LOCATION_ID}', TRUE);
SET LOCAL ROLE kokonut_agent_summary_source_reader;
DO $$
DECLARE visible_rows BIGINT;
BEGIN
    IF has_table_privilege('kokonut_agent_summary_source_reader',
        'public.organic_readiness_assessment', 'SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_login',
        'public.organic_readiness_assessment', 'SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_reader',
        'public.v_public_organic_readiness', 'SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_login',
        'public.v_public_organic_readiness', 'SELECT') THEN
        RAISE EXCEPTION 'source identities retained direct organic table/view access';
    END IF;
    IF has_table_privilege('kokonut_agent_summary_source_reader',
        'kokonut_agent_source.organic_readiness_assessment', 'INSERT')
       OR has_schema_privilege('kokonut_agent_summary_source_reader',
        'kokonut_agent_source', 'CREATE')
       OR has_schema_privilege('kokonut_agent_summary_source_login',
        'kokonut_agent_source', 'CREATE')
       OR has_schema_privilege('kokonut_agent_summary_source_view_owner',
        'kokonut_agent_source', 'CREATE') THEN
        RAISE EXCEPTION 'migration replay retained a stale write/create grant';
    END IF;
    IF NOT has_table_privilege('kokonut_agent_summary_source_reader',
        'kokonut_agent_source.organic_readiness_assessment', 'SELECT') THEN
        RAISE EXCEPTION 'signed reader cannot select its approved projection';
    END IF;
    IF has_table_privilege('kokonut_agent_summary_source_view_owner',
        'public.organic_readiness_assessment', 'SELECT') THEN
        RAISE EXCEPTION 'view owner has unnecessary direct readiness-table access';
    END IF;
    IF has_column_privilege('kokonut_agent_summary_source_view_owner',
        'public.organic_compliance_checklist', 'notes', 'SELECT') THEN
        RAISE EXCEPTION 'view owner can read private checklist narrative';
    END IF;
    BEGIN
        PERFORM 1 FROM public.organic_readiness_assessment;
        RAISE EXCEPTION 'source reader queried the raw assessment table';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    SELECT count(*) INTO visible_rows
      FROM kokonut_agent_source.organic_readiness_assessment;
    IF visible_rows <> 1 THEN
        RAISE EXCEPTION 'location-filtered source returned % rows, expected 1', visible_rows;
    END IF;
    IF EXISTS (
        SELECT 1 FROM kokonut_agent_source.organic_readiness_assessment
         WHERE id = 'b0000000-0000-4000-8000-000000000201'
    ) THEN
        RAISE EXCEPTION 'source projection returned a foreign location row';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'kokonut_agent_source'
           AND table_name = 'organic_readiness_assessment'
           AND column_name IN ('notes', 'assessor', 'source_raw')
    ) THEN
        RAISE EXCEPTION 'scoped readiness projection exposes private fields';
    END IF;
END;
$$;
ROLLBACK;
""")
        checks.extend([
            "replay clears stale raw/public-view grants and schema/write privileges",
            "synthetic location-context wrapper filters foreign location rows",
            "organic assessment projection omits private narrative/source fields",
            "view owner has only the checklist row-count columns on raw tables",
        ])
        evidence["result"] = "passed"
    except Exception as exc:  # noqa: BLE001 - evidence excludes credentials and connection details
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_summary"] = str(exc)[:1200]
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    evidence["assertions"] = checks
    evidence["assertions_passed"] = len(checks)
    evidence["scope_note"] = (
        "This isolated migration test substitutes a synthetic transaction-local location context; "
        "signature validation is covered by the existing worker-context disposable checks."
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
