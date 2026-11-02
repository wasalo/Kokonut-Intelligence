#!/usr/bin/env python3
"""Exercise resource-efficiency SQL against synthetic disposable PostgreSQL 16."""

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.analytics.resource_efficiency import compute_labor_efficiency  # noqa: E402

IMAGE = os.environ.get("RESOURCE_EFFICIENCY_TEST_IMAGE", "postgres:16")
EVIDENCE = (
    ROOT
    / "docs/refactor/builds/2026-10-29-recovery/resource-efficiency-disposable.json"
)


def docker_run(args: list[str], *, check: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Docker command failed: {args[1]}")
    return result.stdout.strip()


def wait_ready(container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                shutil.which("docker") or "docker",
                "exec",
                container,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "postgres",
                "-d",
                "postgres",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


class DisposablePsqlConnection:
    """Run source SQL with psql inside the isolated PostgreSQL container."""

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
            raise RuntimeError("resource-efficiency SQL has unbound parameters")
        output = self.connection.execute(statement)
        return [
            tuple(None if value == "" else value for value in line.split("\t"))
            for line in output.splitlines()
            if line
        ]

    def close(self):
        return None


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    container = f"kokonut-resource-efficiency-{os.getpid()}-{secrets.token_hex(3)}"
    network = f"kokonut-resource-efficiency-net-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    conn = None
    evidence: dict[str, object] = {
        "result": "failed",
        "database": "disposable PostgreSQL 16",
        "candidate_or_legacy_modified": False,
        "external_provider_contacted": False,
        "network_isolated": True,
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
        wait_ready(container)
        conn = DisposablePsqlConnection(docker, container)
        stage = "schema_and_fixture_setup"
        location_a, location_b = str(uuid.uuid4()), str(uuid.uuid4())
        crop_corn, crop_beans = str(uuid.uuid4()), str(uuid.uuid4())
        cycle_a, cycle_b = str(uuid.uuid4()), str(uuid.uuid4())
        other_cycle = str(uuid.uuid4())
        conn.execute(
            """
                CREATE TABLE crop (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL
                );
                CREATE TABLE crop_cycle (
                    id UUID PRIMARY KEY,
                    location_id UUID NOT NULL,
                    crop_id UUID NOT NULL REFERENCES crop(id),
                    cycle_name TEXT,
                    actual_harvest_date DATE,
                    status TEXT NOT NULL
                );
                CREATE TABLE harvest_event (
                    crop_cycle_id UUID NOT NULL,
                    location_id UUID NOT NULL,
                    quantity NUMERIC NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE labor_event (
                    crop_cycle_id UUID,
                    location_id UUID NOT NULL,
                    hours_worked NUMERIC NOT NULL,
                    status TEXT NOT NULL
                );
                """
        )
        conn.execute(
            f"INSERT INTO crop (id, name) VALUES ('{crop_corn}'::uuid, 'Corn'), "
            f"('{crop_beans}'::uuid, 'Beans')"
        )
        conn.execute(
            f"""
                INSERT INTO crop_cycle
                    (id, location_id, crop_id, cycle_name, actual_harvest_date, status)
                VALUES
                    ('{cycle_a}'::uuid, '{location_a}'::uuid, '{crop_corn}'::uuid,
                     'Target corn cycle', DATE '2026-09-01', 'completed'),
                    ('{cycle_b}'::uuid, '{location_a}'::uuid, '{crop_beans}'::uuid,
                     'Target bean cycle', DATE '2026-10-01', 'harvested'),
                    ('{other_cycle}'::uuid, '{location_b}'::uuid, '{crop_corn}'::uuid,
                     'Other farm cycle', DATE '2026-08-01', 'completed')
                """
        )
        conn.execute(
            f"""
                INSERT INTO harvest_event (crop_cycle_id, location_id, quantity, status)
                VALUES
                    ('{cycle_a}'::uuid, '{location_a}'::uuid, 100, 'verified'),
                    ('{cycle_a}'::uuid, '{location_a}'::uuid, 50, 'published'),
                    ('{cycle_a}'::uuid, '{location_b}'::uuid, 900, 'verified'),
                    ('{cycle_b}'::uuid, '{location_a}'::uuid, 40, 'verified'),
                    ('{other_cycle}'::uuid, '{location_b}'::uuid, 1000, 'published')
                """,
        )
        conn.execute(
            f"""
                INSERT INTO labor_event (crop_cycle_id, location_id, hours_worked, status)
                VALUES
                    ('{cycle_a}'::uuid, '{location_a}'::uuid, 2, 'verified'),
                    ('{cycle_a}'::uuid, '{location_a}'::uuid, 3, 'published'),
                    ('{cycle_a}'::uuid, '{location_b}'::uuid, 99, 'verified'),
                    ('{cycle_b}'::uuid, '{location_a}'::uuid, 4, 'verified'),
                    ('{other_cycle}'::uuid, '{location_b}'::uuid, 200, 'published')
                """,
        )

        stage = "resource_efficiency_query"
        result = compute_labor_efficiency(conn, str(location_a))
        evidence["cycle_names"] = [cycle["cycle_name"] for cycle in result["cycles"]]
        evidence["cycle_crop_names"] = [cycle["crop_name"] for cycle in result["cycles"]]
        evidence["cycle_totals"] = [
            {
                "harvest_kg": cycle["harvest_kg"],
                "labor_hours": cycle["labor_hours"],
                "kg_per_labor_hour": cycle["kg_per_labor_hour"],
            }
            for cycle in result["cycles"]
        ]
        evidence["total_harvest_kg"] = result["total_harvest_kg"]
        evidence["total_labor_hours"] = result["total_labor_hours"]
        evidence["overall_kg_per_labor_hour"] = result["overall_kg_per_labor_hour"]

        expected = {
            "cycle_names": ["Target corn cycle", "Target bean cycle"],
            "cycle_crop_names": ["Corn", "Beans"],
            "cycle_totals": [
                {"harvest_kg": 150.0, "labor_hours": 5.0, "kg_per_labor_hour": 30.0},
                {"harvest_kg": 40.0, "labor_hours": 4.0, "kg_per_labor_hour": 10.0},
            ],
            "total_harvest_kg": 190.0,
            "total_labor_hours": 9.0,
            "overall_kg_per_labor_hour": 21.11,
        }
        evidence["assertions"] = {
            key: evidence[key] == value for key, value in expected.items()
        }
        evidence["result"] = "passed" if all(evidence["assertions"].values()) else "failed"
    except Exception as exc:  # noqa: BLE001 - keep disposable credentials and fixture IDs private
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_code"] = getattr(exc, "pgcode", None)
        evidence["failure_stage"] = stage
        diagnostic = getattr(getattr(exc, "diag", None), "message_primary", None)
        if diagnostic:
            evidence["failure_detail"] = diagnostic
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()
        cleanup_errors = []
        if started:
            subprocess.run(
                [docker, "stop", container], text=True, capture_output=True, check=False
            )
            remaining = subprocess.run(
                [docker, "ps", "-aq", "--filter", f"name=^{container}$"],
                text=True,
                capture_output=True,
                check=False,
            )
            if remaining.returncode != 0:
                cleanup_errors.append("container_inventory")
            elif remaining.stdout.strip():
                removed = subprocess.run(
                    [docker, "rm", "--force", container],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if removed.returncode != 0:
                    cleanup_errors.append("container_remove")
        if network_created:
            removed_network = subprocess.run(
                [docker, "network", "rm", network],
                text=True,
                capture_output=True,
                check=False,
            )
            if removed_network.returncode != 0:
                cleanup_errors.append("network_remove")
        evidence["cleanup"] = "passed" if not cleanup_errors else "failed"
        if cleanup_errors:
            evidence["cleanup_error_classes"] = cleanup_errors
            evidence["result"] = "failed"
        evidence["completed_at"] = datetime.now(timezone.utc).isoformat()
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")

    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
