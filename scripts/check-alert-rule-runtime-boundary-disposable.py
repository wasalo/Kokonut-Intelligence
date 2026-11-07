#!/usr/bin/env python3
"""Check migration 739 with an isolated, network-disabled PostgreSQL 16."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIGRATION = ROOT / "schemas/postgres/739_runtime_alert_rule_read_only.sql"
IMAGE = os.environ.get(
    "ALERT_RULE_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)

FIXTURE = r"""
CREATE ROLE kokonut NOLOGIN;
CREATE ROLE kokonut_anomaly_event_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_sensor_baseline_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA kokonut_security;
CREATE TABLE kokonut_security.directus_relation_privilege_policy (
    schema_name text NOT NULL,
    relation_name text NOT NULL,
    access_mode text NOT NULL,
    source_migration text NOT NULL,
    PRIMARY KEY (schema_name, relation_name)
);
CREATE TABLE public.sensor_type (
    id uuid PRIMARY KEY,
    name text NOT NULL UNIQUE
);
INSERT INTO public.sensor_type (id, name) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'soil_moisture'),
    ('a0000000-0000-0000-0000-000000000002', 'soil_temperature'),
    ('a0000000-0000-0000-0000-000000000003', 'air_temperature'),
    ('a0000000-0000-0000-0000-000000000004', 'humidity'),
    ('a0000000-0000-0000-0000-000000000005', 'rainfall');
GRANT SELECT ON public.sensor_type TO kokonut;
CREATE TABLE public.alert_rule (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    sensor_type_id uuid NOT NULL REFERENCES public.sensor_type(id),
    metric text NOT NULL,
    operator text NOT NULL,
    threshold_value numeric,
    threshold_value_max numeric,
    severity text NOT NULL,
    cooldown_minutes integer NOT NULL DEFAULT 60,
    enabled boolean NOT NULL DEFAULT true,
    auto_create_claim boolean NOT NULL DEFAULT false,
    claim_type text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.alert_rule OWNER TO kokonut;
GRANT SELECT ON public.alert_rule TO kokonut_anomaly_event_owner,
    kokonut_sensor_baseline_owner;
GRANT USAGE, CREATE ON SCHEMA kokonut_security TO kokonut_anomaly_event_owner,
    kokonut_sensor_baseline_owner;
CREATE FUNCTION kokonut_security.worker_alert_rule_read()
RETURNS bigint LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog
AS $$ SELECT count(*) FROM public.alert_rule $$;
ALTER FUNCTION kokonut_security.worker_alert_rule_read()
    OWNER TO kokonut_anomaly_event_owner;
CREATE FUNCTION kokonut_security.baseline_alert_rule_read()
RETURNS bigint LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog
AS $$ SELECT count(*) FROM public.alert_rule $$;
ALTER FUNCTION kokonut_security.baseline_alert_rule_read()
    OWNER TO kokonut_sensor_baseline_owner;
REVOKE ALL ON FUNCTION kokonut_security.worker_alert_rule_read(),
    kokonut_security.baseline_alert_rule_read() FROM PUBLIC;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_anomaly_event_owner,
    kokonut_sensor_baseline_owner;
"""

ASSERT_ROLE_ABSENT = r"""
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                WHERE rolname IN ('kokonut_runtime', 'kokonut_directus_runtime')) THEN
        RAISE EXCEPTION 'migration created an absent application role';
    END IF;
    IF (SELECT count(*) FROM kokonut_security.directus_relation_privilege_policy
         WHERE schema_name = 'public' AND relation_name = 'alert_rule'
           AND access_mode = 'read_only'
           AND source_migration = '739_runtime_alert_rule_read_only.sql') <> 1 THEN
        RAISE EXCEPTION 'Directus read-only policy was not registered';
    END IF;
END $$;
"""

# This repeats the exact post-compatibility grant reconciliation performed by
# the two role provisioners, so a later generic grant cannot reopen the table.
PROVISIONER_REAPPLICATION = r"""
DO $$
DECLARE
    column_name text;
    policy_row record;
