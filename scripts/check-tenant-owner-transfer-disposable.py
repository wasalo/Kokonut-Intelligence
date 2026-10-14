#!/usr/bin/env python3
"""Accept tenant transfer and transaction-local context in disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "tenant_grants_migrations_387_389_disposable.sql"
MIGRATIONS = ROOT / "schemas" / "postgres"
EVIDENCE = (
    ROOT
    / "docs"
    / "refactor"
    / "builds"
    / "2026-10-14-recovery"
    / "tenant-owner-transfer-context-disposable.json"
)

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SECOND_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
UNVERIFIED_LOCATION_ID = "a0000000-0000-0000-0000-000000000003"
OWNER_ORG_ID = "a0000000-0000-0000-0000-000000000701"
PARTNER_ORG_ID = "a0000000-0000-0000-0000-000000000800"
TARGET_ORG_ID = "a0000000-0000-0000-0000-000000000801"
ALTERNATE_ORG_ID = "a0000000-0000-0000-0000-000000000802"
OWNER_ADMIN_ID = "a0000000-0000-0000-0000-000000000901"
PARTNER_ADMIN_ID = "a0000000-0000-0000-0000-000000000902"
LEGACY_OPERATOR_ID = "a0000000-0000-0000-0000-000000000903"
TARGET_ADMIN_ID = "a0000000-0000-0000-0000-000000000904"
TARGET_OPERATOR_ID = "a0000000-0000-0000-0000-000000000905"
FARM_ID = "a0000000-0000-0000-0000-000000000099"
REPORT_ID = "a0000000-0000-0000-0000-000000000098"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def docker_sql(container: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X",
            "-v", "ON_ERROR_STOP=1", "-t", "-A",
            "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def sql_value(container: str, statement: str) -> str:
    return docker_sql(container, statement.rstrip(";") + "\n").strip()


def assert_sql(container: str, statement: str, expected: str, label: str) -> None:
    actual = sql_value(container, statement)
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, received {actual!r}")


def expect_sql_failure(container: str, statement: str, expected_error: str, label: str) -> None:
    result = subprocess.run(
        [
            "docker", "exec", "-i", container, "psql", "-X",
            "-v", "ON_ERROR_STOP=1", "-t", "-A",
            "-U", "postgres", "-d", "postgres",
        ],
        input=statement,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0 or expected_error not in result.stderr:
        raise RuntimeError(
            f"{label}: expected SQL failure containing {expected_error!r}; "
            f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
        )


def invoke_cli(
    arguments: list[str],
    environment: dict[str, str],
    *,
    cwd: Path,
    expected_error: str | None = None,
) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "services.gateway.operator_cli", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expected_error is not None:
        if result.returncode == 0 or expected_error not in result.stderr:
            raise RuntimeError(
                f"CLI should reject {' '.join(arguments)} with {expected_error!r}; "
                f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        return ""
    if result.returncode:
        raise RuntimeError(
            f"CLI failed ({result.returncode}): {' '.join(arguments)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def run_context_acceptance(cli_root: Path, environment: dict[str, str]) -> list[str]:
    source = f'''
import json
import psycopg2
from services.common.database import get_db
from services.common.tenant_context import TenantContextDenied, set_operator_tenant_context
from services.gateway import operator_review

conn = get_db()
try:
    owner = set_operator_tenant_context(
        conn, operator_id='{OWNER_ADMIN_ID}', location_id='{LOCATION_ID}',
        resource='farm_activity', action='read'
    )
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('kokonut.tenant_id', true), current_setting('kokonut.location_id', true), current_setting('kokonut.actor_id', true), current_setting('kokonut.actor_type', true)")
        owner_settings = cur.fetchone()

    partner = set_operator_tenant_context(
        conn, operator_id='{PARTNER_ADMIN_ID}', location_id='{LOCATION_ID}',
        resource='farm_activity', action='review'
    )
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('kokonut.tenant_id', true), current_setting('kokonut.location_id', true), current_setting('kokonut.actor_id', true), current_setting('kokonut.actor_type', true)")
        partner_settings = cur.fetchone()

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO organization
                   (id, org_key, name, org_type, status, source_system, source_id, source_raw)
               VALUES (%s, 'synthetic-alternate-tenant', 'Synthetic Alternate Tenant',
                       'collective', 'active', 'acceptance', 'alternate-tenant', '{{}}')""",
            ('{ALTERNATE_ORG_ID}',),
        )
        cur.execute(
            """INSERT INTO operator_organization_membership
                   (operator_id, organization_id, membership_role, granted_by)
               VALUES (%s, %s, 'operator', 'synthetic acceptance')""",
            ('{PARTNER_ADMIN_ID}', '{ALTERNATE_ORG_ID}'),
        )
        cur.execute(
            """INSERT INTO location_organization_share
                   (location_id, organization_id, granted_by_operator_id, reason)
               VALUES (%s, %s, %s, 'synthetic alternate tenant context')""",
            ('{LOCATION_ID}', '{ALTERNATE_ORG_ID}', '{OWNER_ADMIN_ID}'),
        )
    with conn.cursor() as cur:
        cur.execute("SAVEPOINT tenant_grant_ambiguity")
        try:
            cur.execute(
                """INSERT INTO operator_scope_grant
                       (operator_id, resource, action, location_id, organization_id, granted_by)
                   VALUES (%s, 'farm_activity', 'review', %s, %s, 'synthetic alternate tenant')""",
                ('{PARTNER_ADMIN_ID}', '{LOCATION_ID}', '{ALTERNATE_ORG_ID}'),
            )
        except psycopg2.errors.UniqueViolation as exc:
            duplicate_grant_rejected = (
                exc.diag.constraint_name == 'uq_operator_scope_grant_active'
            )
            cur.execute("ROLLBACK TO SAVEPOINT tenant_grant_ambiguity")
        else:
            duplicate_grant_rejected = False
        cur.execute("RELEASE SAVEPOINT tenant_grant_ambiguity")
        cur.execute("SELECT current_setting('kokonut.tenant_id', true), current_setting('kokonut.location_id', true), current_setting('kokonut.actor_id', true), current_setting('kokonut.actor_type', true)")
        after_duplicate_settings = cur.fetchone()

    try:
        set_operator_tenant_context(
            conn, operator_id='{LEGACY_OPERATOR_ID}', location_id='{LOCATION_ID}',
            resource='farm_activity', action='legacy_read'
        )
    except TenantContextDenied:
        denied = True
    else:
        denied = False
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(NULLIF(current_setting('kokonut.tenant_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.location_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_type', true), ''), '')")
        denied_settings = cur.fetchone()

    set_operator_tenant_context(
        conn, operator_id='{OWNER_ADMIN_ID}', location_id='{LOCATION_ID}',
        resource='farm_activity', action='read'
    )
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(NULLIF(current_setting('kokonut.tenant_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.location_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_type', true), ''), '')")
        committed_settings = cur.fetchone()

    report_events = []
    class CursorProxy:
        def __init__(self, owner, cursor):
            self.owner = owner
            self.cursor = cursor
        def __getattr__(self, name):
            return getattr(self.cursor, name)
        def __enter__(self):
            self.cursor.__enter__()
            return self
        def __exit__(self, *args):
            return self.cursor.__exit__(*args)
        def execute(self, sql, params=None):
            report_events.append(('sql', id(self.owner), sql))
            return self.cursor.execute(sql, params)

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
        @property
        def autocommit(self):
            return self.connection.autocommit
        def cursor(self, *args, **kwargs):
            return CursorProxy(self, self.connection.cursor(*args, **kwargs))
        def rollback(self):
            return self.connection.rollback()
        def close(self):
            # Reuse only this disposable connection between service calls so
            # transaction-local reset can be inspected after each rollback.
            return None

    report_conn = ConnectionProxy(get_db())
    report_contexts = []
    original_set_context = operator_review.set_operator_tenant_context
    def capture_context(connection, **kwargs):
        context = original_set_context(connection, **kwargs)
        report_contexts.append((id(connection), kwargs))
        report_events.append(('context', id(connection), kwargs['action']))
        return context
    operator_review.set_operator_tenant_context = capture_context
    try:
        owner_reports = operator_review.list_submitted_reports(
            '{OWNER_ADMIN_ID}', '{LOCATION_ID}', connection_factory=lambda: report_conn
        )
        with report_conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(current_setting('kokonut.tenant_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.location_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_type', true), ''), '')")
            after_owner_queue = cur.fetchone()
        report_conn.rollback()

        partner_report = operator_review.get_submitted_report(
            '{PARTNER_ADMIN_ID}', '{REPORT_ID}', '{LOCATION_ID}',
            connection_factory=lambda: report_conn,
        )
        with report_conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(current_setting('kokonut.tenant_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.location_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_type', true), ''), '')")
            after_partner_detail = cur.fetchone()
        report_conn.rollback()

        try:
            operator_review.list_submitted_reports(
                '{LEGACY_OPERATOR_ID}', '{LOCATION_ID}', connection_factory=lambda: report_conn
            )
        except TenantContextDenied:
            legacy_report_denied = True
        else:
            legacy_report_denied = False
        with report_conn.cursor() as cur:
            cur.execute("SELECT COALESCE(NULLIF(current_setting('kokonut.tenant_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.location_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_id', true), ''), ''), COALESCE(NULLIF(current_setting('kokonut.actor_type', true), ''), '')")
            after_legacy_denial = cur.fetchone()
    finally:
        report_conn.rollback()
        report_conn.connection.close()
