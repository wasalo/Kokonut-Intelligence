#!/usr/bin/env python3
"""Exercise migration 431 sensor ingestion on a disposable PostgreSQL 16 target."""

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
# This acceptance uses only synthetic credentials and database fixtures; keep
# imports from loading or decrypting the unrelated development .env.sops file.
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")
FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_SENSOR = ROOT / "tests/fixtures/sensor_ingestion_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION_SENSOR = ROOT / "schemas/postgres/431_signed_sensor_driver_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-17-recovery/signed-sensor-ingestion-worker-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000951"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
DRIVER_ID = "a0000000-0000-0000-0000-000000000301"
INSTANCE_A = "a0000000-0000-0000-0000-000000000401"
INSTANCE_B = "a0000000-0000-0000-0000-000000000402"
TYPE_ID = "a0000000-0000-0000-0000-000000000501"
SENSOR_A = "a0000000-0000-0000-0000-000000000601"
SENSOR_B = "a0000000-0000-0000-0000-000000000602"
RAW_CREDENTIAL = "synthetic-sensor-ingestion-worker-credential-for-disposable-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
LOGIN_PASSWORD = "synthetic-sensor-login-password-for-disposable-check"


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
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1",
             "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def worker_connection(port: int):
    from services.common.worker_database import get_worker_db

    return get_worker_db("sensor_ingestion", environ={
        "KOKONUT_SENSOR_INGESTION_DATABASE_URL": (
            f"postgresql://kokonut_sensor_ingestion_login:{LOGIN_PASSWORD}@127.0.0.1:{port}/postgres"
        ),
    })


def set_scope(connection, location_id: str = LOCATION_A) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=location_id,
        resource="sensor_driver",
        action="ingest",
    )


def _prepared_record(record: dict, *, validation_status: str = "accepted") -> dict:
    from services.ingestion.base import hash_payload

    return {
        "source_id_sha256": hash_payload({"source_id": "fixture.csv"}),
        "source_index": 0,
        "record_index": 0,
        "payload_hash": hash_payload(record),
        "record": record,
        "validation_status": validation_status,
        "validation_errors": [],
        "validation_warnings": [],
        "dedupe_key": None,
    }


def _call_store(connection, records: list[dict], *, instance_id: str = INSTANCE_A, location_id: str = LOCATION_A):
    set_scope(connection, location_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT records_fetched, records_written, records_rejected "
            "FROM kokonut_security.store_sensor_driver_batch(%s::uuid, %s::uuid, %s::jsonb)",
            (instance_id, location_id, json.dumps(records)),
        )
        result = cursor.fetchone()
    connection.commit()
    return result


