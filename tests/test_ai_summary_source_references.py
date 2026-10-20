"""Bounded location-scoped source references for AI-summary generators."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.agents import ai_summary

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, parameters):
        self.query = " ".join(query.split())
        self.parameters = parameters

    def fetchall(self):
        return self.rows


def test_source_reference_query_is_location_scoped_bounded_and_reports_exact_count():
    rows = [(f"record-{index}", 73) for index in range(50)]
    cursor = _Cursor(rows)
    connection = Mock()
    connection.cursor.return_value = cursor

    result = ai_summary._collect_source_references(
        connection,
        LOCATION_ID,
        {
            "harvest_event": (
                "status IN ('verified', 'published')",
                (),
                "harvest_date, id",
                False,
            )
        },
    )

    assert "WHERE location_id = %s" in cursor.query
    assert "LIMIT %s" in cursor.query
    assert cursor.parameters == (LOCATION_ID, 50)
    assert result["harvest_event"] == {
        "record_ids": [f"record-{index}" for index in range(50)],
        "row_count": 73,
        "truncated": True,
    }


def test_latest_source_reference_is_exactly_one_deterministic_record():
    cursor = _Cursor([("latest-record", 1)])
    connection = Mock()
    connection.cursor.return_value = cursor

    result = ai_summary._collect_source_references(
        connection,
        LOCATION_ID,
        {
            "soil_carbon_measurement": (
                "TRUE",
                (),
                "measurement_date DESC, id DESC",
                True,
            )
        },
    )

    assert "ORDER BY measurement_date DESC, id DESC LIMIT 1" in cursor.query
    assert "COUNT(*) OVER ()" in cursor.query
    assert cursor.parameters == (LOCATION_ID,)
    assert result["soil_carbon_measurement"] == {
        "record_ids": ["latest-record"],
        "row_count": 1,
        "truncated": False,
    }


def test_source_table_name_is_allowlisted_before_database_query():
    connection = Mock()
    with pytest.raises(ValueError, match="Unsupported AI-summary source table"):
        ai_summary._collect_source_references(
            connection,
            LOCATION_ID,
            {"operator_identity": ("TRUE", (), "id", False)},
        )

    connection.cursor.assert_not_called()


def test_operations_manifest_matches_the_top_three_sensor_types(monkeypatch):
    cursor = Mock()
    cursor.fetchone.side_effect = [
        {"count": 0, "total_kg": 0},
        {"count": 0, "total_usd": 0},
        {"count": 0},
    ]
    cursor.fetchall.return_value = []
    connection = Mock()
    connection.cursor.return_value = cursor
    captured = {}

    def collect(_connection, _location_id, scopes):
        captured.update(scopes)
        return {}

    monkeypatch.setattr(ai_summary, "_collect_source_references", collect)
    ai_summary.generate_operations_summary(connection, LOCATION_ID)

    predicate, parameters, ordering, latest_only = captured["sensor_reading"]
    assert "top_sensor_types" in predicate
    assert "GROUP BY sensor_type ORDER BY COUNT(*) DESC, sensor_type NULLS LAST LIMIT 3" in predicate
    assert "IS NOT DISTINCT FROM sensor_reading.sensor_type" in predicate
    assert parameters == (LOCATION_ID,)
    assert ordering == "reading_date, id"
    assert latest_only is False


def test_financial_manifest_matches_the_top_five_configured_expense_categories(monkeypatch):
    cursor = Mock()
    cursor.fetchone.return_value = {"total_noi": 0, "avg_margin": 0}
    cursor.fetchall.return_value = []
    connection = Mock()
    connection.cursor.return_value = cursor
    captured = {}

    def collect(_connection, _location_id, scopes):
        captured.update(scopes)
        return {}

    monkeypatch.setattr(ai_summary, "_collect_source_references", collect)
    ai_summary.generate_financial_summary(connection, LOCATION_ID)

    predicate, parameters, ordering, latest_only = captured["expense_event"]
    assert "category IN" in predicate
    assert "JOIN public.expense_category AS ec ON ee.category = ec.name" in predicate
    assert "ORDER BY SUM(ee.amount) DESC, ee.category LIMIT 5" in predicate
    assert parameters == (LOCATION_ID,)
    assert ordering == "expense_date, id"
    assert latest_only is False
