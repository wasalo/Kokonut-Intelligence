#!/usr/bin/env python3
"""Verify migration 741's curated quality-grade ACL on isolated PostgreSQL 16."""

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

MIGRATION = ROOT / "schemas/postgres/741_runtime_quality_grade_catalog_read_only.sql"
IMAGE = os.environ.get(
    "QUALITY_GRADE_ACL_TEST_IMAGE",
    "postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5",
)
CLIENT_IMAGE = os.environ.get(
    "QUALITY_GRADE_ACL_CLIENT_IMAGE", "kokonut-kernel-candidate-app:latest"
)
RUNTIME = "kokonut_runtime"
DIRECTUS = "kokonut_directus_runtime"
PUBLIC_PROBE = "kokonut_public_probe"
OWNER = "kokonut"
RELATION = "quality_grade"
TABLE_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")

FIXTURE = r"""
CREATE ROLE kokonut NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_public_probe NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA kokonut_security;
CREATE TABLE kokonut_security.directus_relation_privilege_policy (
    schema_name text NOT NULL,
    relation_name text NOT NULL,
    access_mode text NOT NULL,
    source_migration text NOT NULL,
    PRIMARY KEY (schema_name, relation_name)
);
CREATE TABLE public.quality_grade (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(100) NOT NULL UNIQUE,
    category varchar(50) NOT NULL,
    min_score numeric(5,2),
    max_score numeric(5,2),
    description text,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.quality_grade OWNER TO kokonut;
INSERT INTO public.quality_grade (name, category, min_score, max_score, description)
VALUES ('Synthetic grade', 'grade', 70, 79.99, 'Owner maintenance probe');
GRANT ALL PRIVILEGES ON TABLE public.quality_grade TO PUBLIC;
GRANT INSERT (name), UPDATE (category), REFERENCES (id)
    ON TABLE public.quality_grade TO PUBLIC;
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


def _assert_public_denied(connection, *, context: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege(%s, %s, 'SELECT'), "
            + ", ".join("has_table_privilege(%s, %s, %s)" for _ in TABLE_PRIVILEGES),
            (
                PUBLIC_PROBE,
                f"public.{RELATION}",
                *(
                    value
                    for privilege in TABLE_PRIVILEGES
                    for value in (PUBLIC_PROBE, f"public.{RELATION}", privilege)
                ),
            ),
        )
        if cursor.fetchone() != (False, *(False for _ in TABLE_PRIVILEGES)):
            raise AssertionError(f"PUBLIC still has effective table privileges after {context}")
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute "
            "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped "
            "AND (has_column_privilege(%s, %s, attname, 'INSERT') "
            "OR has_column_privilege(%s, %s, attname, 'UPDATE') "
            "OR has_column_privilege(%s, %s, attname, 'REFERENCES')))"
            , (f"public.{RELATION}", PUBLIC_PROBE, f"public.{RELATION}",
               PUBLIC_PROBE, f"public.{RELATION}", PUBLIC_PROBE, f"public.{RELATION}")
        )
        if cursor.fetchone()[0]:
            raise AssertionError(f"PUBLIC retains column writes after {context}")


def _assert_role_acl(connection, role: str, *, context: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege(%s, %s, 'SELECT'), "
            + ", ".join("has_table_privilege(%s, %s, %s)" for _ in TABLE_PRIVILEGES),
            (
                role,
                f"public.{RELATION}",
                *(
                    value
                    for privilege in TABLE_PRIVILEGES
                    for value in (role, f"public.{RELATION}", privilege)
                ),
            ),
        )
        expected = (True, *(False for _ in TABLE_PRIVILEGES))
        if cursor.fetchone() != expected:
            raise AssertionError(f"{role} table ACL is wrong after {context}")
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute "
            "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped "
            "AND (has_column_privilege(%s, %s, attname, 'INSERT') "
            "OR has_column_privilege(%s, %s, attname, 'UPDATE') "
            "OR has_column_privilege(%s, %s, attname, 'REFERENCES')))"
            , (f"public.{RELATION}", role, f"public.{RELATION}",
               role, f"public.{RELATION}", role, f"public.{RELATION}")
        )
        if cursor.fetchone()[0]:
            raise AssertionError(f"{role} retains column writes after {context}")
        cursor.execute(f"SET ROLE {role}")
        cursor.execute("SELECT name FROM public.quality_grade ORDER BY name")
        if cursor.fetchone() != ("Synthetic grade",):
            raise AssertionError(f"{role} cannot read the curated catalog after {context}")
        cursor.execute("RESET ROLE")
    connection.commit()


def _expect_denied(connection, role: str, statement: str, label: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"SET ROLE {role}")
        cursor.execute("SAVEPOINT expected_acl_denial")
        try:
            cursor.execute(statement)
        except errors.InsufficientPrivilege:
            cursor.execute("ROLLBACK TO SAVEPOINT expected_acl_denial")
        else:
            raise AssertionError(f"{role} unexpectedly performed {label}")
        finally:
            cursor.execute("RESET ROLE")
    connection.commit()


def _assert_denied_writes(connection, role: str) -> None:
    for statement, label in (
        ("INSERT INTO public.quality_grade (name, category) VALUES ('Blocked', 'grade')", "INSERT"),
        ("UPDATE public.quality_grade SET category = 'blocked'", "UPDATE"),
        ("DELETE FROM public.quality_grade", "DELETE"),
        ("TRUNCATE public.quality_grade", "TRUNCATE"),
    ):
        _expect_denied(connection, role, statement, label)


def check_database(host: str, password: str) -> dict[str, object]:
    from services.migration import directus_role, runtime_role

    connection = psycopg2.connect(
        host=host, port=5432, dbname="postgres", user="postgres",
        password=password, connect_timeout=5,
    )
    try:
        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute(FIXTURE)
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_catalog.pg_class "
                "WHERE oid = 'public.quality_grade'::regclass"
            )
            rls_before = cursor.fetchone()
        connection.commit()
        migration = MIGRATION.read_text(encoding="utf-8")

        # Apply/replay while application roles are absent, as on a fresh schema.
        _apply(connection, migration)
        _apply(connection, migration)
        _assert_public_denied(connection, context="role-absent replay")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname = ANY(%s)",
                ([RUNTIME, DIRECTUS],),
            )
            if cursor.fetchone()[0] != 0:
                raise AssertionError("migration unexpectedly created an application role")

        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE ROLE {RUNTIME} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; "
                f"CREATE ROLE {DIRECTUS} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; "
                f"GRANT ALL PRIVILEGES ON TABLE public.quality_grade TO {RUNTIME}, {DIRECTUS}; "
                f"GRANT INSERT (name), UPDATE (category), REFERENCES (id) "
                f"ON TABLE public.quality_grade TO {RUNTIME}, {DIRECTUS}"
            )
        connection.commit()

        # Replay with stale compatibility grants, proving the migration closes them.
        _apply(connection, migration)
        _apply(connection, migration)
        _assert_public_denied(connection, context="role-present replay")
        for role in (RUNTIME, DIRECTUS):
            _assert_role_acl(connection, role, context="migration replay")
            _assert_denied_writes(connection, role)

        # Reapply the actual provisioner boundaries after broad compatibility grants.
        with connection.cursor() as cursor:
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RUNTIME}; "
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {DIRECTUS}"
            )
            runtime_policy = runtime_role._apply_scoped_write_boundary(
                cursor, sql.Identifier(RUNTIME)
            )
            runtime_role._verify_scoped_write_boundary(cursor, RUNTIME)
            directus_policy = directus_role._apply_migration_declared_relation_policies(
                cursor, sql.Identifier(DIRECTUS)
            )
        connection.commit()
        if runtime_policy["relations"].get(RELATION) is not True:
            raise AssertionError("runtime-role provisioner omitted quality_grade")
        if directus_policy != {"read_only": 1, "no_access": 0}:
            raise AssertionError(f"unexpected Directus policy result: {directus_policy}")
        for role in (RUNTIME, DIRECTUS):
            _assert_role_acl(connection, role, context="provisioner reapplication")
            _assert_denied_writes(connection, role)
        _assert_public_denied(connection, context="provisioner reapplication")

        # Curated maintenance remains possible as the owning database role.
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE kokonut")
            cursor.execute(
                "UPDATE public.quality_grade SET description = 'Owner update preserved' "
                "WHERE name = 'Synthetic grade'"
            )
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT description FROM public.quality_grade WHERE name = 'Synthetic grade'"
            )
            if cursor.fetchone() != ("Owner update preserved",):
                raise AssertionError("curated owner maintenance was blocked")
            cursor.execute(
                "SELECT schema_name, relation_name, access_mode, source_migration "
                "FROM kokonut_security.directus_relation_privilege_policy "
                "WHERE schema_name = 'public' AND relation_name = 'quality_grade'"
            )
            policy = cursor.fetchone()
            if policy != ("public", RELATION, "read_only", MIGRATION.name):
                raise AssertionError(f"Directus policy registry mismatch: {policy}")
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_catalog.pg_class "
                "WHERE oid = 'public.quality_grade'::regclass"
            )
            if cursor.fetchone() != rls_before:
                raise AssertionError("migration changed quality_grade RLS state")
        connection.commit()

        return {
            "result": "passed",
            "migration": MIGRATION.name,
            "relation": "public.quality_grade",
            "classification": "global curated reference catalog",
            "migration_apply_and_replay_roles_absent": "passed",
            "migration_apply_and_replay_roles_present": "passed",
            "runtime_select_and_dml_denial": "passed",
            "directus_select_and_dml_denial": "passed",
            "public_table_and_column_write_denial": "passed",
            "runtime_provisioner_reapplication": "passed",
            "directus_provisioner_reapplication": "passed",
            "owner_maintenance_write": "passed",
            "rls_unchanged": rls_before,
            "external_writers": "none known; user-confirmed",
            "network": "internal Docker network",
            "host_ports_published": False,
            "candidate_legacy_production_touched": False,
        }
    finally:
        connection.rollback()
        connection.close()


def _validated_migration_count() -> int:
    from services.migration.cli import _discover_files, _validate_sources

    migrations = _discover_files(include_seeds=False)
    _validate_sources(migrations)
    if not migrations or migrations[-1]["id"] != f"schema:{MIGRATION.name}":
        raise RuntimeError("migration 741 is not the latest ordered schema migration")
    return len(migrations)


def check_client() -> dict[str, object]:
    host = os.environ.get("QUALITY_GRADE_ACL_DATABASE_HOST")
    password = os.environ.get("QUALITY_GRADE_ACL_DATABASE_PASSWORD")
    if not host or not password:
        raise RuntimeError("internal client mode requires database host and password")
    evidence = check_database(host, password)
    evidence["ordered_migration_sources_validated"] = _validated_migration_count()
    return evidence


def _published_ports(docker: str, container: str) -> list[dict[str, str]]:
    raw = run([docker, "inspect", "--format", "{{json .HostConfig.PortBindings}}", container]).stdout.strip()
    bindings = json.loads(raw) if raw else None
    return [
        {
            "container_port": str(port),
            "host_ip": str(entry.get("HostIp", "")),
            "host_port": str(entry.get("HostPort", "")),
        }
        for port, entries in (bindings.items() if isinstance(bindings, dict) else [])
        for entry in entries or []
        if isinstance(entry, dict)
    ]


def check() -> dict[str, object]:
    migration_count = _validated_migration_count()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is required for the isolated PostgreSQL acceptance")
    run([docker, "image", "inspect", IMAGE], timeout=30)
    run([docker, "image", "inspect", CLIENT_IMAGE], timeout=30)

    suffix = secrets.token_hex(5)
    database = f"kokonut-quality-grade-acl-{suffix}"
    client = f"{database}-client"
    network = f"{database}-net"
    password = secrets.token_urlsafe(32)
    network_created = database_created = client_created = False
    cleanup = {
        "client_container_removed": True,
        "database_container_removed": True,
        "network_removed": True,
    }
    evidence: dict[str, object] | None = None
    try:
        run([docker, "network", "create", "--internal", network])
        network_created = True
        if run([docker, "network", "inspect", "--format", "{{.Internal}}", network]).stdout.strip().lower() != "true":
            raise RuntimeError("disposable network is not internal")
        run([
            docker, "run", "--pull=never", "--detach", "--name", database,
            "--network", network, "--network-alias", "database",
            "--env", f"POSTGRES_PASSWORD={password}", IMAGE,
        ])
        database_created = True
        if _published_ports(docker, database):
            raise RuntimeError("disposable PostgreSQL unexpectedly publishes a host port")

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            ready = run([docker, "exec", database, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("isolated PostgreSQL did not become ready")

        run([
            docker, "create", "--name", client, "--network", network,
            "--volume", f"{ROOT}:/repo:ro", "--workdir", "/repo",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "KOKONUT_ENV=development",
            "--env", "KOKONUT_ENV_SECRETS_NOT_REQUIRED=true",
            "--env", "QUALITY_GRADE_ACL_DATABASE_HOST=database",
            "--env", f"QUALITY_GRADE_ACL_DATABASE_PASSWORD={password}",
            CLIENT_IMAGE, "python3", "scripts/check-quality-grade-runtime-boundary-disposable.py", "--client-mode",
        ])
        client_created = True
        if _published_ports(docker, client):
            raise RuntimeError("disposable client unexpectedly publishes a host port")
        result = run([docker, "start", "--attach", client], timeout=240)
        evidence = json.loads(result.stdout)
        if evidence.get("result") != "passed":
            raise RuntimeError("disposable client returned unsuccessful evidence")
        evidence.update({
            "postgres_image": IMAGE,
            "client_image": CLIENT_IMAGE,
            "ordered_migration_sources_validated": migration_count,
            "network_internal": True,
            "host_ports_published": False,
        })
    finally:
        if client_created:
            cleanup["client_container_removed"] = run(
                [docker, "rm", "--force", client], check=False
            ).returncode == 0
        if database_created:
            cleanup["database_container_removed"] = run(
                [docker, "rm", "--force", database], check=False
            ).returncode == 0
        if network_created:
            cleanup["network_removed"] = run(
                [docker, "network", "rm", network], check=False
            ).returncode == 0
    if evidence is None:
        raise RuntimeError("disposable PostgreSQL client returned no evidence")
    evidence["cleanup"] = cleanup
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-mode", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/refactor/builds/2026-11-01-recovery/quality-grade-runtime-boundary-741-disposable.json")
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
