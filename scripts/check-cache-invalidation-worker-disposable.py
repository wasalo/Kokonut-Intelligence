#!/usr/bin/env python3
"""Verify signed EventBus cache invalidation on disposable, isolated PostgreSQL 16."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIGRATIONS = (
    "schemas/postgres/116_event_bus.sql",
    "schemas/postgres/118_computation_cache.sql",
    "schemas/postgres/405_signed_worker_tenant_context.sql",
    "schemas/postgres/415_signed_cache_invalidation_worker.sql",
    "schemas/postgres/416_sensor_harvest_cache_invalidation.sql",
)
WORKER_FIXTURE = "tests/fixtures/worker_tenant_context_disposable.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/cache-invalidation-worker-four-handlers-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
EVENT_METRIC_A = "a0000000-0000-0000-0000-000000000101"
EVENT_CRISP_A = "a0000000-0000-0000-0000-000000000102"
EVENT_METRIC_B = "a0000000-0000-0000-0000-000000000103"
EVENT_SENSOR_A = "a0000000-0000-0000-0000-000000000104"
EVENT_HARVEST_A = "a0000000-0000-0000-0000-000000000105"
RAW_CREDENTIAL = "synthetic-cache-worker-credential-for-disposable-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


def run(command: list[str], *, input_text: str | None = None, expect_success: bool = True) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if expect_success and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        safe_command = [
            "POSTGRES_PASSWORD=<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
            for item in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
    if not expect_success and result.returncode == 0:
        raise AssertionError("expected disposable SQL command to be denied")
    return result.stdout + result.stderr


def docker_sql(docker: str, container: str, statement: str, *, expect_success: bool = True) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
        expect_success=expect_success,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
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


def _context_sql(event_id: str, event_type: str, *, context_location: str = LOCATION_A) -> str:
    return f"""
BEGIN;
SET LOCAL ROLE kokonut_worker_login;
SET LOCAL ROLE kokonut_worker_execution;
DO $$
DECLARE
    established_scope RECORD;
BEGIN
    SELECT * INTO established_scope
      FROM kokonut_security.set_worker_tenant_context(
          '{CREDENTIAL_HASH}', '{context_location}'::uuid,
          'computation_cache', 'invalidate'
      );
    IF NOT FOUND THEN
        RAISE EXCEPTION 'synthetic worker scope was not established';
    END IF;
END;
$$;
DO $$
BEGIN
    PERFORM kokonut_security.invalidate_worker_computation_cache(
        '{event_id}'::uuid, '{event_type}'
    );
    RAISE EXCEPTION 'expected cache invalidation scope denial';
EXCEPTION WHEN insufficient_privilege THEN
    NULL;
