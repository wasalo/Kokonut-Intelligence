#!/usr/bin/env python3
"""Replay migration 643 and exercise its execute-only contract in disposable PostgreSQL 16."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/643_isolated_gnosis_moloch_indexer.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/gnosis-indexer-worker-disposable.json"
WALLET_ID = "11111111-1111-4111-8111-111111111111"
PROTOCOL_ID = "22222222-2222-4222-8222-222222222222"
LOCATION_ID = "33333333-3333-4333-8333-333333333333"
TX_HASH = "0x" + "a" * 64
BLOCK_HASH = "0x" + "b" * 64

FIXTURE = f"""
CREATE TABLE public.wallet_profile (
    id UUID PRIMARY KEY, address VARCHAR(42) NOT NULL, chain VARCHAR(50) NOT NULL,
    owner_type VARCHAR(100), owner_id UUID
);
CREATE TABLE public.protocol (id UUID PRIMARY KEY, slug VARCHAR(255) UNIQUE NOT NULL);
CREATE TABLE public.chain_indexer_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), chain VARCHAR(50) NOT NULL,
    indexer_type VARCHAR(50) NOT NULL, last_synced_block BIGINT,
    last_synced_at TIMESTAMPTZ, status VARCHAR(50), error_message TEXT,
    metadata JSONB DEFAULT '{{}}', updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chain, indexer_type)
);
CREATE TABLE public.gnosis_event_log_receipt (
    chain VARCHAR(50) NOT NULL, transaction_hash VARCHAR(66) NOT NULL,
    log_index BIGINT NOT NULL, block_number BIGINT NOT NULL,
    block_hash VARCHAR(66) NOT NULL, event_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (chain, transaction_hash, log_index)
);
CREATE TABLE public.governance_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), wallet_id UUID, protocol_id UUID,
    chain VARCHAR(50) NOT NULL, event_type VARCHAR(100), proposal_id VARCHAR(255),
    proposal_title TEXT, vote_choice VARCHAR(50), amount NUMERIC(18,8), token VARCHAR(50),
    tx_hash VARCHAR(66), block_number BIGINT, block_timestamp TIMESTAMPTZ,
    metadata JSONB DEFAULT '{{}}'
);
CREATE TABLE public.treasury_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID, wallet_id UUID,
    chain VARCHAR(50) NOT NULL, event_date DATE NOT NULL, flow_direction VARCHAR(10) NOT NULL,
    amount NUMERIC(18,8) NOT NULL, token VARCHAR(50) NOT NULL, usd_value NUMERIC(15,2),
    source VARCHAR(255), tx_hash VARCHAR(66), block_number BIGINT,
    verified BOOLEAN DEFAULT FALSE, notes TEXT
);
CREATE TABLE public.digital_lego_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), wallet_id UUID, protocol_id UUID NOT NULL,
    location_id UUID, usage_date DATE NOT NULL, action_type VARCHAR(100), amount NUMERIC(18,8),
    token VARCHAR(50), tx_hash VARCHAR(66), chain VARCHAR(50), block_number BIGINT,
    verified BOOLEAN DEFAULT FALSE, notes TEXT
);
CREATE TABLE public.clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), event_key VARCHAR(255) NOT NULL UNIQUE,
    source_table VARCHAR(100) NOT NULL, source_id VARCHAR(255) NOT NULL,
    target_table VARCHAR(100) NOT NULL, columns JSONB NOT NULL, rows JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0, available_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO public.wallet_profile VALUES (
    '{WALLET_ID}', '0x{'c' * 40}', 'gnosis', 'farm', '{LOCATION_ID}'
);
INSERT INTO public.protocol VALUES ('{PROTOCOL_ID}', 'kokonut-treasury');
"""

ACCEPTANCE = f"""
ALTER TABLE public.wallet_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_profile FORCE ROW LEVEL SECURITY;
ALTER TABLE public.protocol ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.protocol FORCE ROW LEVEL SECURITY;
ALTER TABLE public.chain_indexer_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_indexer_status FORCE ROW LEVEL SECURITY;
ALTER TABLE public.gnosis_event_log_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gnosis_event_log_receipt FORCE ROW LEVEL SECURITY;
ALTER TABLE public.governance_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.governance_event FORCE ROW LEVEL SECURITY;
ALTER TABLE public.treasury_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.treasury_event FORCE ROW LEVEL SECURITY;
ALTER TABLE public.digital_lego_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.digital_lego_usage FORCE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
ALTER ROLE kokonut_gnosis_indexer_login WITH LOGIN PASSWORD 'synthetic-gnosis-password';
SET SESSION AUTHORIZATION kokonut_gnosis_indexer_login;
DO $$
DECLARE v UUID; inserted BOOLEAN; found_block BIGINT; outbox_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login' THEN
        RAISE EXCEPTION 'worker session identity was not established';
    END IF;
    PERFORM kokonut_security.acquire_gnosis_indexer_lock();
    IF EXISTS (SELECT 1 FROM kokonut_security.read_gnosis_indexer_cursor()) THEN
        RAISE EXCEPTION 'new cursor unexpectedly exists';
    END IF;
    SELECT kokonut_security.resolve_gnosis_wallet('0x{'c' * 40}') INTO v;
    IF v <> '{WALLET_ID}'::UUID THEN RAISE EXCEPTION 'wallet resolution failed'; END IF;
    SELECT kokonut_security.resolve_gnosis_wallet_location(v) INTO v;
    IF v <> '{LOCATION_ID}'::UUID THEN RAISE EXCEPTION 'location resolution failed'; END IF;
    SELECT kokonut_security.resolve_gnosis_protocol() INTO v;
    IF v <> '{PROTOCOL_ID}'::UUID THEN RAISE EXCEPTION 'protocol resolution failed'; END IF;
    SELECT kokonut_security.claim_gnosis_event_log(
        'gnosis', '{TX_HASH}', 0, 100, '{BLOCK_HASH}', 'VoteProposal'
    ) INTO inserted;
    IF NOT inserted THEN RAISE EXCEPTION 'new receipt was not inserted'; END IF;
    SELECT kokonut_security.claim_gnosis_event_log(
        'gnosis', '{TX_HASH}', 0, 100, '{BLOCK_HASH}', 'VoteProposal'
    ) INTO inserted;
    IF inserted THEN RAISE EXCEPTION 'duplicate receipt was not suppressed'; END IF;
    BEGIN
        PERFORM kokonut_security.claim_gnosis_event_log(
            'gnosis', '{TX_HASH}', 0, 101, '0x{'d' * 64}', 'VoteProposal'
        );
        RAISE EXCEPTION 'canonical receipt mismatch was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    SELECT kokonut_security.claim_gnosis_event_log(
        'gnosis', '0x{'e' * 64}', 1, 100, '0x{'c' * 64}', 'Withdraw'
    ) INTO inserted;
    IF NOT inserted THEN RAISE EXCEPTION 'withdraw receipt was not inserted'; END IF;
    SELECT kokonut_security.store_gnosis_governance_event(
        jsonb_build_object(
            'chain','gnosis','event_type','vote_cast','tx_hash','{TX_HASH}',
            'block_number',100,'block_timestamp','2026-10-25T00:00:00Z',
            'wallet_id','{WALLET_ID}','protocol_id','{PROTOCOL_ID}',
            'metadata',jsonb_build_object('voter','0x{'c' * 40}')
        )
    ) INTO v;
    IF v IS NULL THEN RAISE EXCEPTION 'governance event was not stored'; END IF;
    SELECT kokonut_security.store_gnosis_treasury_event(
        jsonb_build_object(
            'chain','gnosis','flow_direction','outflow','tx_hash','0x{'e' * 64}',
            'block_number',100,'event_date','2026-10-25','amount',1,'token','xDAI',
            'wallet_id','{WALLET_ID}','location_id','{LOCATION_ID}',
            'metadata',jsonb_build_object('member','0x{'c' * 40}')
        )
    ) INTO v;
    IF v IS NULL THEN RAISE EXCEPTION 'treasury event was not stored'; END IF;
    SELECT kokonut_security.store_gnosis_digital_lego_usage(
        jsonb_build_object(
            'chain','gnosis','action_type','vote','tx_hash','{TX_HASH}',
            'block_number',100,'usage_date','2026-10-25','wallet_id','{WALLET_ID}',
            'protocol_id','{PROTOCOL_ID}','location_id','{LOCATION_ID}','verified',true
        )
    ) INTO v;
    IF v IS NULL THEN RAISE EXCEPTION 'digital usage was not stored'; END IF;
    SELECT kokonut_security.enqueue_gnosis_clickhouse(
        'governance:wallet_events:{TX_HASH}:vote_cast','governance_event','{TX_HASH}',
        'wallet_events','["timestamp","wallet_address","chain","tx_hash","block_number","event_type","value","token","status","metadata"]'::jsonb,
        '[["2026-10-25 00:00:00.000","0x{'c' * 40}","gnosis","{TX_HASH}",100,"vote_cast",0,"","success",{{}}]]'::jsonb,
        '{'a' * 64}'
    ) INTO outbox_id;
    IF outbox_id IS NULL THEN RAISE EXCEPTION 'outbox intent was not stored'; END IF;
    IF kokonut_security.enqueue_gnosis_clickhouse(
        'governance:wallet_events:{TX_HASH}:vote_cast','governance_event','{TX_HASH}',
        'wallet_events','["timestamp","wallet_address","chain","tx_hash","block_number","event_type","value","token","status","metadata"]'::jsonb,
        '[["2026-10-25 00:00:00.000","0x{'c' * 40}","gnosis","{TX_HASH}",100,"vote_cast",0,"","success",{{}}]]'::jsonb,
        '{'a' * 64}'
    ) <> outbox_id THEN RAISE EXCEPTION 'identical outbox retry changed identity'; END IF;
    PERFORM kokonut_security.enqueue_gnosis_clickhouse(
        'governance:wallet_events:0x{'e' * 64}:','treasury_event','0x{'e' * 64}',
        'wallet_events','["timestamp","wallet_address","chain","tx_hash","block_number","event_type","value","token","status","metadata"]'::jsonb,
        '[["2026-10-25 00:00:00.000","0x{'c' * 40}","gnosis","0x{'e' * 64}",100,"",1,"xDAI","success",{{}}]]'::jsonb,
        '{'b' * 64}'
    );
    PERFORM kokonut_security.enqueue_gnosis_clickhouse(
        'governance:dlego_events:{TX_HASH}:vote','digital_lego_usage','{TX_HASH}',
        'dlego_events','["timestamp","wallet_id","protocol_id","location_id","action_type","amount","token","chain","tx_hash","metadata"]'::jsonb,
        '[["2026-10-25 00:00:00.000","{WALLET_ID}","{PROTOCOL_ID}","{LOCATION_ID}","vote",1,"xDAI","gnosis","{TX_HASH}",{{}}]]'::jsonb,
        '{'d' * 64}'
    );
    BEGIN
        PERFORM kokonut_security.enqueue_gnosis_clickhouse(
            'governance:wallet_events:0x{'d' * 64}:vote_cast','governance_event','0x{'d' * 64}',
            'wallet_events','["timestamp","wallet_address","chain","tx_hash","block_number","event_type","value","token","status","metadata"]'::jsonb,
            '[["2026-10-25 00:00:00.000","0x{'c' * 40}","gnosis","0x{'d' * 64}",100,"vote_cast",0,"","success",{{}}]]'::jsonb,
            '{'c' * 64}'
        );
        RAISE EXCEPTION 'outbox intent without a canonical source was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.store_gnosis_governance_event(
            jsonb_build_object(
                'chain','gnosis','event_type','vote_cast','tx_hash','0x{'d' * 64}',
                'block_number',100,'block_timestamp','2026-10-25T00:00:00Z'
            )
        );
        RAISE EXCEPTION 'governance projection without a receipt was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.store_gnosis_treasury_event(
            jsonb_build_object(
                'chain','gnosis','flow_direction','outflow','tx_hash','{TX_HASH}',
                'block_number',100,'event_date','2026-10-25','amount',1,'token','xDAI'
            )
        );
        RAISE EXCEPTION 'treasury projection with a non-Withdraw receipt was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.store_gnosis_digital_lego_usage(
            jsonb_build_object(
                'chain','gnosis','action_type','swap','tx_hash','{TX_HASH}',
                'block_number',100,'usage_date','2026-10-25','protocol_id','{PROTOCOL_ID}'
            )
        );
        RAISE EXCEPTION 'dLEGO action mismatched to its receipt was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.enqueue_gnosis_clickhouse(
            'governance:wallet_events:{TX_HASH}:vote_cast','governance_event','{TX_HASH}',
            'wallet_events','["timestamp","chain"]'::jsonb,
            '[["2026-10-25 00:00:00.000","gnosis"]]'::jsonb,
            '{'e' * 64}'
        );
        RAISE EXCEPTION 'non-canonical projection shape was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.update_gnosis_indexer_status(
        100,'healthy',NULL,'{{"cursor_reviewed":true}}'::jsonb
    );
    SELECT last_synced_block INTO found_block
      FROM kokonut_security.read_gnosis_indexer_cursor();
    IF found_block <> 100 THEN RAISE EXCEPTION 'cursor update failed'; END IF;
    BEGIN
        PERFORM 1 FROM public.wallet_profile;
        RAISE EXCEPTION 'direct wallet read unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO public.governance_event(chain,event_type) VALUES ('gnosis','vote_cast');
        RAISE EXCEPTION 'direct event insert unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.claim_gnosis_event_log(
            'celo', '0x{'a' * 64}', 9, 100, '0x{'b' * 64}', 'VoteProposal'
        );
        RAISE EXCEPTION 'non-Gnosis receipt scope was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.release_gnosis_indexer_lock();
