#!/usr/bin/env python3
"""Apply migration 404 and exercise Gateway farm-activity guards on disposable PG16."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/farm_activity_gateway_operations_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/404_gateway_farm_activity_operations.sql"
SCOPE_MIGRATION = ROOT / "schemas/postgres/359_activity_scope_and_outputs.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json"
)
ORG_A = "a0000000-0000-0000-0000-000000000701"
ORG_B = "a0000000-0000-0000-0000-000000000702"
LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
PLOT_B = "a0000000-0000-0000-0000-000000000202"
FARM_TASK_A = "a0000000-0000-0000-0000-000000000401"
FARM_TASK_B = "a0000000-0000-0000-0000-000000000402"
OPERATOR_1 = "a0000000-0000-0000-0000-000000000901"
OPERATOR_2 = "a0000000-0000-0000-0000-000000000902"
OPERATOR_3 = "a0000000-0000-0000-0000-000000000903"
OPERATOR_4 = "a0000000-0000-0000-0000-000000000904"


def run(command: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def docker_sql(container: str, statement: str) -> str:
    result = run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
            "-t", "-A", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )
    return result.stdout.strip()


def wait_ready(container: str) -> None:
    deadline = time.monotonic() + 60
    successes = 0
    while time.monotonic() < deadline:
        result = run(
            ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            check=False,
        )
        if result.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def connect(host_port: int):
    return psycopg2.connect(
        host="127.0.0.1",
        port=host_port,
        dbname="postgres",
        user="postgres",
        password=POSTGRES_PASSWORD,
        connect_timeout=5,
    )


POSTGRES_PASSWORD = ""


def runtime_connection(host_port: int, *, operator_id: str, tenant_id: str, location_id: str, action: str, reason: str = ""):
    connection = connect(host_port)
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE kokonut_runtime")
        cursor.execute(
            "SELECT set_config('kokonut.tenant_id', %s, true), "
            "set_config('kokonut.location_id', %s, true), "
            "set_config('kokonut.actor_id', %s, true), "
            "set_config('kokonut.actor_type', 'operator', true), "
            "set_config('kokonut.workflow_action', %s, true), "
            "set_config('kokonut.workflow_reason', %s, true)",
            (tenant_id, location_id, operator_id, action, reason),
        )
    return connection


def expect_database_error(operation, *, expected_code: str, message: str) -> None:
    try:
        operation()
    except psycopg2.Error as exc:
        if exc.pgcode != expected_code:
            raise AssertionError(f"{message}: expected {expected_code}, received {exc.pgcode}") from exc
        return
    raise AssertionError(f"{message}: statement unexpectedly succeeded")


def create_record(
    host_port: int,
    *,
    operator_id: str,
    tenant_id: str,
    location_id: str,
    plot_id=None,
    farm_task_id=None,
) -> str:
    connection = runtime_connection(
        host_port,
        operator_id=operator_id,
        tenant_id=tenant_id,
        location_id=location_id,
        action="draft_created",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO farm_activity (
                       location_id, plot_id, farm_task_id, activity_type, activity_date,
                       schema_version, source_system, created_by, updated_by
                   ) VALUES (%s::uuid, %s::uuid, %s::uuid, 'weeding', DATE '2026-10-15',
                             'gateway_v1', 'kokonut_gateway', %s::uuid, %s::uuid)
                   RETURNING id::text""",
                (location_id, plot_id, farm_task_id, operator_id, operator_id),
            )
            activity_id = cursor.fetchone()[0]
        connection.commit()
        return activity_id
    finally:
        connection.close()


def update_activity(
    host_port: int,
    *,
    operator_id: str,
    tenant_id: str,
    location_id: str,
    activity_id: str,
    action: str,
    changes: dict,
    reason: str = "",
) -> None:
    connection = runtime_connection(
        host_port,
        operator_id=operator_id,
        tenant_id=tenant_id,
        location_id=location_id,
        action=action,
        reason=reason,
    )
    try:
        assignments = ", ".join(f"{column} = %s" for column in changes)
        parameters = (*changes.values(), activity_id)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE farm_activity SET {assignments} WHERE id = %s::uuid",
                parameters,
            )
        connection.commit()
    finally:
        connection.close()


