#!/usr/bin/env python3
"""Apply/replay migration 721 and exercise governance catalog ACLs in disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/721_runtime_governance_reference_catalogs_read_only.sql"
IMAGE = os.environ.get(
    "GOVERNANCE_CATALOG_RUNTIME_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:4])} …\n{details}"
        )
    return result


def docker_psql(container: str, statement: str, database: str = "postgres"):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-v",
            "ON_ERROR_STOP=1", "-U", "postgres", "-d", database,
        ],
        input_text=statement,
    )


SCHEMA_FIXTURE = r"""
CREATE TABLE public.data_governance_category (
    id UUID PRIMARY KEY,
    category_key VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    default_retention_days INTEGER,
    sensitivity VARCHAR(20) NOT NULL DEFAULT 'standard'
        CHECK (sensitivity IN ('low', 'standard', 'sensitive', 'restricted')),
    requires_consent BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.data_governance_scope (
    id UUID PRIMARY KEY,
    scope_key VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    default_active BOOLEAN NOT NULL DEFAULT TRUE,
    legal_reference TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO public.data_governance_category
    (id, category_key, display_name, description, default_retention_days)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'soil', 'Soil Data', 'Initial', NULL);
INSERT INTO public.data_governance_scope
    (id, scope_key, display_name, description, default_active)
VALUES
    ('00000000-0000-0000-0000-000000000002', 'collection', 'Collection', 'Initial', TRUE);
"""

RUNTIME_ROLE_CREATE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT;
"""

BOOTSTRAP_GRANTS = r"""
GRANT USAGE ON SCHEMA public TO kokonut_runtime, kokonut_directus_runtime;
GRANT ALL PRIVILEGES ON TABLE
    public.data_governance_category, public.data_governance_scope
    TO kokonut_runtime, kokonut_directus_runtime;
-- Simulate old standalone column grants that table-level REVOKE does not clear.
GRANT INSERT (category_key), UPDATE (display_name), REFERENCES (category_key)
    ON TABLE public.data_governance_category TO kokonut_runtime;
GRANT INSERT (scope_key), UPDATE (display_name), REFERENCES (scope_key)
    ON TABLE public.data_governance_scope TO kokonut_runtime;
"""

ROLE_ABSENT_ASSERTION = r"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'role-absent migration unexpectedly created kokonut_runtime';
    END IF;
END;
$$;
"""

ACL_ASSERTIONS = r"""
DO $$
DECLARE
    relation_name TEXT;
    privilege_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'data_governance_category', 'data_governance_scope'
    ] LOOP
        IF NOT has_table_privilege(
            'kokonut_runtime', 'public.' || relation_name, 'SELECT'
        ) THEN
            RAISE EXCEPTION 'runtime SELECT is missing on %', relation_name;
        END IF;
        FOREACH privilege_name IN ARRAY ARRAY[
            'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
        ] LOOP
            IF has_table_privilege(
                'kokonut_runtime', 'public.' || relation_name, privilege_name
            ) THEN
                RAISE EXCEPTION 'runtime % privilege remains on %', privilege_name, relation_name;
            END IF;
        END LOOP;

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = ('public.' || relation_name)::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            FOREACH privilege_name IN ARRAY ARRAY['INSERT', 'UPDATE', 'REFERENCES'] LOOP
                IF has_column_privilege(
                    'kokonut_runtime', 'public.' || relation_name,
                    column_name, privilege_name
                ) THEN
                    RAISE EXCEPTION 'runtime column % privilege remains on %.%',
                        privilege_name, relation_name, column_name;
                END IF;
            END LOOP;
        END LOOP;

        IF NOT has_table_privilege(
            'kokonut_directus_runtime', 'public.' || relation_name, 'SELECT'
        ) OR NOT has_table_privilege(
            'kokonut_directus_runtime', 'public.' || relation_name, 'INSERT'
        ) OR NOT has_table_privilege(
            'kokonut_directus_runtime', 'public.' || relation_name, 'UPDATE'
        ) OR NOT has_table_privilege(
            'kokonut_directus_runtime', 'public.' || relation_name, 'DELETE'
        ) THEN
            RAISE EXCEPTION 'Directus grants were changed on %', relation_name;
        END IF;
    END LOOP;
END;
$$;

SET ROLE kokonut_runtime;
DO $$
BEGIN
    IF (SELECT count(*) FROM public.data_governance_category) <> 1
       OR (SELECT count(*) FROM public.data_governance_scope) <> 1 THEN
        RAISE EXCEPTION 'runtime SELECT could not read the seeded catalogs';
    END IF;
    BEGIN
        INSERT INTO public.data_governance_category
            (id, category_key, display_name)
        VALUES ('00000000-0000-0000-0000-000000000011', 'runtime-write', 'Denied');
        RAISE EXCEPTION 'runtime INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.data_governance_scope SET display_name = 'Denied';
        RAISE EXCEPTION 'runtime UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM public.data_governance_category;
        RAISE EXCEPTION 'runtime DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;
RESET ROLE;

SET ROLE kokonut_directus_runtime;
UPDATE public.data_governance_category SET display_name = 'Directus retained write';
RESET ROLE;

