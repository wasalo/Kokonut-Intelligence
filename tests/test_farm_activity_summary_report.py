"""Published-only farm activity projection for generated farm summaries."""

import json
from decimal import Decimal
from unittest.mock import patch

from services.export.reports.context import compute_hash, store_snapshot
from services.export.reports.core import generate_farm_summary

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


class FarmSummaryCursor:
    def __init__(self, activity_rows, harvest_summary=None, farm_rows=None, plot_rows=None):
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
        self.farm_rows = farm_rows if farm_rows is not None else [{"id": "farm-id", "name": "Pilot"}]
        self.plot_rows = plot_rows if plot_rows is not None else []

    def execute(self, sql, params=()):
        statement = " ".join(sql.split())
        self.statements.append((statement, params))
        if "FROM location WHERE" in statement:
            self.one = {"id": LOCATION_ID, "name": "Pilot farm", "boundary": "private", "center": "private"}
        elif "FROM farm WHERE" in statement:
            self.rows = self.farm_rows
        elif "FROM plot p JOIN" in statement:
            self.rows = self.plot_rows
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
    def __init__(self, activity_rows, harvest_summary=None, farm_rows=None, plot_rows=None):
        self.cursor_instance = FarmSummaryCursor(
            activity_rows, harvest_summary, farm_rows=farm_rows, plot_rows=plot_rows
        )
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


def test_farm_summary_selects_only_the_current_schema_projection():
    connection = FarmSummaryConnection([])

    report = generate_farm_summary(connection, LOCATION_ID)

    expected = {
        "FROM location WHERE": [
            "id", "name", "slug", "description", "country", "region",
            "sub_region", "timezone", "latitude", "longitude",
            "baseline_revenue", "baseline_asset_value", "baseline_cash_flow",
            "baseline_cost", "baseline_assumptions", "baseline_source",
            "baseline_date", "status", "metadata", "created_at", "updated_at",
            "created_by", "updated_by", "project_url", "project_start_date",
            "project_end_date", "bioregion", "biome_type", "watershed",
            "sub_watershed", "schema_version", "organization_id",
            "baseline_recorded_at",
        ],
        "FROM farm WHERE": [
            "id", "location_id", "name", "slug", "description", "farm_type",
            "total_area", "area_unit",
            "ST_AsGeoJSON(boundary)::jsonb AS boundary",
            "ST_AsGeoJSON(center)::jsonb AS center", "status",
            "metadata", "created_at", "updated_at", "created_by", "updated_by",
            "property_id", "schema_version", "logo_url", "logo_file_id",
            "traditional_name", "languages", "global_standard_certifications",
            "economic_sectors", "credits_registries", "data_privacy_status",
            "data_privacy_standard", "data_privacy_criteria",
        ],
        "FROM plot p JOIN farm": [
            "p.id", "p.farm_id", "p.name", "p.slug", "p.description", "p.area",
            "p.area_unit", "ST_AsGeoJSON(p.boundary)::jsonb AS boundary",
            "ST_AsGeoJSON(p.center)::jsonb AS center", "p.soil_type",
            "p.water_source", "p.elevation_m", "p.slope_pct", "p.aspect",
            "p.status", "p.metadata", "p.created_at", "p.updated_at",
            "p.created_by", "p.updated_by", "p.schema_version", "p.bed_count",
            "p.bed_area_sqm", "f.name AS farm_name",
        ],
        "FROM crop_cycle cc JOIN crop": [
            "cc.id", "cc.plot_id", "cc.crop_id", "cc.location_id",
            "cc.cycle_name", "cc.season", "cc.planting_date",
            "cc.expected_harvest_date", "cc.actual_harvest_date",
            "cc.expected_yield", "cc.expected_yield_unit", "cc.actual_yield",
            "cc.actual_yield_unit", "cc.expected_price_per_unit",
            "cc.expected_revenue", "cc.actual_revenue", "cc.planting_density",
            "cc.planting_density_unit", "cc.area_planted", "cc.area_unit",
            "cc.status", "cc.failure_reason", "cc.metadata", "cc.schema_version",
            "cc.created_at", "cc.updated_at", "cc.created_by", "cc.updated_by",
            "c.name AS crop_name", "p.name AS plot_name",
        ],
    }
    for from_clause, expected_fields in expected.items():
        statement = next(
            sql for sql, _params in connection.cursor_instance.statements
            if from_clause.lower() in sql.lower()
        )
        projection = statement.lower().split(" from ", maxsplit=1)[0]
        assert projection.startswith("select ")
        selected_fields = [field.strip() for field in projection[7:].split(",")]
        assert selected_fields == [field.lower() for field in expected_fields]
        assert "*" not in projection

    assert "boundary" not in report["location"]
    assert "center" not in report["location"]