finally:
    conn.rollback()
    conn.close()

expected_owner = ('{OWNER_ORG_ID}', '{LOCATION_ID}', '{OWNER_ADMIN_ID}', 'operator')
expected_partner = ('{PARTNER_ORG_ID}', '{LOCATION_ID}', '{PARTNER_ADMIN_ID}', 'operator')
empty = ('', '', '', '')
if owner.tenant_id != '{OWNER_ORG_ID}' or owner_settings != expected_owner:
    raise RuntimeError(f'owner context mismatch: {{owner!r}} {{owner_settings!r}}')
if partner.tenant_id != '{PARTNER_ORG_ID}' or partner_settings != expected_partner:
    raise RuntimeError(f'partner context mismatch: {{partner!r}} {{partner_settings!r}}')
if not duplicate_grant_rejected or after_duplicate_settings != expected_partner:
    raise RuntimeError(f'database failed to reject an ambiguous grant without changing context: {{duplicate_grant_rejected!r}} {{after_duplicate_settings!r}}')
if not denied or denied_settings != empty:
    raise RuntimeError(f'legacy grant was not denied with cleared context: {{denied!r}} {{denied_settings!r}}')
if committed_settings != empty:
    raise RuntimeError(f'transaction-local context survived commit: {{committed_settings!r}}')