-- Migration-owner/seed operations remain available, and catalog values can be
-- maintained without assigning a legal retention duration by default.
INSERT INTO public.data_governance_category
    (id, category_key, display_name, description, default_retention_days)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'soil', 'Soil Data v2', 'Updated', NULL)
ON CONFLICT (category_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    default_retention_days = EXCLUDED.default_retention_days;
INSERT INTO public.data_governance_scope
    (id, scope_key, display_name, description, default_active)
VALUES
    ('00000000-0000-0000-0000-000000000002', 'collection', 'Collection v2', 'Updated', TRUE)
ON CONFLICT (scope_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    default_active = EXCLUDED.default_active;
DO $$
BEGIN
    IF (SELECT display_name FROM public.data_governance_category
         WHERE category_key = 'soil') <> 'Soil Data v2'
       OR (SELECT default_retention_days FROM public.data_governance_category
            WHERE category_key = 'soil') IS NOT NULL
       OR (SELECT display_name FROM public.data_governance_scope
            WHERE scope_key = 'collection') <> 'Collection v2' THEN
        RAISE EXCEPTION 'seed/upsert behavior or nullable retention changed';
    END IF;
END;
$$;
"""


def main() -> None:
    if not MIGRATION.is_file():
        raise SystemExit(f"migration not found: {MIGRATION}")

    container = f"kokonut-gov-catalog-acl-{secrets.token_hex(4)}"
    run(
        [
            "docker", "run", "--detach", "--rm", "--network", "none",
            "--name", container, "-e", "POSTGRES_PASSWORD=disposable-only", IMAGE,
        ]
    )
    stage = "waiting for PostgreSQL"
    try:
        for attempt in range(60):
            ready = run(
                [
                    "docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                    "-U", "postgres", "-d", "postgres",
                ],
                check=False,
            )
            if ready.returncode == 0:
                break
            if attempt == 59:
                raise RuntimeError("disposable PostgreSQL did not become ready")
            time.sleep(1)

        stage = "creating disposable databases"
        docker_psql(
            container,
            "CREATE DATABASE gov_catalog_role_absent; CREATE DATABASE gov_catalog_role_present;",
        )
        for database in ("gov_catalog_role_absent", "gov_catalog_role_present"):
            stage = f"creating synthetic catalog fixture in {database}"
            docker_psql(container, SCHEMA_FIXTURE, database)

        migration_sql = MIGRATION.read_text(encoding="utf-8")

        # The original migration pass must tolerate a not-yet-provisioned app role.
        stage = "applying migration with kokonut_runtime absent"
        docker_psql(container, migration_sql, "gov_catalog_role_absent")
        stage = "asserting role-absent behavior"
        docker_psql(container, ROLE_ABSENT_ASSERTION, "gov_catalog_role_absent")

        # Simulate runtime role bootstrap after old migrations have already run.
        stage = "simulating runtime-role bootstrap"
        docker_psql(container, RUNTIME_ROLE_CREATE)
        for database in ("gov_catalog_role_absent", "gov_catalog_role_present"):
            stage = f"applying bootstrap grants in {database}"
            docker_psql(container, BOOTSTRAP_GRANTS, database)

        # In the role-absent DB, replay after bootstrap repairs the broad grants.
        # In the second DB, this is the normal role-present first apply.
        for database in ("gov_catalog_role_absent", "gov_catalog_role_present"):
            stage = f"applying migration after bootstrap in {database}"
            docker_psql(container, migration_sql, database)
            stage = f"replaying migration in {database}"
            docker_psql(container, migration_sql, database)
            stage = f"asserting ACL and seed behavior in {database}"
            docker_psql(container, ACL_ASSERTIONS, database)

        stage = "complete"
        print(
            json.dumps(
                {
                    "migration": MIGRATION.name,
                    "image": IMAGE,
                    "network": "none",
                    "host_ports_published": False,
                    "databases": [
                        {
                            "name": "gov_catalog_role_absent",
                            "checks": [
                                "migration_skips_absent_role_without_creating_it",
                                "bootstrap_grants_then_replay",
                                "repeat_replay",
                                "runtime_select_and_table_column_dml_denial",
                                "directus_grants_unchanged",
                                "seed_upserts_and_nullable_retention",
                            ],
                        },
                        {
                            "name": "gov_catalog_role_present",
                            "checks": [
                                "role_present_apply_and_replay",
                                "runtime_select_and_table_column_dml_denial",
                                "directus_grants_unchanged",
                                "seed_upserts_and_nullable_retention",
                            ],
                        },
                    ],
                    "result": "passed",
                },
                indent=2,
                sort_keys=True,
            )
        )
    except Exception as exc:
        inspect = run(
            ["docker", "inspect", "--format", "{{.State.Status}} {{.State.OOMKilled}} {{.State.ExitCode}}", container],
            check=False,
        )
        logs = run(["docker", "logs", container], check=False)
        diagnostics = "\n".join(
            part for part in (inspect.stdout.strip(), logs.stdout[-12000:], logs.stderr[-4000:]) if part
        )
        raise RuntimeError(f"{stage}: {exc}\nDisposable container diagnostics:\n{diagnostics}") from exc
    finally:
        run(["docker", "rm", "--force", container], check=False)


if __name__ == "__main__":
    main()
