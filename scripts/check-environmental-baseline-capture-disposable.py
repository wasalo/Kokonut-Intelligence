#!/usr/bin/env python3
"""Exercise migration 733 on an isolated, synthetic PostgreSQL instance."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/733_environmental_baseline_gateway_capture.sql"
IMAGE = os.environ.get(
    "ENVIRONMENTAL_BASELINE_CAPTURE_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)

LOCATION_ID = "10000000-0000-4000-8000-000000000001"
OTHER_LOCATION_ID = "10000000-0000-4000-8000-000000000002"
OPERATOR_ID = "20000000-0000-4000-8000-000000000001"
FARM_ID = "30000000-0000-4000-8000-000000000001"
OTHER_FARM_ID = "30000000-0000-4000-8000-000000000002"
PLOT_ID = "40000000-0000-4000-8000-000000000001"
OTHER_PLOT_ID = "40000000-0000-4000-8000-000000000002"
REQUEST_ID = "50000000-0000-4000-8000-000000000001"
ROLLBACK_REQUEST_ID = "50000000-0000-4000-8000-000000000002"


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:5])} …\n{details}"
        )
    return result


def docker_psql(container: str, statement: str):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-v",
            "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


FIXTURE = f"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
CREATE ROLE kokonut NOLOGIN;
CREATE SCHEMA kokonut_security;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_runtime, kokonut_directus_runtime;

CREATE TABLE public.location (
    id UUID PRIMARY KEY
);
CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY
);
CREATE TABLE public.farm (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id)
);
CREATE TABLE public.plot (
    id UUID PRIMARY KEY,
    farm_id UUID NOT NULL REFERENCES public.farm(id)
);
CREATE TABLE public.environmental_baseline (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES public.plot(id),
    metric_name VARCHAR(100) NOT NULL,
    baseline_value NUMERIC(12,4),
    unit VARCHAR(50),
    measurement_date DATE,
    measurement_method VARCHAR(100),
    source VARCHAR(255),
    evidence_urls TEXT[],
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    schema_version VARCHAR(50)
);
ALTER TABLE public.environmental_baseline ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.environmental_baseline FORCE ROW LEVEL SECURITY;
CREATE POLICY synthetic_runtime_baseline_read
    ON public.environmental_baseline FOR SELECT TO kokonut_runtime USING (TRUE);
CREATE POLICY synthetic_directus_baseline_write
    ON public.environmental_baseline FOR ALL TO kokonut_directus_runtime
    USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY synthetic_seed_maintenance_write
    ON public.environmental_baseline FOR ALL TO kokonut
    USING (TRUE) WITH CHECK (TRUE);

GRANT ALL PRIVILEGES ON TABLE public.environmental_baseline
    TO kokonut_runtime, kokonut_directus_runtime, kokonut;
GRANT SELECT ON TABLE public.location, public.operator_identity,
    public.farm, public.plot TO kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.location,
    public.operator_identity, public.farm, public.plot
    TO kokonut_runtime, kokonut_directus_runtime;

INSERT INTO public.location (id) VALUES
    ('{LOCATION_ID}'), ('{OTHER_LOCATION_ID}');
INSERT INTO public.operator_identity (id) VALUES ('{OPERATOR_ID}');
INSERT INTO public.farm (id, location_id) VALUES
    ('{FARM_ID}', '{LOCATION_ID}'), ('{OTHER_FARM_ID}', '{OTHER_LOCATION_ID}');
INSERT INTO public.plot (id, farm_id) VALUES
    ('{PLOT_ID}', '{FARM_ID}'), ('{OTHER_PLOT_ID}', '{OTHER_FARM_ID}');

CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE (actor_id UUID, location_id UUID, actor_type TEXT)
LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT NULLIF(current_setting('kokonut.test_actor_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.test_location_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.test_actor_type', TRUE), '')::TEXT
$$;
CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_actor_id UUID, requested_resource TEXT, requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT requested_actor_id = NULLIF(current_setting('kokonut.test_actor_id', TRUE), '')::UUID
       AND requested_resource = 'environmental_baseline'
       AND requested_action = 'create'
       AND requested_location_id = NULLIF(current_setting('kokonut.test_grant_location', TRUE), '')::UUID
$$;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_runtime, kokonut_directus_runtime;
"""


