#!/usr/bin/env python3
"""Verify migration 718's isolated global market-data writers on disposable PostgreSQL 16."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_430 = ROOT / "schemas/postgres/430_isolated_market_data_worker.sql"
MIGRATION_718 = ROOT / "schemas/postgres/718_isolated_market_data_global_writes.sql"

FIXTURE = """
CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE kokonut_worker_execution NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE TABLE public.crop (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL
);
CREATE TABLE public.price_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_id UUID REFERENCES public.crop(id),
    commodity_code VARCHAR(50),
    market_name VARCHAR(100),
    price_date DATE NOT NULL,
    price_per_unit NUMERIC(12,4),
    unit VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'USD',
    source VARCHAR(100),
    source_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    location_id UUID,
    quality_grade VARCHAR(50),
    CONSTRAINT uq_price_observation_source_period
        UNIQUE (source, commodity_code, market_name, price_date)
);
CREATE TABLE public.ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_id VARCHAR(255),
    target_table VARCHAR(100) NOT NULL,
    target_id UUID,
    operation VARCHAR(50) NOT NULL,
    payload_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'success',
    rows_affected INTEGER,
    processing_time_ms INTEGER,
    processor_version VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE public.scheduled_task (
    name TEXT PRIMARY KEY,
    module_path TEXT NOT NULL,
    command_args JSONB NOT NULL
);
INSERT INTO public.crop (name) VALUES ('Coffee (Arabica)'), ('Cocoa'), ('Bananas');
INSERT INTO public.scheduled_task (name, module_path, command_args)
VALUES (
    'market_data_world_bank',
    'services.ingestion.market_data',
    '["--source", "world_bank"]'::JSONB
);
ALTER TABLE public.crop ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crop FORCE ROW LEVEL SECURITY;
ALTER TABLE public.price_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_observation FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
CREATE POLICY runtime_price_observation_read ON public.price_observation
    FOR SELECT TO kokonut_runtime USING (true);
GRANT SELECT ON public.price_observation TO kokonut_runtime;
"""


def run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{details}"
        )
    return result


def docker_sql(docker: str, container: str, statement: str) -> str:
    result = run(
        [
            docker, "exec", "-i", container, "psql", "-X", "-q", "-t", "-A",
            "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose",
            "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )
    return result.stdout.strip()


def docker_sql_must_fail(docker: str, container: str, statement: str) -> str:
    result = subprocess.run(
        [
            docker, "exec", "-i", container, "psql", "-X", "-q", "-t", "-A",
            "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose",
            "-U", "postgres", "-d", "postgres",
        ],
        input=statement,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        raise AssertionError(f"statement unexpectedly succeeded: {statement}")
    return result.stdout + result.stderr


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def call_manual(docker: str, container: str, *, price: str = "5.25", crop: str = "Coffee (Arabica)") -> str:
    statement = f"""
SET SESSION AUTHORIZATION kokonut_market_data_login;
SELECT kokonut_security.store_manual_market_price(
    {literal(crop)}, 'Adelphi market', {price}::NUMERIC, 'grade A',
    'kg', 'USD', '{{"source_note":"synthetic"}}'::JSONB
);
"""
    return docker_sql(docker, container, statement)


def call_seed(docker: str, container: str, records: list[dict]) -> int:
    serialized = json.dumps(records, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    statement = f"""
SET SESSION AUTHORIZATION kokonut_market_data_login;
SELECT kokonut_security.store_world_bank_seed_market_data(
    {literal(json.dumps(records))}::JSONB, {literal(digest)}, 7
);
"""
    return int(docker_sql(docker, container, statement))


def call_live(docker: str, container: str, records: list[dict]) -> int:
    payload = json.dumps(records)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    statement = f"""
