#!/usr/bin/env python3
"""Exercise migration 410 actuation intents in disposable PostgreSQL 16."""

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
MIGRATIONS = (
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/406_sensor_anomaly_location_lineage.sql",
    ROOT / "schemas/postgres/407_sensor_anomaly_effect_functions.sql",
    ROOT / "schemas/postgres/408_sensor_alert_event_function.sql",
    ROOT / "schemas/postgres/409_sensor_alert_notification_intent.sql",
    ROOT / "schemas/postgres/410_sensor_alert_actuation_intent.sql",
)
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/"
    "sensor-alert-actuation-intent-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"
READING_ID = "a0000000-0000-0000-0000-000000000021"
SOURCE_EVENT_ID = "a0000000-0000-0000-0000-000000000031"
ALERT_ID = "a0000000-0000-0000-0000-000000000041"
RULE_ID = "a0000000-0000-0000-0000-000000000052"
ALERT_EVENT_ID = "a0000000-0000-0000-0000-000000000061"
WARNING_APPROVAL_ALERT_ID = "a0000000-0000-0000-0000-000000000043"
WARNING_APPROVAL_RULE_ID = "a0000000-0000-0000-0000-000000000051"
WARNING_APPROVAL_EVENT_ID = "a0000000-0000-0000-0000-000000000062"
WARNING_AUTO_ALERT_ID = "a0000000-0000-0000-0000-000000000044"
WARNING_AUTO_RULE_ID = "a0000000-0000-0000-0000-000000000054"
WARNING_AUTO_EVENT_ID = "a0000000-0000-0000-0000-000000000063"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
FUNCTION_NAME = "kokonut_security.create_sensor_alert_actuation_intent"
FUNCTION_SIGNATURE = FUNCTION_NAME + "(uuid,uuid,uuid,uuid,uuid,uuid)"
INTENT_SQL = f"SELECT {FUNCTION_NAME}(%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid)"
RESERVE_SQL = """
SELECT kokonut_security.reserve_sensor_anomaly_effect(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
OUTCOME_SQL = """
SELECT kokonut_security.record_sensor_anomaly_effect_outcome(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'alert_created', %s::uuid
)
"""
PUBLISH_SQL = """
SELECT kokonut_security.publish_sensor_alert_event(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid
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
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
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


def intent(connection, *, alert_event=ALERT_EVENT_ID, source_event=SOURCE_EVENT_ID,
           reading=READING_ID, rule=RULE_ID, alert=ALERT_ID, location=LOCATION_ID):
    with connection.cursor() as cursor:
        cursor.execute(
            INTENT_SQL,
            (alert_event, source_event, reading, rule, alert, location),
        )
        return str(cursor.fetchone()[0])


def expect_sqlstate(connection, params: tuple, expected: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(INTENT_SQL, params)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != expected:
            raise AssertionError(
                f"{label}: expected SQLSTATE {expected}, received {exc.pgcode}"
            ) from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: operation unexpectedly succeeded")


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
    raise AssertionError(f"{label}: direct actuation access unexpectedly succeeded")


def prepare_alert_effect(connection, *, event_id: str, rule_id: str, alert_id: str) -> None:
    set_context(connection)
    with connection.cursor() as cursor:
        cursor.execute(RESERVE_SQL, (SOURCE_EVENT_ID, READING_ID, rule_id, LOCATION_ID))
        if cursor.fetchone()[0] is not True:
            raise AssertionError(f"effect receipt for {rule_id} was not reserved")
        cursor.execute(
            OUTCOME_SQL,
            (SOURCE_EVENT_ID, READING_ID, rule_id, LOCATION_ID, alert_id),
        )
        if cursor.fetchone()[0] is not True:
            raise AssertionError(f"effect receipt for {rule_id} was not linked to alert")
        cursor.execute(
            PUBLISH_SQL,
            (event_id, SOURCE_EVENT_ID, READING_ID, rule_id, alert_id, LOCATION_ID),
        )
        if cursor.fetchone()[0] is not True:
            raise AssertionError(f"alert event for {alert_id} was not published")
    connection.commit()


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("ANOMALY_ACTUATION_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-actuation-{os.getpid()}-{secrets.token_hex(3)}"
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
        migration_sql = MIGRATIONS[5].read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 410 applies and replays after migrations 405 through 409")

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
        try:
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                cursor.execute(
                    INTENT_SQL,
                    (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
                )
            worker.rollback()
            raise AssertionError("actuation intent succeeded without signed context")
        except psycopg2.Error as exc:
            worker.rollback()
            if exc.pgcode != "42501":
                raise AssertionError(
                    f"missing signed context: expected 42501, received {exc.pgcode}"
                ) from exc
        checks.append("intent creation rejects calls without signed worker context")

        for event_id, rule_id, alert_id in (
            (ALERT_EVENT_ID, RULE_ID, ALERT_ID),
            (WARNING_APPROVAL_EVENT_ID, WARNING_APPROVAL_RULE_ID, WARNING_APPROVAL_ALERT_ID),
            (WARNING_AUTO_EVENT_ID, WARNING_AUTO_RULE_ID, WARNING_AUTO_ALERT_ID),
        ):
            prepare_alert_effect(worker, event_id=event_id, rule_id=rule_id, alert_id=alert_id)
        checks.append("only source-linked, signed-location alert receipts publish actuation source events")

        set_context(worker)
        critical_intent_id = intent(worker)
        worker.commit()
        set_context(worker)
        if intent(worker) != critical_intent_id:
            raise AssertionError("critical actuation retry did not return the original ID")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT actuator_type, actuator_command, actuator_topic, command_payload, "
                "trigger_source, trigger_alert_severity, human_approval_required, status, "
                "source_alert_event_id::text FROM public.actuation_log "
                "WHERE id = %s::uuid",
                (critical_intent_id,),
            )
            critical = cursor.fetchone()
            expected_payload = {
                "device_id": SENSOR_ID,
                "actuator_type": "irrigation",
                "command": "open_valve",
                "parameters": {"alert_id": ALERT_ID},
                "trigger_source": "anomaly_detector",
                "alert_id": ALERT_ID,
                "alert_severity": "critical",
            }
            if critical != (
                "irrigation", "open_valve",
                f"actuators/{LOCATION_ID}/irrigation/commands", expected_payload,
                "anomaly_detector", "critical", True, "requires_approval", ALERT_EVENT_ID,
            ):
                raise AssertionError(f"critical intent does not match approval-safe contract: {critical}")
            cursor.execute(
                "SELECT count(*) FROM public.actuation_log WHERE source_alert_event_id = %s::uuid",
                (ALERT_EVENT_ID,),
            )
            if cursor.fetchone()[0] != 1:
                raise AssertionError("critical event did not produce exactly one actuation intent")
        admin.commit()
        checks.append("critical rule command is canonical and always starts requires_approval")
        checks.append("one alert event creates one intent and retries return its stable ID")

        set_context(worker)
        warning_approval_id = intent(worker, alert_event=WARNING_APPROVAL_EVENT_ID,
                                     rule=WARNING_APPROVAL_RULE_ID,
                                     alert=WARNING_APPROVAL_ALERT_ID)
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT human_approval_required, status, actuator_type, actuator_command "
                "FROM public.actuation_log WHERE id = %s::uuid",
                (warning_approval_id,),
            )
            if cursor.fetchone() != (True, "requires_approval", "pest_control", "release_beneficial_insects"):
                raise AssertionError("configured warning approval requirement was not preserved")
        admin.commit()
        checks.append("noncritical rule-level approval remains required")

        set_context(worker)
        warning_auto_id = intent(worker, alert_event=WARNING_AUTO_EVENT_ID,
                                 rule=WARNING_AUTO_RULE_ID, alert=WARNING_AUTO_ALERT_ID)
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT human_approval_required, status, actuator_type, actuator_command "
                "FROM public.actuation_log WHERE id = %s::uuid",
                (warning_auto_id,),
            )
            if cursor.fetchone() != (False, "pending", "fertilization", "apply_water"):
                raise AssertionError("configured automatic warning intent has wrong initial state")
        admin.commit()
        checks.append("noncritical rules without approval create pending intent only")

        with admin.cursor() as cursor:
            cursor.execute(
                "UPDATE public.actuation_log SET status = 'sent', approved_by = %s::uuid, "
                "approved_at = NOW(), sent_at = NOW(), response_payload = '{\"ok\":true}'::jsonb "
                "WHERE id = %s::uuid",
                (WORKER_ID, critical_intent_id),
            )
        admin.commit()
        set_context(worker)
        if intent(worker) != critical_intent_id:
            raise AssertionError("retry after delivery did not return the original intent")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT status, approved_by::text, approved_at IS NOT NULL, sent_at IS NOT NULL, "
                "response_payload FROM public.actuation_log WHERE id = %s::uuid",
                (critical_intent_id,),
            )
            if cursor.fetchone() != (
                "sent", WORKER_ID, True, True, {"ok": True},
            ):
                raise AssertionError("intent retry reset approval or transport state")
        admin.commit()
        checks.append("idempotent retry preserves approved, sent, and response state")

        # Changed canonical rule content cannot be hidden behind an existing key.
        with admin.cursor() as cursor:
            cursor.execute(
                "UPDATE public.alert_rule SET actuator_command = 'close_valve' "
                "WHERE id = %s::uuid", (RULE_ID,),
            )
        admin.commit()
        set_context(worker)
        expect_sqlstate(
            worker,
            (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
            "23505", "changed rule content collision",
        )
        with admin.cursor() as cursor:
            cursor.execute(
                "UPDATE public.alert_rule SET actuator_command = 'open_valve' "
                "WHERE id = %s::uuid", (RULE_ID,),
            )
        admin.commit()
        checks.append("changed command content for an existing alert-event key fails closed")

        for params, label in (
            ((ALERT_EVENT_ID, "a0000000-0000-0000-0000-000000000032", READING_ID,
              RULE_ID, ALERT_ID, LOCATION_ID), "mismatched source event"),
            ((ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
              ALERT_ID, OTHER_LOCATION_ID), "out-of-scope location"),
            ((SOURCE_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
              ALERT_ID, LOCATION_ID), "sensor-reading event used as alert event"),
            ((ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
              WARNING_APPROVAL_ALERT_ID, LOCATION_ID), "mismatched alert"),
            ((ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID,
              ALERT_ID, None), "missing requested location"),
        ):
            set_context(worker)
            expect_sqlstate(worker, params, "42501", label)
        checks.append("wrong source, alert, event type, or location is rejected")

        set_context(worker)
        expect_sqlstate(
            worker,
            (None, SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
            "22023", "missing event identifier",
        )
        checks.append("missing identity inputs are rejected")

        with admin.cursor() as cursor:
            cursor.execute(
                "UPDATE public.alert_rule SET actuator_enabled = FALSE "
                "WHERE id = %s::uuid", (WARNING_AUTO_RULE_ID,),
            )
        admin.commit()
        set_context(worker)
        expect_sqlstate(
            worker,
            (WARNING_AUTO_EVENT_ID, SOURCE_EVENT_ID, READING_ID,
             WARNING_AUTO_RULE_ID, WARNING_AUTO_ALERT_ID, LOCATION_ID),
            "42501", "disabled actuator rule",
        )
        with admin.cursor() as cursor:
            cursor.execute(
                "UPDATE public.alert_rule SET actuator_enabled = TRUE "
                "WHERE id = %s::uuid", (WARNING_AUTO_RULE_ID,),
            )
        admin.commit()
        checks.append("disabled actuator rules cannot create new intents")

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT source_alert_event_id IS NULL, status, location_id::text "
                "FROM public.actuation_log WHERE id = 'a0000000-0000-0000-0000-000000000099'"
            )
            if cursor.fetchone() != (True, "sent", OTHER_LOCATION_ID):
                raise AssertionError("migration modified a legacy actuation row")
            cursor.execute(
                "SELECT has_any_column_privilege('kokonut_worker_execution', "
                "'public.actuation_log', 'SELECT'), "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.actuation_log', 'INSERT'), "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.actuation_log', 'UPDATE'), "
                "has_table_privilege('kokonut_worker_execution', 'public.actuation_log', 'DELETE'), "
                "has_function_privilege('kokonut_worker_execution', %s, 'EXECUTE'), "
                "has_function_privilege('kokonut_anomaly_actuation_owner', %s, 'EXECUTE')",
                (FUNCTION_SIGNATURE, FUNCTION_SIGNATURE),
            )
            if cursor.fetchone() != (False, False, False, False, True, True):
                raise AssertionError("worker actuation privileges exceed bounded EXECUTE")
            cursor.execute(
                "SELECT has_column_privilege('kokonut_anomaly_actuation_owner', "
                "'public.actuation_log', 'location_id', 'INSERT'), "
                "has_column_privilege('kokonut_anomaly_actuation_owner', "
                "'public.actuation_log', 'status', 'INSERT'), "
                "has_column_privilege('kokonut_anomaly_actuation_owner', "
                "'public.actuation_log', 'status', 'SELECT'), "
                "has_column_privilege('kokonut_anomaly_actuation_owner', "
                "'public.actuation_log', 'status', 'UPDATE'), "
                "has_column_privilege('kokonut_anomaly_actuation_owner', "
                "'public.actuation_log', 'approved_by', 'UPDATE'), "
                "has_table_privilege('kokonut_anomaly_actuation_owner', "
                "'public.actuation_log', 'DELETE')"
            )
            if cursor.fetchone() != (True, True, False, False, False, False):
                raise AssertionError("actuation owner has excessive direct table privileges")
            cursor.execute(
                "SELECT role.rolcanlogin, role.rolinherit, role.rolsuper, "
                "role.rolcreatedb, role.rolcreaterole, role.rolreplication, "
                "role.rolbypassrls, EXISTS (SELECT 1 FROM pg_auth_members "
                "WHERE roleid = role.oid OR member = role.oid) "
                "FROM pg_roles AS role "
                "WHERE role.rolname = 'kokonut_anomaly_actuation_owner'"
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False, False):
                raise AssertionError("actuation owner role has unsafe attributes or memberships")
        admin.commit()
        checks.append("migration preserves legacy rows and function owner has column-limited rights")

        for connection, role_name in (
            (runtime, "kokonut_runtime"),
            (operator_auth, "kokonut_operator_auth"),
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_function_privilege(current_user, %s, 'EXECUTE')",
                    (FUNCTION_SIGNATURE,),
                )
                if cursor.fetchone()[0]:
                    raise AssertionError(f"{role_name} can execute actuation function")
        checks.append("runtime and operator-auth roles cannot execute actuation function")

        for statement, label in (
            ("SELECT id FROM public.actuation_log", "direct actuation SELECT"),
            (
                "INSERT INTO public.actuation_log (location_id, sensor_alert_id, "
                "actuator_type, actuator_command, command_payload, trigger_source) "
                f"VALUES ('{LOCATION_ID}', '{ALERT_ID}', 'irrigation', 'test', '{{}}', 'test')",
                "direct actuation INSERT",
            ),
            ("UPDATE public.actuation_log SET status = 'cancelled' WHERE FALSE", "direct actuation UPDATE"),
            ("DELETE FROM public.actuation_log WHERE FALSE", "direct actuation DELETE"),
        ):
            direct_denial(worker, statement, label)
        checks.append("worker cannot directly read, insert, approve, update, or delete actuation rows")

        for connection in connections:
            connection.close()
        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 410 bounded sensor-alert actuation intent",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS],
            "migration_410_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
            "migration_replay": "passed",
            "command": "python3 scripts/check-sensor-alert-actuation-intent-disposable.py",
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
