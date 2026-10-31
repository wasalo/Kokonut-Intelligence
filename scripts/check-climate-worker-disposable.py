#!/usr/bin/env python3
"""Exercise the signed climate boundary through migration 713 on disposable PostGIS."""

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
sys.path.insert(0, str(ROOT))
FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_CLIMATE = ROOT / "tests/fixtures/climate_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION_IDEMPOTENCY = ROOT / "schemas/postgres/428_climate_summary_idempotency.sql"
MIGRATION_CLIMATE = ROOT / "schemas/postgres/429_signed_climate_worker.sql"
MIGRATION_AUDIT_PARITY = ROOT / "schemas/postgres/713_signed_climate_summary_audit_parity.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-31-recovery/climate-worker-713-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000951"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
LOCATION_PLOT_ONLY = "a0000000-0000-0000-0000-000000000003"
LOCATION_NO_GEOMETRY = "a0000000-0000-0000-0000-000000000004"
RAW_CREDENTIAL = "synthetic-climate-worker-credential-for-disposable-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    command = [
        docker, "exec", "-i", container, "psql", "-X", "-q", "-v",
        "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ]
    for attempt in range(3):
        result = subprocess.run(
            command, input=statement, text=True, capture_output=True, check=False
        )
        if result.returncode == 0:
            return result.stdout
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if attempt < 2 and any(
            marker in details for marker in ("database system is shutting down", "database system is starting up")
        ):
            wait_ready(docker, container)
            continue
        raise RuntimeError(f"disposable SQL failed ({result.returncode}): {details}")
    raise RuntimeError("disposable SQL did not complete after PostgreSQL restart")


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    ready_since = None
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            ready_since = ready_since or time.monotonic()
        else:
            ready_since = None
        if ready_since is not None and time.monotonic() - ready_since >= 3:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostGIS did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def worker_connection(port: int):
    from services.common.worker_database import get_worker_db

    return get_worker_db("climate", environ={
        "KOKONUT_CLIMATE_DATABASE_URL": (
            f"postgresql://kokonut_worker_login:worker-execution-fixture@127.0.0.1:{port}/postgres"
        ),
    })


def set_scope(connection, location_id: str = LOCATION_A) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    set_worker_tenant_context(
        connection, credential=RAW_CREDENTIAL, location_id=location_id,
        resource="climate", action="ingest",
    )


def store(connection, summary: dict, source: str | None = None) -> str | None:
    source_key = source or summary["source_key"]
    audit_text = json.dumps(legacy_audit_payload(summary), sort_keys=True, default=str)
    set_scope(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT kokonut_security.store_climate_summary_v2(%s::uuid, %s, %s::jsonb, %s, %s, %s)",
            (LOCATION_A, source_key, json.dumps(summary), audit_text, 37, None),
        )
        result = cursor.fetchone()[0]
    connection.commit()
    return str(result) if result is not None else None


def legacy_audit_payload(summary: dict) -> dict:
    source = summary["source_key"]
    values = summary["values"]
    if source == "worldclim":
        return summary["metadata"]["estimated_bioclimatic_variables"]
    if source == "era5_land":
        return {
            "soil_moisture_6m_volume_fraction": values["soil_moisture_6m"],
            "mean_temp_6m_c": values["mean_temp_6m"],
            "max_temp_6m_c": values["max_temp_6m"],
            "min_temp_6m_c": values["min_temp_6m"],
            "precipitation_6m_mm": values["precipitation_6m"],
        }
    if source == "modis_lst":
        return {
            "lst_day_mean_6m_c": values["lst_day_mean_6m"],
            "lst_night_mean_6m_c": values["lst_night_mean_6m"],
        }
    if source == "smap_moisture":
        return {"soil_moisture_6m_volume_fraction": values["soil_moisture_6m"]}
    return {"vh_median_6m_db": values["vh_median_6m"], "vv_median_6m_db": values["vv_median_6m"]}


