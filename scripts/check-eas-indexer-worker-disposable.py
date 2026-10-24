#!/usr/bin/env python3
"""Exercise migration 433 on a disposable PostgreSQL 16 instance."""

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
MIGRATION = ROOT / "schemas/postgres/433_isolated_eas_indexer.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-17-recovery/eas-indexer-worker-disposable.json"
WALLET_ID = "a0000000-0000-0000-0000-000000000001"
RECIPIENT = "0x" + "a" * 40
FIXTURE = f"""
CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE TABLE public.wallet_profile (
    id UUID PRIMARY KEY,
    address VARCHAR(42),
    chain VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE public.attestation_schema (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_uid VARCHAR(66) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    schema_text TEXT,
    chain VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE public.attestation_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_id UUID NOT NULL REFERENCES public.attestation_schema(id),
    attestation_uid VARCHAR(66) UNIQUE,
    subject_type VARCHAR(100),
    claim_data JSONB NOT NULL,
    status VARCHAR(50),
    tx_hash VARCHAR(66),
    chain VARCHAR(50),
    attested_at TIMESTAMPTZ
);
CREATE TABLE public.eas_indexer_cursor (
    chain TEXT NOT NULL,
    wallet_id UUID NOT NULL REFERENCES public.wallet_profile(id) ON DELETE CASCADE,
    last_attestation_time BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chain, wallet_id)
);
CREATE TABLE public.chain_indexer_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain VARCHAR(50) NOT NULL,
    indexer_type VARCHAR(50) NOT NULL,
    last_synced_block BIGINT,
    last_synced_at TIMESTAMPTZ,
    status VARCHAR(50),
    error_message TEXT,
    metadata JSONB DEFAULT '{{}}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chain, indexer_type)
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
    status VARCHAR(50),
    error_message TEXT,
    rows_affected INTEGER,
    processing_time_ms INTEGER,
    processor_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE public.clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key VARCHAR(255) NOT NULL UNIQUE,
    source_table VARCHAR(100) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    columns JSONB NOT NULL,
    rows JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO public.wallet_profile (id, address, chain, is_active)
VALUES ('{WALLET_ID}', '{RECIPIENT}', 'celo', TRUE);
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run([
        docker, "exec", "-i", container, "psql", "-X", "-q", "-v",
        "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ], input_text=statement)


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user="postgres",
        password=password, connect_timeout=5,
    )


def attestation() -> dict:
    return {
        "id": "0x" + "1" * 64,
        "txid": "0x" + "2" * 64,
        "schema": {"id": "0x" + "3" * 64, "schema": "uint256 value"},
        "attester": "0x" + "4" * 40,
        "recipient": RECIPIENT,
        "data": "0x1234",
        "time": "1800000000",
        "timeCreated": "1800000000",
        "revocable": True,
        "revoked": False,
        "expirationTime": "0",
    }


def _payload_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _call_as_worker(connection, function_call: str, params: tuple):
    with connection.cursor() as cursor:
        cursor.execute("SET SESSION AUTHORIZATION kokonut_eas_indexer_login")
        cursor.execute(function_call, params)
        result = cursor.fetchall()
        cursor.execute("RESET SESSION AUTHORIZATION")
    connection.commit()
    return result


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-eas-indexer-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("EAS_INDEXER_TEST_IMAGE", "postgres:16")
    password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    checks: list[str] = []
    created = False
    connection = None
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={password}", "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration 433 applies and replays on the isolated EAS schema fixture")

        docker_sql(docker, container, """
        ALTER ROLE kokonut_eas_indexer_login WITH LOGIN PASSWORD 'synthetic-eas-indexer-password'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
        GRANT CONNECT ON DATABASE postgres TO kokonut_eas_indexer_login;
        ALTER TABLE public.wallet_profile ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.wallet_profile FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.attestation_schema ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.attestation_schema FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.attestation_record ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.attestation_record FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.eas_indexer_cursor ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.eas_indexer_cursor FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.chain_indexer_status ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.chain_indexer_status FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
        """)
        mapping = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not mapping:
            raise RuntimeError("disposable PostgreSQL host port mapping is missing")
        port = int(mapping[0].rsplit(":", 1)[1])
        connection = connect(port, password)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                "rolbypassrls, rolinherit FROM pg_roles WHERE rolname='kokonut_eas_indexer_login'"
            )
            if cursor.fetchone() != (True, False, False, False, False, False, False):
                raise AssertionError("EAS login role attributes are unsafe")
            cursor.execute(
                "SELECT has_table_privilege('kokonut_eas_indexer_login', 'public.wallet_profile', 'SELECT') "
                "OR has_table_privilege('kokonut_eas_indexer_login', 'public.attestation_record', 'INSERT') "
                "OR has_table_privilege('kokonut_eas_indexer_login', 'public.clickhouse_outbox', 'INSERT')"
            )
            if cursor.fetchone()[0]:
                raise AssertionError("EAS login has direct canonical table access")
        connection.commit()
        checks.append("the EAS login has no direct table grants; forced RLS stays enabled")

        item = attestation()
        page = [{"attestation": item, "payload_hash": _payload_hash(item)}]
        _call_as_worker(
            connection,
            "SELECT kokonut_security.acquire_eas_indexer_chain_lock(%s)",
            ("celo",),
        )
        recipients = _call_as_worker(
            connection,
            "SELECT wallet_id, recipient_address FROM kokonut_security.list_eas_indexer_recipients(%s)",
            ("celo",),
        )
        if recipients != [(WALLET_ID, RECIPIENT)]:
            raise AssertionError(f"unexpected EAS recipients: {recipients}")
        cursor_before = _call_as_worker(
            connection,
            "SELECT kokonut_security.read_eas_indexer_cursor(%s, %s::uuid)",
            ("celo", WALLET_ID),
        )
        if cursor_before != [(0,)]:
            raise AssertionError(f"unexpected initial recipient cursor: {cursor_before}")
        inserted = _call_as_worker(
            connection,
            "SELECT kokonut_security.store_eas_indexer_page(%s, %s::uuid, %s::jsonb)",
            ("celo", WALLET_ID, json.dumps(page)),
        )
        repeated = _call_as_worker(
            connection,
            "SELECT kokonut_security.store_eas_indexer_page(%s, %s::uuid, %s::jsonb)",
            ("celo", WALLET_ID, json.dumps(page)),
        )
        if inserted != [(1,)] or repeated != [(0,)]:
            raise AssertionError(f"EAS insert/replay result mismatch: {inserted}, {repeated}")
        advanced = _call_as_worker(
            connection,
            "SELECT kokonut_security.advance_eas_indexer_cursor(%s, %s::uuid, %s)",
            ("celo", WALLET_ID, 1_800_000_000),
        )
        if advanced != [(1_800_000_000,)]:
            raise AssertionError(f"EAS cursor failed to advance: {advanced}")
        finished = _call_as_worker(
            connection,
            "SELECT kokonut_security.finish_eas_indexer_chain(%s,%s,%s,%s,%s,%s)",
            ("celo", "healthy", None, 1, 17, _payload_hash({"chain": "celo", "wallets": 1})),
        )
        if finished != [(1_800_000_000,)]:
            raise AssertionError(f"unexpected EAS chain watermark: {finished}")
        _call_as_worker(
            connection,
            "SELECT kokonut_security.release_eas_indexer_chain_lock(%s)",
            ("celo",),
        )
        checks.append("recipient lookup, cursor advancement, attestation/outbox atomicity, duplicate replay, and status audit pass under forced RLS")

        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.attestation_record")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("attestation record was not inserted exactly once")
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("ClickHouse intent was not enqueued exactly once")
            cursor.execute("SELECT status, metadata->>'last_attestation_time' FROM public.chain_indexer_status")
            if cursor.fetchone() != ("healthy", "1800000000"):
                raise AssertionError("EAS chain completion status does not match the cursor")
            cursor.execute("SELECT status, rows_affected FROM public.ingestion_log")
            if cursor.fetchone() != ("success", 1):
                raise AssertionError("EAS ingestion audit did not record the inserted count")
        connection.commit()

        for role, statement in (
            ("kokonut_eas_indexer_login", "SELECT id FROM public.wallet_profile"),
            ("kokonut_runtime", "SELECT kokonut_security.list_eas_indexer_recipients('celo')"),
        ):
            with connection.cursor() as cursor:
                cursor.execute(f"SET SESSION AUTHORIZATION {role}")
                try:
                    cursor.execute(statement)
                except errors.InsufficientPrivilege:
                    connection.rollback()
                    with connection.cursor() as reset_cursor:
                        reset_cursor.execute("RESET SESSION AUTHORIZATION")
                    connection.commit()
                    continue
                raise AssertionError(f"{role} unexpectedly executed a denied operation")
        checks.append("direct relation access and runtime execution of EAS worker functions are denied")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"migration": 433, "checks": checks}, indent=2) + "\n")
        print(json.dumps({"status": "passed", "checks": checks, "evidence": str(output)}, indent=2))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if created:
            subprocess.run([docker, "rm", "-f", container], capture_output=True, text=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
