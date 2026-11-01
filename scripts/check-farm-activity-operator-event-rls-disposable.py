#!/usr/bin/env python3
"""Accept migration 728 signed-location RLS on a disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLIENT_IMAGE = os.environ.get(
    "FARM_ACTIVITY_OPERATOR_EVENT_RLS_CLIENT_IMAGE",
    "kokonut-kernel-candidate-app:latest",
)

# Keep this checker independent of repository secrets and external services.
os.environ.setdefault("KOKONUT_ENV", "development")
os.environ.setdefault("KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT", "true")

OPERATOR_FIXTURE = ROOT / "tests/fixtures/operator_tenant_context_disposable.sql"
MOBILE_ROLE_FIXTURE = ROOT / "tests/fixtures/operator_session_mobile_role_boundary.sql"
ACTIVITY_FIXTURE = ROOT / "tests/fixtures/farm_activity_operator_event_rls_disposable.sql"
SCOPE_FUNCTION_MIGRATION = ROOT / "schemas/postgres/711_location_energy_reading_capture.sql"
RUNTIME_MIGRATIONS = tuple(
    ROOT / "schemas/postgres" / name
    for name in (
        "391_mobile_device_tenant_binding.sql",
        "392_mobile_credential_functions.sql",
        "393_mobile_tenant_context_proof.sql",
        "394_signed_operator_tenant_context.sql",
        "395_operator_session_auth_boundary.sql",
        "396_signed_gateway_credential_tenant_context.sql",
        "398_bounded_mobile_device_revocation.sql",
        "399_runtime_security_schema_usage.sql",
        "400_operator_auth_security_schema_usage.sql",
    )
)
ACTIVITY_MIGRATION = ROOT / "schemas/postgres/404_gateway_farm_activity_operations.sql"
MIGRATION = ROOT / "schemas/postgres/728_farm_activity_operator_event_signed_location_rls.sql"
DEFAULT_OUTPUT = Path("/private/tmp/farm-activity-operator-event-rls-728-disposable.json")

LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "a0000000-0000-0000-0000-000000000002"
ORG_A = "a0000000-0000-0000-0000-000000000801"
ORG_B = "a0000000-0000-0000-0000-000000000802"
OPERATOR_A = "a0000000-0000-0000-0000-000000000901"
OPERATOR_B = "a0000000-0000-0000-0000-000000000902"
SESSION_A = "b" * 64
SESSION_B = "c" * 64


def _docker() -> str:
    executable = shutil.which("docker")
    if executable:
        return executable
    desktop_cli = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if desktop_cli.is_file():
        return str(desktop_cli)
    raise RuntimeError("Docker CLI is unavailable")


def _run(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        safe_command = [
            f"{item.split('=', 1)[0]}=<redacted>"
            if "PASSWORD=" in item
            else item
            for item in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(safe_command)}\n{details}"
        )
    return result


def _docker_sql(docker: str, container: str, statement: str) -> str:
    result = _run(
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


def _canonical_operator_scope_grant_function_sql() -> str:
    """Load the exact current implementation from its canonical migration."""
    migration_sql = SCOPE_FUNCTION_MIGRATION.read_text()
    start_marker = "CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows("
    end_marker = "GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)"
    start = migration_sql.index(start_marker)
    end = migration_sql.index(end_marker, start)
    return migration_sql[start:end].strip()


def _wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 90
    successes = 0
    while time.monotonic() < deadline:
        ready = _run(
            [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
            check=False,
        )
        if ready.returncode == 0:
            successes += 1
            if successes >= 4:
                return
        else:
            successes = 0
        time.sleep(0.5)
    raise RuntimeError("disposable PostgreSQL 16 did not become stably ready")


def _connect(host: str, port: int, username: str, password: str):
    return psycopg2.connect(
        host=host,
        port=port,
        dbname="postgres",
        user=username,
        password=password,
        connect_timeout=5,
    )


def _reapply_runtime_event_boundary(
    host: str, port: int, admin_password: str, runtime_password: str
) -> tuple[tuple[bool, bool], tuple[tuple, ...]]:
    """Exercise the exact ACL helper called by the full runtime provisioner."""
    from services.migration import runtime_role

    connection = _connect(host, port, "postgres", admin_password)
    try:
        role_ident = runtime_role.sql.Identifier("kokonut_runtime")
        with connection.cursor() as cursor:
            runtime_role._ensure_login_role(
                cursor,
                name="kokonut_runtime",
                identifier=role_ident,
                password=runtime_password,
            )
            runtime_role._remove_role_memberships(
                cursor,
                role_name="kokonut_runtime",
                identifier=role_ident,
            )
            cursor.execute(
                "GRANT ALL PRIVILEGES ON TABLE public.farm_activity_operator_event "
                "TO kokonut_runtime"
            )
            cursor.execute(
                "GRANT INSERT (reason), UPDATE (reason), REFERENCES (id) "
                "ON TABLE public.farm_activity_operator_event TO kokonut_runtime"
            )
            runtime_role._apply_farm_activity_operator_event_boundary(cursor, role_ident)
            runtime_role._verify_farm_activity_operator_event_boundary(
                cursor, "kokonut_runtime"
            )
        connection.commit()
        _assert_runtime_acl(connection)
        first_snapshot = _relation_policy_snapshot(connection)
        if first_snapshot[0] != (True, True):
            raise AssertionError(f"forced RLS flags are missing: {first_snapshot[0]}")
        if len(first_snapshot[1]) != 4:
            raise AssertionError(f"expected four bounded RLS policies, found {first_snapshot[1]}")

        with connection.cursor() as cursor:
            cursor.execute(
                "GRANT ALL PRIVILEGES ON TABLE public.farm_activity_operator_event "
                "TO kokonut_runtime"
            )
            cursor.execute(
                "GRANT INSERT (reason), UPDATE (reason), REFERENCES (id) "
                "ON TABLE public.farm_activity_operator_event TO kokonut_runtime"
            )
            runtime_role._apply_farm_activity_operator_event_boundary(cursor, role_ident)
            runtime_role._verify_farm_activity_operator_event_boundary(
                cursor, "kokonut_runtime"
            )
        connection.commit()
        _assert_runtime_acl(connection)
        reapply_snapshot = _relation_policy_snapshot(connection)
        if reapply_snapshot != first_snapshot:
            raise AssertionError(
                "runtime event boundary helper changed forced-RLS flags or policy contract"
            )
        return first_snapshot
    finally:
        connection.rollback()
        connection.close()


def _relation_policy_snapshot(connection) -> tuple[tuple[bool, bool], tuple[tuple, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relation.relrowsecurity, relation.relforcerowsecurity
                 FROM pg_catalog.pg_class AS relation
                 JOIN pg_catalog.pg_namespace AS namespace
                   ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relname = 'farm_activity_operator_event'"""
        )
        flags = cursor.fetchone()
        if flags is None:
            raise AssertionError("farm_activity_operator_event is missing")
        cursor.execute(
            """SELECT policyname, permissive, roles, cmd, qual, with_check
                 FROM pg_catalog.pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'farm_activity_operator_event'
                ORDER BY policyname"""
        )
        policies = tuple(cursor.fetchall())
    return (bool(flags[0]), bool(flags[1])), policies