BEGIN
    REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
        ON public.alert_rule FROM kokonut_runtime;
    FOR column_name IN
        SELECT attname FROM pg_catalog.pg_attribute
         WHERE attrelid = 'public.alert_rule'::regclass
           AND attnum > 0 AND NOT attisdropped
    LOOP
        EXECUTE format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON public.alert_rule FROM kokonut_runtime', column_name
        );
    END LOOP;
    GRANT SELECT ON public.alert_rule TO kokonut_runtime;
    GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
    GRANT EXECUTE ON FUNCTION kokonut_security.ensure_default_alert_rules()
        TO kokonut_runtime;

    FOR policy_row IN
        SELECT schema_name, relation_name, access_mode
          FROM kokonut_security.directus_relation_privilege_policy
         WHERE schema_name = 'public' AND relation_name = 'alert_rule'
    LOOP
        IF policy_row.access_mode = 'read_only' THEN
            EXECUTE format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                'ON TABLE %I.%I FROM kokonut_directus_runtime',
                policy_row.schema_name, policy_row.relation_name
            );
            FOR column_name IN
                SELECT attname FROM pg_catalog.pg_attribute
                 WHERE attrelid = format('%I.%I', policy_row.schema_name,
                                         policy_row.relation_name)::regclass
                   AND attnum > 0 AND NOT attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE %2$I.%3$I FROM kokonut_directus_runtime',
                    column_name, policy_row.schema_name, policy_row.relation_name
                );
            END LOOP;
        ELSE
            RAISE EXCEPTION 'unexpected Directus alert_rule policy mode: %',
                policy_row.access_mode;
        END IF;
    END LOOP;
    GRANT SELECT ON public.alert_rule TO kokonut_directus_runtime;
    REVOKE ALL ON FUNCTION kokonut_security.ensure_default_alert_rules()
        FROM kokonut_directus_runtime;
END;
$$;
"""

ASSERT_ACLS_AND_WORKERS = r"""
DO $$
DECLARE
    privilege_name text;
    column_name text;
