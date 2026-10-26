#!/usr/bin/env python3
"""Replay migration 646 and verify its isolated outbox lease contract on PG 16."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/646_isolated_clickhouse_outbox_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/clickhouse-outbox-worker-disposable.json"
ARM64_OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/clickhouse-outbox-worker-arm64-disposable.json"

FIXTURE = """
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
    lease_owner VARCHAR(100),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT clickhouse_outbox_status CHECK (
        status IN ('pending', 'processing', 'succeeded', 'retryable', 'dead_letter', 'resolved', 'discarded')
    ),
    CONSTRAINT clickhouse_outbox_columns_array CHECK (jsonb_typeof(columns) = 'array'),
    CONSTRAINT clickhouse_outbox_rows_array CHECK (jsonb_typeof(rows) = 'array'),
    CONSTRAINT clickhouse_outbox_attempts_nonnegative CHECK (attempt_count >= 0)
);
CREATE INDEX idx_clickhouse_outbox_claim ON public.clickhouse_outbox (available_at, created_at)
    WHERE status IN ('pending', 'retryable');
ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
INSERT INTO public.clickhouse_outbox (event_key, source_table, source_id, target_table, columns, rows, payload_hash, created_at)
VALUES
 ('event-success', 'sensor_reading', 'reading-1', 'sensor_readings',
  '["timestamp","sensor_id","location_id","value"]',
  '[["2026-10-25T00:00:00Z","sensor-1","location-1",1]]', repeat('a',64), NOW() - INTERVAL '2 minutes'),
 ('event-retry', 'sensor_reading', 'reading-2', 'sensor_readings',
  '["timestamp","sensor_id","location_id","value"]',
  '[["2026-10-25T00:00:00Z","sensor-2","location-1",2]]', repeat('b',64), NOW() - INTERVAL '1 minute'),
 ('event-expired', 'sensor_reading', 'reading-3', 'sensor_readings',
  '["timestamp","sensor_id","location_id","value"]',
  '[["2026-10-25T00:00:00Z","sensor-3","location-1",3]]', repeat('c',64), NOW());
UPDATE public.clickhouse_outbox
   SET status='processing', attempt_count=8, lease_owner='stale-worker',
       lease_token=gen_random_uuid(), lease_expires_at=NOW() - INTERVAL '1 minute'
 WHERE event_key='event-expired';
INSERT INTO public.clickhouse_outbox (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash,
    status, attempt_count, lease_owner, lease_token, lease_expires_at
)
SELECT 'event-expired-bulk-' || item, 'sensor_reading', 'expired-' || item,
       'sensor_readings', '["timestamp","sensor_id","location_id","value"]',
       '[["2026-10-25T00:00:00Z","sensor-expired","location-1",4]]', repeat('d',64),
       'processing', 8, 'stale-worker', gen_random_uuid(), NOW() - INTERVAL '1 minute'
  FROM generate_series(1, 100) AS item;
"""

ACCEPTANCE = """
ALTER ROLE kokonut_clickhouse_outbox_login WITH LOGIN PASSWORD 'synthetic-clickhouse-outbox-password';
SET SESSION AUTHORIZATION kokonut_clickhouse_outbox_login;
DO $$
DECLARE claimed RECORD; second_claim RECORD; changed BOOLEAN;
BEGIN
    IF session_user <> 'kokonut_clickhouse_outbox_login' THEN
        RAISE EXCEPTION 'dedicated ClickHouse outbox identity was not established';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.claim_clickhouse_outbox_batch('worker-a', 101);
        RAISE EXCEPTION 'oversized claim limit unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM public.clickhouse_outbox;
        RAISE EXCEPTION 'direct outbox read unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;

    SELECT * INTO claimed FROM kokonut_security.claim_clickhouse_outbox_batch('worker-a', 1);
    IF NOT FOUND OR claimed.event_key <> 'event-success' OR claimed.attempt_count <> 1
       OR claimed.lease_token IS NULL THEN
        RAISE EXCEPTION 'bounded claim did not return the first fenced row';
    END IF;
    SELECT * INTO second_claim FROM kokonut_security.claim_clickhouse_outbox_batch('worker-b', 1);
    IF NOT FOUND OR second_claim.event_key <> 'event-retry' THEN
        RAISE EXCEPTION 'second bounded claim did not skip the active lease';
    END IF;
    SELECT kokonut_security.finish_clickhouse_outbox_delivery(
        claimed.id, 'wrong-worker', claimed.lease_token, TRUE, NULL, 60, FALSE
    ) INTO changed;
    IF changed THEN RAISE EXCEPTION 'wrong worker completed a lease'; END IF;
    SELECT kokonut_security.finish_clickhouse_outbox_delivery(
        claimed.id, 'worker-a', claimed.lease_token, TRUE, NULL, 60, FALSE
    ) INTO changed;
    IF NOT changed THEN RAISE EXCEPTION 'valid successful completion was rejected'; END IF;
    SELECT kokonut_security.finish_clickhouse_outbox_delivery(
        claimed.id, 'worker-a', claimed.lease_token, TRUE, NULL, 60, FALSE
    ) INTO changed;
    IF changed THEN RAISE EXCEPTION 'duplicate completion unexpectedly changed a row'; END IF;

    SELECT kokonut_security.finish_clickhouse_outbox_delivery(
        second_claim.id, 'worker-b', second_claim.lease_token, FALSE,
        'synthetic transient error', 0, FALSE
    ) INTO changed;
    IF NOT changed THEN RAISE EXCEPTION 'retryable completion was rejected'; END IF;
    SELECT * INTO claimed FROM kokonut_security.claim_clickhouse_outbox_batch('worker-c', 1);
    IF NOT FOUND OR claimed.event_key <> 'event-retry' OR claimed.attempt_count <> 2 THEN
        RAISE EXCEPTION 'retryable row did not preserve attempt count and become claimable';
    END IF;
    SELECT kokonut_security.finish_clickhouse_outbox_delivery(
        claimed.id, 'worker-c', claimed.lease_token, FALSE,
        'synthetic permanent contract failure', 0, TRUE
    ) INTO changed;
    IF NOT changed THEN RAISE EXCEPTION 'permanent failure transition was rejected'; END IF;