def _assert_runtime_acl(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'SELECT'),
                      has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'INSERT'),
                      has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'UPDATE'),
                      has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'DELETE'),
                      has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'TRUNCATE'),
                      has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'REFERENCES'),
                      has_table_privilege('kokonut_runtime',
                       'public.farm_activity_operator_event', 'TRIGGER')"""
        )
        if cursor.fetchone() != (True, False, False, False, False, False, False):
            raise AssertionError("runtime access to the event ledger is no longer SELECT-only")
        cursor.execute(
            """SELECT attribute.attname,
                      has_column_privilege(
                          'kokonut_runtime', relation.oid, attribute.attname, 'SELECT'
                      ),
                      has_column_privilege(
                          'kokonut_runtime', relation.oid, attribute.attname, 'INSERT'
                      ),
                      has_column_privilege(
                          'kokonut_runtime', relation.oid, attribute.attname, 'UPDATE'
                      ),
                      has_column_privilege(
                          'kokonut_runtime', relation.oid, attribute.attname, 'REFERENCES'
                      )
                 FROM pg_catalog.pg_class AS relation
                 JOIN pg_catalog.pg_namespace AS namespace
                   ON namespace.oid = relation.relnamespace
                 JOIN pg_catalog.pg_attribute AS attribute
                   ON attribute.attrelid = relation.oid
                WHERE namespace.nspname = 'public'
                  AND relation.relname = 'farm_activity_operator_event'
                  AND attribute.attnum > 0
                  AND NOT attribute.attisdropped"""
        )
        if any(not select or insert or update or references for _, select, insert, update, references in cursor.fetchall()):
            raise AssertionError("runtime retains an unexpected column-level event-ledger privilege")


def _set_operator_context(connection, *, session_hash: str, operator_id: str, location_id: str, action: str, extra_scopes=()) -> None:
    scopes = [{"resource": resource, "action": scope_action} for resource, scope_action in extra_scopes]
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
                 FROM kokonut_security.set_operator_tenant_context(
                     %s, %s::uuid, %s::uuid, 'farm_activity', %s, %s::jsonb
                 )""",
            (session_hash, operator_id, location_id, action, json.dumps(scopes)),
        )
        row = cursor.fetchone()
    if row is None or row[1] != location_id or row[2] != operator_id or row[3] != "operator":
        raise AssertionError("database did not establish the expected signed operator location context")


