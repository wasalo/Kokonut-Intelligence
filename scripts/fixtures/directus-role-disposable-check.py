#!/usr/bin/env python3
"""Exercise the Directus runtime role against a disposable PostgreSQL instance."""

from __future__ import annotations

import json
import os

import psycopg2
from psycopg2 import sql

ADMIN = os.environ["KOKONUT_DB_ADMIN_USER"]
ADMIN_PASSWORD = os.environ["KOKONUT_DB_ADMIN_PASSWORD"]
DIRECTUS_USER = os.environ["KOKONUT_DIRECTUS_RUNTIME_USER"]
DIRECTUS_PASSWORD = os.environ["KOKONUT_DIRECTUS_RUNTIME_PASSWORD"]
HOST = os.environ["PG_HOST"]
PORT = int(os.environ["PG_PORT"])
DATABASE = os.environ["PG_DB"]
METADATA_DATABASE = "kokonut_metabase"


def connect(database: str, user: str, password: str):
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=database,
        user=user,
        password=password,
        connect_timeout=5,
    )


def expect_denied(connection, statement: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
    except psycopg2.Error as exc:
        connection.rollback()
        if exc.pgcode != "42501":
            raise AssertionError(f"expected permission denial, got SQLSTATE {exc.pgcode}") from exc
        return
    connection.rollback()
    raise AssertionError("Directus runtime unexpectedly executed a denied statement")


def expect_database_denied(database: str) -> None:
    try:
        connection = connect(database, DIRECTUS_USER, DIRECTUS_PASSWORD)
    except psycopg2.OperationalError:
        return
    else:
        connection.close()
        raise AssertionError(f"Directus role unexpectedly connected to {database}")


def main() -> None:
    admin = connect(DATABASE, ADMIN, ADMIN_PASSWORD)
    admin.autocommit = True
    try:
        with admin.cursor() as cursor:
            cursor.execute("CREATE DATABASE kokonut_metabase")
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS INHERIT"
                ).format(sql.Identifier(DIRECTUS_USER)),
                (DIRECTUS_PASSWORD,),
            )
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE kokonut_metabase_app WITH LOGIN PASSWORD %s NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(),
                ("metadata-role-secret-for-disposable-check",),
            )
            cursor.execute("GRANT CONNECT ON DATABASE kokonut_metabase TO kokonut_metabase_app")
            cursor.execute("CREATE SCHEMA private_app")
            cursor.execute("CREATE TABLE private_app.hidden_probe (value TEXT)")
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA private_app TO {}").format(sql.Identifier(DIRECTUS_USER)))
            cursor.execute(
                sql.SQL("GRANT SELECT ON private_app.hidden_probe TO {}").format(sql.Identifier(DIRECTUS_USER))
            )
            cursor.execute("CREATE TABLE public.directus_probe (id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)")
            cursor.execute("CREATE SCHEMA kokonut")
            cursor.execute("CREATE TABLE kokonut.directus_probe (value TEXT NOT NULL)")

        from services.migration.directus_role import provision_directus_role

        first_result = provision_directus_role(
            admin,
            database=DATABASE,
            admin_user=ADMIN,
            directus_user=DIRECTUS_USER,
            directus_password=DIRECTUS_PASSWORD,
        )
        second_result = provision_directus_role(
            admin,
            database=DATABASE,
            admin_user=ADMIN,
            directus_user=DIRECTUS_USER,
            directus_password=DIRECTUS_PASSWORD,
        )

        # Objects created later by the configured migration owner inherit only
        # the reviewed DML grants and sequence access.
        with admin.cursor() as cursor:
            cursor.execute("CREATE TABLE public.directus_future_probe (id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)")
            cursor.execute("INSERT INTO public.directus_probe (value) VALUES ('preexisting')")
        admin.commit()
        directus = connect(DATABASE, DIRECTUS_USER, DIRECTUS_PASSWORD)
        try:
            with directus.cursor() as cursor:
                cursor.execute("INSERT INTO public.directus_probe (value) VALUES ('existing-dml') RETURNING id")
                row_id = cursor.fetchone()[0]
                cursor.execute("UPDATE public.directus_probe SET value = 'updated' WHERE id = %s", (row_id,))
                cursor.execute("DELETE FROM public.directus_probe WHERE id = %s", (row_id,))
                cursor.execute("INSERT INTO kokonut.directus_probe (value) VALUES ('kokonut-dml')")
                cursor.execute("INSERT INTO public.directus_future_probe (value) VALUES ('future-dml') RETURNING id")
                future_id = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT has_sequence_privilege(current_user, 'public.directus_future_probe_id_seq', 'USAGE')"
                )
                if cursor.fetchone()[0] is not True:
                    raise AssertionError("default sequence grant was not applied")
            directus.commit()
            expect_denied(directus, "CREATE TABLE public.directus_ddl_denied (id INTEGER)")
            expect_denied(directus, "SELECT value FROM private_app.hidden_probe")
            with directus.cursor() as cursor:
                cursor.execute("SELECT value FROM public.directus_future_probe WHERE id = %s", (future_id,))
                if cursor.fetchone() != ("future-dml",):
                    raise AssertionError("future DML grant did not permit the expected read")
            directus.rollback()
        finally:
            directus.close()

        expect_database_denied("postgres")
        expect_database_denied(METADATA_DATABASE)
        print(
            json.dumps(
                {
                    "status": "passed",
                    "database": DATABASE,
                    "role": DIRECTUS_USER,
                    "idempotent_replay": "passed",
                    "existing_and_future_dml": "passed",
                    "schema_and_role_ownership_denials": "passed",
                    "stale_schema_acl_removed": "passed",
                    "application_database_only": "passed",
                    "explicit_metadata_service_grant_preserved": "passed",
                    "database_names": [DATABASE],
                    "secrets_logged": False,
                    "first_provision": first_result["status"],
                    "second_provision": second_result["status"],
                },
                sort_keys=True,
            )
        )
    finally:
        admin.close()


if __name__ == "__main__":
    main()
