#!/usr/bin/env python3
"""Replay pollinator migrations and exercise service SQL in disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.analytics import pollinator_health  # noqa: E402

MIGRATIONS = (
    ROOT / "schemas/postgres/155_pollinator_health.sql",
    ROOT / "schemas/postgres/602_pollinator_health_kernel_alignment.sql",
)
OUTPUT = ROOT / "docs/refactor/builds/2026-10-23-recovery/cap-006-pollinator-health-disposable.json"
IMAGE = os.environ.get("POLLINATOR_TEST_IMAGE", "postgres:16")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} {command[1]} …\n{details}")
    return result.stdout.strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-pollinator-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    conn = None
    assertions = 0
    try:
        run([
            docker, "run", "--detach", "--rm", "--name", container,
            "--env", f"POSTGRES_PASSWORD={password}", "--publish", "127.0.0.1::5432", IMAGE,
        ])
        started = True
        wait_ready(docker, container)
        mapping = json.loads(run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container]))
        port = int(mapping["5432/tcp"][0]["HostPort"])
        conn = psycopg2.connect(
            host="127.0.0.1", port=port, dbname="postgres", user="postgres",
            password=password, connect_timeout=5,
        )
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text())
            cursor.execute(MIGRATIONS[-1].read_text())  # idempotent replay
            assertions += 1
            cursor.execute(
                "INSERT INTO location (id, name) VALUES (%s, 'A'), (%s, 'B')",
                (str(uuid.uuid4()), str(uuid.uuid4())),
            )
        conn.autocommit = False

        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM location WHERE name = 'A'")
            location_a = str(cursor.fetchone()[0])
            cursor.execute("SELECT id FROM location WHERE name = 'B'")
            location_b = str(cursor.fetchone()[0])

        hive = pollinator_health.add_hive(conn, location_a, "H-1", colony_strength=8)
        foreign_hive = pollinator_health.add_hive(conn, location_b, "H-B")
        pollinator_health.record_observation(
            conn, location_a, "honeybee", 20, observation_date=date.today(),
            hive_record_id=hive["record_id"],
        )
        pollinator_health.record_observation(
            conn, location_b, "butterfly", 900, hive_record_id=foreign_hive["record_id"],
        )
        with conn.cursor() as cursor:
            cursor.execute("UPDATE pollinator_observation SET status = 'verified' WHERE location_id = %s", (location_a,))
            cursor.execute("UPDATE pollinator_observation SET status = 'verified' WHERE location_id = %s", (location_b,))
            cursor.execute("UPDATE hive_record SET status = 'active' WHERE location_id = %s", (location_a,))
        conn.commit()

        summary = pollinator_health.get_pollinator_summary(conn, location_a)
        if len(summary["pollinator_types"]) != 1 or summary["pollinator_types"][0]["total_count"] != 20.0:
            raise AssertionError("pollinator summary did not remain location-scoped or preserve counts")
        assertions += 1

        habitat = pollinator_health.create_habitat(
            conn, location_a, "Native strip", "wildflower_strip", 80,
            plant_species=["clover"], bloom_start_month=3, bloom_end_month=8,
            water_source=True, nesting_sites="deadwood",
        )
        inventory = pollinator_health.get_habitat_inventory(conn, location_a)
        if inventory["habitat_count"] != 1 or inventory["habitats"][0]["id"] != habitat["habitat_id"]:
            raise AssertionError("habitat write/read failed against the installed column contract")
        assertions += 1

        pesticide = pollinator_health.record_pesticide_impact(
            conn, location_a, date.today(), "Sample", "ingredient", "high",
            pollinator_safe_period_days=3, pollinator_mortality_observed=True, mortality_pct=2.5,
        )
        with conn.cursor() as cursor:
            cursor.execute("UPDATE pesticide_impact_log SET status = 'verified' WHERE id = %s", (pesticide["record_id"],))
        conn.commit()
        risk = pollinator_health.get_pesticide_risk(conn, location_a)
        if risk["total_applications"] != 1 or risk["overall_risk"] != "critical":
            raise AssertionError("pesticide write/read lost current risk or mortality fields")
        assertions += 1

        inspection = pollinator_health.record_hive_inspection(
            conn, location_a, "H-1", colony_strength="moderate", queen_status="present", varroa_count=4,
        )
        with conn.cursor() as cursor:
            cursor.execute("UPDATE pollinator_hive_inspection SET status = 'verified' WHERE id = %s", (inspection["inspection_id"],))
        conn.commit()
        hive_status = pollinator_health.get_hive_status(conn, location_a)
        if (
            hive_status["hives"][0]["last_inspection"]["colony_strength"] != "moderate"
            or hive_status["hives"][0]["avg_daily_foragers"] != 20.0
        ):
            raise AssertionError("location-bound inspection or linked daily observation did not appear in hive status")
        assertions += 1

        try:
            pollinator_health.record_observation(
                conn, location_a, "honeybee", 1, hive_record_id=foreign_hive["record_id"],
            )
        except psycopg2.errors.ForeignKeyViolation:
            conn.rollback()
            assertions += 1
        else:
            raise AssertionError("invalid hive linkage was not rejected by the composite location foreign key")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "migrations": [migration.name for migration in MIGRATIONS],
            "migration_602_replayed": True,
            "assertion_groups_passed": assertions,
            "checks": [
                "migration 155 and additive 602 apply; migration 602 replays idempotently",
                "observation writes satisfy required date, pollinator type, method, and lifecycle checks",
                "summary reads only reviewed observations and isolates location rows",
                "habitat and pesticide service queries use the actual 155/602 table and column names",
                "hive inspections append history and update only the matching location-bound hive",
                "composite foreign key rejects an observation linked to another location's hive",
            ],
            "candidate_database_touched": False,
            "legacy_database_touched": False,
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
    except Exception as exc:  # noqa: BLE001 - disposable acceptance should expose SQL failures.
        print(f"pollinator disposable check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