BEGIN
    IF NOT has_table_privilege('kokonut_runtime', 'public.alert_rule', 'SELECT')
       OR NOT has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'SELECT') THEN
        RAISE EXCEPTION 'runtime or Directus SELECT was removed';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.alert_rule', 'INSERT')
       OR has_table_privilege('kokonut_runtime', 'public.alert_rule', 'UPDATE')
       OR has_table_privilege('kokonut_runtime', 'public.alert_rule', 'DELETE')
       OR has_table_privilege('kokonut_runtime', 'public.alert_rule', 'TRUNCATE')
       OR has_table_privilege('kokonut_runtime', 'public.alert_rule', 'REFERENCES')
       OR has_table_privilege('kokonut_runtime', 'public.alert_rule', 'TRIGGER') THEN
        RAISE EXCEPTION 'runtime retains alert_rule table DML';
    END IF;
    IF has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'UPDATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'DELETE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'TRUNCATE')
       OR has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'REFERENCES')
       OR has_table_privilege('kokonut_directus_runtime', 'public.alert_rule', 'TRIGGER') THEN
        RAISE EXCEPTION 'Directus retains alert_rule table DML';
    END IF;
    FOR column_name IN
        SELECT attname FROM pg_catalog.pg_attribute
         WHERE attrelid = 'public.alert_rule'::regclass
           AND attnum > 0 AND NOT attisdropped
    LOOP
        FOREACH privilege_name IN ARRAY ARRAY['INSERT', 'UPDATE', 'REFERENCES'] LOOP
            IF has_column_privilege('kokonut_runtime', 'public.alert_rule', column_name, privilege_name)
               OR has_column_privilege('kokonut_directus_runtime', 'public.alert_rule', column_name, privilege_name) THEN
                RAISE EXCEPTION 'column-level DML remains on alert_rule.%', column_name;
            END IF;
        END LOOP;
    END LOOP;
    IF NOT has_function_privilege(
        'kokonut_runtime', 'kokonut_security.ensure_default_alert_rules()', 'EXECUTE'
    ) OR has_function_privilege(
        'kokonut_directus_runtime', 'kokonut_security.ensure_default_alert_rules()', 'EXECUTE'
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc AS procedure
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(procedure.proacl, pg_catalog.acldefault('f', procedure.proowner))
          ) AS acl_entry
         WHERE procedure.oid = pg_catalog.to_regprocedure(
             'kokonut_security.ensure_default_alert_rules()'
         )
           AND acl_entry.grantee = 0
           AND acl_entry.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'bounded initializer execute grants are incorrect';
    END IF;
    IF NOT has_table_privilege('kokonut_anomaly_event_owner', 'public.alert_rule', 'SELECT')
       OR NOT has_table_privilege('kokonut_sensor_baseline_owner', 'public.alert_rule', 'SELECT') THEN
        RAISE EXCEPTION 'worker function owner reads were revoked';
    END IF;
    IF (SELECT rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                 OR rolbypassrls OR rolinherit
          FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_alert_rule_owner') THEN
        RAISE EXCEPTION 'bounded function owner has unsafe role attributes';
    END IF;
    IF has_schema_privilege('kokonut_alert_rule_owner', 'kokonut_security', 'CREATE')
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members AS membership
           JOIN pg_catalog.pg_roles AS owner ON owner.oid = membership.roleid
           JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
           WHERE owner.rolname = 'kokonut_alert_rule_owner'
              OR member.rolname = 'kokonut_alert_rule_owner'
       )
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_class
            WHERE relowner = (
                SELECT oid FROM pg_catalog.pg_roles
                 WHERE rolname = 'kokonut_alert_rule_owner'
            )
              AND relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
       ) THEN
        RAISE EXCEPTION 'bounded function owner retained CREATE, membership, or relation ownership';
    END IF;
    IF NOT has_table_privilege('kokonut', 'public.alert_rule', 'INSERT')
       OR NOT has_table_privilege('kokonut', 'public.alert_rule', 'UPDATE')
       OR NOT has_table_privilege('kokonut', 'public.alert_rule', 'DELETE') THEN
        RAISE EXCEPTION 'owner/admin seed write access was removed';
    END IF;
    IF (SELECT relrowsecurity FROM pg_catalog.pg_class
         WHERE oid = 'public.alert_rule'::regclass) THEN
        RAISE EXCEPTION 'alert_rule RLS posture changed';
    END IF;
END;
$$;

SET ROLE kokonut_runtime;
DO $$
DECLARE inserted integer;
BEGIN
    IF (SELECT count(*) FROM public.alert_rule) <> 0 THEN
        RAISE EXCEPTION 'catalog was not empty before lazy initialization';
    END IF;
    SELECT kokonut_security.ensure_default_alert_rules() INTO inserted;
    IF inserted <> 10 OR (SELECT count(*) FROM public.alert_rule) <> 10 THEN
        RAISE EXCEPTION 'empty catalog did not receive ten defaults';
    END IF;
    SELECT kokonut_security.ensure_default_alert_rules() INTO inserted;
    IF inserted <> 0 OR (SELECT count(*) FROM public.alert_rule) <> 10 THEN
        RAISE EXCEPTION 'default initialization is not idempotent';
    END IF;
END;
$$;
RESET ROLE;

DO $$ BEGIN
    IF kokonut_security.worker_alert_rule_read() <> 10
       OR kokonut_security.baseline_alert_rule_read() <> 10 THEN
        RAISE EXCEPTION 'anomaly worker owner function cannot read alert_rule';
    END IF;
END $$;

SET ROLE kokonut_runtime;
DO $$ BEGIN
    BEGIN
        INSERT INTO public.alert_rule
            (name, sensor_type_id, metric, operator, severity)
        VALUES ('denied', 'a0000000-0000-0000-0000-000000000001', 'value', 'gt', 'warning');
        RAISE EXCEPTION 'runtime INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.alert_rule SET name = 'denied';
        RAISE EXCEPTION 'runtime UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM public.alert_rule;
        RAISE EXCEPTION 'runtime DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END $$;
