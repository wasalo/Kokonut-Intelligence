#!/usr/bin/env python3
"""Exercise the signed NOI snapshot boundary on disposable PostgreSQL 16."""

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
FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_NOI = ROOT / "tests/fixtures/noi_snapshot_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION_NOI = ROOT / "schemas/postgres/425_signed_noi_snapshot_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/noi-snapshot-worker-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
CYCLE_A = "a0000000-0000-0000-0000-000000000101"
RAW_CREDENTIAL = "synthetic-noi-snapshot-worker-credential-for-disposable-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


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


def worker_connection(port: int):
    from services.common.worker_database import get_worker_db

    dsn = (
        f"postgresql://kokonut_worker_login:worker-execution-fixture@"
        f"127.0.0.1:{port}/postgres"
    )
    return get_worker_db("noi_snapshot", environ={
        "KOKONUT_NOI_SNAPSHOT_DATABASE_URL": dsn,
    })


def reconcile(connection, location_id: str = LOCATION_A) -> int:
    from services.common.tenant_context import set_worker_tenant_context

    set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=location_id,
        resource="noi_snapshot",
        action="reconcile",
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT kokonut_security.reconcile_noi_snapshot_for_location(%s::uuid)",
            (location_id,),
        )
        return int(cursor.fetchone()[0])


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-noi-worker-{os.getpid()}-{secrets.token_hex(3)}"
    image = os.getenv("NOI_WORKER_TEST_IMAGE", "postgres:16")
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    previous = {
        name: os.environ.get(name)
        for name in (
            "KOKONUT_NOI_SNAPSHOT_DATABASE_URL",
            "KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL",
        )
    }
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
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_ACL.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_NOI.read_text(encoding="utf-8"))
        migration = MIGRATION_NOI.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migrations 405, 419, and 425 apply in order; migration 425 replays cleanly")

        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'noi-snapshot-disposable');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}',
                'noi_snapshot', 'reconcile', 'disposable fixture'
            );
            """,
        )
        port_output = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_output:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_output[0].rsplit(":", 1)[1])
        admin = connect(port, "postgres", admin_password)
        worker = worker_connection(port)

        affected = reconcile(worker)
        worker.commit()
        if affected != 1:
            raise AssertionError(f"expected one location-A snapshot insert; received {affected}")
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), min(location_id::text), min(noi) "
                "FROM public.noi_snapshot WHERE crop_cycle_id = %s::uuid",
                (CYCLE_A,),
            )
            if cursor.fetchone() != (1, LOCATION_A, 55):
                raise AssertionError("signed NOI reconcile wrote an unexpected row")
            cursor.execute("UPDATE public.crop_cycle SET noi = 61 WHERE id = %s::uuid", (CYCLE_A,))
        admin.commit()
        if reconcile(worker) != 1:
            raise AssertionError("natural-key replay did not update exactly one snapshot")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), min(location_id::text), min(noi) "
                "FROM public.noi_snapshot WHERE crop_cycle_id = %s::uuid",
                (CYCLE_A,),
            )
            if cursor.fetchone() != (1, LOCATION_A, 61):
                raise AssertionError("signed NOI replay duplicated or failed to refresh its row")
            cursor.execute(
                "SELECT count(*) FROM public.noi_snapshot WHERE location_id = %s::uuid",
                (LOCATION_B,),
            )
            if cursor.fetchone()[0] != 1:
                raise AssertionError("location-A worker changed or removed the unrelated location-B snapshot")
            cursor.execute(
                "SELECT location_id::text, noi FROM public.noi_snapshot WHERE crop_cycle_id = %s::uuid",
                ("a0000000-0000-0000-0000-000000000103",),
            )
            if cursor.fetchone() != (LOCATION_B, 777):
                raise AssertionError("location-A worker overwrote a conflicting location-B snapshot")
        admin.commit()
        checks.append("signed location-A worker inserts and idempotently refreshes only its snapshots; a stale cross-location conflict remains unchanged")

        try:
            with worker.cursor() as cursor:
                cursor.execute(
                    "SELECT kokonut_security.reconcile_noi_snapshot_for_location(%s::uuid)",
                    (LOCATION_A,),
                )
            raise AssertionError("bounded function accepted a transaction without signed context")
        except errors.InsufficientPrivilege:
            worker.rollback()
        checks.append("bounded function denies a missing signed worker context")

        try:
            reconcile(worker, LOCATION_B)
            raise AssertionError("worker credential established a scope for an ungranted location")
        except PermissionError:
            worker.rollback()
        checks.append("worker context rejects a location without an exact owner/resource/action grant")

        reconcile(worker)
        try:
            with worker.cursor() as cursor:
                cursor.execute(
                    "SELECT kokonut_security.reconcile_noi_snapshot_for_location(%s::uuid)",
                    (LOCATION_B,),
                )
            raise AssertionError("bounded function accepted a location different from signed scope")
        except errors.InsufficientPrivilege:
            worker.rollback()
        checks.append("bounded function rejects a requested location different from signed context")

        with admin.cursor() as cursor:
            cursor.execute(
                """SELECT has_table_privilege('kokonut_worker_login', 'public.crop_cycle', 'SELECT'),
                          has_table_privilege('kokonut_worker_login', 'public.v_crop_cycle_noi', 'SELECT'),
                          has_table_privilege('kokonut_worker_login', 'public.noi_snapshot', 'SELECT'),
                          has_table_privilege('kokonut_worker_login', 'public.noi_snapshot', 'INSERT'),
                          has_table_privilege('kokonut_worker_login', 'public.noi_snapshot', 'UPDATE'),
                          has_table_privilege('kokonut_worker_execution', 'public.crop_cycle', 'SELECT'),
                          has_table_privilege('kokonut_worker_execution', 'public.noi_snapshot', 'UPDATE'),
                          has_function_privilege('kokonut_runtime',
                            'kokonut_security.reconcile_noi_snapshot_for_location(uuid)', 'EXECUTE'),
                          has_function_privilege('kokonut_worker_execution',
                            'kokonut_security.reconcile_noi_snapshot_for_location(uuid)', 'EXECUTE')"""
            )
            privileges = cursor.fetchone()
            if privileges != (False, False, False, False, False, False, False, False, True):
                raise AssertionError(f"unexpected NOI worker privilege boundary: {privileges}")
            cursor.execute(
                """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                          rolreplication, rolbypassrls, rolinherit
                     FROM pg_roles WHERE rolname = 'kokonut_noi_snapshot_owner'"""
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False):
                raise AssertionError("NOI function owner has unsafe role attributes")
        admin.commit()
        checks.append("worker login and execution role have no direct source/target table access; runtime cannot call the bounded function")

        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            cursor.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("transaction-end worker context did not clear")
        worker.rollback()
        checks.append("signed worker context is transaction-local and absent after commit")

        result = {
            "schema_migrations": [405, 419, 425],
            "checks": checks,
            "candidate_or_legacy_database_accessed": False,
            "feature_enabled": False,
            "worker_credentials_provisioned": False,
            "application_rls_enabled": False,
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
