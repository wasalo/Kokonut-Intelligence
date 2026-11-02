#!/usr/bin/env python3
"""Replay migration 725 and verify curated framework catalog ACLs in disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "schemas/postgres/725_runtime_framework_reference_catalogs_read_only.sql"
)
IMAGE = os.environ.get(
    "FRAMEWORK_CATALOG_RUNTIME_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
RELATIONS = (
    "form_of_capital",
    "sdg",
    "pillar_of_value",
    "regeneration_principle",
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
CREATE TABLE public.form_of_capital (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    capital_key VARCHAR(100) UNIQUE,
    kokonut_question TEXT,
    evidence_examples TEXT[] DEFAULT '{}',
    sort_order INTEGER,
    metadata JSONB DEFAULT '{}'
);
CREATE TABLE public.sdg (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    sdg_number INTEGER UNIQUE,
    short_name VARCHAR(255),
    evidence_maturity VARCHAR(100),
    tier VARCHAR(50),
    metadata JSONB DEFAULT '{}'
);
CREATE TABLE public.pillar_of_value (
    pillar_key VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    core_question TEXT NOT NULL,
    schema_connections TEXT[] DEFAULT '{}',
    sort_order INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE public.regeneration_principle (
    principle_key VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    evidence_examples TEXT[] DEFAULT '{}',
    sort_order INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.form_of_capital OWNER TO kokonut;
ALTER TABLE public.sdg OWNER TO kokonut;
ALTER TABLE public.pillar_of_value OWNER TO kokonut;
ALTER TABLE public.regeneration_principle OWNER TO kokonut;
INSERT INTO public.form_of_capital
    (id, capital_key, name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'natural', 'Natural Capital');
INSERT INTO public.sdg
    (id, sdg_number, name) VALUES
    ('00000000-0000-0000-0000-000000000002', 1, 'No Poverty');
INSERT INTO public.pillar_of_value
    (pillar_key, name, core_question) VALUES
    ('what', 'WHAT', 'What value is created?');
INSERT INTO public.regeneration_principle
    (principle_key, name) VALUES ('soil_protection', 'Protect soil');
"""

ROLE_CREATE = r"""
CREATE ROLE kokonut NOLOGIN;
"""

BOOTSTRAP_GRANTS = """
GRANT USAGE ON SCHEMA public TO kokonut_runtime, kokonut_directus_runtime;
GRANT ALL PRIVILEGES ON TABLE
    public.form_of_capital, public.sdg, public.pillar_of_value,
    public.regeneration_principle
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (capital_key), UPDATE (name), REFERENCES (capital_key)
    ON TABLE public.form_of_capital TO kokonut_runtime;
GRANT INSERT (sdg_number), UPDATE (name), REFERENCES (sdg_number)
    ON TABLE public.sdg TO kokonut_runtime;
GRANT INSERT (pillar_key), UPDATE (name), REFERENCES (pillar_key)
    ON TABLE public.pillar_of_value TO kokonut_runtime;
GRANT INSERT (principle_key), UPDATE (name), REFERENCES (principle_key)
    ON TABLE public.regeneration_principle TO kokonut_runtime;
"""

ASSERT_ROLE_ABSENT = r"""
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        RAISE EXCEPTION 'role-absent migration unexpectedly created kokonut_runtime';
    END IF;
END $$;
"""