def test_farm_summary_projects_postgis_geometry_as_geojson_objects():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[-69.9, 18.5], [-69.8, 18.5], [-69.8, 18.6], [-69.9, 18.5]]],
    }
    point = {"type": "Point", "coordinates": [-69.85, 18.55]}
    connection = FarmSummaryConnection(
        [],
        farm_rows=[
            {
                "id": "farm-id",
                "location_id": LOCATION_ID,
                "name": "Pilot",
                "boundary": polygon,
                "center": None,
            }
        ],
        plot_rows=[
            {
                "id": "plot-id",
                "farm_id": "farm-id",
                "name": "North",
                "boundary": None,
                "center": point,
            }
        ],
    )

    report = generate_farm_summary(connection, LOCATION_ID)

    assert report["farms"][0]["boundary"] == polygon
    assert report["farms"][0]["center"] is None
    assert report["plots"][0]["boundary"] is None
    assert report["plots"][0]["center"] == point
    farm_query = next(
        sql for sql, _params in connection.cursor_instance.statements if "FROM farm WHERE" in sql
    )
    plot_query = next(
        sql for sql, _params in connection.cursor_instance.statements if "FROM plot p JOIN" in sql
    )
    assert "ST_AsGeoJSON(boundary)::jsonb AS boundary" in farm_query
    assert "ST_AsGeoJSON(center)::jsonb AS center" in farm_query
    assert "ST_AsGeoJSON(p.boundary)::jsonb AS boundary" in plot_query
    assert "ST_AsGeoJSON(p.center)::jsonb AS center" in plot_query



def test_farm_summary_applies_period_bounds_to_finance_and_verified_expenses():
    connection = FarmSummaryConnection([])

    generate_farm_summary(
        connection,
        LOCATION_ID,
        period_start="2026-10-01",
        period_end="2026-10-31",
    )

    finance_query, finance_params = next(
        (sql, params)
        for sql, params in connection.cursor_instance.statements
        if "FROM financial_transaction" in sql
    )
    assert "transaction_date >= %s::date" in finance_query
    assert "transaction_date <= %s::date" in finance_query
    assert finance_params == (LOCATION_ID, "2026-10-01", "2026-10-01", "2026-10-31", "2026-10-31")

    expense_query, expense_params = next(
        (sql, params)
        for sql, params in connection.cursor_instance.statements
        if "FROM expense_event" in sql
    )
    assert "ee.status IN ('verified', 'published')" in expense_query
    assert "ee.expense_date >= %s::date" in expense_query
    assert "ee.expense_date <= %s::date" in expense_query
    assert expense_params == (LOCATION_ID, "2026-10-01", "2026-10-01", "2026-10-31", "2026-10-31")


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
    assert "cc.location_id = he.location_id" in query


def test_farm_summary_crop_cycles_require_plot_farm_location_match():
    connection = FarmSummaryConnection([])

    generate_farm_summary(connection, LOCATION_ID)

    query = next(
        sql for sql, _params in connection.cursor_instance.statements
        if "FROM crop_cycle cc" in sql
    ).lower()
    assert "join farm f on f.id = p.farm_id" in query
    assert "f.location_id = cc.location_id" in query


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
