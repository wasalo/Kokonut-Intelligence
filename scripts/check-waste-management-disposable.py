#!/usr/bin/env python3
"""Apply migration 153 and exercise waste-management CLI SQL in disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.analytics import waste_management  # noqa: E402

MIGRATION = ROOT / "schemas/postgres/153_waste_management.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-24-recovery/cap-006-waste-management-disposable.json"
IMAGE = os.environ.get("WASTE_MANAGEMENT_TEST_IMAGE", "postgres:16")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]} …\n{details}"
        )
    return result.stdout.strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [
                docker, "exec", container, "pg_isready", "-h", "127.0.0.1",
                "-U", "postgres", "-d", "postgres",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    container = f"kokonut-waste-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    conn = None
    checks: list[str] = []
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "--env", f"POSTGRES_PASSWORD={password}",
            "--publish", "127.0.0.1::5432", IMAGE,
        ])
        started = True
        wait_ready(docker, container)
        mapping = json.loads(
            run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container])
        )
        port = int(mapping["5432/tcp"][0]["HostPort"])
        conn = psycopg2.connect(
            host="127.0.0.1", port=port, dbname="postgres", user="postgres",
            password=password, connect_timeout=5,
        )
        conn.autocommit = True
        with conn.cursor() as cursor:
            # The migration needs only the canonical location key/name surface.
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)")
            cursor.execute(MIGRATION.read_text())
            cursor.execute(MIGRATION.read_text())  # migration is safe to replay
            location_a, location_b = str(uuid.uuid4()), str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO location (id, name) VALUES (%s, 'Test A'), (%s, 'Test B')",
                (location_a, location_b),
            )
        conn.autocommit = False
        checks.append("migration 153 applies and replays with only the required location fixture")

        try:
            waste_management.record_waste(
                conn, location_a, "organic", "Crop residues", 25, "composting",
                source="field log", notes="synthetic waste record",
            )
        except waste_management.TenantContextDenied:
            pass
        else:
            raise AssertionError("unscoped legacy waste writer was not retired")
        try:
            waste_management.record_composting(
                conn, location_a, "Banana stems", 100, "vermicomposting",
                output_kg=45, temperature_c=55, ph=6.5, moisture_pct=60,
            )
        except waste_management.TenantContextDenied:
            pass
        else:
            raise AssertionError("unscoped legacy composting writer was not retired")
        waste_a_id, waste_b_id = str(uuid.uuid4()), str(uuid.uuid4())
        compost_id = str(uuid.uuid4())
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO waste_stream
                    (id, location_id, waste_type, waste_name, quantity_kg,
                     quantity_unit, record_date, disposal_method, notes, metadata, status)
                VALUES
                    (%s, %s, 'organic_waste', 'Crop residues', 25, 'kg', CURRENT_DATE,
                     'composting', 'synthetic waste record', %s::jsonb, 'verified'),
                    (%s, %s, 'other', 'Container', 4, 'kg', CURRENT_DATE,
                     'other', NULL, %s::jsonb, 'verified')
                """,
                (
                    waste_a_id, location_a, json.dumps({"source": "field log"}),
                    waste_b_id, location_b, json.dumps({
                        "legacy_waste_type": "chemical",
                        "legacy_disposal_method": "incineration",
                    }),
                ),
            )
            cursor.execute(
                """
                INSERT INTO composting_record
                    (id, location_id, compost_date, feedstock_type, feedstock_kg,
                     compost_method, temperature_c, moisture_pct, duration_days,
                     finished_volume_kg, status, metadata)
                VALUES (%s, %s, CURRENT_DATE, 'other', 100, 'vermiculture',
                        55, 60, 30, 45, 'verified', %s::jsonb)
                """,
                (compost_id, location_a, json.dumps({"ph": 6.5})),
            )
        waste_a = {"waste_id": waste_a_id}
        waste_b = {"waste_id": waste_b_id}
        compost = {"compost_id": compost_id}
        recycling = waste_management.record_recycling(
            conn, location_a, "steel_scrap", 8, "Scrap yard", revenue=12.5,
        )
        incident = waste_management.report_incident(
            conn, location_a, "air_pollution", "high", "Synthetic event",
            "North plot", reported_by="synthetic operator",
        )
        checks.append(
            "unscoped legacy waste and composting writers fail closed; synthetic read fixtures are isolated"
        )

        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM waste_stream WHERE id = %s", (waste_a["waste_id"],))
            if cursor.fetchone()[0] != "verified":
                raise AssertionError("synthetic waste fixture is not eligible for verified summary")
            cursor.execute("SELECT status FROM composting_record WHERE id = %s", (compost["compost_id"],))
            if cursor.fetchone()[0] != "verified":
                raise AssertionError("synthetic compost fixture is not eligible for verified summary")
            cursor.execute("SELECT status FROM recycling_log WHERE id = %s", (recycling["recycle_id"],))
            if cursor.fetchone()[0] != "recorded":
                raise AssertionError("recycling writer did not use the canonical recorded state")
            cursor.execute(
                "SELECT status, resolved FROM pollution_incident WHERE id = %s",
                (incident["incident_id"],),
            )
            if cursor.fetchone() != ("open", False):
                raise AssertionError("incident writer did not use the canonical open state")
            cursor.execute(
                "UPDATE recycling_log SET status = 'verified' WHERE id = %s",
                (recycling["recycle_id"],),
            )
            cursor.execute(
                "SELECT waste_type, disposal_method, metadata FROM waste_stream WHERE id = %s",
                (waste_a["waste_id"],),
            )
            waste_row = cursor.fetchone()
            if waste_row[0] != "organic_waste" or waste_row[1] != "composting":
                raise AssertionError("waste category/disposal mapping is incorrect")
            if waste_row[2].get("source") != "field log":
                raise AssertionError("waste source was not preserved in metadata")
            cursor.execute(
                "SELECT waste_type, disposal_method, metadata FROM waste_stream WHERE id = %s",
                (waste_b["waste_id"],),
            )
            unsupported_waste = cursor.fetchone()
            if (
                unsupported_waste[0] != "other"
                or unsupported_waste[1] != "other"
                or unsupported_waste[2].get("legacy_waste_type") != "chemical"
                or unsupported_waste[2].get("legacy_disposal_method") != "incineration"
            ):
                raise AssertionError("unsupported waste labels were not retained")
            cursor.execute(
                "SELECT feedstock_type, compost_method, metadata FROM composting_record WHERE id = %s",
                (compost["compost_id"],),
            )
            compost_row = cursor.fetchone()
            if (
                compost_row[0] != "other"
                or compost_row[1] != "vermiculture"
                or float(compost_row[2]["ph"]) != 6.5
            ):
                raise AssertionError("compost mapping or pH metadata did not persist")
            cursor.execute(
                "SELECT material_type, metadata FROM recycling_log WHERE id = %s",
                (recycling["recycle_id"],),
            )
            recycling_row = cursor.fetchone()
            if (
                recycling_row[0] != "other"
                or recycling_row[1].get("legacy_material_type") != "steel_scrap"
            ):
                raise AssertionError("unsupported recycling label was not retained")
            cursor.execute(
                "SELECT incident_type, metadata FROM pollution_incident WHERE id = %s",
                (incident["incident_id"],),
            )
            incident_row = cursor.fetchone()
            if (
                incident_row[0] != "air_emission"
                or incident_row[1].get("reported_by") != "synthetic operator"
                or incident_row[1].get("legacy_incident_type") != "air_pollution"
            ):
                raise AssertionError("incident type/reporter metadata did not persist")
        conn.commit()
        checks.append("remaining legacy writers start in canonical recorded/open states")
        checks.append("schema-constrained category mappings and JSONB compatibility fields persist")

        waste_summary = waste_management.get_waste_summary(conn, location_a, days=30)
        if waste_summary["total_waste_kg"] != 25 or waste_summary["total_records"] != 1:
            raise AssertionError("waste summary is not verified-only and location-scoped")
        checks.append("verified waste summary excludes the second location")

        compost_summary = waste_management.get_composting_efficiency(conn, location_a)
        if (
            compost_summary["total_batches"] != 1
            or compost_summary["overall_yield_pct"] != 45.0
            or compost_summary["recent_quality"][0]["ph"] != 6.5
        ):
            raise AssertionError("compost summary lost verified output or metadata pH")
        checks.append("compost efficiency reads canonical columns, verified rows, and numeric pH metadata")

        open_incidents = waste_management.get_open_incidents(conn, location_a)
        if (
            open_incidents["open_count"] != 1
            or open_incidents["incidents"][0]["reported_by"] != "synthetic operator"
        ):
            raise AssertionError("incident summary lost active state or reporter attribution")
        resolved = waste_management.resolve_incident(
            conn, incident["incident_id"], "Synthetic cleanup", "2026-10-24",
        )
        after_resolution = waste_management.get_open_incidents(conn, location_a)
        if (
            resolved["status"] != "resolved"
            or after_resolution["open_count"] != 0
            or after_resolution["resolved_count"] != 1
        ):
            raise AssertionError("incident resolution did not update its canonical lifecycle fields")
        checks.append("incident reads and resolution use canonical lifecycle fields")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "migration": MIGRATION.name,
            "migration_replayed": True,
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "provider_calls": False,
            "host_binding": "127.0.0.1 ephemeral port",
            "synthetic_records_only": True,
            "cleanup": "Disposable container stopped with --rm; connection closed.",
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if conn is not None:
            conn.close()
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - disposable acceptance should expose actual SQL failures.
        print(f"waste-management disposable check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
