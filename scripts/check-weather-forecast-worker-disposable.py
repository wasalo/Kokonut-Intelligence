#!/usr/bin/env python3
"""Exercise migration 426 against disposable PostgreSQL 16 only."""

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
# This disposable acceptance supplies every credential it uses explicitly and
# must not decrypt the repository's unrelated .env.sops during module imports.
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")
FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_WEATHER = ROOT / "tests/fixtures/weather_forecast_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION_WEATHER = ROOT / "schemas/postgres/426_signed_weather_forecast_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/weather-forecast-worker-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
RAW_CREDENTIAL = "synthetic-weather-forecast-worker-credential"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


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
    successes = 0
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def make_record() -> dict:
    return {
        "location_id": LOCATION_A,
        "source": "openweathermap",
        "forecast_date": "2026-10-16",
        "forecast_hour": 12,
        "temp_c": 24.0,
        "temp_min_c": 20.0,
        "temp_max_c": 27.0,
        "feels_like_c": 25.0,
        "humidity_pct": 70,
        "precipitation_mm": 0,
        "precipitation_prob_pct": 10,
        "rain_3h_mm": 0,
        "wind_speed_kmh": 4.0,
        "wind_direction_deg": 90,
        "wind_gust_kmh": 6.0,
        "cloud_cover_pct": 10,
        "visibility_km": 10,
        "pressure_hpa": 1012,
        "uv_index": 4,
        "description": "clear sky",
        "metadata": {"weather_main": "Clear"},
    }


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-weather-worker-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("WEATHER_WORKER_TEST_IMAGE", "postgres:16")
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    env_names = (
        "KOKONUT_WEATHER_FORECAST_DATABASE_URL",
        "KOKONUT_WEATHER_FORECAST_WORKER_CREDENTIAL",
        "KOKONUT_FEATURE_SIGNED_WEATHER_FORECAST_WORKER",
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
        docker_sql(docker, container, FIXTURE_WEATHER.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_ACL.read_text(encoding="utf-8"))
        migration = MIGRATION_WEATHER.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migrations 405, 419, and 426 apply in order; migration 426 replays cleanly")

        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'weather-forecast-disposable');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}',
                'weather_forecast', 'ingest', 'disposable fixture'
            );
            """,
        )
        port_output = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_output:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_output[0].rsplit(":", 1)[1])
        dsn = f"postgresql://kokonut_worker_login:worker-execution-fixture@127.0.0.1:{port}/postgres"
        os.environ["KOKONUT_WEATHER_FORECAST_DATABASE_URL"] = dsn
        os.environ["KOKONUT_WEATHER_FORECAST_WORKER_CREDENTIAL"] = RAW_CREDENTIAL
        os.environ["KOKONUT_FEATURE_SIGNED_WEATHER_FORECAST_WORKER"] = "false"
        admin = connect(port, "postgres", admin_password)

        from services.common.tenant_context import set_worker_tenant_context
        from services.common.worker_database import get_worker_db
        from services.ingestion.weather_forecast import build_forecast_clickhouse_projection
        from services.ingestion.weather_forecast_worker import _load_location, _store_batch

        worker = get_worker_db("weather_forecast")
        if _load_location(LOCATION_A, RAW_CREDENTIAL) != ("Synthetic A", 18.5, -69.9):
            raise AssertionError("signed location lookup returned unexpected coordinates")
        checks.append("signed location lookup returns only the granted active location coordinates")

        record = make_record()
        projection = build_forecast_clickhouse_projection([record])
        for _ in range(2):
            affected = _store_batch(
                LOCATION_A,
                RAW_CREDENTIAL,
                records=[record],
                projection=projection,
                provider_source_id="synthetic-city",
                provider_payload_hash="b" * 64,
                processing_time_ms=24,
            )
            if affected != 1:
                raise AssertionError(f"expected one forecast upsert; received {affected}")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.weather_forecast WHERE location_id = %s::uuid", (LOCATION_A,))
            forecast_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox WHERE source_table = 'weather_forecast'")
            outbox_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.ingestion_log WHERE status = 'success' AND location_id = %s::uuid", (LOCATION_A,))
            success_count = cursor.fetchone()[0]
        admin.commit()
        if (forecast_count, outbox_count, success_count) != (1, 1, 2):
            raise AssertionError("weather retry duplicated forecast/outbox rows or lost audit records")
        checks.append("forecast upsert, ingestion audit, and canonical outbox intent commit atomically and replay idempotently")

        set_worker_tenant_context(
            worker,
            credential=RAW_CREDENTIAL,
            location_id=LOCATION_A,
            resource="weather_forecast",
            action="ingest",
        )
        try:
            with worker.cursor() as cursor:
                cursor.execute(
                    """SELECT kokonut_security.store_weather_forecast_batch(
                               %s::uuid, '[]'::jsonb, '[]'::jsonb,
                               NULL, '', NULL, 1, NULL
                           )""",
                    (LOCATION_B,),
                )
            raise AssertionError("bounded function accepted a location different from signed scope")
        except errors.InsufficientPrivilege:
            worker.rollback()
        checks.append("bounded function rejects a requested location different from signed context")

        try:
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                cursor.execute(
                    """SELECT kokonut_security.store_weather_forecast_batch(
                               %s::uuid, '[]'::jsonb, '[]'::jsonb,
                               NULL, '', NULL, 1, NULL
                           )""",
                    (LOCATION_A,),
                )
            raise AssertionError("bounded function accepted a transaction without signed context")
        except errors.InsufficientPrivilege:
            worker.rollback()
        checks.append("bounded function denies a missing signed worker context")

        try:
            _store_batch(
                LOCATION_A,
                RAW_CREDENTIAL,
                records=[{**record, "location_id": LOCATION_B}],
                projection=build_forecast_clickhouse_projection([{**record, "location_id": LOCATION_B}]),
                provider_source_id="wrong-location",
                provider_payload_hash="c" * 64,
                processing_time_ms=1,
            )
            raise AssertionError("bounded function accepted a forecast row for another location")
        except psycopg2.Error:
            pass
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.weather_forecast WHERE location_id = %s::uuid", (LOCATION_B,))
            if cursor.fetchone()[0] != 0:
                raise AssertionError("mismatched location produced a forecast row")
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox WHERE source_table = 'weather_forecast'")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("mismatched location produced an outbox row")
        admin.commit()
        checks.append("function rejects cross-location forecast rows without writing forecast or outbox data")

        failed = _store_batch(
            LOCATION_A,
            RAW_CREDENTIAL,
            records=[],
            projection={"rows": [], "payload_hash": ""},
            provider_source_id="",
            provider_payload_hash=None,
            processing_time_ms=1,
            error_text="synthetic provider failure",
        )
        if failed != 0:
            raise AssertionError("failed provider audit unexpectedly reported forecast writes")
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), min(error_message) FROM public.ingestion_log WHERE status = 'failed' AND location_id = %s::uuid",
                (LOCATION_A,),
            )
            failure_row = cursor.fetchone()
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox WHERE source_table = 'weather_forecast'")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("failed provider run created an outbox row")
        admin.commit()
        if failure_row != (1, "synthetic provider failure"):
            raise AssertionError("failed provider audit row was not persisted as expected")
        checks.append("sanitized provider failure records audit state with zero forecast rows and no outbox intent")

        worker.rollback()
        set_worker_tenant_context(
            worker,
            credential=RAW_CREDENTIAL,
            location_id=LOCATION_A,
            resource="weather_forecast",
            action="ingest",
        )
        worker.commit()
        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            cursor.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("signed weather context survived transaction completion")
        worker.rollback()
        checks.append("signed worker context clears at transaction end")

        with admin.cursor() as cursor:
            cursor.execute(
                """SELECT has_table_privilege('kokonut_worker_login', 'public.location', 'SELECT'),
                          has_table_privilege('kokonut_worker_login', 'public.weather_forecast', 'SELECT'),
                          has_table_privilege('kokonut_worker_login', 'public.weather_forecast', 'INSERT'),
                          has_table_privilege('kokonut_worker_login', 'public.ingestion_log', 'INSERT'),
                          has_table_privilege('kokonut_worker_login', 'public.clickhouse_outbox', 'INSERT'),
                          has_table_privilege('kokonut_worker_execution', 'public.weather_forecast', 'SELECT'),
                          has_table_privilege('kokonut_worker_execution', 'public.clickhouse_outbox', 'INSERT'),
                          has_function_privilege('kokonut_runtime',
                            'kokonut_security.store_weather_forecast_batch(uuid,jsonb,jsonb,text,text,text,integer,text)', 'EXECUTE'),
                          has_function_privilege('kokonut_worker_execution',
                            'kokonut_security.store_weather_forecast_batch(uuid,jsonb,jsonb,text,text,text,integer,text)', 'EXECUTE')"""
            )
            privileges = cursor.fetchone()
            if privileges != (False, False, False, False, False, False, False, False, True):
                raise AssertionError(f"unexpected weather worker privilege boundary: {privileges}")
            cursor.execute(
                """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                          rolreplication, rolbypassrls, rolinherit
                     FROM pg_roles WHERE rolname = 'kokonut_weather_forecast_owner'"""
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False):
                raise AssertionError("weather function owner has unsafe role attributes")
            cursor.execute(
                """SELECT count(*) FROM pg_auth_members AS membership
                     JOIN pg_roles AS member_role ON member_role.oid = membership.member
                     JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
                    WHERE member_role.rolname = 'kokonut_weather_forecast_owner'
                       OR granted_role.rolname = 'kokonut_weather_forecast_owner'"""
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("weather function owner has role memberships")
        admin.commit()
        checks.append("worker login/execution role have no direct application-table access; runtime cannot call bounded function")

        result = {
            "schema_migrations": [405, 419, 426],
            "checks": checks,
            "candidate_or_legacy_database_accessed": False,
            "feature_enabled": False,
            "worker_credentials_provisioned": False,
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
