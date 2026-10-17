"""Saved dataset SQL stays on the restricted reporting connection."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from services.export import dataset_refresh


class FakeCursor:
    def __init__(self, conn, *, return_dataset=True):
        self.conn = conn
        self.return_dataset = return_dataset
        self.rowcount = 1
        self.result = None
        self.closed = False

    def execute(self, sql: str, params: Any = None) -> None:
        self.conn.statements.append((sql, params))
        if sql.startswith("SELECT id, name, dataset_type, query_sql"):
            self.result = (
                {
                    "id": "dataset-1",
                    "name": "Approved fixture",
                    "dataset_type": "reporting",
                    "query_sql": self.conn.query_sql,
                    "refresh_interval_minutes": 60,
                }
                if self.return_dataset
                else None
            )

    def fetchone(self):
        return self.result

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class FakeApplicationConnection:
    def __init__(self, *, return_dataset=True):
        self.query_sql = "SELECT * FROM kokonut_reporting.v_farm_summary"
        self.return_dataset = return_dataset
        self.statements: list[tuple[str, Any]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self._first_cursor = True

    def cursor(self, *args, **kwargs):
        if self._first_cursor:
            self._first_cursor = False
            return FakeCursor(self, return_dataset=self.return_dataset)
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_refresh_executes_saved_sql_only_through_reporting_reader(monkeypatch):
    conn = FakeApplicationConnection()
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)
    executed: list[str] = []

    def reporting_count(query_sql: str) -> int:
        executed.append(query_sql)
        return 7

    monkeypatch.setattr(dataset_refresh, "count_reporting_rows", reporting_count)

    result = dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert result["status"] == "active"
    assert result["row_count"] == 7
    assert executed == [conn.query_sql]
    assert all(conn.query_sql not in sql for sql, _ in conn.statements)
    update_sql, update_params = conn.statements[-1]
    assert update_sql.lstrip().startswith("UPDATE dashboard_dataset")
    assert json.loads(update_params[0])["row_count"] == 7
    assert conn.commits == 1


def test_refresh_records_sanitized_reader_failure_without_echoing_sql(monkeypatch, capsys):
    conn = FakeApplicationConnection()
    conn.query_sql = "SELECT 'private literal' FROM unauthorized_table"
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)

    def fail_reader(query_sql: str) -> int:
        raise RuntimeError(f"failed query: {query_sql}")

    monkeypatch.setattr(dataset_refresh, "count_reporting_rows", fail_reader)

    result = dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert result["status"] == "error"
    assert result["row_count"] == 0
    assert result["error"] == "RuntimeError"
    output = capsys.readouterr().out
    assert "private literal" not in output
    assert "unauthorized_table" not in output
    assert conn.commits == 1


def test_inactive_dataset_is_never_sent_to_reader(monkeypatch):
    conn = FakeApplicationConnection(return_dataset=False)
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)
    monkeypatch.setattr(
        dataset_refresh,
        "count_reporting_rows",
        lambda query_sql: pytest.fail("inactive dataset SQL must not execute"),
    )

    with pytest.raises(ValueError, match="Active dataset"):
        dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert conn.commits == 0


def test_changed_dataset_query_does_not_receive_stale_refresh_metadata(monkeypatch):
    conn = FakeApplicationConnection()
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)
    monkeypatch.setattr(dataset_refresh, "count_reporting_rows", lambda query_sql: 7)

    class ConcurrentEditCursor(FakeCursor):
        def execute(self, sql: str, params: Any = None) -> None:
            super().execute(sql, params)
            if sql.lstrip().startswith("UPDATE dashboard_dataset"):
                self.rowcount = 0

    conn.cursor = lambda *args, **kwargs: (
        FakeCursor(conn, return_dataset=True) if conn._first_cursor else ConcurrentEditCursor(conn)
    )
    conn._first_cursor = False

    with pytest.raises(RuntimeError, match="changed while its reporting query ran"):
        dataset_refresh.refresh_dataset(conn, "dataset-1")

    update_sql, update_params = conn.statements[-1]
    assert "query_sql = %s" in update_sql
    assert update_params[1:] == ("dataset-1", conn.query_sql)
    assert conn.commits == 0
    assert conn.rollbacks == 1


@pytest.mark.parametrize("arguments", [["--all"], ["--dataset-id", "dataset-1"]])
def test_disabled_refresh_fails_before_opening_database(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", *arguments])
    requested_features: list[str] = []

    def reject_feature(feature_name: str) -> None:
        requested_features.append(feature_name)
        raise RuntimeError("legacy dataset SQL is disabled")

    monkeypatch.setattr(dataset_refresh, "require_feature", reject_feature)
    monkeypatch.setattr(
        dataset_refresh,
        "get_pg",
        lambda: pytest.fail("disabled refresh must fail before opening PostgreSQL"),
    )

    with pytest.raises(RuntimeError, match="legacy dataset SQL is disabled"):
        dataset_refresh.main()

    assert requested_features == ["legacy_dataset_sql"]


def test_list_remains_available_when_refresh_feature_is_disabled(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", "--list"])
    conn = FakeApplicationConnection()
    monkeypatch.setattr(
        dataset_refresh,
        "require_feature",
        lambda feature_name: pytest.fail("listing must not require the refresh feature"),
    )
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)

    dataset_refresh.main()

    assert "No active datasets found." in capsys.readouterr().out
    assert conn.closed


def test_no_operation_prints_help_without_opening_database(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["dataset_refresh"])
    monkeypatch.setattr(
        dataset_refresh,
        "get_pg",
        lambda: pytest.fail("help output must not open PostgreSQL"),
    )

    dataset_refresh.main()

    assert "Dashboard Dataset Refresh Engine" in capsys.readouterr().out


def test_dataset_refresh_all_redacts_outer_exception_and_dataset_name(
    monkeypatch, capsys
):
    secret = "database password=private-token"
    conn = FakeApplicationConnection()
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", "--all"])
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)
    monkeypatch.setattr(
        dataset_refresh,
        "list_datasets",
        lambda _conn: [{"id": "dataset-1", "name": "Confidential dashboard name"}],
    )
    monkeypatch.setattr(
        dataset_refresh,
        "refresh_dataset",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    dataset_refresh.main()

    output = capsys.readouterr().out
    assert "dataset refresh failed (RuntimeError)" in output
    assert "Confidential dashboard name" not in output
    assert secret not in output
    assert "1 failed" in output
    assert conn.closed


def test_single_dataset_refresh_redacts_outer_exception_and_closes(
    monkeypatch, capsys
):
    secret = "database password=private-token"
    conn = FakeApplicationConnection()
    monkeypatch.setattr(
        sys, "argv", ["dataset_refresh", "--dataset-id", "dataset-1"]
    )
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)
    monkeypatch.setattr(
        dataset_refresh,
        "refresh_dataset",
        lambda *_args: (_ for _ in ()).throw(ValueError(secret)),
    )

    with pytest.raises(RuntimeError, match=r"dataset refresh failed \(ValueError\)") as error:
        dataset_refresh.main()

    output = capsys.readouterr().out
    assert secret not in str(error.value)
    assert secret not in output
    assert conn.closed


@pytest.mark.parametrize("arguments", [["--all"], ["--dataset-id", "dataset-1"]])
def test_reported_dataset_query_error_is_not_echoed(monkeypatch, capsys, arguments):
    secret = "database password=private-token"
    conn = FakeApplicationConnection()
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", *arguments])
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)
    monkeypatch.setattr(
        dataset_refresh,
        "list_datasets",
        lambda *_args: [{"id": "dataset-1", "name": "Fixture dataset"}],
    )
    monkeypatch.setattr(
        dataset_refresh,
        "refresh_dataset",
        lambda *_args: {"status": "error", "error": secret},
    )

    dataset_refresh.main()

    output = capsys.readouterr().out
    assert "reported query error" in output
    assert secret not in output
    assert conn.closed
