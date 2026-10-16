#!/usr/bin/env python3
"""Exercise migration 412 reads in disposable PostgreSQL 16."""

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = (
    ROOT / "tests/fixtures/worker_tenant_context_disposable.sql",
    ROOT / "tests/fixtures/sensor_anomaly_effect_functions_disposable.sql",
)
EVENT_FIXTURE = ROOT / "tests/fixtures/sensor_alert_event_function_disposable.sql"
NOTIFICATION_FIXTURE = ROOT / "tests/fixtures/sensor_alert_notification_intent_disposable.sql"
ACTUATION_FIXTURE = ROOT / "tests/fixtures/sensor_alert_actuation_intent_disposable.sql"
CLAIM_FIXTURE = ROOT / "tests/fixtures/sensor_alert_draft_claim_intent_disposable.sql"
READ_FIXTURE = ROOT / "tests/fixtures/sensor_anomaly_worker_reads_disposable.sql"
MIGRATIONS = tuple(
    ROOT / f"schemas/postgres/{number}_{name}.sql"
    for number, name in (
        (405, "signed_worker_tenant_context"),
        (406, "sensor_anomaly_location_lineage"),
        (407, "sensor_anomaly_effect_functions"),
        (408, "sensor_alert_event_function"),
        (409, "sensor_alert_notification_intent"),
        (410, "sensor_alert_actuation_intent"),
        (411, "sensor_alert_draft_claim_intent"),
        (412, "sensor_anomaly_worker_reads"),
    )
)
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/"
    "sensor-anomaly-worker-reads-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"
READING_ID = "a0000000-0000-0000-0000-000000000021"
SOURCE_EVENT_ID = "a0000000-0000-0000-0000-000000000031"
MISMATCH_EVENT_ID = "a0000000-0000-0000-0000-000000000032"
OTHER_TYPE_EVENT_ID = "a0000000-0000-0000-0000-000000000035"
VALUE_RULE_ID = "a0000000-0000-0000-0000-000000000091"
RATE_RULE_ID = "a0000000-0000-0000-0000-000000000092"
GAP_RULE_ID = "a0000000-0000-0000-0000-000000000093"
MIN_RULE_ID = "a0000000-0000-0000-0000-000000000094"
MAX_RULE_ID = "a0000000-0000-0000-0000-000000000095"
OTHER_TYPE_RULE_ID = "a0000000-0000-0000-0000-000000000096"
DISABLED_RULE_ID = "a0000000-0000-0000-0000-000000000097"
COOLDOWN_RULE_ID = "a0000000-0000-0000-0000-000000000098"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()

