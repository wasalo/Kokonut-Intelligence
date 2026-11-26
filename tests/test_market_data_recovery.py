"""Mocked recovery and transaction checks for the isolated market-data writer."""

from __future__ import annotations

import json

import pytest

from services.ingestion import market_data
from services.ingestion import market_data_worker as worker


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        if self.connection.execute_error is not None:
            raise self.connection.execute_error

    def fetchone(self):
        return (self.connection.rows_affected,)


class _Connection:
    def __init__(self, rows_affected=2, execute_error=None):
        self.cursor_instance = _Cursor(self)
        self.rows_affected = rows_affected
        self.execute_error = execute_error
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _parsed_record(code="COFFEE", date="2025-01-01"):
    return {
        "commodity_code": code,
        "commodity_name": "Coffee",
        "price_date": date,
        "price_per_unit": 7.89,
    }


def _enable_worker(monkeypatch):
    monkeypatch.setattr(worker, "is_enabled", lambda _feature: True)


def _stub_world_bank(monkeypatch, records):
    monkeypatch.setattr(worker, "download_pink_sheet", lambda: b"fixture")
    monkeypatch.setattr(worker, "parse_pink_sheet", lambda *_args, **_kwargs: records)


def _assert_bounded_call(connection, function_name):
    statements = connection.cursor_instance.statements
    assert len(statements) == 1
    statement, parameters = statements[0]
    normalized_sql = " ".join(statement.split())
    assert normalized_sql.startswith("SELECT ")
    assert function_name in normalized_sql
    assert not any(
        dml in normalized_sql.upper() for dml in ("INSERT INTO", "UPDATE ", "DELETE FROM")
    )
    return parameters


def test_world_bank_download_failure_does_not_fallback_to_seed(monkeypatch):
    _enable_worker(monkeypatch)
    monkeypatch.setattr(
        worker,
        "download_pink_sheet",
        lambda: (_ for _ in ()).throw(OSError("provider unavailable")),
    )
    monkeypatch.setattr(
        worker, "get_worker_db", lambda *_args, **_kwargs: pytest.fail("worker DB opened")
    )
    monkeypatch.setattr(
        market_data, "run_seed_data", lambda **_kwargs: pytest.fail("seed fallback")
    )

    with pytest.raises(RuntimeError, match="use explicit --source seed"):
        market_data.run_world_bank()


@pytest.mark.parametrize(
    ("records", "message"),
    [([], "no usable price records"), ([_parsed_record("UNSUPPORTED")], "no records for COFFEE")],
)
def test_world_bank_empty_or_unmatched_response_fails_before_worker_database(
    monkeypatch, records, message
):
    _enable_worker(monkeypatch)
    _stub_world_bank(monkeypatch, records)
    monkeypatch.setattr(
        worker, "get_worker_db", lambda *_args, **_kwargs: pytest.fail("worker DB opened")
    )

    with pytest.raises(RuntimeError, match=message):
        market_data.run_world_bank(commodity="coffee")


def test_world_bank_persists_audited_batch_through_one_bounded_call(monkeypatch):
    connection = _Connection(rows_affected=2)
    _enable_worker(monkeypatch)
    _stub_world_bank(monkeypatch, [_parsed_record(), _parsed_record(date="2025-02-01")])
    monkeypatch.setattr(worker, "get_worker_db", lambda key: connection)

    inserted = market_data.run_world_bank(commodity="coffee")

    assert inserted == 2
    parameters = _assert_bounded_call(connection, "kokonut_security.store_world_bank_market_data")
    rows = json.loads(parameters[0])
    assert rows == [
        {
            "commodity_code": "COFFEE",
            "commodity_name": "Coffee",
            "price_date": "2025-01-01",
            "price_per_unit": 7.89,
        },
        {
            "commodity_code": "COFFEE",
            "commodity_name": "Coffee",
            "price_date": "2025-02-01",
            "price_per_unit": 7.89,
        },
    ]
    assert all(
        set(record) == {"commodity_code", "commodity_name", "price_date", "price_per_unit"}
        for record in rows
    )
    assert parameters[1] == worker.WORLD_BANK_FALLBACK_URL
    assert len(parameters[2]) == 64
    assert 0 <= parameters[3] <= 600_000
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_world_bank_bounded_function_failure_rolls_back_atomic_batch(monkeypatch):
    connection = _Connection(execute_error=RuntimeError("bounded write or audit failed"))
    _enable_worker(monkeypatch)
    _stub_world_bank(monkeypatch, [_parsed_record()])
    monkeypatch.setattr(worker, "get_worker_db", lambda key: connection)

    with pytest.raises(RuntimeError, match="bounded write or audit failed"):
        market_data.run_world_bank()

    _assert_bounded_call(connection, "kokonut_security.store_world_bank_market_data")
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed


def test_explicit_seed_uses_separate_bounded_source(monkeypatch):
    connection = _Connection(rows_affected=2)
    _enable_worker(monkeypatch)
    monkeypatch.setattr(worker, "get_worker_db", lambda key: connection)

    inserted = market_data.run_seed_data(commodity="coffee")

    assert inserted == 2
    parameters = _assert_bounded_call(
        connection, "kokonut_security.store_world_bank_seed_market_data"
    )
    records = json.loads(parameters[0])
    assert len(records) == len(market_data.COMMODITY_SEED_DATA["COFFEE"]["prices"])
    assert {record["commodity_code"] for record in records} == {"COFFEE"}
    assert {record["unit"] for record in records} == {"USD/kg"}
    assert len(parameters[1]) == 64
    assert 0 <= parameters[2] <= 600_000
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_explicit_seed_bounded_function_failure_rolls_back_batch(monkeypatch):
    connection = _Connection(execute_error=RuntimeError("seed bounded write failed"))
    _enable_worker(monkeypatch)
    monkeypatch.setattr(worker, "get_worker_db", lambda key: connection)

    with pytest.raises(RuntimeError, match="seed bounded write failed"):
        market_data.run_seed_data(commodity="coffee")

    _assert_bounded_call(connection, "kokonut_security.store_world_bank_seed_market_data")
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed
