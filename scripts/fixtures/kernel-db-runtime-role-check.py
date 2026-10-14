#!/usr/bin/env python3
"""Prove runtime-role DML access and administrative denial in a scratch DB."""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg2

from services.migration.runtime_role import provision_runtime_role

HOST = os.environ.get("PG_HOST", "database")
PORT = int(os.environ.get("PG_PORT", "5432"))
DATABASE = os.environ.get("PG_DB", "kokonut_intelligence")
ADMIN_USER = os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut")
ADMIN_PASSWORD = os.environ["KOKONUT_DB_ADMIN_PASSWORD"]
RUNTIME_USER = os.environ.get("KOKONUT_RUNTIME_USER", "kokonut_runtime")
RUNTIME_PASSWORD = os.environ["KOKONUT_RUNTIME_PASSWORD"]
OPERATOR_AUTH_USER = os.environ.get("KOKONUT_OPERATOR_AUTH_USER", "kokonut_operator_auth")
OPERATOR_AUTH_PASSWORD = os.environ["KOKONUT_OPERATOR_AUTH_PASSWORD"]
UNRELATED_DATABASE = "runtime_role_unrelated"
OPERATOR_SESSION_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "schemas/postgres/395_operator_session_auth_boundary.sql"
)
GATEWAY_CONTEXT_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "schemas/postgres/396_signed_gateway_credential_tenant_context.sql"
)
MOBILE_ROLE_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests/fixtures/operator_session_mobile_role_boundary.sql"
)


def connect(user: str, password: str, database: str = DATABASE):
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=database,
        user=user,
        password=password,
        connect_timeout=5,
    )


def expect_privilege_denial(conn, statement: str) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(statement)
    except psycopg2.Error as exc:
        conn.rollback()
        if exc.pgcode != "42501":
            raise AssertionError(f"expected permission denial (42501), got {exc.pgcode}") from exc
        return
    conn.rollback()
    raise AssertionError(f"runtime role unexpectedly succeeded: {statement}")


def main() -> None:
    admin = connect(ADMIN_USER, ADMIN_PASSWORD)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (UNRELATED_DATABASE,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{UNRELATED_DATABASE}"')
            cur.execute("DROP TABLE IF EXISTS public.kernel_role_probe_existing CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.kernel_role_probe_future CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.mobile_device_enrollment CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.mobile_device CASCADE")
            cur.execute(
                """CREATE TABLE IF NOT EXISTS public.operator_identity (
                       id UUID PRIMARY KEY,
                       issuer TEXT NOT NULL,
                       subject TEXT NOT NULL,
                       display_name TEXT,
                       email TEXT,
                       enabled BOOLEAN NOT NULL DEFAULT FALSE,
                       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                       updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                       UNIQUE (issuer, subject)
                   )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS public.operator_session (
                       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                       operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
                       session_token_hash CHAR(64) NOT NULL UNIQUE,
                       csrf_token_hash CHAR(64) NOT NULL,
                       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                       last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                       expires_at TIMESTAMPTZ NOT NULL,
                       revoked_at TIMESTAMPTZ
                   )"""
            )
            cur.execute(OPERATOR_SESSION_MIGRATION.read_text())
            cur.execute(GATEWAY_CONTEXT_MIGRATION.read_text())
            cur.execute(MOBILE_ROLE_FIXTURE.read_text())
            cur.execute(
                """
                CREATE TABLE public.kernel_role_probe_existing (
                    id BIGSERIAL PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT INTO public.kernel_role_probe_existing (value) VALUES ('admin-seeded')"
            )

        first = provision_runtime_role(
            admin,
            database=DATABASE,
            admin_user=ADMIN_USER,
            admin_password=ADMIN_PASSWORD,
            runtime_user=RUNTIME_USER,
            runtime_password=RUNTIME_PASSWORD,
            operator_auth_user=OPERATOR_AUTH_USER,
            operator_auth_password=OPERATOR_AUTH_PASSWORD,
        )
        second = provision_runtime_role(
            admin,
            database=DATABASE,
            admin_user=ADMIN_USER,
            admin_password=ADMIN_PASSWORD,
            runtime_user=RUNTIME_USER,
            runtime_password=RUNTIME_PASSWORD,
            operator_auth_user=OPERATOR_AUTH_USER,
            operator_auth_password=OPERATOR_AUTH_PASSWORD,
        )

        with admin.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE public.kernel_role_probe_future (
                    id BIGSERIAL PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
        admin.close()

        runtime = connect(RUNTIME_USER, RUNTIME_PASSWORD)
        runtime.autocommit = True
        try:
            with runtime.cursor() as cur:
                cur.execute("SELECT value FROM public.kernel_role_probe_existing WHERE id = 1")
                if cur.fetchone()[0] != "admin-seeded":
                    raise AssertionError("runtime role could not read an existing admin-owned relation")
                cur.execute(
                    "INSERT INTO public.kernel_role_probe_existing (value) VALUES ('runtime-insert') RETURNING id"
                )
                inserted_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE public.kernel_role_probe_existing SET value = 'runtime-updated' WHERE id = %s",
                    (inserted_id,),
                )
                cur.execute("DELETE FROM public.kernel_role_probe_existing WHERE id = %s", (inserted_id,))
                cur.execute(
                    "INSERT INTO public.kernel_role_probe_future (value) VALUES ('default-privilege-grant') RETURNING id"
                )
                future_id = cur.fetchone()[0]
                cur.execute("DELETE FROM public.kernel_role_probe_future WHERE id = %s", (future_id,))

            for statement in (
                "SELECT device_token_hash FROM public.mobile_device LIMIT 1",
                "SELECT push_token FROM public.mobile_device LIMIT 1",
                "SELECT code_hash FROM public.mobile_device_enrollment LIMIT 1",
                "CREATE TABLE public.kernel_role_probe_forbidden (id INTEGER)",
                "CREATE ROLE kernel_role_probe_forbidden LOGIN",
                "CREATE DATABASE kernel_role_probe_forbidden",
                f"SET ROLE {ADMIN_USER}",
            ):
                expect_privilege_denial(runtime, statement)
        finally:
            runtime.close()

        unrelated_denials = []
        for database in ("postgres", "template1", UNRELATED_DATABASE):
            try:
                unexpected = connect(RUNTIME_USER, RUNTIME_PASSWORD, database)
            except psycopg2.OperationalError as exc:
                if "permission denied" not in str(exc).lower():
                    raise AssertionError(f"unexpected connection failure for {database}") from exc
                unrelated_denials.append(database)
            else:
                unexpected.close()
                raise AssertionError(f"runtime role unexpectedly connected to {database}")

        admin = connect(ADMIN_USER, ADMIN_PASSWORD)
        try:
            with admin.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication,
                           r.rolbypassrls, r.rolinherit,
                           has_schema_privilege(r.oid, 'public', 'CREATE'),
                           EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid),
                           EXISTS (SELECT 1 FROM pg_class c
                                   WHERE c.relowner = r.oid AND c.relname LIKE 'kernel_role_probe_%%')
                    FROM pg_roles r WHERE r.rolname = %s
                    """,
                    (RUNTIME_USER,),
                )
                role_state = cur.fetchone()
                if role_state != (False, False, False, False, False, False, False, False, False):
                    raise AssertionError(f"runtime role retained elevated attributes: {role_state}")
                cur.execute(
                    """
                    SELECT datname, has_database_privilege(%s, oid, 'CONNECT')
                    FROM pg_database WHERE datallowconn OR datname = 'template1'
                    ORDER BY datname
                    """,
                    (RUNTIME_USER,),
                )
                database_access = {name: allowed for name, allowed in cur.fetchall()}
        finally:
            admin.close()

        if database_access.get(DATABASE) is not True:
            raise AssertionError("runtime role cannot connect to the configured database")
        if any(allowed for name, allowed in database_access.items() if name != DATABASE):
            raise AssertionError(f"runtime role has unrelated database access: {database_access}")
        if unrelated_denials != ["postgres", "template1", UNRELATED_DATABASE]:
            raise AssertionError(f"unexpected unrelated database denial evidence: {unrelated_denials}")

        print(json.dumps({
            "result": "passed",
            "provisioning_runs": [first["status"], second["status"]],
            "runtime_user": RUNTIME_USER,
            "runtime_password_distinct_from_admin": RUNTIME_PASSWORD != ADMIN_PASSWORD,
            "role_attributes": {
                "superuser": role_state[0],
                "createdb": role_state[1],
                "createrole": role_state[2],
                "replication": role_state[3],
                "bypassrls": role_state[4],
                "inherit": role_state[5],
                "public_schema_create": role_state[6],
                "role_memberships": role_state[7],
                "owns_probe_relations": role_state[8],
            },
            "existing_and_future_admin_owned_table_dml": ["select", "insert", "update", "delete"],
            "denied_actions": ["persistent DDL", "create role", "create database", "set role admin"],
            "denied_unrelated_databases": unrelated_denials,
            "runtime_database_access": database_access,
            "network_egress": "disabled",
            "fixture_data": "synthetic",
        }, sort_keys=True))
    finally:
        if not admin.closed:
            admin.close()


if __name__ == "__main__":
    main()