SOURCE_SQL = """
SELECT * FROM kokonut_security.read_sensor_anomaly_source(
    %s::uuid, %s::uuid, %s
)
"""
RULES_SQL = """
SELECT * FROM kokonut_security.list_sensor_anomaly_rules(%s::uuid, %s::uuid)
"""
EVALUATE_SQL = """
SELECT kokonut_security.evaluate_sensor_anomaly_rule(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
COOLDOWN_SQL = """
SELECT kokonut_security.sensor_anomaly_in_cooldown(
    %s::uuid, %s::uuid, %s::uuid
)
"""


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
    stable_checks = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if check.returncode == 0:
            stable_checks += 1
            if stable_checks >= 4:
                return
        else:
            stable_checks = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=user,
        password=password, connect_timeout=5,
    )


def set_context(connection) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    context = set_worker_tenant_context(
        connection, credential=RAW_CREDENTIAL, location_id=LOCATION_ID,
        resource="sensor_reading", action="process",
    )
    if context.tenant_id != TENANT_ID or context.location_id != LOCATION_ID:
        raise AssertionError("signed worker setter returned an unexpected tenant scope")


def call(connection, statement: str, params: tuple):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        result = cursor.fetchall()
    connection.commit()
    return result


def expect_sqlstate(connection, statement: str, params: tuple, expected: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != expected:
            raise AssertionError(
                f"{label}: expected SQLSTATE {expected}, received {exc.pgcode}"
            ) from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: operation unexpectedly succeeded")


def call_worker(connection, statement: str, params: tuple):
    set_context(connection)
    return call(connection, statement, params)


def direct_denial(connection, statement: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            cursor.execute(statement)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != "42501":
            raise AssertionError(f"{label}: expected 42501, received {exc.pgcode}") from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: direct table access unexpectedly succeeded")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("ANOMALY_READ_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-reads-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
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
        docker_sql(docker, container, FIXTURES[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURES[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[2].read_text(encoding="utf-8"))
        docker_sql(docker, container, EVENT_FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[3].read_text(encoding="utf-8"))
        docker_sql(docker, container, NOTIFICATION_FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[4].read_text(encoding="utf-8"))
        docker_sql(docker, container, ACTUATION_FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[5].read_text(encoding="utf-8"))
        docker_sql(docker, container, CLAIM_FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[6].read_text(encoding="utf-8"))
        docker_sql(docker, container, READ_FIXTURE.read_text(encoding="utf-8"))
        migration_sql = MIGRATIONS[7].read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 412 applies and replays after migrations 405 through 411")

        docker_sql(
            docker, container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'sensor-anomaly');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
                'sensor_reading', 'process', 'disposable fixture'
            );
            """,
        )

        port_lines = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not port_lines:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(port_lines[0].rsplit(":", 1)[1])
        worker = connect(port, "kokonut_worker_login", "worker-execution-fixture")
        runtime = connect(port, "kokonut_runtime", "worker-runtime-fixture")
        operator_auth = connect(port, "kokonut_operator_auth", "worker-auth-fixture")
        admin = connect(port, "postgres", admin_password)
        connections = (worker, runtime, operator_auth, admin)

        for function_sql, params, label in (
            (SOURCE_SQL, (SOURCE_EVENT_ID, LOCATION_ID, SENSOR_ID), "source read"),
            (RULES_SQL, (SENSOR_ID, LOCATION_ID), "rule list"),
            (EVALUATE_SQL, (SOURCE_EVENT_ID, READING_ID, VALUE_RULE_ID, LOCATION_ID), "metric evaluation"),
            (COOLDOWN_SQL, (SENSOR_ID, COOLDOWN_RULE_ID, LOCATION_ID), "cooldown read"),
        ):
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            expect_sqlstate(worker, function_sql, params, "42501", f"unsigned {label}")
        checks.append("all bounded read functions reject calls without signed worker context")

        source = call_worker(
            worker, SOURCE_SQL, (SOURCE_EVENT_ID, LOCATION_ID, SENSOR_ID)
        )
        if len(source) != 1 or (
            str(source[0][0]), str(source[0][1]), source[0][2], source[0][3]
        ) != (READING_ID, SENSOR_ID, "soil_moisture", 18) or (
            str(source[0][6]) != LOCATION_ID
            or str(source[0][8]) != SENSOR_ID
            or source[0][9] != "Synthetic soil probe"
            or source[0][11:13] != ("soil_moisture", "Synthetic Farm One")
        ):
            raise AssertionError(f"source read returned unexpected lineage: {source}")
        checks.append("source read returns one event-linked reading and matching device/location context")

        for params, label in (
            ((MISMATCH_EVENT_ID, LOCATION_ID, SENSOR_ID), "mismatched sensor selector"),
            ((OTHER_TYPE_EVENT_ID, LOCATION_ID, SENSOR_ID), "wrong source event type"),
            ((SOURCE_EVENT_ID, OTHER_LOCATION_ID, SENSOR_ID), "out-of-scope location"),
            ((SOURCE_EVENT_ID, LOCATION_ID, "a0000000-0000-0000-0000-000000000012"), "wrong sensor selector"),
        ):
            set_context(worker)
            expect_sqlstate(worker, SOURCE_SQL, params, "42501", label)
        checks.append("source event, payload selectors, requested sensor, and signed location must agree")

        rules = call_worker(worker, RULES_SQL, (SENSOR_ID, LOCATION_ID))
        rule_ids = {str(row[0]) for row in rules}
        if rule_ids != {
            VALUE_RULE_ID, RATE_RULE_ID, GAP_RULE_ID, MIN_RULE_ID,
            MAX_RULE_ID, COOLDOWN_RULE_ID,
        }:
            raise AssertionError(f"rule list escaped sensor type/enabled scope: {rule_ids}")
        set_context(worker)
        expect_sqlstate(
            worker, RULES_SQL,
            ("a0000000-0000-0000-0000-000000000012", LOCATION_ID),
            "42501", "other location device in rule list",
        )
        checks.append("rule list is limited to enabled rules matching the signed-location device type")

        metric_results = {}
        for label, rule_id, expected in (
            ("value", VALUE_RULE_ID, True),
            ("rate_of_change", RATE_RULE_ID, True),
            ("gap", GAP_RULE_ID, True),
            ("min", MIN_RULE_ID, True),
            ("max_excludes_other_location", MAX_RULE_ID, False),
        ):
            result = call_worker(
                worker, EVALUATE_SQL,
                (SOURCE_EVENT_ID, READING_ID, rule_id, LOCATION_ID),
            )[0][0]
            if result is not expected:
                raise AssertionError(f"{label} metric returned {result}, expected {expected}")
            metric_results[label] = result
        checks.append("value, rate, gap, and min metrics match synthetic history; max excludes another farm")

        for params, label in (
            ((MISMATCH_EVENT_ID, READING_ID, VALUE_RULE_ID, LOCATION_ID), "mismatched evaluation event"),
            ((OTHER_TYPE_EVENT_ID, READING_ID, VALUE_RULE_ID, LOCATION_ID), "wrong-type evaluation event"),
            ((SOURCE_EVENT_ID, READING_ID, VALUE_RULE_ID, OTHER_LOCATION_ID), "out-of-scope evaluation"),
            ((SOURCE_EVENT_ID, READING_ID, OTHER_TYPE_RULE_ID, LOCATION_ID), "wrong sensor type rule"),
            ((SOURCE_EVENT_ID, READING_ID, DISABLED_RULE_ID, LOCATION_ID), "disabled rule"),
        ):
            set_context(worker)
            expect_sqlstate(worker, EVALUATE_SQL, params, "42501", label)
        checks.append("metric evaluation requires the event, reading, rule, and signed location to match")

        active_cooldown = call_worker(
            worker, COOLDOWN_SQL, (SENSOR_ID, COOLDOWN_RULE_ID, LOCATION_ID)
        )[0][0]
        inactive_cooldown = call_worker(
            worker, COOLDOWN_SQL, (SENSOR_ID, VALUE_RULE_ID, LOCATION_ID)
        )[0][0]
        if active_cooldown is not True or inactive_cooldown is not False:
            raise AssertionError("cooldown state did not match the scoped synthetic alert")
        set_context(worker)
        expect_sqlstate(
            worker, COOLDOWN_SQL,
            (SENSOR_ID, COOLDOWN_RULE_ID, OTHER_LOCATION_ID),
            "42501", "out-of-scope cooldown",
        )
        set_context(worker)
        expect_sqlstate(
            worker, COOLDOWN_SQL,
            ("a0000000-0000-0000-0000-000000000012", COOLDOWN_RULE_ID, LOCATION_ID),
            "42501", "cross-location cooldown device",
        )
        set_context(worker)
        expect_sqlstate(
            worker, COOLDOWN_SQL,
            (SENSOR_ID, DISABLED_RULE_ID, LOCATION_ID),
            "42501", "disabled cooldown rule",
        )
        checks.append("cooldown reads match the device, rule, and signed location")

        table_names = (
            "platform_event", "sensor_reading", "sensor_device", "sensor_type",
            "location", "alert_rule", "sensor_alert",
        )
        for table_name in table_names:
            direct_denial(
                worker, f"SELECT * FROM public.{table_name} LIMIT 0",
                f"direct worker SELECT on {table_name}",
            )
        checks.append("worker execution role has no direct SELECT on any anomaly source table")

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT has_any_column_privilege('kokonut_worker_execution', "
                "'public.' || table_name, 'SELECT') "
                "FROM unnest(%s::text[]) AS tables(table_name)",
                (list(table_names),),
            )
            if any(row[0] for row in cursor.fetchall()):
                raise AssertionError("worker role retained direct anomaly source table access")
            cursor.execute(
                "SELECT has_function_privilege('kokonut_worker_execution', %s, 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', %s, 'EXECUTE'), "
                "has_function_privilege('kokonut_operator_auth', %s, 'EXECUTE')",
                (
                    "kokonut_security.evaluate_sensor_anomaly_rule(uuid,uuid,uuid,uuid)",
                ) * 3,
            )
            if cursor.fetchone() != (True, False, False):
                raise AssertionError("bounded evaluation function privileges are incorrect")
            cursor.execute(
                "SELECT role.rolcanlogin, role.rolinherit, role.rolsuper, "
                "role.rolcreatedb, role.rolcreaterole, role.rolreplication, "
                "role.rolbypassrls, EXISTS (SELECT 1 FROM pg_auth_members "
                "WHERE roleid = role.oid OR member = role.oid) "
                "FROM pg_roles AS role WHERE role.rolname = 'kokonut_anomaly_read_owner'"
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False, False):
                raise AssertionError("anomaly read owner role has unsafe attributes or memberships")
            cursor.execute(
                "SELECT has_column_privilege('kokonut_anomaly_read_owner', "
                "'public.sensor_reading', 'value', 'SELECT'), "
                "has_column_privilege('kokonut_anomaly_read_owner', "
                "'public.sensor_reading', 'quality', 'SELECT'), "
                "has_column_privilege('kokonut_anomaly_read_owner', "
                "'public.sensor_device', 'name', 'SELECT'), "
                "has_column_privilege('kokonut_anomaly_read_owner', "
                "'public.sensor_device', 'endpoint_url', 'SELECT')"
            )
            if cursor.fetchone() != (True, False, True, False):
                raise AssertionError("anomaly read owner column grants are broader than intended")
        admin.commit()
        checks.append("worker, shared runtime, and auth roles are separated from the no-login read owner")

        for connection in connections:
            connection.close()

        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 412 signed sensor-anomaly reads",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS],
            "migration_412_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
            "migration_replay": "passed",
            "metric_results": metric_results,
            "command": "python3 scripts/check-sensor-anomaly-worker-reads-disposable.py",
            "container_network": "loopback-only published port; runner makes no external requests",
            "checks": [{"result": "passed", "description": item} for item in checks],
            "candidate_or_legacy_database_access": False,
            "worker_credential_printed": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if created:
            subprocess.run(
                [docker, "rm", "-f", container],
                text=True, capture_output=True, check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
