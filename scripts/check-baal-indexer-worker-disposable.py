#!/usr/bin/env python3
"""Replay migration 644 and test its bounded Baal-worker contract on PostgreSQL 16."""

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
MIGRATION = ROOT / "schemas/postgres/644_isolated_baal_indexer.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/baal-indexer-worker-disposable.json"
WALLET_ID = "11111111-1111-4111-8111-111111111111"
PROTOCOL_ID = "22222222-2222-4222-8222-222222222222"
TX_HASH = "0x" + "a" * 64

FIXTURE = f"""
CREATE TABLE public.wallet_profile (
    id UUID PRIMARY KEY, address VARCHAR(42) NOT NULL, chain VARCHAR(50) NOT NULL
);
CREATE TABLE public.protocol (
    id UUID PRIMARY KEY, slug VARCHAR(255) UNIQUE NOT NULL
);
CREATE TABLE public.chain_indexer_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), chain VARCHAR(50) NOT NULL,
    indexer_type VARCHAR(50) NOT NULL, last_synced_block BIGINT,
    last_synced_at TIMESTAMPTZ, status VARCHAR(50), error_message TEXT,
    metadata JSONB DEFAULT '{{}}', updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chain, indexer_type)
);
CREATE TABLE public.governance_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), wallet_id UUID REFERENCES wallet_profile(id),
    protocol_id UUID REFERENCES protocol(id), chain VARCHAR(50) NOT NULL,
    event_type VARCHAR(100), proposal_id VARCHAR(255), proposal_title TEXT,
    vote_choice VARCHAR(50), amount NUMERIC(18,8), token VARCHAR(50),
    tx_hash VARCHAR(66), block_number BIGINT, block_timestamp TIMESTAMPTZ,
    metadata JSONB DEFAULT '{{}}'
);
CREATE UNIQUE INDEX uq_governance_event_baal_source
    ON public.governance_event (chain, event_type, tx_hash);
INSERT INTO public.wallet_profile VALUES ('{WALLET_ID}', '0x{'c' * 40}', 'gnosis');
INSERT INTO public.protocol VALUES ('{PROTOCOL_ID}', 'kokonut-treasury');
"""

