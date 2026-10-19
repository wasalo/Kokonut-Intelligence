#!/usr/bin/env python3
"""Exercise migration 447 on a disposable local PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_identity_script = ROOT / "scripts/check-stakeholder-identity-disposable.py"
_identity_spec = importlib.util.spec_from_file_location(
    "check_stakeholder_identity_disposable", _identity_script
)
if _identity_spec is None or _identity_spec.loader is None:
    raise RuntimeError("could not load the identity disposable-check helpers")
_identity_module = importlib.util.module_from_spec(_identity_spec)
_identity_spec.loader.exec_module(_identity_module)
FIXTURE = _identity_module.FIXTURE
IDENTITY_MIGRATION = _identity_module.MIGRATION
acceptance_sql = _identity_module.acceptance_sql
psql = _identity_module.psql
run = _identity_module.run
wait_ready = _identity_module.wait_ready

MIGRATION = ROOT / "schemas/postgres/447_location_scoped_identity_trust_projection.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-025-stakeholder-trust-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def trust_acceptance_sql() -> str:
    reviewer = "a0000000-0000-4000-8000-000000000002"
    unauthorized = "a0000000-0000-4000-8000-000000000003"
    location = "b0000000-0000-4000-8000-000000000001"
    other_location = "b0000000-0000-4000-8000-000000000002"
    profile = "c0000000-0000-4000-8000-000000000001"
    party = "d0000000-0000-4000-8000-000000000001"
    tenant = "f0000000-0000-4000-8000-000000000001"
    return f"""
DO $$ DECLARE is_stable boolean; BEGIN
  SELECT proc.provolatile = 's' INTO is_stable
    FROM pg_catalog.pg_proc AS proc
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = proc.pronamespace
   WHERE namespace.nspname = 'kokonut_security'
     AND proc.proname = 'list_location_party_identity_trust_evidence';
  IF is_stable IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'trust evidence projection is not database-enforced read-only';
  END IF;
  IF has_table_privilege('kokonut_stakeholder_trust_reader', 'public.party_trust_evidence', 'SELECT')
     OR has_table_privilege('kokonut_stakeholder_trust_reader', 'public.v_party_trust_profile', 'SELECT') THEN
    RAISE EXCEPTION 'trust projection owner can read network-wide legacy trust data';
  END IF;
END $$;

INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), '{reviewer}', '{location}', 'stakeholder_trust', 'read', NULL, NULL);

SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE row_result record; direct_denied boolean := false; BEGIN
  SELECT * INTO row_result FROM kokonut_security.list_location_party_identity_trust_evidence(
    '{location}', '{party}', 10, NULL, NULL
  );
  IF row_result.evidence_id IS NULL OR row_result.dimension <> 'identity'
     OR row_result.direction <> 'supporting'
     OR row_result.evidence_code <> 'document_review'
     OR row_result.match_method <> 'verified_document'
     OR row_result.confidence <> 0.85 OR row_result.reviewed_at IS NULL THEN
    RAISE EXCEPTION 'approved identity evidence projection was incomplete or unexpected';
  END IF;
  BEGIN
    PERFORM 1 FROM public.party_location_identity_case;
  EXCEPTION WHEN insufficient_privilege THEN direct_denied := true;
  END;
  IF NOT direct_denied THEN RAISE EXCEPTION 'runtime can read private identity source table'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{unauthorized}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.list_location_party_identity_trust_evidence(
      '{location}', '{party}', 10, NULL, NULL
    );
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'trust projection ignored missing location grant'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{other_location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.list_location_party_identity_trust_evidence(
      '{location}', '{party}', 10, NULL, NULL
    );
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'trust projection accepted a mismatched signed location'; END IF;
END $$;
COMMIT;

RESET ROLE;
INSERT INTO public.farmer_consent VALUES
 (gen_random_uuid(), '{profile}', '{location}', 'personal', 'internal_use', 'withdrawn', NULL, clock_timestamp());
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE evidence_count integer; BEGIN
  SELECT count(*) INTO evidence_count FROM kokonut_security.list_location_party_identity_trust_evidence(
    '{location}', '{party}', 10, NULL, NULL
  );
  IF evidence_count <> 0 THEN RAISE EXCEPTION 'withdrawn source consent remained in trust projection'; END IF;
END $$;
COMMIT;

RESET ROLE;
INSERT INTO public.farmer_consent VALUES
 (gen_random_uuid(), '{profile}', '{location}', 'personal', 'internal_use', 'granted', NULL,
  clock_timestamp() + interval '1 second');
UPDATE public.party SET privacy_level = 'private' WHERE id = '{party}';
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE evidence_count integer; BEGIN
  SELECT count(*) INTO evidence_count FROM kokonut_security.list_location_party_identity_trust_evidence(
    '{location}', '{party}', 10, NULL, NULL
  );
  IF evidence_count <> 0 THEN RAISE EXCEPTION 'private canonical party appeared in trust projection'; END IF;
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
    container = f"kokonut-trust-disposable-{uuid.uuid4().hex[:10]}"
    checks = [
        "ordered migration 446 and 447 application",
        "database-enforced stable projection and no legacy trust-table access",
        "read-only identity evidence projection from independent approval",
        "runtime direct-table denial",
        "location grant and signed location enforcement",
        "consent withdrawal suppresses scoped trust evidence",
        "private canonical identity is not returned",
        "legacy append-only decision ledger remains immutable",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "prerequisite_migration": IDENTITY_MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": checks,
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
        psql(
            docker,
            container,
            "CREATE TABLE public.party_trust_evidence (id uuid PRIMARY KEY); "
            "CREATE VIEW public.v_party_trust_profile AS SELECT 1 AS legacy_network_score; "
            "INSERT INTO public.party_trust_evidence VALUES (gen_random_uuid());",
        )
        stage = "identity_migration_apply"
        psql(docker, container, IDENTITY_MIGRATION.read_text(encoding="utf-8"))
        stage = "trust_migration_apply"
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        stage = "identity_fixture_acceptance"
        psql(docker, container, acceptance_sql())
        stage = "trust_projection_acceptance"
        psql(docker, container, trust_acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - record safe failure metadata only
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
