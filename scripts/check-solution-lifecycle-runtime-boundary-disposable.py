#!/usr/bin/env python3
"""Replay migration 727 and exercise bounded solution lifecycle writers."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import types
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIGRATION = ROOT / "schemas/postgres/727_runtime_solution_lifecycle_read_only.sql"
IMAGE = os.environ.get(
    "SOLUTION_LIFECYCLE_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
CLIENT_IMAGE = os.environ.get(
    "SOLUTION_LIFECYCLE_ACL_CLIENT_IMAGE", "kokonut-kernel-candidate-app:latest"
)
TARGETS = ("solution", "solution_lifecycle_event")
MUTATING_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def run(
    command: list[str], *, timeout: int = 120, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:5])} …\n{details}"
        )
    return result


def _connect(host: str, port: int, password: str, database: str = "postgres"):
    deadline = time.monotonic() + 90
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            connection = psycopg2.connect(
                host=host,
                port=port,
                dbname=database,
                user="postgres",
                password=password,
                connect_timeout=3,
            )
            connection.autocommit = True
            return connection
        except psycopg2.Error as exc:
            last_error = type(exc).__name__
            time.sleep(0.25)
    raise RuntimeError(f"disposable PostgreSQL did not become ready ({last_error})")


def _split_sql_statements(source: str) -> list[str]:
    """Split psql-style input without cutting quoted or dollar-quoted bodies."""
    statements: list[str] = []
    current: list[str] = []
    index = 0
    single_quote = False
    single_quote_escape = False
    double_quote = False
    dollar_tag: str | None = None
    line_comment = False
    block_comment_depth = 0

    while index < len(source):
        if line_comment:
            char = source[index]
            current.append(char)
            index += 1
            if char == "\n":
                line_comment = False
            continue

        if block_comment_depth:
            if source.startswith("/*", index):
                current.append("/*")
                block_comment_depth += 1
                index += 2
            elif source.startswith("*/", index):
                current.append("*/")
                block_comment_depth -= 1
                index += 2
            else:
                current.append(source[index])
                index += 1
            continue

        if dollar_tag is not None:
            if source.startswith(dollar_tag, index):
                current.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
            else:
                current.append(source[index])
                index += 1
            continue

        char = source[index]
        if single_quote:
            current.append(char)
            index += 1
            if single_quote_escape and char == "\\" and index < len(source):
                current.append(source[index])
                index += 1
            elif char == "'":
                if index < len(source) and source[index] == "'":
                    current.append(source[index])
                    index += 1
                else:
                    single_quote = False
                    single_quote_escape = False
            continue

        if double_quote:
            current.append(char)
            index += 1
            if char == '"':
                if index < len(source) and source[index] == '"':
                    current.append(source[index])
                    index += 1
                else:
                    double_quote = False
            continue

        if source.startswith("--", index):
            current.append("--")
            index += 2
            line_comment = True
        elif source.startswith("/*", index):
            current.append("/*")
            index += 2
            block_comment_depth = 1
        elif char == "'":
            previous = source[index - 1] if index else " "
            before_prefix = source[index - 2] if index > 1 else " "
            single_quote_escape = (
                previous in "Ee"
                and (index < 2 or not (before_prefix.isalnum() or before_prefix == "_"))
            )
            single_quote = True
            current.append(char)
            index += 1
        elif char == '"':
            double_quote = True
            current.append(char)
            index += 1
        elif char == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", source[index:])
            if match:
                dollar_tag = match.group(0)
                current.append(dollar_tag)
                index += len(dollar_tag)
            else:
                current.append(char)
                index += 1
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current.clear()
            index += 1
        else:
            current.append(char)
            index += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def _execute(connection, statement: str) -> str:
    output: list[str] = []
    for sql_statement in _split_sql_statements(statement):
        with connection.cursor() as cursor:
            cursor.execute(sql_statement)
            if cursor.description:
                output.extend(
                    "\t".join("" if value is None else str(value) for value in row)
                    for row in cursor.fetchall()
                )
    return "\n".join(output)


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load disposable acceptance helper {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_psql_helpers(module, connection, seen: set[int] | None = None) -> None:
    if seen is None:
        seen = set()
    if not isinstance(module, types.ModuleType) or id(module) in seen:
        return
    seen.add(id(module))
    source = getattr(module, "__file__", "")
    if source.startswith(str(ROOT / "scripts")) and hasattr(module, "psql"):
        module.psql = lambda *args, **kwargs: _execute(connection, args[-1])
    for value in vars(module).values():
        if isinstance(value, types.ModuleType):
            _patch_psql_helpers(value, connection, seen)


def _create_probe_roles_and_grants(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_maintenance_probe') THEN "
            "CREATE ROLE kokonut_maintenance_probe NOLOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; END IF; END $$"
        )
        cursor.execute(
            "GRANT USAGE ON SCHEMA public TO kokonut_runtime, "
            "kokonut_directus_runtime, kokonut_maintenance_probe"
        )
        for relation in TARGETS:
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
                    "ON TABLE public.{} TO kokonut_runtime, kokonut_directus_runtime, "
                    "kokonut_maintenance_probe"
                ).format(sql.Identifier(relation))
            )
        columns_by_relation = {}
        for relation in TARGETS:
            cursor.execute(
                "SELECT attname FROM pg_catalog.pg_attribute "
                "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped",
                (f"public.{relation}",),
            )
            columns_by_relation[relation] = {row[0] for row in cursor.fetchall()}

        def pick(relation: str, candidates: tuple[str, ...]) -> str:
            return next(
                (column for column in candidates if column in columns_by_relation[relation]),
                None,
            )

        solution_insert = pick("solution", ("canonical_key", "id"))
        solution_update = pick("solution", ("current_stage", "status", "id"))
        event_insert = pick("solution_lifecycle_event", ("rationale", "to_stage", "id"))
        event_update = pick("solution_lifecycle_event", ("rationale", "to_stage", "id"))
        if not all((solution_insert, solution_update, event_insert, event_update)):
            raise AssertionError("solution fixtures lack columns for standalone runtime grants")
        cursor.execute(
            sql.SQL(
                "GRANT INSERT ({insert_column}), REFERENCES ({reference_column}), "
                "UPDATE ({update_column}) ON TABLE public.solution TO kokonut_runtime"
            ).format(
                insert_column=sql.Identifier(solution_insert),
                reference_column=sql.Identifier(solution_insert),
                update_column=sql.Identifier(solution_update),
            )
        )
        cursor.execute(
            sql.SQL(
                "GRANT INSERT ({insert_column}), REFERENCES ({reference_column}), "
                "UPDATE ({update_column}) ON TABLE public.solution_lifecycle_event "
                "TO kokonut_runtime"
            ).format(
                insert_column=sql.Identifier(event_insert),
                reference_column=sql.Identifier(event_insert),
                update_column=sql.Identifier(event_update),
            )
        )


def _apply_migration(connection, migration_sql: str) -> None:
    _execute(connection, migration_sql)


def _reapply_runtime_provisioner(connection) -> None:
    from services.migration import runtime_role

    with connection.cursor() as cursor:
        applied = runtime_role._apply_scoped_write_boundary(
            cursor, sql.Identifier("kokonut_runtime")
        )
        runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
    for relation in TARGETS:
        if applied["relations"].get(relation) is not True:
            raise AssertionError(f"runtime provisioner did not reapply {relation} denial")


def _assert_acl(connection, *, functions: tuple[str, ...], owners: tuple[tuple[str, str, str, str], ...]) -> None:
    with connection.cursor() as cursor:
        for relation in TARGETS:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_runtime', %s, 'SELECT'), "
                + ", ".join(
                    "has_table_privilege('kokonut_runtime', %s, %s)"
                    for _ in MUTATING_PRIVILEGES
                ),
                (f"public.{relation}", *(
                    value
                    for privilege in MUTATING_PRIVILEGES
                    for value in (f"public.{relation}", privilege)
                )),
            )
            if cursor.fetchone() != (True, *(False for _ in MUTATING_PRIVILEGES)):
                raise AssertionError(f"runtime table privileges incorrect for {relation}")

            cursor.execute(
                "SELECT attname FROM pg_catalog.pg_attribute "
                "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped",
                (f"public.{relation}",),
            )
            columns = [row[0] for row in cursor.fetchall()]
            for column in columns:
                cursor.execute(
                    "SELECT has_column_privilege('kokonut_runtime', %s, %s, 'INSERT'), "
                    "has_column_privilege('kokonut_runtime', %s, %s, 'UPDATE'), "
                    "has_column_privilege('kokonut_runtime', %s, %s, 'REFERENCES')",
                    (f"public.{relation}", column) * 3,
                )
                if cursor.fetchone() != (False, False, False):
                    raise AssertionError(f"runtime column DML remains on {relation}.{column}")

            cursor.execute("SET ROLE kokonut_runtime")
            cursor.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(relation)))
            cursor.fetchone()
            cursor.execute("RESET ROLE")

        cursor.execute(
            "SELECT has_function_privilege('kokonut_runtime', signature, 'EXECUTE') "
            "FROM unnest(%s::text[]) AS signature",
            (list(functions),),
        )
        if [row[0] for row in cursor.fetchall()] != [True] * len(functions):
            raise AssertionError("migration removed an existing runtime function grant")

        for relation in TARGETS:
            cursor.execute(
                "SELECT has_table_privilege('kokonut_directus_runtime', %s, 'SELECT'), "
                "has_table_privilege('kokonut_directus_runtime', %s, 'INSERT'), "
                "has_table_privilege('kokonut_directus_runtime', %s, 'UPDATE'), "
                "has_table_privilege('kokonut_directus_runtime', %s, 'DELETE'), "
                "has_table_privilege('kokonut_maintenance_probe', %s, 'INSERT'), "
                "has_table_privilege('kokonut_maintenance_probe', %s, 'UPDATE'), "
                "has_table_privilege('kokonut_maintenance_probe', %s, 'DELETE')",
                (f"public.{relation}",) * 7,
            )
            if cursor.fetchone() != (True, True, True, True, True, True, True):
                raise AssertionError(f"Directus or maintenance grants changed for {relation}")

    with connection.cursor() as cursor:
        cursor.execute("BEGIN")
        try:
            cursor.execute("SET ROLE kokonut_runtime")
            for relation, update_column in (
                ("solution", "current_stage"),
                ("solution_lifecycle_event", "rationale"),
            ):
                statements = (
                    (
                        "INSERT",
                        sql.SQL("INSERT INTO public.{} DEFAULT VALUES").format(
                            sql.Identifier(relation)
                        ),
                    ),
                    (
                        "UPDATE",
                        sql.SQL("UPDATE public.{} SET {} = {} WHERE FALSE").format(
                            sql.Identifier(relation),
                            sql.Identifier(update_column),
                            sql.Identifier(update_column),
                        ),
                    ),
                    (
                        "DELETE",
                        sql.SQL("DELETE FROM public.{} WHERE FALSE").format(
                            sql.Identifier(relation)
                        ),
                    ),
                )
                for operation, statement in statements:
                    cursor.execute("SAVEPOINT direct_write_probe")
                    try:
                        cursor.execute(statement)
                    except psycopg2.errors.InsufficientPrivilege:
                        cursor.execute("ROLLBACK TO SAVEPOINT direct_write_probe")
                    else:
                        cursor.execute("ROLLBACK TO SAVEPOINT direct_write_probe")
                        raise AssertionError(
                            f"runtime {operation} unexpectedly succeeded on {relation}"
                        )
                    cursor.execute("RELEASE SAVEPOINT direct_write_probe")
            cursor.execute("RESET ROLE")
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    with connection.cursor() as cursor:
        for role, relation, column, privilege in owners:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s, %s, %s)",
                (role, f"public.{relation}", column, privilege),
            )
            if cursor.fetchone()[0] is not True:
                raise AssertionError(
                    f"bounded owner grant was lost: {role} {privilege} {relation}.{column}"
                )


def _compatibility_setup(connection) -> None:
    _create_probe_roles_and_grants(connection)
    migration_sql = MIGRATION.read_text(encoding="utf-8")
    _apply_migration(connection, migration_sql)
    _apply_migration(connection, migration_sql)
    _reapply_runtime_provisioner(connection)


def _prepare_solution_schema(connection) -> None:
    _execute(connection, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    _execute(
        connection,
        """
        ALTER TABLE public.solution
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE public.solution
            ADD COLUMN IF NOT EXISTS canonical_key TEXT,
            ADD COLUMN IF NOT EXISTS name TEXT,
            ADD COLUMN IF NOT EXISTS solution_type TEXT,
            ADD COLUMN IF NOT EXISTS problem_statement TEXT,
            ADD COLUMN IF NOT EXISTS theory_of_change TEXT,
            ADD COLUMN IF NOT EXISTS baseline_alternative TEXT,
            ADD COLUMN IF NOT EXISTS originating_scope_type TEXT,
            ADD COLUMN IF NOT EXISTS originating_scope_id UUID,
            ADD COLUMN IF NOT EXISTS created_by_party_id UUID,
            ADD COLUMN IF NOT EXISTS risk_class TEXT,
            ADD COLUMN IF NOT EXISTS reversibility TEXT,
            ADD COLUMN IF NOT EXISTS retired_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE public.solution_adopter_readiness
            ADD COLUMN IF NOT EXISTS assessed_by_party_id UUID;
        ALTER TABLE public.solution_configuration
            ADD COLUMN IF NOT EXISTS approved_by_party_id UUID;
        ALTER TABLE public.solution_lifecycle_event
            ADD COLUMN IF NOT EXISTS from_stage TEXT,
            ADD COLUMN IF NOT EXISTS to_stage TEXT,
            ADD COLUMN IF NOT EXISTS rationale TEXT,
            ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::JSONB,
            ADD COLUMN IF NOT EXISTS actor_party_id UUID,
            ADD COLUMN IF NOT EXISTS approved_by_party_id UUID,
            ADD COLUMN IF NOT EXISTS rollback_plan TEXT;
        """,
    )


def _lifecycle_functions(connection) -> dict[str, object]:
    retirement = _load_script(
        "solution_retirement_runtime_boundary",
        ROOT / "scripts/check-solution-retirement-execution-disposable.py",
    )
    creation = _load_script(
        "solution_create_runtime_boundary",
        ROOT / "scripts/check-solution-create-disposable.py",
    )
    nonpromotion = _load_script(
        "solution_nonpromotion_runtime_boundary",
        ROOT / "scripts/check-solution-nonpromotion-stage-transition-disposable.py",
    )
    for module in (retirement, creation, nonpromotion):
        _patch_psql_helpers(module, connection)

    retirement.apply_ordered_lifecycle_chain("embedded", "embedded")
    _prepare_solution_schema(connection)

    for module in (nonpromotion, creation):
        migration_sql = module.MIGRATION.read_text(encoding="utf-8")
        _apply_migration(connection, migration_sql)
        _apply_migration(connection, migration_sql)

    _apply_migration(
        connection,
        (ROOT / "schemas/postgres/714_runtime_location_solution_creation_receipt_private.sql")
        .read_text(encoding="utf-8"),
    )

    _compatibility_setup(connection)
    _execute(connection, creation.ACTOR_FIXTURE)
    _execute(connection, creation.ACCEPTANCE)
    _execute(connection, nonpromotion.ACTOR_FIXTURE)
    _execute(connection, nonpromotion.ACCEPTANCE)
    _execute(connection, retirement.RETIREMENT_ACTOR_FIXTURE)
    _execute(connection, retirement.RETIREMENT_EXECUTION_ACCEPTANCE)

    return {
        "result": "passed",
        "bounded_operations": [
            "solution creation and exact retry",
            "nonpromotion stage transition and exact retry",
            "independent retirement, sunset, review, and exact retries",
        ],
        "migration_apply_and_replay": "passed",
        "runtime_provisioner_reapplication": "passed",
    }


def _gate_flow(connection) -> dict[str, object]:
    checker = _load_script(
        "solution_gate_transition_runtime_boundary",
        ROOT / "scripts/check-solution-gate-evaluation-disposable.py",
    )
    _patch_psql_helpers(checker, connection)
    gate_check = checker.gate_check
    summary_check = checker.summary_check

    _execute(connection, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    _execute(connection, gate_check.FIXTURE)
    _apply_migration(connection, summary_check.MIGRATION.read_text(encoding="utf-8"))
    _execute(connection, gate_check.ACCEPTANCE)
    gate_migration = gate_check.MIGRATION.read_text(encoding="utf-8")
    _apply_migration(connection, gate_migration)
    _apply_migration(connection, gate_migration)
    _execute(connection, gate_check.GATE_ACCEPTANCE)

    _execute(connection, checker.EVALUATOR_FIXTURE)
    migration_sql = checker.MIGRATION.read_text(encoding="utf-8")
    _apply_migration(connection, migration_sql)
    _apply_migration(connection, migration_sql)
    _execute(connection, checker.EVALUATION_ACCEPTANCE)

    review_sql = checker.REVIEW_MIGRATION.read_text(encoding="utf-8")
    _apply_migration(connection, review_sql)
    _apply_migration(connection, review_sql)

    compatibility_sql = checker.COMPATIBILITY_MIGRATION.read_text(encoding="utf-8")
    _apply_migration(connection, compatibility_sql)
    _apply_migration(connection, compatibility_sql)
    _execute(connection, checker.GATE_REVIEW_ACCEPTANCE)

    transition_sql = checker.TRANSITION_MIGRATION.read_text(encoding="utf-8")
    _apply_migration(connection, transition_sql)
    _apply_migration(connection, transition_sql)
    _compatibility_setup(connection)
    _execute(connection, checker.TRANSITION_PREP)
    _execute(connection, checker.NONHUMAN_TRANSITION_ACCEPTANCE)

    old_read_denial = """    denied := false;
    BEGIN PERFORM 1 FROM public.solution_lifecycle_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read lifecycle event evidence'; END IF;"""
    new_read_assertion = """    IF NOT has_table_privilege(
        'kokonut_runtime', 'public.solution_lifecycle_event', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'runtime lifecycle event SELECT was not preserved';
    END IF;
    PERFORM 1 FROM public.solution_lifecycle_event LIMIT 1;"""
    acceptance = checker.TRANSITION_ACCEPTANCE.replace(
        old_read_denial, new_read_assertion
    )
    if acceptance == checker.TRANSITION_ACCEPTANCE:
        raise RuntimeError("could not adapt legacy gate assertion for retained event SELECT")
    _execute(connection, acceptance)

    return {
        "result": "passed",
        "bounded_operations": ["approved gate transition and exact retry"],
        "migration_apply_and_replay": "passed",
        "runtime_provisioner_reapplication": "passed",
    }