def _seed(docker: str, container: str) -> None:
    docker_sql(
        docker,
        container,
        f"""
        INSERT INTO kokonut_security.worker_principal (id, principal_key)
        VALUES ('{WORKER_ID}', 'sensor-ingestion-disposable');
        INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
        VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
        INSERT INTO kokonut_security.worker_scope_grant (
            worker_id, tenant_id, location_id, resource, action, granted_by
        ) VALUES (
            '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}', 'sensor_driver', 'ingest', 'disposable fixture'
        );
        INSERT INTO public.driver_registry (
            id, driver_name, driver_type, module_path, class_name, is_enabled
        ) VALUES (
            '{DRIVER_ID}', 'sensor_csv', 'sensor',
            'services.ingestion.drivers.sensor_csv', 'Driver', TRUE
        );
        INSERT INTO public.driver_instance (id, driver_id, instance_name, config, location_id)
        VALUES
            ('{INSTANCE_A}', '{DRIVER_ID}', 'sensor-a', '{{"file_path":"sensor.csv"}}', '{LOCATION_A}'),
            ('{INSTANCE_B}', '{DRIVER_ID}', 'sensor-b', '{{"file_path":"sensor.csv"}}', '{LOCATION_B}');
        INSERT INTO public.sensor_type (id, name, unit, min_value, max_value)
        VALUES ('{TYPE_ID}', 'soil_moisture', '%', 0, 100);
        INSERT INTO public.sensor_device (id, name, slug, sensor_type_id, location_id, status)
        VALUES
            ('{SENSOR_A}', 'Sensor A', 'sensor-a', '{TYPE_ID}', '{LOCATION_A}', 'active'),
            ('{SENSOR_B}', 'Sensor B', 'sensor-b', '{TYPE_ID}', '{LOCATION_B}', 'active');
        ALTER ROLE kokonut_sensor_ingestion_login WITH LOGIN PASSWORD '{LOGIN_PASSWORD}'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
        GRANT CONNECT ON DATABASE postgres TO kokonut_sensor_ingestion_login;
        ALTER TABLE public.driver_registry ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.driver_registry FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.driver_instance ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.driver_instance FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.driver_instance_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.driver_instance_log FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.sensor_type ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.sensor_type FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.sensor_device ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.sensor_device FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.sensor_reading ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.sensor_reading FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.platform_event ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.platform_event FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
        """,
    )


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-sensor-ingestion-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("SENSOR_INGESTION_TEST_IMAGE", "postgis/postgis:16-3.4")
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    keep_container = os.getenv("SENSOR_INGESTION_KEEP_CONTAINER") == "true"
    created = False
    admin = worker = runtime = None
    checks: list[str] = []
    stage = "container startup"
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={admin_password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        time.sleep(10)
        wait_ready(docker, container)

        stage = "fixtures and migration replay"
        docker_sql(docker, container, FIXTURE_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_ACL.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_SENSOR.read_text(encoding="utf-8"))
        migration = MIGRATION_SENSOR.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        _seed(docker, container)
        docker_sql(docker, container, migration)
        checks.append("migrations 405, 419, and 431 apply in order and migration 431 replays with the configured login")

        port_rows = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_rows:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_rows[0].rsplit(":", 1)[1])
        admin = connect(port, "postgres", admin_password)
        worker = worker_connection(port)
        runtime = connect(port, "kokonut_runtime", "worker-runtime-fixture")

        stage = "worker principal and forced-RLS reads"
        set_scope(worker)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT instance_id::text, driver_name, config "
                "FROM kokonut_security.resolve_sensor_driver_instance(%s::uuid, %s::uuid)",
                (INSTANCE_A, LOCATION_A),
            )
            resolved = cursor.fetchone()
        worker.commit()
        if resolved is None or resolved[0] != INSTANCE_A or resolved[1] != "sensor_csv":
            raise AssertionError(f"signed instance lookup returned an unexpected row: {resolved}")
        set_scope(worker)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT sensor_id::text, location_id::text FROM "
                "kokonut_security.read_sensor_driver_catalog(%s::uuid)", (LOCATION_A,),
            )
            catalog = cursor.fetchall()
        worker.commit()
        if catalog != [(SENSOR_A, LOCATION_A)]:
            raise AssertionError(f"signed sensor catalog escaped or missed location scope: {catalog}")
        checks.append("signed driver and sensor catalog functions return only the granted location under forced RLS")

        stage = "atomic reading, event, audit, and projection"
        record = {
            "device_id": SENSOR_A,
            "reading_date": "2026-10-17",
            "reading_time": "12:00:00",
            "value": "22.5",
        }
        first = _call_store(worker, [_prepared_record(record)])
        if first != (1, 1, 0):
            raise AssertionError(f"first sensor batch returned an unexpected count: {first}")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.sensor_reading")
            reading_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.platform_event")
            event_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox")
            outbox_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.ingestion_log")
            log_count = cursor.fetchone()[0]
        if (reading_count, event_count, outbox_count, log_count) != (1, 1, 1, 1):
            raise AssertionError("sensor write side effects were not committed atomically")
        duplicate = _call_store(worker, [_prepared_record(record)])
        if duplicate != (1, 0, 0):
            raise AssertionError(f"duplicate sensor batch was not suppressed: {duplicate}")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.platform_event")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("duplicate reading emitted another platform event")
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("duplicate reading emitted another ClickHouse projection")
        rejected_record = {
            "device_id": "not-registered",
            "reading_date": "2026-10-17",
            "reading_time": "12:01:00",
            "value": "12.0",
        }
        rejected = _call_store(worker, [_prepared_record(rejected_record)])
        if rejected != (1, 0, 1):
            raise AssertionError(f"unregistered sensor did not become an audited rejection: {rejected}")
        try:
            _call_store(worker, [_prepared_record({**record, "value": "23.0"})])
        except errors.UniqueViolation:
            worker.rollback()
        else:
            raise AssertionError("conflicting timestamp value was accepted")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.sensor_reading")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("conflicting reading escaped transaction rollback")
            cursor.execute("SELECT count(*) FROM public.platform_event")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("conflicting reading emitted a platform event")
        checks.append("accepted, exact duplicate, unknown sensor rejection, and conflicting timestamp preserve atomic effects")

        stage = "signed scope denial and status audit"
        set_scope(worker)
        try:
            with worker.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM kokonut_security.read_sensor_driver_catalog(%s::uuid)",
                    (LOCATION_B,),
                )
        except errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("worker read a location outside its signed context")
        set_scope(worker)
        with worker.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.update_sensor_driver_status(%s::uuid, %s::uuid, "
                "'success', 2, 1, 23, NULL)", (INSTANCE_A, LOCATION_A),
            )
            if cursor.fetchone()[0] is not True:
                raise AssertionError("signed status update rejected the authorized instance")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT last_status, run_count, consecutive_failures "
                "FROM public.driver_instance WHERE id = %s::uuid", (INSTANCE_A,),
            )
            if cursor.fetchone() != ("success", 1, 0):
                raise AssertionError("signed driver status did not update the location-bound instance")
            cursor.execute("SELECT count(*) FROM public.driver_instance_log")
            if cursor.fetchone()[0] != 1:
                raise AssertionError("signed driver status did not append its run audit")
        checks.append("cross-location reads fail closed; the bounded status function appends a run audit")

        stage = "direct privilege and runtime denial"
        set_scope(worker)
        try:
            with worker.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM public.sensor_reading")
        except errors.InsufficientPrivilege:
            worker.rollback()
        else:
            raise AssertionError("sensor worker could read the relation directly")
        try:
            with runtime.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM kokonut_security.read_sensor_driver_catalog(%s::uuid)",
                    (LOCATION_A,),
                )
        except errors.InsufficientPrivilege:
            runtime.rollback()
        else:
            raise AssertionError("runtime role could execute the sensor worker function")
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_sensor_ingestion_login', 'public.sensor_reading', 'SELECT') "
                "OR has_table_privilege('kokonut_sensor_ingestion_login', 'public.sensor_reading', 'INSERT') "
                "OR has_table_privilege('kokonut_worker_execution', 'public.sensor_reading', 'SELECT') "
                "OR has_table_privilege('kokonut_worker_execution', 'public.sensor_reading', 'INSERT')"
            )
            if cursor.fetchone()[0]:
                raise AssertionError("worker principal or execution role retained direct sensor relation access")
            cursor.execute(
                "SELECT pg_has_role('kokonut_sensor_ingestion_login', 'kokonut_worker_execution', 'SET'), "
                "has_function_privilege('kokonut_sensor_ingestion_login', "
                "'kokonut_security.store_sensor_driver_batch(uuid,uuid,jsonb)', 'EXECUTE')"
            )
            if cursor.fetchone() != (True, False):
                raise AssertionError("dedicated login role boundary or privilege mode differs from contract")
        checks.append("dedicated login can SET ROLE only into bounded execution and has no direct sensor-table or function access")

        evidence = {
            "status": "passed",
            "migration": 431,
            "checks": checks,
            "scope": "synthetic records on an ephemeral PostgreSQL 16 container with forced RLS; no candidate or legacy database used",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    except Exception as exc:
        if created:
            logs = subprocess.run(
                [docker, "logs", "--tail", "60", container],
                text=True, capture_output=True, check=False,
            )
            if logs.returncode == 0:
                diagnostic = "\n".join(part for part in (logs.stdout, logs.stderr) if part)
                if diagnostic:
                    print(f"disposable PostgreSQL diagnostics:\n{diagnostic}", file=sys.stderr)
        raise RuntimeError(f"sensor-ingestion disposable acceptance failed during {stage}: {exc}") from exc
    finally:
        for connection in (worker, runtime, admin):
            if connection is not None:
                connection.close()
        if created and keep_container:
            print(f"kept disposable PostgreSQL container for inspection: {container}", file=sys.stderr)
        elif created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
