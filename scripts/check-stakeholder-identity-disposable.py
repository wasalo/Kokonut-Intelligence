#!/usr/bin/env python3
"""Exercise migration 446 on a disposable local PostgreSQL container."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/446_location_scoped_stakeholder_identity_review.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-025-stakeholder-identity-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip().splitlines()
        summary = " | ".join(line[:180] for line in details[-8:]) or "no command output"
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} {command[1]}: {summary}")
    return result.stdout.strip()


def wait_ready(container: str, docker: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    logs = subprocess.run(
        [docker, "logs", container], text=True, capture_output=True, check=False
    )
    details = (logs.stdout + logs.stderr).strip().splitlines()
    summary = " | ".join(line[:180] for line in details[-6:]) or "container logs were empty"
    raise RuntimeError(f"disposable PostgreSQL did not become ready: {summary}")


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE SCHEMA kokonut_security;
CREATE TABLE public.location (id uuid PRIMARY KEY, organization_id uuid, status text NOT NULL);
CREATE TABLE public.organization (id uuid PRIMARY KEY, status text NOT NULL);
CREATE TABLE public.operator_identity (id uuid PRIMARY KEY, enabled boolean NOT NULL);
CREATE TABLE public.operator_scope_grant (
    id uuid PRIMARY KEY, operator_id uuid NOT NULL, location_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, organization_id uuid,
    revoked_at timestamptz
);
CREATE TABLE public.operator_organization_membership (id uuid PRIMARY KEY);
CREATE TABLE public.location_tenant_owner_verification (id uuid PRIMARY KEY);
CREATE TABLE public.location_organization_share (id uuid PRIMARY KEY);
CREATE TABLE public.party (
    id uuid PRIMARY KEY, party_type text NOT NULL, status text NOT NULL,
    privacy_level text NOT NULL, display_name text NOT NULL
);
CREATE TABLE public.party_identifier (
    id uuid PRIMARY KEY, identifier_type text NOT NULL, identifier_value text NOT NULL,
    source_id text, verification_status text NOT NULL
);
CREATE TABLE public.farmer_profile (
    id uuid PRIMARY KEY, location_id uuid, status text NOT NULL,
    first_name text NOT NULL, last_name text
);
CREATE TABLE public.farmer_consent (
    id uuid PRIMARY KEY, farmer_id text NOT NULL, location_id uuid,
    data_category text NOT NULL, consent_scope text NOT NULL, status text NOT NULL,
    expires_at timestamptz, created_at timestamptz NOT NULL
);
CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(tenant_id uuid, location_id uuid, actor_id uuid, actor_type text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT NULLIF(current_setting('kokonut.tenant_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.location_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.actor_id', true), '')::uuid,
           NULLIF(current_setting('kokonut.actor_type', true), '')::text
$$;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id uuid, requested_resource text,
    requested_action text, requested_location_id uuid
) RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.operator_scope_grant AS grant_row
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
    )
$$;
GRANT USAGE ON SCHEMA public TO PUBLIC;
"""