def check_database(
    host: str, port: int, password: str, *, flow: str
) -> dict[str, object]:
    connection = _connect(host, port, password)
    try:
        if flow == "lifecycle":
            flow_result = _lifecycle_functions(connection)
            functions = (
                "kokonut_security.create_location_solution(uuid,uuid,text,text,text,text,text,text,text,text,text,jsonb,boolean)",
                "kokonut_security.transition_location_solution_stage(uuid,uuid,text,text,uuid,text,jsonb,text,boolean)",
                "kokonut_security.transition_location_solution_retirement(uuid,uuid,uuid,text,text,jsonb,timestamp with time zone)",
            )
            owners = (
                ("kokonut_solution_creator_owner", "solution", "canonical_key", "INSERT"),
                ("kokonut_solution_creator_owner", "solution_lifecycle_event", "solution_id", "INSERT"),
                ("kokonut_solution_nonpromotion_transition_owner", "solution", "current_stage", "UPDATE"),
                ("kokonut_solution_nonpromotion_transition_owner", "solution_lifecycle_event", "solution_id", "INSERT"),
                ("kokonut_solution_retirement_execution_owner", "solution", "retired_at", "UPDATE"),
                ("kokonut_solution_retirement_execution_owner", "solution_lifecycle_event", "solution_id", "INSERT"),
            )
            _assert_acl(connection, functions=functions, owners=owners)
        elif flow == "gate":
            flow_result = _gate_flow(connection)
            functions = (
                "kokonut_security.transition_location_solution_gate(uuid,uuid,uuid,text,jsonb,text)",
            )
            owners = (
                ("kokonut_solution_gate_transitioner", "solution", "current_stage", "UPDATE"),
                ("kokonut_solution_gate_transitioner", "solution_lifecycle_event", "solution_id", "INSERT"),
            )
            _assert_acl(connection, functions=functions, owners=owners)
        else:
            raise ValueError(f"unknown solution lifecycle flow: {flow}")

        return {
            "result": "passed",
            "flow": flow,
            "migration": MIGRATION.name,
            "candidate_or_legacy_modified": False,
            "runtime_select": "preserved",
            "runtime_table_and_column_writes": "denied after migration and provisioner reapplication",
            "directus_and_maintenance_grants": "preserved",
            "function_owner_write_grants": "preserved",
            "runtime_function_execute_grants": "preserved",
            "bounded_operations": flow_result,
            "network": "internal-only",
            "host_ports_published": False,
        }
    finally:
        connection.close()