SET SESSION AUTHORIZATION kokonut_market_data_login;
SELECT kokonut_security.store_world_bank_market_data(
    {literal(payload)}::JSONB,
    'https://example.org/world-bank-monthly.xlsx',
    {literal(digest)}, 9
);
"""
    return int(docker_sql(docker, container, statement))


def expect_login_failure(docker: str, container: str, statement: str, label: str) -> None:
    output = docker_sql_must_fail(
        docker, container,
        "SET SESSION AUTHORIZATION kokonut_market_data_login;\n" + statement,
    )
    if "ERROR:" not in output:
        raise AssertionError(f"{label} did not report a PostgreSQL error")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    if not MIGRATION_430.exists() or not MIGRATION_718.exists():
        raise RuntimeError("required market-data migration file is missing")

    container = f"kokonut-price-worker-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("PRICE_OBSERVATION_WORKER_TEST_IMAGE", "postgres:16")
    password = secrets.token_urlsafe(24)
    created = False
    checks: list[str] = []
    try:
        run([
            docker, "run", "-d", "--rm", "--network", "none", "--name", container,
            "-e", f"POSTGRES_PASSWORD={password}", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE)
        migration_430 = MIGRATION_430.read_text(encoding="utf-8")
        migration_718 = MIGRATION_718.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_430)
        docker_sql(docker, container, migration_718)
        docker_sql(docker, container, migration_718)
        checks.append("migrations 430 and 718 apply and migration 718 replays cleanly")

        privileges = docker_sql(docker, container, """
SELECT has_table_privilege('kokonut_runtime', 'public.price_observation', 'SELECT')
   AND NOT has_table_privilege('kokonut_runtime', 'public.price_observation', 'INSERT')
   AND NOT has_table_privilege('kokonut_runtime', 'public.price_observation', 'UPDATE')
   AND NOT has_table_privilege('kokonut_runtime', 'public.price_observation', 'DELETE')
   AND NOT has_column_privilege('kokonut_runtime', 'public.price_observation', 'commodity_code', 'INSERT')
   AND NOT has_column_privilege('kokonut_runtime', 'public.price_observation', 'commodity_code', 'UPDATE')
   AND NOT has_table_privilege('kokonut_market_data_login', 'public.price_observation', 'INSERT')
   AND NOT has_table_privilege('kokonut_market_data_login', 'public.price_observation', 'SELECT')
   AND has_function_privilege(
       'kokonut_market_data_login',
       'kokonut_security.store_manual_market_price(text,text,numeric,text,text,text,jsonb)',
       'EXECUTE'
   )
   AND has_function_privilege(
       'kokonut_market_data_login',
       'kokonut_security.store_world_bank_seed_market_data(jsonb,text,integer)',
       'EXECUTE'
   )
   AND NOT has_function_privilege(
       'kokonut_runtime',
       'kokonut_security.store_manual_market_price(text,text,numeric,text,text,text,jsonb)',
       'EXECUTE'
   )
   AND NOT has_function_privilege(
       'kokonut_worker_execution',
       'kokonut_security.store_world_bank_seed_market_data(jsonb,text,integer)',
       'EXECUTE'
   );
""")
        if privileges != "t":
            raise AssertionError(f"unexpected runtime/worker grants: {privileges}")
        owner_state = docker_sql(docker, container, """
SELECT (SELECT rolcanlogin = false AND rolsuper = false AND rolbypassrls = false
          FROM pg_roles WHERE rolname = 'kokonut_market_data_owner')
   AND (SELECT count(*) = 0 FROM pg_auth_members m
        JOIN pg_roles r ON r.oid = m.roleid
        WHERE r.rolname = 'kokonut_market_data_owner');
""")
        if owner_state != "t":
            raise AssertionError("market-data owner role is not a closed, non-login role")
        checks.append("runtime retains SELECT only; dedicated login has only exact function EXECUTE grants")

        manual_one = call_manual(docker, container)
        manual_two = call_manual(docker, container)
        if manual_one == manual_two or len(manual_one) != 36:
            raise AssertionError("manual writer did not preserve append semantics or return a UUID")
        manual_state = docker_sql(docker, container, f"""
SELECT count(*) = 2
   AND bool_and(source = 'manual' AND location_id IS NULL
                AND quality_grade = 'grade A' AND unit = 'kg' AND currency = 'USD'
                AND price_date = (pg_catalog.clock_timestamp() AT TIME ZONE 'UTC')::DATE)
   AND count(DISTINCT id) = 2
