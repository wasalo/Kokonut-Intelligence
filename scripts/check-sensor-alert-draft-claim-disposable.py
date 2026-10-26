#!/usr/bin/env python3
"""Exercise migration 411 draft claims in disposable PostgreSQL 16."""

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
MIGRATIONS = (
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/406_sensor_anomaly_location_lineage.sql",
    ROOT / "schemas/postgres/407_sensor_anomaly_effect_functions.sql",
    ROOT / "schemas/postgres/408_sensor_alert_event_function.sql",
    ROOT / "schemas/postgres/409_sensor_alert_notification_intent.sql",
    ROOT / "schemas/postgres/410_sensor_alert_actuation_intent.sql",
    ROOT / "schemas/postgres/411_sensor_alert_draft_claim_intent.sql",
)
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/"
    "sensor-alert-draft-claim-disposable.json"
)

WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
SENSOR_ID = "a0000000-0000-0000-0000-000000000011"
READING_ID = "a0000000-0000-0000-0000-000000000021"
SOURCE_EVENT_ID = "a0000000-0000-0000-0000-000000000031"
MISMATCH_EVENT_ID = "a0000000-0000-0000-0000-000000000032"
ALERT_ID = "a0000000-0000-0000-0000-000000000045"
RULE_ID = "a0000000-0000-0000-0000-000000000055"
ALERT_EVENT_ID = "a0000000-0000-0000-0000-000000000061"
LEGACY_ALERT_ID = "a0000000-0000-0000-0000-000000000043"
LEGACY_RULE_ID = "a0000000-0000-0000-0000-000000000051"
LEGACY_CLAIM_ID = "a0000000-0000-0000-0000-000000000099"
NO_AUTO_ALERT_ID = "a0000000-0000-0000-0000-000000000044"
NO_AUTO_RULE_ID = "a0000000-0000-0000-0000-000000000054"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
FUNCTION_NAME = "kokonut_security.create_sensor_alert_draft_claim"
FUNCTION_SIGNATURE = FUNCTION_NAME + "(uuid,uuid,uuid,uuid,uuid)"
CLAIM_SQL = f"SELECT {FUNCTION_NAME}(%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid)"
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


def claim(connection, *, source_event=SOURCE_EVENT_ID, reading=READING_ID,
          rule=RULE_ID, alert=ALERT_ID, location=LOCATION_ID):
    with connection.cursor() as cursor:
        cursor.execute(CLAIM_SQL, (source_event, reading, rule, alert, location))
        return str(cursor.fetchone()[0])


