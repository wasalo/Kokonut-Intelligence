#!/usr/bin/env python3
"""Exercise runtime scoped-write ACL revocation on a disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

POSTGRES_IMAGE = (
    "postgis/postgis:16-3.4@sha256:"
    "44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs/refactor/builds/2026-10-26-recovery/"
    "runtime-scoped-write-boundary-disposable.json"
)


def run(command: list[str], *, timeout: int = 90) -> str:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        safe_command = [
            "<redacted>" if item.startswith("POSTGRES_PASSWORD=") else item
            for item in command
        ]
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed: {' '.join(safe_command)}\n{details}")
    return result.stdout


def wait_for_database(host: str, port: int, password: str) -> None:
    deadline = time.monotonic() + 60
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            with psycopg2.connect(
                host=host,
                port=port,
                dbname="postgres",
                user="postgres",
                password=password,
                connect_timeout=3,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() == (1,):
                        return
        except psycopg2.Error as exc:
            last_error = type(exc).__name__
            time.sleep(0.25)
    raise RuntimeError(f"disposable PostgreSQL did not become ready ({last_error})")


def _relation_privileges(connection, table: str) -> tuple[bool, bool, bool, bool]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT has_table_privilege('kokonut_runtime', %s, 'SELECT'),
                      has_table_privilege('kokonut_runtime', %s, 'INSERT'),
                      has_table_privilege('kokonut_runtime', %s, 'UPDATE'),
                      has_table_privilege('kokonut_runtime', %s, 'DELETE')""",
            (f"public.{table}",) * 4,
        )
        return cursor.fetchone()


def check_boundary() -> dict[str, object]:
    from services.migration import runtime_role

    container = f"kokonut-runtime-acl-{uuid.uuid4().hex[:12]}"
    password = secrets.token_urlsafe(32)
    host = "127.0.0.1"
    created = False
    try:
        run(
            [
                "docker", "run", "--pull=never", "--detach", "--rm",
                "--name", container,
                "--publish", "127.0.0.1::5432",
                "--env", f"POSTGRES_PASSWORD={password}",
                POSTGRES_IMAGE,
            ]
        )
        created = True
        published = run(["docker", "port", container, "5432/tcp"]).strip()
        port = int(published.rsplit(":", 1)[1])
        wait_for_database(host, port, password)

        connection = psycopg2.connect(
            host=host,
            port=port,
            dbname="postgres",
            user="postgres",
            password=password,
            connect_timeout=5,
        )
        try:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE ROLE kokonut_runtime NOLOGIN NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
                relations = tuple(
                    dict.fromkeys(
                        (*runtime_role._RUNTIME_PRIVATE_TABLES,
                         *runtime_role._RUNTIME_MUTATION_TABLES)
                    )
                )
                for table in relations:
                    cursor.execute(
                        sql.SQL("CREATE TABLE {} (id uuid PRIMARY KEY, marker text)").format(
                            sql.Identifier("public", table)
                        )
                    )
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    "IN SCHEMA public TO kokonut_runtime"
                )

            with connection.cursor() as cursor:
                result = runtime_role._apply_scoped_write_boundary(
                    cursor, sql.Identifier("kokonut_runtime")
                )
            if set(result["relations"]) != set(relations) or not all(
                result["relations"].values()
            ):
                raise AssertionError("the provisioner did not visit every ACL relation")
            with connection.cursor() as cursor:
                runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")

            private_denied = 0
            for table in runtime_role._RUNTIME_PRIVATE_TABLES:
                if _relation_privileges(connection, table) != (False, False, False, False):
                    raise AssertionError(f"private runtime access remains on {table}")
                private_denied += 1

            mutation_denied = 0
            for table in runtime_role._RUNTIME_MUTATION_TABLES:
                select, insert, update, delete = _relation_privileges(connection, table)
                if (select, insert, update, delete) != (True, False, False, False):
                    raise AssertionError(f"mutation boundary is wrong on {table}")
                mutation_denied += 1

            with connection.cursor() as cursor:
                cursor.execute("GRANT SELECT (marker) ON public.ai_summary_review_decision TO kokonut_runtime")
            try:
                with connection.cursor() as cursor:
                    runtime_role._verify_scoped_write_boundary(cursor, "kokonut_runtime")
            except RuntimeError as exc:
                if "column privileges" not in str(exc):
                    raise
            else:
                raise AssertionError("the verifier missed a residual private column grant")

            return {
                "result": "passed",
                "engine": "PostgreSQL 16, pinned postgis image",
                "database_scope": "temporary container, empty database, synthetic relation definitions",
                "tables_exercised": len(relations),
                "private_tables_without_runtime_access": private_denied,
                "mutation_only_tables_select_only": mutation_denied,
                "column_level_privilege_regression_detected": True,
                "bounded_gateway_function_behavior": "not exercised; source migrations are not installed",
            }
        finally:
            connection.close()
    finally:
        if created:
            run(["docker", "rm", "--force", container])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    evidence = check_boundary()
    evidence["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(args.output)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
