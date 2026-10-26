"""Saved dashboard refreshes use only registered, location-bound query IDs."""

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
        if sql.startswith("SELECT id, name, dataset_type, query_id"):
            self.result = (
                {
                    "id": "dataset-1",
                    "name": "Approved fixture",
                    "dataset_type": "reporting",
                    "query_id": self.conn.query_id,
                    "location_id": self.conn.location_id,
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
        self.query_sql = "SELECT 'private legacy SQL' FROM unauthorized_table"
        self.query_id = "public_farm_summary_count"
        self.location_id = "d4be5d0d-0b44-4e81-9b69-463bc87a9e11"
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


def test_refresh_routes_only_registered_query_id_and_exact_location(monkeypatch):
    conn = FakeApplicationConnection()
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)
    executed: list[tuple[str, str]] = []

    def reporting_count(query_id: str, location_id: str) -> int:
        executed.append((query_id, location_id))
        return 7

    monkeypatch.setattr(dataset_refresh, "count_registered_reporting_rows", reporting_count)

    result = dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert result["status"] == "active"
    assert result["row_count"] == 7
    assert executed == [(conn.query_id, conn.location_id)]
    assert all(conn.query_sql not in sql for sql, _ in conn.statements)
    assert "query_sql" not in conn.statements[0][0]
    update_sql, update_params = conn.statements[-1]
    assert update_sql.lstrip().startswith("UPDATE dashboard_dataset")
    assert json.loads(update_params[0])["row_count"] == 7
    assert conn.commits == 1


def test_refresh_records_sanitized_registry_failure_without_echoing_sql(monkeypatch, capsys):
    conn = FakeApplicationConnection()
    conn.query_sql = "SELECT 'private literal' FROM unauthorized_table"
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)

    def fail_reader(query_id: str, location_id: str) -> int:
        assert query_id == conn.query_id
        assert location_id == conn.location_id
        raise RuntimeError(f"failed legacy SQL: {conn.query_sql}")

    monkeypatch.setattr(dataset_refresh, "count_registered_reporting_rows", fail_reader)

    result = dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert result["status"] == "error"
    assert result["row_count"] == 0
    assert result["error"] == "RuntimeError"
    output = capsys.readouterr().out
    assert "private literal" not in output
    assert "unauthorized_table" not in output
    assert conn.commits == 1


@pytest.mark.parametrize("failure_phase", ["execute", "fetchone"])
def test_refresh_definition_cursor_closes_when_lookup_fails(monkeypatch, failure_phase):
    conn = FakeApplicationConnection()
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(
        dataset_refresh,
        "count_registered_reporting_rows",
        lambda _query: pytest.fail("reporting reader must not run after lookup failure"),
    )

    class FailingCursor(FakeCursor):
        def execute(self, sql: str, params: Any = None) -> None:
            if failure_phase == "execute":
                raise RuntimeError("synthetic definition lookup failure")
            super().execute(sql, params)

        def fetchone(self):
            if failure_phase == "fetchone":
                raise RuntimeError("synthetic definition lookup failure")
            return super().fetchone()

    cursor = FailingCursor(conn)
    conn.cursor = lambda *args, **kwargs: cursor

    with pytest.raises(RuntimeError, match="synthetic definition lookup failure"):
        dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert cursor.closed


def test_inactive_dataset_is_never_sent_to_reader(monkeypatch):
    conn = FakeApplicationConnection(return_dataset=False)
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)
    monkeypatch.setattr(
        dataset_refresh,
        "count_registered_reporting_rows",
        lambda *_args: pytest.fail("inactive dataset query must not execute"),
    )

    with pytest.raises(ValueError, match="Active dataset"):
        dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert conn.commits == 0


def test_unregistered_dataset_is_rejected_before_reporting_or_refresh_metadata(monkeypatch):
    conn = FakeApplicationConnection()
    conn.query_id = None
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(
        dataset_refresh,
        "count_registered_reporting_rows",
        lambda *_args: pytest.fail("unregistered dataset must not open the reporting reader"),
    )

    with pytest.raises(ValueError, match="missing or not registered"):
        dataset_refresh.refresh_dataset(conn, "dataset-1")

    assert not any(sql.lstrip().startswith("UPDATE dashboard_dataset") for sql, _ in conn.statements)
    assert conn.commits == 0
    assert conn.rollbacks == 0


def test_changed_dataset_contract_does_not_receive_stale_refresh_metadata(monkeypatch):
    conn = FakeApplicationConnection()
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda name: None)
    monkeypatch.setattr(dataset_refresh, "count_registered_reporting_rows", lambda *_args: 7)

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
    assert "query_id IS NOT DISTINCT FROM %s" in update_sql
    assert "location_id IS NOT DISTINCT FROM %s" in update_sql
    assert update_params[1:] == ("dataset-1", conn.query_id, conn.location_id)
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
    assert "query_id" in conn.statements[0][0]
    assert "location_id" in conn.statements[0][0]
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