def expect_sqlstate(connection, params: tuple, expected: str, label: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(CLAIM_SQL, params)
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
    raise AssertionError(f"{label}: direct table access unexpectedly succeeded")


def prepare_alert_effect(connection, *, rule_id: str, alert_id: str) -> None:
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
    connection.commit()


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    image = os.getenv("ANOMALY_CLAIM_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-claim-{os.getpid()}-{secrets.token_hex(3)}"
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
        migration_sql = MIGRATIONS[6].read_text(encoding="utf-8")
        docker_sql(docker, container, migration_sql)
        docker_sql(docker, container, migration_sql)
        checks.append("migration 411 applies and replays after migrations 405 through 410")

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
            INSERT INTO public.alert_rule (
                id, enabled, name, severity, sensor_type_id,
                auto_create_claim, claim_type
            ) VALUES (
                '{RULE_ID}', TRUE, 'Synthetic draft claim rule', 'critical',
                'a0000000-0000-0000-0000-000000000071', TRUE, 'sensor_anomaly'
            );
            INSERT INTO public.sensor_alert (
                id, sensor_device_id, alert_rule_id, reading_id, severity,
                status, message, reading_value, threshold_value, location_id
            ) VALUES (
                '{ALERT_ID}', '{SENSOR_ID}', '{RULE_ID}', '{READING_ID}',
                'critical', 'open', 'Synthetic critical draft claim',
                46.25, 42.0, '{LOCATION_ID}'
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
                    CLAIM_SQL,
                    (SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
                )
            worker.rollback()
            raise AssertionError("draft claim succeeded without signed context")
        except psycopg2.Error as exc:
            worker.rollback()
            if exc.pgcode != "42501":
                raise AssertionError(
                    f"missing signed context: expected 42501, received {exc.pgcode}"
                ) from exc
        checks.append("draft claim creation rejects calls without signed worker context")

        for rule_id, alert_id in (
            (RULE_ID, ALERT_ID),
            (LEGACY_RULE_ID, LEGACY_ALERT_ID),
            (NO_AUTO_RULE_ID, NO_AUTO_ALERT_ID),
        ):
            prepare_alert_effect(worker, rule_id=rule_id, alert_id=alert_id)
        checks.append("only matching source-reading receipts can authorize claim creation")

        set_context(worker)
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.platform_event "
                "WHERE event_type = 'sensor_alert' AND source_id = %s::uuid",
                (ALERT_ID,),
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("alert event unexpectedly existed before draft claim")
        admin.commit()

        claim_id = claim(worker)
        worker.commit()
        set_context(worker)
        if claim(worker) != claim_id:
            raise AssertionError("claim retry did not return the original ID")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT claim_type, claim_date::text, claim_data, status, "
                "sensor_device_id::text, sensor_alert_id::text, "
                "source_readings::text, source_record_ids::text, "
                "source_sensor_reading_event_id::text "
                "FROM public.mrv_claim WHERE id = %s::uuid",
                (claim_id,),
            )
            claim_row = cursor.fetchone()
            expected_data = {
                "sensor_device_id": SENSOR_ID,
                "alert_id": ALERT_ID,
                "reading_value": 46.25,
                "threshold_value": 42.0,
                "severity": "critical",
            }
            expected_array = "{" + READING_ID + "}"
            if claim_row != (
                "sensor_anomaly", "2026-10-16", expected_data, "draft",
                SENSOR_ID, ALERT_ID, expected_array, expected_array, SOURCE_EVENT_ID,
            ):
                raise AssertionError(f"claim data or lifecycle differs from contract: {claim_row}")
            cursor.execute(
                "SELECT claim_id::text FROM public.sensor_alert WHERE id = %s::uuid",
                (ALERT_ID,),
            )
            if cursor.fetchone()[0] != claim_id:
                raise AssertionError("sensor alert was not linked to the new draft claim")
            cursor.execute(
                "SELECT count(*) FROM public.mrv_claim "
                "WHERE source_sensor_reading_event_id = %s::uuid AND sensor_alert_id = %s::uuid",
                (SOURCE_EVENT_ID, ALERT_ID),
            )
            if cursor.fetchone()[0] != 1:
                raise AssertionError("source event and alert created more than one claim")
        admin.commit()
        checks.append("rule-driven claim is source-linked, idempotent, and remains draft")

        # Event publication is a separate bounded effect. The publisher's
        # canonical payload omits claim_id, while later notification payloads
        # can read it from the linked alert row.
        set_context(worker)
        with worker.cursor() as cursor:
            cursor.execute(
                PUBLISH_SQL,
                (ALERT_EVENT_ID, SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
            )
            if cursor.fetchone()[0] is not True:
                raise AssertionError("sensor-alert event did not publish after claim creation")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT payload ->> 'alert_id', payload ->> 'location_id' "
                "FROM public.platform_event WHERE id = %s::uuid",
                (ALERT_EVENT_ID,),
            )
            if cursor.fetchone() != (ALERT_ID, LOCATION_ID):
                raise AssertionError("alert event lost canonical alert or location data")
        admin.commit()
        checks.append("alert event publishes canonical alert data independently of claim identity")

        # Human review occurs between attempts. The idempotent operation must not
        # move the lifecycle backward or clear review/attestation data.
        with admin.cursor() as cursor:
            cursor.execute(
                "UPDATE public.mrv_claim SET status = 'verified', reviewer_id = %s::uuid, "
                "review_notes = 'Reviewed after creation', reviewed_at = NOW(), "
                "attestation_uid = %s, attested_at = NOW() WHERE id = %s::uuid",
                (WORKER_ID, "0x" + "b" * 64, claim_id),
            )
        admin.commit()
        set_context(worker)
        if claim(worker) != claim_id:
            raise AssertionError("retry after human review changed the claim ID")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT status, reviewer_id::text, review_notes, "
                "reviewed_at IS NOT NULL, attestation_uid, attested_at IS NOT NULL "
                "FROM public.mrv_claim WHERE id = %s::uuid",
                (claim_id,),
            )
            if cursor.fetchone() != (
                "verified", WORKER_ID, "Reviewed after creation", True,
                "0x" + "b" * 64, True,
            ):
                raise AssertionError("claim retry changed human review or attestation state")
        admin.commit()
        checks.append("claim retries preserve verified, review, and attestation state")

        # Adopt the old handler's exact claim without resetting its reviewed state.
        set_context(worker)
        if claim(
            worker, rule=LEGACY_RULE_ID, alert=LEGACY_ALERT_ID,
        ) != LEGACY_CLAIM_ID:
            raise AssertionError("legacy-linked claim was not adopted")
        worker.commit()
        set_context(worker)
        if claim(
            worker, rule=LEGACY_RULE_ID, alert=LEGACY_ALERT_ID,
        ) != LEGACY_CLAIM_ID:
            raise AssertionError("legacy claim retry returned a different ID")
        worker.commit()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT status, reviewer_id::text, review_notes, "
                "reviewed_at IS NOT NULL, attestation_uid, attested_at IS NOT NULL, "
                "source_sensor_reading_event_id::text, source_readings::text "
                "FROM public.mrv_claim WHERE id = %s::uuid",
                (LEGACY_CLAIM_ID,),
            )
            legacy = cursor.fetchone()
            if legacy[:3] != (
                "verified", WORKER_ID, "Reviewed before bounded worker rollout",
            ) or legacy[4:6] != (
                "0x" + "a" * 64, True,
            ) or legacy[6:] != (SOURCE_EVENT_ID, None):
                raise AssertionError(f"legacy adoption changed review state or lost lineage: {legacy}")
            cursor.execute(
                "SELECT claim_id::text FROM public.sensor_alert WHERE id = %s::uuid",
                (LEGACY_ALERT_ID,),
            )
            if cursor.fetchone()[0] != LEGACY_CLAIM_ID:
                raise AssertionError("legacy sensor alert claim link changed")
        admin.commit()
        checks.append("exact legacy-linked claim receives source identity without lifecycle mutation")

        for params, label in (
            ((MISMATCH_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID), "mismatched source selector"),
            (("a0000000-0000-0000-0000-000000000035", READING_ID, RULE_ID, ALERT_ID, LOCATION_ID), "wrong source event type"),
            ((SOURCE_EVENT_ID, READING_ID, RULE_ID, ALERT_ID, OTHER_LOCATION_ID), "out-of-scope location"),
            ((SOURCE_EVENT_ID, READING_ID, LEGACY_RULE_ID, ALERT_ID, LOCATION_ID), "mismatched rule/alert linkage"),
            ((SOURCE_EVENT_ID, READING_ID, RULE_ID, LEGACY_ALERT_ID, LOCATION_ID), "mismatched alert/receipt linkage"),
        ):
            set_context(worker)
            expect_sqlstate(worker, params, "42501", label)
        checks.append("mismatched event selectors, rule, alert, and location fail closed")

        set_context(worker)
        expect_sqlstate(
            worker, (None, READING_ID, RULE_ID, ALERT_ID, LOCATION_ID),
            "22023", "missing source event identity",
        )
        checks.append("missing source identity is rejected")

        set_context(worker)
        expect_sqlstate(
            worker,
            (SOURCE_EVENT_ID, READING_ID, NO_AUTO_RULE_ID, NO_AUTO_ALERT_ID, LOCATION_ID),
            "42501", "rule without automatic claim creation",
        )
        checks.append("rules without auto_create_claim cannot create claims")

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT has_any_column_privilege('kokonut_worker_execution', "
                "'public.mrv_claim', 'SELECT'), "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.mrv_claim', 'INSERT'), "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.mrv_claim', 'UPDATE'), "
                "has_table_privilege('kokonut_worker_execution', 'public.mrv_claim', 'DELETE'), "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.sensor_alert', 'SELECT'), "
                "has_any_column_privilege('kokonut_worker_execution', "
                "'public.sensor_alert', 'UPDATE'), "
                "has_function_privilege('kokonut_worker_execution', %s, 'EXECUTE'), "
                "has_function_privilege('kokonut_anomaly_claim_owner', %s, 'EXECUTE')",
                (FUNCTION_SIGNATURE, FUNCTION_SIGNATURE),
            )
            if cursor.fetchone() != (False, False, False, False, False, False, True, True):
                raise AssertionError("worker claim privileges exceed bounded EXECUTE")
            cursor.execute(
                "SELECT has_column_privilege('kokonut_anomaly_claim_owner', "
                "'public.mrv_claim', 'location_id', 'INSERT'), "
                "has_column_privilege('kokonut_anomaly_claim_owner', "
                "'public.mrv_claim', 'status', 'INSERT'), "
                "has_column_privilege('kokonut_anomaly_claim_owner', "
                "'public.mrv_claim', 'status', 'UPDATE'), "
                "has_column_privilege('kokonut_anomaly_claim_owner', "
                "'public.mrv_claim', 'reviewer_id', 'UPDATE'), "
                "has_table_privilege('kokonut_anomaly_claim_owner', "
                "'public.mrv_claim', 'DELETE'), "
                "has_column_privilege('kokonut_anomaly_claim_owner', "
                "'public.sensor_alert', 'claim_id', 'UPDATE'), "
                "has_column_privilege('kokonut_anomaly_claim_owner', "
                "'public.sensor_alert', 'status', 'UPDATE')"
            )
            if cursor.fetchone() != (True, True, False, False, False, True, False):
                raise AssertionError("claim function owner has excessive direct table privileges")
            cursor.execute(
                "SELECT role.rolcanlogin, role.rolinherit, role.rolsuper, "
                "role.rolcreatedb, role.rolcreaterole, role.rolreplication, "
                "role.rolbypassrls, EXISTS (SELECT 1 FROM pg_auth_members "
                "WHERE roleid = role.oid OR member = role.oid) "
                "FROM pg_roles AS role "
                "WHERE role.rolname = 'kokonut_anomaly_claim_owner'"
            )
            if cursor.fetchone() != (False, False, False, False, False, False, False, False):
                raise AssertionError("claim owner role has unsafe attributes or memberships")
        admin.commit()
        checks.append("worker and function-owner ACLs limit claims to the approved columns/function")

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
                    raise AssertionError(f"{role_name} can execute draft-claim function")
        checks.append("runtime and operator-auth roles cannot execute draft-claim function")

        for statement, label in (
            ("SELECT id FROM public.mrv_claim", "direct claim SELECT"),
            (
                "INSERT INTO public.mrv_claim "
                "(location_id, claim_type, claim_date, claim_data, status) "
                f"VALUES ('{LOCATION_ID}', 'sensor_anomaly', DATE '2026-10-16', '{{}}', 'draft')",
                "direct claim INSERT",
            ),
            ("UPDATE public.mrv_claim SET status = 'rejected' WHERE FALSE", "direct claim UPDATE"),
            ("DELETE FROM public.mrv_claim WHERE FALSE", "direct claim DELETE"),
            ("SELECT id FROM public.sensor_alert", "direct sensor-alert SELECT"),
            ("UPDATE public.sensor_alert SET claim_id = NULL WHERE FALSE", "direct sensor-alert UPDATE"),
        ):
            direct_denial(worker, statement, label)
        checks.append("worker cannot directly read or mutate MRV claims or sensor alerts")

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT source_sensor_reading_event_id IS NULL, status, "
                "review_notes, attestation_uid FROM public.mrv_claim WHERE id = %s::uuid",
                (LEGACY_CLAIM_ID,),
            )
            if cursor.fetchone() != (
                False, "verified", "Reviewed before bounded worker rollout", "0x" + "a" * 64,
            ):
                raise AssertionError("legacy claim was lost or lifecycle/review state changed")
        admin.commit()
        checks.append("legacy claim data remains intact after adoption")

        for connection in connections:
            connection.close()
        evidence = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 411 bounded sensor-alert draft claim",
            "database": "isolated disposable PostgreSQL 16 container",
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in MIGRATIONS],
            "migration_411_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
            "migration_replay": "passed",
            "command": "python3 scripts/check-sensor-alert-draft-claim-disposable.py",
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
