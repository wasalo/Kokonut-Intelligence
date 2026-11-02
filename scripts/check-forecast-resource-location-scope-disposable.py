#!/usr/bin/env python3
"""Exercise forecast and resource location lineage on disposable PostgreSQL 16."""

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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.analytics.resource_efficiency import compute_resource_consumption_by_crop  # noqa: E402
from services.export.reports.core import generate_forecast_summary  # noqa: E402
from services.forecast.yield_forecast import get_bed_areas_for_location  # noqa: E402

IMAGE = os.environ.get("FORECAST_RESOURCE_SCOPE_TEST_IMAGE", "postgres:16")
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-30-recovery/forecast-resource-location-scope-disposable.json"


def docker_run(args: list[str], *, check: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Docker command failed: {args[1]}")
    return result.stdout.strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


class DisposablePsqlConnection:
    def __init__(self, docker: str, container: str):
        self.docker = docker
        self.container = container

    def cursor(self, **_kwargs):
        return DisposablePsqlCursor(self)

    def execute(self, statement: str) -> str:
        result = subprocess.run(
            [
                self.docker, "exec", "-i", self.container, "psql", "--no-psqlrc", "--quiet",
                "--tuples-only", "--no-align", "--field-separator", "\t", "--set",
                "ON_ERROR_STOP=1", "--username", "postgres", "--dbname", "postgres",
            ],
            input=statement.rstrip() + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("disposable PostgreSQL rejected synthetic SQL")
        return result.stdout

    def rollback(self):
        return None

    def close(self):
        return None


class DisposablePsqlCursor:
    _FORECAST_COLUMNS = (
        "scenario_id scenario_name scenario_type metric_name value unit confidence_low "
        "confidence_high inputs period_start period_end calculated_at"
    ).split()

    def __init__(self, connection: DisposablePsqlConnection):
        self.connection = connection
        self.statement = ""
        self.params: tuple[object, ...] = ()

    def execute(self, statement: str, params=()):
        self.statement = statement
        self.params = tuple(params or ())

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def _query_output(self) -> list[list[str | None]]:
        statement = self.statement
        for parameter in self.params:
            value = str(uuid.UUID(str(parameter)))
            statement = statement.replace("%s", f"'{value}'::uuid", 1)
        if "%s" in statement:
            raise RuntimeError("acceptance query has unbound parameters")
        return [
            [None if field == "" else field for field in row.split("\t")]
            for row in self.connection.execute(statement).splitlines()
            if row
        ]

    def fetchall(self):
        rows = self._query_output()
        if "array_agg(DISTINCT cc.id" in self.statement:
            return [
                (
                    row[0], row[1], int(row[2]), float(row[3]),
                    row[4].strip("{}").split(",") if row[4] else [],
                    row[5].strip("{}").split(",") if row[5] else [],
                )
                for row in rows
            ]
        if "fo.scenario_id" in self.statement:
            result = []
            for row in rows:
                record = dict(zip(self._FORECAST_COLUMNS, row, strict=True))
                if record["inputs"]:
                    record["inputs"] = json.loads(record["inputs"])
                if record["calculated_at"]:
                    record["calculated_at"] = datetime.fromisoformat(
                        record["calculated_at"].replace(" ", "T", 1)
                    )
                result.append(record)
            return result
        return [tuple(row) for row in rows]

    def fetchone(self):
        rows = self._query_output()
        if not rows:
            return None
        if "SELECT name FROM location" in self.statement:
            return {"name": rows[0][0]}
        return tuple(rows[0])

    def close(self):
        return None


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    suffix = f"{os.getpid()}-{secrets.token_hex(3)}"
    container = f"kokonut-lineage-{suffix}"
    network = f"kokonut-lineage-net-{suffix}"
    password = secrets.token_urlsafe(24)
    started = network_created = False
    conn = None
    stage = "container_start"
    evidence: dict[str, object] = {
        "result": "failed",
        "database": "disposable PostgreSQL 16",
        "candidate_or_legacy_modified": False,
        "external_provider_contacted": False,
        "network_isolated": True,
    }
    try:
        docker_run([docker, "network", "create", "--internal", network])
        network_created = True
        docker_run(
            [docker, "run", "--detach", "--rm", "--name", container, "--network", network,
             "--env", f"POSTGRES_PASSWORD={password}", IMAGE]
        )
        started = True
        wait_ready(docker, container)
        conn = DisposablePsqlConnection(docker, container)

        location_a, location_b = str(uuid.uuid4()), str(uuid.uuid4())
        scenario_a, scenario_b = str(uuid.uuid4()), str(uuid.uuid4())
        crop_a, crop_b = str(uuid.uuid4()), str(uuid.uuid4())
        cycle_a, cycle_b = str(uuid.uuid4()), str(uuid.uuid4())
        cycle_a_second, cycle_cross_location = str(uuid.uuid4()), str(uuid.uuid4())
        farm_a, farm_b = str(uuid.uuid4()), str(uuid.uuid4())
        plot_a = str(uuid.uuid4())
        stage = "schema_and_fixture_setup"
        conn.execute(
            """
            CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE forecast_scenario (
                id UUID PRIMARY KEY, location_id UUID NOT NULL, name TEXT NOT NULL,
                scenario_type TEXT NOT NULL, status TEXT NOT NULL, assumptions JSONB,
                created_at TIMESTAMPTZ NOT NULL
            );
            CREATE TABLE forecast_output (
                scenario_id UUID NOT NULL, location_id UUID NOT NULL, metric_name TEXT NOT NULL,
                value NUMERIC, unit TEXT, confidence_low NUMERIC, confidence_high NUMERIC,
                inputs JSONB, period_start DATE, period_end DATE, calculated_at TIMESTAMPTZ
            );
            CREATE TABLE crop (id UUID PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE farm (id UUID PRIMARY KEY, location_id UUID NOT NULL);
            CREATE TABLE plot (
                id UUID PRIMARY KEY, farm_id UUID NOT NULL, name TEXT NOT NULL,
                bed_count INTEGER, bed_area_sqm NUMERIC
            );
            CREATE TABLE crop_cycle (
                id UUID PRIMARY KEY, location_id UUID NOT NULL, crop_id UUID NOT NULL,
                plot_id UUID, status TEXT NOT NULL
            );
            CREATE TABLE resource_consumption (
                location_id UUID NOT NULL, crop_cycle_id UUID NOT NULL, resource_type TEXT NOT NULL,
                unit TEXT NOT NULL, quantity NUMERIC NOT NULL, status TEXT NOT NULL
            );
            """
        )
        conn.execute(
            f"INSERT INTO location VALUES ('{location_a}', 'Target farm'), ('{location_b}', 'Other farm');"
            f"INSERT INTO forecast_scenario VALUES "
            f"('{scenario_a}', '{location_a}', 'Target forecast', 'yield', 'draft', '{{}}', now()), "
            f"('{scenario_b}', '{location_b}', 'Foreign forecast', 'yield', 'draft', '{{}}', now());"
            f"INSERT INTO forecast_output VALUES "
            f"('{scenario_a}', '{location_a}', 'target_metric', 7, 'tonne', 6, 8, '{{}}', NULL, NULL, now()), "
            f"('{scenario_b}', '{location_a}', 'foreign_parent_metric', 999, 'tonne', NULL, NULL, '{{}}', NULL, NULL, now()), "
            f"('{scenario_a}', '{location_b}', 'foreign_output_metric', 888, 'tonne', NULL, NULL, '{{}}', NULL, NULL, now());"
            f"INSERT INTO crop VALUES ('{crop_a}', 'Corn'), ('{crop_b}', 'Beans');"
            f"INSERT INTO farm VALUES ('{farm_a}', '{location_a}'), ('{farm_b}', '{location_b}');"
            f"INSERT INTO plot VALUES ('{plot_a}', '{farm_a}', 'Syntropic beds', 10, 2.0);"
            f"INSERT INTO crop_cycle VALUES "
            f"('{cycle_a}', '{location_a}', '{crop_a}', '{plot_a}', 'completed'), "
            f"('{cycle_a_second}', '{location_a}', '{crop_b}', '{plot_a}', 'completed'), "
            f"('{cycle_b}', '{location_b}', '{crop_b}', NULL, 'completed'), "
            f"('{cycle_cross_location}', '{location_b}', '{crop_b}', '{plot_a}', 'completed');"
            f"INSERT INTO resource_consumption VALUES "
            f"('{location_a}', '{cycle_a}', 'water', 'liter', 12, 'verified'), "
            f"('{location_a}', '{cycle_b}', 'water', 'liter', 500, 'verified'), "
            f"('{location_b}', '{cycle_b}', 'water', 'liter', 900, 'published');"
        )

        stage = "forecast_service_query"
        forecast = generate_forecast_summary(conn, location_a)
        forecast_metrics = [
            metric for scenario in forecast["scenarios"].values() for metric in scenario["metrics"]
        ]
        evidence["forecast_metrics"] = forecast_metrics
        evidence["forecast_foreign_parent_excluded"] = "foreign_parent_metric" not in forecast_metrics
        evidence["forecast_foreign_output_excluded"] = "foreign_output_metric" not in forecast_metrics
        evidence["forecast_target_retained"] = forecast_metrics == ["target_metric"]

        stage = "resource_service_query"
        resources = compute_resource_consumption_by_crop(conn, location_a)
        evidence["resource_rows"] = resources["by_crop"]
        evidence["resource_foreign_cycle_excluded"] = resources["by_crop"] == [
            {"resource_type": "water", "unit": "liter", "crop_name": "Corn", "total_quantity": 12.0}
        ]
        stage = "bed_area_location_and_deduplication"
        with patch("services.ingestion.base.get_db", return_value=conn):
            bed_areas = get_bed_areas_for_location(location_a)
        target_plot = bed_areas["plots"][plot_a]
        evidence["bed_area"] = bed_areas
        evidence["bed_area_counted_once_per_plot"] = (
            bed_areas["plot_count"] == 1
            and bed_areas["total_bed_area_sqm"] == 20.0
        )
        evidence["bed_cycles_same_location_retained"] = set(target_plot["cycle_ids"]) == {
            cycle_a,
            cycle_a_second,
        }
        evidence["bed_cycle_cross_location_excluded"] = (
            cycle_cross_location not in target_plot["cycle_ids"]
        )
        assertions = [
            evidence["forecast_foreign_parent_excluded"],
            evidence["forecast_foreign_output_excluded"],
            evidence["forecast_target_retained"],
            evidence["resource_foreign_cycle_excluded"],
            evidence["bed_area_counted_once_per_plot"],
            evidence["bed_cycles_same_location_retained"],
            evidence["bed_cycle_cross_location_excluded"],
        ]
        evidence["assertions"] = {f"assertion_{index + 1}": passed for index, passed in enumerate(assertions)}
        evidence["result"] = "passed" if all(assertions) else "failed"
    except Exception as exc:  # noqa: BLE001 - omit fixture data and container credentials
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()
        cleanup_errors = []
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)
            remaining = subprocess.run(
                [docker, "ps", "-aq", "--filter", f"name=^{container}$"],
                text=True,
                capture_output=True,
                check=False,
            )
            if remaining.returncode != 0:
                cleanup_errors.append("container_inventory")
            elif remaining.stdout.strip():
                removed = subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
                if removed.returncode != 0:
                    cleanup_errors.append("container_remove")
        if network_created:
            removed_network = subprocess.run([docker, "network", "rm", network], text=True, capture_output=True, check=False)
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