END;
$$;
RESET SESSION AUTHORIZATION;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.gnosis_event_log_receipt) <> 2
       OR (SELECT count(*) FROM public.governance_event) <> 1
       OR (SELECT count(*) FROM public.treasury_event) <> 1
       OR (SELECT count(*) FROM public.digital_lego_usage) <> 1
       OR (SELECT count(*) FROM public.clickhouse_outbox) <> 3 THEN
        RAISE EXCEPTION 'expected worker projections were not committed';
    END IF;
    IF has_any_column_privilege('kokonut_gnosis_indexer_login','public.governance_event','SELECT')
       OR has_any_column_privilege('kokonut_gnosis_indexer_login','public.clickhouse_outbox','INSERT') THEN
        RAISE EXCEPTION 'worker login has direct table privileges';
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


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable = 0
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "/var/run/postgresql", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        stable = stable + 1 if result.returncode == 0 else 0
        if stable >= 4:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    image = "postgres:16"
    container = f"kokonut-gnosis-worker-{secrets.token_hex(4)}"
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    try:
        run([docker, "run", "-d", "--rm", "--network", "none", "--name", container,
             "-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", image])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration 643 applies and replays")
        docker_sql(docker, container, ACCEPTANCE)
        checks.extend([
            "forced-RLS worker writes require matching Gnosis receipts and event mappings",
            "outbox enforces fixed wallet/dLEGO row shapes and canonical source rows",
            "receipt replay, canonical mismatch rejection, and identical outbox retry are enforced",
            "worker login has no direct relation privileges and cannot invoke an unknown function",
        ])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "migration": MIGRATION.name,
            "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
            "postgres_image": image,
            "checks": checks,
            "candidate_or_legacy_accessed": False,
            "provider_accessed": False,
            "schedule_activated": False,
        }, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "checks": checks}, indent=2))
        return 0
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
