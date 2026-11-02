#!/usr/bin/env python3
"""Verify migration 687 and proposal ordering on disposable PostgreSQL 16."""

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
MIGRATION_246 = ROOT / "schemas/postgres/246_governance_proposals.sql"
MIGRATION_687 = ROOT / "schemas/postgres/687_governance_proposal_lineage_created_at.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-29-recovery/governance-proposal-created-at-disposable.json"

FIXTURE = r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE public.governance_circle (
    id uuid PRIMARY KEY,
    circle_key text NOT NULL UNIQUE
);
CREATE TABLE public.governance_tension (id uuid PRIMARY KEY);
CREATE TABLE public.party (
    id uuid PRIMARY KEY,
    display_name text NOT NULL,
    party_type text NOT NULL
);
CREATE TABLE public.governance_role (
    id uuid PRIMARY KEY,
    role_key text NOT NULL
);
CREATE TABLE public.work_item (id uuid PRIMARY KEY);
CREATE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;
"""

EXPECTED_COLUMNS = [
    "proposal_id",
    "proposal_key",
    "circle_id",
    "circle_key",
    "proposal_type",
    "title",
    "status",
    "tension_id",
    "proposed_by_party_id",
    "proposer_name",
    "proposed_by_role_id",
    "proposer_role_key",
    "harm_review_status",
    "minority_review_status",
    "approved_by_party_id",
    "approver_name",
    "approved_at",
    "implementation_work_item_id",
    "review_due_at",
    "objection_count",
    "open_objection_count",
    "open_material_objection_count",
    "review_count",
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
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
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
    container = f"kokonut-proposal-created-at-{uuid.uuid4().hex[:8]}"
    password = secrets.token_urlsafe(24)
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION_687.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "assertions": [
            "migration 687 preserves migration 246 columns and appends created_at",
            "the previous missing-column ordering failure is demonstrated before migration 687",
            "migration 687 applies and replays transactionally",
            "the real list_proposals service query returns proposals in created_at order",
            "circle and status filters remain compatible with the explicit projection",
        ],
    }
    try:
        run(
            [
                docker,
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-p",
                "127.0.0.1::5432",
                "postgres:16-alpine",
            ]
        )
        wait_ready(docker, container)
        psql(docker, container, FIXTURE)
        psql(docker, container, MIGRATION_246.read_text(encoding="utf-8"))

        before = run(
            [
                docker,
                "exec",
                container,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-c",
                "SELECT proposal_id FROM public.v_governance_proposal_lineage ORDER BY created_at",
            ],
            check=False,
        )
        if before.returncode == 0 or 'column "created_at" does not exist' not in before.stderr:
            raise AssertionError("expected migration-246 view to lack created_at before the forward migration")

        migration_sql = MIGRATION_687.read_text(encoding="utf-8")
        psql(docker, container, migration_sql)
        psql(docker, container, migration_sql)

        mapping = run([docker, "port", container, "5432/tcp"])
        port = int(mapping.stdout.strip().rsplit(":", 1)[1])
        connection = psycopg2.connect(
            host="127.0.0.1",
            port=port,
            dbname="postgres",
            user="postgres",
            password=password,
            connect_timeout=10,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'v_governance_proposal_lineage' "
                    "ORDER BY ordinal_position"
                )
                columns = [row[0] for row in cursor.fetchall()]
                if columns != EXPECTED_COLUMNS:
                    raise AssertionError(f"proposal view columns differ: {columns!r}")

                circle_id = uuid.uuid4()
                cursor.execute(
                    "INSERT INTO public.governance_circle (id, circle_key) VALUES (%s, %s)",
                    (str(circle_id), "synthetic-circle"),
                )
                cursor.executemany(
                    "INSERT INTO public.governance_proposal "
                    "(proposal_key, circle_id, proposal_type, title, purpose, proposed_state, status, created_at) "
                    "VALUES (%s, %s, 'change_policy', %s, 'synthetic purpose', 'synthetic state', 'draft', %s)",
                    [
                        ("synthetic-newer", str(circle_id), "Newer proposal", "2026-02-01T00:00:00+00:00"),
                        ("synthetic-older", str(circle_id), "Older proposal", "2026-01-01T00:00:00+00:00"),
                    ],
                )
            connection.commit()

            from services.analytics.governance_proposals import list_proposals

            proposals = list_proposals(connection, circle_id=str(circle_id), status="draft")
            proposal_keys = [proposal["proposal_key"] for proposal in proposals]
            if proposal_keys != ["synthetic-older", "synthetic-newer"]:
                raise AssertionError(f"list_proposals returned unexpected order: {proposal_keys!r}")
            if any("created_at" not in proposal for proposal in proposals):
                raise AssertionError("the explicit proposal projection omitted created_at")
            evidence["view_columns"] = columns
            evidence["service_order"] = proposal_keys
            evidence["service_result_count"] = len(proposals)
        finally:
            connection.close()

        evidence["result"] = "passed"
        evidence["assertions_passed"] = 5
        print("PASS: migration 687 applies/replays; proposal view and service order verified on disposable PostgreSQL 16")
        return_code = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return_code = 1
    finally:
        run([docker, "rm", "--force", container], check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
