#!/usr/bin/env python3
"""Exercise farm-activity role grant provisioning on disposable PostgreSQL."""

from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("KOKONUT_ENV", "development")
# This isolated check supplies its own disposable PostgreSQL connection and
# must not decrypt the repository's project secrets during module import.
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")

from services.gateway import operator_cli  # noqa: E402

DATABASE_IMAGE = "postgres:16"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/farm-activity-role-grant-postgres.json"


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result


def _docker() -> str:
    executable = shutil.which("docker")
    if executable:
        return executable
    desktop_cli = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if desktop_cli.is_file():
        return str(desktop_cli)
    raise RuntimeError("Docker CLI is unavailable")


def _wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    successes = 0
    while time.monotonic() < deadline:
        result = _run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            check=False,
        )
        if result.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not remain healthy")


def _psql(docker: str, container: str, sql: str) -> None:
    process = subprocess.run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres"],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        details = "\n".join(part for part in (process.stdout, process.stderr) if part)
        raise RuntimeError(f"disposable SQL failed:\n{details}")


def _fixture_sql() -> str:
    return """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE organization (id uuid PRIMARY KEY, status text NOT NULL);
CREATE TABLE operator_identity (id uuid PRIMARY KEY, enabled boolean NOT NULL);
CREATE TABLE location (id uuid PRIMARY KEY, organization_id uuid);
CREATE TABLE location_tenant_owner_verification (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), location_id uuid NOT NULL,
    organization_id uuid NOT NULL, revoked_at timestamptz
);
CREATE TABLE operator_organization_membership (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), operator_id uuid NOT NULL,
    organization_id uuid NOT NULL, revoked_at timestamptz
);
CREATE TABLE location_organization_share (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), location_id uuid NOT NULL,
    organization_id uuid NOT NULL, revoked_at timestamptz, expires_at timestamptz
);
CREATE TABLE operator_scope_grant (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), operator_id uuid NOT NULL,
    resource text NOT NULL, action text NOT NULL, location_id uuid NOT NULL,
    organization_id uuid, granted_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT NOW(),
    revoked_at timestamptz
);
CREATE UNIQUE INDEX uq_operator_scope_grant_active
    ON operator_scope_grant(operator_id, resource, action, location_id)
    WHERE revoked_at IS NULL;

INSERT INTO organization (id, status) VALUES
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'active'),
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'active');
INSERT INTO operator_identity (id, enabled) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', TRUE),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', TRUE),
 ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', TRUE);
INSERT INTO location (id, organization_id) VALUES
 ('11111111-1111-4111-8111-111111111111', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO location_tenant_owner_verification (location_id, organization_id) VALUES
 ('11111111-1111-4111-8111-111111111111', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO operator_organization_membership (operator_id, organization_id) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'),
 ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO location_organization_share (location_id, organization_id, expires_at) VALUES
 ('11111111-1111-4111-8111-111111111111', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', NOW() + INTERVAL '1 day');
INSERT INTO operator_scope_grant (
    operator_id, resource, action, location_id, organization_id, granted_by
) VALUES (
    'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'farm_activity', 'read',
    '11111111-1111-4111-8111-111111111111', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    'existing-conflicting-tenant'
);
"""


class _Harness:
    def __init__(self, host_port: int, password: str):
        self.host_port = host_port
        self.password = password
        self.output: list[dict] = []
        self.original_connection = operator_cli.get_connection
        self.original_print_json = operator_cli.print_json

    def __enter__(self):
        import psycopg2

        from services.common.database import DatabaseConnection

        def connection_factory():
            return DatabaseConnection(
                psycopg2.connect(
                    host="127.0.0.1",
                    port=self.host_port,
                    dbname="postgres",
                    user="postgres",
                    password=self.password,
                    connect_timeout=5,
                )
            )

        operator_cli.get_connection = connection_factory
        operator_cli.print_json = self.output.append
        return self

    def __exit__(self, *_args):
        operator_cli.get_connection = self.original_connection
        operator_cli.print_json = self.original_print_json


def _grant(harness: _Harness, *, role: str, operator_id: str, organization_id: str) -> None:
    operator_cli.grant_farm_activity_role(
        SimpleNamespace(
            role=role,
            operator_id=operator_id,
            organization_id=organization_id,
            location_id="11111111-1111-4111-8111-111111111111",
            granted_by="synthetic-tenant-admin",
        )
    )


