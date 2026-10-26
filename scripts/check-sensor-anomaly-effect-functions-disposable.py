#!/usr/bin/env python3
"""Exercise bounded anomaly-effect functions in disposable PostgreSQL 16."""

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
FIXTURE_ROOT = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
FIXTURE_ANOMALY = ROOT / "tests/fixtures/sensor_anomaly_effect_functions_disposable.sql"
MIGRATION_CONTEXT = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
MIGRATION_LINEAGE = ROOT / "schemas/postgres/406_sensor_anomaly_location_lineage.sql"
MIGRATION_EFFECTS = ROOT / "schemas/postgres/407_sensor_anomaly_effect_functions.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-16-recovery/"
    "sensor-anomaly-effect-functions-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
READING_ID = "a0000000-0000-0000-0000-000000000021"
OTHER_READING_ID = "a0000000-0000-0000-0000-000000000022"
EVENT_ID = "a0000000-0000-0000-0000-000000000031"
SINGLE_SELECTOR_EVENT_ID = "a0000000-0000-0000-0000-000000000034"
ALERT_ID = "a0000000-0000-0000-0000-000000000041"
OTHER_LOCATION_ALERT_ID = "a0000000-0000-0000-0000-000000000042"
RULE_ID = "a0000000-0000-0000-0000-000000000051"
SECOND_RULE_ID = "a0000000-0000-0000-0000-000000000052"
DISABLED_RULE_ID = "a0000000-0000-0000-0000-000000000053"
UNUSED_RULE_ID = "a0000000-0000-0000-0000-000000000054"
RESOURCE = "sensor_reading"
ACTION = "process"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()

