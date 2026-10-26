#!/usr/bin/env python3
"""Exercise saved-query isolation on a purpose-built disposable PostgreSQL DB.

The caller must provide a fresh disposable instance and the explicit guard
environment variables. The fixture creates synthetic roles/tables/views only;
the container used by the documented command is removed after this process.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.analytics.reporting_reader import count_reporting_rows, safe_query_error
from services.export import dataset_refresh

DATABASE = "kernel_reporting_check_20261014"
ADMIN_USER = "kernel_reporting_admin"
READER_USER = "kokonut_analytics_ro"
APP_USER = "kokonut_dataset_app"
REPORTING_SCHEMA = "kokonut_reporting"
REPORTING_VIEWS = (
    "v_farm_summary",
    "v_verified_metric_values",
    "v_attestation_summary",
)


def _require_disposable_target() -> None:
    if os.environ.get("KOKONUT_DISPOSABLE_REPORTING_CHECK") != "1":
        raise RuntimeError("set KOKONUT_DISPOSABLE_REPORTING_CHECK=1 for this fixture")
    if os.environ.get("PG_DB") != DATABASE or os.environ.get("PG_USER") != ADMIN_USER:
        raise RuntimeError("fixture refuses any database except its named disposable target")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,}", os.environ.get("PG_PASSWORD", "")):
        raise RuntimeError("disposable admin password must be synthetic and at least 24 characters")


def _connect(user: str, password: str):
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "127.0.0.1"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=DATABASE,
        user=user,
        password=password,
        connect_timeout=5,
    )


def _prepare_database(reader_password: str, app_password: str) -> None:
    conn = _connect(ADMIN_USER, os.environ["PG_PASSWORD"])
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for role in (READER_USER, APP_USER):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                if cur.fetchone():
                    raise RuntimeError("fixture role already exists; use a fresh database")

            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(READER_USER), sql.Literal(reader_password))
            )
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS"
                ).format(sql.Identifier(APP_USER), sql.Literal(app_password))
            )

            cur.execute("SELECT datname FROM pg_database WHERE datallowconn")
            for (database_name,) in cur.fetchall():
                cur.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database_name)))
            cur.execute(sql.SQL("REVOKE TEMPORARY ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DATABASE)))
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
                    sql.Identifier(DATABASE),
                    sql.Identifier(READER_USER),
                    sql.Identifier(APP_USER),
                )
            )
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(APP_USER)))
            cur.execute("CREATE SCHEMA kokonut_reporting")
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA kokonut_reporting TO {}").format(sql.Identifier(READER_USER)))
            cur.execute("CREATE TABLE public.reader_fixture (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
            cur.execute(
                "INSERT INTO public.reader_fixture (id, payload) "
                "VALUES (1, 'synthetic'), (2, 'synthetic'), (3, 'synthetic')"
            )
            for view in REPORTING_VIEWS:
                cur.execute(
                    sql.SQL("CREATE VIEW kokonut_reporting.{} AS SELECT id FROM public.reader_fixture").format(
                        sql.Identifier(view)
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT ON kokonut_reporting.{} TO {}").format(
                        sql.Identifier(view), sql.Identifier(READER_USER)
                    )
                )
            cur.execute(
                "CREATE TABLE public.dashboard_dataset "
                "(id TEXT PRIMARY KEY, name TEXT NOT NULL, dataset_type TEXT, query_sql TEXT, "
                "refresh_interval_minutes INTEGER, last_refreshed_at TIMESTAMPTZ, "
                "metadata JSONB, status TEXT NOT NULL)"
            )
            query_sql = "SELECT id FROM kokonut_reporting.v_farm_summary"
            cur.execute(
                "INSERT INTO public.dashboard_dataset "
                "(id, name, dataset_type, query_sql, refresh_interval_minutes, metadata, status) "
                "VALUES ('fixture-dataset', 'Synthetic reporting check', 'reporting', %s, 60, '{}', 'active')",
                (query_sql,),
            )
            cur.execute(
                sql.SQL("GRANT SELECT, UPDATE ON public.dashboard_dataset TO {}").format(sql.Identifier(APP_USER))
            )
    finally:
        conn.close()


def main() -> None:
    _require_disposable_target()
    reader_password = secrets.token_urlsafe(32)
    app_password = secrets.token_urlsafe(32)
    _prepare_database(reader_password, app_password)

    os.environ["KOKONUT_ANALYTICS_USER"] = READER_USER
    os.environ["KOKONUT_ANALYTICS_PASSWORD"] = reader_password
    dataset_refresh.require_feature = lambda _feature: None

    try:
        count_reporting_rows(f"SELECT id FROM {REPORTING_SCHEMA}.v_farm_summary")
    except Exception as exc:
        # Policy errors use fixed, non-sensitive explanations. Include one here
        # so a disposable ACL contract failure can be repaired without logging
        # connection details or user-authored SQL.
        raise RuntimeError(f"reporting reader preflight failed: {exc}") from exc

    app = _connect(APP_USER, app_password)
    try:
        result = dataset_refresh.refresh_dataset(app, "fixture-dataset")
        if result["status"] != "active" or result["row_count"] != 3:
            raise AssertionError("application metadata update did not use the reporting result")
        app.commit()
    finally:
        app.close()

    denied_private_read = False
    try:
        count_reporting_rows("SELECT id FROM public.reader_fixture")
    except psycopg2.Error as exc:
        denied_private_read = True
        private_read_error = safe_query_error(exc)
    else:
        raise AssertionError("reporting reader unexpectedly read the private base table")

    denied_write = False
    try:
        count_reporting_rows(
            "WITH changed AS (DELETE FROM public.reader_fixture RETURNING id) SELECT count(*) FROM changed"
        )
    except psycopg2.Error as exc:
        denied_write = True
        write_error = safe_query_error(exc)
    else:
        raise AssertionError("reporting reader unexpectedly executed a data-changing query")

    admin = _connect(ADMIN_USER, os.environ["PG_PASSWORD"])
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.reader_fixture")
            remaining_rows = cur.fetchone()[0]
            cur.execute(
                "SELECT metadata->'last_refresh' FROM public.dashboard_dataset WHERE id = %s", ("fixture-dataset",)
            )
            refresh_metadata = cur.fetchone()[0]
            cur.execute(
                "SELECT has_table_privilege(%s, 'public.dashboard_dataset', 'UPDATE'), "
                "has_table_privilege(%s, 'kokonut_reporting.v_farm_summary', 'SELECT')",
                (APP_USER, APP_USER),
            )
            app_privileges = cur.fetchone()
        if remaining_rows != 3:
            raise AssertionError("a denied query changed fixture data")
        if not refresh_metadata or refresh_metadata["row_count"] != 3:
            raise AssertionError("dataset refresh metadata was not recorded")
        if app_privileges != (True, False):
            raise AssertionError("fixture app role does not prove connection separation")
    finally:
        admin.close()

    print(
        json.dumps(
            {
                "result": "passed",
                "database": DATABASE,
                "scope": "fresh disposable PostgreSQL instance with synthetic roles and rows",
                "dataset_refresh": "app role updated metadata while lacking reporting-view SELECT",
                "reporting_role": "verified; read-only and limited to the three curated views",
                "private_base_table_read_denied": denied_private_read,
                "data_changing_cte_denied": denied_write,
                "synthetic_rows_after_denials": remaining_rows,
                "safe_errors": {
                    "private_read": private_read_error,
                    "write": write_error,
                },
                "candidate_or_legacy_database_touched": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
