#!/usr/bin/env python3
"""Check event-fanout analytics queries against isolated synthetic PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.analytics.economic_performance import compute_revenue_per_acre  # noqa: E402
from services.analytics.gap_closures import compute_weather_growth_correlation  # noqa: E402

IMAGE = os.environ.get("ANALYTICS_EVENT_TEST_IMAGE", "postgres:16")
EVIDENCE = (
    ROOT
    / "docs/refactor/builds/2026-10-29-recovery/analytics-event-aggregation-disposable.json"
)


def docker_run(args: list[str], *, check: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode:
        detail = result.stderr.strip() if args[1] == "network" else ""
        suffix = f": {detail[:500]}" if detail else ""
        raise RuntimeError(f"Docker command failed: {args[1]}{suffix}")
    return result.stdout.strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


class DisposablePsqlConnection:
    """Minimal DB-API surface that sends SQL to psql inside the container."""

    def __init__(self, docker: str, container: str):
        self.docker = docker
        self.container = container

    def cursor(self):
        return DisposablePsqlCursor(self)

    def execute(self, statement: str) -> str:
        result = subprocess.run(
            [
                self.docker,
                "exec",
                "-i",
                self.container,
                "psql",
                "--no-psqlrc",
                "--quiet",
                "--tuples-only",
                "--no-align",
                "--field-separator",
                "\t",
                "--set",
                "ON_ERROR_STOP=1",
                "--username",
                "postgres",
                "--dbname",
                "postgres",
            ],
            input=statement.rstrip() + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("disposable PostgreSQL rejected synthetic SQL")
        return result.stdout

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class DisposablePsqlCursor:
    def __init__(self, connection: DisposablePsqlConnection):
        self.connection = connection
        self.statement = ""
        self.params = ()

    def execute(self, statement: str, params=()):
        self.statement = statement
        self.params = tuple(params or ())

    def fetchall(self):
        statement = self.statement
        for parameter in self.params:
            location_id = str(uuid.UUID(str(parameter)))
            statement = statement.replace("%s", f"'{location_id}'::uuid", 1)
        if "%s" in statement:
            raise RuntimeError("analytics SQL has unbound parameters")
        output = self.connection.execute(statement)
        rows = [
            [None if value == "" else value for value in line.split("\t")]
            for line in output.splitlines()
            if line
        ]
        if "weather_observation" in self.statement:
            return [
                (*row[:8], int(row[8]), int(row[9]))
                for row in rows
            ]
        return rows

    def close(self):
        return None


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    suffix = f"{os.getpid()}-{secrets.token_hex(3)}"
    container = f"kokonut-analytics-event-{suffix}"
    network = f"kokonut-analytics-event-net-{suffix}"
    password = secrets.token_urlsafe(24)
    evidence: dict[str, object] = {
        "result": "failed",
        "database": "disposable PostgreSQL 16",
        "candidate_or_legacy_modified": False,
        "provider_contacted": False,
        "network_isolated": True,
        "host_port_published": False,
    }
    started = False
    network_created = False
    stage = "container_start"
    try:
        docker_run([docker, "network", "create", "--internal", network])
        network_created = True
        docker_run(
            [
                docker,
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                network,
                "--env",
                f"POSTGRES_PASSWORD={password}",
                IMAGE,
            ]
        )
        started = True
        wait_ready(docker, container)
        conn = DisposablePsqlConnection(docker, container)

        stage = "schema_and_fixture_setup"
        location_a = str(uuid.uuid4())
        location_b = str(uuid.uuid4())
        crop_id = str(uuid.uuid4())
        cycle_id = str(uuid.uuid4())
        empty_cycle_id = str(uuid.uuid4())
        conn.execute(
            """
            CREATE TABLE crop (id UUID PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE crop_cycle (
                id UUID PRIMARY KEY,
                location_id UUID NOT NULL,
                crop_id UUID NOT NULL,
                cycle_name TEXT,
                actual_harvest_date DATE,
                status TEXT NOT NULL,
                area_planted NUMERIC,
                area_unit TEXT
            );
            CREATE TABLE harvest_event (
                id UUID PRIMARY KEY,
                crop_cycle_id UUID NOT NULL,
                location_id UUID NOT NULL,
                harvest_date DATE NOT NULL,
                quantity NUMERIC NOT NULL,
                unit TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE weather_observation (
                id UUID PRIMARY KEY,
                location_id UUID NOT NULL,
                observation_date DATE NOT NULL,
                temperature_c NUMERIC,
                humidity_pct NUMERIC,
                rainfall_mm NUMERIC
            );
            CREATE TABLE revenue_event (
                crop_cycle_id UUID,
                location_id UUID NOT NULL,
                amount_usd NUMERIC,
                status TEXT NOT NULL
            );
            CREATE TABLE expense_event (
                crop_cycle_id UUID,
                location_id UUID NOT NULL,
                amount NUMERIC NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        conn.execute(
            f"INSERT INTO crop (id, name) VALUES ('{crop_id}'::uuid, 'Cassava')"
        )
        conn.execute(
            f"""
            INSERT INTO crop_cycle
                (id, location_id, crop_id, cycle_name, actual_harvest_date,
                 status, area_planted, area_unit)
            VALUES
                ('{cycle_id}'::uuid, '{location_a}'::uuid, '{crop_id}'::uuid,
                 'Target cycle', DATE '2026-01-25', 'harvested', 1, 'acres'),
                ('{empty_cycle_id}'::uuid, '{location_a}'::uuid, '{crop_id}'::uuid,
                 'No-event cycle', DATE '2026-02-01', 'completed', 2, 'acres')
            """
        )
        harvest_a, harvest_b, harvest_mismatch = (
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        )
        weather_ids = [str(uuid.uuid4()) for _ in range(3)]
        conn.execute(
            f"""
            INSERT INTO harvest_event
                (id, crop_cycle_id, location_id, harvest_date, quantity, unit, status)
            VALUES
                ('{harvest_a}'::uuid, '{cycle_id}'::uuid, '{location_a}'::uuid,
                 DATE '2026-01-20', 10, 'kg', 'verified'),
                ('{harvest_b}'::uuid, '{cycle_id}'::uuid, '{location_a}'::uuid,
                 DATE '2026-01-25', 5, 'kg', 'published'),
                ('{harvest_mismatch}'::uuid, '{cycle_id}'::uuid, '{location_b}'::uuid,
                 DATE '2026-01-25', 900, 'kg', 'verified')
            """
        )
        conn.execute(
            f"""
            INSERT INTO weather_observation
                (id, location_id, observation_date, temperature_c, humidity_pct, rainfall_mm)
            VALUES
                ('{weather_ids[0]}'::uuid, '{location_a}'::uuid, DATE '2026-01-10', 20, 50, 2),
                ('{weather_ids[1]}'::uuid, '{location_a}'::uuid, DATE '2026-01-18', 30, 70, 3),
                ('{weather_ids[2]}'::uuid, '{location_a}'::uuid, DATE '2026-01-22', 40, 90, 5)
            """
        )
        conn.execute(
            f"""
            INSERT INTO revenue_event (crop_cycle_id, location_id, amount_usd, status)
            VALUES
                ('{cycle_id}'::uuid, '{location_a}'::uuid, 100, 'verified'),
                ('{cycle_id}'::uuid, '{location_a}'::uuid, 200, 'published'),
                ('{cycle_id}'::uuid, '{location_b}'::uuid, 9000, 'verified')
            """
        )
        conn.execute(
            f"""
            INSERT INTO expense_event (crop_cycle_id, location_id, amount, status)
            VALUES
                ('{cycle_id}'::uuid, '{location_a}'::uuid, 10, 'verified'),
                ('{cycle_id}'::uuid, '{location_a}'::uuid, 20, 'published'),
                ('{cycle_id}'::uuid, '{location_a}'::uuid, 30, 'verified'),
                ('{cycle_id}'::uuid, '{location_b}'::uuid, 9000, 'verified')
            """
        )

        stage = "weather_growth_assertions"
        weather_result = compute_weather_growth_correlation(conn, location_a)
        assert weather_result["total_months"] == 1
        weather = weather_result["correlations"][0]
        assert weather["total_harvest_kg"] == 15.0, weather
        assert weather["harvest_event_count"] == 2, weather
        assert weather["weather_obs_count"] == 3, weather
        assert weather["total_rainfall_mm"] == 10.0, weather
        assert weather["avg_temperature_c"] == 30.0, weather
        assert weather["avg_humidity_pct"] == 70.0, weather
        assert weather_result["correlations"][0]["yield_per_temp_humidity_unit"] == 0.0071
        mismatch_result = compute_weather_growth_correlation(conn, location_b)
        assert mismatch_result["correlations"] == [], mismatch_result

        stage = "revenue_per_acre_assertions"
        revenue_result = compute_revenue_per_acre(conn, location_a)
        by_cycle = {row["cycle_id"]: row for row in revenue_result["cycles"]}
        target = by_cycle[cycle_id]
        empty = by_cycle[empty_cycle_id]
        assert target["total_revenue_usd"] == 300.0, target
        assert target["total_expenses_usd"] == 60.0, target
        assert target["roi_pct"] == 400.0, target
        assert empty["total_revenue_usd"] == 0.0, empty
        assert empty["total_expenses_usd"] == 0.0, empty
        assert revenue_result["total_revenue_usd"] == 300.0, revenue_result
        assert revenue_result["total_expenses_usd"] == 60.0, revenue_result

        evidence.update(
            {
                "result": "passed",
                "postgresql_version": "16",
                "fixtures": {
                    "harvest_events": 3,
                    "weather_observations": 3,
                    "revenue_events": 3,
                    "expense_events": 4,
                },
                "weather_growth": {
                    "harvest_kg": weather["total_harvest_kg"],
                    "harvest_event_count": weather["harvest_event_count"],
                    "unique_weather_observation_count": weather["weather_obs_count"],
                    "rainfall_mm": weather["total_rainfall_mm"],
                    "average_temperature_c": weather["avg_temperature_c"],
                    "average_humidity_pct": weather["avg_humidity_pct"],
                    "cross_location_cycle_rows": len(mismatch_result["correlations"]),
                },
                "revenue_per_acre": {
                    "revenue_usd": target["total_revenue_usd"],
                    "expenses_usd": target["total_expenses_usd"],
                    "roi_pct": target["roi_pct"],
                    "no_event_cycle_zero_totals": (
                        empty["total_revenue_usd"] == 0.0
                        and empty["total_expenses_usd"] == 0.0
                    ),
                    "cross_location_events_excluded": True,
                },
            }
        )
    except Exception as exc:
        evidence["failure_stage"] = stage
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_detail"] = str(exc)[:500]
        raise
    finally:
        cleanup_errors = []
        if started:
            result = subprocess.run(
                [docker, "rm", "--force", container],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                cleanup_errors.append("container removal failed")
        if network_created:
            result = subprocess.run(
                [docker, "network", "rm", network],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                cleanup_errors.append("network removal failed")
        evidence["cleanup"] = "failed" if cleanup_errors else "complete"
        if cleanup_errors:
            evidence["cleanup_errors"] = cleanup_errors
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
