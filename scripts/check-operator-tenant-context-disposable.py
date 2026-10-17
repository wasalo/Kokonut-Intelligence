#!/usr/bin/env python3
"""Accept signed operator tenant context against isolated PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/operator_tenant_context_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/394_signed_operator_tenant_context.sql"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-14-recovery/operator-tenant-context-disposable.json"
)
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OWNER_ORG_ID = "a0000000-0000-0000-0000-000000000801"
PARTNER_ORG_ID = "a0000000-0000-0000-0000-000000000802"
OWNER_OPERATOR_ID = "a0000000-0000-0000-0000-000000000901"
PARTNER_OPERATOR_ID = "a0000000-0000-0000-0000-000000000902"
MULTI_OPERATOR_ID = "a0000000-0000-0000-0000-000000000903"
LEGACY_OPERATOR_ID = "a0000000-0000-0000-0000-000000000904"
DISABLED_OPERATOR_ID = "a0000000-0000-0000-0000-000000000905"
REVOKED_OPERATOR_ID = "a0000000-0000-0000-0000-000000000906"
EXPIRED_OPERATOR_ID = "a0000000-0000-0000-0000-000000000907"
OWNER_SESSION_HASH = "b" * 64
PARTNER_SESSION_HASH = "c" * 64
MULTI_SESSION_HASH = "d" * 64
LEGACY_SESSION_HASH = "e" * 64
DISABLED_SESSION_HASH = "f" * 64
REVOKED_SESSION_HASH = "a" * 64
EXPIRED_SESSION_HASH = "9" * 64


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def docker_sql(container: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "-t", "-A",
            "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(container: str) -> None:
    for _ in range(100):
        result = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def enable_forced_rls(container: str) -> None:
    tables = (
        "operator_session",
        "operator_identity",
        "operator_scope_grant",
        "operator_organization_membership",
        "location_organization_share",
        "location",
        "location_tenant_owner_verification",
        "organization",
    )
    rls_sql = "\n".join(
        f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;"
        for table in tables
    )
    docker_sql(
        container,
        rls_sql
        + """
        CREATE POLICY operator_context_probe_scope
            ON public.operator_context_probe
            FOR SELECT TO kokonut_runtime
            USING (
                EXISTS (
                    SELECT 1
                      FROM kokonut_security.current_tenant_context() AS context
                     WHERE context.tenant_id = operator_context_probe.tenant_id
                       AND context.actor_type = 'operator'
                )
            );
        GRANT SELECT ON public.operator_context_probe TO kokonut_runtime;
        ALTER TABLE public.operator_context_probe ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.operator_context_probe FORCE ROW LEVEL SECURITY;
        """,
    )


def run_acceptance(container: str) -> list[str]:
    app_assertions = f"""
    SET ROLE kokonut_runtime;
    BEGIN;
    DO $$
    DECLARE
        context_row RECORD;
        row_count INTEGER;
        key_denied BOOLEAN := FALSE;
    BEGIN
        BEGIN
            PERFORM secret FROM kokonut_security.mobile_context_hmac_key;
        EXCEPTION WHEN insufficient_privilege THEN
            key_denied := TRUE;
        END;
        IF NOT key_denied THEN
            RAISE EXCEPTION 'runtime role read the private context-signing key';
        END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{OWNER_SESSION_HASH}', '{OWNER_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'read', '[]'::jsonb
          );
        IF NOT FOUND THEN RAISE EXCEPTION 'valid owner context was denied'; END IF;
        IF context_row.tenant_id IS DISTINCT FROM '{OWNER_ORG_ID}'::uuid
           OR context_row.actor_id IS DISTINCT FROM '{OWNER_OPERATOR_ID}'::uuid
           OR context_row.actor_type IS DISTINCT FROM 'operator' THEN
            RAISE EXCEPTION 'valid owner context returned incorrect claims';
        END IF;
        SELECT count(*) INTO row_count FROM public.operator_context_probe;
        IF row_count <> 1 OR
           (SELECT value FROM public.operator_context_probe) <> 'owner-row' THEN
            RAISE EXCEPTION 'forced RLS did not filter to the owner tenant row';
        END IF;

        PERFORM set_config('kokonut.tenant_id', '{PARTNER_ORG_ID}', TRUE);
        SELECT count(*) INTO row_count FROM public.operator_context_probe;
        IF row_count <> 1 THEN
            RAISE EXCEPTION 'caller-controlled diagnostic GUC changed signed visibility';
        END IF;
        PERFORM set_config(
            'kokonut.context_payload',
            (current_setting('kokonut.context_payload')::jsonb
                || jsonb_build_object('tenant_id', '{PARTNER_ORG_ID}'))::text,
            TRUE
        );
        SELECT count(*) INTO row_count
          FROM kokonut_security.current_tenant_context();
        IF row_count <> 0 THEN
            RAISE EXCEPTION 'tampered context payload passed HMAC verification';
        END IF;
        SELECT count(*) INTO row_count FROM public.operator_context_probe;
        IF row_count <> 0 THEN
            RAISE EXCEPTION 'tampered context retained tenant visibility';
        END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{PARTNER_SESSION_HASH}', '{PARTNER_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'review', '[]'::jsonb
          );
        IF NOT FOUND THEN RAISE EXCEPTION 'active share did not establish partner context'; END IF;
        IF context_row.tenant_id IS DISTINCT FROM '{PARTNER_ORG_ID}'::uuid
           OR (SELECT value FROM public.operator_context_probe) <> 'partner-row' THEN
            RAISE EXCEPTION 'partner context exposed an incorrect tenant';
        END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{MULTI_SESSION_HASH}', '{MULTI_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'read',
              '[{{"resource":"report_snapshot","action":"read"}}]'::jsonb
          );
        IF FOUND THEN RAISE EXCEPTION 'cross-tenant required scopes were accepted'; END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{LEGACY_SESSION_HASH}', '{LEGACY_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'legacy_read', '[]'::jsonb
          );
        IF FOUND THEN RAISE EXCEPTION 'legacy NULL-tenant grant was accepted'; END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{DISABLED_SESSION_HASH}', '{DISABLED_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'read', '[]'::jsonb
          );
        IF FOUND THEN RAISE EXCEPTION 'disabled operator identity was accepted'; END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{REVOKED_SESSION_HASH}', '{REVOKED_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'read', '[]'::jsonb
          );
        IF FOUND THEN RAISE EXCEPTION 'revoked operator session was accepted'; END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              '{EXPIRED_SESSION_HASH}', '{EXPIRED_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'expired_share', '[]'::jsonb
          );
        IF FOUND THEN RAISE EXCEPTION 'expired session/share was accepted'; END IF;

        SELECT * INTO context_row
          FROM kokonut_security.set_operator_tenant_context(
              repeat('0', 64), '{OWNER_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'read', '[]'::jsonb
          );
        IF FOUND THEN RAISE EXCEPTION 'unknown session token hash was accepted'; END IF;

        SELECT count(*) INTO row_count
          FROM kokonut_security.current_tenant_context();
        IF row_count <> 0 THEN RAISE EXCEPTION 'denial retained signed context'; END IF;
        SELECT count(*) INTO row_count FROM public.operator_context_probe;
        IF row_count <> 0 THEN RAISE EXCEPTION 'denial retained tenant visibility'; END IF;
    END;
    $$;
    COMMIT;
    """
    docker_sql(container, app_assertions)

    docker_sql(
        container,
        f"""
        UPDATE public.location_organization_share
           SET revoked_at = NOW()
         WHERE location_id = '{LOCATION_ID}'
           AND organization_id = '{PARTNER_ORG_ID}'
           AND revoked_at IS NULL;
        """,
    )
    docker_sql(
        container,
        f"""
        SET ROLE kokonut_runtime;
        BEGIN;
        DO $$
        DECLARE context_row RECORD; row_count INTEGER;
        BEGIN
            SELECT * INTO context_row
              FROM kokonut_security.set_operator_tenant_context(
                  '{PARTNER_SESSION_HASH}', '{PARTNER_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
                  'farm_activity', 'review', '[]'::jsonb
              );
            IF FOUND THEN RAISE EXCEPTION 'revoked location share remained authorized'; END IF;
            SELECT count(*) INTO row_count FROM kokonut_security.current_tenant_context();
            IF row_count <> 0 THEN RAISE EXCEPTION 'revoked share retained signed context'; END IF;
        END;
        $$;
        COMMIT;
        """,
    )

    first_command = [
        "docker", "exec", "-i", container, "psql", "-X", "-qAt",
        "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ]
    first_sql = f"""
        SET application_name = 'kokonut-operator-context-lock-holder';
        SET ROLE kokonut_runtime;
        BEGIN;
        SELECT tenant_id
          FROM kokonut_security.set_operator_tenant_context(
              '{OWNER_SESSION_HASH}', '{OWNER_OPERATOR_ID}'::uuid, '{LOCATION_ID}'::uuid,
              'farm_activity', 'read', '[]'::jsonb
          );
        SELECT pg_sleep(2);
        COMMIT;
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        holder = pool.submit(run, first_command, input_text=first_sql)
        for _ in range(40):
            active = docker_sql(
                container,
                """SELECT count(*) FROM pg_stat_activity
                    WHERE application_name = 'kokonut-operator-context-lock-holder'
                      AND query LIKE 'SELECT pg_sleep%';""",
            ).strip()
            if active == "1":
                break
            time.sleep(0.05)
        else:
            holder.result(timeout=10)
            raise RuntimeError("could not observe the signed-context lock holder")
        docker_sql(
            container,
            f"""
            BEGIN;
            SET LOCAL lock_timeout = '150ms';
            DO $$
            DECLARE blocked BOOLEAN := FALSE;
            BEGIN
                BEGIN
                    UPDATE public.operator_scope_grant SET revoked_at = NOW()
                     WHERE operator_id = '{OWNER_OPERATOR_ID}'
                       AND resource = 'farm_activity' AND action = 'read'
                       AND revoked_at IS NULL;
                EXCEPTION WHEN lock_not_available THEN
                    blocked := TRUE;
                END;
                IF NOT blocked THEN
                    RAISE EXCEPTION 'scope revocation did not wait for the active tenant context';
                END IF;
            END;
            $$;
            ROLLBACK;
            """,
        )
        holder.result(timeout=10)

    docker_sql(
        container,
        """
        SET ROLE kokonut_runtime;
        BEGIN;
        DO $$
        DECLARE row_count INTEGER;
        BEGIN
            SELECT count(*) INTO row_count FROM public.operator_context_probe;
            IF row_count <> 0 THEN RAISE EXCEPTION 'transaction-local context survived commit'; END IF;
        END;
        $$;
        COMMIT;
        """,
    )
    return [
        "current owner session and tenant-qualified grant establish signed forced-RLS context",
        "active location share plus operator membership and grant establish partner context",
        "cross-tenant required scopes, legacy grants, disabled identity, revoked/expired sessions, and expired share are denied",
        "denied scope clears prior signed context and application row visibility",
        "caller-controlled GUC and tampered HMAC payload cannot forge tenant visibility",
        "share revocation immediately removes shared tenant context",
        "share locks serialize grant revocation against an active signed context",
        "transaction end clears signed context",
        "runtime role cannot read the private context-signing key",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"kokonut-operator-context-{uuid.uuid4().hex[:10]}"
    started = False
    try:
        run(
            [
                "docker", "run", "--detach", "--rm", "--network", "none",
                "--name", container,
                "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
                "postgres:16",
            ]
        )
        started = True
        wait_ready(container)
        docker_sql(container, FIXTURE.read_text())
        migration_sql = MIGRATION.read_text()
        docker_sql(container, migration_sql)
        docker_sql(container, migration_sql)
        enable_forced_rls(container)
        checks = run_acceptance(container)
        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with Docker networking disabled",
            "migrations": [
                "394_signed_operator_tenant_context.sql",
                "394_signed_operator_tenant_context.sql (idempotency replay)",
            ],
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "external_network_requests": 0,
            "candidate_application_table_rls_enabled": False,
            "disposable_forced_rls": True,
            "synthetic_rows_remaining": 0,
            "scope_limit": "Validates the OIDC operator context function and signed tenant accessor under synthetic forced RLS. Runtime session-table isolation, API-key context, workers, Directus, legacy CLI, and candidate RLS rollout remain open.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - show isolated acceptance failures.
        print(f"OPERATOR TENANT CONTEXT ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        if started:
            logs = subprocess.run(
                ["docker", "logs", container],
                text=True,
                capture_output=True,
                check=False,
            )
            if logs.stdout or logs.stderr:
                print("DISPOSABLE POSTGRES LOGS:", file=sys.stderr)
                print(logs.stdout, file=sys.stderr, end="")
                print(logs.stderr, file=sys.stderr, end="")
        return 1
    finally:
        if started:
            subprocess.run(
                ["docker", "stop", container],
                text=True,
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
