#!/usr/bin/env python3
"""Apply/replay migration 720 and exercise thesaurus ACLs in disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/720_runtime_thesaurus_bounded_writes.sql"
IMAGE = os.environ.get(
    "THESAURUS_RUNTIME_TEST_IMAGE",
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
CREATE SCHEMA kokonut_security;
CREATE TABLE public.thesaurus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    date_updated DATE,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE public.thesaurus_keyword (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesaurus_id UUID NOT NULL REFERENCES public.thesaurus(id) ON DELETE CASCADE,
    keyword_about VARCHAR(255) NOT NULL,
    alt_label VARCHAR(255),
    parent_keyword_id UUID REFERENCES public.thesaurus_keyword(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE public.thesaurus_keyword_label (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword_id UUID NOT NULL REFERENCES public.thesaurus_keyword(id) ON DELETE CASCADE,
    label VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(keyword_id, language)
);
GRANT ALL ON TABLE public.thesaurus, public.thesaurus_keyword,
    public.thesaurus_keyword_label TO PUBLIC;
"""

RUNTIME_ROLE_CREATE = r"""
CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT;
"""

RUNTIME_ROLE_GRANTS = r"""
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime;
GRANT ALL ON TABLE public.thesaurus, public.thesaurus_keyword,
    public.thesaurus_keyword_label TO kokonut_runtime;
"""

ROLE_ABSENT_ASSERTIONS = r"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'role-absent fixture unexpectedly created kokonut_runtime';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc AS function
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = function.pronamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(function.proacl, pg_catalog.acldefault('f', function.proowner))
          ) AS privilege
         WHERE namespace.nspname = 'kokonut_security'
           AND function.proname = ANY(ARRAY[
               'create_thesaurus', 'add_thesaurus_keyword',
               'upsert_thesaurus_keyword_label', 'delete_thesaurus_keyword'
           ])
           AND privilege.grantee = 0
           AND privilege.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC EXECUTE was not revoked without kokonut_runtime';
    END IF;