ASSERTIONS = r"""
DO $$
DECLARE
    relation_name TEXT;
    privilege_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'form_of_capital', 'sdg', 'pillar_of_value', 'regeneration_principle'
    ] LOOP
        IF NOT has_table_privilege('kokonut_runtime', 'public.' || relation_name, 'SELECT') THEN
            RAISE EXCEPTION 'runtime SELECT missing on %', relation_name;
        END IF;
        FOREACH privilege_name IN ARRAY ARRAY[
            'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
        ] LOOP
            IF has_table_privilege('kokonut_runtime', 'public.' || relation_name, privilege_name) THEN
                RAISE EXCEPTION 'runtime % remains on %', privilege_name, relation_name;
            END IF;
        END LOOP;
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = ('public.' || relation_name)::REGCLASS
               AND attribute.attnum > 0 AND NOT attribute.attisdropped
        LOOP
            FOREACH privilege_name IN ARRAY ARRAY['INSERT', 'UPDATE', 'REFERENCES'] LOOP
                IF has_column_privilege(
                    'kokonut_runtime', 'public.' || relation_name,
                    column_name, privilege_name
                ) THEN
                    RAISE EXCEPTION 'runtime column % remains on %.%',
                        privilege_name, relation_name, column_name;
                END IF;
            END LOOP;
        END LOOP;
        IF NOT has_table_privilege('kokonut_directus_runtime',
                                   'public.' || relation_name, 'SELECT')
           OR NOT has_table_privilege('kokonut_directus_runtime',
                                      'public.' || relation_name, 'INSERT')
           OR NOT has_table_privilege('kokonut_directus_runtime',
                                      'public.' || relation_name, 'UPDATE')
           OR NOT has_table_privilege('kokonut_directus_runtime',
                                      'public.' || relation_name, 'DELETE') THEN
            RAISE EXCEPTION 'Directus grants changed on %', relation_name;
        END IF;
        IF NOT has_table_privilege('kokonut', 'public.' || relation_name, 'INSERT')
           OR NOT has_table_privilege('kokonut', 'public.' || relation_name, 'UPDATE')
           OR NOT has_table_privilege('kokonut', 'public.' || relation_name, 'DELETE') THEN
            RAISE EXCEPTION 'database owner maintenance rights missing on %', relation_name;
        END IF;
    END LOOP;
END $$;

SET ROLE kokonut_runtime;
DO $$ BEGIN
    IF (SELECT count(*) FROM public.form_of_capital) <> 1
       OR (SELECT count(*) FROM public.sdg) <> 1
       OR (SELECT count(*) FROM public.pillar_of_value) <> 1
       OR (SELECT count(*) FROM public.regeneration_principle) <> 1 THEN
        RAISE EXCEPTION 'runtime SELECT cannot read seeded catalogs';
    END IF;
    BEGIN
        UPDATE public.form_of_capital SET name = 'Denied';
        RAISE EXCEPTION 'runtime UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM public.sdg;
        RAISE EXCEPTION 'runtime DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO public.pillar_of_value (pillar_key, name, core_question)
        VALUES ('denied', 'Denied', 'Denied');
        RAISE EXCEPTION 'runtime INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END $$;
RESET ROLE;

SET ROLE kokonut_directus_runtime;
UPDATE public.sdg SET name = 'Directus retained write' WHERE sdg_number = 1;
RESET ROLE;

-- Curated seed DML continues to run under the database owner, not the app role.
SET ROLE kokonut;
INSERT INTO public.form_of_capital (id, capital_key, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'natural', 'Natural Capital v2')
ON CONFLICT (capital_key) DO UPDATE SET name = EXCLUDED.name;
INSERT INTO public.sdg (id, sdg_number, name)
VALUES ('00000000-0000-0000-0000-000000000002', 1, 'No Poverty v2')
ON CONFLICT (sdg_number) DO UPDATE SET name = EXCLUDED.name;
INSERT INTO public.pillar_of_value (pillar_key, name, core_question)
VALUES ('what', 'WHAT v2', 'What value is created?')
ON CONFLICT (pillar_key) DO UPDATE SET name = EXCLUDED.name;
INSERT INTO public.regeneration_principle (principle_key, name)
VALUES ('soil_protection', 'Protect soil v2')
ON CONFLICT (principle_key) DO UPDATE SET name = EXCLUDED.name;
RESET ROLE;
DO $$ BEGIN
    IF (SELECT name FROM public.form_of_capital WHERE capital_key = 'natural') <> 'Natural Capital v2'
       OR (SELECT name FROM public.sdg WHERE sdg_number = 1) <> 'No Poverty v2'
       OR (SELECT name FROM public.pillar_of_value WHERE pillar_key = 'what') <> 'WHAT v2'
       OR (SELECT name FROM public.regeneration_principle WHERE principle_key = 'soil_protection') <> 'Protect soil v2' THEN
        RAISE EXCEPTION 'owner seed upsert did not persist';
    END IF;
END $$;
"""


def main() -> None:
    if not MIGRATION.is_file():
        raise SystemExit(f"migration not found: {MIGRATION}")

    container = f"kokonut-framework-catalog-acl-{secrets.token_hex(4)}"
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

        stage = "creating disposable databases and roles"
        docker_psql(container, ROLE_CREATE)
        docker_psql(
            container,
            "CREATE DATABASE framework_catalog_role_absent; "
            "CREATE DATABASE framework_catalog_role_present;",
        )
        for database in ("framework_catalog_role_absent", "framework_catalog_role_present"):
            stage = f"creating synthetic catalog fixture in {database}"
            docker_psql(container, SCHEMA_FIXTURE, database)

        migration_sql = MIGRATION.read_text(encoding="utf-8")
        stage = "applying migration with runtime role temporarily absent"
        docker_psql(container, migration_sql, "framework_catalog_role_absent")
        docker_psql(container, ASSERT_ROLE_ABSENT, "framework_catalog_role_absent")

        stage = "creating runtime and Directus roles"
        docker_psql(
            container,
            "CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT; "
            "CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT;",
        )
        for database in ("framework_catalog_role_absent", "framework_catalog_role_present"):
            stage = f"simulating legacy compatibility grants in {database}"
            docker_psql(container, BOOTSTRAP_GRANTS, database)
            stage = f"applying migration and replaying in {database}"
            docker_psql(container, migration_sql, database)
            docker_psql(container, migration_sql, database)
            stage = f"asserting migration, ACL, seed, and read behavior in {database}"
            docker_psql(container, ASSERTIONS, database)

        stage = "complete"
        print(
            json.dumps(
                {
                    "migration": MIGRATION.name,
                    "relations": list(RELATIONS),
                    "image": IMAGE,
                    "network": "none",
                    "host_ports_published": False,
                    "databases": [
                        {
                            "name": "framework_catalog_role_absent",
                            "checks": [
                                "role-absent-migration-does-not-create-role",
                                "role-bootstrap-followed-by-revocation",
                                "migration-replay",
                                "runtime-select-and-table-column-dml-denial",
                                "Directus-grants-unchanged",
                                "database-owner-seed-upserts-retained",
                            ],
                        },
                        {
                            "name": "framework_catalog_role_present",
                            "checks": [
                                "role-present-apply-and-replay",
                                "runtime-select-and-table-column-dml-denial",
                                "Directus-grants-unchanged",
                                "database-owner-seed-upserts-retained",
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
            [
                "docker", "inspect", "--format",
                "{{.State.Status}} {{.State.OOMKilled}} {{.State.ExitCode}}", container,
            ],
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
