"""Unit contracts for tenant-scoped report export Gateway services."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import psycopg2
import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import report_exports
from services.gateway.report_exports import (
    ReportExportArtifactUnavailable,
    ReportExportNotFound,
    download_report_export,
    get_report_export,
    list_exportable_report_snapshots,
    list_report_exports,
    request_report_export,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
SNAPSHOT_ID = "22222222-2222-4222-8222-222222222222"
REQUEST_ID = "33333333-3333-4333-8333-333333333333"
ARTIFACT_ID = "44444444-4444-4444-8444-444444444444"
IDEMPOTENCY_KEY = "55555555-5555-4555-8555-555555555555"
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _summary(**overrides):
    row = {
        "request_id": UUID(REQUEST_ID),
        "snapshot_id": UUID(SNAPSHOT_ID),
        "location_id": UUID(LOCATION_ID),
        "status": "pending",
        "attempt_count": 0,
        "artifact_size": None,
        "created_at": NOW,
        "updated_at": NOW,
        "completed_at": None,
        "last_error_class": None,
    }
    return {**row, **overrides}


class FakeCursor:
    def __init__(self, connection, *, one=None, many=None):
        self.connection = connection
        self.one = one
        self.many = many or []
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.connection.statements.append((sql, params))
        if "request_report_snapshot_export" in sql:
            row = {"request_id": UUID(REQUEST_ID), "status": "pending", "created_at": NOW}
        elif "authorize_report_snapshot_export_download" in sql:
            content = b'{"summary":"safe"}'
            row = {
                "artifact_id": UUID(ARTIFACT_ID),
                "artifact_sha256": hashlib.sha256(content).hexdigest(),
                "artifact_size": len(content),
            }
        elif "get_report_snapshot_export" in sql:
            row = self.one
        else:
            row = None
        if row is not None:
            self.description = [SimpleNamespace(name=key) for key in row]
            self.one = tuple(row.values())
        if "list_report_snapshot_exports" in sql or "list_report_snapshot_export_candidates" in sql:
            self.description = [SimpleNamespace(name=key) for key in self.many[0]] if self.many else []
            self.many = [tuple(row.values()) for row in self.many]

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    autocommit = False

    def __init__(self, *, one=None, many=None):
        self.statements = []
        self.cursor_value = FakeCursor(self, one=one, many=many)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def context_calls(monkeypatch):
    calls = []

    def set_context(connection, **kwargs):
        calls.append((connection, kwargs))
        connection.statements.append(("SET OPERATOR CONTEXT", kwargs))

    monkeypatch.setattr(report_exports, "set_operator_tenant_context", set_context)
    return calls


def _assert_context_precedes_function(connection, context_calls, function_name, action):
    assert len(context_calls) == 1
    context_connection, context = context_calls[0]
    assert context_connection is connection
    assert context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "report_snapshot_export",
        "action": action,
    }
    context_index = connection.statements.index(("SET OPERATOR CONTEXT", context))
    function_index = next(
        index
        for index, (sql, _params) in enumerate(connection.statements)
        if function_name in sql
    )
    assert context_index < function_index
    assert any(sql == "SET LOCAL statement_timeout = '5s'" for sql, _ in connection.statements)
    assert any(sql == "SET LOCAL lock_timeout = '2s'" for sql, _ in connection.statements)
    assert not any("SET TRANSACTION READ ONLY" in sql for sql, _ in connection.statements)


def test_request_uses_create_scope_and_commits_only_after_bounded_function(context_calls):
    connection = FakeConnection()

    result = request_report_export(
        OPERATOR_ID,
        LOCATION_ID,
        SNAPSHOT_ID,
        IDEMPOTENCY_KEY,
        connection_factory=lambda: connection,
    )

    assert result == {"request_id": UUID(REQUEST_ID), "status": "pending", "created_at": NOW}
    _assert_context_precedes_function(
        connection, context_calls, "request_report_snapshot_export", "create"
    )
    function_call = next(
        (sql, params)
        for sql, params in connection.statements
        if "request_report_snapshot_export" in sql
    )
    assert function_call[1] == (LOCATION_ID, SNAPSHOT_ID, IDEMPOTENCY_KEY)
    assert connection.committed and not connection.rolled_back and connection.closed


def test_report_export_list_uses_read_grant_and_bounded_location_scope(context_calls):
    connection = FakeConnection(many=[_summary()])

    rows = list_report_exports(
        OPERATOR_ID,
        LOCATION_ID,
        25,
        connection_factory=lambda: connection,
    )

    assert rows == [_summary()]
    _assert_context_precedes_function(
        connection, context_calls, "list_report_snapshot_exports", "read"
    )
    query = next(
        (sql, params)
        for sql, params in connection.statements
        if "list_report_snapshot_exports" in sql
    )
    assert query[1] == (LOCATION_ID, 25)
    assert connection.rolled_back and connection.closed


def test_candidate_list_uses_same_transaction_read_context_and_overfetch_pagination(context_calls):
    candidate = {
        "snapshot_id": UUID(SNAPSHOT_ID),
        "location_id": UUID(LOCATION_ID),
        "report_name": "Synthetic impact report",
        "report_type": "impact",
        "status": "verified",
        "period_start": None,
        "period_end": None,
        "snapshot_hash": "a" * 64,
        "created_at": NOW,
    }
    connection = FakeConnection(many=[candidate, {**candidate, "snapshot_id": UUID(ARTIFACT_ID)}])

    result = list_exportable_report_snapshots(
        OPERATOR_ID,
        LOCATION_ID,
        1,
        7,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "limit": 1,
        "offset": 7,
        "has_more": True,
        "data": [candidate],
    }
    _assert_context_precedes_function(
        connection, context_calls, "list_report_snapshot_export_candidates", "read"
    )
    query = next(
        (sql, params)
        for sql, params in connection.statements
        if "list_report_snapshot_export_candidates" in sql
    )
    assert query[1] == (LOCATION_ID, 1, 7)
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (51, 0), (1, -1), (1, 5001), (True, 0), (1, True)],
)
def test_invalid_candidate_list_page_fails_before_database_open(limit, offset):
    opened = False

    def connect():
        nonlocal opened
        opened = True
        return FakeConnection()

    with pytest.raises(ValueError):
        list_exportable_report_snapshots(
            OPERATOR_ID,
            LOCATION_ID,
            limit,
            offset,
            connection_factory=connect,
        )
    assert not opened


@pytest.mark.parametrize("limit", [0, 51])
def test_invalid_list_bound_fails_before_opening_database(limit):
    opened = False

    def connect():
        nonlocal opened
        opened = True
        return FakeConnection()

    with pytest.raises(ValueError, match="between 1 and 50"):
        list_report_exports(OPERATOR_ID, LOCATION_ID, limit, connection_factory=connect)
    assert not opened


def test_database_idempotency_collision_becomes_safe_conflict_and_rolls_back(
    monkeypatch, context_calls
):
    connection = FakeConnection()

    def raise_conflict(sql, params=None):
        connection.statements.append((sql, params))
        if "request_report_snapshot_export" in sql:
            raise psycopg2.errors.UniqueViolation("sensitive database detail")

    connection.cursor_value.execute = raise_conflict
    with pytest.raises(report_exports.ReportExportConflict):
        request_report_export(
            OPERATOR_ID,
            LOCATION_ID,
            SNAPSHOT_ID,
            IDEMPOTENCY_KEY,
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed


def test_missing_or_non_exportable_source_zero_rows_becomes_not_found(context_calls):
    connection = FakeConnection()

    def no_source(sql, params=None):
        connection.statements.append((sql, params))
        if "request_report_snapshot_export" in sql:
            connection.cursor_value.one = None
            connection.cursor_value.description = None

    connection.cursor_value.execute = no_source
    with pytest.raises(ReportExportNotFound):
        request_report_export(
            OPERATOR_ID,
            LOCATION_ID,
            SNAPSHOT_ID,
            IDEMPOTENCY_KEY,
            connection_factory=lambda: connection,
        )
    assert not connection.committed
    assert connection.rolled_back and connection.closed


def test_report_export_detail_uses_read_context_and_returns_no_row_when_missing(context_calls):
    connection = FakeConnection(one=None)
    # Cursor's get-function result can be independently set to None after query.
    result = get_report_export(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result is None
    _assert_context_precedes_function(
        connection, context_calls, "get_report_snapshot_export", "read"
    )
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("denied_action", ["create", "read", "download"])
def test_tenant_denial_prevents_export_function_call_and_closes_connection(
    monkeypatch, denied_action
):
    connection = FakeConnection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("grant required")

    monkeypatch.setattr(report_exports, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        if denied_action == "create":
            request_report_export(
                OPERATOR_ID, LOCATION_ID, SNAPSHOT_ID, IDEMPOTENCY_KEY,
                connection_factory=lambda: connection,
            )
        elif denied_action == "read":
            list_report_exports(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
            )
        else:
            download_report_export(
                OPERATOR_ID, LOCATION_ID, REQUEST_ID,
                connection_factory=lambda: connection,
                artifact_store_factory=lambda: None,
            )
    assert not any("report_snapshot_export" in sql for sql, _params in connection.statements)
    assert connection.rolled_back and connection.closed


def test_download_reads_private_store_while_authorization_transaction_is_open(context_calls):
    content = b'{"summary":"safe"}'
    connection = FakeConnection()

    class Store:
        def read(self, artifact_id, *, max_bytes):
            assert str(artifact_id) == ARTIFACT_ID
            assert max_bytes == len(content)
            assert not connection.closed
            return content

    artifact = download_report_export(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
        artifact_store_factory=Store,
    )

    assert artifact.request_id == UUID(REQUEST_ID)
    assert artifact.content == content
    _assert_context_precedes_function(
        connection, context_calls, "authorize_report_snapshot_export_download", "download"
    )
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("content", [b'{"tampered":true}', b"short"])
def test_download_rejects_hash_or_size_mismatch(content, context_calls):
    connection = FakeConnection()

    class Store:
        def read(self, _artifact_id, *, max_bytes):
            assert max_bytes == len(b'{"summary":"safe"}')
            return content

    with pytest.raises(ReportExportArtifactUnavailable):
        download_report_export(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=lambda: connection,
            artifact_store_factory=Store,
        )
    assert connection.rolled_back and connection.closed


def test_download_missing_metadata_does_not_open_storage(context_calls):
    connection = FakeConnection()
    connection.cursor_value.execute = lambda sql, params=None: (
        connection.statements.append((sql, params)),
        setattr(connection.cursor_value, "description", None),
        setattr(connection.cursor_value, "one", None),
    )
    opened = False

    def store_factory():
        nonlocal opened
        opened = True
        raise AssertionError("storage must not open for an unavailable request")

    with pytest.raises(ReportExportNotFound):
        download_report_export(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=lambda: connection,
            artifact_store_factory=store_factory,
        )
    assert not opened
    assert connection.rolled_back and connection.closed