ACCEPTANCE = f"""
ALTER TABLE public.wallet_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_profile FORCE ROW LEVEL SECURITY;
ALTER TABLE public.protocol ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.protocol FORCE ROW LEVEL SECURITY;
ALTER TABLE public.chain_indexer_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_indexer_status FORCE ROW LEVEL SECURITY;
ALTER TABLE public.governance_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.governance_event FORCE ROW LEVEL SECURITY;
ALTER ROLE kokonut_baal_indexer_login WITH LOGIN PASSWORD 'synthetic-baal-password';
SET SESSION AUTHORIZATION kokonut_baal_indexer_login;
DO $$
DECLARE resolved UUID; inserted BOOLEAN; block_cursor BIGINT;
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login' THEN
        RAISE EXCEPTION 'worker login identity was not established';
    END IF;
    PERFORM kokonut_security.acquire_baal_indexer_lock();
    IF EXISTS (SELECT 1 FROM kokonut_security.read_baal_indexer_cursor()) THEN
        RAISE EXCEPTION 'new Baal cursor unexpectedly exists';
    END IF;
    SELECT kokonut_security.resolve_baal_wallet('0x{'c' * 40}') INTO resolved;
    IF resolved <> '{WALLET_ID}'::UUID THEN RAISE EXCEPTION 'wallet lookup failed'; END IF;
    SELECT kokonut_security.resolve_baal_protocol() INTO resolved;
    IF resolved <> '{PROTOCOL_ID}'::UUID THEN RAISE EXCEPTION 'protocol lookup failed'; END IF;
    SELECT kokonut_security.store_baal_governance_event(jsonb_build_object(
        'chain','gnosis','event_type','vote_cast','tx_hash','{TX_HASH}',
        'block_number',100,'block_timestamp','2026-10-25T00:00:00Z',
        'wallet_id','{WALLET_ID}','protocol_id','{PROTOCOL_ID}',
        'proposal_id','3','vote_choice','yes','metadata',jsonb_build_object('member','0x{'c' * 40}')
    )) INTO inserted;
    IF inserted IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'event insert failed'; END IF;
    SELECT kokonut_security.store_baal_governance_event(jsonb_build_object(
        'chain','gnosis','event_type','vote_cast','tx_hash','{TX_HASH}',
        'block_number',100,'block_timestamp','2026-10-25T00:00:00Z',
        'wallet_id','{WALLET_ID}','protocol_id','{PROTOCOL_ID}',
        'proposal_id','3','vote_choice','yes','metadata',jsonb_build_object('member','0x{'c' * 40}')
    )) INTO inserted;
    IF inserted IS DISTINCT FROM FALSE THEN RAISE EXCEPTION 'duplicate event was not suppressed'; END IF;
    PERFORM kokonut_security.update_baal_indexer_status(100,'healthy',NULL);
    SELECT last_synced_block INTO block_cursor
      FROM kokonut_security.read_baal_indexer_cursor();
    IF block_cursor <> 100 THEN RAISE EXCEPTION 'cursor update failed'; END IF;
    BEGIN
        PERFORM 1 FROM public.wallet_profile;
        RAISE EXCEPTION 'direct wallet read unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO public.governance_event(chain,event_type) VALUES ('gnosis','vote_cast');
        RAISE EXCEPTION 'direct governance-event insert unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.store_baal_governance_event(jsonb_build_object(
            'chain','celo','event_type','vote_cast','tx_hash','0x{'d' * 64}',
            'block_number',101,'block_timestamp','2026-10-25T00:00:00Z'
        ));
        RAISE EXCEPTION 'non-Gnosis event was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.store_baal_governance_event(jsonb_build_object(
            'chain','gnosis','event_type','unknown_event','tx_hash','0x{'e' * 64}',
            'block_number',101,'block_timestamp','2026-10-25T00:00:00Z'
        ));
        RAISE EXCEPTION 'unknown event type was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.release_baal_indexer_lock();
END;
$$;
RESET SESSION AUTHORIZATION;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.governance_event) <> 1 THEN
        RAISE EXCEPTION 'expected one canonical Baal event';
    END IF;
    IF has_any_column_privilege('kokonut_baal_indexer_login','public.wallet_profile','SELECT')
       OR has_any_column_privilege('kokonut_baal_indexer_login','public.governance_event','INSERT') THEN
        RAISE EXCEPTION 'Baal login has direct relation privileges';
    END IF;
    IF has_schema_privilege('kokonut_baal_indexer_login','kokonut_security','CREATE')
       OR has_schema_privilege('kokonut_baal_indexer_login','public','CREATE') THEN
        RAISE EXCEPTION 'Baal login can create schema objects';
    END IF;
    IF NOT (
        has_function_privilege('kokonut_baal_indexer_login','kokonut_security.acquire_baal_indexer_lock()','EXECUTE')
        AND has_function_privilege('kokonut_baal_indexer_login','kokonut_security.release_baal_indexer_lock()','EXECUTE')
        AND has_function_privilege('kokonut_baal_indexer_login','kokonut_security.read_baal_indexer_cursor()','EXECUTE')
        AND has_function_privilege('kokonut_baal_indexer_login','kokonut_security.resolve_baal_protocol()','EXECUTE')
        AND has_function_privilege('kokonut_baal_indexer_login','kokonut_security.resolve_baal_wallet(text)','EXECUTE')
        AND has_function_privilege('kokonut_baal_indexer_login','kokonut_security.store_baal_governance_event(jsonb)','EXECUTE')
        AND has_function_privilege('kokonut_baal_indexer_login','kokonut_security.update_baal_indexer_status(bigint,text,text)','EXECUTE')
    ) THEN RAISE EXCEPTION 'Baal login is missing a bounded worker function'; END IF;
    IF EXISTS (
        SELECT 1 FROM pg_proc AS procedure
        JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
        WHERE namespace.nspname IN ('public','kokonut_security')
          AND procedure.prosecdef
          AND procedure.oid <> ALL(ARRAY[
              'kokonut_security.acquire_baal_indexer_lock()'::regprocedure,
              'kokonut_security.release_baal_indexer_lock()'::regprocedure,
              'kokonut_security.read_baal_indexer_cursor()'::regprocedure,
              'kokonut_security.resolve_baal_protocol()'::regprocedure,
              'kokonut_security.resolve_baal_wallet(text)'::regprocedure,
              'kokonut_security.store_baal_governance_event(jsonb)'::regprocedure,
              'kokonut_security.update_baal_indexer_status(bigint,text,text)'::regprocedure
          ])
          AND has_function_privilege('kokonut_baal_indexer_login', procedure.oid, 'EXECUTE')
    ) THEN RAISE EXCEPTION 'Baal login can execute another SECURITY DEFINER function'; END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relkind = 'S'
          AND (has_sequence_privilege('kokonut_baal_indexer_login', relation.oid, 'USAGE')
            OR has_sequence_privilege('kokonut_baal_indexer_login', relation.oid, 'SELECT')
            OR has_sequence_privilege('kokonut_baal_indexer_login', relation.oid, 'UPDATE'))
    ) THEN RAISE EXCEPTION 'Baal login has sequence privileges'; END IF;
END;
$$;
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                docker,
                "exec",
                container,
                "pg_isready",
                "-h",
                "/var/run/postgresql",
                "-U",
                "postgres",
                "-d",
                "postgres",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-baal-worker-{secrets.token_hex(4)}"
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    migration = MIGRATION.read_text(encoding="utf-8")
    checks: list[str] = []
    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--network",
                "none",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
                "postgres:16",
            ]
        )
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration 644 applies and replays before login provisioning")
        docker_sql(docker, container, ACCEPTANCE)
        docker_sql(docker, container, migration)
        checks.extend(
            [
                "migration 644 replays after the dedicated login is provisioned",
                "forced-RLS contract resolves only the Gnosis wallet and canonical Baal protocol",
                "bounded event insert is idempotent and status advances the dedicated cursor",
                "unknown event types and non-Gnosis records fail closed",
                "login has no direct relation or sequence privileges",
            ]
        )
        evidence = {
            "date": "2026-10-25",
            "migration": MIGRATION.name,
            "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
            "database": "PostgreSQL 16 disposable container; Docker network disabled",
            "checks": checks,
            "result": "passed",
            "isolation": "Synthetic schema and records only; no candidate, legacy, provider, or network access.",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
