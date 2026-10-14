#!/usr/bin/env python3
"""Replay migrations 387-389 and exercise tenant authorization in disposable PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MIGRATIONS = ROOT / "schemas" / "postgres"
DEFAULT_EVIDENCE = (
    ROOT
    / "docs"
    / "refactor"
    / "builds"
    / "2026-10-13-recovery"
    / "tenant-grants-migrations-disposable.json"
)
CLI_EVIDENCE = (
    ROOT
    / "docs"
    / "refactor"
    / "builds"
    / "2026-10-13-recovery"
    / "tenant-grants-cli-disposable.json"
)

CHECKS = [
    "ordered 387-389 replay on a minimal compatible PostgreSQL 16 schema",
    "replay of migrations 388 and 389 is idempotent",
    "confirmed Kokonut Network ownership is recorded for both seed locations",
    "owner access succeeds and partner access needs an explicit active share",
    "expired and revoked shares deny partner access",
    "revoked membership, inactive organization, disabled identity, and revoked grant deny access",
    "unverified location and stale ownership verification deny tenant access",
    "legacy NULL-tenant grants remain compatible but still require an enabled identity",
    "Field Collector draft insert requires current create and review grants",
    "Field Collector draft edit requires all three current grants",
    "workflow events require current action grants; draft-edited events require review grants",
    "legacy NULL-tenant grants pass the Field Collector trigger boundary",
    "non-target manual records remain outside the Field Collector tenant triggers",
]


def run(command: list[str], *, input_text: str | None = None, capture: bool = True) -> str:
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if completed.returncode:
        details = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{details}")
    return completed.stdout or ""


def sql(container: str, statement: str) -> str:
    return run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def sql_value(container: str, statement: str) -> str:
    return sql(container, f"{statement.rstrip(';')}\n").strip()


def invoke_operator_cli(arguments: list[str], environment: dict[str, str], *, expected_error: str | None = None) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "services.gateway.operator_cli", *arguments],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expected_error is not None:
        if result.returncode == 0 or expected_error not in result.stderr:
            raise RuntimeError(
                f"operator CLI should reject {' '.join(arguments)} with {expected_error!r}; "
                f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        return ""
    if result.returncode:
        raise RuntimeError(
            f"operator CLI failed ({result.returncode}): {' '.join(arguments)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def run_operator_cli_acceptance(container: str, host_port: str) -> list[str]:
    location_id = "a0000000-0000-0000-0000-000000000001"
    owner_org_id = "a0000000-0000-0000-0000-000000000701"
    partner_org_id = "a0000000-0000-0000-0000-000000000800"
    owner_operator_id = "a0000000-0000-0000-0000-000000000901"
    partner_operator_id = "a0000000-0000-0000-0000-000000000902"
    environment = {
        **os.environ,
        "KOKONUT_ENV": "development",
        "KOKONUT_FEATURE_CLICKHOUSE": "false",
        "PG_HOST": "127.0.0.1",
        "PG_PORT": host_port,
        "PG_DB": "postgres",
        "PG_USER": "postgres",
        "PG_PASSWORD": "disposable-trust-auth",
    }
    checks: list[str] = []

    listing = json.loads(invoke_operator_cli(["list"], environment))
    if not {"identities", "grants", "memberships", "shares"}.issubset(listing):
        raise RuntimeError("operator CLI list omitted one or more expected sections")
    checks.append("operator list reads named database rows")

    membership = json.loads(
        invoke_operator_cli(
            [
                "organization-membership", "grant", "--operator-id", partner_operator_id,
                "--organization-id", partner_org_id, "--membership-role", "operator",
                "--granted-by", "disposable acceptance",
            ],
            environment,
        )
    )
    invoke_operator_cli(
        [
            "organization-membership", "grant", "--operator-id", partner_operator_id,
            "--organization-id", partner_org_id, "--membership-role", "tenant_admin",
            "--granted-by", "disposable acceptance",
        ],
        environment,
        expected_error="active membership has a different role",
    )
    invoke_operator_cli(
        [
            "organization-membership", "revoke", "--membership-id", str(membership["id"]),
            "--revoked-by", "acceptance", "--reason", "exercise CLI lifecycle",
        ],
        environment,
    )
    membership = json.loads(
        invoke_operator_cli(
            [
                "organization-membership", "grant", "--operator-id", partner_operator_id,
                "--organization-id", partner_org_id, "--membership-role", "tenant_admin",
                "--granted-by", "disposable acceptance",
            ],
            environment,
        )
    )
    checks.append("membership grant is idempotent, role changes require revocation, and revoked membership can be regranted")

    share_arguments = [
        "location-share", "grant", "--location-id", location_id,
        "--organization-id", partner_org_id, "--reason", "disposable CLI acceptance",
    ]
    invoke_operator_cli(
        [*share_arguments, "--granted-by-operator-id", partner_operator_id],
        environment,
        expected_error="owner tenant administrator",
    )
    grant_arguments = [
        "grant", "--operator-id", partner_operator_id, "--resource", "farm_activity",
        "--action", "create_draft", "--location-id", location_id,
        "--organization-id", partner_org_id, "--granted-by", "disposable acceptance",
    ]
    invoke_operator_cli(
        grant_arguments, environment, expected_error="explicit location share"
    )
    checks.append("non-owner cannot create a share and partner grant is denied before sharing")

    share = json.loads(
        invoke_operator_cli(
            [*share_arguments, "--granted-by-operator-id", owner_operator_id], environment
        )
    )
    repeated_share = json.loads(
        invoke_operator_cli(
            [*share_arguments, "--granted-by-operator-id", owner_operator_id], environment
        )
    )
    if str(share["id"]) != str(repeated_share["id"]):
        raise RuntimeError("repeating an active share did not return the existing share")
    grant = json.loads(invoke_operator_cli(grant_arguments, environment))
    if str(grant["organization_id"]) != partner_org_id:
        raise RuntimeError("partner CLI grant was not stored under the partner tenant")
    if sql_value(
        container,
        "SELECT operator_scope_grant_allows('a" + "0000000-0000-0000-0000-000000000902', "
        "'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000001')",
    ) != "t":
        raise RuntimeError("shared partner grant was not authorized")
    checks.append("owner share creation is idempotent and enables the partner scope grant")

    invoke_operator_cli(
        [
            "location-share", "revoke", "--share-id", str(share["id"]),
            "--revoked-by-operator-id", owner_operator_id,
            "--reason", "disposable CLI acceptance revocation",
        ],
        environment,
    )
    if sql_value(
        container,
        "SELECT operator_scope_grant_allows('a0000000-0000-0000-0000-000000000902', "
        "'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000001')",
    ) != "f":
        raise RuntimeError("revoking the share did not deny and revoke the partner grant")
    checks.append("share revocation removes dependent authorization")

    share = json.loads(
        invoke_operator_cli(
            [*share_arguments, "--granted-by-operator-id", owner_operator_id], environment
        )
    )
    invoke_operator_cli(grant_arguments, environment)
    invoke_operator_cli(
        [
            "organization-membership", "revoke", "--membership-id", str(membership["id"]),
            "--revoked-by", "acceptance", "--reason", "verify dependent grant revocation",
        ],
        environment,
    )
    if sql_value(
        container,
        "SELECT operator_scope_grant_allows('a0000000-0000-0000-0000-000000000902', "
        "'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000001')",
    ) != "f":
        raise RuntimeError("membership revocation did not deny the partner grant")
    checks.append("membership revocation removes dependent authorization")

    sql(
        container,
        """INSERT INTO operator_scope_grant
                 (operator_id, resource, action, location_id, granted_by)
             VALUES ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'verify',
                     'a0000000-0000-0000-0000-000000000001', 'legacy fixture')""",
    )
    converted = json.loads(
        invoke_operator_cli(
            [
                "grant", "--operator-id", owner_operator_id, "--resource", "farm_activity",
                "--action", "verify", "--location-id", location_id,
                "--organization-id", owner_org_id, "--granted-by", "disposable acceptance",
            ],
            environment,
        )
    )
    if str(converted["organization_id"]) != owner_org_id:
        raise RuntimeError("legacy NULL-tenant grant was not converted to the verified owner")
    if sql_value(
        container,
        "SELECT operator_scope_grant_allows('a0000000-0000-0000-0000-000000000901', "
        "'farm_activity', 'verify', 'a0000000-0000-0000-0000-000000000001')",
    ) != "t":
        raise RuntimeError("converted owner grant is not authorized")
    checks.append("legacy NULL-tenant owner grant converts in place and remains authorized")
    return checks


def wait_until_ready(container: str) -> None:
    deadline = time.monotonic() + 60
    last_error = ""
    while time.monotonic() < deadline:
        check = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if check.returncode == 0:
            return
        last_error = check.stdout.strip()
        time.sleep(1)
    raise RuntimeError(f"disposable PostgreSQL did not become ready: {last_error}")


def wait_until_host_port_ready(host_port: str) -> None:
    deadline = time.monotonic() + 30
    last_error = "connection refused"
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", int(host_port)), timeout=1):
                return
        except OSError as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"disposable PostgreSQL loopback port did not become ready: {last_error}")


def choose_loopback_port() -> str:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return str(listener.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="sanitized JSON evidence destination (defaults by acceptance mode)",
    )
    parser.add_argument(
        "--operator-cli",
        action="store_true",
        help="also exercise the operator CLI over a loopback-only port on a dedicated disposable Docker bridge",
    )
    args = parser.parse_args()

    container = f"kokonut-tenant-grants-check-{uuid.uuid4().hex[:10]}"
    network = f"kokonut-tenant-grants-net-{uuid.uuid4().hex[:10]}"
    started = False
    network_started = False
    host_port: str | None = None
    output_path = args.output or (CLI_EVIDENCE if args.operator_cli else DEFAULT_EVIDENCE)
    try:
        docker_run = ["docker", "run", "--detach", "--rm", "--name", container]
        if args.operator_cli:
            host_port = choose_loopback_port()
            run(["docker", "network", "create", "--label", "kokonut.disposable=true", network])
            network_started = True
            docker_run.extend(["--network", network, "--publish", f"127.0.0.1:{host_port}:5432"])
        else:
            docker_run.extend(["--network", "none"])
        docker_run.extend(["--env", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16"])
        run(
            docker_run
        )
        started = True
        wait_until_ready(container)
        if args.operator_cli:
            published = run(["docker", "port", container, "5432/tcp"]).strip()
            if not published.startswith("127.0.0.1:") or not published.endswith(f":{host_port}"):
                raise RuntimeError(f"disposable database port is not bound to the reserved loopback address: {published}")
            wait_until_host_port_ready(host_port)

        sql(container, (FIXTURES / "tenant_grants_migrations_387_389_disposable.sql").read_text())
        for migration in (
            "387_kokonut_network_tenant_ownership.sql",
            "388_tenant_aware_operator_grants.sql",
            "389_tenant_aware_field_collector_write_guards.sql",
        ):
            sql(container, (MIGRATIONS / migration).read_text())

        # Repeat the new migration pair to catch non-idempotent DDL or seed behavior.
        for migration in (
            "388_tenant_aware_operator_grants.sql",
            "389_tenant_aware_field_collector_write_guards.sql",
        ):
            sql(container, (MIGRATIONS / migration).read_text())

        sql(container, (FIXTURES / "tenant_grants_migrations_387_389_assertions.sql").read_text())

        cli_checks = run_operator_cli_acceptance(container, host_port) if host_port else []
        acceptance_checks = CHECKS + cli_checks

        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": (
                "PostgreSQL 16 disposable container on a dedicated Docker bridge with a loopback-only host port; no external requests are made"
                if args.operator_cli
                else "PostgreSQL 16 disposable container with Docker network disabled"
            ),
            "candidate_database_touched": False,
            "migrations": [
                "387_kokonut_network_tenant_ownership.sql",
                "388_tenant_aware_operator_grants.sql",
                "389_tenant_aware_field_collector_write_guards.sql",
            ],
            "idempotency_replay": [
                "388_tenant_aware_operator_grants.sql",
                "389_tenant_aware_field_collector_write_guards.sql",
            ],
            "operator_cli_checks": cli_checks,
            "checks": acceptance_checks,
            "scope_limit": (
                "Uses a minimal compatible schema for the touched tables. It does not replay "
                "the full repository migration chain or test migrations 384-385 trigger interaction."
            ),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - report disposable acceptance failures plainly.
        print(f"DISPOSABLE TENANT GRANT CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        if network_started:
            subprocess.run(
                ["docker", "network", "rm", network],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