expected_owner_report = ('{OWNER_ORG_ID}', '{LOCATION_ID}', '{OWNER_ADMIN_ID}', 'operator')
expected_partner_report = ('{PARTNER_ORG_ID}', '{LOCATION_ID}', '{PARTNER_ADMIN_ID}', 'operator')
if len(owner_reports) != 1 or owner_reports[0].get('id') != '{REPORT_ID}':
    raise RuntimeError(f'owner report queue query failed: {{owner_reports!r}}')
if partner_report is None or partner_report.get('id') != '{REPORT_ID}' or partner_report.get('report_data') != {{'synthetic': True}}:
    raise RuntimeError(f'explicitly shared report detail query failed: {{partner_report!r}}')
if [row[1] for row in report_contexts] != [
    {{'operator_id': '{OWNER_ADMIN_ID}', 'location_id': '{LOCATION_ID}', 'resource': 'report_snapshot_review', 'action': 'read'}},
    {{'operator_id': '{PARTNER_ADMIN_ID}', 'location_id': '{LOCATION_ID}', 'resource': 'report_snapshot_review', 'action': 'read'}},
]:
    raise RuntimeError(f'report context was not set for owner and share: {{report_contexts!r}}')
if any(row[0] != id(report_conn) for row in report_contexts):
    raise RuntimeError(f'tenant context used a different connection: {{report_contexts!r}}')
markers = [index for index, event in enumerate(report_events) if event[0] == 'context']
queries = [index for index, event in enumerate(report_events) if event[0] == 'sql' and 'FROM report_snapshot AS rs' in event[2]]
if len(markers) != 2 or len(queries) != 2 or any(marker >= query for marker, query in zip(markers, queries)):
    raise RuntimeError(f'report context was not set before both protected queries: {{markers!r}} {{queries!r}}')
if after_owner_queue != empty or after_partner_detail != empty or not legacy_report_denied or after_legacy_denial != empty:
    raise RuntimeError(f'report query context leaked or legacy grant was accepted: {{after_owner_queue!r}} {{after_partner_detail!r}} {{legacy_report_denied!r}} {{after_legacy_denial!r}}')