RESET ROLE;

SET ROLE kokonut_directus_runtime;
DO $$ BEGIN
    BEGIN
        INSERT INTO public.alert_rule
            (name, sensor_type_id, metric, operator, severity)
        VALUES ('denied', 'a0000000-0000-0000-0000-000000000001', 'value', 'gt', 'warning');
        RAISE EXCEPTION 'Directus INSERT unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.alert_rule SET name = 'denied';
        RAISE EXCEPTION 'Directus UPDATE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM public.alert_rule;
        RAISE EXCEPTION 'Directus DELETE unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM kokonut_security.ensure_default_alert_rules();
        RAISE EXCEPTION 'Directus initializer execution unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END $$;
RESET ROLE;

SET ROLE kokonut;
INSERT INTO public.alert_rule
    (name, sensor_type_id, metric, operator, severity)
VALUES ('owner seed', 'a0000000-0000-0000-0000-000000000001', 'value', 'gt', 'warning');
RESET ROLE;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.alert_rule WHERE name = 'owner seed') THEN
        RAISE EXCEPTION 'owner/admin seed insert did not persist';
    END IF;
END $$;
"""


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
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
            "docker", "exec", "-i", container, "psql", "-X", "-q", "-v",
            "ON_ERROR_STOP=1", "-A", "-t", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def pilot_alert_rule_insert() -> str:
    seed = (ROOT / "schemas/seeds/003_pilot_environmental.sql").read_text(encoding="utf-8")
    match = re.search(r"-- Alert Rules\s*(INSERT INTO alert_rule.*?;)", seed, re.DOTALL)
    if match is None:
        raise RuntimeError("pilot alert rule seed statement is missing")
    statement = match.group(1)
    if len(re.findall(r"\('a0000000-0000-0000-0000-00000000014[0-7]'", statement)) != 8:
        raise RuntimeError("pilot alert rule seed no longer contains the expected eight IDs")
    return statement


def assert_migration_source() -> dict[str, object]:
    from services.migration.cli import _discover_files, _validate_sources

    migrations = _discover_files(include_seeds=False)
    _validate_sources(migrations)
    if not migrations or migrations[-1]["id"] != "schema:739_runtime_alert_rule_read_only.sql":
        raise RuntimeError("migration 739 is not the newest ordered schema migration")
    return {"migration_sources_validated": len(migrations), "latest": migrations[-1]["id"]}


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is required for this disposable acceptance")
    source_result = assert_migration_source()
    container = f"kokonut-alert-rule-acl-{secrets.token_hex(5)}"
    started = False
    phase = "container_start"
    try:
        run([
            docker, "run", "--pull=never", "--detach", "--rm", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ])
        started = True
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            logs = run([docker, "logs", container], check=False)
            init_complete = (
                "PostgreSQL init process complete; ready for start up."
                in (logs.stdout + logs.stderr)
            )
            ready = run(
                [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                check=False,
            )
            if init_complete and ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("isolated PostgreSQL did not become ready")

        phase = "schema_fixture"
        psql(container, FIXTURE)
        migration = MIGRATION.read_text(encoding="utf-8")
        phase = "role_absent_migration_apply"
        psql(container, migration)
        phase = "role_absent_assertions"
        psql(container, ASSERT_ROLE_ABSENT)
        phase = "role_absent_migration_replay"
        psql(container, migration)  # exact migration replay before role bootstrap

        # Model the role bootstrap's broad compatibility grants, then replay
        # migration 739 with both application logins present.
        phase = "post_migration_role_bootstrap"
        psql(container, r"""
CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT ALL PRIVILEGES ON TABLE public.alert_rule
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (name), UPDATE (name), REFERENCES (name)
    ON TABLE public.alert_rule TO kokonut_runtime, kokonut_directus_runtime;
""")
        phase = "role_present_migration_replay"
        psql(container, migration)
        psql(container, "SELECT 'migration replay with pre-existing roles passed';")

        # Reapply broad compatibility grants after migration, then run the same
        # declared boundaries used by the runtime and Directus provisioners.
        phase = "provisioner_compatibility_grants"
        psql(container, r"""
