"""Regression checks for the optional, least-privilege saved-query reader."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from services.analytics import reporting_reader
from services.analytics.reporting_reader import (
    REPORTING_QUERY_REGISTRY,
    REPORTING_SCHEMA,
    REPORTING_VIEWS,
    ReportingReaderPolicyError,
    count_registered_reporting_rows,
    open_reporting_connection,
    validate_reporting_connection,
)


class FakeCursor:
    def __init__(self, conn: "FakeReportingConnection"):
        self.conn = conn
        self.statement = ""

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str, params: Any = None) -> None:
        self.statement = statement
        self.conn.statements.append((statement, params))

    def fetchone(self):
        if "SELECT current_user, session_user" in self.statement:
            return self.conn.identity
        if "FROM pg_auth_members" in self.statement:
            return (self.conn.role_membership,)
        if "has_table_privilege(current_user, c.oid, 'INSERT')" in self.statement:
            return (self.conn.has_write_privilege,)
        if "FROM pg_proc p JOIN pg_namespace" in self.statement:
            return (self.conn.has_security_definer,)
        if "FROM pg_database" in self.statement:
            return (self.conn.can_connect_other_database,)
        if "SELECT count(*) FROM kokonut_reporting." in self.statement:
            return (self.conn.result_count,)
        raise AssertionError(f"unexpected fetchone for SQL: {self.statement}")

    def fetchall(self):
        if "extension_owned" in self.statement:
            return self.conn.readable_relations
        raise AssertionError(f"unexpected fetchall for SQL: {self.statement}")


class FakeReportingConnection:
    def __init__(self):
        self.identity = ("kokonut_analytics_ro", "kokonut_analytics_ro", *(False for _ in range(9)))
        self.role_membership = False
        self.readable_relations = [(REPORTING_SCHEMA, view, False) for view in sorted(REPORTING_VIEWS)] + [
            ("public", "spatial_ref_sys", True)
        ]
        self.has_write_privilege = False
        self.has_security_definer = False
        self.can_connect_other_database = False
        self.result_count = 3
        self.statements: list[tuple[str, Any]] = []
        self.session_options: dict[str, Any] | None = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs: Any) -> None:
        self.session_options = kwargs

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def test_open_reporting_connection_requires_distinct_provisioned_identity(monkeypatch):
    monkeypatch.setattr(reporting_reader.psycopg2, "connect", lambda **kwargs: kwargs)
    monkeypatch.setenv("PG_HOST", "reporting-test-db")
    monkeypatch.setenv("PG_PORT", "15439")
    monkeypatch.setenv("PG_DB", "reporting-test-db")
    monkeypatch.setenv("PG_USER", "kokonut_runtime")
    monkeypatch.setenv("PG_PASSWORD", "runtime-password")
    monkeypatch.setenv("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro")
    monkeypatch.setenv("KOKONUT_ANALYTICS_PASSWORD", "a" * 32)
    settings = open_reporting_connection()

    assert settings["host"] == "reporting-test-db"
    assert settings["port"] == 15439
    assert settings["dbname"] == "reporting-test-db"
    assert settings["user"] == "kokonut_analytics_ro"
    assert settings["password"] == "a" * 32
    assert "default_transaction_read_only=on" in settings["options"]
    assert "statement_timeout=15000" in settings["options"]
    assert settings["application_name"] == "kokonut-saved-report-reader"


@pytest.mark.parametrize(
    ("analytics_user", "analytics_password"),
    [
        ("kokonut_runtime", "a" * 32),
        ("kokonut_analytics_ro", "short"),
        ("kokonut_analytics_ro", "replace-with-distinct-analytics-password-min-24-chars"),
    ],
)
def test_open_reporting_connection_fails_closed_without_distinct_credentials(
    monkeypatch, analytics_user, analytics_password
):
    monkeypatch.setenv("PG_USER", "kokonut_runtime")
    monkeypatch.setenv("PG_PASSWORD", "runtime-password")
    monkeypatch.setenv("KOKONUT_ANALYTICS_USER", analytics_user)
    monkeypatch.setenv("KOKONUT_ANALYTICS_PASSWORD", analytics_password)
    monkeypatch.setattr(
        reporting_reader.psycopg2,
        "connect",
        lambda **kwargs: pytest.fail("must not open a connection with unsafe credentials"),
    )

    with pytest.raises(ReportingReaderPolicyError):
        open_reporting_connection()


@pytest.mark.parametrize(
    ("query_id", "expected_view"),
    [
        ("public_farm_summary_count", "v_farm_summary"),
        ("public_verified_metric_values_count", "v_verified_metric_values"),
        ("public_attestation_summary_count", "v_attestation_summary"),
    ],
)
def test_reader_runs_registered_query_with_bound_exact_location(
    monkeypatch, query_id, expected_view
):
    conn = FakeReportingConnection()
    monkeypatch.setenv("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro")
    location_id = "d4be5d0d-0b44-4e81-9b69-463bc87a9e11"

    count = count_registered_reporting_rows(
        query_id,
        location_id,
        connection_factory=lambda: conn,
    )

    assert count == 3
    assert conn.session_options == {"readonly": True, "autocommit": False}
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert conn.closed
    assert any("SET LOCAL search_path TO kokonut_reporting" in sql for sql, _ in conn.statements)
    report_query = next(
        (sql, params) for sql, params in conn.statements
        if "SELECT count(*) FROM kokonut_reporting." in sql
    )
    assert expected_view in report_query[0]
    assert "WHERE location_id = %s" in report_query[0]
    assert report_query[1] == (location_id,)
    assert any("WHERE datallowconn" in sql for sql, _ in conn.statements)
    security_definer_check = next(sql for sql, _ in conn.statements if "FROM pg_proc p JOIN pg_namespace" in sql)
    assert "WHERE p.prosecdef" in security_definer_check
    assert "pg_extension" not in security_definer_check


@pytest.mark.parametrize(
    ("query_id", "location_id", "message"),
    [
        (None, "d4be5d0d-0b44-4e81-9b69-463bc87a9e11", "missing or not registered"),
        ("SELECT 1", "d4be5d0d-0b44-4e81-9b69-463bc87a9e11", "missing or not registered"),
        ("public_farm_summary_count", None, "exact location"),
        ("public_farm_summary_count", "not-a-uuid", "valid location ID"),
    ],
)
def test_registered_reader_rejects_untrusted_or_unscoped_query_before_connection(
    query_id, location_id, message
):
    with pytest.raises(ValueError, match=message):
        count_registered_reporting_rows(
            query_id,
            location_id,
            connection_factory=lambda: pytest.fail("invalid query contract must fail before connecting"),
        )


def test_reporting_registry_uses_only_fixed_location_scoped_contracts():
    assert set(REPORTING_QUERY_REGISTRY) == {
        "public_farm_summary_count",
        "public_verified_metric_values_count",
        "public_attestation_summary_count",
    }
    assert all(
        contract.scope == "exact_location" and "WHERE location_id = %s" in contract.sql
        for contract in REPORTING_QUERY_REGISTRY.values()
    )


def test_registered_reader_accepts_database_uuid_objects(monkeypatch):
    conn = FakeReportingConnection()
    monkeypatch.setenv("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro")
    location_id = UUID("d4be5d0d-0b44-4e81-9b69-463bc87a9e11")

    assert count_registered_reporting_rows(
        "public_farm_summary_count",
        location_id,
        connection_factory=lambda: conn,
    ) == 3
    assert next(
        params for sql, params in conn.statements
        if "SELECT count(*) FROM kokonut_reporting." in sql
    ) == (str(location_id),)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("readable_relations", "outside the approved reporting views"),
        ("has_write_privilege", "application write privileges"),
        ("has_security_definer", "security-definer function"),
        ("can_connect_other_database", "another database"),
        ("role_membership", "assume another database role"),
    ],
)
def test_reader_verification_rejects_acl_drift(change, message):
    conn = FakeReportingConnection()
    if change == "readable_relations":
        conn.readable_relations.append(("public", "metric_value", False))
    else:
        setattr(conn, change, True)

    with pytest.raises(ReportingReaderPolicyError, match=message):
        validate_reporting_connection(conn, expected_user="kokonut_analytics_ro")


def test_reader_verification_rejects_elevated_login():
    conn = FakeReportingConnection()
    conn.identity = ("kokonut_analytics_ro", "kokonut_analytics_ro", True, *(False for _ in range(8)))

    with pytest.raises(ReportingReaderPolicyError, match="elevated privileges"):
        validate_reporting_connection(conn, expected_user="kokonut_analytics_ro")


def test_failed_reader_check_rolls_back_and_closes_connection(monkeypatch):
    conn = FakeReportingConnection()
    conn.readable_relations.append(("public", "metric_value", False))
    monkeypatch.setenv("KOKONUT_ANALYTICS_USER", "kokonut_analytics_ro")

    with pytest.raises(ReportingReaderPolicyError):
        count_registered_reporting_rows(
            "public_farm_summary_count",
            "d4be5d0d-0b44-4e81-9b69-463bc87a9e11",
            connection_factory=lambda: conn,
        )

    assert conn.commits == 0
    assert conn.rollbacks == 1
    assert conn.closed
    assert not any("SELECT count(*) FROM kokonut_reporting." in sql for sql, _ in conn.statements)


def test_saved_sql_error_diagnostic_does_not_echo_query_text():
    class DatabaseError(RuntimeError):
        pgcode = "42501"

    exc = DatabaseError("secret query text")

    assert reporting_reader.safe_query_error(exc) == "DatabaseError (SQLSTATE 42501)"
    assert "secret" not in reporting_reader.safe_query_error(exc)


def test_policy_error_diagnostic_keeps_safe_operator_guidance():
    exc = ReportingReaderPolicyError("saved reporting query login has unexpected identity or elevated privileges")

    assert reporting_reader.safe_query_error(exc) == str(exc)
