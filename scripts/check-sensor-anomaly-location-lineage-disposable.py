#!/usr/bin/env python3
"""Replay sensor-anomaly location lineage migration on disposable PostgreSQL."""

from __future__ import annotations

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
FIXTURE = ROOT / "tests/fixtures/sensor_anomaly_location_lineage_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/406_sensor_anomaly_location_lineage.sql"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-16-recovery/sensor-anomaly-location-lineage.json"
)


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
            f"{value.split('=', 1)[0]}=<redacted>"
            if value.startswith(("POSTGRES_PASSWORD=", "PGPASSWORD="))
            else value
            for value in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
    return result.stdout


def docker_sql(docker: str, container: str, password: str, statement: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            "--env",
            f"PGPASSWORD={password}",
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
    stable_ready = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode == 0:
            stable_ready += 1
            if stable_ready >= 4:
                return
        else:
            stable_ready = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def check_application_writes(docker: str, container: str, password: str) -> None:
    published = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
    if not published:
        raise RuntimeError("disposable PostgreSQL has no host-side test mapping")
    port = int(published[0].rsplit(":", 1)[1])
    connection = psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user="postgres",
        password=password,
        connect_timeout=5,
    )
    try:
        sys.path.insert(0, str(ROOT))
        import services.common.env as environment_loader

        # This acceptance uses an explicit disposable connection and does not
        # need application secrets. Keep module imports from decrypting .env.sops.
        environment_loader._LOADED = True
        from services.events import notification_outbox
        from services.ingestion.anomaly_detector import create_alert
        from services.ingestion.base import log_ingestion

        location_id = "a0000000-0000-0000-0000-000000000001"
        device_id = "a0000000-0000-0000-0000-000000000011"
        reading_id = "a0000000-0000-0000-0000-000000000021"
        alert_id = create_alert(
            connection,
            device_id,
            "a0000000-0000-0000-0000-000000000051",
            reading_id,
            "warning",
            "Disposable location-lineage check",
            12.5,
            15.0,
            location_id=location_id,
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT location_id::text FROM public.sensor_alert WHERE id = %s", (alert_id,))
            if cursor.fetchone()[0] != location_id:
                raise AssertionError("application alert insert lost its location lineage")
        try:
            create_alert(
                connection,
                device_id,
                "a0000000-0000-0000-0000-000000000051",
                reading_id,
                "warning",
                "Wrong location must fail",
                12.5,
                15.0,
                location_id="a0000000-0000-0000-0000-000000000002",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("application alert insert accepted a mismatched device location")
        try:
            create_alert(
                connection,
                device_id,
                "a0000000-0000-0000-0000-000000000051",
                "a0000000-0000-0000-0000-000000000022",
                "warning",
                "Cross-location reading must fail",
                12.5,
                15.0,
                location_id=location_id,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("application alert insert accepted a cross-location reading")

        log_ingestion(
            source_system="anomaly_detector",
            source_table="sensor_reading",
            source_id=reading_id,
            target_table="sensor_alert",
            target_id=alert_id,
            operation="insert",
            payload_hash="a" * 64,
            db=connection,
            location_id=location_id,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT location_id::text FROM public.ingestion_log "
                "WHERE target_id = %s ORDER BY id DESC LIMIT 1",
                (alert_id,),
            )
            if cursor.fetchone()[0] != location_id:
                raise AssertionError("application ingestion audit insert lost its location lineage")

        notification_outbox._notification_payloads = lambda *_args, **_kwargs: [
            ("webhook", "disposable", {"subject": "Lineage check"})
        ]
        outbox_event_id = "a0000000-0000-0000-0000-000000000092"
        notification_outbox.enqueue_event_notification(
            connection,
            event_id=outbox_event_id,
            event_type="sensor_alert",
            payload={"message": "Disposable"},
            location_id=location_id,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT location_id::text FROM public.notification_outbox "
                "WHERE source_event_id = %s",
                (outbox_event_id,),
            )
            if cursor.fetchone()[0] != location_id:
                raise AssertionError("application notification enqueue lost its location lineage")
        connection.commit()
    finally:
        connection.close()


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    image = os.getenv("ANOMALY_LINEAGE_TEST_IMAGE", "postgres:16")
    container = f"kokonut-anomaly-lineage-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
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
                f"POSTGRES_PASSWORD={password}",
                "-p",
                "127.0.0.1::5432",
                image,
            ]
        )
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, password, FIXTURE.read_text(encoding="utf-8"))
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_sql(docker, container, password, migration_sql)
        docker_sql(docker, container, password, migration_sql)
        checks.append("migration 406 applies and replays idempotently on PostgreSQL 16")

        assertions = """
        DO $$
        DECLARE actual UUID;
        BEGIN
            SELECT location_id INTO actual FROM public.sensor_alert
             WHERE id = 'a0000000-0000-0000-0000-000000000041';
            IF actual IS DISTINCT FROM 'a0000000-0000-0000-0000-000000000001'::UUID THEN
                RAISE EXCEPTION 'matching alert did not inherit device location';
            END IF;
            IF (SELECT location_id FROM public.sensor_alert
                 WHERE id = 'a0000000-0000-0000-0000-000000000042') IS NOT NULL
               OR (SELECT location_id FROM public.sensor_alert
                    WHERE id = 'a0000000-0000-0000-0000-000000000043') IS NOT NULL
               OR (SELECT location_id FROM public.sensor_alert
                    WHERE id = 'a0000000-0000-0000-0000-000000000044') IS NOT NULL THEN
                RAISE EXCEPTION 'mismatched or missing alert lineage was assigned';
            END IF;

            IF (SELECT location_id FROM public.sensor_anomaly_effect
                 WHERE alert_rule_id = 'a0000000-0000-0000-0000-000000000051')
                 IS DISTINCT FROM 'a0000000-0000-0000-0000-000000000001'::UUID THEN
                RAISE EXCEPTION 'valid anomaly receipt lineage was not backfilled';
            END IF;
            IF (SELECT count(*) FROM public.sensor_anomaly_effect
                 WHERE alert_rule_id IN (
                     'a0000000-0000-0000-0000-000000000052',
                     'a0000000-0000-0000-0000-000000000053',
                     'a0000000-0000-0000-0000-000000000054'
                 ) AND location_id IS NOT NULL) <> 0 THEN
                RAISE EXCEPTION 'mismatched or conflicting event lineage was assigned';
            END IF;

            IF (SELECT location_id FROM public.ingestion_log
                 WHERE id = 'a0000000-0000-0000-0000-000000000061')
                 IS DISTINCT FROM 'a0000000-0000-0000-0000-000000000001'::UUID
               OR (SELECT location_id FROM public.ingestion_log
                    WHERE id = 'a0000000-0000-0000-0000-000000000062')
                 IS DISTINCT FROM 'a0000000-0000-0000-0000-000000000001'::UUID THEN
                RAISE EXCEPTION 'valid source or target audit lineage was not backfilled';
            END IF;
            IF (SELECT location_id FROM public.ingestion_log
                 WHERE id = 'a0000000-0000-0000-0000-000000000063') IS NOT NULL THEN
                RAISE EXCEPTION 'conflicting audit lineage was assigned';
            END IF;

            IF (SELECT location_id FROM public.notification_outbox
                 WHERE source_event_id = 'a0000000-0000-0000-0000-000000000034')
                 IS DISTINCT FROM 'a0000000-0000-0000-0000-000000000001'::UUID
               OR (SELECT location_id FROM public.notification_outbox
                    WHERE source_event_id = 'a0000000-0000-0000-0000-000000000035') IS NOT NULL THEN
                RAISE EXCEPTION 'notification event lineage was not safely resolved';
            END IF;
        END;
        $$;
        """
        docker_sql(docker, container, password, assertions)
        checks.extend(
            [
                "sensor alerts backfill only from matching device and reading; missing readings stay unresolved",
                "anomaly receipts require matching event/source/location and every supplied sensor selector",
                "ingestion audit rows use matching reading/alert lineage; conflicts remain NULL",
                "notification intents backfill only from a matching linked alert and event location",
            ]
        )

        fk_check = """
        DO $$
        BEGIN
            BEGIN
                INSERT INTO public.sensor_alert (
                    id, sensor_device_id, alert_rule_id, severity, message, location_id
                )
                VALUES (
                    'a0000000-0000-0000-0000-000000000091',
                    'a0000000-0000-0000-0000-000000000011',
                    'a0000000-0000-0000-0000-000000000051',
                    'warning',
                    'foreign key check',
                    'a0000000-0000-0000-0000-000000000099'
                );
                RAISE EXCEPTION 'location foreign key accepted an unknown location';
            EXCEPTION WHEN foreign_key_violation THEN
                NULL;
            END;
        END;
        $$;
        """
        docker_sql(docker, container, password, fk_check)
        checks.append("new direct location keys reject unknown locations")
        check_application_writes(docker, container, password)
        checks.append(
            "application alert binds device, reading, and location; audit/outbox helpers preserve location scope"
        )

        evidence = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "postgres_image": image,
            "migration": MIGRATION.relative_to(ROOT).as_posix(),
            "candidate_or_legacy_database_touched": False,
            "checks": checks,
            "result": "passed",
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
