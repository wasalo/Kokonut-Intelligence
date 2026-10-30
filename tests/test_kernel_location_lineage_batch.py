"""Focused regressions for farm/location lineage joins in the Kernel batch."""

from __future__ import annotations

from unittest.mock import patch

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


class _RecordingCursor:
    def __init__(self, connection):
        self.connection = connection
        self.statement = ""
        self.params = ()

    def execute(self, statement, params=None):
        self.statement = " ".join(statement.split())
        self.params = tuple(params or ())
        self.connection.statements.append((self.statement, self.params))

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def close(self):
        pass


class _RecordingConnection:
    def __init__(self):
        self.statements = []

    def cursor(self, **_kwargs):
        return _RecordingCursor(self)


def _queries(connection):
    return [statement.lower() for statement, _params in connection.statements]


def test_sales_events_and_crop_cycles_must_share_location():
    from services.analytics.demand import compute_demand_forecast, compute_demand_trends
    from services.revenue_multiplier.dimensions import loss_reduction, value_added

    demand = _RecordingConnection()
    compute_demand_forecast(demand, LOCATION_ID)
    compute_demand_trends(demand, LOCATION_ID)
    assert sum("from sales_event se" in sql for sql in _queries(demand)) == 2
    assert all("cc.location_id = se.location_id" in sql for sql in _queries(demand) if "from sales_event se" in sql)

    revenue = _RecordingConnection()
    loss_reduction.analyze(revenue, LOCATION_ID)
    value_added.analyze(revenue, LOCATION_ID)
    event_queries = [
        sql for sql in _queries(revenue)
        if "from loss_event le" in sql or "from sales_event s" in sql
    ]
    assert len(event_queries) == 2
    assert all(
        "cc.location_id = le.location_id" in sql
        or "cc.location_id = s.location_id" in sql
        for sql in event_queries
    )


def test_plot_analytics_require_the_plot_farm_to_match_record_location():
    from services.analytics import ecology, gap_closures, soc_prediction, tree_tracking
    from services.metrics.calculators.soil_carbon_delta import compute_soil_carbon_delta

    connection = _RecordingConnection()
    ecology.compare_soil_carbon(connection, LOCATION_ID)
    ecology.ndvi_trends(connection, LOCATION_ID)
    ecology.crop_diversity(connection, LOCATION_ID)
    ecology.soil_health(connection, LOCATION_ID)
    gap_closures.compute_soil_nutrient_input_correlation(connection, LOCATION_ID)
    gap_closures.compute_species_richness_per_ha(connection, LOCATION_ID)
    soc_prediction.extract_training_data(connection, LOCATION_ID)
    tree_tracking.compute_tree_density(connection, LOCATION_ID)
    compute_soil_carbon_delta(connection, LOCATION_ID)

    queries = _queries(connection)
    farm_joined_queries = [sql for sql in queries if "join farm f" in sql or "join farm farm_geom" in sql]
    assert len(farm_joined_queries) >= 10
    assert any("f.location_id = sc.location_id" in sql for sql in queries)
    assert any("f.location_id = rs.location_id" in sql for sql in queries)
    assert any("f.location_id = cc.location_id" in sql for sql in queries)
    assert any("f.location_id = ss.location_id" in sql for sql in queries)
    assert any("farm_geom.location_id = scm.location_id" in sql for sql in queries)
    assert any("f.location_id = t.location_id" in sql for sql in queries)
    assert any("scoped_farm.location_id = so.location_id" in sql for sql in queries)


def test_revenue_multiplier_and_crop_noi_reject_cross_location_cycles():
    from services.export.reports.core import generate_crop_noi
    from services.revenue_multiplier.dimensions import crop_mix
    from tests.test_crop_noi_report import CropNoiConnection

    revenue = _RecordingConnection()
    crop_mix.analyze(revenue, LOCATION_ID)
    cycle_query = next(sql for sql in _queries(revenue) if "from crop_cycle cc" in sql)
    snapshot_query = next(sql for sql in _queries(revenue) if "from noi_snapshot ns" in sql)
    assert "f.location_id = cc.location_id" in cycle_query
    assert "cc.location_id = ns.location_id" in snapshot_query

    report_connection = CropNoiConnection([])
    generate_crop_noi(report_connection, LOCATION_ID)
    report_query = report_connection.cursor_instance.query.lower()
    assert "cc.location_id = v.location_id" in report_query
    assert "f.location_id = cc.location_id" in report_query


def test_crisp_carbon_yield_does_not_run_its_unused_harvest_query(monkeypatch):
    from services.crisp import carbon_yield

    monkeypatch.setattr(
        carbon_yield, "_query_tree_summary",
        lambda *_args: {"tree_count": 0, "total_biomass_kg": 0, "total_co2e_tonnes": 0},
    )
    monkeypatch.setattr(carbon_yield, "_query_soil_carbon", lambda *_args: {})
    monkeypatch.setattr(carbon_yield, "_query_ndvi_latest", lambda *_args: None)
    monkeypatch.setattr(carbon_yield, "_query_carbon_benchmark", lambda *_args: {})

    score = carbon_yield.compute_carbon_yield_risk(object(), LOCATION_ID)

    assert score.dimension_key == "carbon_yield"
    assert not hasattr(carbon_yield, "_query_harvest_summary")


def test_bed_area_projection_groups_cycles_once_per_location_plot(monkeypatch):
    from services.forecast import yield_forecast

    rows = [
        (
            "plot-1", "Syntropic beds", 10, 2.0,
            ["cycle-1", "cycle-2"], ["Cassava", "Sweet Potato"],
        )
    ]

    class Cursor:
        statement = ""
        params = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            self.statement = " ".join(statement.split())
            self.params = params

        def fetchall(self):
            return rows

    class Connection:
        def __init__(self):
            self.test_cursor = Cursor()
            self.closed = False

        def cursor(self):
            return self.test_cursor

        def close(self):
            self.closed = True

    connection = Connection()
    with patch("services.ingestion.base.get_db", return_value=connection):
        result = yield_forecast.get_bed_areas_for_location(LOCATION_ID)

    assert connection.closed
    assert connection.test_cursor.params == (LOCATION_ID,)
    assert "cc.location_id = f.location_id" in connection.test_cursor.statement
    assert "group by p.id, p.name, p.bed_count, p.bed_area_sqm" in connection.test_cursor.statement.lower()
    assert result["plot_count"] == 1
    assert result["total_bed_area_sqm"] == 20.0
    assert result["plots"]["plot-1"]["cycle_ids"] == ["cycle-1", "cycle-2"]

