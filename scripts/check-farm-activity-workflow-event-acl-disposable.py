#!/usr/bin/env python3
"""Verify migration 734's append-only farm-activity event ACL on disposable PG16."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/734_runtime_farm_activity_workflow_event_append_only.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-11-01-recovery/farm-activity-workflow-event-acl-734-disposable.json"
)


def run(command: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{detail}"
        )
    return result


def docker_sql(container: str, statement: str) -> str:
    result = run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )
    return result.stdout.strip()


def wait_ready(container: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = run(
            [
                "docker",
                "exec",
                container,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "postgres",
                "-d",
                "postgres",
            ],
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def assert_result(name: str, value: str, expected: str) -> None:
    if value != expected:
        raise AssertionError(f"{name}: expected {expected!r}, received {value!r}")


def main() -> int:
    container = f"kokonut-farm-event-acl-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(24)
    started = False
    try:
        run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--network",
                "none",
                "--name",
                container,
                "--env",
                f"POSTGRES_PASSWORD={password}",
                "postgres:16",
            ]
        )
        started = True
        wait_ready(container)
        docker_sql(
            container,
            """
            CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT;
            CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT;
            CREATE ROLE kokonut_maintenance NOLOGIN NOINHERIT;
            CREATE TABLE public.farm_activity_workflow_event (
                id bigint PRIMARY KEY,
                event_payload text NOT NULL
            );
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
                public.farm_activity_workflow_event
                TO kokonut_runtime, kokonut_directus_runtime, kokonut_maintenance;
            -- Model stale per-column grants from older provisioner/role states.
            GRANT SELECT (id), INSERT (event_payload), UPDATE (event_payload),
                  REFERENCES (event_payload) ON TABLE
                public.farm_activity_workflow_event TO kokonut_runtime;
            CREATE FUNCTION public.test_event_update_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'farm activity workflow events are append-only';
            END;
            $$;
            CREATE TRIGGER trg_test_event_update_guard
            BEFORE UPDATE OR DELETE ON public.farm_activity_workflow_event
            FOR EACH ROW EXECUTE FUNCTION public.test_event_update_guard();
            """,
        )

        # Replay proves the ACL migration is idempotent.
        docker_sql(container, MIGRATION.read_text())
        docker_sql(container, MIGRATION.read_text())
        assert_result(
            "runtime table privileges",
            docker_sql(
                container,
                """SELECT has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'SELECT')::int || ',' ||
                          has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'INSERT')::int || ',' ||
                          has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'UPDATE')::int || ',' ||
                          has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'DELETE')::int || ',' ||
                          has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'TRUNCATE')::int || ',' ||
                          has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'REFERENCES')::int || ',' ||
                          has_table_privilege('kokonut_runtime',
                          'public.farm_activity_workflow_event', 'TRIGGER')::int""",
            ),
            "1,1,0,0,0,0,0",
        )
        assert_result(
            "runtime column grants removed",
            docker_sql(
                container,
                """SELECT EXISTS (
                       SELECT 1
                         FROM pg_catalog.pg_attribute AS attribute
                         CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS privilege
                        WHERE attribute.attrelid = 'public.farm_activity_workflow_event'::regclass
                          AND attribute.attnum > 0 AND NOT attribute.attisdropped
                          AND privilege.grantee = (
                              SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
                          )
                          AND privilege.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES')
                     )::int""",
            ),
            "0",
        )
        assert_result(
            "Directus and maintenance privileges unchanged",
            docker_sql(
                container,
                """SELECT bool_and(
                           has_table_privilege(role_name,
                               'public.farm_activity_workflow_event', privilege)
                       )::int
                     FROM (VALUES
                         ('kokonut_directus_runtime', 'SELECT'),
                         ('kokonut_directus_runtime', 'INSERT'),
                         ('kokonut_directus_runtime', 'UPDATE'),
                         ('kokonut_directus_runtime', 'DELETE'),
                         ('kokonut_maintenance', 'SELECT'),
                         ('kokonut_maintenance', 'INSERT'),
                         ('kokonut_maintenance', 'UPDATE'),
                         ('kokonut_maintenance', 'DELETE')
                     ) AS expected(role_name, privilege)""",
            ),
            "1",
        )
        assert_result(
            "append-only trigger preserved",
            docker_sql(
                container,
                """SELECT count(*)::text FROM pg_catalog.pg_trigger
                    WHERE tgrelid = 'public.farm_activity_workflow_event'::regclass
                      AND tgname = 'trg_test_event_update_guard' AND NOT tgisinternal""",
            ),
            "1",
        )
        runtime_write_result = docker_sql(
            container,
            """
            SET ROLE kokonut_runtime;
            INSERT INTO public.farm_activity_workflow_event (id, event_payload)
                VALUES (1, 'synthetic');
            DO $$
            DECLARE denied BOOLEAN;
            BEGIN
                IF (SELECT count(*) FROM public.farm_activity_workflow_event) <> 1 THEN
                    RAISE EXCEPTION 'runtime SELECT failed';
                END IF;
                denied := FALSE;
                BEGIN
                    UPDATE public.farm_activity_workflow_event
                       SET event_payload = 'changed' WHERE id = 1;
                EXCEPTION WHEN insufficient_privilege THEN
                    denied := TRUE;
                END;
                IF NOT denied THEN RAISE EXCEPTION 'runtime UPDATE unexpectedly succeeded'; END IF;
                denied := FALSE;
                BEGIN
                    DELETE FROM public.farm_activity_workflow_event WHERE id = 1;
                EXCEPTION WHEN insufficient_privilege THEN
                    denied := TRUE;
                END;
                IF NOT denied THEN RAISE EXCEPTION 'runtime DELETE unexpectedly succeeded'; END IF;
            END;
            $$;
            RESET ROLE;
            SELECT 'passed';
            """,
        )
        if runtime_write_result.splitlines()[-1:] != ["passed"]:
            raise AssertionError(
                "runtime can read and append, but not update/delete: "
                f"received {runtime_write_result!r}"
            )

        output = {
            "status": "passed",
            "migration": MIGRATION.name,
            "postgres_major": 16,
            "network": "none",
            "host_ports": "none",
            "synthetic_data_only": True,
            "checks": [
                "migration replay is idempotent",
                "runtime retains only table-level SELECT and INSERT",
                "stale per-column grants are removed",
                "runtime UPDATE and DELETE fail before table triggers",
                "Directus and maintenance grants remain unchanged",
                "append-only trigger remains installed",
            ],
        }
        DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
        print(json.dumps(output, indent=2))
        return 0
    except (OSError, RuntimeError, AssertionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if started:
            run(["docker", "stop", container], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