def _set_workflow(connection, *, operator_id: str, action: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT set_config('kokonut.actor_id', %s, TRUE),
                      set_config('kokonut.actor_type', 'operator', TRUE),
                      set_config('kokonut.workflow_action', %s, TRUE),
                      set_config('kokonut.workflow_reason', '', TRUE)""",
            (operator_id, action),
        )


def _create_gateway_activity(connection, *, session_hash: str, operator_id: str, location_id: str) -> str:
    _set_operator_context(
        connection,
        session_hash=session_hash,
        operator_id=operator_id,
        location_id=location_id,
        action="create_draft",
        extra_scopes=(("farm_activity", "read_detail"),),
    )
    _set_workflow(connection, operator_id=operator_id, action="draft_created")
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO public.farm_activity (
                       location_id, activity_type, activity_date, status,
                       schema_version, source_system, created_by, updated_by
                   ) VALUES (
                       %s::uuid, 'weeding', DATE '2026-10-15', 'draft',
                       'gateway_v1', 'kokonut_gateway', %s::uuid, %s::uuid
                   )
                   RETURNING id::text""",
            (location_id, operator_id, operator_id),
        )
        activity_id = cursor.fetchone()[0]
    connection.commit()
    return activity_id


def _submit_gateway_activity(connection, *, session_hash: str, operator_id: str, location_id: str, activity_id: str) -> None:
    _set_operator_context(
        connection,
        session_hash=session_hash,
        operator_id=operator_id,
        location_id=location_id,
        action="submit",
    )
    _set_workflow(connection, operator_id=operator_id, action="submitted")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.farm_activity SET status = 'submitted' WHERE id = %s::uuid",
            (activity_id,),
        )
        if cursor.rowcount != 1:
            raise AssertionError("signed submit did not update its Gateway activity")
    connection.commit()


