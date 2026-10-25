"""Bounded location-scoped source references for AI-summary generators."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.agents import ai_summary

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
SUMMARY_SOURCE_TABLES = {
    "operations": {
        "harvest_event",
        "sales_event",
        "crop_cycle",
        "sensor_reading",
    },
    "financial": {
        "sales_event",
        "expense_event",
        "noi_snapshot",
        "crop_cycle",
        "crop",
        "expense_category",
    },
    "environmental": {
        "soil_carbon_measurement",
        "species_observation",
        "remote_sensing_observation",
        "weather_observation",
    },
}
SUMMARY_SOURCE_TABLES["combined"] = set().union(*SUMMARY_SOURCE_TABLES.values())


def _complete_summary(summary_type):
    source_tables = sorted(SUMMARY_SOURCE_TABLES[summary_type])
    return {
        "summary_type": summary_type,
        "source_tables": source_tables,
        "source_references": {
            table: {"record_ids": [], "row_count": 0, "truncated": False}
            for table in source_tables
        },
    }


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


@pytest.mark.parametrize("summary_type", SUMMARY_SOURCE_TABLES)
def test_deterministic_summary_source_coverage_accepts_complete_registered_manifests(
    summary_type,
):
    summary = _complete_summary(summary_type)

    ai_summary.validate_source_reference_coverage(summary)


@pytest.mark.parametrize("summary_type", SUMMARY_SOURCE_TABLES)
@pytest.mark.parametrize("omission", ["source_table", "reference"])
def test_deterministic_summary_source_coverage_rejects_missing_provenance(
    summary_type, omission
):
    summary = _complete_summary(summary_type)
    missing = summary["source_tables"][0]
    if omission == "source_table":
        summary["source_tables"].remove(missing)
    else:
        del summary["source_references"][missing]

    with pytest.raises(ValueError, match="source tables|source references"):
        ai_summary.validate_source_reference_coverage(summary)


@pytest.mark.parametrize("summary_type", SUMMARY_SOURCE_TABLES)
@pytest.mark.parametrize("addition", ["source_table", "reference"])
def test_deterministic_summary_source_coverage_rejects_extra_provenance(
    summary_type, addition
):
    summary = _complete_summary(summary_type)
    extra = "unexpected_source"
    if addition == "source_table":
        summary["source_tables"].append(extra)
    else:
        summary["source_references"][extra] = {
            "record_ids": [],
            "row_count": 0,
            "truncated": False,
        }

    with pytest.raises(ValueError, match="source tables|source references"):
        ai_summary.validate_source_reference_coverage(summary)


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
    assert "JOIN expense_category AS ec ON ee.category = ec.name" in predicate
    assert "ORDER BY SUM(ee.amount) DESC, ee.category LIMIT 5" in predicate
    assert parameters == (LOCATION_ID,)
    assert ordering == "expense_date, id"
    assert latest_only is False
    sales_predicate, _, _, _ = captured["sales_event"]
    assert "cycle.location_id = sales_event.location_id" in sales_predicate
    cycle_predicate, cycle_parameters, _, _ = captured["crop_cycle"]
    assert "se.crop_cycle_id IS NOT NULL" in cycle_predicate
    assert cycle_parameters == (LOCATION_ID,)
    revenue_query, revenue_parameters = cursor.execute.call_args_list[0][0]
    assert "cc.location_id = se.location_id" in revenue_query
    assert revenue_parameters == (LOCATION_ID,)


@pytest.mark.parametrize(
    "summary_function",
    [
        ai_summary._check_registry_backed,
        ai_summary.generate_operations_summary,
        ai_summary.generate_financial_summary,
        ai_summary.generate_environmental_summary,
    ],
    ids=["registry-check", "operations", "financial", "environmental"],
)
@pytest.mark.parametrize("failure_point", ["execute", "fetch"])
def test_summary_queries_close_cursors_when_database_operations_fail(
    summary_function, failure_point
):
    class Cursor:
        closed = False

        def execute(self, _query, _parameters):
            if failure_point == "execute":
                raise RuntimeError("synthetic query failure")

        def fetchone(self):
            raise RuntimeError("synthetic fetch failure")

        def fetchall(self):
            raise RuntimeError("synthetic fetch failure")

        def close(self):
            self.closed = True

    cursor = Cursor()

    class Connection:
        def cursor(self, **_kwargs):
            return cursor

    with pytest.raises(RuntimeError, match="synthetic (query|fetch) failure"):
        summary_function(Connection(), LOCATION_ID)

    assert cursor.closed is True


def test_global_crop_reference_is_limited_to_location_verified_sales():
    cursor = _Cursor([
        ("f0000000-0000-4000-8000-000000000001", 2),
        ("f0000000-0000-4000-8000-000000000002", 2),
    ])
    connection = Mock()
    connection.cursor.return_value = cursor

    result = ai_summary._collect_source_references(
        connection,
        LOCATION_ID,
        {"crop": ("TRUE", (), "id", False)},
    )

    assert "JOIN crop_cycle AS cycle ON cycle.crop_id = crop.id" in cursor.query
    assert "JOIN sales_event AS sale ON sale.crop_cycle_id = cycle.id" in cursor.query
    assert "sale.status IN ('verified', 'published')" in cursor.query
    assert "cycle.location_id = %s" in cursor.query
    assert "cycle.location_id = sale.location_id" in cursor.query
    assert cursor.parameters == (LOCATION_ID, LOCATION_ID, 50)
    assert result["crop"]["row_count"] == 2


def test_global_expense_category_reference_matches_the_displayed_top_five():
    cursor = _Cursor([("f0000000-0000-4000-8000-000000000003", 5)])
    connection = Mock()
    connection.cursor.return_value = cursor

    result = ai_summary._collect_source_references(
        connection,
        LOCATION_ID,
        {"expense_category": ("TRUE", (), "id", False)},
    )

    assert "JOIN expense_event AS expense" in cursor.query
    assert "expense.location_id = %s" in cursor.query
    assert "ORDER BY SUM(expense.amount) DESC, category.name LIMIT 5" in cursor.query
    assert cursor.parameters == (LOCATION_ID, 50)
    assert result["expense_category"]["row_count"] == 5
