#!/usr/bin/env python3
"""Exercise migration 428 and climate summary upserts on disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/428_climate_summary_idempotency.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-17-recovery/climate-summary-idempotency-disposable.json"
)
TABLES = (
    "ncep_weather_summary",
    "modis_lst_summary",
    "smap_soil_moisture",
    "sentinel1_sar_summary",
)
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
PLOT_ID = "22222222-2222-4222-8222-222222222222"
TARGET_DATE = "2026-10-16"


def run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )


def checked(command: list[str], *, input_text: str | None = None) -> str:
    result = run(command, input_text=input_text)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return checked(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v",
         "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    ready_count = 0
    while time.monotonic() < deadline:
        result = run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"]
        )
        ready_count = ready_count + 1 if result.returncode == 0 else 0
        if ready_count >= 4:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def create_fixture_sql() -> str:
    return "\n".join(
        f"""CREATE TABLE public.{table} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            location_id UUID NOT NULL,
            plot_id UUID,
            target_date DATE NOT NULL,
            source TEXT
        );"""
        for table in TABLES
    )


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    image = os.getenv("CLIMATE_SUMMARY_TEST_IMAGE", "postgres:16")
    container = f"kokonut-climate-summary-{os.getpid()}-{secrets.token_hex(3)}"
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    created = False
    checks: list[str] = []
    migration = MIGRATION.read_text(encoding="utf-8")

    try:
        checked([
            docker, "run", "-d", "--rm", "--network", "none", "--name", container,
            "-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", image,
        ])
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, create_fixture_sql())

        docker_sql(
            docker,
            container,
            f"""
            INSERT INTO public.ncep_weather_summary (location_id, plot_id, target_date, source)
            VALUES ('{LOCATION_ID}', NULL, '{TARGET_DATE}', 'era5_land_daily_aggr'),
                   ('{LOCATION_ID}', NULL, '{TARGET_DATE}', 'era5_land_daily_aggr');
            """,
        )
        duplicate_attempt = run(
            [docker, "exec", "-i", container, "psql", "-X", "-q", "-v",
             "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
            input_text=migration,
        )
        duplicate_output = "\n".join((duplicate_attempt.stdout, duplicate_attempt.stderr))
        if duplicate_attempt.returncode == 0 or "duplicate location-level rows" not in duplicate_output:
            raise AssertionError("migration did not fail closed on duplicate location summaries")
        checks.append("migration refuses unreviewed location-level duplicates")

        docker_sql(
            docker,
            container,
            f"DELETE FROM public.ncep_weather_summary WHERE location_id = '{LOCATION_ID}';",
        )
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        checks.append("migration applies and replays cleanly after duplicate reconciliation")

        for table in TABLES:
            docker_sql(
                docker,
                container,
                f"""
                INSERT INTO public.{table} (location_id, plot_id, target_date, source)
                VALUES ('{LOCATION_ID}', NULL, '{TARGET_DATE}', 'synthetic-provider')
                ON CONFLICT (location_id, target_date, source)
                    WHERE plot_id IS NULL AND source IS NOT NULL
                DO UPDATE SET target_date = EXCLUDED.target_date;
                INSERT INTO public.{table} (location_id, plot_id, target_date, source)
                VALUES ('{LOCATION_ID}', NULL, '{TARGET_DATE}', 'synthetic-provider')
                ON CONFLICT (location_id, target_date, source)
                    WHERE plot_id IS NULL AND source IS NOT NULL
                DO UPDATE SET target_date = EXCLUDED.target_date;
                """,
            )

        docker_sql(
            docker,
            container,
            f"""
            DO $$
            DECLARE table_name TEXT;
                    row_count INTEGER;
            BEGIN
                FOREACH table_name IN ARRAY ARRAY[
                    'ncep_weather_summary', 'modis_lst_summary',
                    'smap_soil_moisture', 'sentinel1_sar_summary'
                ] LOOP
                    EXECUTE format(
                        'SELECT COUNT(*) FROM public.%I WHERE location_id = $1 AND plot_id IS NULL AND target_date = $2 AND source = $3',
                        table_name
                    ) INTO row_count USING '{LOCATION_ID}'::uuid, '{TARGET_DATE}'::date, 'synthetic-provider';
                    IF row_count <> 1 THEN
                        RAISE EXCEPTION 'idempotent upsert failed for %', table_name;
                    END IF;
                END LOOP;
            END
            $$;
            """,
        )
        checks.append("all four canonical summary keys collapse repeated provider retries")

        docker_sql(
            docker,
            container,
            f"""
            INSERT INTO public.modis_lst_summary (location_id, plot_id, target_date, source)
            VALUES ('{LOCATION_ID}', '{PLOT_ID}', '{TARGET_DATE}', 'synthetic-provider'),
                   ('{LOCATION_ID}', '{PLOT_ID}', '{TARGET_DATE}', 'synthetic-provider');
            DO $$
            BEGIN
                IF (SELECT COUNT(*) FROM public.modis_lst_summary
                     WHERE plot_id = '{PLOT_ID}'::uuid) <> 2 THEN
                    RAISE EXCEPTION 'plot-level source rows must remain outside the location key';
                END IF;
            END
            $$;
            """,
        )
        checks.append("plot-level records retain their existing independent key space")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"migration": MIGRATION.name, "checks": checks}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "checks": checks, "evidence": str(output)}, indent=2))
        return 0
    finally:
        if created:
            run([docker, "rm", "-f", container])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"climate summary disposable check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
