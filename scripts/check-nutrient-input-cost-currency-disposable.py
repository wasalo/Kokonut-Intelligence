#!/usr/bin/env python3
"""Exercise migration 601 and currency-safe nutrient cost summaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/601_nutrient_input_cost_currency.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-23-recovery/nutrient-input-cost-currency-disposable.json"
IMAGE = "postgis/postgis:16-3.4"


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip().splitlines()
        summary = " | ".join(line[:180] for line in details[-8:]) or "no command output"
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]} {command[1]}: {summary}"
        )
    return result.stdout.strip()


def wait_ready(container: str, docker: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL 16 did not become ready")


def psql(docker: str, container: str, sql: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )


FIXTURE = r"""
CREATE TABLE public.nutrient_budget (
    id uuid PRIMARY KEY, location_id uuid NOT NULL, season text NOT NULL, crop_name text
);
CREATE TABLE public.nutrient_input (
    id uuid PRIMARY KEY, budget_id uuid NOT NULL REFERENCES public.nutrient_budget(id),
    input_date date NOT NULL, input_type text NOT NULL, product_name text,
    nitrogen_kg numeric(10,2), phosphorus_kg numeric(10,2), potassium_kg numeric(10,2),
    application_rate numeric(10,2), rate_unit text, cost numeric(10,2),
    notes text, status text NOT NULL
);
CREATE VIEW public.v_nutrient_input_summary AS
SELECT ni.budget_id, nb.location_id, nb.season, nb.crop_name, ni.input_type,
       COUNT(*) AS event_count, SUM(ni.nitrogen_kg) AS total_nitrogen_kg,
       SUM(ni.phosphorus_kg) AS total_phosphorus_kg,
       SUM(ni.potassium_kg) AS total_potassium_kg, SUM(ni.cost) AS total_cost,
       AVG(ni.application_rate) AS avg_application_rate, ni.rate_unit
  FROM public.nutrient_input AS ni
  JOIN public.nutrient_budget AS nb ON nb.id = ni.budget_id
 WHERE ni.status IN ('recorded', 'verified')
 GROUP BY ni.budget_id, nb.location_id, nb.season, nb.crop_name,
          ni.input_type, ni.rate_unit;

INSERT INTO public.nutrient_budget VALUES
    ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '2026S1', 'maize');
-- A pre-migration amount has no currency and must never be inferred as USD.
INSERT INTO public.nutrient_input
    (id, budget_id, input_date, input_type, nitrogen_kg, cost, status)
VALUES
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '2026-01-01', 'fertilizer', 1, 9.50, 'recorded');
"""


ACCEPTANCE = r"""
INSERT INTO public.nutrient_input
    (id, budget_id, input_date, input_type, nitrogen_kg, cost, cost_currency_code, status)
VALUES
    ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '2026-01-02', 'fertilizer', 2, 12.00, 'USD', 'recorded'),
    ('20000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', '2026-01-03', 'fertilizer', 3, 300.00, 'DOP', 'verified'),
    ('20000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', '2026-01-04', 'fertilizer', 4, NULL, NULL, 'recorded');

DO $$
DECLARE
    amount numeric;
    unknown_count bigint;
    status text;
BEGIN
    SELECT total_cost INTO amount
      FROM public.v_nutrient_input_summary
     WHERE input_type = 'fertilizer' AND cost_currency_code = 'USD';
    IF amount IS DISTINCT FROM 12.00::numeric THEN
        RAISE EXCEPTION 'USD cost total is wrong: %', amount;
    END IF;

    SELECT total_cost INTO amount
      FROM public.v_nutrient_input_summary
     WHERE input_type = 'fertilizer' AND cost_currency_code = 'DOP';
    IF amount IS DISTINCT FROM 300.00::numeric THEN
        RAISE EXCEPTION 'DOP cost total is wrong: %', amount;
    END IF;

    SELECT total_cost, unclassified_cost_count
      INTO amount, unknown_count
      FROM public.v_nutrient_input_summary
     WHERE input_type = 'fertilizer' AND cost_currency_code IS NULL;
    IF amount IS NOT NULL OR unknown_count <> 1 THEN
        RAISE EXCEPTION 'unclassified historical amount was exposed or not counted';
    END IF;

    SELECT cost_currency_code INTO status
      FROM public.nutrient_input
     WHERE id = '20000000-0000-0000-0000-000000000001';
    IF status IS NOT NULL THEN
        RAISE EXCEPTION 'migration guessed a historical currency';
    END IF;

    BEGIN
        INSERT INTO public.nutrient_input
            (id, budget_id, input_date, input_type, cost, cost_currency_code, status)
        VALUES
            ('20000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', '2026-01-05', 'fertilizer', 1, 'US1', 'recorded');
        RAISE EXCEPTION 'malformed currency code was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    BEGIN
        INSERT INTO public.nutrient_input
            (id, budget_id, input_date, input_type, cost, status)
        VALUES
            ('20000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', '2026-01-06', 'fertilizer', 1, 'recorded');
        RAISE EXCEPTION 'new cost without currency was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    UPDATE public.nutrient_input
       SET notes = 'legacy annotation'
     WHERE id = '20000000-0000-0000-0000-000000000001';

    BEGIN
        UPDATE public.nutrient_input
           SET cost = 9.75
         WHERE id = '20000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'legacy cost changed without currency';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-nutrient-currency-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "fresh disposable PostgreSQL 16/PostGIS container",
        "candidate_or_legacy_modified": False,
        "assertions": [
            "migration 601 applies and replays transactionally",
            "historical cost values remain unclassified instead of defaulting to USD",
            "currency-qualified cost totals remain separated for USD and DOP",
            "unclassified cost amounts are excluded from totals and counted",
            "malformed currency codes are rejected by the database constraint",
            "new/changed cost amounts require currency while unrelated legacy edits remain possible",
        ],
    }
    try:
        run([docker, "run", "--detach", "--rm", "--network", "none", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", IMAGE])
        wait_ready(container, docker)
        psql(docker, container, FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(evidence["assertions"])
        print("PASS: migration 601 applies/replays and all six disposable PostgreSQL assertions passed")
        return_code = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return_code = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