def check_client() -> dict[str, object]:
    lifecycle_host = os.environ.get(
        "SOLUTION_LIFECYCLE_ACL_LIFECYCLE_HOST", ""
    ).strip()
    gate_host = os.environ.get("SOLUTION_LIFECYCLE_ACL_GATE_HOST", "").strip()
    password = os.environ.get("SOLUTION_LIFECYCLE_ACL_DATABASE_PASSWORD", "")
    try:
        port = int(os.environ.get("SOLUTION_LIFECYCLE_ACL_DATABASE_PORT", "5432"))
    except ValueError as exc:
        raise RuntimeError("invalid disposable database port") from exc
    if not lifecycle_host or not gate_host or not password or not 1 <= port <= 65535:
        raise RuntimeError("disposable database client configuration is incomplete")
    lifecycle_result = check_database(
        lifecycle_host, port, password, flow="lifecycle"
    )
    gate_result = check_database(gate_host, port, password, flow="gate")
    return {
        "ok": True,
        "migration": MIGRATION.name,
        "database_target": "two isolated disposable PostgreSQL 16 clusters",
        "candidate_or_legacy_modified": False,
        "runtime_select": "preserved on both relations",
        "runtime_table_and_column_writes": "denied after migration and provisioner reapplication",
        "directus_and_maintenance_grants": "preserved",
        "function_owner_write_grants": "preserved",
        "runtime_function_execute_grants": "preserved",
        "lifecycle_acceptance": lifecycle_result,
        "gate_acceptance": gate_result,
        "network": "internal-only",
        "host_ports_published": False,
    }