def _count(docker: str, container: str, query: str) -> int:
    result = _run(
        [docker, "exec", container, "psql", "-X", "-At", "-U", "postgres", "-c", query]
    )
    return int(result.stdout.strip())


def main() -> int:
    docker = _docker()
    suffix = secrets.token_hex(6)
    container = f"kokonut-role-grant-{suffix}"
    network = f"kokonut-role-grant-{suffix}"
    password = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
    container_started = False
    network_created = False
    result = {
        "date": "2026-10-16",
        "database": "disposable PostgreSQL 16; no volume; dedicated Docker network; loopback-only port",
        "checks": [],
    }
    try:
        # Docker Desktop does not expose published ports on --internal networks.
        # This dedicated bridge carries only the temporary database container;
        # the only host ingress is an ephemeral port bound to 127.0.0.1.
        _run([docker, "network", "create", network])
        network_created = True
        _run(
            [
                docker,
                "run",
                "-d",
                "--name",
                container,
                "--network",
                network,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-p",
                "127.0.0.1::5432",
                DATABASE_IMAGE,
            ]
        )
        container_started = True
        _wait_ready(docker, container)
        port_data = json.loads(
            _run(
                [
                    docker,
                    "inspect",
                    "--format",
                    "{{json .NetworkSettings.Ports}}",
                    container,
                ]
            ).stdout
        )
        bindings = port_data.get("5432/tcp") or []
        loopback_binding = next(
            (binding for binding in bindings if binding.get("HostIp") == "127.0.0.1"),
            None,
        )
        if loopback_binding is None:
            raise RuntimeError("disposable PostgreSQL has no loopback-only host port binding")
        host_port = int(loopback_binding["HostPort"])
        _psql(docker, container, _fixture_sql())

        with _Harness(host_port, password) as harness:
            owner_operator = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            owner_org = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            partner_operator = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
            partner_org = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

            _grant(harness, role="analyst", operator_id=owner_operator, organization_id=owner_org)
            _grant(harness, role="analyst", operator_id=owner_operator, organization_id=owner_org)
            if _count(docker, container, "SELECT COUNT(*) FROM operator_scope_grant WHERE operator_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'") != 2:
                raise AssertionError("role grant retry was not idempotent")
            result["checks"].append("verified-owner role grants are tenant-qualified and idempotent")

            _grant(harness, role="finance", operator_id=partner_operator, organization_id=partner_org)
            if _count(docker, container, "SELECT COUNT(*) FROM operator_scope_grant WHERE operator_id = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd' AND organization_id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'") != 2:
                raise AssertionError("active owner share did not issue partner-tenant grants")
            result["checks"].append("active owner-issued location share permits partner-tenant role grants")

            before = _count(docker, container, "SELECT COUNT(*) FROM operator_scope_grant WHERE operator_id = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'")
            try:
                _grant(harness, role="field_worker", operator_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", organization_id=owner_org)
            except ValueError as exc:
                if "different tenant" not in str(exc):
                    raise
            else:
                raise AssertionError("conflicting tenant grant was accepted")
            after = _count(docker, container, "SELECT COUNT(*) FROM operator_scope_grant WHERE operator_id = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'")
            if before != after:
                raise AssertionError("partial role grants survived a conflicting tenant row")
            result["checks"].append("conflicting existing tenant grant aborts the bundle without partial writes")

            before = _count(docker, container, "SELECT COUNT(*) FROM operator_scope_grant WHERE operator_id = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'")
            _run(
                [docker, "exec", container, "psql", "-X", "-q", "-U", "postgres", "-c",
                 "UPDATE location_organization_share SET expires_at = NOW() - INTERVAL '1 second' WHERE organization_id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'"]
            )
            try:
                _grant(harness, role="auditor", operator_id=partner_operator, organization_id=partner_org)
            except ValueError as exc:
                if "active location share" not in str(exc):
                    raise
            else:
                raise AssertionError("expired location share was accepted")
            after = _count(docker, container, "SELECT COUNT(*) FROM operator_scope_grant WHERE operator_id = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'")
            if before != after:
                raise AssertionError("expired-share role grant left rows")
            result["checks"].append("expired location share is denied before any role grant")

        result["result"] = "passed"
        print(json.dumps(result, indent=2))
        DEFAULT_OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
        return 0
    finally:
        if container_started:
            _run([docker, "rm", "-f", container], check=False)
        if network_created:
            _run([docker, "network", "rm", network], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
