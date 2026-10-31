#!/usr/bin/env python3
"""Replay migration 686 against synthetic PostgreSQL revenue-stream rows."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/686_location_scoped_revenue_stream_cycle_join.sql"
EVIDENCE = (
    ROOT
    / "docs/refactor/builds/2026-10-29-recovery/revenue-stream-location-join-disposable.json"
)
IMAGE = os.environ.get("REVENUE_STREAM_JOIN_TEST_IMAGE", "postgres:16")

LOCATION_A = "11111111-1111-4111-8111-111111111111"
LOCATION_B = "22222222-2222-4222-8222-222222222222"
CYCLE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CYCLE_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REVENUE_LOCAL = "33333333-3333-4333-8333-333333333333"
REVENUE_FOREIGN = "44444444-4444-4444-8444-444444444444"
REVENUE_UNLINKED = "55555555-5555-4555-8555-555555555555"


def docker(args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        raise RuntimeError(f"Docker operation failed: {args[1]}")
    return result.stdout.strip()


def wait_ready(binary: str, container: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [binary, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def psql(binary: str, container: str, sql: str) -> str:
    result = subprocess.run(
        [
            binary,
            "exec",
            "-i",
            container,
            "psql",
            "--no-psqlrc",
            "--quiet",
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "postgres",
            "--dbname",
            "postgres",
            "--file",
            "-",
        ],
        input=sql.rstrip() + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("disposable PostgreSQL rejected the synthetic SQL")
    return result.stdout.strip()


def snapshot(binary: str, container: str) -> dict[str, object]:
    query = f"""
        SELECT pg_catalog.json_build_object(
            'row_count', pg_catalog.count(*),
            'gross_revenue', pg_catalog.sum(gross_revenue),
            'net_contribution', pg_catalog.sum(net_contribution),
            'local_cycle_name', pg_catalog.max(cycle_name)
                FILTER (WHERE id = '{REVENUE_LOCAL}'::uuid),
            'foreign_row_present', pg_catalog.bool_or(id = '{REVENUE_FOREIGN}'::uuid),
            'foreign_cycle_name', pg_catalog.max(cycle_name)
                FILTER (WHERE id = '{REVENUE_FOREIGN}'::uuid),
            'unlinked_cycle_name', pg_catalog.max(cycle_name)
                FILTER (WHERE id = '{REVENUE_UNLINKED}'::uuid)
        )::text
        FROM public.v_public_revenue_streams
        WHERE location_id = '{LOCATION_A}'::uuid;
    """
    output = docker(
        [
            binary,
            "exec",
            container,
            "psql",
            "--no-psqlrc",
            "--quiet",
            "--tuples-only",
            "--no-align",
            "--username",
            "postgres",
            "--dbname",
            "postgres",
            "--command",
            query,
        ]
    )
    return json.loads(output)


def assert_snapshot(value: dict[str, object], *, migrated: bool) -> None:
    expected = {
        "row_count": 3,
        "gross_revenue": 175,
        "net_contribution": 120,
        "local_cycle_name": "Local crop cycle",
        "foreign_row_present": True,
        "unlinked_cycle_name": None,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise AssertionError(f"unexpected revenue view value for {key}")
    foreign_name = value.get("foreign_cycle_name")
    if migrated:
        if foreign_name is not None:
            raise AssertionError("migration did not hide a foreign crop-cycle label")
    elif foreign_name != "Foreign crop cycle":
        raise AssertionError("baseline fixture did not reproduce the location mismatch")


def main() -> int:
    binary = shutil.which("docker")
    if binary is None:
        raise RuntimeError("Docker CLI is unavailable")

    container = f"kokonut-revenue-view-{os.getpid()}-{secrets.token_hex(3)}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database": "disposable PostgreSQL 16",
        "network_disabled": True,
        "host_port_published": False,
        "candidate_or_legacy_modified": False,
        "provider_contacted": False,
    }
    started = False
    stage = "container_start"
    try:
        docker(
            [
                binary,
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--network",
                "none",
                "--env",
                f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
                IMAGE,
            ]
        )
        started = True
        wait_ready(binary, container)

        stage = "synthetic_schema_and_baseline_view"
        psql(
            binary,
            container,
            f"""
            CREATE TABLE public.location (
                id UUID PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE public.farm_registry_record (
                id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE public.crop_cycle (
                id UUID PRIMARY KEY, location_id UUID NOT NULL, cycle_name TEXT
            );
            CREATE TABLE public.revenue_stream_contribution (
                id UUID PRIMARY KEY,
                location_id UUID NOT NULL,
                crop_cycle_id UUID,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                stream_name TEXT NOT NULL,
                stream_category TEXT NOT NULL,
                gross_revenue NUMERIC NOT NULL,
                direct_costs NUMERIC NOT NULL,
                allocated_costs NUMERIC NOT NULL,
                net_contribution NUMERIC NOT NULL,
                contribution_pct NUMERIC NOT NULL,
                notes TEXT,
                status TEXT NOT NULL
            );

            INSERT INTO public.location (id, name, status) VALUES
                ('{LOCATION_A}'::uuid, 'Synthetic location A', 'active'),
                ('{LOCATION_B}'::uuid, 'Synthetic location B', 'active');
            INSERT INTO public.farm_registry_record (id, location_id, status) VALUES
                ('66666666-6666-4666-8666-666666666666'::uuid, '{LOCATION_A}'::uuid, 'verified'),
                ('77777777-7777-4777-8777-777777777777'::uuid, '{LOCATION_B}'::uuid, 'published');
            INSERT INTO public.crop_cycle (id, location_id, cycle_name) VALUES
                ('{CYCLE_A}'::uuid, '{LOCATION_A}'::uuid, 'Local crop cycle'),
                ('{CYCLE_B}'::uuid, '{LOCATION_B}'::uuid, 'Foreign crop cycle');
            INSERT INTO public.revenue_stream_contribution (
                id, location_id, crop_cycle_id, period_start, period_end,
                stream_name, stream_category, gross_revenue, direct_costs,
                allocated_costs, net_contribution, contribution_pct, notes, status
            ) VALUES
                ('{REVENUE_LOCAL}'::uuid, '{LOCATION_A}'::uuid, '{CYCLE_A}'::uuid,
                 DATE '2026-01-01', DATE '2026-01-31', 'Local sales', 'crop',
                 100, 10, 10, 80, 80, NULL, 'verified'),
                ('{REVENUE_FOREIGN}'::uuid, '{LOCATION_A}'::uuid, '{CYCLE_B}'::uuid,
                 DATE '2026-02-01', DATE '2026-02-28', 'Mixed sales', 'crop',
                 50, 5, 5, 40, 80, NULL, 'published'),
                ('{REVENUE_UNLINKED}'::uuid, '{LOCATION_A}'::uuid, NULL,
                 DATE '2026-03-01', DATE '2026-03-31', 'Unlinked sales', 'other',
                 25, 2, 3, 0, 0, NULL, 'verified');

            CREATE OR REPLACE VIEW public.v_public_revenue_streams AS
            SELECT rsc.id, rsc.location_id, l.name AS location_name,
                   rsc.crop_cycle_id, cc.cycle_name, rsc.period_start,
                   rsc.period_end, rsc.stream_name, rsc.stream_category,
                   rsc.gross_revenue, rsc.direct_costs, rsc.allocated_costs,
                   rsc.net_contribution, rsc.contribution_pct, rsc.notes, rsc.status
              FROM public.revenue_stream_contribution AS rsc
              JOIN public.location AS l ON l.id = rsc.location_id
              LEFT JOIN public.crop_cycle AS cc ON cc.id = rsc.crop_cycle_id
             WHERE l.status = 'active'
               AND rsc.status IN ('verified', 'published')
               AND EXISTS (
                   SELECT 1 FROM public.farm_registry_record AS fr
                    WHERE fr.location_id = l.id
                      AND fr.status IN ('verified', 'published')
               );
            """,
        )
        baseline = snapshot(binary, container)
        assert_snapshot(baseline, migrated=False)

        stage = "migration_686_apply_and_replay"
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(binary, container, migration_sql)
        first = snapshot(binary, container)
        assert_snapshot(first, migrated=True)
        psql(binary, container, migration_sql)
        replay = snapshot(binary, container)
        assert_snapshot(replay, migrated=True)

        evidence.update(
            {
                "result": "passed",
                "baseline": baseline,
                "after_apply": first,
                "after_replay": replay,
                "assertions": {
                    "baseline_exposes_mismatched_cycle_label": True,
                    "same_location_cycle_label_preserved": True,
                    "cross_location_cycle_label_null_after_migration": True,
                    "cross_location_contribution_preserved": True,
                    "unlinked_contribution_preserved": True,
                    "location_a_row_count": 3,
                    "location_a_gross_revenue": 175,
                    "location_a_net_contribution": 120,
                    "migration_replay_safe": True,
                },
                "cleanup": "pending",
            }
        )
        return 0
    except Exception as exc:
        evidence["failure_stage"] = stage
        evidence["failure_class"] = type(exc).__name__
        raise
    finally:
        if started:
            docker([binary, "stop", "--time", "5", container], check=False)
        if evidence.get("result") == "passed":
            evidence["cleanup"] = "container stopped and auto-removed"
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
