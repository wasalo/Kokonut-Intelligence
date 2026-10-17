"""Mocked recovery and transaction checks for market-data ingestion."""

from __future__ import annotations

import pytest

from services.ingestion import market_data


class _Cursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchall(self):
        return []


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
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


def test_world_bank_download_failure_does_not_fallback_to_seed(monkeypatch):
    monkeypatch.setattr(market_data, "get_db", lambda: pytest.fail("DB opened"))
    monkeypatch.setattr(
        market_data,
        "download_pink_sheet",
        lambda: (_ for _ in ()).throw(OSError("provider unavailable")),
    )
    monkeypatch.setattr(
        market_data, "run_seed_data", lambda **_kwargs: pytest.fail("seed fallback")
    )

    with pytest.raises(RuntimeError, match="use explicit --source seed"):
        market_data.run_world_bank()


@pytest.mark.parametrize("records", [[], [_parsed_record("UNSUPPORTED")]])
def test_world_bank_empty_or_unmatched_response_fails_before_database(monkeypatch, records):
    monkeypatch.setattr(market_data, "download_pink_sheet", lambda: b"fixture")
    monkeypatch.setattr(market_data, "parse_pink_sheet", lambda *_args, **_kwargs: records)
    monkeypatch.setattr(market_data, "get_db", lambda: pytest.fail("DB opened"))

    with pytest.raises(RuntimeError, match="no usable price records" if not records else "no records for COFFEE"):
        market_data.run_world_bank(commodity="coffee")


def test_world_bank_persists_audited_batch_atomically_and_keeps_live_source(monkeypatch):
    connection = _Connection()
    inserted_records = []
    audit = []
    monkeypatch.setattr(market_data, "download_pink_sheet", lambda: b"fixture")
    monkeypatch.setattr(
        market_data,
        "parse_pink_sheet",
        lambda *_args, **_kwargs: [_parsed_record(), _parsed_record(date="2025-02-01")],
    )
    monkeypatch.setattr(market_data, "get_db", lambda: connection)

    def insert_price(_db, record):
        inserted_records.append(record)
        return f"id-{len(inserted_records)}", len(inserted_records) == 1

    monkeypatch.setattr(market_data, "insert_price", insert_price)
    monkeypatch.setattr(market_data, "log_ingestion", lambda **kwargs: audit.append(kwargs))

    market_data.run_world_bank(commodity="coffee")

    assert len(inserted_records) == 2
    assert {record["source"] for record in inserted_records} == {"world_bank_pink_sheet"}
    assert {record["metadata"]["source_type"] for record in inserted_records} == {"live_download"}
    assert len(audit) == 1
    assert audit[0]["source_system"] == "world_bank"
    assert audit[0]["rows_affected"] == 1
    assert audit[0]["db"] is connection
    assert audit[0]["payload_hash"]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_world_bank_insert_failure_rolls_back_without_success_audit(monkeypatch):
    connection = _Connection()
    insert_count = 0
    monkeypatch.setattr(market_data, "download_pink_sheet", lambda: b"fixture")
    monkeypatch.setattr(
        market_data,
        "parse_pink_sheet",
        lambda *_args, **_kwargs: [_parsed_record(), _parsed_record(date="2025-02-01")],
    )
    monkeypatch.setattr(market_data, "get_db", lambda: connection)

    def insert_price(_db, _record):
        nonlocal insert_count
        insert_count += 1
        if insert_count == 2:
            raise RuntimeError("synthetic insert failure")
        return "id-1", True

    monkeypatch.setattr(market_data, "insert_price", insert_price)
    monkeypatch.setattr(
        market_data,
        "log_ingestion",
        lambda **_kwargs: pytest.fail("failed batch must not receive success audit"),
    )

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        market_data.run_world_bank()

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed


def test_world_bank_audit_failure_rolls_back_insert_batch(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(market_data, "download_pink_sheet", lambda: b"fixture")
    monkeypatch.setattr(market_data, "parse_pink_sheet", lambda *_args, **_kwargs: [_parsed_record()])
    monkeypatch.setattr(market_data, "get_db", lambda: connection)
    monkeypatch.setattr(market_data, "insert_price", lambda *_args: ("id-1", True))
    monkeypatch.setattr(
        market_data,
        "log_ingestion",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        market_data.run_world_bank()

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed


def test_explicit_seed_uses_separate_source_and_audits_insert_count(monkeypatch):
    connection = _Connection()
    inserted_records = []
    audit = []
    monkeypatch.setattr(market_data, "get_db", lambda: connection)

    def insert_price(_db, record):
        inserted_records.append(record)
        return f"id-{len(inserted_records)}", len(inserted_records) <= 2

    monkeypatch.setattr(market_data, "insert_price", insert_price)
    monkeypatch.setattr(market_data, "log_ingestion", lambda **kwargs: audit.append(kwargs))

    market_data.run_seed_data(commodity="coffee")

    assert inserted_records
    assert {record["source"] for record in inserted_records} == {"world_bank_pink_sheet_seed"}
    assert {record["metadata"]["source_type"] for record in inserted_records} == {"seed_data"}
    assert audit[0]["source_system"] == "seed"
    assert audit[0]["rows_affected"] == 2
    assert audit[0]["db"] is connection
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_explicit_seed_failure_rolls_back_entire_batch(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(market_data, "get_db", lambda: connection)
    monkeypatch.setattr(
        market_data,
        "insert_price",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("seed insert failed")),
    )

    with pytest.raises(RuntimeError, match="seed insert failed"):
        market_data.run_seed_data(commodity="coffee")

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed

