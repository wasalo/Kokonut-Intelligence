#!/usr/bin/env python3
"""Check landscape migration 603 in disposable PostgreSQL 16."""

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
from psycopg2 import errors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATION_154 = ROOT / "schemas/postgres/154_landscape_conservation.sql"
MIGRATION_603 = ROOT / "schemas/postgres/603_location_bound_landscape_references.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-23-recovery/cap-006-landscape-reference-location-disposable.json"
IMAGE = os.environ.get("LANDSCAPE_REFERENCE_TEST_IMAGE", "postgres:16")

from services.analytics.landscape_reference_preflight import (  # noqa: E402
    get_location_reference_mismatch_counts,
)


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
    container = f"kokonut-landscape-reference-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    conn = None
    preflight_conn = None
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
            # The checker exercises 154's ordinary SQL/view contract without
            # needing spatial operators or a PostGIS image; this domain stands
            # in for the unused boundary column only.
            cursor.execute("CREATE DOMAIN geometry AS text")
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)")
            cursor.execute(MIGRATION_154.read_text())
            location_a, location_b = str(uuid.uuid4()), str(uuid.uuid4())
            habitat_a, habitat_b = str(uuid.uuid4()), str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO location (id, name) VALUES (%s, 'Farm A'), (%s, 'Farm B')",
                (location_a, location_b),
            )
            cursor.execute(
                """
                INSERT INTO habitat_zone (id, location_id, zone_name, habitat_type)
                VALUES (%s, %s, 'A habitat', 'riparian'), (%s, %s, 'B private habitat', 'wetland')
                """,
                (habitat_a, location_a, habitat_b, location_b),
            )
            # These rows model historic references that passed the old single-ID FKs.
            cursor.execute(
                """
                INSERT INTO wildlife_corridor
                    (location_id, corridor_name, source_habitat_id, condition)
                VALUES (%s, 'Legacy cross-farm corridor', %s, 'fair')
                """,
                (location_a, habitat_b),
            )
            cursor.execute(
                """
                INSERT INTO buffer_zone_monitoring
                    (location_id, habitat_zone_id, check_date, compliant)
                VALUES (%s, %s, CURRENT_DATE, TRUE)
                """,
                (location_a, habitat_b),
            )
            cursor.execute(MIGRATION_603.read_text())
            cursor.execute(MIGRATION_603.read_text())

            # Exercise the operator preflight on a dedicated read-only
            # transaction. Only fixed reference categories and counts escape.
            preflight_conn = psycopg2.connect(
                host="127.0.0.1", port=port, dbname="postgres", user="postgres",
                password=password, connect_timeout=5,
                application_name="kokonut-landscape-reference-preflight-test",
            )
            preflight = get_location_reference_mismatch_counts(preflight_conn)
            expected_counts = {
                "corridor_source": 1,
                "corridor_target": 0,
                "buffer_habitat": 1,
            }
            if preflight["location_reference_mismatch_counts"] != expected_counts:
                raise AssertionError("aggregate preflight did not count historical mismatches by reference type")
            if preflight["total_location_reference_mismatch_count"] != 2:
                raise AssertionError("aggregate preflight total did not match the synthetic archive")
            sanitized_preflight = json.dumps(preflight, sort_keys=True)
            for private_marker in (
                location_a, location_b, habitat_a, habitat_b,
                "Farm A", "Farm B", "private habitat",
            ):
                if private_marker in sanitized_preflight:
                    raise AssertionError("aggregate preflight exposed a location, habitat, or descriptive value")

            preflight_cli = ROOT / "scripts/landscape-reference-preflight.py"
            minimal_environment = {"PATH": os.environ.get("PATH", "")}
            missing_target = subprocess.run(
                [sys.executable, str(preflight_cli)],
                text=True,
                capture_output=True,
                env=minimal_environment,
                check=False,
            )
            if missing_target.returncode != 2 or json.loads(missing_target.stdout).get("result") != "blocked":
                raise AssertionError("preflight CLI did not fail closed without an explicit target")

            dsn = (
                f"host=127.0.0.1 port={port} dbname=postgres user=postgres "
                f"password={password} connect_timeout=5"
            )
            selected_environment = {
                **minimal_environment,
                "LANDSCAPE_REFERENCE_PREFLIGHT_DSN": dsn,
            }
            selected_target = subprocess.run(
                [sys.executable, str(preflight_cli)],
                text=True,
                capture_output=True,
                env=selected_environment,
                check=False,
            )
            if selected_target.returncode != 0:
                raise AssertionError("preflight CLI failed on the explicitly selected disposable target")
            cli_output = json.loads(selected_target.stdout)
            if cli_output != {"result": "completed", **preflight}:
                raise AssertionError("preflight CLI output did not match the sanitized aggregate contract")
            for private_marker in (
                dsn, password, location_a, location_b, habitat_a, habitat_b,
                "Farm A", "Farm B", "private habitat",
            ):
                if private_marker in selected_target.stdout:
                    raise AssertionError("preflight CLI output exposed credentials or fixture identifiers")
            assertions += 1
            try:
                with preflight_conn.cursor() as preflight_cursor:
                    preflight_cursor.execute(
                        "INSERT INTO wildlife_corridor (location_id, corridor_name) VALUES (%s, %s)",
                        (location_a, "preflight write probe"),
                    )
            except errors.ReadOnlySqlTransaction:
                assertions += 1
            else:
                preflight_conn.rollback()
                raise AssertionError("aggregate preflight transaction allowed a write")
            preflight_conn.rollback()

            cursor.execute(
                "SELECT source_habitat FROM v_corridor_status WHERE location_id = %s",
                (location_a,),
            )
            if cursor.fetchone() != (None,):
                raise AssertionError("legacy corridor view exposed a habitat from another location")
            cursor.execute(
                "SELECT corridor_count FROM v_habitat_summary WHERE habitat_id = %s",
                (habitat_b,),
            )
            if cursor.fetchone() != (0,):
                raise AssertionError("habitat summary attributed a foreign corridor to this habitat")
            assertions += 1

            cursor.execute(
                "SELECT habitat_zone_name FROM v_buffer_compliance WHERE location_id = %s",
                (location_a,),
            )
            if cursor.fetchone() != (None,):
                raise AssertionError("legacy buffer view exposed a habitat from another location")
            assertions += 1

            for statement, params in (
                (
                    """
                    INSERT INTO wildlife_corridor (location_id, corridor_name, source_habitat_id)
                    VALUES (%s, 'Rejected cross-farm corridor', %s)
                    """,
                    (location_a, habitat_b),
                ),
                (
                    """
                    INSERT INTO buffer_zone_monitoring (location_id, habitat_zone_id, check_date)
                    VALUES (%s, %s, CURRENT_DATE)
                    """,
                    (location_a, habitat_b),
                ),
            ):
                try:
                    cursor.execute(statement, params)
                except errors.ForeignKeyViolation:
                    assertions += 1
                else:
                    raise AssertionError("cross-location landscape reference was accepted")

            cursor.execute(
                """
                INSERT INTO wildlife_corridor (location_id, corridor_name, source_habitat_id, condition)
                VALUES (%s, 'Same-farm corridor', %s, 'good')
                """,
                (location_a, habitat_a),
            )
            cursor.execute(
                """
                INSERT INTO buffer_zone_monitoring (location_id, habitat_zone_id, check_date, compliant)
                VALUES (%s, %s, CURRENT_DATE, TRUE)
                """,
                (location_a, habitat_a),
            )
            cursor.execute(
                "SELECT source_habitat FROM v_corridor_status WHERE corridor_name = 'Same-farm corridor'"
            )
            if cursor.fetchone() != ("A habitat",):
                raise AssertionError("same-location habitat relationship was not preserved")
            cursor.execute(
                "SELECT habitat_zone_name FROM v_buffer_compliance WHERE location_id = %s AND habitat_zone_id = %s",
                (location_a, habitat_a),
            )
            if cursor.fetchone() != ("A habitat",):
                raise AssertionError("same-location buffer habitat was not preserved")
            assertions += 1

            cursor.execute(MIGRATION_603.read_text())
            cursor.execute("SELECT source_habitat FROM v_corridor_status WHERE location_id = %s", (location_a,))
            visible_names = [row[0] for row in cursor.fetchall()]
            if "B private habitat" in visible_names or "A habitat" not in visible_names:
                raise AssertionError("migration replay changed the view's location-safe projection")
            assertions += 1

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with a geometry domain stub",
            "migrations": [MIGRATION_154.name, MIGRATION_603.name],
            "migration_603_replayed": True,
            "assertion_groups_passed": assertions,
            "historical_reference_preflight": preflight,
            "preflight_write_attempt_rejected": True,
            "checks": [
                "migration 603 adds location-composite references without rejecting historic rows",
                "read-only preflight returns only global counts for the three fixed reference types",
                "operator CLI requires an explicit target and prints only the sanitized aggregate",
                "read-only preflight transaction rejects a synthetic write",
                "legacy corridor/buffer views hide mismatched foreign habitat names and counts",
                "new cross-location source-habitat and buffer links fail database constraints",
                "same-location corridor and buffer relationships remain available",
                "migration replay preserves the location-safe view behavior",
            ],
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "historical_mismatches_rewritten": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if conn is not None:
            conn.close()
        if preflight_conn is not None:
            preflight_conn.close()
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - expose disposable SQL acceptance failures.
        print(f"landscape reference disposable check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
