#!/usr/bin/env python3
"""Verify migration 743's public EBF scorecard ACL in isolated PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2 import errors, sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATION = ROOT / "schemas/postgres/743_runtime_public_ebf_scorecard_read_only.sql"
IMAGE = os.environ.get(
    "PUBLIC_EBF_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
CLIENT_IMAGE = os.environ.get(
    "PUBLIC_EBF_ACL_CLIENT_IMAGE", "kokonut-kernel-candidate-app:latest"
)
RUNTIME = "kokonut_runtime"
RELATION = "v_public_ebf_scorecard"
PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")

FIXTURE = """
CREATE ROLE kokonut NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_public_probe NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE TABLE public.ebf_scorecard (id uuid PRIMARY KEY, location_id uuid NOT NULL);
CREATE TABLE public.location (id uuid PRIMARY KEY, name text NOT NULL);
CREATE VIEW public.v_public_ebf_scorecard AS
    SELECT scorecard.id AS scorecard_id, scorecard.location_id, location.name AS location_name
      FROM public.ebf_scorecard AS scorecard
      JOIN public.location AS location ON location.id = scorecard.location_id;
INSERT INTO public.location VALUES ('11111111-1111-4111-8111-111111111111', 'Synthetic location');
INSERT INTO public.ebf_scorecard VALUES
    ('22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111');
GRANT ALL PRIVILEGES ON TABLE public.v_public_ebf_scorecard TO PUBLIC;
GRANT INSERT (scorecard_id), UPDATE (location_name), REFERENCES (location_id)
    ON TABLE public.v_public_ebf_scorecard TO PUBLIC;