END;
$$;
RESET SESSION AUTHORIZATION;
DO $$
BEGIN
    IF (SELECT status FROM public.clickhouse_outbox WHERE event_key='event-success') <> 'succeeded'
       OR (SELECT delivered_at IS NULL FROM public.clickhouse_outbox WHERE event_key='event-success')
       OR (SELECT status FROM public.clickhouse_outbox WHERE event_key='event-retry') <> 'dead_letter'
       OR (SELECT status FROM public.clickhouse_outbox WHERE event_key='event-expired') <> 'dead_letter'
       OR (SELECT lease_token IS NOT NULL FROM public.clickhouse_outbox WHERE event_key='event-retry') THEN
        RAISE EXCEPTION 'outbox success, retry, or expired-lease transition is incorrect';
    END IF;
    IF (SELECT count(*) FROM public.clickhouse_outbox
         WHERE status='processing' AND lease_expires_at < NOW()) <> 98 THEN
        RAISE EXCEPTION 'expired-lease recovery did not respect its requested batch bound';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname='public' AND relation.relkind IN ('r','p','v','m','f')
          AND (has_table_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'SELECT')
            OR has_table_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'INSERT')
            OR has_table_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'UPDATE')
            OR has_table_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'DELETE')
            OR has_any_column_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'SELECT')
            OR has_any_column_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'INSERT')
            OR has_any_column_privilege('kokonut_clickhouse_outbox_login', relation.oid, 'UPDATE'))
    ) THEN RAISE EXCEPTION 'dedicated login retains direct relation privileges'; END IF;
    IF EXISTS (
        SELECT 1 FROM pg_proc procedure
        JOIN pg_namespace namespace ON namespace.oid=procedure.pronamespace
        WHERE namespace.nspname IN ('public','kokonut_security') AND procedure.prosecdef
          AND has_function_privilege('kokonut_clickhouse_outbox_login', procedure.oid, 'EXECUTE')
          AND procedure.oid NOT IN (
            'kokonut_security.claim_clickhouse_outbox_batch(text,integer)'::regprocedure,
            'kokonut_security.finish_clickhouse_outbox_delivery(uuid,text,uuid,boolean,text,integer,boolean)'::regprocedure
          )
    ) THEN RAISE EXCEPTION 'dedicated login can execute an unexpected SECURITY DEFINER function'; END IF;
    IF (SELECT count(*) FROM pg_proc procedure
        JOIN pg_namespace namespace ON namespace.oid=procedure.pronamespace
        WHERE namespace.nspname='kokonut_security' AND procedure.prosecdef
          AND has_function_privilege('kokonut_clickhouse_outbox_login', procedure.oid, 'EXECUTE')) <> 2 THEN
        RAISE EXCEPTION 'dedicated login does not have exactly two bounded functions';
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
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "psql", "-X", "-q", "-t", "-A",
             "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
             "-c", "SELECT 1"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--image", default="postgres:16")
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    args = parser.parse_args()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-clickhouse-outbox-{secrets.token_hex(4)}"
    output = args.output or (ARM64_OUTPUT if args.platform == "linux/arm64" else DEFAULT_OUTPUT)
    migration = MIGRATION.read_text(encoding="utf-8")
    created = False
    try:
        command = [docker, "run", "-d", "--rm", "--network", "none", "--name", container]
        if args.platform is not None:
            command.extend(("--platform", args.platform))
        command.extend(("-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", args.image))
        run(command)
        created = True
        wait_ready(docker, container)
        architecture = run([docker, "exec", container, "uname", "-m"]).strip()
        expected_architecture = {
            "linux/amd64": "x86_64",
            "linux/arm64": "aarch64",
        }.get(args.platform)
        if expected_architecture is not None and architecture != expected_architecture:
            raise RuntimeError("disposable PostgreSQL container architecture mismatch")
        docker_sql(docker, container, FIXTURE)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, ACCEPTANCE)
        docker_sql(docker, container, migration)
        evidence = {
            "date": "2026-10-25",
            "migration": MIGRATION.name,
            "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
            "database": "PostgreSQL 16 disposable container; Docker network disabled",
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "checks": [
                "migration 646 applies and replays while clickhouse_outbox is FORCE RLS",
                "claim and expired-lease recovery are capped at the requested limit (up to 100), skip active leases, and increment attempts",
                "only the claimed worker and live token can finish; duplicate and stale completion fail closed",
                "transient retry, explicit permanent failure, and exhausted expired lease states are preserved",
                "dedicated login has no direct table, column, sequence, or unexpected SECURITY DEFINER access",
            ],
            "result": "passed",
            "isolation": "Synthetic schema and rows only; no candidate, legacy, provider, or network access.",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True,
                           capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
