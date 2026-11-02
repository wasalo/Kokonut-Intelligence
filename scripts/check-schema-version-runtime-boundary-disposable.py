#!/usr/bin/env python3
"""Verify migration 709 preserves schema-version reads and maintenance writes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/709_runtime_schema_version_read_only.sql"
IMAGE = os.environ.get(
    "SCHEMA_VERSION_RUNTIME_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:4])} …\n{details}"
        )
    return result


def sql(container: str, statement: str, *, check: bool = True):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-A", "-t",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
        check=check,
    )


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
CREATE ROLE kokonut_maintenance_probe NOLOGIN;
CREATE TABLE public.schema_version (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO public.schema_version (version, description, applied_by)
VALUES ('708', 'prior schema', 'maintenance');
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.schema_version
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT INSERT (version), UPDATE (description), REFERENCES (version)
    ON TABLE public.schema_version TO kokonut_runtime;
"""


ASSERTIONS = r"""
DO $$
DECLARE
    privilege TEXT;
BEGIN
    IF NOT has_table_privilege('kokonut_runtime', 'public.schema_version', 'SELECT') THEN
        RAISE EXCEPTION 'runtime SELECT was not preserved';
    END IF;
    FOREACH privilege IN ARRAY ARRAY[
        'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
    ] LOOP
        IF has_table_privilege('kokonut_runtime', 'public.schema_version', privilege) THEN
            RAISE EXCEPTION 'runtime retains table privilege %', privilege;
        END IF;
    END LOOP;
    IF has_column_privilege(
        'kokonut_runtime', 'public.schema_version', 'version', 'INSERT'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.schema_version', 'description', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.schema_version', 'version', 'REFERENCES'
    ) THEN
        RAISE EXCEPTION 'runtime retains a residual column write privilege';
    END IF;
END;
$$;

SET ROLE kokonut_directus_runtime;
INSERT INTO public.schema_version (version, description, applied_by)
VALUES ('directus-probe', 'preserved directus write', 'directus');
UPDATE public.schema_version SET description = 'updated by directus'
 WHERE version = 'directus-probe';
DELETE FROM public.schema_version WHERE version = 'directus-probe';
RESET ROLE;

SET ROLE kokonut_maintenance_probe;
INSERT INTO public.schema_version (version, description, applied_by)
VALUES ('maintenance-probe', 'preserved maintenance write', 'maintenance');
UPDATE public.schema_version SET description = 'updated by maintenance'
 WHERE version = 'maintenance-probe';
DELETE FROM public.schema_version WHERE version = 'maintenance-probe';
RESET ROLE;

DO $$
BEGIN
    IF NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.schema_version', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.schema_version', 'UPDATE'
    ) OR NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.schema_version', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'migration changed Directus table write grants';
    END IF;
    IF NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.schema_version', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.schema_version', 'UPDATE'
    ) OR NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.schema_version', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'migration changed maintenance table write grants';
    END IF;
END;
$$;
SELECT 'migration 709 ACL assertions passed';
"""


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for disposable PostgreSQL checks")
    container = f"kokonut-schema-version-{uuid.uuid4().hex[:12]}"
    started = False
    try:
        run(
            [
                docker, "run", "--pull=never", "--detach", "--rm", "--name", container,
                "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
            ]
        )
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            probe = run(
                [docker, "exec", container, "pg_isready", "-U", "postgres"],
                check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        sql(container, FIXTURE)
        migration_sql = MIGRATION.read_text()
        sql(container, migration_sql)
        sql(container, migration_sql)
        result = sql(container, ASSERTIONS)
        print(json.dumps({
            "ok": True,
            "migration": MIGRATION.name,
            "migration_replay": "passed",
            "runtime_select": "preserved",
            "runtime_table_and_column_writes": "denied",
            "directus_and_maintenance_writes": "preserved",
            "network": "none",
            "host_ports_published": False,
            "container_cleaned_up": True,
            "postgres_output": result.stdout.strip(),
        }, indent=2))
        return 0
    finally:
        if started:
            run([docker, "rm", "--force", container], check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"schema_version disposable check failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