"""


def run(command: list[str], *, timeout: int = 90, check: bool = True):
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
    if check and result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command[:5])} …\n{detail}")
    return result


def _apply(connection, migration: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(migration)
    connection.commit()


def _assert_read_only(connection, role: str, *, context: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege(%s, %s, 'SELECT'), "
            + ", ".join("has_table_privilege(%s, %s, %s)" for _ in PRIVILEGES),
            (
                role,
                f"public.{RELATION}",
                *(value for privilege in PRIVILEGES for value in (role, f"public.{RELATION}", privilege)),
            ),
        )
        expected = (role in (RUNTIME, "kokonut_public_probe"), *(False for _ in PRIVILEGES))
        if cursor.fetchone() != expected:
            raise AssertionError(f"{role} table privileges are wrong after {context}")
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute "
            "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped "
            "AND (has_column_privilege(%s, %s, attname, 'INSERT') "
            "OR has_column_privilege(%s, %s, attname, 'UPDATE') "
            "OR has_column_privilege(%s, %s, attname, 'REFERENCES')))",
            (f"public.{RELATION}", role, f"public.{RELATION}", role, f"public.{RELATION}", role, f"public.{RELATION}"),
        )
        if cursor.fetchone()[0]:
            raise AssertionError(f"{role} retains column writes after {context}")
        if expected[0]:
            cursor.execute(f"SET ROLE {role}")
            cursor.execute(f"SELECT scorecard_id::text, location_name FROM public.{RELATION}")
            if cursor.fetchone() != ("22222222-2222-4222-8222-222222222222", "Synthetic location"):
                raise AssertionError(f"{role} SELECT projection changed or failed")
            cursor.execute("RESET ROLE")
    connection.commit()


def _expect_denied(connection, role: str, statement: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"SET ROLE {role}")
        cursor.execute("SAVEPOINT expected_acl_denial")
        try:
            cursor.execute(statement)
        except (errors.InsufficientPrivilege, errors.ObjectNotInPrerequisiteState):
            cursor.execute("ROLLBACK TO SAVEPOINT expected_acl_denial")
        else:
            raise AssertionError(f"{role} unexpectedly performed a scorecard view write")
        finally:
            cursor.execute("RESET ROLE")
    connection.commit()


def check_database(host: str, password: str) -> dict[str, object]:
    from services.migration import runtime_role

    connection = psycopg2.connect(
        host=host, port=5432, dbname="postgres", user="postgres",
        password=password, connect_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(FIXTURE)
        connection.commit()
        migration = MIGRATION.read_text(encoding="utf-8")

        _apply(connection, migration)
        _apply(connection, migration)
        _assert_read_only(connection, "kokonut_public_probe", context="role-absent replay")
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname = %s", (RUNTIME,))
            if cursor.fetchone()[0] != 0:
                raise AssertionError("migration unexpectedly created kokonut_runtime")

        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE ROLE {RUNTIME} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                f"NOREPLICATION NOBYPASSRLS; "
                f"GRANT ALL PRIVILEGES ON TABLE public.{RELATION} TO {RUNTIME}; "
                f"GRANT INSERT (scorecard_id), UPDATE (location_name), REFERENCES (location_id) "
                f"ON TABLE public.{RELATION} TO {RUNTIME}"
            )
        connection.commit()

        _apply(connection, migration)
        _apply(connection, migration)
        _assert_read_only(connection, "kokonut_public_probe", context="role-present replay")
        _assert_read_only(connection, RUNTIME, context="migration replay")
        for statement in (
            f"INSERT INTO public.{RELATION} (scorecard_id, location_id, location_name) "
            "VALUES ('33333333-3333-4333-8333-333333333333', "
            "'11111111-1111-4111-8111-111111111111', 'blocked')",
            f"UPDATE public.{RELATION} SET location_name = 'blocked'",
            f"DELETE FROM public.{RELATION}",
        ):
            _expect_denied(connection, RUNTIME, statement)

        with connection.cursor() as cursor:
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RUNTIME}"
            )
            result = runtime_role._apply_scoped_write_boundary(cursor, sql.Identifier(RUNTIME))
            runtime_role._verify_scoped_write_boundary(cursor, RUNTIME)
        connection.commit()
        if result["relations"].get(RELATION) is not True:
            raise AssertionError("runtime-role provisioner omitted the EBF scorecard view")
        _assert_read_only(connection, RUNTIME, context="runtime provisioner reapplication")
        for statement in (
            f"INSERT INTO public.{RELATION} (scorecard_id, location_id, location_name) "
            "VALUES ('44444444-4444-4444-8444-444444444444', "
            "'11111111-1111-4111-8111-111111111111', 'blocked')",
            f"UPDATE public.{RELATION} SET location_name = 'blocked'",
            f"DELETE FROM public.{RELATION}",
        ):
            _expect_denied(connection, RUNTIME, statement)

        return {
            "result": "passed",
            "migration": MIGRATION.name,
            "relation": f"public.{RELATION}",
            "migration_apply_and_replay_roles_absent": "passed",
            "migration_apply_and_replay_roles_present": "passed",
            "public_select_preserved_and_mutation_acl_denied": "passed",
            "runtime_select_and_dml_denial": "passed",
            "runtime_provisioner_reapplication": "passed",
            "view_non_updatable_guard": "passed",
            "candidate_legacy_production_touched": False,
        }
    finally:
        connection.rollback()
        connection.close()


def _published_ports(docker: str, container: str) -> list[dict[str, str]]:
    raw = run([docker, "inspect", "--format", "{{json .HostConfig.PortBindings}}", container]).stdout.strip()
    bindings = json.loads(raw) if raw else None
    return [
        {"container_port": str(port), "host_ip": str(entry.get("HostIp", "")), "host_port": str(entry.get("HostPort", ""))}
        for port, entries in (bindings.items() if isinstance(bindings, dict) else [])
        for entry in entries or [] if isinstance(entry, dict)
    ]


def _validated_migration_count() -> int:
    sys.path.insert(0, str(ROOT))
    from services.migration.cli import _discover_files, _validate_sources

    migrations = _discover_files(include_seeds=False)
    _validate_sources(migrations)
    if not any(migration["id"] == f"schema:{MIGRATION.name}" for migration in migrations):
        raise RuntimeError("migration 743 is missing from the ordered schema migrations")
    return len(migrations)


def check_client() -> dict[str, object]:
    host = os.environ.get("PUBLIC_EBF_ACL_DATABASE_HOST")
    password = os.environ.get("PUBLIC_EBF_ACL_DATABASE_PASSWORD")
    if not host or not password:
        raise RuntimeError("internal client mode requires database host and password")
    evidence = check_database(host, password)
    evidence["ordered_migration_sources_validated"] = _validated_migration_count()
    return evidence


def check() -> dict[str, object]:
    migration_count = _validated_migration_count()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is required for the isolated PostgreSQL acceptance")
    run([docker, "image", "inspect", IMAGE], timeout=30)
    run([docker, "image", "inspect", CLIENT_IMAGE], timeout=30)

    suffix = secrets.token_hex(5)
    database = f"kokonut-public-ebf-acl-{suffix}"
    client = f"{database}-client"
    network = f"{database}-net"
    password = secrets.token_urlsafe(32)
    network_created = database_created = client_created = False
    evidence: dict[str, object] | None = None
    cleanup = {"client_container_removed": True, "database_container_removed": True, "network_removed": True}
    try:
        run([docker, "network", "create", "--internal", network])
        network_created = True
        if run([docker, "network", "inspect", "--format", "{{.Internal}}", network]).stdout.strip().lower() != "true":
            raise RuntimeError("disposable network is not internal")
        run([docker, "run", "--pull=never", "--detach", "--name", database, "--network", network,
             "--network-alias", "database", "--env", f"POSTGRES_PASSWORD={password}", IMAGE])
        database_created = True
        if _published_ports(docker, database):
            raise RuntimeError("disposable PostgreSQL unexpectedly publishes a host port")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if run([docker, "exec", database, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], check=False).returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("isolated PostgreSQL did not become ready")
        run([docker, "create", "--name", client, "--network", network, "--volume", f"{ROOT}:/repo:ro",
             "--workdir", "/repo", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "KOKONUT_ENV=development",
             "--env", "KOKONUT_ENV_SECRETS_NOT_REQUIRED=true", "--env", "PUBLIC_EBF_ACL_DATABASE_HOST=database",
             "--env", f"PUBLIC_EBF_ACL_DATABASE_PASSWORD={password}", CLIENT_IMAGE,
             "python3", "scripts/check-public-ebf-scorecard-runtime-boundary-disposable.py", "--client-mode"])
        client_created = True
        if _published_ports(docker, client):
            raise RuntimeError("disposable client unexpectedly publishes a host port")
        result = run([docker, "start", "--attach", client], timeout=240)
        evidence = json.loads(result.stdout)
        if evidence.get("result") != "passed":
            raise RuntimeError("disposable client returned unsuccessful evidence")
        evidence.update({"postgres_image": IMAGE, "client_image": CLIENT_IMAGE,
                         "ordered_migration_sources_validated": migration_count,
                         "network_internal": True, "host_ports_published": False})
    finally:
        if client_created:
            cleanup["client_container_removed"] = run([docker, "rm", "--force", client], check=False).returncode == 0
        if database_created:
            cleanup["database_container_removed"] = run([docker, "rm", "--force", database], check=False).returncode == 0
        if network_created:
            cleanup["network_removed"] = run([docker, "network", "rm", network], check=False).returncode == 0
    if evidence is None:
        raise RuntimeError("disposable PostgreSQL client returned no evidence")
    evidence["cleanup"] = cleanup
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-mode", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/refactor/builds/2026-11-01-recovery/public-ebf-scorecard-runtime-boundary-743-disposable.json")
    args = parser.parse_args()
    evidence = check_client() if args.client_mode else check()
    evidence["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if args.client_mode:
        print(json.dumps(evidence, sort_keys=True))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
