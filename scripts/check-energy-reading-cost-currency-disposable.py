#!/usr/bin/env python3
"""Exercise migration 604 against a synthetic PostgreSQL 16 energy schema."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATION = ROOT / "schemas/postgres/604_energy_reading_cost_currency.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-24-recovery/cap-006-energy-cost-currency-disposable.json"
IMAGE = os.environ.get("ENERGY_COST_CURRENCY_TEST_IMAGE", "postgres:16")

from services.analytics.energy_monitoring import (  # noqa: E402
    get_consumption,
    get_cost_analysis,
    record_reading,
)


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
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


def psql(docker: str, container: str, sql: str) -> str:
    return run([
        docker, "exec", "-i", container, "psql", "-X", "-q",
        "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ], input_text=sql)


FIXTURE = r"""
CREATE TABLE public.location (id uuid PRIMARY KEY, name text NOT NULL);
CREATE TABLE public.energy_source (
    id uuid PRIMARY KEY, location_id uuid NOT NULL REFERENCES public.location(id),
    source_name text NOT NULL, source_type text NOT NULL
);
CREATE TABLE public.energy_reading (
    id uuid PRIMARY KEY, location_id uuid NOT NULL REFERENCES public.location(id),
    source_id uuid NOT NULL REFERENCES public.energy_source(id), reading_date date NOT NULL,
    reading_type text NOT NULL, kwh numeric(10,2) NOT NULL, cost_per_kwh numeric(8,4),
    total_cost numeric(10,2), activity_type text, equipment_id uuid, notes text,
    metadata jsonb NOT NULL DEFAULT '{}', status text NOT NULL DEFAULT 'recorded'
);
CREATE VIEW public.v_energy_consumption AS
SELECT er.location_id, l.name AS location_name, es.source_name, es.source_type,
       er.activity_type, er.reading_date, er.reading_type, er.kwh,
       er.cost_per_kwh, er.total_cost, er.status
  FROM public.energy_reading er
  JOIN public.location l ON l.id = er.location_id
  JOIN public.energy_source es ON es.id = er.source_id
 WHERE er.reading_type = 'consumption';
INSERT INTO public.location VALUES ('10000000-0000-0000-0000-000000000001', 'Synthetic Farm');
INSERT INTO public.energy_source VALUES
 ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'Synthetic grid', 'grid');
-- Historic costs are intentionally unclassified.
INSERT INTO public.energy_reading
 (id, location_id, source_id, reading_date, reading_type, kwh, cost_per_kwh, total_cost)
VALUES
 ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', CURRENT_DATE, 'consumption', 100, .10, 10);
"""

ACCEPTANCE = r"""
INSERT INTO public.energy_reading
 (id, location_id, source_id, reading_date, reading_type, kwh, cost_per_kwh, total_cost, cost_currency_code)
VALUES
 ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', CURRENT_DATE, 'consumption', 100, .15, 15, 'USD'),
 ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', CURRENT_DATE, 'consumption', 100, .60, 60, 'DOP'),
 ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', CURRENT_DATE, 'consumption', 10, NULL, NULL, NULL);

DO $$
DECLARE
    v_cost numeric;
    v_currency text;
    v_count bigint;
BEGIN
    SELECT cost_currency_code INTO v_currency FROM public.energy_reading
     WHERE id = '30000000-0000-0000-0000-000000000001';
    IF v_currency IS NOT NULL THEN RAISE EXCEPTION 'historical currency was guessed'; END IF;

    SELECT sum(total_cost) INTO v_cost FROM public.energy_reading WHERE cost_currency_code = 'USD';
    IF v_cost IS DISTINCT FROM 15::numeric THEN RAISE EXCEPTION 'USD total is wrong'; END IF;
    SELECT sum(total_cost) INTO v_cost FROM public.energy_reading WHERE cost_currency_code = 'DOP';
    IF v_cost IS DISTINCT FROM 60::numeric THEN RAISE EXCEPTION 'DOP total is wrong'; END IF;
    SELECT count(*) INTO v_count FROM public.v_energy_consumption WHERE cost_currency_code IS NULL;
    IF v_count <> 2 THEN RAISE EXCEPTION 'view did not preserve historic and no-cost rows'; END IF;

    BEGIN
        INSERT INTO public.energy_reading
            (id, location_id, source_id, reading_date, reading_type, kwh, total_cost)
        VALUES
            ('30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', CURRENT_DATE, 'consumption', 1, 1);
        RAISE EXCEPTION 'cost without currency was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO public.energy_reading
            (id, location_id, source_id, reading_date, reading_type, kwh, cost_per_kwh, cost_currency_code)
        VALUES
            ('30000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', CURRENT_DATE, 'consumption', 1, 1, 'US1');
        RAISE EXCEPTION 'malformed currency was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        UPDATE public.energy_reading SET total_cost = 11
         WHERE id = '30000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'historic cost change without currency was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    UPDATE public.energy_reading SET activity_type = 'irrigation'
     WHERE id = '30000000-0000-0000-0000-000000000001';
