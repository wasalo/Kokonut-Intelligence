#!/usr/bin/env python3
"""Exercise migration 427 using disposable PostgreSQL 16 only."""

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

import psycopg2
from psycopg2 import errors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# This acceptance supplies every credential directly and must not decrypt the
# repository's unrelated encrypted development environment during imports.
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")
FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_FORECAST = ROOT / "tests/fixtures/weather_forecast_worker_disposable.sql"
FIXTURE_WEATHER = ROOT / "tests/fixtures/weather_observation_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_PRIVATE_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION_FORECAST = ROOT / "schemas/postgres/426_signed_weather_forecast_worker.sql"
MIGRATION_WEATHER = ROOT / "schemas/postgres/427_signed_weather_observation_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-17-recovery/weather-observation-worker-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000902"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
RAW_CREDENTIAL = "synthetic-current-weather-worker-credential-over-32-bytes"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable = 0
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        stable = stable + 1 if ready.returncode == 0 else 0
        if stable >= 4:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def weather_record(location_id: str = LOCATION_A) -> dict:
    return {
        "location_id": location_id,
        "observation_date": "2026-10-17",
        "observation_time": "12:30:00+00:00",
        "source": "openweathermap",
        "temperature_c": 24.5,
        "humidity_pct": 70,
        "precipitation_mm": 0,
        "wind_speed_kmh": 4.0,
        "wind_direction_deg": 90,
        "pressure_hpa": 1012,
        "visibility_km": 10,
        "cloud_cover_pct": 15,
        "metadata": json.dumps({"weather_main": "Clear"}),
    }


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-weather-observation-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("WEATHER_WORKER_TEST_IMAGE", "postgres:16")
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    env_names = (
        "KOKONUT_WEATHER_DATABASE_URL",
        "KOKONUT_WEATHER_WORKER_CREDENTIAL",
        "KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY",
        "KOKONUT_FEATURE_SIGNED_WEATHER_WORKER",
    )
    previous = {name: os.environ.get(name) for name in env_names}
    created = False
    admin = None
    worker = None
    checks: list[str] = []
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={admin_password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_FORECAST.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_WEATHER.read_text(encoding="utf-8"))
        for migration in (MIGRATION_CONTEXT, MIGRATION_PRIVATE_ACL, MIGRATION_FORECAST):
            docker_sql(docker, container, migration.read_text(encoding="utf-8"))
        migration_sql = MIGRATION_WEATHER.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migrations 405, 419, 426, and 427 apply in order; migration 427 replays cleanly")

        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'weather-observation-disposable');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}',
                'weather_observation', 'ingest', 'disposable fixture'
            );
            """,
        )
        port_output = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_output:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_output[0].rsplit(":", 1)[1])
        os.environ["KOKONUT_WEATHER_DATABASE_URL"] = (
            f"postgresql://kokonut_worker_login:worker-execution-fixture@127.0.0.1:{port}/postgres"
        )
        os.environ["KOKONUT_WEATHER_WORKER_CREDENTIAL"] = RAW_CREDENTIAL
        os.environ["KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY"] = "synthetic-provider-key-not-used"
        os.environ["KOKONUT_FEATURE_SIGNED_WEATHER_WORKER"] = "false"
        admin = connect(port, "postgres", admin_password)

        from services.common.tenant_context import TenantContextDenied, set_worker_tenant_context
        from services.common.worker_database import get_worker_db
        from services.ingestion.weather import build_weather_clickhouse_projection
        from services.ingestion.weather_worker import _load_location, _store_observation

        worker = get_worker_db("weather")
        if _load_location(LOCATION_A, RAW_CREDENTIAL) != (18.5, -69.9):
            raise AssertionError("signed location lookup returned unexpected coordinates")
        checks.append("signed location function returns only granted active-location coordinates")

        record = weather_record()
        projection = build_weather_clickhouse_projection([record])
        with admin.cursor() as cursor:
            cursor.execute(
                """INSERT INTO public.clickhouse_outbox (
                       event_key, source_table, source_id, target_table,
                       columns, rows, payload_hash
                   ) VALUES (%s, 'weather_observation', %s, 'weather_events',
                             %s::jsonb, %s::jsonb, %s)""",
                (
                    f"weather:weather_events:{projection['payload_hash']}",
                    projection["payload_hash"],
                    json.dumps(projection["columns"]),
                    json.dumps(projection["rows"], default=str),
                    projection["payload_hash"],
                ),
            )
        admin.commit()
        first = _store_observation(
            LOCATION_A, RAW_CREDENTIAL, record=record, projection=projection,
            provider_source_id="7", provider_payload_hash="b" * 64,
            processing_time_ms=23,
        )
        replay = _store_observation(
            LOCATION_A, RAW_CREDENTIAL, record=record, projection=projection,
            provider_source_id="7", provider_payload_hash="b" * 64,
            processing_time_ms=25,
        )
        if not first[0] or first[1] is not True or replay != (first[0], False):
            raise AssertionError("current-weather retry did not return its original receipt")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.weather_observation WHERE location_id = %s::uuid", (LOCATION_A,))
            observations = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox WHERE source_table = 'weather_observation'")
            outbox_rows = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.ingestion_log WHERE source_table = 'weather_api' AND status = 'success'")
            audit_rows = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM kokonut_security.weather_observation_worker_receipt")
            receipts = cursor.fetchone()[0]
        admin.commit()
        if (observations, outbox_rows, audit_rows, receipts) != (1, 1, 1, 1):
            raise AssertionError("replayed response duplicated a canonical or projection effect")
        checks.append("observation/audit/receipt commit once and an identical legacy projection intent is reused")

        conflicting_projection = {
            **projection,
            "payload_hash": "e" * 64,
        }
        with admin.cursor() as cursor:
            cursor.execute(
                """INSERT INTO public.clickhouse_outbox (
                       event_key, source_table, source_id, target_table,
                       columns, rows, payload_hash
                   ) VALUES (%s, 'weather_observation', %s, 'weather_events',
                             %s::jsonb, '[]'::jsonb, %s)""",
                (
                    f"weather:weather_events:{conflicting_projection['payload_hash']}",
                    conflicting_projection["payload_hash"],
                    json.dumps(conflicting_projection["columns"]),
                    conflicting_projection["payload_hash"],
                ),
            )
        admin.commit()
        try:
            _store_observation(
                LOCATION_A, RAW_CREDENTIAL, record=record,
                projection=conflicting_projection, provider_source_id="7",
                provider_payload_hash="f" * 64, processing_time_ms=1,
            )
            raise AssertionError("conflicting current-weather outbox identity was reused")
        except psycopg2.Error:
            pass
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.weather_observation WHERE location_id = %s::uuid", (LOCATION_A,))
            if cursor.fetchone()[0] != 1:
                raise AssertionError("outbox collision left a partial canonical weather row")
            cursor.execute(
                "SELECT count(*) FROM kokonut_security.weather_observation_worker_receipt "
                "WHERE provider_payload_hash = %s",
                ("f" * 64,),
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("outbox collision left an idempotency receipt")
        admin.commit()
        checks.append("conflicting outbox identity aborts the whole weather/audit/receipt transaction")

        try:
            _store_observation(
                LOCATION_B, RAW_CREDENTIAL, record=weather_record(LOCATION_B),
                projection=build_weather_clickhouse_projection([weather_record(LOCATION_B)]),
                provider_source_id="7", provider_payload_hash="c" * 64,
                processing_time_ms=1,
            )
            raise AssertionError("weather grant was accepted for an ungranted location")
        except (psycopg2.Error, TenantContextDenied):
            pass
        try:
            _store_observation(
                LOCATION_A, RAW_CREDENTIAL, record=weather_record(LOCATION_B),
                projection=build_weather_clickhouse_projection([weather_record(LOCATION_B)]),
                provider_source_id="7", provider_payload_hash="d" * 64,
                processing_time_ms=1,
            )
            raise AssertionError("bounded function accepted a row for another location")
        except psycopg2.Error:
            pass
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.weather_observation WHERE location_id = %s::uuid", (LOCATION_B,))
            if cursor.fetchone()[0] != 0:
                raise AssertionError("cross-location attempts wrote weather data")
        admin.commit()
        checks.append("ungranted and mismatched locations are denied before any cross-location write")

        try:
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                cursor.execute(
                    """SELECT * FROM kokonut_security.store_weather_observation(
                         %s::uuid, NULL, '[]'::jsonb, NULL, '', NULL, 1, NULL
                    )""",
                    (LOCATION_A,),
                )
            raise AssertionError("store function accepted a transaction without signed context")
        except errors.InsufficientPrivilege:
            worker.rollback()
        checks.append("bounded function rejects missing signed worker context")

        failed = _store_observation(
            LOCATION_A, RAW_CREDENTIAL, record=None, projection=None,
            provider_source_id="", provider_payload_hash=None,
            processing_time_ms=4,
            error_text="weather fetch or parsing failed (RuntimeError)",
        )
        if failed != (None, False):
            raise AssertionError("failed provider call returned an observation")
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), min(error_message) FROM public.ingestion_log "
                "WHERE source_table = 'weather_api' AND status = 'failed'"
            )
            failure_audit = cursor.fetchone()
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox WHERE source_table = 'weather_observation'")
            if cursor.fetchone()[0] != 2:
                raise AssertionError("failed provider call enqueued a projection")
        admin.commit()
        if failure_audit != (1, "weather fetch or parsing failed (RuntimeError)"):
            raise AssertionError("sanitized provider failure audit was not persisted")
        checks.append("sanitized failed-provider audit is location-scoped and creates no observation/outbox rows")

        worker.rollback()
        set_worker_tenant_context(
            worker, credential=RAW_CREDENTIAL, location_id=LOCATION_A,
            resource="weather_observation", action="ingest",
        )
        worker.commit()
        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            cursor.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("signed worker scope survived transaction end")
        worker.rollback()
        checks.append("transaction completion clears the signed worker context")

        with admin.cursor() as cursor:
            cursor.execute(
                """SELECT has_table_privilege('kokonut_worker_login', 'public.weather_observation', 'INSERT'),
                          has_table_privilege('kokonut_worker_login', 'public.ingestion_log', 'INSERT'),
                          has_table_privilege('kokonut_worker_login', 'public.clickhouse_outbox', 'INSERT'),
                          has_table_privilege('kokonut_worker_login', 'kokonut_security.weather_observation_worker_receipt', 'SELECT'),
                          has_table_privilege('kokonut_worker_execution', 'public.weather_observation', 'INSERT'),
                          has_function_privilege('kokonut_runtime',
                            'kokonut_security.store_weather_observation(uuid,jsonb,jsonb,text,text,text,integer,text)', 'EXECUTE'),
                          has_function_privilege('kokonut_worker_execution',
                            'kokonut_security.store_weather_observation(uuid,jsonb,jsonb,text,text,text,integer,text)', 'EXECUTE')"""
            )
            privileges = cursor.fetchone()
            if privileges != (False, False, False, False, False, False, True):
                raise AssertionError(f"unexpected weather observation worker ACLs: {privileges}")
            cursor.execute(
                """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                          rolreplication, rolbypassrls, rolinherit
                     FROM pg_roles WHERE rolname = 'kokonut_weather_observation_owner'"""
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False):
                raise AssertionError("function owner has unsafe role attributes")
            cursor.execute(
                """SELECT bool_and(relrowsecurity AND relforcerowsecurity)
                     FROM pg_class
                    WHERE oid IN ('public.weather_observation'::regclass,
                                  'public.ingestion_log'::regclass,
                                  'public.clickhouse_outbox'::regclass)"""
            )
            if cursor.fetchone()[0] is not True:
                raise AssertionError("fixture no longer proves forced-RLS execution")
        admin.commit()
        checks.append("worker login/execution role have no direct table access; runtime cannot call the bounded function; forced RLS passes")

        result = {
            "schema_migrations": [405, 419, 426, 427],
            "checks": checks,
            "candidate_or_legacy_database_accessed": False,
            "feature_enabled": False,
            "worker_credentials_provisioned": False,
            "provider_contacted": False,
            "candidate_application_rls_enabled": False,
            "fixture_forced_rls": True,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    finally:
        if worker is not None:
            worker.close()
        if admin is not None:
            admin.close()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
