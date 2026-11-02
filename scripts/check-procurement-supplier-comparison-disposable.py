#!/usr/bin/env python3
"""Exercise supplier comparison against isolated synthetic PostgreSQL 16."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.analytics.procurement import compute_supplier_comparison  # noqa: E402

IMAGE = os.environ.get("PROCUREMENT_TEST_IMAGE", "postgres:16")


def docker_call(args: list[str], *, check: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode:
        diagnostic = result.stderr.strip()
        for argument in args:
            if argument.startswith("POSTGRES_PASSWORD="):
                diagnostic = diagnostic.replace(argument, "POSTGRES_PASSWORD=[redacted]")
        raise RuntimeError(f"Docker command failed: {args[1]}: {diagnostic[:300]}")
    return result.stdout.strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready = subprocess.run(
            [
                docker,
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
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    try:
        canonical_uuid = str(uuid.UUID(text))
    except (ValueError, AttributeError):
        return "'" + text.replace("'", "''") + "'"
    return f"'{canonical_uuid}'::uuid"


class DisposablePsqlConnection:
    """Run adapter SQL through psql inside the isolated container."""

    def __init__(self, docker: str, container: str) -> None:
        self.docker = docker
        self.container = container
        self.schema: str | None = None

    def cursor(self, *, cursor_factory: Any = None) -> "DisposablePsqlCursor":
        del cursor_factory
        return DisposablePsqlCursor(self)

    def execute(self, statement: str) -> str:
        prefix = f'SET search_path TO "{self.schema}", public;\n' if self.schema else ""
        result = subprocess.run(
            [
                self.docker,
                "exec",
                "-i",
                self.container,
                "psql",
                "--no-psqlrc",
                "--quiet",
                "--csv",
                "--set",
                "ON_ERROR_STOP=1",
                "--username",
                "postgres",
                "--dbname",
                "postgres",
            ],
            input=prefix + statement.rstrip() + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("disposable PostgreSQL rejected synthetic SQL")
        return result.stdout

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


class DisposablePsqlCursor:
    def __init__(self, connection: DisposablePsqlConnection) -> None:
        self.connection = connection
        self.statement = ""
        self.params: tuple[Any, ...] = ()

    def execute(self, statement: str, params: tuple[Any, ...] | list[Any] = ()) -> None:
        self.statement = statement
        self.params = tuple(params or ())

    def fetchall(self) -> list[dict[str, Any]]:
        statement = self.statement
        for parameter in self.params:
            if "%s" not in statement:
                raise RuntimeError("supplier-comparison SQL has fewer placeholders than values")
            statement = statement.replace("%s", _sql_literal(parameter), 1)
        if "%s" in statement:
            raise RuntimeError("supplier-comparison SQL has unbound parameters")

        output = self.connection.execute(statement)
        reader = csv.DictReader(io.StringIO(output))
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            row: dict[str, Any] = {}
            for key, value in raw_row.items():
                if value in (None, ""):
                    row[key] = None
                elif key == "order_count":
                    row[key] = int(value)
                elif key in {
                    "quality_rating",
                    "reliability_score",
                    "total_spend",
                    "avg_order_value",
                    "avg_discount_pct",
                    "latest_quality_score",
                }:
                    row[key] = Decimal(value)
                else:
                    row[key] = value
            rows.append(row)
        return rows

    def close(self) -> None:
        return None


def _assert_metrics(
    row: dict[str, Any], *, count: int, spend: Decimal, average: Decimal
) -> None:
    assert row["order_count"] == count
    assert Decimal(row["total_spend"]) == spend
    assert math.isclose(
        float(row["avg_order_value"]), float(average), rel_tol=1e-12, abs_tol=1e-12
    )


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    suffix = f"{os.getpid()}-{secrets.token_hex(3)}"
    container = f"kokonut-procurement-{suffix}"
    network = f"kokonut-procurement-net-{suffix}"
    password = secrets.token_urlsafe(24)
    connection: DisposablePsqlConnection | None = None
    container_started = False
    network_created = False
    cleanup_errors: list[str] = []
    result: dict[str, object] = {
        "database": "disposable PostgreSQL 16",
        "network_isolated": True,
        "candidate_or_legacy_modified": False,
        "provider_contacted": False,
        "result": "failed",
    }
    stage = "container_start"

    try:
        docker_call([docker, "network", "create", "--internal", network])
        network_created = True
        docker_call(
            [
                docker,
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                network,
                "--tmpfs",
                "/var/lib/postgresql/data:rw,nosuid,size=256m",
                "--env",
                f"POSTGRES_PASSWORD={password}",
                IMAGE,
            ]
        )
        container_started = True
        wait_ready(docker, container)
        connection = DisposablePsqlConnection(docker, container)

        stage = "version_and_schema_setup"
        version_rows = DisposablePsqlCursor(connection)
        version_rows.execute("SELECT current_setting('server_version_num') AS version_num")
        version_num = int(version_rows.fetchall()[0]["version_num"])
        if version_num < 160000 or version_num >= 170000:
            raise RuntimeError("disposable database image is not PostgreSQL 16")

        schema = f"procurement_test_{secrets.token_hex(6)}"
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.schema = schema
        connection.execute(
            """
            CREATE TABLE supplier_profile (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                supplier_type VARCHAR(100),
                quality_rating NUMERIC(3, 2),
                reliability_score NUMERIC(3, 2),
                delivery_lead_time_days INTEGER,
                payment_terms VARCHAR(100),
                status VARCHAR(50) NOT NULL
            );
            CREATE TABLE purchase_order (
                id UUID PRIMARY KEY,
                location_id UUID,
                supplier_id UUID NOT NULL REFERENCES supplier_profile(id),
                total_amount NUMERIC(15, 2),
                discount_pct NUMERIC(5, 2),
                status VARCHAR(50) NOT NULL
            );
            CREATE TABLE purchase_order_item (
                id UUID PRIMARY KEY,
                order_id UUID NOT NULL REFERENCES purchase_order(id),
                product_category VARCHAR(100)
            );
            CREATE TABLE supplier_quality_assessment (
                id UUID PRIMARY KEY,
                supplier_id UUID NOT NULL REFERENCES supplier_profile(id),
                assessment_date DATE NOT NULL,
                overall_score NUMERIC(3, 2)
            );
            """
        )

        stage = "synthetic_fixture_setup"
        supplier_id = uuid.uuid4()
        location_a, location_b = uuid.uuid4(), uuid.uuid4()
        order_soil_a1, order_soil_a2 = uuid.uuid4(), uuid.uuid4()
        order_seed_a, order_soil_b = uuid.uuid4(), uuid.uuid4()
        cancelled_soil = uuid.uuid4()
        connection.execute(
            f"""
            INSERT INTO supplier_profile (
                id, name, supplier_type, quality_rating, reliability_score,
                delivery_lead_time_days, payment_terms, status
            ) VALUES (
                {_sql_literal(supplier_id)}, 'Synthetic Supplier', 'cooperative',
                0.9, 0.8, 7, 'net 30', 'active'
            );
            INSERT INTO purchase_order (
                id, location_id, supplier_id, total_amount, discount_pct, status
            ) VALUES
                ({_sql_literal(order_soil_a1)}, {_sql_literal(location_a)}, {_sql_literal(supplier_id)}, 10, 2, 'paid'),
                ({_sql_literal(order_soil_a2)}, {_sql_literal(location_a)}, {_sql_literal(supplier_id)}, 20, 4, 'paid'),
                ({_sql_literal(order_seed_a)}, {_sql_literal(location_a)}, {_sql_literal(supplier_id)}, 100, 10, 'paid'),
                ({_sql_literal(order_soil_b)}, {_sql_literal(location_b)}, {_sql_literal(supplier_id)}, 1000, 20, 'paid'),
                ({_sql_literal(cancelled_soil)}, {_sql_literal(location_a)}, {_sql_literal(supplier_id)}, 999, 99, 'cancelled');
            INSERT INTO purchase_order_item (id, order_id, product_category) VALUES
                ({_sql_literal(uuid.uuid4())}, {_sql_literal(order_soil_a1)}, 'soil'),
                ({_sql_literal(uuid.uuid4())}, {_sql_literal(order_soil_a1)}, 'soil'),
                ({_sql_literal(uuid.uuid4())}, {_sql_literal(order_soil_a2)}, 'soil'),
                ({_sql_literal(uuid.uuid4())}, {_sql_literal(order_seed_a)}, 'seed'),
                ({_sql_literal(uuid.uuid4())}, {_sql_literal(order_soil_b)}, 'soil'),
                ({_sql_literal(uuid.uuid4())}, {_sql_literal(cancelled_soil)}, 'soil');
            """
        )

        stage = "category_scoped_supplier_comparison"
        category_scoped = compute_supplier_comparison(
            connection, location_id=str(location_a), product_category="soil"
        )
        assert len(category_scoped) == 1
        _assert_metrics(
            category_scoped[0], count=2, spend=Decimal("30"), average=Decimal("15")
        )

        stage = "location_only_supplier_comparison"
        location_only = compute_supplier_comparison(connection, location_id=str(location_a))
        assert len(location_only) == 1
        _assert_metrics(
            location_only[0],
            count=3,
            spend=Decimal("130"),
            average=Decimal("130") / Decimal("3"),
        )

        stage = "category_only_supplier_comparison"
        category_only = compute_supplier_comparison(connection, product_category="soil")
        assert len(category_only) == 1
        _assert_metrics(
            category_only[0],
            count=3,
            spend=Decimal("1030"),
            average=Decimal("1030") / Decimal("3"),
        )

        stage = "unfiltered_supplier_comparison"
        unfiltered = compute_supplier_comparison(connection)
        assert len(unfiltered) == 1
        _assert_metrics(
            unfiltered[0],
            count=4,
            spend=Decimal("1130"),
            average=Decimal("1130") / Decimal("4"),
        )

        result.update(
            {
                "result": "passed",
                "version_major": version_num // 10000,
                "category_and_location": {
                    "order_count": category_scoped[0]["order_count"],
                    "total_spend": str(category_scoped[0]["total_spend"]),
                    "avg_order_value": str(category_scoped[0]["avg_order_value"]),
                },
                "location_only": {
                    "order_count": location_only[0]["order_count"],
                    "total_spend": str(location_only[0]["total_spend"]),
                    "avg_order_value": str(location_only[0]["avg_order_value"]),
                },
                "category_only": {
                    "order_count": category_only[0]["order_count"],
                    "total_spend": str(category_only[0]["total_spend"]),
                    "avg_order_value": str(category_only[0]["avg_order_value"]),
                },
                "unfiltered": {
                    "order_count": unfiltered[0]["order_count"],
                    "total_spend": str(unfiltered[0]["total_spend"]),
                    "avg_order_value": str(unfiltered[0]["avg_order_value"]),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 - avoid printing connection details/credentials
        result["failure_stage"] = stage
        result["failure_type"] = type(exc).__name__
        result["failure_code"] = getattr(exc, "pgcode", None)
        if isinstance(exc, RuntimeError):
            result["failure_detail"] = str(exc)[:400]
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()
        if container_started:
            stopped = subprocess.run(
                [docker, "stop", container], text=True, capture_output=True, check=False
            )
            if stopped.returncode:
                cleanup_errors.append("container_stop")
                removed = subprocess.run(
                    [docker, "rm", "--force", container],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if removed.returncode:
                    cleanup_errors.append("container_remove")
        if network_created:
            removed_network = subprocess.run(
                [docker, "network", "rm", network],
                text=True,
                capture_output=True,
                check=False,
            )
            if removed_network.returncode:
                cleanup_errors.append("network_remove")
        result["cleanup"] = "passed" if not cleanup_errors else "failed"
        if cleanup_errors:
            result["cleanup_errors"] = cleanup_errors
            result["result"] = "failed"

    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