GRANT ALL PRIVILEGES ON TABLE public.alert_rule
    TO kokonut_runtime, kokonut_directus_runtime;
GRANT INSERT (name), UPDATE (name), REFERENCES (name)
    ON TABLE public.alert_rule TO kokonut_runtime, kokonut_directus_runtime;
""")
        phase = "provisioner_boundary_reapplication"
        psql(container, PROVISIONER_REAPPLICATION)
        phase = "acl_and_worker_assertions"
        psql(container, ASSERT_ACLS_AND_WORKERS)

        phase = "pilot_seed_behavior"
        pilot_seed = pilot_alert_rule_insert()
        psql(container, "TRUNCATE public.alert_rule; SET ROLE kokonut;\n" + pilot_seed + "\nRESET ROLE;")
        phase = "populated_catalog_behavior"
        psql(container, r"""
SET ROLE kokonut_runtime;
DO $$ DECLARE inserted integer; BEGIN
    SELECT kokonut_security.ensure_default_alert_rules() INTO inserted;
    IF inserted <> 0 OR (SELECT count(*) FROM public.alert_rule) <> 8 THEN
        RAISE EXCEPTION 'lazy defaults changed the existing eight-rule pilot seed';
    END IF;
END $$;
RESET ROLE;
""")
        pilot_count = psql(container, "SELECT count(*) FROM public.alert_rule;")
        if pilot_count.stdout.strip() != "8":
            raise RuntimeError("pilot seed did not retain exactly eight alert rules")

        # A pre-existing single custom rule must continue suppressing defaults.
        psql(container, r"""
TRUNCATE public.alert_rule;
SET ROLE kokonut;
INSERT INTO public.alert_rule (name, sensor_type_id, metric, operator, severity)
VALUES ('custom existing rule', 'a0000000-0000-0000-0000-000000000001', 'value', 'gt', 'warning');
RESET ROLE;
SET ROLE kokonut_runtime;
DO $$ DECLARE inserted integer; BEGIN
    SELECT kokonut_security.ensure_default_alert_rules() INTO inserted;
    IF inserted <> 0 OR (SELECT count(*) FROM public.alert_rule) <> 1 THEN
        RAISE EXCEPTION 'nonempty catalog was overwritten or supplemented';
    END IF;
END $$;
RESET ROLE;
""")
        print(json.dumps({
            "result": "passed",
            "migration": MIGRATION.name,
            **source_result,
            "role_absent_ordering": "passed; migration did not create runtime or Directus roles",
            "apply_and_replay": "passed with roles absent and present",
            "empty_catalog": "runtime bounded call inserted ten defaults; repeat inserted zero",
            "pilot_seed": "actual 003 pilot alert_rule insert retained exactly eight rows",
            "populated_catalog": "single custom rule suppresses default insertion",
            "runtime_acl": "SELECT and bounded execute preserved; table/column writes denied",
            "directus_acl": "SELECT preserved; table/column writes and initializer execution denied",
            "worker_reads": "both anomaly-event and sensor-baseline SECURITY DEFINER readers returned the rule count",
            "owner_seed_access": "kokonut owner inserted a curated rule",
            "runtime_provisioner_reapplication": "broad grant was revoked and bounded function/SELECT restored",
            "directus_provisioner_reapplication": "read_only registry policy removed broad grant and retained SELECT",
            "rls": "unchanged and disabled for the global catalog",
            "network": "none",
            "host_ports_published": False,
            "container_cleaned_up": True,
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        diagnostic = run([docker, "logs", container], check=False) if started else None
        detail = (diagnostic.stdout + diagnostic.stderr)[-6000:] if diagnostic else ""
        raise RuntimeError(
            f"{phase}: {type(exc).__name__}: {exc}; disposable postgres log tail: {detail}"
        ) from exc
    finally:
        if started:
            run([docker, "rm", "--force", container], check=False)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # output only exception class/message, never environment values
        print(f"alert-rule disposable acceptance failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
