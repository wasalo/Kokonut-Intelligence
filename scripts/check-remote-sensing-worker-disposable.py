#!/usr/bin/env python3
"""Exercise migration 432 on an ephemeral PostgreSQL 16/PostGIS target."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg2
from psycopg2 import errors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")
FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_REMOTE_SENSING = ROOT / "tests/fixtures/remote_sensing_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION = ROOT / "schemas/postgres/432_signed_remote_sensing_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-17-recovery/signed-remote-sensing-worker-disposable.json"

TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
WORKER_ID = "a0000000-0000-0000-0000-000000000951"
FARM_ID = "a0000000-0000-0000-0000-000000000101"
PLOT_ID = "a0000000-0000-0000-0000-000000000201"
JOB_A1 = "a0000000-0000-0000-0000-000000000901"
JOB_A2 = "a0000000-0000-0000-0000-000000000902"
JOB_B = "a0000000-0000-0000-0000-000000000903"
RAW_CREDENTIAL = "synthetic-remote-sensing-worker-credential-for-disposable-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode()).hexdigest()
LOGIN_PASSWORD = "synthetic-remote-sensing-login-password"


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
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
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

    return get_worker_db("remote_sensing", environ={
        "KOKONUT_REMOTE_SENSING_DATABASE_URL": (
            f"postgresql://kokonut_remote_sensing_login:{LOGIN_PASSWORD}@127.0.0.1:{port}/postgres"
        ),
    })


def set_scope(connection, location_id: str = LOCATION_A) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=location_id,
        resource="remote_sensing",
        action="run",
    )


def _seed(docker: str, container: str) -> None:
    docker_sql(docker, container, f"""
        INSERT INTO public.farm (id, location_id, name)
        VALUES ('{FARM_ID}', '{LOCATION_A}', 'Synthetic farm');
        INSERT INTO public.plot (id, farm_id, boundary)
        VALUES ('{PLOT_ID}', '{FARM_ID}',
            public.ST_GeomFromText('POLYGON((-70 18,-69.99 18,-69.99 18.01,-70 18.01,-70 18))', 4326));
        INSERT INTO public.remote_sensing_job (id, location_id, plot_id, provider, bbox, metadata)
        VALUES
            ('{JOB_A1}', '{LOCATION_A}', '{PLOT_ID}', 'copernicus', NULL,
                '{{"fallback_provider":"gee"}}'),
            ('{JOB_A2}', '{LOCATION_A}', '{PLOT_ID}', 'gee', NULL, '{{}}'),
            ('{JOB_B}', '{LOCATION_B}', NULL, 'gee', NULL, '{{}}');
        INSERT INTO kokonut_security.worker_principal (id, principal_key)
        VALUES ('{WORKER_ID}', 'remote-sensing-disposable');
        INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
        VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
        INSERT INTO kokonut_security.worker_scope_grant (
            worker_id, tenant_id, location_id, resource, action, granted_by
        ) VALUES (
            '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}', 'remote_sensing', 'run', 'disposable fixture'
        );
        ALTER ROLE kokonut_remote_sensing_login WITH LOGIN PASSWORD '{LOGIN_PASSWORD}'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
        GRANT CONNECT ON DATABASE postgres TO kokonut_remote_sensing_login;
        ALTER TABLE public.remote_sensing_job ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.remote_sensing_job FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.remote_sensing_observation ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.remote_sensing_observation FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.remote_sensing_provider_attempt ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.remote_sensing_provider_attempt FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.farm ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.farm FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.plot ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.plot FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.ingestion_log FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.clickhouse_outbox ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.clickhouse_outbox FORCE ROW LEVEL SECURITY;
    """)


def claim(port: int, location_id: str = LOCATION_A):
    connection = worker_connection(port)
    try:
        set_scope(connection, location_id)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.claim_remote_sensing_job(%s::uuid)", (location_id,)
            )
            row = cursor.fetchone()
        connection.commit()
        return row[0] if row else None
    finally:
        connection.close()


def finish(port: int, job: dict, attempts: list[dict], observations: list[dict], *, location_id=LOCATION_A):
    connection = worker_connection(port)
    try:
        set_scope(connection, location_id)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.finish_remote_sensing_job(%s::uuid,%s::uuid,%s,%s::jsonb,%s::jsonb)",
                (job["id"], location_id, job["lease_owner"], json.dumps(attempts), json.dumps(observations)),
            )
            result = cursor.fetchone()[0]
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _attempt(provider: str, outcome: str, *, fallback: bool = False, count: int = 0) -> dict:
    now = datetime.now(UTC)
    return {
        "provider": provider,
        "outcome": outcome,
        "retryable": outcome == "retryable",
        "observations": count,
        "message": "synthetic retry" if outcome == "retryable" else None,
        "fallback_used": fallback,
        "metadata": {},
        "started_at": (now - timedelta(seconds=1)).isoformat(),
        "finished_at": now.isoformat(),
    }


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-remote-sensing-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("REMOTE_SENSING_TEST_IMAGE", "postgis/postgis:16-3.4")
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    admin = worker = runtime = None
    checks: list[str] = []
    stage = "container startup"
    try:
        run([docker, "run", "-d", "--rm", "--name", container,
             "-e", f"POSTGRES_PASSWORD={admin_password}", "-p", "127.0.0.1::5432", image])
        created = True
        time.sleep(10)
        wait_ready(docker, container)

        stage = "isolated schema and migration replay"
        docker_sql(docker, container, FIXTURE_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_ACL.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_REMOTE_SENSING.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        _seed(docker, container)
        docker_sql(docker, container, migration)
        checks.append("migration 432 applies after signed worker context and safely replays with the dedicated login; no candidate or legacy database used")

        mapping = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not mapping:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(mapping[0].rsplit(":", 1)[1])
        admin = connect(port, "postgres", admin_password)
        runtime = connect(port, "kokonut_runtime", "worker-runtime-fixture")

        stage = "signed claim and forced-RLS scope"
        first_job = claim(port)
        if str(first_job["id"]) != JOB_A1 or str(first_job["location_id"]) != LOCATION_A:
            raise AssertionError(f"worker claimed an unexpected job: {first_job}")
        if first_job["bbox"] is None or first_job["bbox"]["west"] > -70 or first_job["bbox"]["east"] < -69.99:
            raise AssertionError(f"plot geometry did not produce a bounded bbox: {first_job.get('bbox')}")
        denied_worker = worker_connection(port)
        denied = False
        try:
            set_scope(denied_worker, LOCATION_A)
            with denied_worker.cursor() as cursor:
                cursor.execute(
                    "SELECT kokonut_security.claim_remote_sensing_job(%s::uuid)", (LOCATION_B,)
                )
        except errors.InsufficientPrivilege:
            denied = True
            denied_worker.rollback()
        finally:
            denied_worker.close()
        if not denied:
            raise AssertionError("signed worker claimed a job outside its grant")
        checks.append("signed claim returns only the granted location, derives the plot bbox, and denies another location under forced RLS")

        stage = "fallback, atomic persistence, and projection parity"
        observed_at = datetime.now(UTC).date().isoformat()
        observation = {
            "plot_id": PLOT_ID, "location_id": LOCATION_A, "observation_date": observed_at,
            "source": "sentinel-2", "source_system": "gee_api", "source_id": "synthetic-scene-1",
            "ndvi": 0.7123, "canopy_cover_pct": 81.4, "canopy_height_m": 2.5,
            "cloud_cover_pct": 4.2, "metadata": {"fixture": True},
        }
        attempts = [_attempt("copernicus", "retryable"), _attempt("gee", "success", fallback=True, count=1)]
        if finish(port, first_job, attempts, [observation]) != 1:
            raise AssertionError("first remote-sensing observation was not inserted")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*), min(attempt_number), max(attempt_number) FROM public.remote_sensing_provider_attempt WHERE job_id=%s::uuid", (JOB_A1,))
            attempt_result = cursor.fetchone()
            cursor.execute("SELECT location_id::text, plot_id::text, canopy_cover_pct::text, canopy_height_m::text FROM public.remote_sensing_observation")
            observation_result = cursor.fetchone()
            cursor.execute("SELECT count(*) FROM public.ingestion_log")
            log_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*), bool_or(columns @> '[\"canopy_cover_pct\"]'::jsonb) FROM public.clickhouse_outbox")
            outbox_result = cursor.fetchone()
            cursor.execute("SELECT last_run_status, observations_fetched, lease_owner FROM public.remote_sensing_job WHERE id=%s::uuid", (JOB_A1,))
            job_result = cursor.fetchone()
        if attempt_result != (2, 1, 2) or observation_result != (LOCATION_A, PLOT_ID, "81.40", "2.50"):
            raise AssertionError(
                f"fallback attempts or normalized observation fields were not stored: "
                f"attempts={attempt_result!r}, observation={observation_result!r}"
            )
        if (log_count, outbox_result) != (1, (1, True)) or job_result != ("success", 1, None):
            raise AssertionError(
                f"audit/outbox/job effects were not committed atomically: "
                f"logs={log_count!r}, outbox={outbox_result!r}, job={job_result!r}"
            )

        second_job = claim(port)
        if str(second_job["id"]) != JOB_A2:
            raise AssertionError(f"second location A job was not claimed: {second_job}")
        bad_record = {**observation, "source_system": "copernicus_api", "source_id": "atomicity-failure"}
        try:
            finish(port, second_job, [_attempt("gee", "success", count=1)], [bad_record])
        except errors.InvalidParameterValue:
            pass
        else:
            raise AssertionError("provider/source mismatch was accepted")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.remote_sensing_provider_attempt WHERE job_id=%s::uuid", (JOB_A2,))
            if cursor.fetchone()[0] != 0:
                raise AssertionError("failed completion left a provider attempt behind")
        if finish(port, second_job, [_attempt("gee", "success", count=1)], [observation]) != 0:
            raise AssertionError("same-scope duplicate observation was not suppressed")
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.remote_sensing_observation")
            obs_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.clickhouse_outbox")
            outbox_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM public.ingestion_log")
            audit_count = cursor.fetchone()[0]
        if (obs_count, outbox_count, audit_count) != (1, 1, 1):
            raise AssertionError("duplicate replay emitted a duplicate observation or side effect")
        checks.append("fallback attempt history, canopy fields, ingestion audit, and ClickHouse outbox commit atomically; source mismatch rolls back and duplicate replay is idempotent")

        stage = "least privilege and transaction cleanup"
        worker = worker_connection(port)
        set_scope(worker)
        with worker.cursor() as cursor:
            cursor.execute("SELECT current_user")
            if cursor.fetchone()[0] != "kokonut_worker_execution":
                raise AssertionError("signed scope did not switch to worker execution role")
            cursor.execute("SELECT current_setting('kokonut.context_payload', true) <> ''")
            if not cursor.fetchone()[0]:
                raise AssertionError("worker context was not signed in the active transaction")
        worker.commit()
        with worker.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.remote_sensing_job")
        raise AssertionError("worker could read the job table directly")
    except errors.InsufficientPrivilege:
        if stage != "least privilege and transaction cleanup":
            raise
        worker.rollback()
        with worker.cursor() as cursor:
            cursor.execute("SELECT current_user, current_setting('kokonut.context_payload', true)")
            if cursor.fetchone() != ("kokonut_remote_sensing_login", ""):
                raise AssertionError("transaction end did not restore login role and clear signed context")
        try:
            with runtime.cursor() as cursor:
                cursor.execute("SELECT kokonut_security.claim_remote_sensing_job(%s::uuid)", (LOCATION_A,))
        except errors.InsufficientPrivilege:
            runtime.rollback()
        else:
            raise AssertionError("shared runtime role could execute the remote-sensing worker function")
        with admin.cursor() as cursor:
            cursor.execute("SELECT has_table_privilege('kokonut_remote_sensing_login','public.remote_sensing_job','SELECT') OR has_table_privilege('kokonut_worker_execution','public.remote_sensing_job','SELECT')")
            if cursor.fetchone()[0]:
                raise AssertionError("worker login or execution role retained direct table access")
            cursor.execute("SELECT pg_has_role('kokonut_remote_sensing_login','kokonut_worker_execution','SET')")
            if not cursor.fetchone()[0]:
                raise AssertionError("dedicated worker login cannot enter its bounded execution role")
        checks.append("dedicated login has no direct relation privileges, runtime cannot call bounded functions, and transaction end clears signed context/restores login")

        evidence = {
            "status": "passed",
            "migration": 432,
            "checks": checks,
            "scope": "synthetic data on an ephemeral PostgreSQL 16/PostGIS container with forced RLS; no candidate or legacy database used",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    except Exception as exc:
        if created:
            logs = subprocess.run([docker, "logs", "--tail", "60", container], text=True, capture_output=True, check=False)
            if logs.returncode == 0:
                diagnostic = "\n".join(part for part in (logs.stdout, logs.stderr) if part)
                if diagnostic:
                    print(f"disposable PostgreSQL diagnostics:\n{diagnostic}", file=sys.stderr)
        raise RuntimeError(f"remote-sensing disposable acceptance failed during {stage}: {exc}") from exc
    finally:
        for connection in (worker, runtime, admin):
            if connection is not None:
                connection.close()
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