def _visible_events(
    connection, *, session_hash: str, operator_id: str, location_id: str
) -> list[tuple[str, str, str]]:
    _set_operator_context(
        connection,
        session_hash=session_hash,
        operator_id=operator_id,
        location_id=location_id,
        action="read_detail",
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT farm_activity_id::text, location_id::text, action
                 FROM public.farm_activity_operator_event
                ORDER BY location_id, created_at, id"""
        )
        return cursor.fetchall()


def _assert_runtime_rls(
    host: str, port: int, admin_password: str, runtime_password: str
) -> list[str]:
    checks: list[str] = []
    runtime = _connect(host, port, "kokonut_runtime", runtime_password)
    try:
        with runtime.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.farm_activity_operator_event")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("event ledger was visible without signed tenant context")
            cursor.execute("SELECT set_config('kokonut.location_id', %s, TRUE)", (LOCATION_A,))
            cursor.execute("SELECT count(*) FROM public.farm_activity_operator_event")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("caller-controlled diagnostic GUC exposed ledger rows")
            cursor.execute(
                "SELECT set_config('kokonut.context_payload', %s, TRUE), "
                "set_config('kokonut.context_signature', %s, TRUE), "
                "set_config('kokonut.actor_id', %s, TRUE), "
                "set_config('kokonut.actor_type', 'operator', TRUE)",
                (
                    json.dumps(
                        {
                            "backend_pid": 0,
                            "transaction_id": "0",
                            "tenant_id": ORG_A,
                            "location_id": LOCATION_A,
                            "actor_id": OPERATOR_A,
                            "actor_type": "operator",
                            "nonce": "forged",
                        }
                    ),
                    "0" * 64,
                    OPERATOR_A,
                ),
            )
            cursor.execute("SELECT count(*) FROM public.farm_activity_operator_event")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("caller-forged signed-context GUCs exposed ledger rows")
        runtime.rollback()
        checks.append("no-context, diagnostic-GUC, and forged signed-context reads return no event rows")

        activity_a = _create_gateway_activity(
            runtime, session_hash=SESSION_A, operator_id=OPERATOR_A, location_id=LOCATION_A
        )
        activity_b = _create_gateway_activity(
            runtime, session_hash=SESSION_B, operator_id=OPERATOR_B, location_id=LOCATION_B
        )
        _submit_gateway_activity(
            runtime,
            session_hash=SESSION_A,
            operator_id=OPERATOR_A,
            location_id=LOCATION_A,
            activity_id=activity_a,
        )
        checks.append("SECURITY DEFINER create/update triggers append ledger events under forced RLS")

        admin = _connect(host, port, "postgres", admin_password)
        try:
            for statement in (
                "UPDATE public.farm_activity_operator_event "
                "SET reason = 'tampered' WHERE farm_activity_id = %s::uuid",
                "DELETE FROM public.farm_activity_operator_event "
                "WHERE farm_activity_id = %s::uuid",
            ):
                try:
                    with admin.cursor() as cursor:
                        cursor.execute(statement, (activity_a,))
                except psycopg2.Error as exc:
                    if exc.pgcode != "P0001":
                        raise AssertionError(
                            f"append-only protection raised unexpected SQLSTATE {exc.pgcode}"
                        ) from exc
                    admin.rollback()
                else:
                    raise AssertionError("event ledger trigger allowed a privileged direct mutation")
        finally:
            admin.close()
        checks.append("append-only trigger rejects even privileged direct UPDATE and DELETE")

        visible_a = _visible_events(
            runtime, session_hash=SESSION_A, operator_id=OPERATOR_A, location_id=LOCATION_A
        )
        if len(visible_a) != 2 or any(
            activity_id != activity_a or location_id != LOCATION_A
            for activity_id, location_id, _ in visible_a
        ):
            raise AssertionError(f"location A did not see exactly its own two audit events: {visible_a}")
        with runtime.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.farm_activity_operator_event "
                "WHERE farm_activity_id = %s::uuid",
                (activity_b,),
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("signed location A context exposed location B events")
        runtime.rollback()
        checks.append("signed location A reads its audit history and cannot read location B")

        visible_b = _visible_events(
            runtime, session_hash=SESSION_B, operator_id=OPERATOR_B, location_id=LOCATION_B
        )
        if len(visible_b) != 1 or visible_b[0][:2] != (activity_b, LOCATION_B):
            raise AssertionError(f"location B did not see only its own event: {visible_b}")
        with runtime.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.farm_activity_operator_event "
                "WHERE farm_activity_id = %s::uuid",
                (activity_a,),
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("signed location B context exposed location A events")
        runtime.rollback()
        checks.append("signed location B reads its audit history and cannot read location A")

        with runtime.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.farm_activity_operator_event")
            if cursor.fetchone()[0] != 0:
                raise AssertionError("transaction rollback retained signed ledger visibility")
        checks.append("rollback clears signed context before the next transaction")

        for statement in (
            "INSERT INTO public.farm_activity_operator_event "
            "(farm_activity_id, location_id, actor_operator_id, action, to_status) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, 'draft_created', 'draft')",
            "UPDATE public.farm_activity_operator_event SET reason = 'tampered' WHERE id = %s::uuid",
            "DELETE FROM public.farm_activity_operator_event WHERE id = %s::uuid",
        ):
            try:
                with runtime.cursor() as cursor:
                    if statement.startswith("INSERT"):
                        cursor.execute(statement, (activity_a, LOCATION_A, OPERATOR_A))
                    else:
                        cursor.execute(statement, (activity_a,))
            except psycopg2.Error as exc:
                runtime.rollback()
                if exc.pgcode != "42501":
                    raise AssertionError(f"unexpected direct mutation error {exc.pgcode}") from exc
            else:
                runtime.rollback()
                raise AssertionError("runtime unexpectedly mutated the append-only event ledger")
        checks.append("runtime remains SELECT-only; direct ledger INSERT, UPDATE, and DELETE are denied")
    finally:
        runtime.rollback()
        runtime.close()
    return checks


def _check_database(
    host: str,
    port: int,
    admin_password: str,
    runtime_password: str,
) -> dict[str, object]:
    _reapply_runtime_event_boundary(host, port, admin_password, runtime_password)

    checks = _assert_runtime_rls(host, port, admin_password, runtime_password)
    return {
        "result": "passed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": "PostgreSQL 16 disposable container and client on an internal-only Docker network",
        "migration": MIGRATION.name,
        "scope_grant_function_source": SCOPE_FUNCTION_MIGRATION.name,
        "migration_replay": "applied twice",
        "runtime_role_provisioning": (
            "event boundary helper applied twice after synthetic compatibility-wide "
            "table and column DML grants; SELECT-only ACL and RLS policies preserved"
        ),
        "forced_rls": True,
        "checks": [
            "migration applies and replays idempotently",
            "uses the exact canonical operator_scope_grant_allows body from migration 711",
            "migration removes synthetic stale table-level and column-level runtime writes",
            "runtime provisioner event-boundary helper clears table and column writes and preserves forced-RLS policies",
            *checks,
        ],
        "candidate_database_touched": False,
        "legacy_database_touched": False,
        "external_network_requests": 0,
        "container_network_external_routing": False,
        "host_ports_published": False,
        "persistent_database_touched": False,
        "scope_limit": (
            "Uses a minimal compatible schema with the real migration-394 signed operator context, migration-404 "
            "farm-activity triggers, and migration-728 event-ledger policies. It does not enable RLS on the parent "
            "farm_activity table or establish populated candidate/production parity."
        ),
    }


def _client_main() -> int:
    try:
        host = os.environ["FARM_ACTIVITY_OPERATOR_EVENT_RLS_DATABASE_HOST"]
        port = int(os.environ.get("FARM_ACTIVITY_OPERATOR_EVENT_RLS_DATABASE_PORT", "5432"))
        admin_password = os.environ["FARM_ACTIVITY_OPERATOR_EVENT_RLS_ADMIN_PASSWORD"]
        runtime_password = os.environ["FARM_ACTIVITY_OPERATOR_EVENT_RLS_RUNTIME_PASSWORD"]
        report = _check_database(host, port, admin_password, runtime_password)
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - acceptance must report SQL and infrastructure failures.
        print(f"FARM ACTIVITY OPERATOR EVENT RLS CLIENT FAILED: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--client", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.client:
        return _client_main()

    docker = _docker()
    container = f"kokonut-farm-activity-event-rls-{uuid.uuid4().hex[:10]}"
    network = f"{container}-internal"
    admin_password = secrets.token_urlsafe(24)
    runtime_password = secrets.token_urlsafe(24)
    started = False
    network_started = False
    try:
        _run([docker, "image", "inspect", "postgres:16"])
        _run([docker, "image", "inspect", CLIENT_IMAGE])
        _run([docker, "network", "create", "--internal", network])
        network_started = True
        _run(
            [
                docker,
                "run",
                "--detach",
                "--rm",
                "--pull=never",
                "--name",
                container,
                "--network",
                network,
                "--network-alias",
                "database",
                "--env",
                f"POSTGRES_PASSWORD={admin_password}",
                "postgres:16",
            ]
        )
        started = True
        _wait_ready(docker, container)

        _docker_sql(docker, container, OPERATOR_FIXTURE.read_text())
        _docker_sql(docker, container, MOBILE_ROLE_FIXTURE.read_text())
        for migration in RUNTIME_MIGRATIONS:
            _docker_sql(docker, container, migration.read_text())
        _docker_sql(docker, container, ACTIVITY_FIXTURE.read_text())
        _docker_sql(docker, container, _canonical_operator_scope_grant_function_sql())
        _docker_sql(docker, container, ACTIVITY_MIGRATION.read_text())
        _docker_sql(
            docker,
            container,
            "GRANT ALL PRIVILEGES ON TABLE public.farm_activity_operator_event "
            "TO kokonut_runtime; "
            "GRANT INSERT (reason), UPDATE (reason), REFERENCES (id) "
            "ON TABLE public.farm_activity_operator_event TO kokonut_runtime;",
        )
        migration_sql = MIGRATION.read_text()
        _docker_sql(docker, container, migration_sql)
        _docker_sql(docker, container, migration_sql)

        client_result = _run(
            [
                docker,
                "run",
                "--pull=never",
                "--rm",
                "--network",
                network,
                "--mount",
                f"type=bind,source={ROOT},target=/workspace,readonly",
                "--workdir",
                "/workspace",
                "--env",
                "FARM_ACTIVITY_OPERATOR_EVENT_RLS_DATABASE_HOST=database",
                "--env",
                "FARM_ACTIVITY_OPERATOR_EVENT_RLS_DATABASE_PORT=5432",
                "--env",
                f"FARM_ACTIVITY_OPERATOR_EVENT_RLS_ADMIN_PASSWORD={admin_password}",
                "--env",
                f"FARM_ACTIVITY_OPERATOR_EVENT_RLS_RUNTIME_PASSWORD={runtime_password}",
                CLIENT_IMAGE,
                "python3",
                "scripts/check-farm-activity-operator-event-rls-disposable.py",
                "--client",
            ],
            timeout=900,
        )
        try:
            report = json.loads(client_result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("disposable PostgreSQL client returned invalid evidence") from exc
        if report.get("result") != "passed":
            raise RuntimeError("disposable PostgreSQL client did not report acceptance success")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - acceptance must report SQL and infrastructure failures.
        print(f"FARM ACTIVITY OPERATOR EVENT RLS ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        if started:
            logs = subprocess.run([docker, "logs", container], text=True, capture_output=True, check=False)
            if logs.stdout or logs.stderr:
                print("DISPOSABLE POSTGRES LOGS:", file=sys.stderr)
                print(logs.stdout, file=sys.stderr, end="")
                print(logs.stderr, file=sys.stderr, end="")
        return 1
    finally:
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)
        if network_started:
            subprocess.run([docker, "network", "rm", network], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