FROM public.price_observation
WHERE id IN ({literal(manual_one)}::UUID, {literal(manual_two)}::UUID);
""")
        if manual_state != "t":
            raise AssertionError("manual write lost its global scope, attribution, or date semantics")
        checks.append("manual writes preserve exact crop lookup, source, UTC date, global scope, and append behavior")

        expect_login_failure(
            docker, container,
            "INSERT INTO public.price_observation (market_name, price_date) VALUES ('bypass', CURRENT_DATE);",
            "direct table insert",
        )
        expect_login_failure(
            docker, container,
            "SELECT id FROM public.crop LIMIT 1;",
            "direct crop read",
        )
        for crop, price, label in [
            ("Missing crop", "2.00", "unknown crop"),
            ("Coffee (Arabica)", "0", "non-positive price"),
            ("Coffee (Arabica)", "100000000", "numeric overflow price"),
            ("Coffee (Arabica)", "'NaN'", "NaN price"),
        ]:
            output = docker_sql_must_fail(docker, container, f"""
SET SESSION AUTHORIZATION kokonut_market_data_login;
SELECT kokonut_security.store_manual_market_price(
    {literal(crop)}, 'Adelphi market', {price}::NUMERIC, NULL, 'kg', 'USD', '{{}}'::JSONB
);
""")
            if "22023" not in output:
                raise AssertionError(f"manual writer did not reject {label} as invalid input")
        checks.append("manual writer rejects direct table access and invalid crop/price values")

        seed_records = [
            {"commodity_code": "COFFEE", "commodity_name": "Coffee (Arabica)",
             "price_date": "2025-01-01", "price_per_unit": 7.89, "unit": "USD/kg"},
            {"commodity_code": "COCOA", "commodity_name": "Cocoa",
             "price_date": "2025-01-01", "price_per_unit": 7.15, "unit": "USD/kg"},
            {"commodity_code": "PALM_OIL", "commodity_name": "Palm Oil",
             "price_date": "2025-01-01", "price_per_unit": 865, "unit": "USD/tonne"},
            {"commodity_code": "RICE", "commodity_name": "Rice",
             "price_date": "2025-01-01", "price_per_unit": 555, "unit": "USD/tonne"},
            {"commodity_code": "MAIZE", "commodity_name": "Maize",
             "price_date": "2025-01-01", "price_per_unit": 218, "unit": "USD/tonne"},
            {"commodity_code": "SUGAR", "commodity_name": "Sugar",
             "price_date": "2025-01-01", "price_per_unit": 0.35, "unit": "USD/kg"},
            {"commodity_code": "TEA", "commodity_name": "Tea",
             "price_date": "2025-01-01", "price_per_unit": 2.78, "unit": "USD/kg"},
            {"commodity_code": "BANANA", "commodity_name": "Bananas",
             "price_date": "2025-04-01", "price_per_unit": 2.85, "unit": "USD/kg"},
        ]
        if (call_seed(docker, container, seed_records), call_seed(docker, container, seed_records)) != (8, 0):
            raise AssertionError("reference seed write did not insert each supported commodity once")
        seed_state = docker_sql(docker, container, """
SELECT count(*) = 8
   AND bool_and(source = 'world_bank_pink_sheet_seed'
                AND market_name = 'World Bank Pink Sheet'
                AND source_url = 'https://www.worldbank.org/en/research/commodity-markets'
                AND metadata = '{"source_type":"seed_data"}'::JSONB
                AND location_id IS NULL AND currency = 'USD')
FROM public.price_observation
WHERE source = 'world_bank_pink_sheet_seed';
""")
        if seed_state != "t":
            raise AssertionError("seed write lost global scope or source attribution")
        checks.append("reference seeds preserve canonical source data, null location, and replay idempotency")

        invalid_seed_batches = [
            ([{**seed_records[0], "commodity_code": "DURIAN"}], "unsupported commodity"),
            ([{**seed_records[0], "unit": "kg"}], "mismatched unit"),
            ([{**seed_records[0], "price_date": "2025-02-02"}], "non-month-start date"),
            ([{**seed_records[0], "extra": "field"}], "unexpected field"),
            ([seed_records[0], {**seed_records[1], "commodity_code": "DURIAN"}], "atomic mixed batch"),
        ]
        for bad_records, label in invalid_seed_batches:
            try:
                call_seed(docker, container, bad_records)
            except RuntimeError as exc:
                # The SQLSTATE proves this was the bounded function's input
                # rejection, rather than a Docker/psql failure.
                if "22023" not in str(exc):
                    raise
            else:
                raise AssertionError(f"reference seed writer accepted {label}")
        bad_seed_totals = docker_sql(docker, container, """
