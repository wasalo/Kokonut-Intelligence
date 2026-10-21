"""Published-only farm activity projection for generated farm summaries."""

import json
from decimal import Decimal
from unittest.mock import patch

from services.export.reports.context import compute_hash, store_snapshot
from services.export.reports.core import generate_farm_summary

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


class FarmSummaryCursor:
    def __init__(self, activity_rows, harvest_summary=None):
        self.activity_rows = activity_rows
        self.harvest_summary = harvest_summary or {
            "total_harvests": 0,
            "total_quantity": 0,
            "avg_harvest_size": 0,
            "cycles_with_harvest": 0,
            "quantity_unit": None,
            "total_quantity_by_unit": {},
        }
        self.rows = []
        self.one = None
        self.statements = []

    def execute(self, sql, params=()):
        statement = " ".join(sql.split())
        self.statements.append((statement, params))
        if "FROM location WHERE" in statement:
            self.one = {"id": LOCATION_ID, "name": "Pilot farm", "boundary": "private", "center": "private"}
        elif "FROM farm WHERE" in statement:
            self.rows = [{"id": "farm-id", "name": "Pilot"}]
        elif "FROM plot p JOIN" in statement:
            self.rows = []
        elif "FROM crop_cycle cc" in statement:
            self.rows = []
        elif "FROM harvest_event" in statement:
            self.one = self.harvest_summary
        elif "FROM financial_transaction" in statement:
            self.one = {"total_revenue": 0, "total_expenses": 0, "net_income": 0}
        elif "FROM expense_event" in statement:
            self.rows = []
        elif "FROM attestation_record" in statement:
            self.one = {"total_records": 0, "attested": 0, "draft": 0}
        elif "FROM farm_activity" in statement:
            self.rows = self.activity_rows
        else:
            raise AssertionError(f"Unexpected farm summary query: {statement}")

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows

    def close(self):
        return None


class FarmSummaryConnection:
    def __init__(self, activity_rows, harvest_summary=None):
        self.cursor_instance = FarmSummaryCursor(activity_rows, harvest_summary)
        self.snapshot_cursor = SnapshotCursor()
        self.cursor_calls = 0
        self.committed = False

    def cursor(self, **_kwargs):
        self.cursor_calls += 1
        if self.cursor_calls == 1:
            return self.cursor_instance
        return self.snapshot_cursor

    def commit(self):
        self.committed = True


class SnapshotCursor:
    def __init__(self):
        self.sql = ""
        self.params = None

    def execute(self, sql, params):
        self.sql = " ".join(sql.split())
        self.params = params

    def fetchone(self):
        return ("snapshot-id",)

    def close(self):
        return None


def test_farm_summary_aggregates_only_published_activities_and_excludes_private_fields():
    connection = FarmSummaryConnection(
        [
            {
                "activity_type": "weeding",
                "activity_count": 2,
                "reported_labor_hours": Decimal("3.25"),
            },
            {
                "activity_type": "planting",
                "activity_count": 1,
                "reported_labor_hours": Decimal("2.00"),
            },
        ]
    )

    report = generate_farm_summary(
        connection,
        LOCATION_ID,
        period_start="2026-10-01",
        period_end="2026-10-31",
    )

    summary = report["farm_activity_summary"]
    assert summary == {
        "published_activity_count": 3,
        "reported_labor_hours": 5.25,
        "reported_labor_hours_unit": "hours",
        "by_activity_type": [
            {
                "activity_type": "weeding",
                "activity_count": 2,
                "reported_labor_hours": 3.25,
                "reported_labor_hours_unit": "hours",
            },
            {
                "activity_type": "planting",
                "activity_count": 1,
                "reported_labor_hours": 2.0,
                "reported_labor_hours_unit": "hours",
            },
        ],
    }

    activity_query, params = next(
        (sql, params)
        for sql, params in connection.cursor_instance.statements
        if "FROM farm_activity" in sql
    )
    normalized = activity_query.lower()
    assert "status = 'published'" in normalized
    assert "activity_date >= %s::date" in normalized
    assert "activity_date <= %s::date" in normalized
    assert params == (LOCATION_ID, "2026-10-01", "2026-10-01", "2026-10-31", "2026-10-31")
    selected_columns = normalized.split("from farm_activity", maxsplit=1)[0]
    for private_field in ("description", "notes", "source_raw", "device_id", "participant"):
        assert private_field not in selected_columns
    assert "farm_activity_source_eligible_for_use" in normalized
    assert "location" in report
    assert "boundary" not in report["location"]
    assert "center" not in report["location"]


def test_farm_summary_returns_zeroes_when_no_activity_is_published():
    report = generate_farm_summary(FarmSummaryConnection([]), LOCATION_ID)

    assert report["farm_activity_summary"] == {
        "published_activity_count": 0,
        "reported_labor_hours": 0.0,
        "reported_labor_hours_unit": "hours",
        "by_activity_type": [],
    }


def test_farm_harvest_summary_filters_governed_rows_and_keeps_mixed_units_separate():
    connection = FarmSummaryConnection(
        [],
        {
            "total_harvests": 3,
            "total_quantity": None,
            "avg_harvest_size": None,
            "cycles_with_harvest": 2,
            "quantity_unit": None,
            "total_quantity_by_unit": {"kg": 120, "tonnes": 1.5},
        },
    )

    report = generate_farm_summary(connection, LOCATION_ID)

    harvest = report["harvest_summary"]
    assert harvest["total_quantity"] is None
    assert harvest["avg_harvest_size"] is None
    assert harvest["quantity_unit"] is None
    assert harvest["total_quantity_by_unit"] == {"kg": 120, "tonnes": 1.5}
    query = next(
        sql for sql, _params in connection.cursor_instance.statements if "FROM harvest_event" in sql
    )
    assert "status IN ('verified', 'published')" in query
    assert "COUNT(DISTINCT unit) <= 1" in query
    assert "jsonb_object_agg(unit, total_quantity)" in query


def test_farm_activity_summary_is_stored_as_an_unfrozen_hashed_draft():
    connection = FarmSummaryConnection(
        [
            {
                "activity_type": "weeding",
                "activity_count": 1,
                "reported_labor_hours": Decimal("1.50"),
            }
        ]
    )
    report = generate_farm_summary(connection, LOCATION_ID)

    with patch(
        "services.export.reports.context.attach_public_interest_context",
        side_effect=lambda _conn, data, _location_id: data,
    ):
        snapshot_id = store_snapshot(connection, report, LOCATION_ID)

    sql = connection.snapshot_cursor.sql
    assert "'draft', FALSE, NULL" in sql
    assert "'published', TRUE" not in sql
    stored_report = json.loads(connection.snapshot_cursor.params[5])
    assert stored_report["farm_activity_summary"] == report["farm_activity_summary"]
    assert connection.snapshot_cursor.params[6] == compute_hash(stored_report)
    assert snapshot_id == "snapshot-id"
    assert connection.committed is True
