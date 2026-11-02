#!/usr/bin/env python3
"""Apply/replay migration 710 and verify isolated cache-rule ACL behavior."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/710_runtime_cache_invalidation_rule_read_only.sql"
IMAGE = os.environ.get(
    "CACHE_RULE_RUNTIME_TEST_IMAGE",
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


def psql(container: str, statement: str):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-A", "-t",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


FIXTURE = r"""
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
CREATE ROLE kokonut_maintenance_probe NOLOGIN;
CREATE TABLE public.cache_invalidation_rule (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    target_computation_type VARCHAR(100) NOT NULL,
    scope VARCHAR(50) NOT NULL DEFAULT 'location',
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO public.cache_invalidation_rule
    (id, event_type, target_computation_type, description)
VALUES
    ('71000000-0000-4000-8000-000000000001', 'sensor_reading', 'metric', 'synthetic rule');
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.cache_invalidation_rule
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT INSERT (event_type), UPDATE (description), REFERENCES (id)
    ON TABLE public.cache_invalidation_rule TO kokonut_runtime;
"""


ASSERTIONS = r"""
SET ROLE kokonut_runtime;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.cache_invalidation_rule) <> 1 THEN
        RAISE EXCEPTION 'runtime read was not preserved';
    END IF;
END;
$$;
RESET ROLE;

DO $$
DECLARE
    privilege TEXT;
BEGIN
    IF NOT has_table_privilege(
        'kokonut_runtime', 'public.cache_invalidation_rule', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'runtime SELECT privilege was not preserved';
    END IF;
    FOREACH privilege IN ARRAY ARRAY[
        'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
    ] LOOP
        IF has_table_privilege(
            'kokonut_runtime', 'public.cache_invalidation_rule', privilege
        ) THEN
            RAISE EXCEPTION 'runtime retains table privilege %', privilege;
        END IF;
    END LOOP;
    IF has_column_privilege(
        'kokonut_runtime', 'public.cache_invalidation_rule', 'event_type', 'INSERT'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.cache_invalidation_rule', 'description', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.cache_invalidation_rule', 'id', 'REFERENCES'
    ) THEN
        RAISE EXCEPTION 'runtime retains residual column write privileges';
    END IF;
END;
$$;

SET ROLE kokonut_directus_runtime;
INSERT INTO public.cache_invalidation_rule
    (id, event_type, target_computation_type, description)
VALUES ('71000000-0000-4000-8000-000000000002', 'directus_probe', 'metric', 'before');
UPDATE public.cache_invalidation_rule SET description = 'updated'
 WHERE id = '71000000-0000-4000-8000-000000000002';
DELETE FROM public.cache_invalidation_rule
 WHERE id = '71000000-0000-4000-8000-000000000002';
RESET ROLE;

SET ROLE kokonut_maintenance_probe;
INSERT INTO public.cache_invalidation_rule
    (id, event_type, target_computation_type, description)
VALUES ('71000000-0000-4000-8000-000000000003', 'maintenance_probe', 'metric', 'before');
UPDATE public.cache_invalidation_rule SET description = 'updated'
 WHERE id = '71000000-0000-4000-8000-000000000003';
DELETE FROM public.cache_invalidation_rule
 WHERE id = '71000000-0000-4000-8000-000000000003';
RESET ROLE;

DO $$
BEGIN
    IF NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.cache_invalidation_rule', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.cache_invalidation_rule', 'UPDATE'
    ) OR NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.cache_invalidation_rule', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'migration changed Directus mutation grants';
    END IF;
    IF NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.cache_invalidation_rule', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.cache_invalidation_rule', 'UPDATE'
    ) OR NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.cache_invalidation_rule', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'migration changed maintenance mutation grants';
    END IF;
END;
$$;
SELECT 'migration 710 ACL assertions passed';
"""


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for disposable PostgreSQL checks")
    container = f"kokonut-cache-rule-{uuid.uuid4().hex[:12]}"
    started = False
    try:
        run([
            docker, "run", "--pull=never", "--detach", "--rm", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ])
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = run(
                [docker, "exec", container, "pg_isready", "-U", "postgres"],
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        psql(container, FIXTURE)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        psql(container, migration_sql)
        psql(container, migration_sql)
        result = psql(container, ASSERTIONS)
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
        print(f"cache invalidation rule disposable check failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