ACL_ASSERTIONS = r"""
DO $$
DECLARE
    privilege_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH privilege_name IN ARRAY ARRAY[
        'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
    ] LOOP
        IF has_table_privilege('kokonut_runtime',
                               'public.environmental_baseline', privilege_name) THEN
            RAISE EXCEPTION 'runtime % remains on environmental_baseline', privilege_name;
        END IF;
    END LOOP;
    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = 'public.environmental_baseline'::REGCLASS
           AND attribute.attnum > 0 AND NOT attribute.attisdropped
    LOOP
        FOREACH privilege_name IN ARRAY ARRAY['INSERT', 'UPDATE', 'REFERENCES'] LOOP
            IF has_column_privilege(
                'kokonut_runtime', 'public.environmental_baseline',
                column_name, privilege_name
            ) THEN
                RAISE EXCEPTION 'runtime column % remains on environmental_baseline.%',
                    privilege_name, column_name;
            END IF;
        END LOOP;
    END LOOP;
    IF NOT has_table_privilege(
        'kokonut_runtime', 'public.environmental_baseline', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'runtime SELECT was not preserved';
    END IF;
    FOREACH privilege_name IN ARRAY ARRAY['INSERT', 'UPDATE', 'DELETE'] LOOP
        IF NOT has_table_privilege(
            'kokonut_directus_runtime', 'public.environmental_baseline', privilege_name
        ) THEN
            RAISE EXCEPTION 'Directus % changed unexpectedly', privilege_name;
        END IF;
    END LOOP;
END $$;

SET ROLE kokonut_runtime;
DO $$ BEGIN
    BEGIN
        INSERT INTO public.environmental_baseline (
            id, location_id, metric_name, baseline_value
        ) VALUES (
            '60000000-0000-4000-8000-000000000001',
            '10000000-0000-4000-8000-000000000001', 'direct_insert', 1
        );
        RAISE EXCEPTION USING ERRCODE = 'ZX001', MESSAGE = 'runtime INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.environmental_baseline SET metric_name = 'changed';
        RAISE EXCEPTION USING ERRCODE = 'ZX002', MESSAGE = 'runtime UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM public.environmental_baseline;
        RAISE EXCEPTION USING ERRCODE = 'ZX003', MESSAGE = 'runtime DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM count(*) FROM public.environmental_baseline;
END $$;
RESET ROLE;

-- The optional Directus adapter retains its preexisting grants and row policy.
SET ROLE kokonut_directus_runtime;
INSERT INTO public.environmental_baseline (
    id, location_id, metric_name, baseline_value
) VALUES (
    '60000000-0000-4000-8000-000000000002',
    '10000000-0000-4000-8000-000000000001', 'directus_compatibility', 2
);
RESET ROLE;

-- Legacy pilot seed data remains writable through the maintenance identity.
SET ROLE kokonut;
INSERT INTO public.environmental_baseline (
    id, location_id, metric_name, baseline_value
) VALUES (
    '60000000-0000-4000-8000-000000000003',
    '10000000-0000-4000-8000-000000000001', 'pilot_seed_compatibility', 3
);
RESET ROLE;

-- Invalid signed context fails closed; valid context is location- and plot-bound.
BEGIN;
SET LOCAL ROLE kokonut_runtime;
DO $$
DECLARE result JSONB;
BEGIN
    BEGIN
        result := kokonut_security.capture_location_environmental_baseline(
            '10000000-0000-4000-8000-000000000001',
            '50000000-0000-4000-8000-000000000001',
            '40000000-0000-4000-8000-000000000001',
            'soil_carbon', 24.97, 'tonnes/ha', DATE '2026-10-31',
            'lab_analysis', 'field_capture', ARRAY['https://evidence.invalid/a'], 'synthetic'
        );
        RAISE EXCEPTION USING ERRCODE = 'ZX004', MESSAGE = 'unsigned context unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE '42501' THEN NULL;
    END;
END $$;
RESET ROLE;
ROLLBACK;

BEGIN;
SELECT set_config('kokonut.test_actor_id', '20000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.test_location_id', '10000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.test_actor_type', 'operator', TRUE);
SELECT set_config('kokonut.test_grant_location', '10000000-0000-4000-8000-000000000001', TRUE);
SET LOCAL ROLE kokonut_runtime;
DO $$
DECLARE first_result JSONB;
DECLARE replay_result JSONB;
DECLARE conflict_result JSONB;
BEGIN
    first_result := kokonut_security.capture_location_environmental_baseline(
        '10000000-0000-4000-8000-000000000001',
        '50000000-0000-4000-8000-000000000001',
        '40000000-0000-4000-8000-000000000001',
        'soil_carbon', 24.97, 'tonnes/ha', DATE '2026-10-31',
        'lab_analysis', 'field_capture', ARRAY['https://evidence.invalid/a'], 'synthetic'
    );
    replay_result := kokonut_security.capture_location_environmental_baseline(
        '10000000-0000-4000-8000-000000000001',
        '50000000-0000-4000-8000-000000000001',
        '40000000-0000-4000-8000-000000000001',
        'soil_carbon', 24.97, 'tonnes/ha', DATE '2026-10-31',
        'lab_analysis', 'field_capture', ARRAY['https://evidence.invalid/a'], 'synthetic'
    );
    IF first_result ->> 'replayed' <> 'false'
       OR replay_result ->> 'replayed' <> 'true'
       OR first_result ->> 'baseline_id' IS DISTINCT FROM replay_result ->> 'baseline_id'
       OR first_result ->> 'location_id' IS DISTINCT FROM '10000000-0000-4000-8000-000000000001' THEN
        RAISE EXCEPTION 'capture/replay receipts did not match';
    END IF;
    BEGIN
        PERFORM kokonut_security.capture_location_environmental_baseline(
            '10000000-0000-4000-8000-000000000001',
            '50000000-0000-4000-8000-000000000001',
            '40000000-0000-4000-8000-000000000001',
            'soil_carbon', 25.00, 'tonnes/ha', DATE '2026-10-31',
            'lab_analysis', 'field_capture', ARRAY['https://evidence.invalid/a'], 'synthetic'
        );
        RAISE EXCEPTION USING ERRCODE = 'ZX005', MESSAGE = 'idempotency collision unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE 'P0001' THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.capture_location_environmental_baseline(
            '10000000-0000-4000-8000-000000000001',
            '50000000-0000-4000-8000-000000000003',
            '40000000-0000-4000-8000-000000000002',
            'soil_carbon', 24.97, 'tonnes/ha', DATE '2026-10-31',
            'lab_analysis', 'field_capture', ARRAY[]::TEXT[], NULL
        );
        RAISE EXCEPTION USING ERRCODE = 'ZX006', MESSAGE = 'cross-location plot unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE '22023' THEN NULL;
    END;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.environmental_baseline WHERE metric_name = 'soil_carbon') <> 1
       OR (SELECT count(*) FROM kokonut_security.environmental_baseline_capture_receipt) <> 1 THEN
        RAISE EXCEPTION 'idempotent capture duplicated source or receipt rows';
    END IF;
END $$;

-- The function and its private receipt roll back with the caller transaction.
BEGIN;
SELECT set_config('kokonut.test_actor_id', '20000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.test_location_id', '10000000-0000-4000-8000-000000000001', TRUE);
SELECT set_config('kokonut.test_actor_type', 'operator', TRUE);
SELECT set_config('kokonut.test_grant_location', '10000000-0000-4000-8000-000000000001', TRUE);
SET LOCAL ROLE kokonut_runtime;
SELECT kokonut_security.capture_location_environmental_baseline(
    '10000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000002', NULL,
    'rollback_probe', 1.00, 'index', DATE '2026-10-31',
    'synthetic', 'disposable', ARRAY[]::TEXT[], NULL
);
ROLLBACK;
RESET ROLE;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM kokonut_security.environmental_baseline_capture_receipt
         WHERE request_id = '50000000-0000-4000-8000-000000000002'
    ) OR EXISTS (
        SELECT 1 FROM public.environmental_baseline
         WHERE metric_name = 'rollback_probe'
    ) THEN
        RAISE EXCEPTION 'capture survived an outer transaction rollback';
    END IF;
END $$;
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-output", type=Path)
    args = parser.parse_args()
    container = f"kokonut-env-baseline-{secrets.token_hex(4)}"
    evidence = {
        "migration": MIGRATION.name,
        "disposable": True,
        "network_disabled": True,
        "candidate_legacy_or_production_db_touched": False,
        "checks": [],
    }
    try:
        run(
            [
                "docker", "run", "--detach", "--rm", "--network", "none",
                "--name", container, "-e", "POSTGRES_PASSWORD=synthetic-disposable",
                IMAGE,
            ]
        )
        ready = False
        for _ in range(60):
            result = run(
                ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
                check=False,
            )
            if result.returncode == 0:
                ready = True
                break
            time.sleep(1)
        if not ready:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        docker_psql(container, FIXTURE)
        docker_psql(container, MIGRATION.read_text(encoding="utf-8"))
        docker_psql(container, MIGRATION.read_text(encoding="utf-8"))
        docker_psql(container, ACL_ASSERTIONS)
        evidence["checks"] = [
            "migration applies and replays transactionally",
            "kokonut_runtime retains SELECT and loses table/column DML",
            "Directus and owner-seed write paths remain intact",
            "signed context and exact-location create grant are required",
            "plot must belong to the signed location",
            "same request/input replays one receipt; changed input conflicts",
            "baseline and receipt roll back with the caller transaction",
        ]
        evidence["result"] = "passed"
    finally:
        run(["docker", "rm", "--force", container], check=False)

    encoded = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.evidence_output:
        output_path = args.evidence_output
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
