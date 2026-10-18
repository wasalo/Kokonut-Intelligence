#!/usr/bin/env python3
"""Exercise migration 436 on a disposable, network-disabled PostgreSQL 16 container."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/436_isolated_rpc_indexer.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-18-recovery/rpc-indexer-worker-disposable.json"
WALLET_ID = "11111111-1111-4111-8111-111111111111"
ADDRESS = "0x" + "a" * 40
TX_HASH = "0x" + "b" * 64

FIXTURE = f"""
CREATE TABLE public.wallet_profile (
    id UUID PRIMARY KEY,
    address VARCHAR(42) NOT NULL,
    chain VARCHAR(50) NOT NULL,
    label VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE public.wallet_activity_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID NOT NULL REFERENCES public.wallet_profile(id),
    chain VARCHAR(50) NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    block_number BIGINT,
    block_timestamp TIMESTAMPTZ,
    from_address VARCHAR(42),
    to_address VARCHAR(42),
    value NUMERIC(18,8),
    token VARCHAR(50),
    gas_used NUMERIC(18,8),
    gas_price NUMERIC(18,8),
    status VARCHAR(20),
    activity_type VARCHAR(100)
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
INSERT INTO public.wallet_profile (id, address, chain, label)
VALUES ('{WALLET_ID}', '{ADDRESS}', 'celo', 'Synthetic Treasury');
INSERT INTO public.wallet_activity_event (
    wallet_id, chain, tx_hash, block_number, block_timestamp, from_address,
    to_address, value, token, gas_used, gas_price, status, activity_type
) VALUES (
    '{WALLET_ID}', 'celo', 'balance-check-celo-{WALLET_ID}-100', 100,
    NOW(), '', '{ADDRESS}', 1.23456789, 'ETH', 0, 0, 'success', 'balance_check'
);
"""

ACCEPTANCE = f"""
ALTER TABLE public.wallet_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_profile FORCE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_activity_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_activity_event FORCE ROW LEVEL SECURITY;
ALTER TABLE public.chain_indexer_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_indexer_status FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
ALTER ROLE kokonut_rpc_indexer_login WITH LOGIN PASSWORD 'synthetic-rpc-indexer-password';

SET SESSION AUTHORIZATION kokonut_rpc_indexer_login;
DO $$
DECLARE
    record JSONB := jsonb_build_object(
        'wallet_id', '{WALLET_ID}', 'chain', 'celo', 'tx_hash', '{TX_HASH}',
        'block_number', 100, 'block_timestamp', '2023-11-14T22:13:20+00:00',
        'from_address', '', 'to_address', '{ADDRESS}', 'value', 1.23456789,
        'token', 'ETH', 'gas_used', 0, 'gas_price', 0,
        'status', 'success', 'activity_type', 'balance_check'
    );
    changed JSONB;
    inserted BOOLEAN;
    wallet_rows INTEGER;
BEGIN
    PERFORM kokonut_security.acquire_rpc_indexer_chain_lock('celo');
    SELECT count(*) INTO wallet_rows
      FROM kokonut_security.list_rpc_indexer_wallets('celo');
    IF wallet_rows <> 1 THEN RAISE EXCEPTION 'scoped wallet list mismatch'; END IF;

    changed := jsonb_set(record, '{{tx_hash}}', 'null'::JSONB);
    BEGIN
        PERFORM kokonut_security.store_rpc_indexer_snapshot(
            'celo', '{WALLET_ID}', changed, repeat('e', 64)
        );
        RAISE EXCEPTION 'snapshot without a transaction identity unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE '22023' THEN NULL;
    END;

    inserted := kokonut_security.store_rpc_indexer_snapshot(
        'celo', '{WALLET_ID}', record, repeat('a', 64)
    );
    IF inserted THEN RAISE EXCEPTION 'legacy snapshot was duplicated'; END IF;

    changed := jsonb_set(record, '{{block_number}}', '101'::JSONB);
    changed := jsonb_set(changed, '{{block_timestamp}}', to_jsonb('2023-11-14T22:13:21+00:00'::TEXT));
    changed := jsonb_set(changed, '{{tx_hash}}', to_jsonb('0x' || repeat('c', 64)));
    changed := jsonb_set(changed, '{{value}}', '0.00000001'::JSONB);
    inserted := kokonut_security.store_rpc_indexer_snapshot(
        'celo', '{WALLET_ID}', changed, repeat('a', 64)
    );
    IF NOT inserted THEN RAISE EXCEPTION 'new snapshot was not inserted'; END IF;
    inserted := kokonut_security.store_rpc_indexer_snapshot(
        'celo', '{WALLET_ID}', changed, repeat('a', 64)
    );
    IF inserted THEN RAISE EXCEPTION 'duplicate snapshot was not suppressed'; END IF;

    changed := jsonb_set(changed, '{{value}}', '1.5'::JSONB);
    BEGIN
        PERFORM kokonut_security.store_rpc_indexer_snapshot(
            'celo', '{WALLET_ID}', changed, repeat('c', 64)
        );
        RAISE EXCEPTION 'conflicting snapshot unexpectedly succeeded';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    PERFORM kokonut_security.finish_rpc_indexer_chain(
        'celo', 'healthy', NULL, 1, 101, 25, repeat('d', 64)
    );

    BEGIN
        PERFORM 1 FROM public.wallet_activity_event;
        RAISE EXCEPTION 'direct activity table access unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.release_rpc_indexer_chain_lock('celo');
END;
$$;
RESET SESSION AUTHORIZATION;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.wallet_activity_event) <> 2 THEN
        RAISE EXCEPTION 'snapshot write count mismatch';
    END IF;
    IF (SELECT count(*) FROM public.clickhouse_outbox) <> 1 THEN
        RAISE EXCEPTION 'outbox idempotency mismatch';
    END IF;
    IF (SELECT count(*) FROM public.ingestion_log) <> 1 THEN
        RAISE EXCEPTION 'completion audit count mismatch';
    END IF;
    IF (SELECT value FROM public.wallet_activity_event
         WHERE tx_hash = '0x' || repeat('c', 64)) IS DISTINCT FROM 0.00000001::NUMERIC THEN
        RAISE EXCEPTION 'eight-decimal wallet balance precision was not preserved';
    END IF;
    IF NOT has_function_privilege(
        'kokonut_rpc_indexer_login',
        'kokonut_security.store_rpc_indexer_snapshot(text,uuid,jsonb,text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'bounded function grant missing';
    END IF;
    IF has_table_privilege(
        'kokonut_rpc_indexer_login', 'public.wallet_activity_event', 'SELECT'
    ) OR has_table_privilege(
        'kokonut_rpc_indexer_login', 'public.wallet_activity_event', 'INSERT'
    ) THEN
        RAISE EXCEPTION 'worker login has direct activity table privilege';
    END IF;
END;
$$;
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker is required for the disposable PostgreSQL acceptance")
    name = f"kokonut-rpc-indexer-check-{secrets.token_hex(4)}"
    image = "postgres:16"
    started = False
    try:
        run([
            docker, "run", "--detach", "--rm", "--network", "none", "--name", name,
            "-e", "POSTGRES_PASSWORD=synthetic-only-password", image,
            "postgres", "-c", "listen_addresses=127.0.0.1",
        ])
        started = True
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            ready = subprocess.run(
                [docker, "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                text=True, capture_output=True, check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            logs = subprocess.run(
                [docker, "logs", name], text=True, capture_output=True, check=False
            )
            details = "\n".join(
                part for part in (logs.stdout, logs.stderr) if part
            )
            raise RuntimeError(
                "disposable PostgreSQL did not become ready"
                + (f":\n{details}" if details else "")
            )

        migration = MIGRATION.read_text()
        docker_sql(docker, name, FIXTURE + migration + migration + ACCEPTANCE)
        evidence = {
            "migration": MIGRATION.name,
            "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
            "migration_replay": "passed twice",
            "postgresql_major": 16,
            "network": "none",
            "forced_rls": "bounded function operations passed",
            "direct_table_access": "denied",
            "snapshot_and_outbox_idempotency": "passed",
            "numeric_eight_decimal_precision": "passed",
            "legacy_snapshot_reuse": "passed without duplicate activity or outbox row",
            "malformed_identity": "rejected",
            "conflicting_snapshot": "rejected",
            "runtime_database_touched": False,
            "provider_contacted": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps(evidence, sort_keys=True))
        return 0
    finally:
        if started:
            subprocess.run([docker, "rm", "--force", name], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
