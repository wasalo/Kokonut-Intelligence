#!/usr/bin/env python3
"""Exercise migration 430 against a temporary PostgreSQL 16 database."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2 import errors

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/430_isolated_market_data_worker.sql"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-17-recovery/market-data-worker-disposable.json"
)
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
INSERT INTO public.crop (name) VALUES ('Coffee (Arabica)'), ('Cocoa');
ALTER TABLE public.crop ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crop FORCE ROW LEVEL SECURITY;
ALTER TABLE public.price_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_observation FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
GRANT SELECT ON public.crop TO kokonut_runtime;
GRANT SELECT (commodity_code) ON public.price_observation TO kokonut_runtime;
GRANT UPDATE (status) ON public.ingestion_log TO kokonut_worker_execution;
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [
            docker, "exec", "-i", container, "psql", "-X", "-q",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user="postgres",
        password=password, connect_timeout=5,
    )


def call_as_market_data_login(port: int, password: str, records: list[dict]) -> int:
    connection = connect(port, password)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION AUTHORIZATION kokonut_market_data_login")
            cursor.execute(
                "SELECT kokonut_security.store_world_bank_market_data(%s::jsonb, %s, %s, %s)",
                (
                    json.dumps(records),
                    "https://example.org/world-bank-monthly.xlsx",
                    hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
                    17,
                ),
            )
            result = cursor.fetchone()[0]
            cursor.execute("RESET SESSION AUTHORIZATION")
        connection.commit()
        return result
    finally:
        connection.close()


def expect_denied_as(role: str, port: int, password: str, statement: str, args=()) -> None:
    connection = connect(port, password)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SET SESSION AUTHORIZATION {role}")
            try:
                cursor.execute(statement, args)
            except errors.InsufficientPrivilege:
                return
            raise AssertionError(f"{role} unexpectedly executed a denied statement")
    finally:
        connection.close()


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-market-data-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("MARKET_DATA_WORKER_TEST_IMAGE", "postgres:16")
    password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    checks: list[str] = []
    created = False
    connection = None
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration 430 applies on the minimal schema and replays idempotently")

        port_mapping = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_mapping:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_mapping[0].rsplit(":", 1)[1])
        connection = connect(port, password)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_market_data_login', 'public.crop', 'SELECT') "
                "OR has_table_privilege('kokonut_market_data_login', 'public.price_observation', 'INSERT') "
                "OR has_table_privilege('kokonut_market_data_login', 'public.ingestion_log', 'INSERT') "
                "OR has_column_privilege('kokonut_runtime', 'public.crop', 'name', 'SELECT') "
                "OR has_column_privilege('kokonut_runtime', 'public.price_observation', 'commodity_code', 'SELECT') "
                "OR has_column_privilege('kokonut_worker_execution', 'public.ingestion_log', 'status', 'UPDATE')"
            )
            if cursor.fetchone()[0]:
                raise AssertionError("migration left direct or column-level target grants in place")
            cursor.execute(
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                "rolbypassrls, rolinherit FROM pg_roles WHERE rolname = 'kokonut_market_data_login'"
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False):
                raise AssertionError("market-data principal does not have the expected closed role state")
        connection.commit()
        checks.append("dedicated login is non-login until secret provisioning and has no table or column grants")

        record = {
            "commodity_code": "COFFEE",
            "commodity_name": "Coffee (Arabica)",
            "price_date": "2026-07-01",
            "price_per_unit": 5.25,
        }
        first = call_as_market_data_login(port, password, [record])
        second = call_as_market_data_login(port, password, [record])
        if (first, second) != (1, 0):
            raise AssertionError(f"expected first/duplicate insertion counts (1, 0), got {(first, second)}")
        checks.append("dedicated function succeeds under forced RLS and suppresses duplicate natural keys")

        expect_denied_as(
            "kokonut_market_data_login", port, password,
            "SELECT id FROM public.crop LIMIT 1",
        )
        expect_denied_as(
            "kokonut_runtime", port, password,
            "SELECT kokonut_security.store_world_bank_market_data('[]'::jsonb, 'https://example.org/a', %s, 1)",
            ("a" * 64,),
        )
        expect_denied_as(
            "kokonut_worker_execution", port, password,
            "SELECT kokonut_security.store_world_bank_market_data('[]'::jsonb, 'https://example.org/a', %s, 1)",
            ("a" * 64,),
        )
        expect_denied_as(
            "postgres", port, password,
            "SELECT kokonut_security.store_world_bank_market_data('[]'::jsonb, 'https://example.org/a', %s, 1)",
            ("a" * 64,),
        )
        checks.append("login cannot read source tables directly; runtime, worker-execution, and non-worker sessions cannot call the function")

        for invalid, message in [
            ([{**record, "commodity_code": "DURIAN"}], "unsupported commodity"),
            ([{**record, "price_date": "2026-07-02"}], "non-month-start date"),
            ([{**record, "unexpected": "field"}], "unexpected row field"),
            ([{**record, "commodity_name": 42}], "non-string commodity name"),
            ([{**record, "price_per_unit": "5.25"}], "non-numeric JSON price"),
            ([record, {**record, "commodity_code": "DURIAN"}], "atomic mixed batch"),
        ]:
            try:
                call_as_market_data_login(port, password, invalid)
            except errors.InvalidParameterValue:
                continue
            raise AssertionError(f"bounded function accepted {message}")
        checks.append("unsupported rows, dates, extra fields, and mixed batches fail closed")

        connection = connect(port, password)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.price_observation")
            prices = cursor.fetchone()[0]
            cursor.execute("SELECT count(*), sum(rows_affected) FROM public.ingestion_log")
            audits = cursor.fetchone()
        if (prices, audits) != (1, (2, 1)):
            raise AssertionError(f"failed batches were not rolled back: prices={prices}, audits={audits}")
        connection.commit()
        checks.append("invalid mixed batch leaves price and audit state unchanged")

        connection.close()
        connection = None
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "database": "temporary PostgreSQL 16 container",
                    "candidate_or_legacy_database_touched": False,
                    "checks": checks,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "checks": len(checks), "evidence": str(output)}))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if created:
            subprocess.run(
                [docker, "rm", "-f", container], text=True, capture_output=True, check=False
            )


if __name__ == "__main__":
    raise SystemExit(main())