END;
$$;
"""


def check_service_queries(port: int, password: str) -> None:
    location_id = "10000000-0000-0000-0000-000000000001"
    source_id = "20000000-0000-0000-0000-000000000001"
    conn = psycopg2.connect(
        host="127.0.0.1", port=port, dbname="postgres", user="postgres",
        password=password, connect_timeout=5,
    )
    try:
        zero_rate = record_reading(
            conn, source_id, date.today(),
            "consumption", 10, cost_per_kwh=0, cost_currency_code="usd",
        )
        if zero_rate["total_cost"] != 0 or zero_rate["cost_currency_code"] != "USD":
            raise AssertionError("legacy writer did not preserve a classified zero-rate cost")

        consumption = get_consumption(conn, location_id, days=0)
        if consumption["total_cost"] is not None or consumption["cost_currency_code"] is not None:
            raise AssertionError("mixed currency or unclassified history was exposed as a total")
        if consumption["unclassified_cost_readings"] != 1:
            raise AssertionError("legacy unclassified cost was not counted")
        by_currency = {
            row["cost_currency_code"]: row for row in consumption["costs_by_currency"]
        }
        if by_currency.get("USD", {}).get("total_cost") != 15.0:
            raise AssertionError("USD consumption total is wrong")
        if by_currency.get("DOP", {}).get("total_cost") != 60.0:
            raise AssertionError("DOP consumption total is wrong")

        analysis = get_cost_analysis(conn, location_id, days=30)
        if analysis["total_cost"] is not None or analysis["cost_currency_code"] is not None:
            raise AssertionError("cost analysis exposed a mixed/unclassified total")
        if analysis["unclassified_cost_readings"] != 1:
            raise AssertionError("cost analysis did not count unclassified history")
        analyzed = {row["cost_currency_code"]: row for row in analysis["costs_by_currency"]}
        if analyzed.get("USD", {}).get("total_cost") != 15.0:
            raise AssertionError("USD cost analysis total is wrong")
        if analyzed.get("DOP", {}).get("total_cost") != 60.0:
            raise AssertionError("DOP cost analysis total is wrong")

        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE energy_reading SET total_cost = 11, cost_currency_code = 'USD' WHERE id = %s",
                ("30000000-0000-0000-0000-000000000001",),
            )
            cur.execute(
                "SELECT total_cost, cost_currency_code FROM energy_reading WHERE id = %s",
                ("30000000-0000-0000-0000-000000000001",),
            )
            if cur.fetchone() != (11, "USD"):
                raise AssertionError("reviewed historic-cost classification did not succeed")
        conn.rollback()
    finally:
        conn.close()


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-energy-currency-{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(24)
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "fresh disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "assertions": [
            "migration applies and replays transactionally while preserving the energy view column contract",
            "historic values remain unclassified and are not assigned an inferred currency",
            "currency-specific totals remain separate for USD and DOP",
            "new cost values and changed historical costs require a currency",
            "unrelated historical-row edits remain possible",
            "malformed currency codes are rejected",
            "real legacy service writer and summary SQL execute against the migrated schema",
            "service summaries preserve currency totals and withhold mixed/unclassified totals",
            "a reviewed historic currency classification is accepted without being persisted by the checker",
        ],
    }
    started = False
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "--publish", "127.0.0.1::5432", "--env", f"POSTGRES_PASSWORD={password}", IMAGE])
        started = True
        wait_ready(docker, container)
        mapping = json.loads(run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container]))
        port = int(mapping["5432/tcp"][0]["HostPort"])
        psql(docker, container, FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, ACCEPTANCE)
        check_service_queries(port, password)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(evidence["assertions"])
        print("PASS: migration 604 apply/replay, schema guards, and energy service queries")
        return_code = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return_code = 1
    finally:
        if started:
            subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