def sample_summaries() -> list[dict]:
    bioclim = {f"bio_{number}": float(number) for number in range(1, 20)}
    bioclim.update({
        "bio_1": 12, "bio_4": 75, "bio_5": 28, "bio_6": 12, "bio_7": 18,
        "bio_12": 1000, "bio_15": 60, "bio_16": 300, "bio_17": 100,
    })
    return [
        {
            "source_key": "worldclim", "target_date": None, "resolution_m": None,
            "values": {
                "bio1_mean_annual_temp": 12, "bio12_annual_precipitation": 1000,
                "bio15_precip_seasonality": 60, "bio16_precip_wettest_quarter": 300,
                "bio17_precip_driest_quarter": 100, "bio4_temp_seasonality": 75,
                "bio5_max_temp_warmest_month": 28, "bio6_min_temp_coldest_month": 12,
                "temp_range": 18,
            },
            "metadata": {
                "estimation_method": "latitude_proxy_v1",
                "estimated_bioclimatic_variables": bioclim,
            },
        },
        {
            "source_key": "era5_land", "target_date": "2026-10-17", "resolution_m": 11132,
            "values": {"soil_moisture_6m": 0.24, "mean_temp_6m": 23, "max_temp_6m": 28,
                        "min_temp_6m": 18, "precipitation_6m": 640},
            "metadata": {"dataset": "ECMWF/ERA5_LAND/DAILY_AGGR"},
        },
        {
            "source_key": "modis_lst", "target_date": "2026-10-17", "resolution_m": 1000,
            "values": {"lst_day_mean_6m": 30, "lst_night_mean_6m": 22},
            "metadata": {"dataset": "MODIS/061/MOD11A2"},
        },
        {
            "source_key": "smap_moisture", "target_date": "2026-10-17", "resolution_m": 9000,
            "values": {"soil_moisture_6m": 0.31},
            "metadata": {"dataset": "NASA/SMAP/SPL3SMP_E/006"},
        },
        {
            "source_key": "sentinel1_sar", "target_date": "2026-10-17", "resolution_m": 10,
            "values": {"vh_median_6m": -18.2, "vv_median_6m": -10.1},
            "metadata": {"dataset": "COPERNICUS/S1_GRD"},
        },
    ]


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-climate-worker-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("CLIMATE_WORKER_TEST_IMAGE", "postgis/postgis:16-3.4")
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    previous = {
        name: os.environ.get(name)
        for name in ("KOKONUT_CLIMATE_DATABASE_URL", "KOKONUT_CLIMATE_WORKER_CREDENTIAL")
    }
    created = False
    admin = None
    worker = None
    stage = "container startup"
    checks: list[str] = []
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={admin_password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        # The PostGIS entrypoint starts a temporary PostgreSQL to load its
        # extensions, then restarts the server once initialization is complete.
        # Do not connect during that deliberate shutdown/restart window.
        time.sleep(10)
        wait_ready(docker, container)
        stage = "context fixture and migrations"
        docker_sql(docker, container, FIXTURE_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_ACL.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_CLIMATE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_IDEMPOTENCY.read_text(encoding="utf-8"))
        migration = MIGRATION_CLIMATE.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        audit_migration = MIGRATION_AUDIT_PARITY.read_text(encoding="utf-8")
        docker_sql(docker, container, audit_migration)
        docker_sql(docker, container, audit_migration)
        checks.append("migrations 405, 419, 428, 429, and 713 apply in order; migrations 429 and 713 replay cleanly")

        stage = "synthetic worker grants"
        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'climate-disposable');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}', 'climate', 'ingest', 'disposable fixture'
            ), (
                '{WORKER_ID}', 'a0000000-0000-0000-0000-000000000802',
                '{LOCATION_B}', 'climate', 'ingest', 'disposable fixture'
            ), (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_PLOT_ONLY}', 'climate', 'ingest', 'disposable fixture'
            ), (
                '{WORKER_ID}', 'a0000000-0000-0000-0000-000000000802',
                '{LOCATION_NO_GEOMETRY}', 'climate', 'ingest', 'disposable fixture'
            );
            """,
        )
        port_rows = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_rows:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_rows[0].rsplit(":", 1)[1])
        admin = connect(port, "postgres", admin_password)
        worker = worker_connection(port)

        stage = "signed location read"
        set_scope(worker)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude, west, south, east, north "
                "FROM kokonut_security.climate_location(%s::uuid)", (LOCATION_A,),
            )
            bounds = cursor.fetchone()
        worker.commit()
        if bounds != (18.5, -69.9, -70.0, 18.0, -69.0, 19.0):
            raise AssertionError(f"signed plot bbox lookup returned unexpected bounds: {bounds}")
        set_scope(worker, LOCATION_B)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT west, south, east, north FROM kokonut_security.climate_location(%s::uuid)",
                (LOCATION_B,),
            )
            fallback = cursor.fetchone()
        worker.commit()
        if fallback != (-70.05, 18.95, -69.95, 19.05):
            raise AssertionError(f"coordinate fallback bbox was unexpected: {fallback}")
        set_scope(worker, LOCATION_PLOT_ONLY)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude, west, south, east, north "
                "FROM kokonut_security.climate_location(%s::uuid)", (LOCATION_PLOT_ONLY,),
            )
            plot_only = cursor.fetchone()
        worker.commit()
        if plot_only != (None, None, -72.0, 16.0, -71.0, 17.0):
            raise AssertionError(f"plot-only location lookup returned unexpected values: {plot_only}")
        set_scope(worker, LOCATION_NO_GEOMETRY)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude, west, south, east, north "
                "FROM kokonut_security.climate_location(%s::uuid)", (LOCATION_NO_GEOMETRY,),
            )
            no_geometry = cursor.fetchone()
        worker.commit()
        if no_geometry != (None, None, None, None, None, None):
            raise AssertionError(f"empty location lookup returned unexpected values: {no_geometry}")
        checks.append("signed location lookup supports plot-only, coordinate-fallback, and empty geometry scopes")

        stage = "direct table denial"
        try:
            with worker.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM public.worldclim_climate")
            raise AssertionError("worker login received direct climate-table access")
        except errors.InsufficientPrivilege:
            worker.rollback()
        checks.append("worker login has no direct climate-table access despite forced RLS")

        stage = "five summary writes"
        ids: dict[str, str | None] = {}
        for summary in sample_summaries():
            ids[summary["source_key"]] = store(worker, summary)
        if not all(ids.values()):
            raise AssertionError("one or more canonical summaries returned no ID")
        checks.append("all five whitelisted source summaries and ingestion audit rows commit through the v2 bounded function")

        stage = "audit payload and duration parity"
        expected_audits = {
            summary["source_key"]: (
                hashlib.sha256(
                    json.dumps(
                        legacy_audit_payload(summary), sort_keys=True, default=str
                    ).encode("utf-8")
                ).hexdigest(),
                37,
            )
            for summary in sample_summaries()
        }
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT source_id, payload_hash, processing_time_ms, execution_duration_ms "
                "FROM public.ingestion_log WHERE location_id = %s::uuid AND status = 'success' "
                "ORDER BY source_id",
                (LOCATION_A,),
            )
            audit_rows = cursor.fetchall()
        admin.commit()
        if len(audit_rows) != 5:
            raise AssertionError(f"expected five success audit rows, received {len(audit_rows)}")
        for source_id, payload_hash, processing_ms, duration_ms in audit_rows:
            # `source_id` is canonical provider provenance, not the source key.
            source_key = {
                "latitude_proxy_v1": "worldclim",
                "ECMWF/ERA5_LAND/DAILY_AGGR": "era5_land",
                "MODIS/061/MOD11A2": "modis_lst",
                "NASA/SMAP/SPL3SMP_E/006": "smap_moisture",
                "COPERNICUS/S1_GRD": "sentinel1_sar",
            }.get(source_id)
            if source_key is None or (payload_hash, duration_ms) != expected_audits[source_key]:
                raise AssertionError(f"success audit hash or execution duration mismatched: {source_id}")
            if processing_ms != 0:
                raise AssertionError("legacy success processing_time_ms did not preserve its zero value")
        checks.append("v2 audit hashes match the legacy serialized payload; legacy success timing remains zero and elapsed duration is separate")

        stage = "idempotent replay and payload rejection"
        modis = next(item for item in sample_summaries() if item["source_key"] == "modis_lst")
        same_id = store(worker, modis)
        if same_id != ids["modis_lst"]:
            raise AssertionError("replayed MODIS summary did not upsert the existing row")
        checks.append("same-date/source retries upsert one location-level climate record")

        invalid = dict(modis)
        invalid["values"] = {**modis["values"], "unreviewed_field": 999}
        try:
            store(worker, invalid)
            raise AssertionError("source payload accepted an unexpected metric")
        except errors.RaiseException:
            worker.rollback()
        checks.append("source payload field allowlists reject unapproved data columns")

        stage = "cross-location denial"
        set_scope(worker)
        with worker.cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT kokonut_security.store_climate_summary_v2(%s::uuid, 'modis_lst', "
                    "%s::jsonb, %s, 1, NULL)",
                    (LOCATION_B, json.dumps(modis), json.dumps(legacy_audit_payload(modis), sort_keys=True)),
                )
                raise AssertionError("signed climate write accepted a different location")
            except errors.InsufficientPrivilege:
                worker.rollback()
        checks.append("bounded climate writes reject cross-location IDs")

        stage = "failure audit"
        set_scope(worker)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.store_climate_summary_v2(%s::uuid, 'smap_moisture', "
                "NULL, NULL, 23, %s)",
                (LOCATION_A, "synthetic provider failure"),
            )
        worker.commit()
        stage = "privilege boundary"
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT status, rows_affected, error_message FROM public.ingestion_log "
                "WHERE location_id = %s::uuid AND source_id = 'NASA/SMAP/SPL3SMP_E/006' "
                "ORDER BY created_at DESC LIMIT 1", (LOCATION_A,),
            )
            failure = cursor.fetchone()
        admin.commit()
        if failure != ("failed", 0, "synthetic provider failure"):
            raise AssertionError("provider failure audit is missing or incorrect")
        checks.append("provider failures create scoped audit rows without writing summaries")

        with admin.cursor() as cursor:
            cursor.execute("""
                SELECT has_table_privilege('kokonut_worker_login', 'public.worldclim_climate', 'INSERT'),
                       has_table_privilege('kokonut_worker_execution', 'public.worldclim_climate', 'INSERT'),
                       has_function_privilege('kokonut_worker_login',
                           'kokonut_security.store_climate_summary_v2(uuid,text,jsonb,text,integer,text)', 'EXECUTE'),
                       has_function_privilege('kokonut_worker_execution',
                           'kokonut_security.store_climate_summary_v2(uuid,text,jsonb,text,integer,text)', 'EXECUTE'),
                       has_table_privilege('kokonut_runtime', 'public.worldclim_climate', 'INSERT'),
                       has_table_privilege('kokonut_runtime', 'public.ncep_weather_summary', 'UPDATE'),
                       has_table_privilege('kokonut_runtime', 'public.modis_lst_summary', 'DELETE'),
                       has_table_privilege('kokonut_runtime', 'public.smap_soil_moisture', 'INSERT'),
                       has_table_privilege('kokonut_runtime', 'public.sentinel1_sar_summary', 'UPDATE')
            """)
            privileges = cursor.fetchone()
        admin.commit()
        if privileges != (False, False, False, True, False, False, False, False, False):
            raise AssertionError(f"climate worker privilege boundary is unexpected: {privileges}")
        checks.append("only the non-login worker execution role can call v2; runtime climate DML stays denied")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"migration": MIGRATION_AUDIT_PARITY.name, "checks": checks}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "checks": checks, "evidence": str(output)}, indent=2))
        return 0
    except Exception:
        print(f"disposable climate acceptance failed during: {stage}", file=sys.stderr)
        if created:
            logs = subprocess.run(
                [docker, "logs", container], text=True, capture_output=True, check=False
            )
            if logs.returncode == 0 and logs.stdout:
                print("temporary PostgreSQL logs:\n" + logs.stdout[-4000:], file=sys.stderr)
            if logs.returncode == 0 and logs.stderr:
                print("temporary PostgreSQL diagnostics:\n" + logs.stderr[-4000:], file=sys.stderr)
        raise
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
            subprocess.run([docker, "rm", "-f", container], capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"climate worker disposable check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
