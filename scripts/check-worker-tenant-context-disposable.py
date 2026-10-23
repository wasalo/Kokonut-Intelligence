#!/usr/bin/env python3
"""Exercise signed worker tenant context in isolated disposable PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
MIGRATION = ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql"
AGENT_SAFETY_MIGRATION = ROOT / "schemas/postgres/578_authenticated_agent_safety_trigger.sql"
AGENT_SAFETY_INSERT_MIGRATION = ROOT / "schemas/postgres/579_agent_safety_insert_guard.sql"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-22-recovery/cap-038-agent-safety-insert-disposable.json"
)
WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
OTHER_TENANT_ID = "a0000000-0000-0000-0000-000000000802"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
RESOURCE = "sensor_reading"
ACTION = "process"
RAW_CREDENTIAL = "synthetic-worker-credential-2026-10-16-not-production"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()


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
        safe_command = [
            "POSTGRES_PASSWORD=<redacted>" if part.startswith("POSTGRES_PASSWORD=") else part
            for part in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
        ],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 60
    successes = 0
    while time.monotonic() < deadline:
        check = subprocess.run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become stably ready")


def connect(port: int, user: str, password: str):
    return psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user=user,
        password=password,
        connect_timeout=5,
    )


def set_context(connection, *, location_id=LOCATION_ID, resource=RESOURCE, action=ACTION):
    from services.common.tenant_context import set_worker_tenant_context

    return set_worker_tenant_context(
        connection,
        credential=RAW_CREDENTIAL,
        location_id=location_id,
        resource=resource,
        action=action,
    )


def assert_no_context(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
        cursor.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
        if cursor.fetchone()[0] != 0:
            raise AssertionError("denied or transaction-ended worker scope remained active")


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")

    image = os.getenv("WORKER_CONTEXT_TEST_IMAGE", "postgres:16")
    container = f"kokonut-worker-tenant-context-{os.getpid()}-{secrets.token_hex(3)}"
    admin_password = secrets.token_urlsafe(24)
    worker_password = "worker-execution-fixture"
    runtime_password = "worker-runtime-fixture"
    output = DEFAULT_OUTPUT
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])

    created = False
    checks: list[str] = []
    try:
        run(
            [
                docker,
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-e",
                f"POSTGRES_PASSWORD={admin_password}",
                "-p",
                "127.0.0.1::5432",
                image,
            ]
        )
        created = True
        wait_ready(docker, container)
        docker_sql(docker, container, FIXTURE.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        docker_sql(docker, container, MIGRATION.read_text(encoding="utf-8"))
        docker_sql(docker, container, AGENT_SAFETY_MIGRATION.read_text(encoding="utf-8"))
        docker_sql(docker, container, AGENT_SAFETY_MIGRATION.read_text(encoding="utf-8"))
        docker_sql(docker, container, AGENT_SAFETY_INSERT_MIGRATION.read_text(encoding="utf-8"))
        docker_sql(docker, container, AGENT_SAFETY_INSERT_MIGRATION.read_text(encoding="utf-8"))
        docker_sql(
            docker,
            container,
            f"""
            GRANT kokonut_worker_execution TO kokonut_worker_login
                WITH INHERIT FALSE, SET TRUE;
            INSERT INTO kokonut_security.worker_principal (id, principal_key)
            VALUES ('{WORKER_ID}', 'sensor-anomaly');
            INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
            VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
            INSERT INTO kokonut_security.worker_scope_grant (
                worker_id, tenant_id, location_id, resource, action, granted_by
            ) VALUES (
                '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
                '{RESOURCE}', '{ACTION}', 'disposable fixture'
            );
            GRANT SELECT, INSERT, UPDATE ON public.agent_safety_probe
                TO kokonut_worker_execution, kokonut_runtime;
            """,
        )
        mapped = run([docker, "port", container, "5432/tcp"]).strip().splitlines()
        if not mapped:
            raise RuntimeError("disposable PostgreSQL port mapping is missing")
        port = int(mapped[0].rsplit(":", 1)[1])

        worker = connect(port, "kokonut_worker_login", worker_password)
        runtime = connect(port, "kokonut_runtime", runtime_password)
        admin = connect(port, "postgres", admin_password)
        try:
            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_catalog.pg_trigger "
                    "WHERE tgrelid = 'public.agent_safety_probe'::pg_catalog.regclass "
                    "AND tgname = 'trg_agent_safety_insert' AND NOT tgisinternal"
                )
                if cursor.fetchone()[0] != 1:
                    raise AssertionError("migration replay did not leave exactly one insert trigger")
            checks.append("migration replay leaves one idempotent terminal-status insert trigger")

            context = set_context(worker)
            if (
                context.tenant_id != TENANT_ID
                or context.location_id != LOCATION_ID
                or context.actor_id != WORKER_ID
                or context.actor_type != "system_worker"
            ):
                raise AssertionError(f"valid worker grant returned incorrect scope: {context}")
            with worker.cursor() as cursor:
                cursor.execute(
                    "SELECT tenant_id::text, location_id::text, actor_id::text, resource, action "
                    "FROM kokonut_security.current_worker_scope(%s, %s)",
                    (RESOURCE, ACTION),
                )
                if cursor.fetchone() != (TENANT_ID, LOCATION_ID, WORKER_ID, RESOURCE, ACTION):
                    raise AssertionError("exact signed worker scope was not exposed")
                cursor.execute(
                    "SELECT count(*) FROM kokonut_security.current_worker_scope(%s, %s)",
                    (RESOURCE, "delete"),
                )
                if cursor.fetchone()[0] != 0:
                    raise AssertionError("worker scope accepted a different action")
                cursor.execute(
                    "SELECT set_config('kokonut.context_payload', "
                    "(current_setting('kokonut.context_payload')::jsonb "
                    "|| jsonb_build_object('action', 'delete'))::text, TRUE)"
                )
                cursor.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
                if cursor.fetchone()[0] != 0:
                    raise AssertionError("tampered worker payload passed signature validation")
            checks.append("valid exact worker grant signs tenant/location/actor and operation")
            checks.append("tampered worker context payload fails HMAC validation")

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL app.agent_id = ''")
                try:
                    cursor.execute(
                        "UPDATE public.agent_safety_probe SET status = 'verified' WHERE id = 1"
                    )
                except psycopg2.Error as exc:
                    worker.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    worker.rollback()
                    raise AssertionError(
                        "authenticated worker role changed a governed status without app.agent_id"
                    )
            checks.append(
                "authenticated worker role cannot verify governed records when app.agent_id is cleared"
            )

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL app.agent_id = ''")
                try:
                    cursor.execute(
                        "SELECT public.agent_safety_security_definer_update_probe(4, 'published')"
                    )
                except psycopg2.Error as exc:
                    worker.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    worker.rollback()
                    raise AssertionError(
                        "security-definer worker call bypassed governed lifecycle guard"
                    )
            checks.append(
                "worker session membership preserves lifecycle guard through a security-definer function"
            )

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute("UPDATE public.agent_safety_probe SET status = 'draft' WHERE id = 2")
            worker.commit()
            with runtime.cursor() as cursor:
                cursor.execute("SELECT status FROM public.agent_safety_probe WHERE id = 2")
                if cursor.fetchone()[0] != "draft":
                    raise AssertionError("worker could not perform a permitted non-terminal transition")
            checks.append("worker can perform allowed non-terminal governed status transitions")

            with runtime.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.agent_safety_probe SET status = 'verified' WHERE id = 1"
                )
            runtime.commit()
            checks.append("non-worker runtime retains the existing human lifecycle path")

            with runtime.cursor() as cursor:
                cursor.execute("SET LOCAL app.agent_id = 'synthetic-agent'")
                try:
                    cursor.execute(
                        "UPDATE public.agent_safety_probe SET status = 'published' WHERE id = 3"
                    )
                except psycopg2.Error as exc:
                    runtime.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    runtime.rollback()
                    raise AssertionError("legacy agent marker stopped restricting lifecycle escalation")
            checks.append("legacy app.agent_id marker remains restrictive for compatibility")

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL app.agent_id = ''")
                try:
                    cursor.execute(
                        "INSERT INTO public.agent_safety_probe (id, status) VALUES (5, 'verified')"
                    )
                except psycopg2.Error as exc:
                    worker.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    worker.rollback()
                    raise AssertionError("worker inserted a terminal-status governed record")
            checks.append("worker cannot insert a verified record when app.agent_id is cleared")

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL app.agent_id = ''")
                try:
                    cursor.execute(
                        "SELECT public.agent_safety_security_definer_insert_probe(6, 'published')"
                    )
                except psycopg2.Error as exc:
                    worker.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    worker.rollback()
                    raise AssertionError("security-definer worker call inserted a terminal status")
            checks.append("worker session membership protects terminal inserts through security-definer functions")

            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.agent_safety_probe (id, status) VALUES (7, 'draft')"
                )
            worker.commit()
            checks.append("worker can insert a draft governed record")

            with runtime.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.agent_safety_probe (id, status) VALUES (8, 'verified')"
                )
            runtime.commit()
            checks.append("non-worker runtime retains terminal human insert behavior")

            with runtime.cursor() as cursor:
                cursor.execute("SET LOCAL app.agent_id = 'synthetic-agent'")
                try:
                    cursor.execute(
                        "INSERT INTO public.agent_safety_probe (id, status) VALUES (9, 'published')"
                    )
                except psycopg2.Error as exc:
                    runtime.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    runtime.rollback()
                    raise AssertionError("legacy agent marker stopped restricting terminal inserts")
            checks.append("legacy app.agent_id marker also restricts terminal inserts")

            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                for statement in (
                    "SELECT * FROM kokonut_security.worker_credential",
                    "SELECT secret FROM kokonut_security.mobile_context_hmac_key",
                ):
                    try:
                        cursor.execute(statement)
                    except psycopg2.Error as exc:
                        worker.rollback()
                        if exc.pgcode != "42501":
                            raise
                        cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                    else:
                        worker.rollback()
                        raise AssertionError("worker execution role read a private credential table")
            checks.append("worker role cannot read credentials or the HMAC signing key")

            worker.rollback()
            set_context(worker)
            with worker.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('kokonut.context_payload'), "
                    "current_setting('kokonut.context_signature')"
                )
                prior_payload, prior_signature = cursor.fetchone()
            worker.commit()
            assert_no_context(worker)
            worker.commit()
            checks.append("signed worker context expires at transaction end")

            with worker.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                cursor.execute("SELECT set_config('kokonut.context_payload', %s, TRUE)", (prior_payload,))
                cursor.execute(
                    "SELECT set_config('kokonut.context_signature', %s, TRUE)",
                    (prior_signature,),
                )
                cursor.execute("SELECT count(*) FROM kokonut_security.current_tenant_context()")
                if cursor.fetchone()[0] != 0:
                    raise AssertionError("previous transaction's signed worker context was replayed")
            worker.rollback()
            checks.append("signed worker context cannot be replayed in a later transaction")

            denied_cases = [
                (OTHER_LOCATION_ID, RESOURCE, ACTION, "cross-location grant"),
                (LOCATION_ID, RESOURCE, "delete", "wrong action"),
                (LOCATION_ID, "platform_event", ACTION, "wrong resource"),
            ]
            for location, resource, action, label in denied_cases:
                try:
                    set_context(worker, location_id=location, resource=resource, action=action)
                except Exception as exc:
                    from services.common.tenant_context import TenantContextDenied

                    if not isinstance(exc, TenantContextDenied):
                        raise
                else:
                    raise AssertionError(f"worker unexpectedly received {label}")
                assert_no_context(worker)
                worker.rollback()
            checks.append("cross-location and non-exact resource/action grants fail closed")

            set_context(worker)
            try:
                set_context(worker, action="delete")
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("second denied setter call unexpectedly succeeded")
            assert_no_context(worker)
            worker.rollback()
            checks.append("a denied setter clears an earlier signed scope in the transaction")

            with runtime.cursor() as cursor:
                cursor.execute(
                    "SELECT has_function_privilege(current_user, "
                    "'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE')"
                )
                if cursor.fetchone()[0]:
                    raise AssertionError("shared runtime role can execute worker setter")
                try:
                    cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
                except psycopg2.Error as exc:
                    runtime.rollback()
                    if exc.pgcode != "42501":
                        raise
                else:
                    runtime.rollback()
                    raise AssertionError("shared runtime role can assume worker execution role")
            checks.append("shared runtime login cannot execute or assume worker execution role")

            set_context(worker)
            with admin.cursor() as cursor:
                try:
                    cursor.execute(
                        "SELECT id FROM kokonut_security.worker_scope_grant "
                        "WHERE worker_id = %s::uuid FOR UPDATE NOWAIT",
                        (WORKER_ID,),
                    )
                except psycopg2.Error as exc:
                    admin.rollback()
                    if exc.pgcode != "55P03":
                        raise
                else:
                    admin.rollback()
                    raise AssertionError("worker context did not retain its grant row lock")
            worker.rollback()
            checks.append("worker grant lock serializes revocation with an active context")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.location_tenant_owner_verification SET revoked_at = now() "
                    "WHERE location_id = %s::uuid AND revoked_at IS NULL",
                    (LOCATION_ID,),
                )
                cursor.execute(
                    "UPDATE public.location SET organization_id = %s::uuid WHERE id = %s::uuid",
                    (OTHER_TENANT_ID, LOCATION_ID),
                )
                cursor.execute(
                    "INSERT INTO public.location_tenant_owner_verification "
                    "(id, location_id, organization_id) VALUES "
                    "(gen_random_uuid(), %s::uuid, %s::uuid)",
                    (LOCATION_ID, OTHER_TENANT_ID),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("revoked grant survived owner transfer")
            assert_no_context(worker)
            worker.rollback()
            checks.append("owner transfer invalidates a still-active worker grant")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.location SET organization_id = %s::uuid WHERE id = %s::uuid",
                    (TENANT_ID, LOCATION_ID),
                )
                cursor.execute(
                    "INSERT INTO public.location_tenant_owner_verification "
                    "(id, location_id, organization_id) VALUES "
                    "(gen_random_uuid(), %s::uuid, %s::uuid)",
                    (LOCATION_ID, TENANT_ID),
                )
                cursor.execute(
                    "UPDATE public.location SET status = 'inactive' WHERE id = %s::uuid",
                    (LOCATION_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("inactive location remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("inactive location is denied")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.location SET status = 'active' WHERE id = %s::uuid",
                    (LOCATION_ID,),
                )
                cursor.execute(
                    "UPDATE public.organization SET status = 'inactive' WHERE id = %s::uuid",
                    (TENANT_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("inactive tenant remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("inactive owner tenant is denied")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.organization SET status = 'active' WHERE id = %s::uuid",
                    (TENANT_ID,),
                )
                cursor.execute(
                    "UPDATE kokonut_security.worker_scope_grant SET expires_at = now() - interval '1 second' "
                    "WHERE worker_id = %s::uuid",
                    (WORKER_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("expired worker scope grant remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("expired worker grant is denied")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE kokonut_security.worker_scope_grant SET expires_at = NULL "
                    "WHERE worker_id = %s::uuid",
                    (WORKER_ID,),
                )
                cursor.execute(
                    "UPDATE kokonut_security.worker_principal SET is_active = FALSE, "
                    "disabled_at = now() WHERE id = %s::uuid",
                    (WORKER_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("inactive worker principal remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("inactive worker principal is denied")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE kokonut_security.worker_principal SET is_active = TRUE, "
                    "disabled_at = NULL WHERE id = %s::uuid",
                    (WORKER_ID,),
                )
                cursor.execute(
                    "UPDATE kokonut_security.worker_credential SET expires_at = now() - interval '1 second' "
                    "WHERE worker_id = %s::uuid",
                    (WORKER_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("expired worker credential remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("expired worker credential is denied")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE kokonut_security.worker_credential SET expires_at = NULL "
                    "WHERE worker_id = %s::uuid",
                    (WORKER_ID,),
                )
                cursor.execute(
                    "UPDATE kokonut_security.worker_scope_grant SET revoked_at = now(), "
                    "revoked_by = 'fixture', revocation_reason = 'test' "
                    "WHERE worker_id = %s::uuid",
                    (WORKER_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("revoked worker grant remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("revoked worker grant is denied")

            with admin.cursor() as cursor:
                cursor.execute(
                    "UPDATE kokonut_security.worker_credential SET revoked_at = now(), "
                    "revoked_by = 'fixture', revocation_reason = 'test' "
                    "WHERE worker_id = %s::uuid",
                    (WORKER_ID,),
                )
            admin.commit()
            try:
                set_context(worker)
            except Exception as exc:
                from services.common.tenant_context import TenantContextDenied

                if not isinstance(exc, TenantContextDenied):
                    raise
            else:
                raise AssertionError("revoked worker credential remained authorized")
            assert_no_context(worker)
            worker.rollback()
            checks.append("revoked worker credential is denied")

            for connection in (worker, runtime, admin):
                connection.close()
        finally:
            for connection in (worker, runtime, admin):
                if not connection.closed:
                    connection.close()

        result = {
            "schema_version": 1,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scope": "Migration 405 signed worker context and migrations 578–579 authenticated agent lifecycle guard acceptance",
            "database": "isolated disposable PostgreSQL 16 container",
            "migration_files": [
                MIGRATION.relative_to(ROOT).as_posix(),
                AGENT_SAFETY_MIGRATION.relative_to(ROOT).as_posix(),
                AGENT_SAFETY_INSERT_MIGRATION.relative_to(ROOT).as_posix(),
            ],
            "migration_replay": "passed for migrations 405, 578, and 579",
            "command": "python3 scripts/check-worker-tenant-context-disposable.py",
            "container_network": "loopback-only published port; runner makes no external requests",
            "checks": [{"result": "passed", "description": item} for item in checks],
            "candidate_or_legacy_database_access": False,
            "worker_credential_printed": False,
            "limitations": [
                "Migrations 405, 578, and 579 ran against a minimal synthetic prior-schema fixture; the lifecycle triggers use one synthetic table instead of replaying all governed tables.",
                "No application-table RLS policy, handler integration, worker deployment, provider, candidate, or legacy database was changed or exercised.",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Worker tenant context acceptance passed ({len(checks)} checks): {output}")
        return 0
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
