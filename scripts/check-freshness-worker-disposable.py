#!/usr/bin/env python3
"""Replay migration 645 and exercise the isolated freshness contract on PostgreSQL 16."""

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
MIGRATION = ROOT / "schemas/postgres/645_isolated_data_freshness_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-25-recovery/freshness-worker-disposable.json"
LOCATION_ONE = "11111111-1111-4111-8111-111111111111"
LOCATION_TWO = "22222222-2222-4222-8222-222222222222"
WEATHER_CONFIG = "33333333-3333-4333-8333-333333333333"
GLOBAL_CONFIG = "44444444-4444-4444-8444-444444444444"

FIXTURE = f"""
CREATE TABLE public.location (id UUID PRIMARY KEY);
CREATE TABLE public.data_freshness_config (
    id UUID PRIMARY KEY, source_system VARCHAR(100) UNIQUE NOT NULL,
    expected_interval_minutes INTEGER NOT NULL, stale_threshold_minutes INTEGER NOT NULL,
    critical_threshold_minutes INTEGER NOT NULL, location_scoped BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE, alert_cooldown_minutes INTEGER NOT NULL DEFAULT 60,
    escalation_cooldown_minutes INTEGER NOT NULL DEFAULT 15
);
CREATE TABLE public.weather_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    observation_date TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.sensor_reading (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), sensor_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.sensor_device (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.remote_sensing_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    observation_date TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.price_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL,
    observation_date TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.attestation_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), attested_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.wallet_activity_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), block_timestamp TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.governance_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), block_timestamp TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.data_freshness_check (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), config_id UUID NOT NULL,
    source_system VARCHAR(100) NOT NULL, location_id UUID, last_data_at TIMESTAMPTZ,
    check_time TIMESTAMPTZ NOT NULL DEFAULT NOW(), gap_minutes INTEGER,
    status VARCHAR(20) NOT NULL, alert_sent BOOLEAN DEFAULT FALSE,
    alert_channel VARCHAR(50), metadata JSONB DEFAULT '{{}}'
);
CREATE TABLE public.data_freshness_alert_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_system VARCHAR(100) NOT NULL,
    location_id UUID, current_status VARCHAR(20) NOT NULL, last_event_type VARCHAR(20),
    last_event_status VARCHAR(20), last_event_at TIMESTAMPTZ, alert_count INTEGER NOT NULL DEFAULT 0,
    escalation_count INTEGER NOT NULL DEFAULT 0, recovery_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(source_system, location_id)
);
CREATE UNIQUE INDEX freshness_state_scope ON public.data_freshness_alert_state
    (source_system, COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid));
CREATE TABLE public.data_freshness_alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), state_id UUID NOT NULL,
    check_id UUID, source_system VARCHAR(100) NOT NULL, location_id UUID,
    event_type VARCHAR(20) NOT NULL, previous_status VARCHAR(20), status VARCHAR(20) NOT NULL,
    gap_minutes INTEGER, created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE public.platform_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), event_type VARCHAR(100) NOT NULL,
    source_table VARCHAR(100), source_id UUID, payload JSONB NOT NULL DEFAULT '{{}}',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal', status VARCHAR(20) NOT NULL DEFAULT 'pending',
    max_retries INTEGER NOT NULL DEFAULT 3, metadata JSONB
);
CREATE SEQUENCE public.freshness_privilege_probe;
INSERT INTO public.location VALUES ('{LOCATION_ONE}'), ('{LOCATION_TWO}');
INSERT INTO public.data_freshness_config (
    id, source_system, expected_interval_minutes, stale_threshold_minutes,
    critical_threshold_minutes, location_scoped, is_active
) VALUES
    ('{WEATHER_CONFIG}', 'weather', 30, 60, 120, TRUE, TRUE),
    ('{GLOBAL_CONFIG}', 'eas_indexer', 60, 120, 240, FALSE, TRUE);
INSERT INTO public.weather_observation (location_id, observation_date) VALUES
    ('{LOCATION_ONE}', '2026-10-25T00:00:00Z'),
    ('{LOCATION_TWO}', '2026-10-24T00:00:00Z');
INSERT INTO public.attestation_record (attested_at) VALUES ('2026-10-25T01:00:00Z');
DO $$
DECLARE relation_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'location', 'data_freshness_config', 'weather_observation', 'sensor_reading',
        'sensor_device', 'remote_sensing_observation', 'price_observation',
        'attestation_record', 'wallet_activity_event', 'governance_event',
        'data_freshness_check', 'data_freshness_alert_state',
        'data_freshness_alert_history', 'platform_event'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', relation_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', relation_name);
    END LOOP;
END;
$$;
"""

