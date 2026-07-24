"""Focused reliability tests for export pagination and filter handling."""

from __future__ import annotations

import pytest

from services.export.exporter import Exporter


def test_postgres_filters_fail_closed_for_empty_in_and_unknown_operator() -> None:
    exporter = Exporter()

    with pytest.raises(ValueError, match="non-empty"):
        exporter._build_where({"status": {"$in": []}})
    with pytest.raises(ValueError, match="Unsupported"):
        exporter._build_where({"status": {"$contains": "draft"}})


def test_clickhouse_filters_match_governed_operator_contract() -> None:
    exporter = Exporter()

    where, params = exporter._build_clickhouse_where(
        {"status": {"$in": ["verified", "published"]}, "created_at": {"$gte": "2026-01-01"}}
    )

    assert "status IN" in where
    assert "created_at >=" in where
    assert len(params) == 3


def test_clickhouse_query_has_deterministic_order_and_no_silent_cap(monkeypatch) -> None:
    class Result:
        column_names = ["id", "timestamp"]
        result_rows = []

    class Client:
        def __init__(self):
            self.query_text = None

        def query(self, query, parameters):
            self.query_text = query
            return Result()

    client = Client()
    monkeypatch.setattr("services.export.exporter.get_ch", lambda: client)
    list(Exporter(source="clickhouse")._query_clickhouse("sensor_reading", None)[0])

    assert "ORDER BY timestamp DESC, id DESC" in client.query_text
    assert "100000" not in client.query_text
