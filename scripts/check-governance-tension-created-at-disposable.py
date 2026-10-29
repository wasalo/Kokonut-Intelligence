#!/usr/bin/env python3
"""Verify migration 688 and tension ordering on disposable PostgreSQL 16."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATION_244 = ROOT / "schemas/postgres/244_governance_tensions.sql"
MIGRATION_688 = ROOT / "schemas/postgres/688_governance_tension_health_created_at.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-29-recovery/governance-tension-created-at-disposable.json"

FIXTURE = r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE public.governance_circle (
    id uuid PRIMARY KEY,
    circle_key text NOT NULL UNIQUE,
    name text NOT NULL
);
CREATE TABLE public.party (id uuid PRIMARY KEY, display_name text NOT NULL);
CREATE TABLE public.stakeholder_interest (id uuid PRIMARY KEY);
CREATE TABLE public.governance_role (id uuid PRIMARY KEY, role_key text NOT NULL);
CREATE TABLE public.work_item (id uuid PRIMARY KEY);
CREATE TABLE public.stakeholder_decision (id uuid PRIMARY KEY);
CREATE TABLE public.stakeholder_grievance_case (id uuid PRIMARY KEY);
CREATE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;
"""

EXPECTED_COLUMNS = [
    "tension_id",
    "tension_key",
    "title",
    "description",
    "tension_type",
    "severity",
    "urgency",
    "circle_id",
    "circle_key",
    "circle_name",
    "scope_type",
    "scope_id",
    "status",
    "reported_by_party_id",
    "reported_by_name",
    "affected_party_id",
    "affected_party_name",
    "owner_role_id",
    "owner_role_key",
    "owner_party_id",
    "owner_party_name",
    "work_item_id",
    "decision_id",
    "grievance_id",
    "review_due_at",
    "deferred_until",
    "link_count",
    "is_overdue",
    "created_at",
]


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"command failed ({result.returncode}): {detail}")
    return result


def psql(docker: str, container: str, sql: str):
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=sql,
    )


def wait_ready(docker: str, container: str):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        result = run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL 16 did not become ready")


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-tension-created-at-{uuid.uuid4().hex[:8]}"
    password = secrets.token_urlsafe(24)
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_688.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "assertions": [
            "migration 244's existing view lacks created_at and its list ordering fails before migration 688",
            "migration 688 preserves all existing view fields and appends created_at",
            "migration 688 applies and replays transactionally",
            "the real list_tensions service query preserves circle/status filters and severity/urgency/time ordering",
            "the real get_tension service query returns created_at with its existing link collection",
        ],
    }
    try:
        run(
            [docker, "run", "--detach", "--rm", "--name", container, "-e", f"POSTGRES_PASSWORD={password}", "-p", "127.0.0.1::5432", "postgres:16-alpine"]
        )
        wait_ready(docker, container)
        psql(docker, container, FIXTURE)
        psql(docker, container, MIGRATION_244.read_text(encoding="utf-8"))

        before = run(
            [docker, "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-c", "SELECT tension_id FROM public.v_governance_tension_health ORDER BY created_at"],
            check=False,
        )
        if before.returncode == 0 or 'column "created_at" does not exist' not in before.stderr:
            raise AssertionError("expected migration-244 view to lack created_at before the forward migration")

        migration_sql = MIGRATION_688.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)

        mapping = run([docker, "port", container, "5432/tcp"])
        port = int(mapping.stdout.strip().rsplit(":", 1)[1])
        connection = psycopg2.connect(
            host="127.0.0.1", port=port, dbname="postgres", user="postgres", password=password, connect_timeout=10
        )
        try:
            circle_id = uuid.uuid4()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'v_governance_tension_health' "
                    "ORDER BY ordinal_position"
                )
                columns = [row[0] for row in cursor.fetchall()]
                if columns != EXPECTED_COLUMNS:
                    raise AssertionError(f"tension view columns differ: {columns!r}")

                cursor.execute(
                    "INSERT INTO public.governance_circle (id, circle_key, name) VALUES (%s, %s, %s)",
                    (str(circle_id), "synthetic-circle", "Synthetic Circle"),
                )
                cursor.executemany(
                    "INSERT INTO public.governance_tension "
                    "(tension_key, title, description, tension_type, severity, urgency, circle_id, status, created_at) "
                    "VALUES (%s, %s, 'Synthetic case', 'evidence_gap', %s, %s, %s, 'draft', %s)",
                    [
                        ("synthetic-newer", "Newer tension", 4, 3, str(circle_id), "2026-02-01T00:00:00+00:00"),
                        ("synthetic-older", "Older tension", 4, 3, str(circle_id), "2026-01-01T00:00:00+00:00"),
                        ("synthetic-lower", "Lower severity", 3, 5, str(circle_id), "2025-12-01T00:00:00+00:00"),
                    ],
                )
            connection.commit()

            from services.analytics.governance_tensions import get_tension, list_tensions

            tensions = list_tensions(connection, circle_id=str(circle_id), status="draft")
            keys = [tension["tension_key"] for tension in tensions]
            if keys != ["synthetic-older", "synthetic-newer", "synthetic-lower"]:
                raise AssertionError(f"list_tensions returned unexpected order: {keys!r}")
            if any("created_at" not in tension for tension in tensions):
                raise AssertionError("list_tensions omitted created_at")

            older_id = tensions[0]["tension_id"]
            detail = get_tension(connection, older_id)
            if not detail or detail["tension_key"] != "synthetic-older" or "created_at" not in detail or detail["links"] != []:
                raise AssertionError("get_tension did not preserve detail and links with created_at")

            evidence["view_columns"] = columns
            evidence["service_order"] = keys
            evidence["service_detail"] = {"tension_key": detail["tension_key"], "link_count": len(detail["links"])}
        finally:
            connection.close()

        evidence["result"] = "passed"
        evidence["assertions_passed"] = 5
        print("PASS: migration 688 applies/replays; tension view and service order verified on disposable PostgreSQL 16")
        return 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        run([docker, "rm", "--force", container], check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
