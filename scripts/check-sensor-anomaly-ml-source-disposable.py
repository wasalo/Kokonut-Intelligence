#!/usr/bin/env python3
"""Exercise migration 650 with a synthetic isolated PostgreSQL 16 worker."""

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

from psycopg2 import errors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATIONS = (
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/419_private_worker_context_functions.sql",
    ROOT / "schemas/postgres/650_signed_sensor_anomaly_ml_source.sql",
)
FIXTURES = (
    ROOT / "tests/fixtures/worker_tenant_context_disposable.sql",
    ROOT / "tests/fixtures/sensor_anomaly_ml_source_disposable.sql",
)
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-26-recovery/"
    "sensor-anomaly-ml-source-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
RAW_CREDENTIAL = "synthetic-sensor-anomaly-ml-worker-credential-for-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
LOGIN = "kokonut_sensor_anomaly_ml_source_login"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        safe_command = [
            "POSTGRES_PASSWORD=<redacted>" if part.startswith("POSTGRES_PASSWORD=") else part
            for part in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
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
        result = subprocess.run(
            [
                docker, "exec", container, "pg_isready", "-h", "127.0.0.1",
                "-U", "postgres", "-d", "postgres",
            ],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-anomaly-ml-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("SENSOR_ANOMALY_ML_TEST_IMAGE", "postgres:16")
    admin_password = secrets.token_urlsafe(24)
    login_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    worker = None
    created = False
    checks: list[str] = []
    try:
        run([
            docker, "run", "-d", "--rm", "--name", container,
            "-e", f"POSTGRES_PASSWORD={admin_password}",
            "-p", "127.0.0.1::5432", image,
        ])
        created = True
        wait_ready(docker, container)
        for fixture in FIXTURES:
            docker_sql(docker, container, fixture.read_text(encoding="utf-8"))
        for migration in MIGRATIONS:
            source = migration.read_text(encoding="utf-8")
            docker_sql(docker, container, source)
        docker_sql(docker, container, MIGRATIONS[-1].read_text(encoding="utf-8"))
        checks.append("migrations 405, 419, and 650 apply in order; migration 650 replays")

        docker_sql(
            docker,
            container,
            f"""
            ALTER ROLE {LOGIN} WITH LOGIN PASSWORD '{login_password}';
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'sensor-anomaly-ml-disposable');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}',
                'sensor_anomaly_ml', 'analyze', 'disposable fixture'
            );
            """,
        )

        port_output = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_output:
            raise RuntimeError("disposable PostgreSQL did not expose its random local port")
        port = int(port_output[0].rsplit(":", 1)[1])
        from services.common.tenant_context import (
            TenantContextDenied,
            set_agent_source_tenant_context,
        )
        from services.common.worker_database import get_worker_db

        worker = get_worker_db(
            "sensor_anomaly_ml_source",
            environ={
                "KOKONUT_SENSOR_ANOMALY_ML_SOURCE_DATABASE_URL": (
                    f"postgresql://{LOGIN}:{login_password}@127.0.0.1:{port}/postgres"
                )
            },
        )
        checks.append("dedicated source login authenticates without shared PG credentials")

        set_agent_source_tenant_context(
            worker,
            credential=RAW_CREDENTIAL,
            location_id=LOCATION_A,
            resource="sensor_anomaly_ml",
            action="analyze",
        )
        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_sensor_anomaly_ml_reader")
            cursor.execute(
                "SELECT location_id::text, sensor_id::text, quality, device_slug "
                "FROM kokonut_anomaly_ml_source.sensor_reading ORDER BY reading_time"
            )
            rows = cursor.fetchall()
        if rows != [(LOCATION_A, "a0000000-0000-0000-0000-000000000011", "good", "synthetic-location-a")]:
            raise AssertionError(f"source reader returned unexpected tenant rows: {rows!r}")
        worker.commit()
        checks.append("signed context exposes only good-quality readings from exact location A")

        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_sensor_anomaly_ml_reader")
            cursor.execute("SELECT count(*) FROM kokonut_anomaly_ml_source.sensor_reading")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("transaction-local worker context persisted after commit")
        worker.rollback()
        checks.append("signed context and reader role reset at transaction end")

        try:
            set_agent_source_tenant_context(
                worker,
                credential=RAW_CREDENTIAL,
                location_id=LOCATION_B,
                resource="sensor_anomaly_ml",
                action="analyze",
            )
        except TenantContextDenied:
            worker.rollback()
        else:
            raise AssertionError("ungranted location B unexpectedly established worker scope")
        checks.append("location without a matching worker grant is denied")

        denied_direct = False
        try:
            with worker.cursor() as cursor:
                cursor.execute("SELECT id FROM public.sensor_reading")
                cursor.fetchall()
        except errors.InsufficientPrivilege:
            denied_direct = True
            worker.rollback()
        if not denied_direct:
            raise AssertionError("source login can select the raw sensor table")
        checks.append("source login cannot select public sensor tables directly")

        denied_view_bypass = False
        try:
            with worker.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM kokonut_anomaly_ml_source.sensor_reading")
                cursor.fetchone()
        except errors.InsufficientPrivilege:
            denied_view_bypass = True
            worker.rollback()
        if not denied_view_bypass:
            raise AssertionError("source login bypassed its SET-only reader role")
        checks.append("source login cannot bypass its reader role to use the source view")

        worker.rollback()
        worker.close()
        worker = None
        cleanup = subprocess.run(
            [docker, "rm", "-f", container],
            text=True, capture_output=True, check=False,
        )
        if cleanup.returncode:
            raise RuntimeError("disposable PostgreSQL container cleanup failed")
        created = False

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "check": "sensor_anomaly_ml_signed_source_disposable",
                    "postgres_image": image,
                    "migration_versions": [405, 419, 650],
                    "migration_650_replayed": True,
                    "forced_rls": True,
                    "source_login_authenticated": True,
                    "returned_location_ids": [LOCATION_A],
                    "worker_credentials_in_output": False,
                    "candidate_or_legacy_touched": False,
                    "container_removed": True,
                    "checks": checks,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "checks": checks, "evidence": str(output)}))
        return 0
    finally:
        if worker is not None:
            try:
                worker.rollback()
            finally:
                worker.close()
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True, capture_output=True, check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
