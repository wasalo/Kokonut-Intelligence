#!/usr/bin/env python3
"""Exercise migration 448 on disposable local PostgreSQL 16."""

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
identity_acceptance_sql = _identity_module.acceptance_sql
psql = _identity_module.psql
run = _identity_module.run
wait_ready = _identity_module.wait_ready

_trust_script = ROOT / "scripts/check-stakeholder-trust-disposable.py"
_trust_spec = importlib.util.spec_from_file_location(
    "check_stakeholder_trust_disposable", _trust_script
)
if _trust_spec is None or _trust_spec.loader is None:
    raise RuntimeError("could not load the trust disposable-check helpers")
_trust_module = importlib.util.module_from_spec(_trust_spec)
_trust_spec.loader.exec_module(_trust_module)
TRUST_MIGRATION = _trust_module.MIGRATION

MIGRATION = ROOT / "schemas/postgres/448_location_scoped_identity_resolution.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-025-identity-resolution-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def resolution_acceptance_sql() -> str:
    reviewer = "a0000000-0000-4000-8000-000000000002"
    unauthorized = "a0000000-0000-4000-8000-000000000003"
    location = "b0000000-0000-4000-8000-000000000001"
    other_location = "b0000000-0000-4000-8000-000000000002"
    profile = "c0000000-0000-4000-8000-000000000001"
    withdrawn_profile = "c0000000-0000-4000-8000-000000000002"
    legacy_profile = "c0000000-0000-4000-8000-000000000003"
    party = "d0000000-0000-4000-8000-000000000001"
    tenant = "f0000000-0000-4000-8000-000000000001"
    return f"""
INSERT INTO public.operator_scope_grant VALUES
 (gen_random_uuid(), '{reviewer}', '{location}', 'stakeholder_identity', 'resolve', NULL, NULL);

SET ROLE kokonut_runtime;
BEGIN;
SET TRANSACTION READ ONLY;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE resolved record; direct_denied boolean := false; BEGIN
  SELECT * INTO resolved FROM kokonut_security.resolve_location_farmer_party_identity(
    '{location}', '{profile}'
  );
  IF resolved.party_id <> '{party}'::uuid OR resolved.resolved_at IS NULL THEN
    RAISE EXCEPTION 'approved mapping did not resolve in its source location';
  END IF;
  BEGIN
    PERFORM 1 FROM public.party_location_identity_case;
  EXCEPTION WHEN insufficient_privilege THEN direct_denied := true;
  END;
  IF NOT direct_denied THEN RAISE EXCEPTION 'runtime can read identity map directly'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{unauthorized}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.resolve_location_farmer_party_identity(
      '{location}', '{profile}'
    );
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'resolver ignored its distinct exact grant'; END IF;
END $$;
COMMIT;

BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{other_location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE denied boolean := false; BEGIN
  BEGIN
    PERFORM * FROM kokonut_security.resolve_location_farmer_party_identity(
      '{location}', '{profile}'
    );
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'resolver accepted mismatched signed location'; END IF;
END $$;
COMMIT;

RESET ROLE;
INSERT INTO public.party_identifier VALUES
 (gen_random_uuid(), 'farmer_profile_id', '{profile}', '{profile}', 'verified');
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE resolved_count integer; BEGIN
  SELECT count(*) INTO resolved_count FROM kokonut_security.resolve_location_farmer_party_identity(
    '{location}', '{profile}'
  );
  IF resolved_count <> 0 THEN RAISE EXCEPTION 'resolver returned conflicting legacy mapping'; END IF;
  SELECT count(*) INTO resolved_count FROM kokonut_security.resolve_location_farmer_party_identity(
    '{location}', '{legacy_profile}'
  );
  IF resolved_count <> 0 THEN RAISE EXCEPTION 'resolver returned unapproved source'; END IF;
  SELECT count(*) INTO resolved_count FROM kokonut_security.resolve_location_farmer_party_identity(
    '{location}', '{withdrawn_profile}'
  );
  IF resolved_count <> 0 THEN RAISE EXCEPTION 'resolver returned a pending source'; END IF;
END $$;
COMMIT;

RESET ROLE;
DELETE FROM public.party_identifier WHERE identifier_value = '{profile}';
INSERT INTO public.farmer_consent VALUES
 (gen_random_uuid(), '{profile}', '{location}', 'personal', 'internal_use', 'withdrawn', NULL, clock_timestamp());
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE resolved_count integer; BEGIN
  SELECT count(*) INTO resolved_count FROM kokonut_security.resolve_location_farmer_party_identity(
    '{location}', '{profile}'
  );
  IF resolved_count <> 0 THEN RAISE EXCEPTION 'resolver ignored withdrawn consent'; END IF;
END $$;
COMMIT;

RESET ROLE;
INSERT INTO public.farmer_consent VALUES
 (gen_random_uuid(), '{profile}', '{location}', 'personal', 'internal_use', 'granted', NULL, clock_timestamp());
UPDATE public.party SET privacy_level = 'private' WHERE id = '{party}';
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', '{tenant}', true);
SELECT set_config('kokonut.location_id', '{location}', true);
SELECT set_config('kokonut.actor_id', '{reviewer}', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$ DECLARE resolved_count integer; BEGIN
  SELECT count(*) INTO resolved_count FROM kokonut_security.resolve_location_farmer_party_identity(
    '{location}', '{profile}'
  );
  IF resolved_count <> 0 THEN RAISE EXCEPTION 'resolver returned private canonical party'; END IF;
END $$;
COMMIT;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-resolution-disposable-{uuid.uuid4().hex[:10]}"
    checks = [
        "ordered migrations 446–448 application",
        "approved mapping resolves to canonical party in its source location",
        "resolver requires a distinct exact location grant",
        "mismatched signed location is denied",
        "legacy conflict, unapproved, and pending sources return no mapping",
        "consent withdrawal suppresses resolution",
        "private canonical party suppresses resolution",
        "runtime cannot read the identity ledger directly",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
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
        stage = "identity_migration_apply"
        psql(docker, container, IDENTITY_MIGRATION.read_text(encoding="utf-8"))
        stage = "trust_migration_apply"
        psql(docker, container, TRUST_MIGRATION.read_text(encoding="utf-8"))
        stage = "resolution_migration_apply"
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        stage = "identity_fixture_acceptance"
        psql(docker, container, identity_acceptance_sql())
        stage = "resolution_acceptance"
        psql(docker, container, resolution_acceptance_sql())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
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
