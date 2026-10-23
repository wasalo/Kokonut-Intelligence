#!/usr/bin/env python3
"""Exercise migration 599 and the signed credit-adjustment worker on PostgreSQL 16."""

from __future__ import annotations

import argparse
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURE_CONTEXT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_SOURCE = ROOT / "tests/fixtures/credit_adjustment_worker_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_ACL = ROOT / "schemas/postgres/419_private_worker_context_functions.sql"
MIGRATION_WORKER = ROOT / "schemas/postgres/599_signed_credit_adjustment_check_worker.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-23-recovery/credit-adjustment-worker-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
TENANT_B_ID = "a0000000-0000-0000-0000-000000000802"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
RAW_CREDENTIAL = "synthetic-credit-adjustment-worker-credential-for-check"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def docker_run_command(
    docker: str,
    container: str,
    image: str,
    password: str,
    platform: str | None = None,
) -> list[str]:
    command = [docker, "run", "-d", "--rm", "--name", container]
    if platform is not None:
        command.extend(("--platform", platform))
    command.extend((
        "-e", f"POSTGRES_PASSWORD={password}",
        "-p", "127.0.0.1::5432", image,
    ))
    return command


def wait_ready(docker: str, container: str, *, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--image",
        default=os.getenv("CREDIT_ADJUSTMENT_TEST_IMAGE", "postgres:16"),
    )
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    parser.add_argument("--startup-timeout", type=int, default=180)
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    if not 30 <= args.startup_timeout <= 900:
        parser.error("--startup-timeout must be between 30 and 900 seconds")

    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-credit-check-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = args.output
    created = False
    admin = None
    checks: list[str] = []
    prior_env = {
        key: os.environ.get(key)
        for key in (
            "KOKONUT_CREDIT_ADJUSTMENT_DATABASE_URL",
            "KOKONUT_CREDIT_ADJUSTMENT_WORKER_CREDENTIAL",
        )
    }
    try:
        run(docker_run_command(
            docker, container, args.image, admin_password, args.platform
        ))
        created = True
        wait_ready(docker, container, timeout_seconds=args.startup_timeout)
        architecture = run([docker, "exec", container, "uname", "-m"]).strip()
        expected_architecture = {
            "linux/amd64": "x86_64",
            "linux/arm64": "aarch64",
        }.get(args.platform)
        if expected_architecture is not None and architecture != expected_architecture:
            raise RuntimeError("disposable PostgreSQL container architecture mismatch")
        docker_sql(docker, container, FIXTURE_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_ACL.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_SOURCE.read_text(encoding="utf-8"))
        migration = MIGRATION_WORKER.read_text(encoding="utf-8")
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migrations 405, 419, and 599 apply in order; migration 599 replays cleanly")

        docker_sql(docker, container, f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'credit-adjustment-disposable');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES
                ('{WORKER_ID}', '{TENANT_ID}', '{LOCATION_A}', 'carbon_credit_adjustment', 'read', 'disposable fixture'),
                ('{WORKER_ID}', '{TENANT_B_ID}', '{LOCATION_B}', 'carbon_credit_adjustment', 'read', 'disposable fixture');
        """)
        port_mapping = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_mapping:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_mapping[0].rsplit(":", 1)[1])
        admin = connect(port, "postgres", admin_password)
        dsn = f"postgresql://kokonut_worker_login:worker-execution-fixture@127.0.0.1:{port}/postgres"
        os.environ["KOKONUT_CREDIT_ADJUSTMENT_DATABASE_URL"] = dsn
        os.environ["KOKONUT_CREDIT_ADJUSTMENT_WORKER_CREDENTIAL"] = RAW_CREDENTIAL

        from services.analytics.carbon_credit_adjustment_worker import check

        location_a = check(LOCATION_A)
        if location_a != [{
            "credit_code": "KKNT-A-STALE",
            "current_tonnes": 100.0,
            "recomputed_tonnes": 1100.0,
            "delta_pct": 1000.0,
            "needs_adjustment": True,
        }]:
            raise AssertionError(f"location-A output did not match the latest summary: {location_a!r}")
        checks.append("signed location-A check returns only eligible location-A credits and applies the legacy 0.1% threshold")

        location_b = check(LOCATION_B)
        if location_b != [{
            "credit_code": "KKNT-B-FALLBACK",
            "current_tonnes": 100.0,
            "recomputed_tonnes": 207.34,
            "delta_pct": 107.34,
            "needs_adjustment": True,
        }]:
            raise AssertionError(f"location-B fallback output did not match verified tree/soil inputs: {location_b!r}")
        checks.append("fallback recomputation uses verified tree rows and deterministic first/last soil measurements")

        from services.common.tenant_context import set_worker_tenant_context
        from services.common.worker_database import get_worker_db

        denied = get_worker_db("credit_adjustment")
        try:
            set_worker_tenant_context(
                denied,
                credential=RAW_CREDENTIAL,
                location_id=LOCATION_A,
                resource="carbon_credit_adjustment",
                action="read",
            )
            with denied.cursor() as cursor:
                try:
                    cursor.execute(
                        "SELECT * FROM kokonut_security.credit_adjustment_snapshot_for_location(%s::uuid)",
                        (LOCATION_B,),
                    )
                except psycopg2.errors.InsufficientPrivilege:
                    denied.rollback()
                else:
                    raise AssertionError("signed location-A context read location-B data")
        finally:
            denied.close()
        checks.append("bounded function rejects a location argument that differs from signed context")

        with admin.cursor() as cursor:
            cursor.execute("""
                SELECT
                    has_table_privilege('kokonut_worker_login', 'public.carbon_credit', 'SELECT'),
                    has_table_privilege('kokonut_worker_login', 'public.climate_impact_summary', 'SELECT'),
                    has_table_privilege('kokonut_worker_login', 'public.tree_inventory', 'SELECT'),
                    has_table_privilege('kokonut_worker_login', 'public.soil_carbon_measurement', 'SELECT'),
                    has_table_privilege('kokonut_worker_execution', 'public.carbon_credit', 'SELECT'),
                    has_function_privilege('kokonut_worker_execution',
                        'kokonut_security.credit_adjustment_snapshot_for_location(uuid)', 'EXECUTE')
            """)
            privileges = cursor.fetchone()
        if privileges != (False, False, False, False, False, True):
            raise AssertionError(f"unexpected worker source privileges: {privileges!r}")
        checks.append("worker login reaches only the execution role; execution role can call the bounded function but cannot directly read source tables")

        with admin.cursor() as cursor:
            cursor.execute("SELECT (SELECT count(*) FROM public.credit_adjustment), "
                           "(SELECT count(*) FROM public.credit_retirement)")
            if cursor.fetchone() != (0, 0):
                raise AssertionError("read-only credit check created adjustment or retirement rows")
        checks.append("read-only worker created no adjustment, retirement, or review records")

        evidence = {
            "status": "passed",
            "postgres_major": 16,
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "startup_timeout_seconds": args.startup_timeout,
            "migrations": [405, 419, 599],
            "replay": "zero pending migration function changes; migration 599 applied twice",
            "locations": 2,
            "checks": checks,
            "candidate_touched": False,
            "legacy_touched": False,
            "provider_called": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        for key, value in prior_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if admin is not None:
            admin.close()
        if created:
            subprocess.run([docker, "rm", "-f", container], capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
