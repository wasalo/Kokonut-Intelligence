#!/usr/bin/env python3
"""Exercise migration 463 on a new disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_CHECK = ROOT / "scripts/check-business-canvas-disposable.py"
MIGRATION_457 = ROOT / "schemas/postgres/457_location_scoped_business_canvas_read.sql"
MIGRATION_463 = ROOT / "schemas/postgres/463_location_scoped_business_canvas_create.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-065-business-canvas-create-disposable.json"

_spec = importlib.util.spec_from_file_location("business_canvas_read_disposable", BASE_CHECK)
if _spec is None or _spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
run = _base.run
psql = _base.psql
wait_ready = _base.wait_ready

FIXTURE = _base.FIXTURE + r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER TABLE public.operator_organization_membership
    ADD COLUMN operator_id uuid,
    ADD COLUMN organization_id uuid,
    ADD COLUMN revoked_at timestamptz;
ALTER TABLE public.location_tenant_owner_verification
    ADD COLUMN location_id uuid,
    ADD COLUMN organization_id uuid,
    ADD COLUMN revoked_at timestamptz;
ALTER TABLE public.location_organization_share
    ADD COLUMN location_id uuid,
    ADD COLUMN organization_id uuid,
    ADD COLUMN revoked_at timestamptz,
    ADD COLUMN expires_at timestamptz;
ALTER TABLE public.business_model_canvas
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN version SET DEFAULT 1,
    ALTER COLUMN status SET DEFAULT 'draft',
    ALTER COLUMN created_at SET DEFAULT clock_timestamp(),
    ALTER COLUMN updated_at SET DEFAULT clock_timestamp();
"""

SEED = r"""
INSERT INTO public.operator_identity VALUES
 ('a0000000-0000-4000-8000-000000000001', true),
 ('a0000000-0000-4000-8000-000000000002', true);
INSERT INTO public.organization VALUES
 ('f0000000-0000-4000-8000-000000000001', 'active'),
 ('f0000000-0000-4000-8000-000000000002', 'active');
INSERT INTO public.location VALUES
 ('b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', 'active'),
 ('b0000000-0000-4000-8000-000000000002', 'f0000000-0000-4000-8000-000000000002', 'active');
INSERT INTO public.location_tenant_owner_verification
 (id, location_id, organization_id, revoked_at) VALUES
 (gen_random_uuid(), 'b0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'b0000000-0000-4000-8000-000000000002', 'f0000000-0000-4000-8000-000000000002', NULL);
INSERT INTO public.operator_organization_membership
 (id, operator_id, organization_id, revoked_at) VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.operator_scope_grant
 (id, operator_id, location_id, resource, action, organization_id, revoked_at) VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'business_planning', 'create', 'f0000000-0000-4000-8000-000000000001', NULL);
"""