def check() -> dict[str, object]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is required for the disposable PostgreSQL check")
    run([docker, "image", "inspect", CLIENT_IMAGE], timeout=30)
    run([docker, "image", "inspect", IMAGE], timeout=30)

    network = f"kokonut-solution-lifecycle-acl-net-{uuid.uuid4().hex[:10]}"
    lifecycle_container = f"kokonut-solution-lifecycle-acl-{uuid.uuid4().hex[:10]}"
    gate_container = f"kokonut-solution-gate-acl-{uuid.uuid4().hex[:10]}"
    password = uuid.uuid4().hex + uuid.uuid4().hex
    network_created = False
    started_containers: list[str] = []
    try:
        run([docker, "network", "create", "--internal", network])
        network_created = True
        for container, alias in (
            (lifecycle_container, "lifecycle-database"),
            (gate_container, "gate-database"),
        ):
            run(
                [
                    docker, "run", "--pull=never", "--detach", "--rm", "--name", container,
                    "--network", network, "--network-alias", alias,
                    "--env", f"POSTGRES_PASSWORD={password}", IMAGE,
                ],
                timeout=60,
            )
            started_containers.append(container)
        client_result = run(
            [
                docker, "run", "--pull=never", "--rm", "--network", network,
                "--mount", f"type=bind,source={ROOT},target=/workspace,readonly",
                "--workdir", "/workspace",
                "--env", "SOLUTION_LIFECYCLE_ACL_LIFECYCLE_HOST=lifecycle-database",
                "--env", "SOLUTION_LIFECYCLE_ACL_GATE_HOST=gate-database",
                "--env", "SOLUTION_LIFECYCLE_ACL_DATABASE_PORT=5432",
                "--env", f"SOLUTION_LIFECYCLE_ACL_DATABASE_PASSWORD={password}",
                CLIENT_IMAGE, "python3",
                "scripts/check-solution-lifecycle-runtime-boundary-disposable.py",
                "--client",
            ],
            timeout=900,
        )
        try:
            evidence = json.loads(client_result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("disposable PostgreSQL client returned invalid evidence") from exc
        if evidence.get("ok") is not True:
            raise RuntimeError("disposable PostgreSQL client did not report success")
        return evidence
    finally:
        for container in started_containers:
            run([docker, "rm", "--force", container], check=False)
        if network_created:
            run([docker, "network", "rm", network], check=False)


def main() -> int:
    result = check_client() if "--client" in sys.argv[1:] else check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"solution lifecycle runtime ACL check failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