print(json.dumps({{'result': 'passed', 'owner': owner_settings, 'partner': partner_settings, 'ambiguous_grant_rejected': duplicate_grant_rejected, 'after_duplicate': after_duplicate_settings, 'denied_context': denied_settings, 'after_commit': committed_settings, 'report_contexts': [row[1] for row in report_contexts], 'report_cleanup': [after_owner_queue, after_partner_detail, after_legacy_denial], 'legacy_report_denied': legacy_report_denied}}))
'''
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=cli_root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "tenant-context acceptance failed\n"
            f"{result.stdout}\n{result.stderr}"
        )
    report = json.loads(result.stdout)
    if report.get("result") != "passed":
        raise RuntimeError(f"unexpected tenant-context result: {report!r}")
    return [
        "owner and explicitly shared tenant-qualified grants set database-derived context",
        "database uniqueness guard prevents ambiguous tenant-grant context",
        "legacy NULL-tenant grants are denied and previous local context is cleared",
        "transaction-local tenant context resets at commit on the reused connection",
        "report-review owner and shared-grant queries set context before protected reads on one connection",
        "report-review reads clear tenant context after transaction rollback",
        "legacy location-only report-review grants are denied before query execution",
    ]


def wait_ready(container: str) -> None:
    deadline = time.monotonic() + 90
    last = ""
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode == 0:
            return
        last = result.stdout.strip()
        time.sleep(1)
    raise RuntimeError(f"disposable PostgreSQL did not become ready: {last}")


def loopback_port_ready(port: int) -> None:
    deadline = time.monotonic() + 30
    last = "connection refused"
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError as exc:
            last = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"loopback database port did not become ready: {last}")


def choose_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def add_fixture_rows(container: str) -> None:
    docker_sql(
        container,
        f"""
        INSERT INTO organization (id, org_key, name, org_type, status)
        VALUES ('{TARGET_ORG_ID}', 'transfer-target', 'Transfer Target', 'collective', 'active');
        INSERT INTO operator_identity (id, issuer, subject, display_name, enabled) VALUES
          ('{TARGET_ADMIN_ID}', 'https://issuer.example.test', 'target-admin', 'Target Admin', TRUE),
          ('{TARGET_OPERATOR_ID}', 'https://issuer.example.test', 'target-operator', 'Target Operator', TRUE);
        INSERT INTO operator_organization_membership
            (operator_id, organization_id, membership_role, granted_by)
        VALUES
          ('{OWNER_ADMIN_ID}', '{OWNER_ORG_ID}', 'tenant_admin', 'disposable acceptance'),
          ('{PARTNER_ADMIN_ID}', '{PARTNER_ORG_ID}', 'tenant_admin', 'disposable acceptance'),
          ('{TARGET_ADMIN_ID}', '{TARGET_ORG_ID}', 'tenant_admin', 'disposable acceptance'),
          ('{TARGET_OPERATOR_ID}', '{TARGET_ORG_ID}', 'operator', 'disposable acceptance');
        INSERT INTO farm (id) VALUES ('{FARM_ID}');
        UPDATE organization_member
           SET farm_id = '{FARM_ID}'
         WHERE location_id = '{LOCATION_ID}'
           AND organization_id = '{OWNER_ORG_ID}'
           AND membership_type = 'owned' AND role = 'primary' AND status = 'active';
        INSERT INTO location_organization_share
            (location_id, organization_id, granted_by_operator_id, reason)
        VALUES ('{LOCATION_ID}', '{PARTNER_ORG_ID}', '{OWNER_ADMIN_ID}', 'synthetic transfer share');
        INSERT INTO operator_scope_grant
            (operator_id, resource, action, location_id, organization_id, granted_by)
        VALUES
          ('{OWNER_ADMIN_ID}', 'farm_activity', 'read', '{LOCATION_ID}', '{OWNER_ORG_ID}', 'fixture'),
          ('{PARTNER_ADMIN_ID}', 'farm_activity', 'review', '{LOCATION_ID}', '{PARTNER_ORG_ID}', 'fixture'),
          ('{LEGACY_OPERATOR_ID}', 'farm_activity', 'legacy_read', '{LOCATION_ID}', NULL, 'fixture');
        INSERT INTO operator_scope_grant
            (operator_id, resource, action, location_id, organization_id, granted_by)
        VALUES
          ('{OWNER_ADMIN_ID}', 'report_snapshot_review', 'read', '{LOCATION_ID}', '{OWNER_ORG_ID}', 'fixture'),
          ('{PARTNER_ADMIN_ID}', 'report_snapshot_review', 'read', '{LOCATION_ID}', '{PARTNER_ORG_ID}', 'fixture');
        INSERT INTO report_snapshot
            (id, report_name, report_type, location_id, report_data, snapshot_hash, status)
        VALUES
          ('{REPORT_ID}', 'Synthetic tenant report', 'impact', '{LOCATION_ID}', '{{"synthetic": true}}', 'synthetic-hash', 'submitted');
        """,
    )


def run_acceptance(container: str, port: int, cli_root: Path) -> list[str]:
    env = {
        **os.environ,
        "KOKONUT_ENV": "development",
        "KOKONUT_FEATURE_CLICKHOUSE": "false",
        "PG_HOST": "127.0.0.1",
        "PG_PORT": str(port),
        "PG_DB": "postgres",
        "PG_USER": "postgres",
        "PG_PASSWORD": "disposable-trust-auth",
    }
    checks: list[str] = []

    # Running copied source from a clean temporary root keeps the CLI from
    # discovering and decrypting the repository's real .env.sops. All DB
    # credentials below are synthetic and point only at the disposable DB.
    env["PYTHONPATH"] = str(cli_root)

    def cli(arguments: list[str], *, expected_error: str | None = None) -> str:
        return invoke_cli(arguments, env, cwd=cli_root, expected_error=expected_error)

    listing = json.loads(cli(["list"]))
    if not {"identities", "grants", "memberships", "shares", "tenant_transfers"}.issubset(listing):
        raise RuntimeError("operator list did not include all expected sections")
    checks.append("operator CLI lists tenant-transfer history")
    checks.extend(run_context_acceptance(cli_root, env))

    for operator_id, resource, action in (
        (OWNER_ADMIN_ID, "farm_activity", "read"),
        (PARTNER_ADMIN_ID, "farm_activity", "review"),
        (LEGACY_OPERATOR_ID, "farm_activity", "legacy_read"),
    ):
        assert_sql(
            container,
            f"SELECT operator_scope_grant_allows('{operator_id}', '{resource}', '{action}', '{LOCATION_ID}')",
            "t",
            f"pre-transfer authorization for {operator_id}",
        )

    request_output = cli(
        [
            "tenant-transfer", "request", "--location-id", LOCATION_ID,
            "--target-organization-id", TARGET_ORG_ID,
            "--requested-by-operator-id", OWNER_ADMIN_ID,
            "--request-reference", "CASE-390-PRIMARY",
            "--reason", "Reviewed synthetic ownership transfer",
        ],
    )
    transfer_id = str(json.loads(request_output)["id"])
    assert_sql(container, f"SELECT organization_id FROM location WHERE id = '{LOCATION_ID}'", OWNER_ORG_ID, "pending request leaves location owner unchanged")
    assert_sql(container, f"SELECT status FROM location_tenant_transfer WHERE id = '{transfer_id}'", "pending", "transfer begins pending")
    assert_sql(
        container,
        f"SELECT count(*) FROM operator_scope_grant WHERE location_id = '{LOCATION_ID}' AND revoked_at IS NULL",
        "5",
        "pending request leaves grants unchanged",
    )
    checks.append("pending transfer preserves owner, shares, and all existing grants")

    cli(
        [
            "tenant-transfer", "accept", "--transfer-id", transfer_id,
            "--accepting-operator-id", OWNER_ADMIN_ID,
            "--acceptance-reference", "APPROVAL-390-SELF",
        ],
        expected_error="transfer request and acceptance require different operators",
    )
    cli(
        [
            "tenant-transfer", "accept", "--transfer-id", transfer_id,
            "--accepting-operator-id", TARGET_OPERATOR_ID,
            "--acceptance-reference", "APPROVAL-390-NONADMIN",
        ],
        expected_error="acceptance requires an enabled target-owner tenant administrator",
    )
    checks.append("self-approval and non-admin target approval are denied")

    stale_transfer = str(
        json.loads(
            cli(
                [
                    "tenant-transfer", "request", "--location-id", SECOND_LOCATION_ID,
                    "--target-organization-id", TARGET_ORG_ID,
                    "--requested-by-operator-id", OWNER_ADMIN_ID,
                    "--request-reference", "CASE-390-STALE",
                    "--reason", "Synthetic stale relationship check",
                ],
            )
        )["id"]
    )
    docker_sql(
        container,
        f"""INSERT INTO organization_member
             (organization_id, location_id, membership_type, role, status, metadata)
           VALUES ('{OWNER_ORG_ID}', '{SECOND_LOCATION_ID}', 'owned', 'satellite', 'active', '{{}}');""",
    )
    cli(
        [
            "tenant-transfer", "accept", "--transfer-id", stale_transfer,
            "--accepting-operator-id", TARGET_ADMIN_ID,
            "--acceptance-reference", "APPROVAL-390-STALE",
        ],
        expected_error="owner relationships changed after the transfer was requested",
    )
    cli(
        [
            "tenant-transfer", "cancel", "--transfer-id", stale_transfer,
            "--cancelling-operator-id", OWNER_ADMIN_ID,
            "--reason", "Cancel after owner relationship changed",
        ],
    )
    docker_sql(
        container,
        f"""DELETE FROM organization_member
             WHERE location_id = '{SECOND_LOCATION_ID}'
               AND organization_id = '{OWNER_ORG_ID}'
               AND membership_type = 'owned' AND role = 'satellite';""",
    )
    checks.append("changed owner-relationship snapshot blocks acceptance and can be cancelled")

    docker_sql(
        container,
        f"""INSERT INTO organization_member
             (organization_id, location_id, membership_type, role, status, metadata)
           VALUES ('{TARGET_ORG_ID}', '{SECOND_LOCATION_ID}', 'owned', 'satellite', 'active', '{{}}');""",
    )
    cli(
        [
            "tenant-transfer", "request", "--location-id", SECOND_LOCATION_ID,
            "--target-organization-id", TARGET_ORG_ID,
            "--requested-by-operator-id", OWNER_ADMIN_ID,
            "--request-reference", "CASE-390-CONFLICT",
            "--reason", "Synthetic conflicting ownership check",
        ],
        expected_error="conflicting active owner relationships must be reconciled first",
    )
    docker_sql(
        container,
        f"""DELETE FROM organization_member
             WHERE location_id = '{SECOND_LOCATION_ID}'
               AND organization_id = '{TARGET_ORG_ID}'
               AND membership_type = 'owned' AND role = 'satellite';""",
    )
    cli(
        [
            "tenant-transfer", "request", "--location-id", UNVERIFIED_LOCATION_ID,
            "--target-organization-id", TARGET_ORG_ID,
            "--requested-by-operator-id", OWNER_ADMIN_ID,
            "--request-reference", "CASE-390-UNVERIFIED",
            "--reason", "Synthetic unverified ownership check",
        ],
        expected_error="location must have a current verified tenant owner",
    )
    checks.append("conflicting and unverified locations cannot enter a transfer")

    docker_sql(
        container,
        """
        CREATE FUNCTION public.acceptance_abort_owner_transfer()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'injected transfer failure after owner and grant updates';
        END;
        $$;
        CREATE TRIGGER zzz_acceptance_abort_owner_transfer
        BEFORE UPDATE ON location_tenant_transfer
        FOR EACH ROW EXECUTE FUNCTION public.acceptance_abort_owner_transfer();
        """,
    )
    cli(
        [
            "tenant-transfer", "accept", "--transfer-id", transfer_id,
            "--accepting-operator-id", TARGET_ADMIN_ID,
            "--acceptance-reference", "APPROVAL-390-ROLLBACK",
        ],
        expected_error="injected transfer failure after owner and grant updates",
    )
    assert_sql(container, f"SELECT organization_id FROM location WHERE id = '{LOCATION_ID}'", OWNER_ORG_ID, "failed acceptance rolls back location owner")
    assert_sql(container, f"SELECT count(*) FROM location_tenant_owner_verification WHERE location_id = '{LOCATION_ID}' AND revoked_at IS NULL AND organization_id = '{OWNER_ORG_ID}'", "1", "failed acceptance rolls back owner verification")
    assert_sql(container, f"SELECT count(*) FROM operator_scope_grant WHERE location_id = '{LOCATION_ID}' AND revoked_at IS NULL", "5", "failed acceptance rolls back every grant revocation")
    assert_sql(container, f"SELECT count(*) FROM location_organization_share WHERE location_id = '{LOCATION_ID}' AND revoked_at IS NULL", "2", "failed acceptance rolls back share revocation")
    docker_sql(
        container,
        "DROP TRIGGER zzz_acceptance_abort_owner_transfer ON location_tenant_transfer;\n"
        "DROP FUNCTION public.acceptance_abort_owner_transfer();\n",
    )
    checks.append("injected post-mutation failure rolls back owner, verification, grants, and shares")

    accepted = json.loads(
        cli(
            [
                "tenant-transfer", "accept", "--transfer-id", transfer_id,
                "--accepting-operator-id", TARGET_ADMIN_ID,
                "--acceptance-reference", "APPROVAL-390-TARGET",
            ],
        )
    )
    assert accepted["status"] == "accepted"
    assert_sql(container, f"SELECT organization_id FROM location WHERE id = '{LOCATION_ID}'", TARGET_ORG_ID, "accepted transfer changes tenant owner")
    assert_sql(container, f"SELECT count(*) FROM location_tenant_owner_verification WHERE location_id = '{LOCATION_ID}' AND revoked_at IS NULL AND organization_id = '{TARGET_ORG_ID}'", "1", "accepted transfer creates current target verification")
    assert_sql(container, f"SELECT count(*) FROM location_tenant_owner_verification WHERE id = (SELECT source_owner_verification_id FROM location_tenant_transfer WHERE id = '{transfer_id}') AND revoked_at IS NOT NULL", "1", "accepted transfer retires source verification")
    assert_sql(container, f"SELECT count(*) FROM organization_member WHERE location_id = '{LOCATION_ID}' AND organization_id = '{OWNER_ORG_ID}' AND membership_type = 'owned' AND status = 'active'", "0", "accepted transfer deactivates source owner relationships")
    assert_sql(container, f"SELECT count(*) FROM organization_member WHERE location_id = '{LOCATION_ID}' AND organization_id = '{TARGET_ORG_ID}' AND membership_type = 'owned' AND role = 'primary' AND status = 'active' AND farm_id = '{FARM_ID}'", "1", "accepted transfer preserves farm link in new owner relationship")
    assert_sql(container, f"SELECT count(*) FROM operator_scope_grant WHERE ownership_transfer_id = '{transfer_id}' AND revoked_by = '{TARGET_ADMIN_ID}' AND revoked_at IS NOT NULL", "5", "accepted transfer records and revokes each location grant")
    assert_sql(container, f"SELECT count(*) FROM location_organization_share WHERE ownership_transfer_id = '{transfer_id}' AND revoked_by_operator_id = '{TARGET_ADMIN_ID}' AND revoked_at IS NOT NULL", "2", "accepted transfer records and revokes each location share")
    for operator_id, resource, action in (
        (OWNER_ADMIN_ID, "farm_activity", "read"),
        (PARTNER_ADMIN_ID, "farm_activity", "review"),
        (LEGACY_OPERATOR_ID, "farm_activity", "legacy_read"),
    ):
        assert_sql(
            container,
            f"SELECT operator_scope_grant_allows('{operator_id}', '{resource}', '{action}', '{LOCATION_ID}')",
            "f",
            f"previous authorization revoked for {operator_id}",
        )
    checks.append("acceptance atomically transfers owner links and revokes owner, partner, and legacy access")

    target_grant = json.loads(
        cli(
            [
                "grant", "--operator-id", TARGET_ADMIN_ID, "--organization-id", TARGET_ORG_ID,
                "--resource", "farm_activity", "--action", "read", "--location-id", LOCATION_ID,
                "--granted-by", "post-transfer explicit grant",
            ],
        )
    )
    if str(target_grant["organization_id"]) != TARGET_ORG_ID:
        raise RuntimeError("post-transfer grant was not stored under the target tenant")
    assert_sql(
        container,
        f"SELECT operator_scope_grant_allows('{TARGET_ADMIN_ID}', 'farm_activity', 'read', '{LOCATION_ID}')",
        "t",
        "target access is restored only by a new explicit grant",
    )
    checks.append("new owner receives access only after a separate tenant-qualified grant")

    expect_sql_failure(
        container,
        f"UPDATE location_tenant_transfer SET request_reason = 'tampered' WHERE id = '{transfer_id}';",
        "transfer request evidence is immutable",
        "transfer request mutation",
    )
    expect_sql_failure(
        container,
        f"DELETE FROM location_tenant_transfer WHERE id = '{transfer_id}';",
        "location tenant transfer history is append-only",
        "transfer history deletion",
    )
    expect_sql_failure(
        container,
        "TRUNCATE location_tenant_transfer CASCADE;",
        "location tenant transfer history is append-only",
        "transfer history truncation",
    )
    checks.append("transfer request evidence cannot be updated, deleted, or truncated")

    docker_sql(
        container,
        (MIGRATIONS / "390_audited_location_tenant_transfers.sql").read_text(),
    )
    assert_sql(container, f"SELECT status FROM location_tenant_transfer WHERE id = '{transfer_id}'", "accepted", "migration replay preserves transfer history")
    assert_sql(container, f"SELECT organization_id FROM location WHERE id = '{LOCATION_ID}'", TARGET_ORG_ID, "migration replay preserves transferred owner")
    checks.append("migration 390 idempotent replay preserves accepted transfer and grants")
    return checks


def main() -> int:
    container = f"kokonut-owner-transfer-{uuid.uuid4().hex[:10]}"
    network = f"kokonut-owner-transfer-net-{uuid.uuid4().hex[:10]}"
    port = choose_loopback_port()
    started = False
    network_started = False
    cli_root_removed = False
    cli_root = Path(tempfile.mkdtemp(prefix="kokonut-tenant-transfer-cli-"))
    try:
        shutil.copy2(ROOT / "VERSION", cli_root / "VERSION")
        shutil.copytree(
            ROOT / "services",
            cli_root / "services",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        # Docker does not publish host ports for an --internal network. Keep
        # the database on an isolated named bridge with only its host port
        # bound to loopback; this script makes no outbound network requests.
        run(["docker", "network", "create", "--label", "kokonut.disposable=true", network])
        network_started = True
        published = f"127.0.0.1:{port}:5432"
        run(
            [
                "docker", "run", "--detach", "--rm", "--name", container,
                "--network", network, "--publish", published,
                "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16",
            ]
        )
        started = True
        wait_ready(container)
        docker_sql(container, FIXTURE.read_text())
        for name in (
            "387_kokonut_network_tenant_ownership.sql",
            "388_tenant_aware_operator_grants.sql",
            "389_tenant_aware_field_collector_write_guards.sql",
            "390_audited_location_tenant_transfers.sql",
        ):
            docker_sql(container, (MIGRATIONS / name).read_text())

        host_binding = run(["docker", "port", container, "5432/tcp"]).strip()
        if not host_binding.startswith("127.0.0.1:") or not host_binding.endswith(f":{port}"):
            raise RuntimeError(f"disposable port is not bound to loopback: {host_binding}")
        loopback_port_ready(port)
        add_fixture_rows(container)
        checks = run_acceptance(container, port, cli_root)

        run(["docker", "rm", "--force", container])
        started = False
        run(["docker", "network", "rm", network])
        network_started = False
        shutil.rmtree(cli_root)
        cli_root_removed = True

        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 on a disposable Docker bridge; host port bound to loopback only",
            "migrations": [
                "387_kokonut_network_tenant_ownership.sql",
                "388_tenant_aware_operator_grants.sql",
                "389_tenant_aware_field_collector_write_guards.sql",
                "390_audited_location_tenant_transfers.sql",
            ],
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "external_network_access": "Docker bridge egress was available; the check made no external requests",
            "repository_secrets_read": False,
            "checks": checks,
            "cleanup": {
                "container_removed": not started,
                "named_network_removed": not network_started,
                "temporary_source_copy_removed": cli_root_removed,
                "volume_retained": False,
            },
            "scope_limit": "Synthetic disposable data only; no archive, pilot, candidate, or production records were used. Acceptance verifies database, local CLI, and report-review query wiring, not legal land title or RLS.",
        }
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - print disposable check failure without a traceback.
        print(f"TENANT OWNER TRANSFER DISPOSABLE CHECK FAILED: {exc}", file=sys.stderr)
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
        shutil.rmtree(cli_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