RESERVE_SQL = """
SELECT kokonut_security.reserve_sensor_anomaly_effect(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid
)
"""
OUTCOME_SQL = """
SELECT kokonut_security.record_sensor_anomaly_effect_outcome(
    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid
)
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
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
    successes = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
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


def set_context(connection):
    from services.common.tenant_context import set_worker_tenant_context

    return set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=LOCATION_ID,
        resource=RESOURCE,
        action=ACTION,
    )


def call_reserve(connection, event_id: str, reading_id: str, rule_id: str, location_id=LOCATION_ID):
    with connection.cursor() as cursor:
        cursor.execute(RESERVE_SQL, (event_id, reading_id, rule_id, location_id))
        return cursor.fetchone()[0]


def call_outcome(
    connection,
    event_id: str,
    reading_id: str,
    rule_id: str,
    outcome: str,
    alert_id: str | None = None,
    location_id=LOCATION_ID,
):
    with connection.cursor() as cursor:
        cursor.execute(
            OUTCOME_SQL,
            (event_id, reading_id, rule_id, location_id, outcome, alert_id),
        )
        return cursor.fetchone()[0]


def expect_sqlstate(connection, sql: str, params: tuple, expected: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != expected:
            raise AssertionError(
                f"{label}: expected SQLSTATE {expected}, received {exc.pgcode}"
            ) from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: call unexpectedly succeeded")


def expect_direct_denial(connection, statement: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
            cursor.execute(statement)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != "42501":
            raise AssertionError(f"{label}: expected privilege denial, received {exc.pgcode}") from exc
        return
    connection.rollback()
    raise AssertionError(f"{label}: direct table access unexpectedly succeeded")


def check_signed_scope_and_replay(worker, checks: list[str]) -> None:
    with worker.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
    expect_sqlstate(
        worker,
        RESERVE_SQL,
        (EVENT_ID, READING_ID, RULE_ID, LOCATION_ID),
        "42501",
        "unsigned reservation",
    )
    checks.append("receipt reservation rejects missing signed worker context")

    scope = set_context(worker)
    if scope.location_id != LOCATION_ID or scope.tenant_id != TENANT_ID:
        raise AssertionError("signed worker setter returned an unexpected tenant scope")
    if call_reserve(worker, EVENT_ID, READING_ID, RULE_ID) is not True:
        raise AssertionError("first matching receipt reservation was not inserted")
    if call_reserve(worker, EVENT_ID, READING_ID, RULE_ID) is not False:
        raise AssertionError("duplicate receipt reservation was not suppressed")
    worker.commit()
    checks.append("matching signed scope reserves once and suppresses duplicate retries")


def check_outcome_transitions(worker, checks: list[str]) -> None:
    set_context(worker)
    if call_outcome(worker, EVENT_ID, READING_ID, RULE_ID, "cooldown") is not True:
        raise AssertionError("no_match receipt did not transition to cooldown")
    if call_outcome(worker, EVENT_ID, READING_ID, RULE_ID, "cooldown") is not False:
        raise AssertionError("cooldown transition was not replay-safe")
    worker.commit()
    checks.append("cooldown outcome transitions once and cannot be replayed")

    set_context(worker)
    if call_reserve(worker, SINGLE_SELECTOR_EVENT_ID, READING_ID, SECOND_RULE_ID) is not True:
        raise AssertionError("single-selector matching event did not reserve")
    if call_outcome(
        worker,
        SINGLE_SELECTOR_EVENT_ID,
        READING_ID,
        SECOND_RULE_ID,
        "alert_created",
        ALERT_ID,
    ) is not True:
        raise AssertionError("matching alert did not link to the reserved receipt")
    if call_outcome(
        worker,
        SINGLE_SELECTOR_EVENT_ID,
        READING_ID,
        SECOND_RULE_ID,
        "alert_created",
        ALERT_ID,
    ) is not False:
        raise AssertionError("alert-created transition was not replay-safe")
    worker.commit()
    checks.append("alert-created outcome links a same-location alert and transitions once")


def check_reservation_denials(worker, checks: list[str]) -> None:
    invalid_sources = (
        ("a0000000-0000-0000-0000-000000000032", READING_ID, "conflicting sensor selectors"),
        ("a0000000-0000-0000-0000-000000000033", OTHER_READING_ID, "other location"),
        ("a0000000-0000-0000-0000-000000000035", READING_ID, "wrong event type and source table"),
        (EVENT_ID, OTHER_READING_ID, "event and reading mismatch"),
    )
    for event_id, reading_id, label in invalid_sources:
        set_context(worker)
        expect_sqlstate(
            worker,
            RESERVE_SQL,
            (event_id, reading_id, UNUSED_RULE_ID, LOCATION_ID),
            "42501",
            label,
        )

    set_context(worker)
    expect_sqlstate(
        worker,
        RESERVE_SQL,
        (EVENT_ID, READING_ID, DISABLED_RULE_ID, LOCATION_ID),
        "42501",
        "disabled alert rule",
    )
    set_context(worker)
    expect_sqlstate(
        worker,
        RESERVE_SQL,
        (EVENT_ID, READING_ID, RULE_ID, OTHER_LOCATION_ID),
        "42501",
        "requested location differs from signed scope",
    )
    worker.rollback()
    checks.append(
        "reservation rejects conflicting selectors, wrong event/reading/location, "
        "disabled rules, and out-of-scope locations"
    )


def check_outcome_denials(worker, checks: list[str]) -> None:
    set_context(worker)
    if call_reserve(worker, SINGLE_SELECTOR_EVENT_ID, READING_ID, UNUSED_RULE_ID) is not True:
        raise AssertionError("alert-link denial fixture receipt did not reserve")
    worker.commit()

    invalid_outcomes = (
        ("published", None, "22023", "unsupported outcome"),
        ("cooldown", ALERT_ID, "22023", "cooldown with alert link"),
        ("alert_created", None, "42501", "alert-created without alert"),
        ("alert_created", OTHER_LOCATION_ALERT_ID, "42501", "cross-location alert"),
        ("alert_created", ALERT_ID, "42501", "alert rule does not match receipt"),
    )
    for outcome, alert_id, sqlstate, label in invalid_outcomes:
        set_context(worker)
        expect_sqlstate(
            worker,
            OUTCOME_SQL,
            (
                SINGLE_SELECTOR_EVENT_ID,
                READING_ID,
                UNUSED_RULE_ID,
                LOCATION_ID,
                outcome,
                alert_id,
            ),
            sqlstate,
            label,
        )
    worker.rollback()
    checks.append(
        "outcome API rejects unsupported transitions, bad alert links, and cross-location alerts"
    )


def check_privileges(admin, runtime, operator_auth, worker, checks: list[str]) -> None:
    with admin.cursor() as cursor:
        cursor.execute(
            """
            SELECT has_any_column_privilege(
                       'kokonut_worker_execution', 'public.sensor_anomaly_effect', 'SELECT'
                   ),
                   has_any_column_privilege(
                       'kokonut_worker_execution', 'public.sensor_anomaly_effect', 'INSERT'
                   ),
                   has_any_column_privilege(
                       'kokonut_worker_execution', 'public.sensor_anomaly_effect', 'UPDATE'
                   ),
                   has_table_privilege(
                       'kokonut_worker_execution', 'public.sensor_anomaly_effect', 'DELETE'
                   ),
                   has_function_privilege(
                       'kokonut_worker_execution',
                       'kokonut_security.reserve_sensor_anomaly_effect(uuid,uuid,uuid,uuid)',
                       'EXECUTE'
                   ),
                   has_function_privilege(
                       'kokonut_worker_execution',
                       'kokonut_security.record_sensor_anomaly_effect_outcome(uuid,uuid,uuid,uuid,text,uuid)',
                       'EXECUTE'
                   )
            """
        )
        result = cursor.fetchone()
        if result != (False, False, False, False, True, True):
            raise AssertionError(f"unexpected worker receipt privileges: {result}")

        cursor.execute(
            """
            SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole,
                   rolreplication, rolbypassrls
              FROM pg_roles WHERE rolname = 'kokonut_anomaly_effect_owner'
            """
        )
        if cursor.fetchone() != (False, False, False, False, False, False, False):
            raise AssertionError("anomaly function owner has unsafe role attributes")

    for connection, role_name in ((runtime, "kokonut_runtime"), (operator_auth, "kokonut_operator_auth")):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_function_privilege(current_user, %s, 'EXECUTE')",
                ("kokonut_security.reserve_sensor_anomaly_effect(uuid,uuid,uuid,uuid)",),
            )
            if cursor.fetchone()[0]:
                raise AssertionError(f"{role_name} can execute anomaly receipt functions")
    checks.append(
        "worker has only bounded receipt EXECUTE grants; runtime/auth lack EXECUTE and worker has no direct DML"
    )

    for statement, label in (
        ("SELECT * FROM public.sensor_anomaly_effect", "direct receipt SELECT"),
        (
            "INSERT INTO public.sensor_anomaly_effect "
            "(location_id, source_reading_id, alert_rule_id, source_event_id, outcome) "
            f"VALUES ('{LOCATION_ID}', '{READING_ID}', '{UNUSED_RULE_ID}', "
            f"'{EVENT_ID}', 'no_match')",
            "direct receipt INSERT",
        ),
        (
            "UPDATE public.sensor_anomaly_effect SET outcome = 'cooldown' "
            f"WHERE source_reading_id = '{READING_ID}'",
            "direct receipt UPDATE",
        ),
        (
            "DELETE FROM public.sensor_anomaly_effect "
            f"WHERE source_reading_id = '{READING_ID}'",
            "direct receipt DELETE",
        ),
    ):
        expect_direct_denial(worker, statement, label)
    checks.append("worker login cannot directly SELECT, INSERT, UPDATE, or DELETE receipt rows")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    image = os.getenv("ANOMALY_EFFECT_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-effects-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    worker_password = "worker-execution-fixture"
    runtime_password = "worker-runtime-fixture"
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
        docker_sql(docker, container, FIXTURE_ROOT.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_CONTEXT.read_text(encoding="utf-8"))
        docker_sql(docker, container, FIXTURE_ANOMALY.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION_LINEAGE.read_text(encoding="utf-8"))
        migration_sql = MIGRATION_EFFECTS.read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 407 applies and replays cleanly after migrations 405 and 406")
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
                '{RESOURCE}', '{ACTION}', 'disposable fixture'
            );
            """,
        )

        mapped = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not mapped:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(mapped[0].rsplit(":", 1)[1])
        worker = connect(port, "kokonut_worker_login", worker_password)
        runtime = connect(port, "kokonut_runtime", runtime_password)
        operator_auth = connect(port, "kokonut_operator_auth", "worker-auth-fixture")
        admin = connect(port, "postgres", admin_password)
        try:
            check_signed_scope_and_replay(worker, checks)
            check_outcome_transitions(worker, checks)
            check_reservation_denials(worker, checks)
            check_outcome_denials(worker, checks)
            check_privileges(admin, runtime, operator_auth, worker, checks)
            for connection in (worker, runtime, operator_auth, admin):
                connection.close()
        finally:
            for connection in (worker, runtime, operator_auth, admin):
                if not connection.closed:
                    connection.close()

        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 407 bounded anomaly-effect reservation and outcome functions",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [
                MIGRATION_CONTEXT.relative_to(ROOT).as_posix(),
                MIGRATION_LINEAGE.relative_to(ROOT).as_posix(),
                MIGRATION_EFFECTS.relative_to(ROOT).as_posix(),
            ],
            "migration_407_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
            "migration_replay": "passed",
            "command": "python3 scripts/check-sensor-anomaly-effect-functions-disposable.py",
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