def acceptance_sql() -> str:
    proposer = "a0000000-0000-4000-8000-000000000001"
    reviewer = "a0000000-0000-4000-8000-000000000002"
    unauthorized = "a0000000-0000-4000-8000-000000000003"
    location = "b0000000-0000-4000-8000-000000000001"
    other_location = "b0000000-0000-4000-8000-000000000002"
    profile = "c0000000-0000-4000-8000-000000000001"
    withdrawn_profile = "c0000000-0000-4000-8000-000000000002"
    legacy_profile = "c0000000-0000-4000-8000-000000000003"
    party = "d0000000-0000-4000-8000-000000000001"
    request = "e0000000-0000-4000-8000-000000000001"
    request_withdrawn = "e0000000-0000-4000-8000-000000000002"
    decision_request = "e0000000-0000-4000-8000-000000000003"
    decision_request_withdrawn = "e0000000-0000-4000-8000-000000000004"
    legacy_request = "e0000000-0000-4000-8000-000000000005"
    approved_retry_request = "e0000000-0000-4000-8000-000000000006"
    return f"""
INSERT INTO public.location VALUES
 ('{location}', NULL, 'active'), ('{other_location}', NULL, 'active');
INSERT INTO public.operator_identity VALUES
 ('{proposer}', true), ('{reviewer}', true), ('{unauthorized}', true);
INSERT INTO public.party VALUES
 ('{party}', 'person', 'active', 'limited', 'Synthetic Canonical Party');
INSERT INTO public.farmer_profile VALUES
 ('{profile}', '{location}', 'active', 'Synthetic', 'Participant'),
 ('{withdrawn_profile}', '{location}', 'active', 'Withdrawn', 'Participant'),
 ('{legacy_profile}', '{location}', 'active', 'Legacy', 'Linked Participant');
INSERT INTO public.farmer_consent VALUES
 (gen_random_uuid(), '{profile}', '{location}', 'personal', 'internal_use', 'granted', NULL, clock_timestamp()),
 (gen_random_uuid(), '{withdrawn_profile}', '{location}', 'personal', 'internal_use', 'granted', NULL, clock_timestamp()),
 (gen_random_uuid(), '{legacy_profile}', '{location}', 'personal', 'internal_use', 'granted', NULL, clock_timestamp());
INSERT INTO public.party_identifier VALUES
 (gen_random_uuid(), 'farmer_profile_id', '{legacy_profile}', '{legacy_profile}', 'verified');
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), '{proposer}', '{location}', 'stakeholder_identity', 'create', NULL, NULL),
 (gen_random_uuid(), '{proposer}', '{location}', 'stakeholder_identity', 'review', NULL, NULL),
 (gen_random_uuid(), '{reviewer}', '{location}', 'stakeholder_identity', 'review', NULL, NULL),
 (gen_random_uuid(), '{unauthorized}', '{location}', 'stakeholder_identity', 'review', NULL, NULL);

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{proposer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN PERFORM 1 FROM public.party_location_identity_case;
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'runtime can read identity case table directly'; END IF;
END $$;
CREATE TEMP TABLE test_identity_result AS
SELECT * FROM kokonut_security.propose_location_party_identity(
 '{location}', '{profile}', '{party}', '{request}', 'verified_document', 'document_review', 0.85
);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.propose_location_party_identity(
      '{location}', '{legacy_profile}', '{party}', '{legacy_request}', 'manual', 'verified_identifier', 0.8
    );
  EXCEPTION WHEN unique_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'source with a legacy verified link entered Kernel review'; END IF;
END $$;
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.decide_location_party_identity(
      '{location}', (SELECT case_id FROM test_identity_result), '{decision_request}', 'approve', 'match_confirmed'
    );
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'proposer could review their own identity case'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE reviewed record; denied boolean := false; BEGIN
  SELECT * INTO reviewed FROM kokonut_security.decide_location_party_identity(
    '{location}', (SELECT case_id FROM test_identity_result), '{decision_request}', 'approve', 'match_confirmed'
  );
  IF reviewed.case_status <> 'approved' OR reviewed.reviewer_operator_id <> '{reviewer}'::uuid THEN
    RAISE EXCEPTION 'independent identity approval returned unexpected result';
  END IF;
  SELECT * INTO reviewed FROM kokonut_security.decide_location_party_identity(
    '{location}', (SELECT case_id FROM test_identity_result), '{decision_request}', 'approve', 'match_confirmed'
  );
  IF reviewed.case_status <> 'approved' OR reviewed.reviewer_operator_id <> '{reviewer}'::uuid THEN
    RAISE EXCEPTION 'identity decision retry was not idempotent';
  END IF;
  denied := false;
  BEGIN
    PERFORM * FROM kokonut_security.decide_location_party_identity(
      '{location}', (SELECT case_id FROM test_identity_result), '{decision_request}', 'reject', 'conflicting_identity'
    );
  EXCEPTION WHEN invalid_parameter_value THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'decision request key accepted conflicting content'; END IF;
END $$;
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN PERFORM 1 FROM public.party_location_identity_decision;
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'runtime can read identity decision table directly'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{proposer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.propose_location_party_identity(
      '{location}', '{profile}', '{party}', '{approved_retry_request}', 'manual', 'verified_identifier', 0.8
    );
  EXCEPTION WHEN unique_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'approved source could be reopened as a new pending case'; END IF;
END $$;
CREATE TEMP TABLE test_withdrawn_result AS
SELECT * FROM kokonut_security.propose_location_party_identity(
 '{location}', '{withdrawn_profile}', '{party}', '{request_withdrawn}', 'manual', 'participant_confirmation', 0.65
);
COMMIT;

RESET ROLE;
INSERT INTO public.farmer_consent VALUES
 (gen_random_uuid(), '{withdrawn_profile}', '{location}', 'personal', 'internal_use', 'withdrawn', NULL, clock_timestamp() + interval '1 second');
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE listed record; denied boolean := false; BEGIN
  SELECT * INTO listed FROM kokonut_security.list_location_party_identity_cases('{location}', 10, NULL, NULL)
   WHERE case_id = (SELECT case_id FROM test_withdrawn_result);
  IF listed.case_id IS NULL OR listed.source_label IS NOT NULL OR listed.candidate_name IS NOT NULL
     OR listed.candidate_party_id IS NOT NULL THEN
    RAISE EXCEPTION 'withdrawn-consent queue entry exposed source or candidate identity';
  END IF;
  BEGIN
    PERFORM * FROM kokonut_security.decide_location_party_identity(
      '{location}', listed.case_id, '{decision_request_withdrawn}', 'approve', 'match_confirmed'
    );
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'identity approval succeeded after consent withdrawal'; END IF;
END $$;
COMMIT;
RESET ROLE;
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    UPDATE public.party_location_identity_decision SET reason_code = 'match_confirmed';
  EXCEPTION WHEN OTHERS THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'identity decision history was mutable'; END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-identity-disposable-{uuid.uuid4().hex[:10]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration application",
            "direct table denial",
            "scope-qualified functions under synthetic tenant context",
            "independent reviewer enforcement",
            "decision retry and collision handling",
            "legacy-link conflict and approved-source guards",
            "withdrawn-consent source concealment and approval denial",
            "append-only decision history",
        ],
    }
    stage = "container_start"
    try:
        run([
            docker, "run", "--rm", "--detach", "--name", container,
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
            "--publish", "127.0.0.1::5432", IMAGE,
        ])
        wait_ready(container, docker)
        stage = "fixture_setup"
        psql(docker, container, FIXTURE)
        stage = "migration_apply"
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        stage = "acceptance_assertions"
        psql(docker, container, acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(evidence["checks"])
    except Exception as exc:  # noqa: BLE001 - save only safe failure metadata
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:400]
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
