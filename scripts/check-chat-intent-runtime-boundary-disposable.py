#!/usr/bin/env python3
"""Apply/replay migration 717 and verify isolated chat-intent ACL behavior."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/717_runtime_chat_intent_read_only.sql"
IMAGE = os.environ.get(
    "CHAT_INTENT_RUNTIME_TEST_IMAGE",
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
CREATE TABLE public.chat_intent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    examples JSONB DEFAULT '[]',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO public.chat_intent (name, description)
VALUES ('get_yield', 'synthetic seeded intent');
GRANT USAGE ON SCHEMA public
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.chat_intent
    TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance_probe;
GRANT INSERT (description), UPDATE (description), REFERENCES (id)
    ON TABLE public.chat_intent TO kokonut_runtime;
"""


ASSERTIONS = r"""
SET ROLE kokonut_runtime;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.chat_intent WHERE status = 'active') <> 1 THEN
        RAISE EXCEPTION 'runtime active-intent read was not preserved';
    END IF;
END;
$$;
RESET ROLE;

DO $$
DECLARE
    privilege TEXT;
BEGIN
    IF NOT has_table_privilege('kokonut_runtime', 'public.chat_intent', 'SELECT') THEN
        RAISE EXCEPTION 'runtime SELECT privilege was not preserved';
    END IF;
    FOREACH privilege IN ARRAY ARRAY[
        'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
    ] LOOP
        IF has_table_privilege('kokonut_runtime', 'public.chat_intent', privilege) THEN
            RAISE EXCEPTION 'runtime retains table privilege %', privilege;
        END IF;
    END LOOP;
    IF has_column_privilege(
        'kokonut_runtime', 'public.chat_intent', 'description', 'INSERT'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.chat_intent', 'description', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.chat_intent', 'id', 'REFERENCES'
    ) THEN
        RAISE EXCEPTION 'runtime retains residual column write privileges';
    END IF;
END;
$$;

SET ROLE kokonut_runtime;
DO $$
BEGIN
    BEGIN
        INSERT INTO public.chat_intent (name) VALUES ('runtime_insert_probe');
        RAISE EXCEPTION 'runtime INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    BEGIN
        UPDATE public.chat_intent SET description = 'runtime update probe';
        RAISE EXCEPTION 'runtime UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    BEGIN
        DELETE FROM public.chat_intent;
        RAISE EXCEPTION 'runtime DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;
RESET ROLE;

SET ROLE kokonut_directus_runtime;
INSERT INTO public.chat_intent (name, description)
VALUES ('directus_probe', 'before');
UPDATE public.chat_intent SET description = 'updated'
 WHERE name = 'directus_probe';
DELETE FROM public.chat_intent WHERE name = 'directus_probe';
RESET ROLE;

SET ROLE kokonut_maintenance_probe;
INSERT INTO public.chat_intent (name, description)
VALUES ('get_yield', 'seed upsert')
ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.chat_intent', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.chat_intent', 'UPDATE'
    ) OR NOT has_table_privilege(
        'kokonut_directus_runtime', 'public.chat_intent', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'migration changed Directus mutation grants';
    END IF;
    IF NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.chat_intent', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.chat_intent', 'UPDATE'
    ) OR NOT has_table_privilege(
        'kokonut_maintenance_probe', 'public.chat_intent', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'migration changed maintenance mutation grants';
    END IF;
    IF (SELECT description FROM public.chat_intent WHERE name = 'get_yield')
        <> 'seed upsert' THEN
        RAISE EXCEPTION 'maintenance seed upsert path was not preserved';
    END IF;
END;
$$;
SELECT 'migration 717 ACL assertions passed';
"""


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for disposable PostgreSQL checks")
    container = f"kokonut-chat-intent-{uuid.uuid4().hex[:12]}"
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
            "directus_writes": "preserved",
            "maintenance_seed_upsert": "preserved",
            "external_consumer_gate": (
                "runtime-login SQL writers are unconfirmed; verify before candidate/production rollout"
            ),
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
        print(f"chat_intent runtime boundary check failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