END;
$$;
ROLLBACK;
"""


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("CACHE_INVALIDATION_TEST_IMAGE", "postgres:16")
    container = f"kokonut-cache-invalidation-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    migration_path = ROOT / "schemas/postgres/415_signed_cache_invalidation_worker.sql"
    extension_migration_path = ROOT / "schemas/postgres/416_sensor_harvest_cache_invalidation.sql"

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
                f"POSTGRES_PASSWORD={admin_password}",
                image,
            ]
        )
        created = True
        wait_ready(docker, container)

        docker_sql(docker, container, (ROOT / "schemas/postgres/116_event_bus.sql").read_text())
        docker_sql(docker, container, (ROOT / "schemas/postgres/118_computation_cache.sql").read_text())
        docker_sql(docker, container, (ROOT / WORKER_FIXTURE).read_text())
        docker_sql(docker, container, (ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql").read_text())
        docker_sql(
            docker,
            container,
            """
            ALTER TABLE public.platform_event ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.platform_event FORCE ROW LEVEL SECURITY;
            ALTER TABLE public.cache_entry ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.cache_entry FORCE ROW LEVEL SECURITY;
            """,
        )
        migration_sql = migration_path.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        extension_migration_sql = extension_migration_path.read_text(encoding="utf-8")
        docker_sql(docker, container, extension_migration_sql)
        docker_sql(docker, container, extension_migration_sql)
        checks.append("migrations 415 and 416 apply and replay after the signed worker-context migration")

        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'cache-invalidation');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}',
                'computation_cache', 'invalidate', 'disposable fixture'
            );
            INSERT INTO public.platform_event (id, event_type, payload) VALUES
                ('{EVENT_METRIC_A}', 'metric_computed', '{{"location_id":"{LOCATION_A}"}}'),
                ('{EVENT_CRISP_A}', 'crisp_scored', '{{"location_id":"{LOCATION_A}"}}'),
                ('{EVENT_METRIC_B}', 'metric_computed', '{{"location_id":"{LOCATION_B}"}}'),
                ('{EVENT_SENSOR_A}', 'sensor_reading', '{{"location_id":"{LOCATION_A}"}}'),
                ('{EVENT_HARVEST_A}', 'harvest_recorded', '{{"location_id":"{LOCATION_A}"}}');
            INSERT INTO public.cache_entry
                (cache_key, computation_type, location_id, result, expires_at)
            VALUES
                ('analytics-a', 'analytics', '{LOCATION_A}', '{{}}', NOW() + INTERVAL '1 day'),
                ('crisp-a', 'crisp', '{LOCATION_A}', '{{}}', NOW() + INTERVAL '1 day'),
                ('analytics-b', 'analytics', '{LOCATION_B}', '{{}}', NOW() + INTERVAL '1 day'),
                ('metric-a', 'metric', '{LOCATION_A}', '{{}}', NOW() + INTERVAL '1 day'),
                ('metric-sensor-a', 'metric', '{LOCATION_A}', '{{}}', NOW() + INTERVAL '1 day'),
                ('metric-harvest-a', 'metric', '{LOCATION_A}', '{{}}', NOW() + INTERVAL '1 day'),
                ('metric-b', 'metric', '{LOCATION_B}', '{{}}', NOW() + INTERVAL '1 day');
            """,
        )

        effect_result = docker_sql(
            docker,
            container,
            f"""
            BEGIN;
            SET LOCAL ROLE kokonut_worker_login;
            SET LOCAL ROLE kokonut_worker_execution;
            SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
              FROM kokonut_security.set_worker_tenant_context(
                  '{CREDENTIAL_HASH}', '{LOCATION_A}'::uuid,
                  'computation_cache', 'invalidate'
              );
            SELECT kokonut_security.invalidate_worker_computation_cache(
                '{EVENT_METRIC_A}'::uuid, 'metric_computed'
            );
            SELECT kokonut_security.invalidate_worker_computation_cache(
                '{EVENT_METRIC_A}'::uuid, 'metric_computed'
            );
            SELECT kokonut_security.invalidate_worker_computation_cache(
                '{EVENT_CRISP_A}'::uuid, 'crisp_scored'
            );
            RESET ROLE;
            UPDATE public.cache_entry SET is_valid = TRUE WHERE cache_key = 'metric-harvest-a';
            SET LOCAL ROLE kokonut_worker_login;
            SET LOCAL ROLE kokonut_worker_execution;
            SELECT kokonut_security.invalidate_worker_computation_cache(
                '{EVENT_SENSOR_A}'::uuid, 'sensor_reading'
            );
            RESET ROLE;
            UPDATE public.cache_entry SET is_valid = TRUE WHERE cache_key = 'metric-harvest-a';
            SET LOCAL ROLE kokonut_worker_login;
            SET LOCAL ROLE kokonut_worker_execution;
            SELECT kokonut_security.invalidate_worker_computation_cache(
                '{EVENT_HARVEST_A}'::uuid, 'harvest_recorded'
            );
            RESET ROLE;
            SELECT string_agg(cache_key || '=' || is_valid::text, ',' ORDER BY cache_key)
              FROM public.cache_entry;
            COMMIT;
            """,
        ).splitlines()
        if effect_result != [
            f"{TENANT_ID}|{LOCATION_A}|{WORKER_ID}|system_worker",
            "1",
            "0",
            "1",
            "3",
            "1",
            "analytics-a=false,analytics-b=true,crisp-a=false,metric-a=false,metric-b=true,metric-harvest-a=false,metric-sensor-a=false",
        ]:
            raise AssertionError(f"signed cache type/location mapping differed: {effect_result}")
        checks.append("all four event types invalidate only their mapped cache type at the signed location")
        checks.append("same-event retry returns zero additional invalidations and preserves idempotent cache state")

        for event_id, requested_type, event_location in (
            (EVENT_CRISP_A, "metric_computed", LOCATION_A),
            (EVENT_METRIC_B, "metric_computed", LOCATION_A),
        ):
            denied = docker_sql(
                docker,
                container,
                _context_sql(event_id, requested_type, context_location=event_location),
            )
            if denied.strip():
                raise AssertionError(f"expected handled scope denial to be quiet: {denied}")
        checks.append("wrong event type and mismatched event location are rejected under signed context")

        boundary = docker_sql(
            docker,
            container,
            """
            SELECT has_function_privilege(
                       'kokonut_worker_execution',
                       'kokonut_security.invalidate_worker_computation_cache(uuid,text)',
                       'EXECUTE'
                   )::text,
                   (NOT has_table_privilege('kokonut_worker_execution', 'public.cache_entry', 'SELECT'))::text,
                   (NOT has_table_privilege('kokonut_worker_execution', 'public.platform_event', 'SELECT'))::text,
                   count(*) FILTER (WHERE schemaname = 'public' AND tablename = 'platform_event'
                                     AND policyname = 'cache_invalidation_owner_event_select'),
                   count(*) FILTER (WHERE schemaname = 'public' AND tablename = 'cache_entry'
                                     AND policyname IN ('cache_invalidation_owner_select',
                                                        'cache_invalidation_owner_update'))
              FROM pg_policies;
            """,
        ).strip()
        if boundary != "true|true|true|1|2":
            raise AssertionError(f"worker role or forced-RLS policies differ from contract: {boundary}")
        checks.append("forced-RLS policies scope the function owner while execution role has no direct table reads")

        registrations = docker_sql(
            docker,
            container,
            """
            SELECT string_agg(handler_name || '|' || event_type || '|' || module_path || '|' || function_name,
                              ',' ORDER BY handler_name)
              FROM public.event_handler
             WHERE handler_name IN ('sensor_cache_invalidator', 'harvest_cache_invalidator');
            """,
        ).strip()
        if registrations != (
            "harvest_cache_invalidator|harvest_recorded|services.cache.events|handle_harvest_recorded,"
            "sensor_cache_invalidator|sensor_reading|services.cache.events|handle_sensor_reading"
        ):
            raise AssertionError(f"new cache event handler registrations differ from contract: {registrations}")
        checks.append("migration 416 registers the existing sensor and harvest cache handlers")

        for table in ("cache_entry", "platform_event"):
            denial = docker_sql(
                docker,
                container,
                f"SET ROLE kokonut_worker_login; SET ROLE kokonut_worker_execution; SELECT * FROM public.{table} LIMIT 0;",
                expect_success=False,
            )
            if f"permission denied for table {table}" not in denial:
                raise AssertionError(f"unexpected direct {table} denial result: {denial}")
        checks.append("worker execution is denied direct reads of cache and event tables")

        rls_state = docker_sql(
            docker,
            container,
            """
            SELECT bool_and(relrowsecurity AND relforcerowsecurity)::text
              FROM pg_class
             WHERE oid IN ('public.cache_entry'::regclass, 'public.platform_event'::regclass);
            """,
        ).strip()
        if rls_state != "true":
            raise AssertionError("forced RLS was not retained on both synthetic tables")
        checks.append("both synthetic tables remain FORCE ROW LEVEL SECURITY during bounded execution")

        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Signed EventBus cache invalidation",
            "database": "isolated disposable PostgreSQL 16 container with --network none",
            "migration_415_sha256": hashlib.sha256(migration_path.read_bytes()).hexdigest(),
            "migration_416_sha256": hashlib.sha256(extension_migration_path.read_bytes()).hexdigest(),
            "migrations": [*MIGRATIONS],
            "result": "passed",
            "checks": [{"result": "passed", "description": item} for item in checks],
            "candidate_or_legacy_database_access": False,
            "network": "disabled for the disposable database container",
            "raw_worker_credential_printed": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
