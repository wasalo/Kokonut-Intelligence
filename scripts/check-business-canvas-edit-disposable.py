#!/usr/bin/env python3
"""Exercise migration 464 on a fresh disposable PostgreSQL 16 container."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE_CHECK = ROOT / "scripts/check-business-canvas-create-disposable.py"
MIGRATION_457 = ROOT / "schemas/postgres/457_location_scoped_business_canvas_read.sql"
MIGRATION_463 = ROOT / "schemas/postgres/463_location_scoped_business_canvas_create.sql"
MIGRATION_464 = ROOT / "schemas/postgres/464_location_scoped_business_canvas_edit.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-065-business-canvas-edit-disposable.json"

spec = importlib.util.spec_from_file_location("business_canvas_create_disposable", CREATE_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load disposable PostgreSQL helpers")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
run = helper.run
wait_ready = helper.wait_ready


def psql(docker: str, container: str, sql: str) -> str:
    command = [
        docker, "exec", "-i", container, "psql", "-X", "-q", "-v",
        "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ]
    result = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"psql failed ({result.returncode}): {details}")
    return result.stdout.strip()

FIXTURE = helper.FIXTURE + r"""
ALTER TABLE public.business_model_canvas
    ALTER COLUMN updated_at SET DEFAULT now();
CREATE TABLE public.canvas_version (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canvas_id uuid NOT NULL REFERENCES public.business_model_canvas(id),
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    changes text,
    change_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid,
    UNIQUE (canvas_id, version)
);
"""

SEED = helper.SEED + r"""
INSERT INTO public.operator_scope_grant
 (id, operator_id, location_id, resource, action, organization_id, revoked_at) VALUES
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'business_planning', 'read', 'f0000000-0000-4000-8000-000000000001', NULL),
 (gen_random_uuid(), 'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'business_planning', 'update', 'f0000000-0000-4000-8000-000000000001', NULL);
INSERT INTO public.business_model_canvas (
 id, location_id, entity_type, entity_id, key_partners, key_activities,
 key_resources, value_propositions, customer_relationships, channels,
 customer_segments, revenue_streams, cost_structure, canvas_name, version, status
) VALUES (
 'c0000000-0000-4000-8000-000000000010',
 'b0000000-0000-4000-8000-000000000001', 'location',
 'b0000000-0000-4000-8000-000000000001', '[{"name":"Legacy partner"}]',
 '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}', 'Legacy snapshot canvas', 2, 'draft'
);
INSERT INTO public.canvas_version (canvas_id, version, snapshot, change_reason)
VALUES (
 'c0000000-0000-4000-8000-000000000010', 1,
 '{"key_partners":[{"name":"Legacy partner"}],"raw_import":"PRIVATE-LEGACY-SNAPSHOT","metadata":{"private":"hidden"}}'::jsonb,
 'Legacy version'
);
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    created record;
    edited record;
    replayed record;
    history_row record;
    expected_time timestamptz := transaction_timestamp();
    denied boolean;
    history_count integer;
BEGIN
    SELECT * INTO created FROM kokonut_security.create_location_business_model_canvas(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000001',
        'Editable draft', 'Synthetic disposable draft', 2026, ARRAY['planning'],
        '{"key_partners":[{"name":"Original partner"}]}'::jsonb
    );
    IF created.status <> 'draft' OR created.version <> 1 OR created.replayed THEN
        RAISE EXCEPTION 'fixture draft was not created at version one';
    END IF;

    SELECT * INTO edited FROM kokonut_security.update_location_business_model_canvas_block(
        'b0000000-0000-4000-8000-000000000001', created.canvas_id,
        'c0000000-0000-4000-8000-000000000002', 1, expected_time,
        'key_partners', '[{"name":"Updated partner"}]'::jsonb,
        'Approved synthetic edit'
    );
    IF edited.status <> 'draft' OR edited.version <> 2 OR edited.replayed THEN
        RAISE EXCEPTION 'block update did not create draft version two';
    END IF;

    SELECT * INTO replayed FROM kokonut_security.update_location_business_model_canvas_block(
        'b0000000-0000-4000-8000-000000000001', created.canvas_id,
        'c0000000-0000-4000-8000-000000000002', 1, expected_time,
        'key_partners', '[{"name":"Updated partner"}]'::jsonb,
        'Approved synthetic edit'
    );
    IF NOT replayed.replayed OR replayed.version <> 2 OR replayed.canvas_id <> created.canvas_id THEN
        RAISE EXCEPTION 'exact edit retry was not idempotent';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.update_location_business_model_canvas_block(
            'b0000000-0000-4000-8000-000000000001', created.canvas_id,
            'c0000000-0000-4000-8000-000000000003', 1, expected_time,
            'key_partners', '[{"name":"Stale edit"}]'::jsonb, 'Stale request'
        );
    EXCEPTION WHEN serialization_failure THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'stale version/timestamp was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.update_location_business_model_canvas_block(
            'b0000000-0000-4000-8000-000000000001', created.canvas_id,
            'c0000000-0000-4000-8000-000000000002', 1, expected_time,
            'key_partners', '[{"name":"Changed retry"}]'::jsonb, 'Changed request'
        );
    EXCEPTION WHEN unique_violation THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'changed-content request ID reuse was accepted'; END IF;

    SELECT count(*) INTO history_count
      FROM kokonut_security.list_location_business_model_canvas_versions(
          'b0000000-0000-4000-8000-000000000001', created.canvas_id, 10, 0
      );
    IF history_count <> 2 THEN RAISE EXCEPTION 'history must contain prior and current versions'; END IF;
    SELECT * INTO history_row FROM kokonut_security.list_location_business_model_canvas_versions(
        'b0000000-0000-4000-8000-000000000001', created.canvas_id, 10, 0
    ) ORDER BY version DESC LIMIT 1;
    IF history_row.version <> 2 OR NOT history_row.is_current
       OR history_row.snapshot->'blocks'->'key_partners'->0->>'name' <> 'Updated partner' THEN
        RAISE EXCEPTION 'current version history projection is incorrect';
    END IF;
    SELECT * INTO history_row FROM kokonut_security.list_location_business_model_canvas_versions(
        'b0000000-0000-4000-8000-000000000001', created.canvas_id, 10, 1
    );
    IF history_row.version <> 1 OR history_row.is_current
       OR history_row.snapshot->'blocks'->'key_partners'->0->>'name' <> 'Original partner' THEN
        RAISE EXCEPTION 'prior immutable canvas snapshot was not retained';
    END IF;

    SELECT * INTO history_row FROM kokonut_security.list_location_business_model_canvas_versions(
        'b0000000-0000-4000-8000-000000000001',
        'c0000000-0000-4000-8000-000000000010', 10, 0
    ) WHERE version = 1;
    IF history_row.snapshot ? 'raw_import'
       OR history_row.snapshot ? 'metadata'
       OR history_row.snapshot->'blocks'->'key_partners'->0->>'name' <> 'Legacy partner' THEN
        RAISE EXCEPTION 'legacy version snapshot leaked non-canvas fields or lost block content';
    END IF;

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.list_location_business_model_canvas_versions(
            'b0000000-0000-4000-8000-000000000002', created.canvas_id, 10, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location version read was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.update_location_business_model_canvas_block(
            'b0000000-0000-4000-8000-000000000001', created.canvas_id,
            'c0000000-0000-4000-8000-000000000004', 2, edited.updated_at,
            'key_partners', '[]'::jsonb, 'No update grant'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without update grant was accepted'; END IF;
    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);

    denied := false;
    BEGIN
        PERFORM * FROM kokonut_security.update_location_business_model_canvas_block(
            'b0000000-0000-4000-8000-000000000002', created.canvas_id,
            'c0000000-0000-4000-8000-000000000005', 2, edited.updated_at,
            'key_partners', '[]'::jsonb, 'Cross-location update'
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location signed context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM 1 FROM public.business_model_canvas_kernel_edit_request;
    EXCEPTION WHEN insufficient_privilege THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can read private edit ledger directly'; END IF;

END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    denied boolean := false;
BEGIN
    UPDATE public.business_model_canvas SET status = 'submitted'
     WHERE source_system = 'kokonut_gateway'
       AND source_id = 'c0000000-0000-4000-8000-000000000001';
END $$;

SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE
    canvas_row RECORD;
    denied boolean := false;
BEGIN
    SELECT * INTO canvas_row
      FROM kokonut_security.list_location_business_model_canvases(
          'b0000000-0000-4000-8000-000000000001', 10, 0
      ) AS canvas
     WHERE canvas.canvas_name = 'Editable draft';
    IF NOT FOUND THEN RAISE EXCEPTION 'read grant cannot find the test canvas'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.update_location_business_model_canvas_block(
            'b0000000-0000-4000-8000-000000000001', canvas_row.canvas_id,
            'c0000000-0000-4000-8000-000000000006', canvas_row.version,
            canvas_row.updated_at, 'key_partners', '[]'::jsonb, 'Submitted edit'
        );
    EXCEPTION WHEN object_not_in_prerequisite_state THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'submitted canvas remained editable'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    denied boolean := false;
BEGIN
    BEGIN
        UPDATE public.business_model_canvas_kernel_edit_request
           SET request_digest = repeat('0', 64);
    EXCEPTION WHEN raise_exception THEN denied := true;
    END;
    IF NOT denied THEN RAISE EXCEPTION 'Kernel edit history was mutable'; END IF;
    IF NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.update_location_business_model_canvas_block(uuid,uuid,uuid,integer,timestamp with time zone,text,jsonb,text)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime',
       'kokonut_security.list_location_business_model_canvas_versions(uuid,uuid,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.update_location_business_model_canvas_block(uuid,uuid,uuid,integer,timestamp with time zone,text,jsonb,text)', 'EXECUTE')
       OR has_function_privilege('kokonut_directus_runtime',
       'kokonut_security.list_location_business_model_canvas_versions(uuid,uuid,integer,integer)', 'EXECUTE')
       OR has_table_privilege('kokonut_runtime', 'public.business_model_canvas_kernel_edit_request', 'SELECT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.business_model_canvas_kernel_edit_request', 'SELECT') THEN
        RAISE EXCEPTION 'Kernel edit function and private ledger privileges are unsafe';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-business-canvas-edit-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_464.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 457, 463, and 464 apply and migration 464 replays",
            "exact business_planning:update and signed location context are required",
            "only draft canvases accept block edits; status remains unchanged",
            "version and updated_at concurrency rejects stale writes",
            "request ID retries are idempotent and changed-content collisions fail",
            "prior snapshots and current state are returned under exact read grant",
            "legacy snapshots expose only the allowlisted canvas fields and blocks",
            "edit history is append-only and hidden from runtime/directus table access",
            "runtime can invoke bounded functions but Directus cannot",
            "migration 464 also applies with runtime/directus roles absent",
        ],
    }
    roleless_container = f"kokonut-business-canvas-edit-roleless-{uuid.uuid4().hex[:8]}"
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgis/postgis:16-3.4",
        ])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        psql(docker, container, MIGRATION_457.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_463.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_464.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION_464.read_text(encoding="utf-8"))
        psql(docker, container, SEED)
        psql(docker, container, ACCEPTANCE)

        roleless_fixture = FIXTURE.replace(
            "CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;\n",
            "",
        ).replace(
            "CREATE ROLE kokonut_directus_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;\n",
            "",
        )
        if "CREATE ROLE kokonut_runtime" in roleless_fixture or "CREATE ROLE kokonut_directus_runtime" in roleless_fixture:
            raise RuntimeError("roleless fixture still creates optional application roles")
        run([
            docker, "run", "--detach", "--rm", "--name", roleless_container,
            "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgis/postgis:16-3.4",
        ])
        wait_ready(roleless_container, docker)
        psql(docker, roleless_container, roleless_fixture)
        psql(docker, roleless_container, MIGRATION_457.read_text(encoding="utf-8"))
        psql(docker, roleless_container, MIGRATION_463.read_text(encoding="utf-8"))
        psql(docker, roleless_container, MIGRATION_464.read_text(encoding="utf-8"))

        evidence["result"] = "passed"
        evidence["assertions_passed"] = 14
        print("PASS: migration 464 applies/replays and all fourteen disposable PostgreSQL assertions passed")
        result = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        result = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        subprocess.run([docker, "rm", "--force", roleless_container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
