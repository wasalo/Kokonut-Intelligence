#!/usr/bin/env python3
"""Exercise migration 413 alert/audit writes in disposable PostgreSQL 16."""

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
    ROOT / "tests/fixtures/sensor_alert_event_function_disposable.sql",
    ROOT / "tests/fixtures/sensor_alert_notification_intent_disposable.sql",
    ROOT / "tests/fixtures/sensor_alert_actuation_intent_disposable.sql",
    ROOT / "tests/fixtures/sensor_alert_draft_claim_intent_disposable.sql",
    ROOT / "tests/fixtures/sensor_anomaly_worker_reads_disposable.sql",
    ROOT / "tests/fixtures/sensor_anomaly_alert_write_disposable.sql",
)
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
        (413, "sensor_anomaly_alert_write"),
    )
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-16-recovery/sensor-anomaly-alert-write-disposable.json"

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"
READING_ID = "a0000000-0000-0000-0000-000000000021"
OTHER_READING_ID = "a0000000-0000-0000-0000-000000000022"
SOURCE_EVENT_ID = "a0000000-0000-0000-0000-000000000031"
MISMATCH_EVENT_ID = "a0000000-0000-0000-0000-000000000032"
OTHER_LOCATION_EVENT_ID = "a0000000-0000-0000-0000-000000000033"
OTHER_TYPE_EVENT_ID = "a0000000-0000-0000-0000-000000000035"
ATOMICITY_READING_ID = "a0000000-0000-0000-0000-000000000025"
ATOMICITY_EVENT_ID = "a0000000-0000-0000-0000-000000000036"
VALUE_RULE_ID = "a0000000-0000-0000-0000-000000000091"
OTHER_TYPE_RULE_ID = "a0000000-0000-0000-0000-000000000096"
DISABLED_RULE_ID = "a0000000-0000-0000-0000-000000000097"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
PAYLOAD_HASH = hashlib.sha256(b"synthetic anomaly alert audit payload").hexdigest()
ATOMICITY_FAILURE_HASH = "f" * 64
CREATE_SQL = """
SELECT sensor_alert_id::text, triggered_at
  FROM kokonut_security.create_sensor_anomaly_alert(
      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s
  )
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        safe_command = [
            "POSTGRES_PASSWORD=<redacted>" if part.startswith("POSTGRES_PASSWORD=") else part for part in command
        ]
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    stable_checks = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
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
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user=user,
        password=password,
        connect_timeout=5,
    )


def set_context(connection) -> None:
    from services.common.tenant_context import set_worker_tenant_context

    context = set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource="sensor_reading",
        action="process",
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
            raise AssertionError(f"{label}: expected SQLSTATE {expected}, received {exc.pgcode}") from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: operation unexpectedly succeeded")


def call_worker(connection, params: tuple):
    set_context(connection)
    return call(connection, CREATE_SQL, params)


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


def admin_query(connection, statement: str, params: tuple = ()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        result = cursor.fetchall()
    connection.commit()
    return result


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("ANOMALY_ALERT_WRITE_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-alert-write-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
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
                image,
            ]
        )
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURES[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[0].read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURES[1].read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATIONS[1].read_text(encoding="utf-8"))
        for fixture, migration in zip(FIXTURES[2:7], MIGRATIONS[3:8], strict=True):
            docker_sql(docker, container, fixture.read_text(encoding="utf-8"))
            docker_sql(docker, container, migration.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURES[7].read_text(encoding="utf-8"))
        migration_sql = MIGRATIONS[8].read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 413 applies and replays after migrations 405 through 412")

        docker_sql(
            docker,
            container,
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

        no_context_params = (
            SOURCE_EVENT_ID,
            READING_ID,
            VALUE_RULE_ID,
            LOCATION_ID,
            "Synthetic alert without context",
            PAYLOAD_HASH,
        )
        with worker.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
        expect_sqlstate(worker, CREATE_SQL, no_context_params, "42501", "unsigned alert create")
        checks.append("alert creation rejects missing signed worker context")

        for params, label, expected in (
            (
                (MISMATCH_EVENT_ID, READING_ID, VALUE_RULE_ID, LOCATION_ID, "mismatched source", PAYLOAD_HASH),
                "mismatched event selectors",
                "42501",
            ),
            (
                (
                    OTHER_LOCATION_EVENT_ID,
                    OTHER_READING_ID,
                    VALUE_RULE_ID,
                    OTHER_LOCATION_ID,
                    "other location",
                    PAYLOAD_HASH,
                ),
                "cross-location source",
                "42501",
            ),
            (
                (
                    OTHER_TYPE_EVENT_ID,
                    "a0000000-0000-0000-0000-000000000041",
                    VALUE_RULE_ID,
                    LOCATION_ID,
                    "wrong event type",
                    PAYLOAD_HASH,
                ),
                "wrong event type",
                "42501",
            ),
            (
                (SOURCE_EVENT_ID, READING_ID, OTHER_TYPE_RULE_ID, LOCATION_ID, "wrong rule type", PAYLOAD_HASH),
                "wrong sensor-type rule",
                "42501",
            ),
            (
                (SOURCE_EVENT_ID, READING_ID, DISABLED_RULE_ID, LOCATION_ID, "disabled rule", PAYLOAD_HASH),
                "disabled rule",
                "42501",
            ),
            (
                (SOURCE_EVENT_ID, OTHER_READING_ID, VALUE_RULE_ID, LOCATION_ID, "mismatched reading", PAYLOAD_HASH),
                "mismatched event reading",
                "42501",
            ),
            (
                (
                    SOURCE_EVENT_ID,
                    READING_ID,
                    VALUE_RULE_ID,
                    OTHER_LOCATION_ID,
                    "wrong requested location",
                    PAYLOAD_HASH,
                ),
                "requested location mismatch",
                "42501",
            ),
            (
                (SOURCE_EVENT_ID, READING_ID, VALUE_RULE_ID, LOCATION_ID, "malformed hash", "not-a-hash"),
                "malformed payload hash",
                "22023",
            ),
        ):
            set_context(worker)
            expect_sqlstate(worker, CREATE_SQL, params, expected, label)
        checks.append("event, reading, device, enabled rule, message, hash, and signed location are validated")

        set_context(worker)
        expect_sqlstate(worker, CREATE_SQL, no_context_params, "42501", "missing reserved receipt")
        checks.append("alert creation requires a matching reserved no_match receipt")

        docker_sql(
            docker,
            container,
            f"""
            INSERT INTO public.sensor_anomaly_effect (
                location_id, source_reading_id, alert_rule_id, source_event_id, outcome
            ) VALUES (
                '{LOCATION_ID}', '{READING_ID}', '{VALUE_RULE_ID}',
                '{SOURCE_EVENT_ID}', 'no_match'
            ), (
                '{LOCATION_ID}', '{ATOMICITY_READING_ID}', '{VALUE_RULE_ID}',
                '{ATOMICITY_EVENT_ID}', 'no_match'
            );
            """,
        )

        valid_params = (
            SOURCE_EVENT_ID,
            READING_ID,
            VALUE_RULE_ID,
            LOCATION_ID,
            "Synthetic soil moisture threshold exceeded",
            PAYLOAD_HASH,
        )
        created_alert = call_worker(worker, valid_params)
        if len(created_alert) != 1:
            raise AssertionError(f"expected one created alert, got {created_alert}")
        alert_id, triggered_at = created_alert[0]
        alert_row = admin_query(
            admin,
            """SELECT location_id::text, sensor_device_id::text, alert_rule_id::text,
                      reading_id::text, severity, status, message, reading_value,
                      threshold_value
                 FROM public.sensor_alert WHERE id = %s::uuid""",
            (alert_id,),
        )
        if alert_row != [
            (
                LOCATION_ID,
                SENSOR_ID,
                VALUE_RULE_ID,
                READING_ID,
                "warning",
                "open",
                "Synthetic soil moisture threshold exceeded",
                18,
                10,
            )
        ]:
            raise AssertionError(f"alert fields were not source-derived: {alert_row}")
        receipt = admin_query(
            admin,
            """SELECT outcome, sensor_alert_id::text
                 FROM public.sensor_anomaly_effect
                WHERE source_event_id = %s::uuid AND alert_rule_id = %s::uuid""",
            (SOURCE_EVENT_ID, VALUE_RULE_ID),
        )
        audit = admin_query(
            admin,
            """SELECT source_system, source_id, target_table, target_id::text,
                      operation, payload_hash, status, rows_affected, location_id::text
                 FROM public.ingestion_log
                WHERE target_id = %s::uuid""",
            (alert_id,),
        )
        if receipt != [("alert_created", str(alert_id))] or audit != [
            (
                "anomaly_detector",
                READING_ID,
                "sensor_alert",
                str(alert_id),
                "insert",
                PAYLOAD_HASH,
                "success",
                1,
                LOCATION_ID,
            )
        ]:
            raise AssertionError(f"receipt/audit link mismatch: {receipt=}, {audit=}")
        if triggered_at is None:
            raise AssertionError("new alert has no triggered_at timestamp")
        checks.append(
            "forced-RLS worker function creates a derived alert, one audit entry, and linked receipt atomically"
        )

        set_context(worker)
        expect_sqlstate(worker, CREATE_SQL, valid_params, "42501", "duplicate alert create")
        counts = admin_query(
            admin,
            """SELECT
                      (SELECT count(*) FROM public.sensor_alert
                        WHERE reading_id = %s::uuid AND alert_rule_id = %s::uuid),
                      (SELECT count(*) FROM public.ingestion_log WHERE target_id = %s::uuid)""",
            (READING_ID, VALUE_RULE_ID, alert_id),
        )
        if counts != [(1, 1)]:
            raise AssertionError(f"duplicate call changed persisted effects: {counts}")
        checks.append("completed receipt suppresses duplicate alert and audit creation")

        atomicity_params = (
            ATOMICITY_EVENT_ID,
            ATOMICITY_READING_ID,
            VALUE_RULE_ID,
            LOCATION_ID,
            "Synthetic alert should roll back with failed audit",
            ATOMICITY_FAILURE_HASH,
        )
        set_context(worker)
        expect_sqlstate(worker, CREATE_SQL, atomicity_params, "23514", "audit constraint failure")
        atomicity_state = admin_query(
            admin,
            """SELECT
                      (SELECT count(*) FROM public.sensor_alert
                        WHERE reading_id = %s::uuid AND alert_rule_id = %s::uuid),
                      (SELECT outcome FROM public.sensor_anomaly_effect
                        WHERE source_event_id = %s::uuid AND alert_rule_id = %s::uuid),
                      (SELECT count(*) FROM public.ingestion_log
                        WHERE source_id = %s AND target_table = 'sensor_alert')""",
            (ATOMICITY_READING_ID, VALUE_RULE_ID, ATOMICITY_EVENT_ID, VALUE_RULE_ID, ATOMICITY_READING_ID),
        )
        if atomicity_state != [(0, "no_match", 0)]:
            raise AssertionError(f"failed audit left partial alert effects: {atomicity_state}")
        checks.append("an audit constraint failure rolls back alert insertion and preserves the reserved receipt")

        for statement, label in (
            ("SELECT * FROM public.sensor_alert LIMIT 0", "worker SELECT sensor_alert"),
            (
                "INSERT INTO public.sensor_alert (id, location_id, sensor_device_id, alert_rule_id, severity, message) "
                f"VALUES (gen_random_uuid(), '{LOCATION_ID}', '{SENSOR_ID}', '{VALUE_RULE_ID}', 'warning', 'direct')",
                "worker INSERT sensor_alert",
            ),
            (
                "UPDATE public.sensor_alert SET status = 'closed' WHERE id = '00000000-0000-0000-0000-000000000000'",
                "worker UPDATE sensor_alert",
            ),
            ("SELECT * FROM public.ingestion_log LIMIT 0", "worker SELECT ingestion_log"),
            (
                "INSERT INTO public.ingestion_log (source_system, target_table, payload_hash) "
                "VALUES ('direct', 'sensor_alert', 'hash')",
                "worker INSERT ingestion_log",
            ),
            ("UPDATE public.ingestion_log SET status = 'changed'", "worker UPDATE ingestion_log"),
            ("SELECT * FROM public.sensor_anomaly_effect LIMIT 0", "worker SELECT anomaly receipt"),
            ("UPDATE public.sensor_anomaly_effect SET outcome = 'cooldown'", "worker UPDATE anomaly receipt"),
        ):
            direct_denial(worker, statement, label)
        checks.append(
            "worker execution has no direct table SELECT/INSERT/UPDATE path for alert, audit, or receipt records"
        )

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT has_function_privilege('kokonut_worker_execution', %s, 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', %s, 'EXECUTE'), "
                "has_function_privilege('kokonut_operator_auth', %s, 'EXECUTE')",
                ("kokonut_security.create_sensor_anomaly_alert(uuid,uuid,uuid,uuid,text,text)",) * 3,
            )
            if cursor.fetchone() != (True, False, False):
                raise AssertionError("alert function execute grants are broader than intended")
            cursor.execute(
                "SELECT role.rolcanlogin, role.rolinherit, role.rolsuper, "
                "role.rolcreatedb, role.rolcreaterole, role.rolreplication, "
                "role.rolbypassrls, EXISTS (SELECT 1 FROM pg_auth_members "
                "WHERE roleid = role.oid OR member = role.oid) "
                "FROM pg_roles AS role WHERE role.rolname = 'kokonut_anomaly_alert_owner'"
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False, False):
                raise AssertionError("alert function owner has unsafe role attributes or memberships")
            cursor.execute(
                "SELECT table_name, relrowsecurity, relforcerowsecurity "
                "FROM pg_class JOIN pg_namespace ON pg_namespace.oid = relnamespace "
                "JOIN unnest(%s::text[]) AS expected(table_name) ON relname = table_name "
                "WHERE nspname = 'public' ORDER BY table_name",
                (
                    list(
                        (
                            "platform_event",
                            "sensor_reading",
                            "sensor_device",
                            "sensor_type",
                            "alert_rule",
                            "sensor_anomaly_effect",
                            "sensor_alert",
                            "ingestion_log",
                        )
                    ),
                ),
            )
            rls_rows = cursor.fetchall()
            if len(rls_rows) != 8 or any(not row[1] or not row[2] for row in rls_rows):
                raise AssertionError(f"forced-RLS test fixture incomplete: {rls_rows}")
            cursor.execute(
                "SELECT has_any_column_privilege('kokonut_worker_execution', "
                "'public.' || table_name, 'SELECT') OR "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.' || table_name, 'INSERT') OR "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.' || table_name, 'UPDATE') "
                "FROM unnest(%s::text[]) AS tables(table_name)",
                (list(("sensor_alert", "ingestion_log", "sensor_anomaly_effect")),),
            )
            if any(row[0] for row in cursor.fetchall()):
                raise AssertionError("worker role retained direct write-target table access")
        admin.commit()
        checks.append(
            "function ownership, role separation, forced-RLS activation, and direct table grants are verified"
        )

        for connection in connections:
            connection.close()

        migration_hash = hashlib.sha256(migration_sql.encode("utf-8")).hexdigest()
        runner_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 413 signed sensor-anomaly alert, audit, and receipt write",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS],
            "migration_413_sha256": migration_hash,
            "runner_sha256": runner_hash,
            "migration_replay": "passed",
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
                text=True,
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
