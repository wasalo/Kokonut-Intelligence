#!/usr/bin/env python3
"""Verify migration 527 on an isolated PostgreSQL 16 container."""

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
MIGRATION = ROOT / "schemas/postgres/527_location_consistent_crop_cycle_noi_inputs.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-21-recovery/cap-066-crop-noi-view-disposable.json"
IMAGE = os.environ.get("CROP_NOI_VIEW_TEST_IMAGE", "postgres:16")


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

    container = f"kokonut-crop-noi-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    created = False
    connection = None
    assertions = 0
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
                IMAGE,
            ]
        )
        created = True
        wait_ready(docker, container)
        mapping = json.loads(
            run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container])
        )
        port = int(mapping["5432/tcp"][0]["HostPort"])
        connection = psycopg2.connect(
            host="127.0.0.1",
            port=port,
            dbname="postgres",
            user="postgres",
            password=password,
            connect_timeout=5,
        )
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE crop_cycle (
                    id text PRIMARY KEY, location_id text NOT NULL, crop_id text NOT NULL,
                    plot_id text NOT NULL, cycle_name text, status text,
                    planting_date date, expected_harvest_date date, actual_harvest_date date,
                    expected_yield numeric, actual_yield numeric, expected_revenue numeric
                );
                CREATE TABLE crop (id text PRIMARY KEY, name text NOT NULL);
                CREATE TABLE plot (id text PRIMARY KEY, name text NOT NULL);
                CREATE TABLE sales_event (
                    crop_cycle_id text, location_id text, status text, total_amount numeric,
                    return_amount numeric, discount_amount numeric
                );
                CREATE TABLE expense_event (
                    id text PRIMARY KEY, location_id text NOT NULL,
                    crop_cycle_id text, status text, amount numeric
                );
                CREATE TABLE crop_cost_allocation (
                    crop_cycle_id text NOT NULL, expense_id text NOT NULL,
                    allocated_amount numeric NOT NULL
                );
                CREATE TABLE harvest_event (
                    crop_cycle_id text, location_id text, status text,
                    quantity numeric, loss_amount numeric
                );
                """
            )
            cursor.execute(MIGRATION.read_text())
            cursor.execute(
                """
                INSERT INTO crop VALUES ('crop-a', 'Plantain'), ('crop-b', 'Coffee');
                INSERT INTO plot VALUES ('plot-a', 'North'), ('plot-b', 'South');
                INSERT INTO crop_cycle VALUES
                    ('cycle-a', 'location-a', 'crop-a', 'plot-a', 'A', 'completed',
                     '2026-01-01', '2026-06-30', '2026-06-01', 100, 90, 1400),
                    ('cycle-b', 'location-b', 'crop-b', 'plot-b', 'B', 'completed',
                     '2026-01-01', '2026-06-30', '2026-06-01', 80, 70, 600);
                INSERT INTO sales_event VALUES
                    ('cycle-a', 'location-a', 'verified', 1000, 100, 50),
                    ('cycle-a', 'location-a', 'draft', 900, 0, 0),
                    ('cycle-a', 'location-b', 'verified', 700, 0, 0),
                    ('cycle-b', 'location-b', 'published', 500, 0, 0);
                INSERT INTO expense_event VALUES
                    ('direct-a', 'location-a', 'cycle-a', 'verified', 100),
                    ('cross-direct', 'location-b', 'cycle-a', 'verified', 300),
                    ('draft-a', 'location-a', NULL, 'draft', 1000),
                    ('rejected-a', 'location-a', NULL, 'rejected', 500),
                    ('shared-a', 'location-a', NULL, 'published', 40),
                    ('shared-b', 'location-a', NULL, 'draft', 90),
                    ('cross-location', 'location-b', NULL, 'verified', 700),
                    ('shared-c', 'location-b', NULL, 'verified', 20);
                INSERT INTO crop_cost_allocation VALUES
                    ('cycle-a', 'shared-a', 40),
                    ('cycle-a', 'shared-b', 90),
                    ('cycle-a', 'rejected-a', 500),
                    ('cycle-a', 'cross-location', 700),
                    ('cycle-b', 'shared-c', 20);
                INSERT INTO harvest_event VALUES
                    ('cycle-a', 'location-a', 'verified', 90, 5),
                    ('cycle-a', 'location-a', 'draft', 500, 200),
                    ('cycle-a', 'location-b', 'verified', 1000, 900);
                """
            )

            cursor.execute(
                """
                SELECT crop_cycle_id, gross_revenue, returns_discounts, net_revenue,
                       direct_crop_costs, allocated_shared_costs, total_costs, noi,
                       operating_margin_pct, loss_rate_pct
                FROM v_crop_cycle_noi ORDER BY crop_cycle_id
                """
            )
            rows = cursor.fetchall()
            expected = [
                ("cycle-a", 1000, 150, 850, 100, 40, 140, 710, 83.52941176470588, 5.555555555555555),
                ("cycle-b", 500, 0, 500, 0, 20, 20, 480, 96, 0),
            ]
            if len(rows) != len(expected):
                raise AssertionError(f"expected two location-isolated NOI rows, got {len(rows)}")
            for actual, wanted in zip(rows, expected, strict=True):
                if actual[0:8] != wanted[0:8]:
                    raise AssertionError(f"unexpected lifecycle/scope NOI values: {actual}")
                if abs(float(actual[8]) - wanted[8]) > 1e-9 or abs(float(actual[9]) - wanted[9]) > 1e-9:
                    raise AssertionError(f"unexpected NOI ratios: {actual}")
                assertions += 1

            # CREATE OR REPLACE can safely be applied again during a migration replay.
            cursor.execute(MIGRATION.read_text())
            cursor.execute(
                "SELECT allocated_shared_costs, noi FROM v_crop_cycle_noi WHERE crop_cycle_id = 'cycle-a'"
            )
            if cursor.fetchone() != (40, 710):
                raise AssertionError("migration replay changed the accepted shared-cost result")
            assertions += 1

        evidence = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "migration": MIGRATION.name,
            "postgres_image": IMAGE,
            "disposable_database_only": True,
            "assertion_groups_passed": assertions,
            "checks": [
                "verified and published same-location sales, expenses, shared allocations, and harvest contribute",
                "draft and rejected sources do not contribute",
                "sales, expenses, shared allocations, and harvest linked to another location do not contribute",
                "existing NOI view output shape and ratio calculations remain intact",
                "migration replay preserves the corrected result",
            ],
            "candidate_or_legacy_database_touched": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - keep output class-only for disposable checks
        print(f"crop-cycle NOI disposable check failed ({type(exc).__name__})", file=sys.stderr)
        raise
