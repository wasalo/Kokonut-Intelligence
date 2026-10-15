"""Transaction-bound tenant checks for report-review reads."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import operator_review
from services.gateway.operator_review import (
    ReportPayloadTooLarge,
    get_submitted_report,
    list_submitted_reports,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
REPORT_ID = "22222222-2222-4222-8222-222222222222"
CREATED_AT = datetime(2026, 10, 15, 12, 30, tzinfo=timezone.utc)


def _list_row():
    return {
        "id": UUID(REPORT_ID),
        "report_name": "Farm summary",
        "report_type": "farm_summary",
        "status": "submitted",
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 14),
        "snapshot_hash": "a" * 64,
        "created_at": CREATED_AT,
        "location_name": "Kokonut Genesis",
    }


def _detail_row(**overrides):
    row = _list_row()
    row.update({"report_data": {"summary": "Reviewed fixture"}, "report_size": 31})
    row.update(overrides)
    return row


class FakeCursor:
    def __init__(self, connection, list_row=None, detail_row=None):
        self.connection = connection
        self.list_row = list_row or _list_row()
        self.detail_row = detail_row or _detail_row()
        self.description = None
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.connection.statements.append((sql, params))
        if "CASE WHEN octet_length(rs.report_data::text)" in sql:
            self.result = self.detail_row
            self.description = [SimpleNamespace(name=name) for name in self.detail_row]
        elif "FROM report_snapshot AS rs" in sql:
            self.result = self.list_row
            self.description = [SimpleNamespace(name=name) for name in self.list_row]

    def fetchall(self):
        return [tuple(self.result.values())]

    def fetchone(self):
        return tuple(self.result.values()) if self.result is not None else None


class FakeConnection:
    autocommit = False

    def __init__(self, list_row=None, detail_row=None):
        self.statements = []
        self.cursor_instance = FakeCursor(self, list_row, detail_row)
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def tenant_context_spy(monkeypatch):
    calls = []

    def set_context(connection, **kwargs):
        calls.append((connection, kwargs))
        connection.statements.append(("SET TENANT CONTEXT", kwargs))

    monkeypatch.setattr(operator_review, "set_operator_tenant_context", set_context)
    return calls


def _assert_context_precedes_report_read(connection, tenant_context_spy, query_marker):
    assert len(tenant_context_spy) == 1
    context_connection, context = tenant_context_spy[0]
    assert context_connection is connection
    assert context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "report_snapshot_review",
        "action": "read",
    }
    statements = connection.statements
    context_index = statements.index(("SET TENANT CONTEXT", context))
    query_index = next(i for i, (sql, _params) in enumerate(statements) if query_marker in sql)
    assert statements[0][0] == "SET TRANSACTION READ ONLY"
    assert context_index < query_index


def test_report_queue_uses_same_transaction_tenant_context_and_rolls_back(
    tenant_context_spy,
):
    connection = FakeConnection()

    rows = list_submitted_reports(
        OPERATOR_ID,
        LOCATION_ID,
        7,
        connection_factory=lambda: connection,
    )

    assert rows[0]["id"] == REPORT_ID
    assert rows[0]["period_start"] == "2026-10-01"
    assert rows[0]["created_at"] == CREATED_AT.isoformat()
    query = next(
        (sql, params)
        for sql, params in connection.statements
        if "FROM report_snapshot AS rs" in sql
    )
    assert query[1] == (LOCATION_ID, OPERATOR_ID, 7)
    assert "grant_row.location_id = rs.location_id" in query[0]
    assert "operator_scope_grant_allows" in query[0]
    _assert_context_precedes_report_read(connection, tenant_context_spy, "FROM report_snapshot AS rs")
    assert connection.rolled_back and connection.closed


def test_report_detail_uses_same_transaction_tenant_context_and_bounds_payload(
    tenant_context_spy,
):
    connection = FakeConnection()

    result = get_submitted_report(
        OPERATOR_ID,
        REPORT_ID,
        LOCATION_ID,
        connection_factory=lambda: connection,
    )

    assert result["id"] == REPORT_ID
    assert result["report_data"] == {"summary": "Reviewed fixture"}
    assert "report_size" not in result
    query = next(
        (sql, params)
        for sql, params in connection.statements
        if "CASE WHEN octet_length(rs.report_data::text)" in sql
    )
    assert query[1] == (REPORT_ID, LOCATION_ID, OPERATOR_ID)
    assert "grant_row.location_id = rs.location_id" in query[0]
    assert "operator_scope_grant_allows" in query[0]
    _assert_context_precedes_report_read(
        connection,
        tenant_context_spy,
        "CASE WHEN octet_length(rs.report_data::text)",
    )
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("detail", [False, True])
def test_legacy_or_unqualified_grant_denial_runs_no_report_query_and_cleans_up(
    detail, monkeypatch
):
    connection = FakeConnection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("tenant-qualified grant required")

    monkeypatch.setattr(operator_review, "set_operator_tenant_context", deny)
    reader = get_submitted_report if detail else list_submitted_reports
    args = (OPERATOR_ID, REPORT_ID, LOCATION_ID) if detail else (OPERATOR_ID, LOCATION_ID)

    with pytest.raises(TenantContextDenied, match="tenant-qualified"):
        reader(*args, connection_factory=lambda: connection)

    assert not any("FROM report_snapshot AS rs" in sql for sql, _params in connection.statements)
    assert connection.rolled_back and connection.closed


def test_oversized_report_detail_is_rejected_and_connection_is_cleaned(tenant_context_spy):
    connection = FakeConnection(detail_row=_detail_row(report_data=None, report_size=524289))

    with pytest.raises(ReportPayloadTooLarge, match="512 KiB"):
        get_submitted_report(
            OPERATOR_ID,
            REPORT_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    _assert_context_precedes_report_read(
        connection,
        tenant_context_spy,
        "CASE WHEN octet_length(rs.report_data::text)",
    )
    assert connection.rolled_back and connection.closed