SELECT (SELECT count(*) FROM public.price_observation WHERE source = 'world_bank_pink_sheet_seed') = 8
   AND (SELECT count(*) FROM public.ingestion_log WHERE source_id = 'world_bank_pink_sheet_seed') = 2;
""")
        if bad_seed_totals != "t":
            raise AssertionError("invalid seed batches changed observations or ingestion audit rows")
        checks.append("invalid seed rows fail atomically without adding price or audit state")

        live_record = {
            "commodity_code": "COFFEE",
            "commodity_name": "Coffee (Arabica)",
            "price_date": "2026-07-01",
            "price_per_unit": 5.25,
        }
        if (call_live(docker, container, [live_record]), call_live(docker, container, [live_record])) != (1, 0):
            raise AssertionError("existing World Bank writer behavior changed")
        live_state = docker_sql(docker, container, """
SELECT count(*) = 1
   AND bool_and(source = 'world_bank_pink_sheet'
                AND source_url = 'https://example.org/world-bank-monthly.xlsx'
                AND location_id IS NULL AND metadata = '{"source_type":"live_download"}'::JSONB)
FROM public.price_observation WHERE source = 'world_bank_pink_sheet';
""")
        if live_state != "t":
            raise AssertionError("existing World Bank writer lost global source semantics")
        checks.append("existing live World Bank function retains source, location, audit, and idempotency")

        # Simulate a broad compatibility grant, then ensure migration replay
        # restores its runtime DML boundary without removing SELECT.
        docker_sql(docker, container, """
GRANT ALL ON TABLE public.price_observation TO kokonut_runtime;
GRANT INSERT (commodity_code), UPDATE (commodity_code), REFERENCES (commodity_code)
    ON TABLE public.price_observation TO kokonut_runtime;
""")
        docker_sql(docker, container, migration_718)
        reprovision_state = docker_sql(docker, container, """
SELECT has_table_privilege('kokonut_runtime', 'public.price_observation', 'SELECT')
   AND NOT has_table_privilege('kokonut_runtime', 'public.price_observation', 'INSERT')
   AND NOT has_table_privilege('kokonut_runtime', 'public.price_observation', 'UPDATE')
   AND NOT has_column_privilege('kokonut_runtime', 'public.price_observation', 'commodity_code', 'INSERT')
   AND NOT has_column_privilege('kokonut_runtime', 'public.price_observation', 'commodity_code', 'UPDATE');
""")
        if reprovision_state != "t":
            raise AssertionError("migration replay failed to restore runtime DML denial")
        runtime_read = docker_sql(docker, container, """
SET SESSION AUTHORIZATION kokonut_runtime;
SELECT count(*) FROM public.price_observation;
""")
        if runtime_read != "11":
            raise AssertionError(f"runtime SELECT was not preserved after replay: {runtime_read}")
        checks.append("replay repairs broad runtime DML grants while preserving usable runtime SELECT")

        schedule = docker_sql(docker, container, """
SELECT module_path || '|' || command_args::TEXT
FROM public.scheduled_task WHERE name = 'market_data_world_bank';
""")
        if schedule != 'services.ingestion.market_data|["--source", "world_bank"]':
            raise AssertionError(f"legacy persisted market-data task was rewritten: {schedule}")
        checks.append("migration leaves the old persisted task module and arguments intact for the compatibility dispatcher")

        print(json.dumps({
            "status": "passed",
            "database": "temporary PostgreSQL 16 container (network disabled)",
            "candidate_or_legacy_database_touched": False,
            "checks": checks,
        }, indent=2))
        return 0
    finally:
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
