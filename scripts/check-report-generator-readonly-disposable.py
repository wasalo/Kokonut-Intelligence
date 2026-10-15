#!/usr/bin/env python3
"""Prove report calculations stay read-only against a disposable local database."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.export.report_generator import generate_report_data_read_only


def disposable_dsn() -> str:
    dsn = os.environ.get("REPORT_GENERATOR_TEST_DSN", "")
    parsed = urlsplit(dsn)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.path.lstrip("/") != "postgres"
    ):
        raise ValueError(
            "REPORT_GENERATOR_TEST_DSN must target the local disposable postgres database"
        )
    return dsn


def row_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{table}"')
        return int(cur.fetchone()[0])


def main() -> int:
    try:
        dsn = disposable_dsn()
    except ValueError as exc:
        print(json.dumps({"result": "blocked", "reason": str(exc)}))
        return 2

    table = f"report_ro_probe_{uuid.uuid4().hex}"
    conn = psycopg2.connect(dsn, connect_timeout=8, application_name="report-ro-disposable-check")
    evidence: dict[str, object] = {
        "result": "failed",
        "database_target": "local disposable postgres database",
        "candidate_or_legacy_modified": False,
    }
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE TABLE "{table}" (value integer NOT NULL)')
        conn.commit()

        def read_only_generator(read_conn, *_args):
            with read_conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0]

        evidence["read_only_select"] = generate_report_data_read_only(
            conn, read_only_generator, None, None, None
        ) == 1

        def write_generator(read_conn, *_args):
            with read_conn.cursor() as cur:
                cur.execute(f'INSERT INTO "{table}" (value) VALUES (1)')

        try:
            generate_report_data_read_only(conn, write_generator, None, None, None)
            evidence["direct_write_rejected"] = False
        except psycopg2.Error as exc:
            evidence["direct_write_rejected"] = exc.pgcode == "25006"

        def autocommit_escape_generator(read_conn, *_args):
            with read_conn.cursor() as cur:
                cur.execute("SET default_transaction_read_only TO off")
            read_conn.commit()
            read_conn.autocommit = True
            with read_conn.cursor() as cur:
                cur.execute(f'INSERT INTO "{table}" (value) VALUES (2)')

        try:
            generate_report_data_read_only(conn, autocommit_escape_generator, None, None, None)
            evidence["autocommit_escape_rejected"] = False
        except RuntimeError as exc:
            evidence["autocommit_escape_rejected"] = "cannot enable autocommit" in str(exc)

        def cursor_connection_escape_generator(read_conn, *_args):
            with read_conn.cursor() as cur:
                cur.connection.autocommit = True

        try:
            generate_report_data_read_only(
                conn, cursor_connection_escape_generator, None, None, None
            )
            evidence["cursor_connection_escape_rejected"] = False
        except RuntimeError as exc:
            evidence["cursor_connection_escape_rejected"] = "cannot enable autocommit" in str(exc)

        evidence["rows_after_rejected_calculations"] = row_count(conn, table)
        with conn.cursor() as cur:
            cur.execute(f'INSERT INTO "{table}" (value) VALUES (3)')
        conn.commit()
        evidence["draft_write_after_calculation"] = row_count(conn, table) == 1
        evidence["result"] = (
            "passed"
            if all(
                evidence[key]
                for key in (
                    "read_only_select",
                    "direct_write_rejected",
                    "autocommit_escape_rejected",
                    "cursor_connection_escape_rejected",
                    "draft_write_after_calculation",
                )
            )
            and evidence["rows_after_rejected_calculations"] == 0
            else "failed"
        )
    except Exception as exc:  # noqa: BLE001 - emit only sanitized failure metadata
        evidence["failure_type"] = type(exc).__name__
        evidence["sqlstate"] = getattr(exc, "pgcode", None)
    finally:
        try:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(f'DROP TABLE IF EXISTS "{table}"')
            conn.commit()
        except Exception:  # noqa: BLE001 - best-effort cleanup of disposable data
            conn.rollback()
            evidence["cleanup"] = "failed"
        conn.close()

    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