ACCEPTANCE = f"""
ALTER ROLE kokonut_freshness_login WITH LOGIN PASSWORD 'synthetic-freshness-password';
SET SESSION AUTHORIZATION kokonut_freshness_login;
DO $$
DECLARE observed TIMESTAMPTZ; check_uuid UUID; state_uuid UUID; alert_uuid UUID;
        current_state TEXT; configs INTEGER;
BEGIN
    IF session_user <> 'kokonut_freshness_login' THEN
        RAISE EXCEPTION 'freshness worker session identity was not established';
    END IF;
    SELECT count(*) INTO configs FROM kokonut_security.list_freshness_configs(NULL);
    IF configs <> 2 THEN RAISE EXCEPTION 'active source configuration list is incomplete'; END IF;
    SELECT kokonut_security.read_freshness_data_at('weather', TRUE, '{LOCATION_ONE}') INTO observed;
    IF observed <> '2026-10-25T00:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'location-scoped timestamp read returned the wrong location';
    END IF;
    SELECT kokonut_security.read_freshness_data_at('eas_indexer', FALSE, NULL) INTO observed;
    IF observed <> '2026-10-25T01:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'global source timestamp read failed';
    END IF;
    BEGIN
        PERFORM kokonut_security.read_freshness_data_at('weather', FALSE, NULL);
        RAISE EXCEPTION 'scope mismatch unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM public.weather_observation;
        RAISE EXCEPTION 'direct source-table read unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    SELECT kokonut_security.create_freshness_check(
        '{WEATHER_CONFIG}', 'weather', '{LOCATION_ONE}', observed, 61, 'stale',
        FALSE, NULL, '{{}}'::jsonb
    ) INTO check_uuid;
    SELECT state.id, state.current_status INTO state_uuid, current_state
      FROM kokonut_security.get_freshness_alert_state('weather', '{LOCATION_ONE}') AS state;
    IF current_state <> 'no_data' THEN RAISE EXCEPTION 'initial state is incorrect'; END IF;
    SELECT kokonut_security.record_freshness_alert_event(
        state_uuid, check_uuid, 'weather', '{LOCATION_ONE}', 'alert', current_state,
        'stale', 61, '2026-10-25T02:00:00Z'
    ) INTO alert_uuid;
    PERFORM kokonut_security.enqueue_freshness_event(
        alert_uuid,
        jsonb_build_object(
            'alert_id', alert_uuid, 'event_type', 'alert', 'source_system', 'weather',
            'status', 'stale', 'location_id', '{LOCATION_ONE}', 'message', 'synthetic alert'
        ),
        'normal'
    );
    PERFORM kokonut_security.update_freshness_check_alert(check_uuid, FALSE, 'event_bus');
    SELECT state.current_status INTO current_state
      FROM kokonut_security.get_freshness_alert_state('weather', '{LOCATION_ONE}') AS state;
    IF current_state <> 'stale' THEN RAISE EXCEPTION 'alert state transition was not stored'; END IF;
END;
$$;
RESET SESSION AUTHORIZATION;
DO $$
DECLARE checks INTEGER; history INTEGER; events INTEGER;
BEGIN
    SELECT count(*) INTO checks FROM public.data_freshness_check WHERE source_system='weather';
    SELECT count(*) INTO history FROM public.data_freshness_alert_history WHERE source_system='weather';
    SELECT count(*) INTO events FROM public.platform_event WHERE event_type='data_stale';
    IF checks <> 1 OR history <> 1 OR events <> 1 THEN
        RAISE EXCEPTION 'freshness check, history, and event did not commit together';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (has_table_privilege('kokonut_freshness_login', relation.oid, 'SELECT')
            OR has_table_privilege('kokonut_freshness_login', relation.oid, 'INSERT')
            OR has_table_privilege('kokonut_freshness_login', relation.oid, 'UPDATE')
            OR has_table_privilege('kokonut_freshness_login', relation.oid, 'DELETE')
            OR has_table_privilege('kokonut_freshness_login', relation.oid, 'TRUNCATE')
            OR has_any_column_privilege('kokonut_freshness_login', relation.oid, 'SELECT')
            OR has_any_column_privilege('kokonut_freshness_login', relation.oid, 'INSERT')
            OR has_any_column_privilege('kokonut_freshness_login', relation.oid, 'UPDATE'))
    ) THEN
        RAISE EXCEPTION 'freshness login has direct relation privileges';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class AS sequence
        JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
        WHERE namespace.nspname = 'public' AND sequence.relkind = 'S'
          AND (has_sequence_privilege('kokonut_freshness_login', sequence.oid, 'USAGE')
            OR has_sequence_privilege('kokonut_freshness_login', sequence.oid, 'SELECT')
            OR has_sequence_privilege('kokonut_freshness_login', sequence.oid, 'UPDATE'))
    ) THEN
        RAISE EXCEPTION 'freshness login has direct sequence privileges';
    END IF;
    IF has_schema_privilege('kokonut_freshness_login','kokonut_security','CREATE')
       OR has_schema_privilege('kokonut_freshness_login','public','CREATE') THEN
        RAISE EXCEPTION 'freshness login can create schema objects';
    END IF;
    IF NOT (
        has_function_privilege('kokonut_freshness_login', 'kokonut_security.list_freshness_configs(text)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.list_freshness_locations()', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.read_freshness_data_at(text,boolean,uuid)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.create_freshness_check(uuid,text,uuid,timestamptz,integer,text,boolean,text,jsonb)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.get_freshness_alert_state(text,uuid)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.record_freshness_alert_event(uuid,uuid,text,uuid,text,text,text,integer,timestamptz)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.update_freshness_alert_state(uuid,text,timestamptz)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.update_freshness_check_alert(uuid,boolean,text)', 'EXECUTE')
        AND has_function_privilege('kokonut_freshness_login', 'kokonut_security.enqueue_freshness_event(uuid,jsonb,text)', 'EXECUTE')
    ) THEN
        RAISE EXCEPTION 'freshness login is missing a bounded function grant';
    END IF;
    IF (
        SELECT count(*) FROM pg_proc AS procedure
        JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
        WHERE namespace.nspname IN ('public', 'kokonut_security')
          AND procedure.prosecdef
          AND has_function_privilege('kokonut_freshness_login', procedure.oid, 'EXECUTE')
    ) <> 9 THEN
        RAISE EXCEPTION 'freshness login can execute an unexpected SECURITY DEFINER function';
    END IF;
END;
$$;
DO $$
DECLARE check_count INTEGER; history_count INTEGER; event_count INTEGER;
BEGIN
    SELECT count(*) INTO check_count FROM public.data_freshness_check;
    SELECT count(*) INTO history_count FROM public.data_freshness_alert_history;
    SELECT count(*) INTO event_count FROM public.platform_event;
    IF check_count <> 1 OR history_count <> 1 OR event_count <> 1 THEN
        RAISE EXCEPTION 'pre-rollback fixture counts are wrong';
    END IF;
END;
$$;
SET SESSION AUTHORIZATION kokonut_freshness_login;
DO $$
DECLARE check_uuid UUID; state_uuid UUID; alert_uuid UUID; current_state TEXT;
BEGIN
    BEGIN
        SELECT kokonut_security.create_freshness_check(
            '{GLOBAL_CONFIG}', 'eas_indexer', NULL, '2026-10-25T01:00:00Z', 300,
            'critical', FALSE, NULL, '{{}}'::jsonb
        ) INTO check_uuid;
        SELECT state.id, state.current_status INTO state_uuid, current_state
          FROM kokonut_security.get_freshness_alert_state('eas_indexer', NULL) AS state;
        SELECT kokonut_security.record_freshness_alert_event(
            state_uuid, check_uuid, 'eas_indexer', NULL, 'alert', current_state,
            'critical', 300, '2026-10-25T03:00:00Z'
        ) INTO alert_uuid;
        PERFORM kokonut_security.enqueue_freshness_event(
            alert_uuid, jsonb_build_object('alert_id', alert_uuid, 'event_type', 'invalid'), 'high'
        );
        RAISE EXCEPTION 'invalid event was unexpectedly accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.data_freshness_check) <> 1
       OR (SELECT count(*) FROM public.data_freshness_alert_history) <> 1
       OR (SELECT count(*) FROM public.platform_event) <> 1
       OR (SELECT count(*) FROM public.data_freshness_alert_state WHERE source_system='eas_indexer') <> 0 THEN
        RAISE EXCEPTION 'failed event enqueue left a partial freshness transition';
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
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "/var/run/postgresql",
             "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-freshness-worker-{secrets.token_hex(4)}"
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    migration = MIGRATION.read_text(encoding="utf-8")
    checks: list[str] = []
    try:
        run([docker, "run", "-d", "--rm", "--network", "none", "--name", container,
             "-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", "postgres:16"])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration 645 applies and replays with forced RLS already enabled")
        docker_sql(docker, container, ACCEPTANCE)
        docker_sql(docker, container, migration)
        checks.extend([
            "location-scoped and global source timestamps return bounded values",
            "scope mismatch and direct source-table reads fail closed",
            "check, state transition, history, and notification event commit together",
            "a rejected event enqueue rolls back the enclosing check and alert transition",
            "login has no direct table/sequence/schema-create access and can execute exactly nine bounded SECURITY DEFINER functions",
            "migration 645 replays after dedicated login provisioning",
        ])
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
            subprocess.run([docker, "rm", "-f", container], text=True,
                           capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