ACCEPTANCE = r"""
GRANT INSERT, UPDATE, DELETE ON public.business_model_canvas TO kokonut_runtime;
GRANT INSERT, UPDATE, DELETE ON public.business_model_canvas TO kokonut_directus_runtime;
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    created record;
    replayed record;
    row_count integer;
    denied boolean;
    saved_actor text;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_business_model_canvas(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'Genesis draft', 'Synthetic disposable draft', 2026, ARRAY['planning'],
        '{"value_propositions":[{"statement":"soil health"}]}'::jsonb
    );
    IF created.status <> 'draft' OR created.version <> 1 OR created.replayed THEN
        RAISE EXCEPTION 'creation did not return a new version-one draft';
    END IF;

    SELECT * INTO replayed FROM kokonut_security.create_location_business_model_canvas(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'Genesis draft', 'Synthetic disposable draft', 2026, ARRAY['planning'],
        '{"value_propositions":[{"statement":"soil health"}]}'::jsonb
    );
    IF replayed.canvas_id <> created.canvas_id OR NOT replayed.replayed THEN
        RAISE EXCEPTION 'exact request retry was not idempotent';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_business_model_canvas(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000001',
            'Genesis draft', 'Changed content', 2026, ARRAY['planning'], '{}'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed content reused an idempotency key'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_business_model_canvas(
            'b0000000-0000-4000-8000-000000000002',
            'c0000000-0000-4000-8000-000000000002',
            'Cross-location draft', NULL, NULL, ARRAY[]::text[], '{}'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'signed location mismatch was accepted'; END IF;

    saved_actor := current_setting('kokonut.actor_id');
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_business_model_canvas(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000003',
            'No grant', NULL, NULL, ARRAY[]::text[], '{}'::jsonb
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without an exact tenant grant was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', saved_actor, true);

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.create_location_business_model_canvas(
            'b0000000-0000-4000-8000-000000000001',
            'c0000000-0000-4000-8000-000000000004',
            'Malformed block', NULL, NULL, ARRAY[]::text[],
            '{"key_partners":{}}'::jsonb
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'malformed BMC block shape was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.business_model_canvas;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read business canvas rows directly'; END IF;

    INSERT INTO public.business_model_canvas(entity_type, entity_id, location_id, canvas_name)
    VALUES ('location', 'b0000000-0000-4000-8000-000000000001',
            'b0000000-0000-4000-8000-000000000001', 'Legacy location insert');
    UPDATE public.business_model_canvas
       SET description = 'Legacy update path remains available';
    GET DIAGNOSTICS row_count = ROW_COUNT;
    IF row_count <> 2 THEN RAISE EXCEPTION 'legacy location canvas edit stopped working'; END IF;
    INSERT INTO public.business_model_canvas(entity_type, entity_id, organization_id, canvas_name)
    VALUES ('organization', 'f0000000-0000-4000-8000-000000000001',
            'f0000000-0000-4000-8000-000000000001', 'Legacy organization canvas');
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    denied boolean := false;
    row_count integer;
BEGIN
    SELECT count(*) INTO row_count FROM public.business_model_canvas
     WHERE source_system = 'kokonut_gateway'
       AND source_id = 'c0000000-0000-4000-8000-000000000001';
    IF row_count <> 1 THEN RAISE EXCEPTION 'create/replay did not produce exactly one Kernel canvas'; END IF;
    BEGIN
        UPDATE public.business_model_canvas_create_request SET request_digest = repeat('0', 64);
    EXCEPTION WHEN raise_exception THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'idempotency request ledger was mutable'; END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.create_location_business_model_canvas(uuid,uuid,text,text,integer,text[],jsonb)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.create_location_business_model_canvas(uuid,uuid,text,text,integer,text[],jsonb)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.business_model_canvas_create_request', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.business_model_canvas_create_request', 'SELECT') THEN
        RAISE EXCEPTION 'runtime/directus function and request-ledger privileges are unsafe';
    END IF;
END $$;

SET ROLE kokonut_directus_runtime;
DO $$
BEGIN
    INSERT INTO public.business_model_canvas(entity_type, entity_id, location_id, canvas_name)
    VALUES ('location', 'b0000000-0000-4000-8000-000000000001',
            'b0000000-0000-4000-8000-000000000001', 'Directus legacy insert');
END $$;
RESET ROLE;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-business-canvas-create-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_463.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 463 applies and replays after migration 457",
            "signed owner tenant and exact create grant produce one draft canvas",
            "identical request retry returns the original canvas",
            "changed-content idempotency reuse and invalid blocks fail closed",
            "cross-location context and missing exact grant are denied",
            "existing runtime location insert/edit and Directus insert remain available",
            "Directus cannot execute the new Kernel function",
            "idempotency ledger is append-only and inaccessible to runtime roles",
        ],
    }
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgis/postgis:16-3.4"])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        psql(docker, container, MIGRATION_457.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_463.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_463.read_text(encoding="utf-8"))
        psql(docker, container, SEED)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = 8
        print("PASS: migration 463 applies/replays and all eight disposable PostgreSQL assertions passed")
        return_code = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return_code = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
