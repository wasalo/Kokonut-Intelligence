#!/usr/bin/env python3
"""Exercise the opt-in API/worker login boundary on disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
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
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")

from services.core.schema_readiness import _require_non_admin_runtime_role  # noqa: E402
from services.migration.runtime_role import (  # noqa: E402
    _ensure_login_role,
    _ensure_worker_runtime_login,
    _role_identifier,
)

POSTGRES_IMAGE = os.environ.get(
    "WORKER_RUNTIME_IDENTITY_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-11-05-recovery/worker-runtime-identity-disposable.json"


def run(command: list[str], *, input_text: str | None = None, secrets_to_redact: tuple[str, ...] = ()) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        for secret in secrets_to_redact:
            details = details.replace(secret, "<redacted>")
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user=user,
        password=password,
        connect_timeout=5,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-worker-runtime-id-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(32)
    api_password = secrets.token_urlsafe(32)
    worker_password = secrets.token_urlsafe(32)
    created = False
    admin_connection = None
    api_connection = None
    worker_connection = None
    checks: list[str] = []
    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={admin_password}",
                "-p",
                "127.0.0.1::5432",
                POSTGRES_IMAGE,
            ],
            secrets_to_redact=(admin_password, api_password, worker_password),
        )
        created = True
        wait_ready(docker, container)
        port_lines = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_lines:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_lines[0].rsplit(":", 1)[1])
        admin_connection = connect(port, "postgres", admin_password)
        admin_connection.autocommit = True
        with admin_connection.cursor() as cursor:
            _ensure_login_role(
                cursor,
                name="kokonut_runtime",
                identifier=_role_identifier("kokonut_runtime", "runtime_user"),
                password=api_password,
            )
            cursor.execute("CREATE TABLE public.worker_identity_probe (id integer PRIMARY KEY, value text NOT NULL)")
            cursor.execute("GRANT USAGE ON SCHEMA public TO kokonut_runtime")
            cursor.execute("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC")
            cursor.execute("GRANT CONNECT ON DATABASE postgres TO kokonut_runtime")
            cursor.execute("GRANT SELECT, INSERT ON public.worker_identity_probe TO kokonut_runtime")
            _ensure_worker_runtime_login(
                cursor,
                name="kokonut_worker_runtime",
                identifier=_role_identifier("kokonut_worker_runtime", "worker_runtime_user"),
                password=worker_password,
                runtime_user="kokonut_runtime",
                runtime_identifier=_role_identifier("kokonut_runtime", "runtime_user"),
            )
            _ensure_worker_runtime_login(
                cursor,
                name="kokonut_worker_runtime",
                identifier=_role_identifier("kokonut_worker_runtime", "worker_runtime_user"),
                password=worker_password,
                runtime_user="kokonut_runtime",
                runtime_identifier=_role_identifier("kokonut_runtime", "runtime_user"),
            )
        checks.append("fresh provisioning and repeat provisioning retain one non-SETtable runtime membership")

        api_connection = connect(port, "kokonut_runtime", api_password)
        api_connection.autocommit = True
        with api_connection.cursor() as cursor:
            _require_non_admin_runtime_role(cursor)
            cursor.execute(
                "SELECT session_user, current_user, has_table_privilege(current_user, "
                "'public.worker_identity_probe', 'SELECT'), "
                "has_table_privilege(current_user, 'public.worker_identity_probe', 'UPDATE')"
            )
            if cursor.fetchone() != ("kokonut_runtime", "kokonut_runtime", True, False):
                raise RuntimeError("API login did not retain its expected identity and ACL")
            cursor.execute("INSERT INTO public.worker_identity_probe VALUES (1, 'api-visible')")
        checks.append("API login passes standalone identity readiness and retains its current runtime ACL")

        worker_connection = connect(port, "kokonut_worker_runtime", worker_password)
        worker_connection.autocommit = True
        with worker_connection.cursor() as cursor:
            _require_non_admin_runtime_role(cursor, expected_parent_role="kokonut_runtime")
            cursor.execute(
                "SELECT session_user, current_user, has_table_privilege(current_user, "
                "'public.worker_identity_probe', 'SELECT'), "
                "has_table_privilege(current_user, 'public.worker_identity_probe', 'INSERT'), "
                "has_table_privilege(current_user, 'public.worker_identity_probe', 'UPDATE')"
            )
            if cursor.fetchone() != ("kokonut_worker_runtime", "kokonut_worker_runtime", True, True, False):
                raise RuntimeError("worker login did not retain only the inherited probe ACL")
            cursor.execute("SELECT value FROM public.worker_identity_probe WHERE id = 1")
            if cursor.fetchone() != ("api-visible",):
                raise RuntimeError("worker could not read a row through inherited API privileges")
            cursor.execute("INSERT INTO public.worker_identity_probe VALUES (2, 'worker-visible')")
            try:
                cursor.execute("SET ROLE kokonut_runtime")
            except errors.InsufficientPrivilege:
                worker_connection.rollback()
            else:
                raise RuntimeError("worker login unexpectedly switched into the API runtime role")
            _require_non_admin_runtime_role(cursor, expected_parent_role="kokonut_runtime")
        checks.append("worker login inherits the API grant, is separately attributable, and cannot SET ROLE to API")

        report = {
            "status": "passed",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "postgres_image": POSTGRES_IMAGE,
            "target": "synthetic disposable PostgreSQL 16; no repository or candidate database",
            "checks": checks,
            "privilege_scope": "identity attribution only; inherited ACL is unchanged; C1 remains open",
        }
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        if worker_connection is not None:
            worker_connection.close()
        if api_connection is not None:
            api_connection.close()
        if admin_connection is not None:
            admin_connection.close()
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