END;
$$;
"""


ASSERTIONS = r"""
DO $$
DECLARE
    relation_name TEXT;
    privilege_name TEXT;
    function_count INTEGER;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_thesaurus_owner'
           AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
           AND NOT rolinherit
    ) THEN
        RAISE EXCEPTION 'function owner role is not safely isolated';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
        WHERE granted_role.rolname = 'kokonut_thesaurus_owner'
           OR member_role.rolname = 'kokonut_thesaurus_owner'
    ) THEN
        RAISE EXCEPTION 'function owner has an unexpected role membership';
    END IF;

    FOREACH relation_name IN ARRAY ARRAY[
        'thesaurus', 'thesaurus_keyword', 'thesaurus_keyword_label'
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
                RAISE EXCEPTION 'direct % privilege remains on %', privilege_name, relation_name;
            END IF;
        END LOOP;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(relation.relacl, pg_catalog.acldefault('r', relation.relowner))
          ) AS privilege
         WHERE namespace.nspname = 'public'
           AND relation.relname = ANY(ARRAY[
               'thesaurus', 'thesaurus_keyword', 'thesaurus_keyword_label'
           ])
           AND privilege.grantee = 0
           AND privilege.privilege_type = ANY(ARRAY[
               'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
           ])
    ) THEN
        RAISE EXCEPTION 'PUBLIC retains direct thesaurus table DML';
    END IF;

    IF has_column_privilege(
        'kokonut_runtime', 'public.thesaurus', 'title', 'UPDATE'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.thesaurus_keyword', 'keyword_about', 'INSERT'
    ) OR has_column_privilege(
        'kokonut_runtime', 'public.thesaurus_keyword_label', 'label', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'runtime retains a residual column mutation grant';
    END IF;

    IF NOT has_column_privilege(
        'kokonut_thesaurus_owner', 'public.thesaurus', 'title', 'UPDATE'
    ) OR NOT has_column_privilege(
        'kokonut_thesaurus_owner', 'public.thesaurus_keyword', 'thesaurus_id', 'INSERT'
    ) OR NOT has_table_privilege(
        'kokonut_thesaurus_owner', 'public.thesaurus_keyword_label', 'DELETE'
    ) THEN
        RAISE EXCEPTION 'function owner lacks a required bounded write grant';
    END IF;
    IF has_table_privilege(
        'kokonut_thesaurus_owner', 'public.thesaurus', 'DELETE'
    ) OR has_column_privilege(
        'kokonut_thesaurus_owner', 'public.thesaurus', 'language', 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'function owner has an unexpected write grant';
    END IF;

    SELECT count(*) INTO function_count
      FROM pg_catalog.pg_proc AS function
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = function.pronamespace
      CROSS JOIN LATERAL pg_catalog.aclexplode(
          COALESCE(function.proacl, pg_catalog.acldefault('f', function.proowner))
      ) AS privilege
     WHERE namespace.nspname = 'kokonut_security'
       AND function.proname = ANY(ARRAY[
           'create_thesaurus', 'add_thesaurus_keyword',
           'upsert_thesaurus_keyword_label', 'delete_thesaurus_keyword'
       ])
       AND privilege.grantee = 0
       AND privilege.privilege_type = 'EXECUTE';
    IF function_count <> 0 THEN
        RAISE EXCEPTION 'PUBLIC can execute a thesaurus mutation function';
    END IF;
END;
$$;

SET ROLE kokonut_runtime;
DO $$
BEGIN
    BEGIN
        INSERT INTO public.thesaurus (identifier, title) VALUES ('direct-insert', 'Denied');
        RAISE EXCEPTION 'runtime INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.thesaurus SET title = 'Denied';
        RAISE EXCEPTION 'runtime UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM public.thesaurus;
        RAISE EXCEPTION 'runtime DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;
RESET ROLE;

SET ROLE kokonut_runtime;
DO $$
DECLARE
    vocabulary_id UUID;
    replay_id UUID;
    other_vocabulary_id UUID;
    root_id UUID;
    child_id UUID;
    label_id UUID;
    replay_label_id UUID;
BEGIN
    SELECT result.id INTO vocabulary_id
      FROM kokonut_security.create_thesaurus(
          'activity_type', 'Activity Types', 'initial', 'en'
      ) AS result;
    SELECT result.id INTO replay_id
      FROM kokonut_security.create_thesaurus(
          'activity_type', 'Updated Activities', 'updated', 'es'
      ) AS result;
    IF vocabulary_id IS DISTINCT FROM replay_id
       OR (SELECT title FROM public.thesaurus WHERE id = vocabulary_id)
            IS DISTINCT FROM 'Updated Activities'
       OR (SELECT description FROM public.thesaurus WHERE id = vocabulary_id)
            IS DISTINCT FROM 'updated'
       OR (SELECT language FROM public.thesaurus WHERE id = vocabulary_id)
            IS DISTINCT FROM 'en' THEN
        RAISE EXCEPTION 'thesaurus create/upsert behavior changed';
    END IF;

    SELECT result.id INTO root_id
      FROM kokonut_security.add_thesaurus_keyword(
          vocabulary_id, 'root', NULL, NULL
      ) AS result;
    SELECT result.id INTO child_id
      FROM kokonut_security.add_thesaurus_keyword(
          vocabulary_id, 'child', 'alternate', root_id
      ) AS result;
    SELECT result.id INTO other_vocabulary_id
      FROM kokonut_security.create_thesaurus(
          'environment_type', 'Environment', NULL, 'en'
      ) AS result;

    BEGIN
        PERFORM * FROM kokonut_security.add_thesaurus_keyword(
            other_vocabulary_id, 'cross-parent', NULL, root_id
        );
        RAISE EXCEPTION 'cross-thesaurus parent unexpectedly succeeded';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    SELECT result.id INTO label_id
      FROM kokonut_security.upsert_thesaurus_keyword_label(
          child_id, 'Child', 'en'
      ) AS result;
    SELECT result.id INTO replay_label_id
      FROM kokonut_security.upsert_thesaurus_keyword_label(
          child_id, 'Updated Child', 'en'
      ) AS result;
    IF label_id IS DISTINCT FROM replay_label_id
       OR (SELECT label FROM public.thesaurus_keyword_label
            WHERE id = label_id) IS DISTINCT FROM 'Updated Child' THEN
        RAISE EXCEPTION 'keyword-label upsert behavior changed';
    END IF;

    IF NOT kokonut_security.delete_thesaurus_keyword(child_id)
       OR kokonut_security.delete_thesaurus_keyword(child_id) THEN
        RAISE EXCEPTION 'keyword deletion result is not compatible';
    END IF;
    IF EXISTS (SELECT 1 FROM public.thesaurus_keyword WHERE id = child_id)
       OR EXISTS (SELECT 1 FROM public.thesaurus_keyword_label WHERE keyword_id = child_id) THEN
        RAISE EXCEPTION 'keyword deletion did not cascade to its labels';
    END IF;
    IF NOT kokonut_security.delete_thesaurus_keyword(root_id) THEN
        RAISE EXCEPTION 'root keyword deletion failed after child removal';
    END IF;
END;
$$;
RESET ROLE;
"""


def main() -> int:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI is required for disposable PostgreSQL acceptance")
    if not MIGRATION.is_file():
        raise RuntimeError(f"required migration is missing: {MIGRATION}")

    container = f"kokonut-thesaurus-acl-{secrets.token_hex(5)}"
    created = False
    try:
        run(
            [
                "docker", "run", "--rm", "--detach", "--network", "none",
                "--name", container, "-e", "POSTGRES_PASSWORD=disposable-only",
                IMAGE,
            ]
        )
        created = True
        deadline = time.monotonic() + 90
        initialization_complete = False
        consecutive_successes = 0
        while time.monotonic() < deadline:
            if not initialization_complete:
                logs = run(["docker", "logs", container], check=False)
                initialization_complete = (
                    "PostgreSQL init process complete; ready for start up."
                    in (logs.stdout + logs.stderr)
                )
            if initialization_complete:
                ready = run(
                    [
                        "docker", "exec", container, "pg_isready", "-h",
                        "127.0.0.1", "-U", "postgres", "-d", "postgres",
                    ],
                    check=False,
                )
                if ready.returncode == 0:
                    consecutive_successes += 1
                    if consecutive_successes >= 4:
                        break
                else:
                    consecutive_successes = 0
            time.sleep(0.25)
        else:
            raise RuntimeError(
                "disposable PostgreSQL did not finish initialization and become ready"
            )

        migration_sql = MIGRATION.read_text(encoding="utf-8")
        docker_psql(container, "CREATE DATABASE thesaurus_role_absent")
        docker_psql(container, "CREATE DATABASE thesaurus_role_present")

        # Standard profile order: apply the schema before runtime-role bootstrap.
        docker_psql(container, SCHEMA_FIXTURE, "thesaurus_role_absent")
        docker_psql(container, migration_sql, "thesaurus_role_absent")
        docker_psql(container, ROLE_ABSENT_ASSERTIONS, "thesaurus_role_absent")
        docker_psql(container, RUNTIME_ROLE_CREATE, "thesaurus_role_absent")
        docker_psql(container, RUNTIME_ROLE_GRANTS, "thesaurus_role_absent")
        # Reapplying after role bootstrap must close compatibility table grants,
        # restore the four function grants, and leave PUBLIC EXECUTE revoked.
        docker_psql(container, migration_sql, "thesaurus_role_absent")
        docker_psql(container, migration_sql, "thesaurus_role_absent")
        docker_psql(container, ASSERTIONS, "thesaurus_role_absent")

        # Existing deployments already have the runtime role when migrations run.
        docker_psql(container, SCHEMA_FIXTURE, "thesaurus_role_present")
        docker_psql(container, RUNTIME_ROLE_GRANTS, "thesaurus_role_present")
        docker_psql(container, migration_sql, "thesaurus_role_present")
        docker_psql(container, migration_sql, "thesaurus_role_present")
        docker_psql(container, ASSERTIONS, "thesaurus_role_present")
        print(
            json.dumps(
                {
                    "result": "passed",
                    "database": "network-disabled disposable PostgreSQL 16",
                    "migration": MIGRATION.name,
                    "migration_replays": 4,
                    "checks": [
                        "migration succeeds before kokonut_runtime exists",
                        "PUBLIC EXECUTE remains revoked before runtime bootstrap",
                        "post-bootstrap compatibility regrants are closed on migration replay",
                        "preexisting runtime role receives explicit grants",
                        "safe no-login function owner and no membership",
                        "runtime read preservation and PUBLIC/runtime direct DML denial",
                        "residual column grant removal and narrow function-owner grants",
                        "PUBLIC execute denied and runtime execute granted",
                        "thesaurus create/upsert compatibility",
                        "keyword parent same-thesaurus enforcement",
                        "label upsert compatibility",
                        "keyword deletion and cascade behavior",
                    ],
                    "candidate_legacy_production_touched": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
    except Exception:
        if created:
            logs = run(["docker", "logs", container], check=False)
            if logs.stdout or logs.stderr:
                print("disposable PostgreSQL logs:\n" + logs.stdout + logs.stderr)
        raise
    finally:
        if created:
            run(["docker", "rm", "--force", container], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
