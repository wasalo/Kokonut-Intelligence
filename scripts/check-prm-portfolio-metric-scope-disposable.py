#!/usr/bin/env python3
"""Replay migration 689 against synthetic PostgreSQL 16 schema and data."""

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

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/689_prm_portfolio_metric_scope.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-30-recovery/prm-portfolio-metric-scope-disposable.json"
IMAGE = os.environ.get("PRM_SCOPE_TEST_IMAGE", "postgres:16")


def command(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {args[0]} {args[1]} …\n{details}")
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return command(
        [
            docker, "exec", "-i", container, "psql", "-X", "-q", "-A", "-t",
            "--username=postgres", "--dbname=postgres", "--set=ON_ERROR_STOP=1",
        ],
        input_text=sql,
    )


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
    container = f"kokonut-prm-scope-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    assertions = 0
    rows: list[str] = []
    try:
        command([
            docker, "run", "--detach", "--rm", "--network", "none",
            "--name", container, "--env", f"POSTGRES_PASSWORD={password}", IMAGE,
        ])
        started = True
        wait_ready(docker, container)

        psql(docker, container, """
            CREATE TABLE process_map (
                process_key VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );
            CREATE TABLE process_maturity_level (
                level INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL
            );
            CREATE TABLE process_maturity (
                id UUID PRIMARY KEY,
                process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key),
                maturity_level INTEGER NOT NULL REFERENCES process_maturity_level(level)
            );
            CREATE TABLE metric_value (
                id UUID PRIMARY KEY,
                metric_id UUID NOT NULL,
                location_id UUID,
                value NUMERIC(15,4),
                unit VARCHAR(50),
                verified BOOLEAN NOT NULL DEFAULT FALSE
            );

            INSERT INTO process_map (process_key, name) VALUES
                ('soil-restoration', 'Soil restoration'),
                ('water-management', 'Water management');
            INSERT INTO process_maturity_level (level, name) VALUES
                (2, 'Managed'), (3, 'Defined'), (4, 'Quantitatively Managed');
            INSERT INTO process_maturity (id, process_key, maturity_level) VALUES
                ('a1000000-0000-4000-8000-000000000001', 'soil-restoration', 3),
                ('a1000000-0000-4000-8000-000000000002', 'soil-restoration', 3),
                ('a1000000-0000-4000-8000-000000000003', 'soil-restoration', 4),
                ('a1000000-0000-4000-8000-000000000004', 'water-management', 2);

            -- Reproduce the existing migration-196 view contract before replacement.
            CREATE VIEW v_process_outcome_correlation AS
            SELECT pm.process_key, pm.name AS process_name,
                   pmaturity.maturity_level, ml.name AS maturity_name,
                   COUNT(DISTINCT mv.id) AS metric_count,
                   AVG(mv.value) AS avg_metric_value,
                   COUNT(DISTINCT mv.location_id) AS location_count
              FROM process_maturity pmaturity
              JOIN process_map pm ON pm.process_key = pmaturity.process_key
              JOIN process_maturity_level ml ON ml.level = pmaturity.maturity_level
              LEFT JOIN metric_value mv ON mv.location_id IS NOT NULL AND mv.verified = TRUE
             GROUP BY pm.process_key, pm.name, pmaturity.maturity_level, ml.name;
        """)

        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        psql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        assertions += 1

        psql(docker, container, """
            INSERT INTO metric_value (id, metric_id, location_id, value, unit, verified) VALUES
                ('b1000000-0000-4000-8000-000000000001', 'b2000000-0000-4000-8000-000000000001', 'c1000000-0000-4000-8000-000000000001', 12.5, 'kg', TRUE),
                ('b1000000-0000-4000-8000-000000000002', 'b2000000-0000-4000-8000-000000000002', 'c1000000-0000-4000-8000-000000000001', 75.0, 'percent', TRUE),
                ('b1000000-0000-4000-8000-000000000003', 'b2000000-0000-4000-8000-000000000003', 'c1000000-0000-4000-8000-000000000002', 240.0, 'USD', TRUE),
                ('b1000000-0000-4000-8000-000000000004', 'b2000000-0000-4000-8000-000000000004', 'c1000000-0000-4000-8000-000000000002', 8.0, 'count', TRUE),
                ('b1000000-0000-4000-8000-000000000005', 'b2000000-0000-4000-8000-000000000005', NULL, 99.0, 'USD', TRUE),
                ('b1000000-0000-4000-8000-000000000006', 'b2000000-0000-4000-8000-000000000006', 'c1000000-0000-4000-8000-000000000001', 11.0, 'kg', FALSE);

            DO $$
            DECLARE
                maturity_rows BIGINT;
                portfolio_rows BIGINT;
                summary_metric_count BIGINT;
                summary_average NUMERIC;
                summary_locations BIGINT;
                bad_maturity_rows BIGINT;
            BEGIN
                SELECT COUNT(*) INTO maturity_rows
                  FROM v_process_outcome_correlation
                 WHERE scope = 'process_maturity';
                IF maturity_rows <> 3 THEN
                    RAISE EXCEPTION 'expected 3 grouped maturity rows, got %', maturity_rows;
                END IF;

                SELECT COUNT(*) INTO bad_maturity_rows
                  FROM v_process_outcome_correlation
                 WHERE scope = 'process_maturity'
                   AND (metric_count IS NOT NULL OR avg_metric_value IS NOT NULL
                        OR location_count IS NOT NULL);
                IF bad_maturity_rows <> 0 THEN
                    RAISE EXCEPTION 'process maturity rows contain portfolio metrics';
                END IF;

                SELECT COUNT(*) INTO portfolio_rows
                  FROM v_process_outcome_correlation
                 WHERE scope = 'portfolio_metrics';
                IF portfolio_rows <> 1 THEN
                    RAISE EXCEPTION 'expected exactly 1 portfolio summary row, got %', portfolio_rows;
                END IF;

                SELECT metric_count, avg_metric_value, location_count
                  INTO summary_metric_count, summary_average, summary_locations
                  FROM v_process_outcome_correlation
                 WHERE scope = 'portfolio_metrics';
                IF summary_metric_count <> 4 OR summary_locations <> 2
                   OR summary_average IS NOT NULL THEN
                    RAISE EXCEPTION 'unexpected portfolio summary: count %, average %, locations %',
                        summary_metric_count, summary_average, summary_locations;
                END IF;
            END $$;
        """)
        assertions += 4

        output = psql(docker, container, """
            SELECT scope || '|' || COALESCE(process_key, '') || '|'
                   || COALESCE(maturity_level::TEXT, '') || '|' || maturity_name || '|'
                   || COALESCE(metric_count::TEXT, '') || '|'
                   || COALESCE(avg_metric_value::TEXT, '') || '|'
                   || COALESCE(location_count::TEXT, '')
              FROM v_process_outcome_correlation
             ORDER BY CASE scope WHEN 'process_maturity' THEN 0 ELSE 1 END,
                      process_key NULLS LAST, maturity_level NULLS LAST;
        """)
        rows = output.splitlines()
        expected = [
            "process_maturity|soil-restoration|3|Defined|||",
            "process_maturity|soil-restoration|4|Quantitatively Managed|||",
            "process_maturity|water-management|2|Managed|||",
            "portfolio_metrics|||Portfolio-wide verified metrics|4||2",
        ]
        if rows != expected:
            raise AssertionError(f"unexpected PRM view rows: {rows!r}")
        assertions += 1

        ports = json.loads(command([
            docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container,
        ]))
        if any(bindings for bindings in ports.values() if bindings):
            raise AssertionError("disposable PostgreSQL unexpectedly published a host port")

    finally:
        if started:
            command([docker, "stop", container])
            cleanup_deadline = time.monotonic() + 10
            while time.monotonic() < cleanup_deadline:
                inspect = subprocess.run(
                    [docker, "inspect", container],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if inspect.returncode != 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("disposable PostgreSQL container remains after cleanup")

    evidence = {
        "result": "passed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": "PostgreSQL 16 disposable container",
        "migration": MIGRATION.name,
        "migration_replayed": True,
        "network_mode": "none",
        "host_port_published": False,
        "synthetic_rows": {
            "duplicate_process_maturity_assessments": 2,
            "verified_metrics_with_location": 4,
            "verified_metrics_without_location": 1,
            "unverified_metrics_with_location": 1,
            "metric_units": ["kg", "percent", "USD", "count"],
        },
        "assertions_passed": assertions,
        "result_rows": rows,
        "candidate_database_touched": False,
        "legacy_database_touched": False,
        "container_cleanup": "passed",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - disposable acceptance should expose SQL failures.
        print(f"PRM portfolio scope check failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise
