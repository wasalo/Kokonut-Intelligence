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
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-11-01-recovery/sensor-alert-worker-acl-732-disposable.json"
BASELINE_FIXTURE = ROOT / "tests/fixtures/sensor_baseline_worker_disposable.sql"
FOLLOW_UP_MIGRATIONS = tuple(
    ROOT / f"schemas/postgres/{number}_{name}.sql"
    for number, name in (
        (649, "signed_sensor_anomaly_replay_inventory"),
        (729, "signed_sensor_baseline_worker"),
        (730, "signed_mock_sensor_cleanup"),
        (731, "sensor_anomaly_sensor_event_inventory"),
        (732, "runtime_sensor_alert_read_only"),
    )
)

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
ATOMICITY_READING_ID = "a0000000-0000-0000-0000-000000000026"
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
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
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


def expect_worker_scope_sqlstate(
    connection, statement: str, params: tuple, expected: str, label: str
) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
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

        docker_sql(docker, container, BASELINE_FIXTURE.read_text(encoding="utf-8"))
        for migration in FOLLOW_UP_MIGRATIONS:
            follow_up_sql = migration.read_text(encoding="utf-8")
            docker_sql(docker, container, follow_up_sql)
            docker_sql(docker, container, follow_up_sql)
        checks.append(
            "migrations 649 and 729–732 apply; the new four-migration slice replays cleanly"
        )

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
        worker_port = int(port_lines[0].rsplit(":", 1)[1])
        os.environ["KOKONUT_SENSOR_ANOMALY_DATABASE_URL"] = (
            "postgresql://kokonut_worker_login:worker-execution-fixture"
            f"@127.0.0.1:{worker_port}/postgres"
        )
        os.environ["KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL"] = RAW_CREDENTIAL
        os.environ["ALERT_WEBHOOK_URL"] = "https://synthetic.invalid/baseline"
        os.environ["ALERT_SMTP_HOST"] = ""
        os.environ["ALERT_EMAIL_TO"] = ""
        os.environ["DIRECTUS_URL"] = ""
        os.environ["DIRECTUS_ADMIN_TOKEN"] = ""
        os.environ["ALERT_SMTP_USER"] = ""
        os.environ["ALERT_SMTP_PASSWORD"] = ""
        port = worker_port
        worker = connect(port, "kokonut_worker_login", "worker-execution-fixture")
        runtime = connect(port, "kokonut_runtime", "worker-runtime-fixture")
        operator_auth = connect(port, "kokonut_operator_auth", "worker-auth-fixture")
        admin = connect(port, "postgres", admin_password)
        connections = (worker, runtime, operator_auth, admin)

        cleanup_and_inventory_acls = admin_query(
            admin,
            """SELECT procedure.proname,
                      pg_catalog.pg_get_userbyid(procedure.proowner),
                      pg_catalog.has_function_privilege(
                          'kokonut_worker_execution', procedure.oid, 'EXECUTE'
                      ),
                      pg_catalog.has_function_privilege(
                          'kokonut_runtime', procedure.oid, 'EXECUTE'
                      ),
                      pg_catalog.has_function_privilege(
                          'kokonut_operator_auth', procedure.oid, 'EXECUTE'
                      ),
                      EXISTS (
                          SELECT 1
                            FROM pg_catalog.aclexplode(COALESCE(
                                procedure.proacl,
                                pg_catalog.acldefault('f', procedure.proowner)
                            )) AS acl
                           WHERE acl.grantee = 0
                             AND acl.privilege_type = 'EXECUTE'
                      )
                 FROM pg_catalog.pg_proc AS procedure
                 JOIN pg_catalog.pg_namespace AS namespace
                   ON namespace.oid = procedure.pronamespace
                WHERE namespace.nspname = 'kokonut_security'
                  AND procedure.proname IN (
                      'delete_mock_sensor_alerts',
                      'delete_mock_sensor_readings',
                      'list_sensor_anomaly_events_for_sensor_since'
                  )
                ORDER BY procedure.proname""",
        )
        if cleanup_and_inventory_acls != [
            (
                "delete_mock_sensor_alerts",
                "kokonut_sensor_mock_cleanup_owner",
                True,
                False,
                False,
                False,
            ),
            (
                "delete_mock_sensor_readings",
                "kokonut_sensor_mock_cleanup_owner",
                True,
                False,
                False,
                False,
            ),
            (
                "list_sensor_anomaly_events_for_sensor_since",
                "kokonut_anomaly_read_owner",
                True,
                False,
                False,
                False,
            ),
        ]:
            raise AssertionError(
                "migration 730/731 function ownership or EXECUTE grants are broader than intended: "
                f"{cleanup_and_inventory_acls}"
            )
        cleanup_owner_attributes = admin_query(
            admin,
            """SELECT role.rolcanlogin, role.rolinherit, role.rolsuper,
                      role.rolcreatedb, role.rolcreaterole, role.rolreplication,
                      role.rolbypassrls,
                      EXISTS (
                          SELECT 1 FROM pg_catalog.pg_auth_members AS membership
                           WHERE membership.roleid = role.oid
                              OR membership.member = role.oid
                      )
                 FROM pg_catalog.pg_roles AS role
                WHERE role.rolname = 'kokonut_sensor_mock_cleanup_owner'""",
        )
        if cleanup_owner_attributes != [
            (False, False, False, False, False, False, False, False)
        ]:
            raise AssertionError(
                "mock cleanup function owner has unsafe role attributes or memberships: "
                f"{cleanup_owner_attributes}"
            )
        checks.append(
            "migrations 730/731 grant function execution only to the worker role and use a restricted cleanup owner"
        )

        from services.ingestion.sensor_baseline_worker import run_baseline_check

        baseline_first = run_baseline_check(LOCATION_ID)
        if baseline_first != {
            "baselines_checked": 1,
            "alerts_triggered": 1,
            "alerts_replayed": 0,
            "notifications_enqueued": 1,
        }:
            raise AssertionError(f"signed baseline check returned unexpected effects: {baseline_first}")
        baseline_alert = admin_query(
            admin,
            """SELECT reading_value, threshold_value, metadata ->> 'sample_count'
                 FROM public.sensor_alert
                WHERE metadata ->> 'source' = 'environmental_baseline'""",
        )
        if baseline_alert != [(14.5, 5, "4")]:
            raise AssertionError(
                "baseline average included a reading whose device/type lineage mismatched: "
                f"{baseline_alert}"
            )
        outbox_before = admin_query(
            admin,
            """SELECT count(*) FROM public.notification_outbox
                WHERE source_event_id IN (
                    SELECT id FROM public.platform_event
                     WHERE event_type = 'sensor_alert'
                       AND payload ->> 'alert_id' IN (
                           SELECT id::TEXT FROM public.sensor_alert
                            WHERE metadata ->> 'source' = 'environmental_baseline'
                       )
                )""",
        )
        if outbox_before != [(1,)]:
            raise AssertionError(f"baseline notification intent missing or duplicated: {outbox_before}")
        baseline_retry = run_baseline_check(LOCATION_ID)
        if baseline_retry != {
            "baselines_checked": 1,
            "alerts_triggered": 0,
            "alerts_replayed": 1,
            "notifications_enqueued": 0,
        }:
            raise AssertionError(f"baseline retry returned unexpected results: {baseline_retry}")
        outbox_after = admin_query(
            admin,
            """SELECT count(*) FROM public.notification_outbox
                WHERE source_event_id IN (
                    SELECT id FROM public.platform_event
                     WHERE event_type = 'sensor_alert'
                       AND payload ->> 'alert_id' IN (
                           SELECT id::TEXT FROM public.sensor_alert
                            WHERE metadata ->> 'source' = 'environmental_baseline'
                       )
                )""",
        )
        if outbox_after != outbox_before:
            raise AssertionError("baseline exact retry duplicated its notification intent")
        checks.append(
            "signed baseline worker uses canonical device type, creates one alert/outbox intent, and replays idempotently"
        )

        # Put prior fixture events outside the short acceptance window, then
        # create fresh source events for exact sensor/device filtering.
        docker_sql(
            docker,
            container,
            f"""
            UPDATE public.platform_event
               SET created_at = NOW() - INTERVAL '2 hours'
             WHERE id NOT IN (
                 'a0000000-0000-0000-0000-000000000037',
                 'a0000000-0000-0000-0000-000000000038',
                 'a0000000-0000-0000-0000-000000000039',
                 'a0000000-0000-0000-0000-000000000040'
             );
            INSERT INTO public.sensor_device (id, location_id, name, sensor_type_id)
            VALUES (
                'a0000000-0000-0000-0000-000000000013',
                '{LOCATION_ID}', 'Synthetic unmarked sensor',
                'a0000000-0000-0000-0000-000000000071'
            );
            INSERT INTO public.sensor_reading (
                id, sensor_id, location_id, sensor_type, value,
                reading_date, reading_time, quality, metadata, created_at
            ) VALUES
                ('{ATOMICITY_READING_ID}', '{SENSOR_ID}', '{LOCATION_ID}',
                 'soil_moisture', 22, CURRENT_DATE, TIME '13:00', 'good',
                 '{{"mock":true}}'::JSONB, NOW()),
                ('a0000000-0000-0000-0000-000000000028', '{SENSOR_ID}',
                 '{LOCATION_ID}', 'soil_moisture', 20, CURRENT_DATE,
                 TIME '13:01', 'good', '{{"mock":true}}'::JSONB, NOW()),
                ('a0000000-0000-0000-0000-000000000029', '{SENSOR_ID}',
                 '{LOCATION_ID}', 'soil_moisture', 21, CURRENT_DATE,
                 TIME '13:02', 'good', '{{"mock":true}}'::JSONB, NOW()),
                ('a0000000-0000-0000-0000-000000000030',
                 'a0000000-0000-0000-0000-000000000013', '{LOCATION_ID}',
                 'soil_moisture', 22, CURRENT_DATE, TIME '13:03', 'good',
                 '{{"mock":true}}'::JSONB, NOW());
            INSERT INTO public.platform_event (
                id, event_type, source_table, source_id, payload,
                priority, status, max_retries
            ) VALUES
                ('a0000000-0000-0000-0000-000000000037', 'sensor_reading',
                 'sensor_reading', 'a0000000-0000-0000-0000-000000000028',
                 '{{"location_id":"{LOCATION_ID}","sensor_id":"{SENSOR_ID}",'
                 '"sensor_device_id":"{SENSOR_ID}"}}'::JSONB,
                 'normal', 'pending', 3),
                ('a0000000-0000-0000-0000-000000000038', 'sensor_reading',
                 'sensor_reading', 'a0000000-0000-0000-0000-000000000028',
                 '{{"location_id":"{LOCATION_ID}","sensor_id":"{SENSOR_ID}",'
                 '"sensor_device_id":"a0000000-0000-0000-0000-000000000013"}}'::JSONB,
                 'normal', 'pending', 3),
                ('a0000000-0000-0000-0000-000000000039', 'sensor_reading',
                 'sensor_reading', 'a0000000-0000-0000-0000-000000000029',
                 '{{"location_id":"{LOCATION_ID}","sensor_device_id":"{SENSOR_ID}"}}'::JSONB,
                 'normal', 'pending', 3),
                ('a0000000-0000-0000-0000-000000000040', 'sensor_reading',
                 'sensor_reading', 'a0000000-0000-0000-0000-000000000030',
                 '{{"location_id":"{LOCATION_ID}","sensor_id":"a0000000-0000-0000-0000-000000000013"}}'::JSONB,
                 'normal', 'pending', 3);
            UPDATE public.platform_event
               SET source_id = '{ATOMICITY_READING_ID}',
                   payload = '{{"location_id":"{LOCATION_ID}",'
                             '"sensor_device_id":"{SENSOR_ID}"}}'::JSONB
             WHERE id = '{ATOMICITY_EVENT_ID}';
            """,
        )

        sensor_inventory_sql = """
        SELECT event_id::text, sensor_id::text
          FROM kokonut_security.list_sensor_anomaly_events_for_sensor_since(
              %s::uuid, %s::uuid, %s::timestamptz, %s::integer
          )
        """
        recent_since = admin_query(
            admin, "SELECT clock_timestamp() - INTERVAL '1 minute'"
        )[0][0]
        set_context(worker)
        bounded_sensor_events = call(
            worker,
            sensor_inventory_sql,
            (LOCATION_ID, SENSOR_ID, recent_since, 1),
        )
        if bounded_sensor_events != [
            ("a0000000-0000-0000-0000-000000000037", SENSOR_ID)
        ]:
            diagnostic = admin_query(
                admin,
                """SELECT event.id::text, event.created_at,
                          %s::timestamptz AS requested_since,
                          statement_timestamp() AS database_now,
                          event.event_type, event.source_table,
                          event.payload ->> 'location_id' AS payload_location,
                          event.payload ->> 'sensor_id' AS payload_sensor,
                          event.payload ->> 'sensor_device_id' AS payload_device,
                          reading.sensor_id::text, reading.location_id::text,
                          reading.sensor_type, device.location_id::text,
                          device.sensor_type_id::text, type.name,
                          (SELECT count(*) FROM public.alert_rule AS rule
                            WHERE rule.enabled
                              AND rule.sensor_type_id = device.sensor_type_id)
                              AS enabled_rule_count,
                          EXISTS (
                              SELECT 1 FROM pg_catalog.pg_policies AS policy
                               WHERE policy.schemaname = 'public'
                                 AND policy.tablename = 'alert_rule'
                                 AND policy.policyname = 'anomaly_read_owner_select'
                          ) AS reader_policy_exists
                     FROM public.platform_event AS event
                     JOIN public.sensor_reading AS reading
                       ON reading.id = event.source_id
                     JOIN public.sensor_device AS device
                       ON device.id = reading.sensor_id
                     JOIN public.sensor_type AS type
                       ON type.id = device.sensor_type_id
                    WHERE event.id =
                        'a0000000-0000-0000-0000-000000000037'""",
                (recent_since,),
            )
            raise AssertionError(
                "sensor-specific event inventory did not enforce source/device/limit: "
                f"{bounded_sensor_events}; diagnostic={diagnostic}"
            )
        set_context(worker)
        all_sensor_events = call(
            worker,
            sensor_inventory_sql,
            (LOCATION_ID, SENSOR_ID, recent_since, 100),
        )
        if all_sensor_events != [
            ("a0000000-0000-0000-0000-000000000037", SENSOR_ID),
            ("a0000000-0000-0000-0000-000000000039", SENSOR_ID),
        ]:
            raise AssertionError(
                f"sensor-specific event inventory returned a mismatched event: {all_sensor_events}"
            )
        with admin.cursor() as cursor:
            cursor.execute(
                """INSERT INTO public.sensor_anomaly_effect (
                           location_id, source_reading_id, alert_rule_id,
                           source_event_id, outcome
                       )
                       SELECT reading.location_id, reading.id, rule.id,
                              %s::uuid, 'no_match'
                         FROM public.sensor_reading AS reading
                         JOIN public.sensor_device AS device
                           ON device.id = reading.sensor_id
                          AND device.location_id = reading.location_id
                         JOIN public.alert_rule AS rule
                           ON rule.sensor_type_id = device.sensor_type_id
                          AND rule.enabled
                        WHERE reading.id = %s::uuid""",
                (
                    "a0000000-0000-0000-0000-000000000037",
                    "a0000000-0000-0000-0000-000000000028",
                ),
            )
            if cursor.rowcount < 1:
                raise AssertionError("receipt fixture inserted no effects for the reading's enabled rules")
        admin.commit()
        set_context(worker)
        unreceipted_sensor_events = call(
            worker,
            sensor_inventory_sql,
            (LOCATION_ID, SENSOR_ID, recent_since, 100),
        )
        if unreceipted_sensor_events != [
            ("a0000000-0000-0000-0000-000000000039", SENSOR_ID)
        ]:
            raise AssertionError(
                "sensor-specific event inventory did not suppress an already receipted reading: "
                f"{unreceipted_sensor_events}"
            )
        set_context(worker)
        repeated_sensor_events = call(
            worker,
            sensor_inventory_sql,
            (LOCATION_ID, SENSOR_ID, recent_since, 100),
        )
        if repeated_sensor_events != unreceipted_sensor_events:
            raise AssertionError(
                "sensor-specific inventory retry changed after a receipt was recorded: "
                f"{repeated_sensor_events}"
            )
        set_context(worker)
        other_device_events = call(
            worker,
            sensor_inventory_sql,
            (
                LOCATION_ID,
                "a0000000-0000-0000-0000-000000000013",
                recent_since,
                100,
            ),
        )
        if other_device_events != [
            ("a0000000-0000-0000-0000-000000000040", "a0000000-0000-0000-0000-000000000013")
        ]:
            raise AssertionError(
                f"sensor-specific event inventory crossed device scope: {other_device_events}"
            )
        expect_worker_scope_sqlstate(
            worker,
            sensor_inventory_sql,
            (LOCATION_ID, SENSOR_ID, recent_since, 100),
            "42501",
            "unsigned sensor-specific event inventory",
        )
        set_context(worker)
        expect_sqlstate(
            worker,
            sensor_inventory_sql,
            (OTHER_LOCATION_ID, SENSOR_ID, recent_since, 100),
            "42501",
            "cross-location sensor-specific event inventory",
        )
        checks.append(
            "migration 731 enforces signed location, exact sensor/device and event payload, bounded results, and stable receipt-aware retries"
        )

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

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'SELECT'), "
                "has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'INSERT'), "
                "has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'UPDATE'), "
                "has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'DELETE'), "
                "has_table_privilege('kokonut_worker_execution', 'public.sensor_alert', 'INSERT'), "
                "has_column_privilege('kokonut_runtime', 'public.sensor_alert', 'status', 'INSERT'), "
                "has_column_privilege('kokonut_runtime', 'public.sensor_alert', 'message', 'UPDATE'), "
                "EXISTS (SELECT 1 FROM pg_catalog.pg_class AS relation "
                "CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE("
                "relation.relacl, pg_catalog.acldefault('r', relation.relowner))) AS acl "
                "WHERE relation.oid = 'public.sensor_alert'::regclass "
                "AND acl.grantee = 0 AND acl.privilege_type IN "
                "('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')), "
                "EXISTS (SELECT 1 FROM pg_catalog.pg_attribute AS attribute "
                "CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl "
                "WHERE attribute.attrelid = 'public.sensor_alert'::regclass "
                "AND attribute.attnum > 0 AND NOT attribute.attisdropped "
                "AND acl.grantee = 0 AND acl.privilege_type IN "
                "('INSERT', 'UPDATE', 'REFERENCES'))"
            )
            if cursor.fetchone() != (
                True, False, False, False, False, False, False, False, False
            ):
                raise AssertionError("migration 732 did not leave sensor_alert runtime read-only")
        admin.commit()
        checks.append(
            "migration 732 clears table and column DML from runtime/worker/PUBLIC while preserving runtime SELECT"
        )

        from psycopg2 import sql

        from services.migration.runtime_role import _apply_scoped_write_boundary

        with admin.cursor() as cursor:
            _apply_scoped_write_boundary(cursor, sql.Identifier("kokonut_runtime"))
        admin.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'SELECT'), "
                "has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'INSERT'), "
                "has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'UPDATE'), "
                "has_table_privilege('kokonut_runtime', 'public.sensor_alert', 'DELETE')"
            )
            if cursor.fetchone() != (True, False, False, False):
                raise AssertionError("runtime provisioner regranted sensor_alert writes")
        admin.commit()
        checks.append("runtime-role provisioner reapplication does not reopen sensor_alert writes")

        from services.ingestion import sensor_mock_cleanup_worker

        cleanup_before = admin_query(
            admin,
            """SELECT
                      (SELECT count(*) FROM public.sensor_alert
                        WHERE location_id = %s::uuid AND sensor_device_id = %s::uuid),
                      (SELECT count(*) FROM public.sensor_reading
                        WHERE location_id = %s::uuid AND sensor_id = %s::uuid
                          AND metadata ->> 'mock' = 'true'),
                      (SELECT count(*) FROM public.sensor_reading
                        WHERE id = 'a0000000-0000-0000-0000-000000000030'),
                      (SELECT count(*) FROM public.sensor_alert
                        WHERE location_id = %s::uuid AND sensor_device_id =
                          'a0000000-0000-0000-0000-000000000012'::uuid)""",
            (LOCATION_ID, SENSOR_ID, LOCATION_ID, SENSOR_ID, OTHER_LOCATION_ID),
        )
        if len(cleanup_before) != 1 or cleanup_before[0][2:] != (1, 1):
            raise AssertionError(f"mock cleanup precondition failed: {cleanup_before}")
        expected_alerts, expected_readings = cleanup_before[0][:2]
        if expected_alerts < 1 or expected_readings < 1:
            raise AssertionError(f"mock cleanup fixture is empty: {cleanup_before}")

        expect_worker_scope_sqlstate(
            worker,
            "SELECT kokonut_security.delete_mock_sensor_alerts(%s::uuid)",
            (LOCATION_ID,),
            "42501",
            "unsigned mock-alert cleanup",
        )
        expect_worker_scope_sqlstate(
            worker,
            "SELECT kokonut_security.delete_mock_sensor_readings(%s::uuid)",
            (LOCATION_ID,),
            "42501",
            "unsigned mock-reading cleanup",
        )
        for statement, label in (
            (
                "SELECT kokonut_security.delete_mock_sensor_alerts(%s::uuid)",
                "cross-location mock-alert cleanup",
            ),
            (
                "SELECT kokonut_security.delete_mock_sensor_readings(%s::uuid)",
                "cross-location mock-reading cleanup",
            ),
        ):
            set_context(worker)
            expect_sqlstate(
                worker,
                statement,
                (OTHER_LOCATION_ID,),
                "42501",
                label,
            )

        deleted_alerts = sensor_mock_cleanup_worker.delete_mock_sensor_alerts(LOCATION_ID)
        deleted_readings = sensor_mock_cleanup_worker.delete_mock_sensor_readings(LOCATION_ID)
        if (deleted_alerts, deleted_readings) != (expected_alerts, expected_readings):
            raise AssertionError(
                "mock cleanup deleted an unexpected number of rows: "
                f"{deleted_alerts=}, {deleted_readings=}, {cleanup_before=}"
            )
        if sensor_mock_cleanup_worker.delete_mock_sensor_alerts(LOCATION_ID) != 0:
            raise AssertionError("mock alert cleanup retry was not idempotent")
        if sensor_mock_cleanup_worker.delete_mock_sensor_readings(LOCATION_ID) != 0:
            raise AssertionError("mock reading cleanup retry was not idempotent")
        cleanup_after = admin_query(
            admin,
            """SELECT
                      (SELECT count(*) FROM public.sensor_alert
                        WHERE location_id = %s::uuid AND sensor_device_id = %s::uuid),
                      (SELECT count(*) FROM public.sensor_reading
                        WHERE location_id = %s::uuid AND sensor_id = %s::uuid
                          AND metadata ->> 'mock' = 'true'),
                      (SELECT count(*) FROM public.sensor_reading
                        WHERE id = 'a0000000-0000-0000-0000-000000000030'),
                      (SELECT count(*) FROM public.sensor_alert
                        WHERE location_id = %s::uuid AND sensor_device_id =
                          'a0000000-0000-0000-0000-000000000012'::uuid)""",
            (LOCATION_ID, SENSOR_ID, LOCATION_ID, SENSOR_ID, OTHER_LOCATION_ID),
        )
        if cleanup_after != [(0, 0, 1, 1)]:
            raise AssertionError(f"mock cleanup crossed markers/location scope: {cleanup_after}")
        checks.append(
            "migration 730 deletes only signed-location demo alerts/readings, rejects missing/cross scope, and retries idempotently"
        )

        for connection in connections:
            connection.close()

        migration_hash = hashlib.sha256(migration_sql.encode("utf-8")).hexdigest()
        runner_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Signed sensor anomaly, baseline, mock cleanup, replay, and shared-runtime alert ACLs",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS]
            + [migration.relative_to(ROOT).as_posix() for migration in FOLLOW_UP_MIGRATIONS],
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