def assert_acceptance(host_port: int) -> list[str]:
    checks = []
    with closing(connect(host_port)) as admin:
        with admin.cursor() as cursor:
            cursor.execute(
                """SELECT has_table_privilege('kokonut_runtime',
                           'public.farm_activity_operator_event', 'SELECT'),
                          has_table_privilege('kokonut_runtime',
                           'public.farm_activity_operator_event', 'INSERT'),
                          has_table_privilege('kokonut_runtime',
                           'public.farm_activity_operator_event', 'UPDATE'),
                          has_table_privilege('kokonut_runtime',
                           'public.farm_activity_operator_event', 'DELETE')"""
            )
            runtime_ledger_privileges = cursor.fetchone()
            if runtime_ledger_privileges != (True, False, False, False):
                raise AssertionError(
                    "migration 404 must give runtime SELECT only on the event ledger; "
                    f"observed {runtime_ledger_privileges}"
                )
    activity_id = create_record(
        host_port,
        operator_id=OPERATOR_1,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
    )
    checks.append("tenant-qualified create creates a Gateway-owned draft and audit event")

    task_linked_activity_id = create_record(
        host_port,
        operator_id=OPERATOR_1,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
        farm_task_id=FARM_TASK_A,
    )
    with closing(connect(host_port)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT farm_task_id::text FROM farm_activity WHERE id = %s::uuid",
                (task_linked_activity_id,),
            )
            if cursor.fetchone() != (FARM_TASK_A,):
                raise AssertionError("same-location farm task link was not preserved")
    checks.append("same-location farm task links survive governed creation")

    def wrong_location_task_create():
        create_record(
            host_port,
            operator_id=OPERATOR_1,
            tenant_id=ORG_A,
            location_id=LOCATION_A,
            farm_task_id=FARM_TASK_B,
        )

    expect_database_error(
        wrong_location_task_create,
        expected_code="P0001",
        message="cross-location farm task references are rejected",
    )
    checks.append("migration 359 rejects cross-location farm task references")

    connection = connect(host_port)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, source_system, schema_version, COUNT(event.id) "
                "FROM farm_activity AS activity "
                "JOIN farm_activity_operator_event AS event ON event.farm_activity_id = activity.id "
                "WHERE activity.id = %s::uuid GROUP BY status, source_system, schema_version",
                (activity_id,),
            )
            if cursor.fetchone() != ("draft", "kokonut_gateway", "gateway_v1", 1):
                raise AssertionError("Gateway draft provenance or creation event is incorrect")
    finally:
        connection.close()

    update_activity(
        host_port,
        operator_id=OPERATOR_1,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
        activity_id=activity_id,
        action="draft_edited",
        changes={"notes": "Synthetic correction"},
        reason="Corrected transcription",
    )
    checks.append("draft edit is reasoned and atomically appended")

    update_activity(
        host_port,
        operator_id=OPERATOR_1,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
        activity_id=activity_id,
        action="submitted",
        changes={"status": "submitted"},
    )
    checks.append("submission records the human actor")

    def self_verify():
        update_activity(
            host_port,
            operator_id=OPERATOR_1,
            tenant_id=ORG_A,
            location_id=LOCATION_A,
            activity_id=activity_id,
            action="verified",
            changes={"status": "verified", "verified_by": OPERATOR_1, "verified_at": datetime.now(timezone.utc)},
        )

    expect_database_error(
        self_verify,
        expected_code="P0001",
        message="submitter cannot verify their own submission",
    )
    checks.append("submitter/verifier separation rejects a self-review")

    update_activity(
        host_port,
        operator_id=OPERATOR_2,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
        activity_id=activity_id,
        action="verified",
        changes={"status": "verified", "verified_by": OPERATOR_2, "verified_at": datetime.now(timezone.utc)},
    )
    update_activity(
        host_port,
        operator_id=OPERATOR_3,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
        activity_id=activity_id,
        action="published",
        changes={"status": "published"},
    )
    checks.append("independent verifier and publisher can complete the governed lifecycle")

    def wrong_location_plot():
        create_record(
            host_port,
            operator_id=OPERATOR_1,
            tenant_id=ORG_A,
            location_id=LOCATION_A,
            plot_id=PLOT_B,
        )

    expect_database_error(
        wrong_location_plot,
        expected_code="P0001",
        message="cross-location plot references are rejected",
    )
    checks.append("cross-location plot references are rejected")

    def wrong_tenant_create():
        create_record(
            host_port,
            operator_id=OPERATOR_4,
            tenant_id=ORG_A,
            location_id=LOCATION_A,
        )

    expect_database_error(
        wrong_tenant_create,
        expected_code="P0001",
        message="organization grant cannot be replayed against another location tenant",
    )
    checks.append("organization/location grants deny a different tenant")

    def cross_tenant_update():
        update_activity(
            host_port,
            operator_id=OPERATOR_4,
            tenant_id=ORG_B,
            location_id=LOCATION_B,
            activity_id=activity_id,
            action="draft_edited",
            changes={"notes": "cross-tenant"},
            reason="Synthetic denial",
        )

    expect_database_error(
        cross_tenant_update,
        expected_code="P0001",
        message="a tenant B context cannot update a tenant A activity",
    )
    checks.append("cross-tenant updates are denied by the row guard")

    runtime = runtime_connection(
        host_port,
        operator_id=OPERATOR_1,
        tenant_id=ORG_A,
        location_id=LOCATION_A,
        action="draft_created",
    )
    try:
        probe_activity_id = create_record(
            host_port,
            operator_id=OPERATOR_1,
            tenant_id=ORG_A,
            location_id=LOCATION_A,
        )
        runtime.rollback()
        runtime = runtime_connection(
            host_port,
            operator_id=OPERATOR_1,
            tenant_id=ORG_A,
            location_id=LOCATION_A,
            action="draft_created",
        )
        def direct_insert():
            with runtime.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO farm_activity_operator_event (
                           farm_activity_id, location_id, actor_operator_id,
                           action, to_status
                       ) VALUES (%s::uuid, %s::uuid, %s::uuid, 'draft_created', 'draft')""",
                    (probe_activity_id, LOCATION_A, OPERATOR_1),
                )

        expect_database_error(
            direct_insert,
            expected_code="42501",
            message="runtime role cannot insert directly into the operator event ledger",
        )
        runtime.rollback()
        for statement in (
            "UPDATE farm_activity_operator_event SET reason = 'tampered' WHERE farm_activity_id = '%s'::uuid"
            % probe_activity_id,
            "DELETE FROM farm_activity_operator_event WHERE farm_activity_id = '%s'::uuid" % probe_activity_id,
        ):
            def execute_denied_sql():
                with runtime.cursor() as cursor:
                    cursor.execute(statement)

            try:
                execute_denied_sql()
            except psycopg2.Error as exc:
                if exc.pgcode not in {"42501", "P0001"}:
                    raise AssertionError("runtime event-ledger mutation failed unexpectedly") from exc
            else:
                raise AssertionError("runtime role unexpectedly mutated the operator event ledger")
            runtime.rollback()
    finally:
        runtime.close()
    checks.append("runtime role has read-only access to the append-only ledger")

    with closing(connect(host_port)) as admin:
        with admin:
            with admin.cursor() as cursor:
                cursor.execute("GRANT UPDATE ON farm_activity_operator_event TO kokonut_farm_activity_event_owner")
    event_owner = connect(host_port)
    try:
        with event_owner.cursor() as cursor:
            cursor.execute("SET ROLE kokonut_farm_activity_event_owner")
            cursor.execute(
                "UPDATE farm_activity_operator_event SET reason = 'tampered' WHERE farm_activity_id = %s::uuid",
                (activity_id,),
            )
    except psycopg2.Error as exc:
        event_owner.rollback()
        if exc.pgcode != "P0001" or "append-only" not in str(exc):
            raise AssertionError("append-only trigger did not reject a privileged mutation") from exc
    else:
        raise AssertionError("append-only trigger allowed a privileged mutation")
    finally:
        event_owner.close()
    with closing(connect(host_port)) as admin:
        with admin:
            with admin.cursor() as cursor:
                cursor.execute("REVOKE UPDATE ON farm_activity_operator_event FROM kokonut_farm_activity_event_owner")
    checks.append("append-only trigger rejects mutation even when table UPDATE is temporarily granted")

    with closing(connect(host_port)) as admin:
        with admin.cursor() as cursor:
            cursor.execute(
                """SELECT has_table_privilege('kokonut_directus_runtime',
                           'public.farm_activity_operator_event', 'SELECT'),
                          has_table_privilege('kokonut_directus_runtime',
                           'public.farm_activity_operator_event', 'INSERT'),
                          has_table_privilege('kokonut_runtime',
                           'public.farm_activity_operator_event', 'SELECT'),
                          has_table_privilege('kokonut_runtime',
                           'public.farm_activity_operator_event', 'INSERT')"""
            )
            if cursor.fetchone() != (False, False, True, False):
                raise AssertionError("runtime or Directus ledger privilege boundary is incorrect")
    checks.append("optional Directus cannot access the ledger and runtime cannot insert")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    global POSTGRES_PASSWORD
    POSTGRES_PASSWORD = secrets.token_urlsafe(32)
    container = f"kokonut-farm-activity-ops-{uuid.uuid4().hex[:10]}"
    started = False
    try:
        run(
            [
                "docker", "run", "--detach", "--rm", "--name", container,
                "--env", f"POSTGRES_PASSWORD={POSTGRES_PASSWORD}",
                "--publish", "127.0.0.1::5432", "postgres:16-alpine",
            ]
        )
        started = True
        wait_ready(container)
        host_binding = run(["docker", "port", container, "5432/tcp"]).stdout.strip().splitlines()
        if len(host_binding) != 1 or not host_binding[0].startswith("127.0.0.1:"):
            raise RuntimeError("disposable PostgreSQL must bind only to host loopback")
        host_port = int(host_binding[0].rsplit(":", 1)[1])

        docker_sql(container, FIXTURE.read_text())
        docker_sql(container, SCOPE_MIGRATION.read_text())
        docker_sql(container, MIGRATION.read_text())
        checks = assert_acceptance(host_port)
        server_version = docker_sql(container, "SELECT current_setting('server_version');")
        report = {
            "status": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "postgres_version": server_version,
            "migrations": [SCOPE_MIGRATION.name, MIGRATION.name],
            "database_scope": "fresh temporary PostgreSQL 16 container with no mounted volumes",
            "connection_scope": "random host port bound to 127.0.0.1 only",
            "tenant_context": "synthetic fixture function; signed-context cryptography is covered separately",
            "checks": checks,
            "candidate_or_legacy_database_touched": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if started:
            run(["docker", "rm", "--force", container], check=False)


if __name__ == "__main__":
    sys.exit(main())