@pytest.mark.parametrize(
    "arguments",
    [["--all", "--list"], ["--all", "--dataset-id", "dataset-1"]],
)
def test_conflicting_refresh_selectors_fail_before_opening_database(
    monkeypatch, arguments
):
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", *arguments])
    monkeypatch.setattr(
        dataset_refresh,
        "get_pg",
        lambda: pytest.fail("conflicting selectors must fail before PostgreSQL"),
    )

    with pytest.raises(SystemExit) as error:
        dataset_refresh.main()

    assert error.value.code == 2


@pytest.mark.parametrize("failure_phase", ["execute", "fetchall"])
def test_list_datasets_closes_cursor_when_inventory_fails(failure_phase):
    conn = FakeApplicationConnection()

    class FailingCursor(FakeCursor):
        def execute(self, _sql: str, _params: Any = None) -> None:
            if failure_phase == "execute":
                raise RuntimeError("synthetic inventory failure")

        def fetchall(self):
            if failure_phase == "fetchall":
                raise RuntimeError("synthetic inventory failure")
            return []

    cursor = FailingCursor(conn)
    conn.cursor = lambda *args, **kwargs: cursor

    with pytest.raises(RuntimeError, match="synthetic inventory failure"):
        dataset_refresh.list_datasets(conn)

    assert cursor.closed


@pytest.mark.parametrize("arguments", [["--list"], ["--all"]])
def test_list_and_bulk_refresh_close_connection_when_inventory_fails(
    monkeypatch, capsys, arguments
):
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", *arguments])
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    conn = FakeApplicationConnection()
    secret = "database password=private-token"
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)
    monkeypatch.setattr(
        dataset_refresh,
        "list_datasets",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    with pytest.raises(RuntimeError, match=r"dataset inventory failed \(RuntimeError\)") as error:
        dataset_refresh.main()

    output = capsys.readouterr().out
    assert secret not in str(error.value)
    assert secret not in output
    assert "dataset inventory failed (RuntimeError)" in output
    assert conn.closed


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
        lambda _conn: [{
            "id": "dataset-1",
            "name": "Confidential dashboard name",
            "query_id": "public_farm_summary_count",
            "location_id": "d4be5d0d-0b44-4e81-9b69-463bc87a9e11",
        }],
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


def test_dataset_refresh_all_skips_unsupported_contracts_without_writes(
    monkeypatch, capsys
):
    conn = FakeApplicationConnection()
    datasets = [
        {"id": "legacy-null", "name": "Legacy SQL", "query_id": None, "location_id": conn.location_id},
        {
            "id": "unknown-query",
            "name": "Unknown registry entry",
            "query_id": "unreviewed_query",
            "location_id": conn.location_id,
        },
        {
            "id": "unscoped-query",
            "name": "Missing location",
            "query_id": "public_farm_summary_count",
            "location_id": None,
        },
    ]
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", "--all"])
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)
    monkeypatch.setattr(dataset_refresh, "list_datasets", lambda _conn: datasets)
    monkeypatch.setattr(
        dataset_refresh,
        "refresh_dataset",
        lambda *_args: pytest.fail("unsupported dataset must not be refreshed"),
    )

    dataset_refresh.main()

    output = capsys.readouterr().out
    assert "Skipped 3 active dataset(s)" in output
    assert "No registered datasets are eligible for refresh." in output
    assert "Legacy SQL" not in output
    assert not conn.statements
    assert conn.commits == 0
    assert conn.closed


def test_dataset_refresh_all_refreshes_registered_rows_and_reports_skips(
    monkeypatch, capsys
):
    conn = FakeApplicationConnection()
    datasets = [
        {"id": "legacy-null", "query_id": None, "location_id": conn.location_id},
        {
            "id": "registered",
            "query_id": "public_farm_summary_count",
            "location_id": conn.location_id,
        },
    ]
    calls = []
    monkeypatch.setattr(sys, "argv", ["dataset_refresh", "--all"])
    monkeypatch.setattr(dataset_refresh, "require_feature", lambda _name: None)
    monkeypatch.setattr(dataset_refresh, "get_pg", lambda: conn)
    monkeypatch.setattr(dataset_refresh, "list_datasets", lambda _conn: datasets)
    monkeypatch.setattr(
        dataset_refresh,
        "refresh_dataset",
        lambda _conn, dataset_id: calls.append(dataset_id) or {
            "status": "active", "name": "Registered", "row_count": 2, "duration_ms": 1,
        },
    )

    dataset_refresh.main()

    output = capsys.readouterr().out
    assert calls == ["registered"]
    assert "1 refreshed, 0 failed, 1 skipped" in output
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
        lambda *_args: [{
            "id": "dataset-1",
            "name": "Fixture dataset",
            "query_id": "public_farm_summary_count",
            "location_id": "d4be5d0d-0b44-4e81-9b69-463bc87a9e11",
        }],
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
