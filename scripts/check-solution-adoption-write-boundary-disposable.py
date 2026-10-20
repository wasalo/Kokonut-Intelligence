#!/usr/bin/env python3
"""Check migration 514 revokes shared-role adoption readiness/configuration writes."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/514_location_solution_adoption_write_boundary.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-20-recovery/cap-035-adoption-write-boundary-disposable.json"

PREPARE = r"""
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;

CREATE TABLE public.solution_adopter_readiness (
    id UUID PRIMARY KEY,
    solution_id UUID NOT NULL,
    adopter_scope_type TEXT NOT NULL,
    adopter_scope_id UUID NOT NULL,
    current_level NUMERIC NOT NULL DEFAULT 0,
    required_level NUMERIC NOT NULL,
    gap NUMERIC GENERATED ALWAYS AS (required_level - current_level) STORED,
    remediation_plan TEXT,
    readiness_status TEXT NOT NULL DEFAULT 'not_ready',
    assessed_by_party_id UUID,
    assessed_at TIMESTAMPTZ
);
CREATE TABLE public.solution_configuration (
    id UUID PRIMARY KEY,
    solution_id UUID NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id UUID NOT NULL,
    version INTEGER NOT NULL,
    invariant_components JSONB NOT NULL DEFAULT '{}'::JSONB,
    configurable_components JSONB NOT NULL DEFAULT '{}'::JSONB,
    prohibited_components JSONB NOT NULL DEFAULT '{}'::JSONB,
    local_assumptions JSONB NOT NULL DEFAULT '{}'::JSONB,
    adaptation_owner_party_id UUID,
    comparability_class TEXT NOT NULL DEFAULT 'comparable',
    evidence_impact TEXT,
    approval_status TEXT NOT NULL DEFAULT 'draft',
    approved_by_party_id UUID,
    approved_at TIMESTAMPTZ
);

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON public.solution_adopter_readiness, public.solution_configuration
    TO PUBLIC, kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (current_level), UPDATE (readiness_status)
    ON public.solution_adopter_readiness TO kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (approval_status), UPDATE (approved_by_party_id)
    ON public.solution_configuration TO kokonut_runtime, kokonut_directus_runtime;
"""

ACCEPTANCE = r"""
DO $$
DECLARE role_name TEXT; table_name TEXT; privilege_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        FOREACH table_name IN ARRAY ARRAY[
            'public.solution_adopter_readiness', 'public.solution_configuration'
        ] LOOP
            IF NOT pg_catalog.has_table_privilege(role_name, table_name, 'SELECT') THEN
                RAISE EXCEPTION '% lost the read boundary for %', role_name, table_name;
            END IF;
            FOREACH privilege_name IN ARRAY ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'] LOOP
                IF pg_catalog.has_table_privilege(role_name, table_name, privilege_name) THEN
                    RAISE EXCEPTION '% retains % on %', role_name, privilege_name, table_name;
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;
    IF pg_catalog.has_column_privilege(
        'kokonut_runtime', 'public.solution_adopter_readiness', 'current_level', 'INSERT'
    ) OR pg_catalog.has_column_privilege(
        'kokonut_runtime', 'public.solution_adopter_readiness', 'readiness_status', 'UPDATE'
    ) OR pg_catalog.has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_configuration', 'approval_status', 'INSERT'
    ) OR pg_catalog.has_column_privilege(
        'kokonut_directus_runtime', 'public.solution_configuration', 'approved_by_party_id', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'column-level runtime/Directus write grant remains';
    END IF;
END;
$$;
"""


def psql(docker: str, container: str, sql: str) -> str:
    result = subprocess.run(
        [docker, "exec", "-i", container, "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "pg_isready", "-U", "postgres"],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-adoption-boundary-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migration 514 applies and replays idempotently",
            "runtime keeps SELECT but loses table-level readiness/configuration writes",
            "Directus keeps SELECT but loses table-level readiness/configuration writes",
            "column-level INSERT and UPDATE grants are revoked",
            "explicit PUBLIC DML grants no longer confer effective write access",
        ],
    }
    try:
        subprocess.run(
            [docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"],
            text=True,
            capture_output=True,
            check=True,
        )
        wait_ready(docker, container)
        psql(docker, container, PREPARE)
        migration_text = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, migration_text)
        psql(docker, container, migration_text)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 5
        print("PASS: migration 514 replay and runtime/Directus adoption write-boundary checks passed")
        return 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
