#!/usr/bin/env python3
"""Exercise the Directus runtime role against a disposable PostgreSQL instance."""

from __future__ import annotations

import json
import os
from pathlib import Path

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
ROOT = Path(__file__).resolve().parents[2]


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
            for table_name in (
                "hive_record",
                "pollinator_hive_inspection",
                "pollinator_observation",
                "pollinator_habitat",
                "pesticide_impact_log",
            ):
                cursor.execute(
                    sql.SQL("CREATE TABLE public.{} (id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)").format(
                        sql.Identifier(table_name)
                    )
                )
            cursor.execute(
                "CREATE TABLE public.farm_activity_operator_event ("
                "id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)"
            )
            for table_name in (
                "capital_source",
                "consent_data_type",
                "process_benchmark",
                "living_wage_benchmark",
            ):
                cursor.execute(
                    sql.SQL("CREATE TABLE public.{} (id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)").format(
                        sql.Identifier(table_name)
                    )
                )

            migration_dir = ROOT / "schemas" / "postgres"
            cursor.execute(
                (migration_dir / "692_runtime_pollinator_hive_writes_read_only.sql").read_text(
                    encoding="utf-8"
                )
            )
            cursor.execute(
                (migration_dir / "693_runtime_pollinator_capture_writes_read_only.sql").read_text(
                    encoding="utf-8"
                )
            )
            policy_migration = (
                migration_dir / "705_directus_relation_privilege_policy.sql"
            ).read_text(encoding="utf-8")
            cursor.execute(policy_migration)
            cursor.execute(policy_migration)
            cursor.execute(
                "SELECT schema_name, relation_name, access_mode "
                "FROM kokonut_security.directus_relation_privilege_policy "
                "ORDER BY schema_name, relation_name"
            )
            policy_rows = cursor.fetchall()
            policy_views = {
                "v_pollution_incidents": ("pollution_incident",),
                "v_waste_summary": ("waste_stream",),
                "v_composting_efficiency": ("composting_record",),
            }
            for schema_name, table_name, _mode in policy_rows:
                if table_name in policy_views:
                    continue
                cursor.execute("SELECT pg_catalog.to_regclass(%s)", (f"{schema_name}.{table_name}",))
                if cursor.fetchone()[0] is None:
                    cursor.execute(
                        sql.SQL("CREATE TABLE {} (id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)").format(
                            sql.Identifier(schema_name, table_name)
                        )
                    )
            for view_name, (base_table,) in policy_views.items():
                cursor.execute(
                    sql.SQL("CREATE VIEW public.{} AS SELECT id, value FROM public.{}").format(
                        sql.Identifier(view_name), sql.Identifier(base_table)
                    )
                )

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

        # Simulate stale table, column, and sequence grants after the ordered
        # migrations; reprovisioning must not restore the protected writes.
        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT INSERT, UPDATE, DELETE ON public.hive_record TO {}").format(
                    sql.Identifier(DIRECTUS_USER)
                )
            )
            cursor.execute(
                sql.SQL("GRANT INSERT (value), UPDATE (value) ON public.pollinator_observation TO {}").format(
                    sql.Identifier(DIRECTUS_USER)
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.hive_record_id_seq TO {}").format(
                    sql.Identifier(DIRECTUS_USER)
                )
            )
        admin.commit()
        third_result = provision_directus_role(
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
            expect_denied(
                directus,
                "SELECT relation_name FROM kokonut_security.directus_relation_privilege_policy",
            )
            for schema_name, table_name, access_mode in policy_rows:
                relation = sql.Identifier(schema_name, table_name)
                select_sql = sql.SQL("SELECT value FROM {} LIMIT 0").format(relation).as_string(directus)
                if access_mode == "read_only":
                    with directus.cursor() as cursor:
                        cursor.execute(select_sql)
                    directus.rollback()
                else:
                    expect_denied(directus, select_sql)
                for statement in (
                    sql.SQL("INSERT INTO {} (value) VALUES ('denied')").format(relation),
                    sql.SQL("UPDATE {} SET value = 'denied'").format(relation),
                    sql.SQL("DELETE FROM {}").format(relation),
                ):
                    expect_denied(directus, statement.as_string(directus))

            # Migrations 695/696/697/704 narrow kokonut_runtime, not the
            # Directus DB role. Keep those compatibility relations in the
            # broad Directus DB grant catalog (their API rules stay separate).
            for table_name in (
                "capital_source",
                "consent_data_type",
                "process_benchmark",
                "living_wage_benchmark",
            ):
                with directus.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("INSERT INTO public.{} (value) VALUES ('compat') RETURNING id").format(
                            sql.Identifier(table_name)
                        )
                    )
                    row_id = cursor.fetchone()[0]
                    cursor.execute(
                        sql.SQL("UPDATE public.{} SET value = 'updated' WHERE id = %s").format(
                            sql.Identifier(table_name)
                        ),
                        (row_id,),
                    )
                    cursor.execute(
                        sql.SQL("DELETE FROM public.{} WHERE id = %s").format(
                            sql.Identifier(table_name)
                        ),
                        (row_id,),
                    )
                directus.rollback()
            with directus.cursor() as cursor:
                cursor.execute(
                    "SELECT has_sequence_privilege(current_user, 'public.hive_record_id_seq', 'USAGE'), "
                    "has_sequence_privilege(current_user, 'public.hive_record_id_seq', 'SELECT'), "
                    "has_sequence_privilege(current_user, 'public.hive_record_id_seq', 'UPDATE')"
                )
                if cursor.fetchone() != (False, False, False):
                    raise AssertionError("read-only relation sequence privileges were restored")
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
                    "migration_denies_survive_reprovision": "passed",
                    "migration_705_replay": "passed",
                    "read_only_and_no_access_policies": "passed",
                    "sequence_and_column_denials": "passed",
                    "schema_and_role_ownership_denials": "passed",
                    "stale_schema_acl_removed": "passed",
                    "application_database_only": "passed",
                    "explicit_metadata_service_grant_preserved": "passed",
                    "database_names": [DATABASE],
                    "secrets_logged": False,
                    "first_provision": first_result["status"],
                    "second_provision": second_result["status"],
                    "third_provision": third_result["status"],
                },
                sort_keys=True,
            )
        )
    finally:
        admin.close()


if __name__ == "__main__":
    main()
