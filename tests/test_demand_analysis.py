"""Demand analysis tests: schema, seeds, analytics."""

from pathlib import Path

from services.analytics.demand import (
    compute_buyer_segmentation,
    compute_demand_forecast,
    compute_demand_trends,
    compute_market_sizing,
    compute_production_market_match,
)

SCHEMA = Path("schemas/postgres/069_demand_analysis.sql")
SEED = Path("schemas/seeds/069_demand_analysis.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in ["buyer_demand_signal", "demand_forecast", "market_size_estimate",
                   "demand_trend", "production_market_match", "buyer_segment"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in ["v_public_demand_forecast", "v_public_buyer_demand_signals",
                   "v_public_market_size_estimates", "v_public_demand_trends",
                   "v_public_buyer_segments", "v_public_production_market_match"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (buyer_type IN" in text
    assert "CHECK (signal_type IN" in text
    assert "CHECK (commitment_level IN" in text
    assert "CHECK (market_scope IN" in text
    assert "CHECK (analysis_type IN" in text
    assert "CHECK (segment_type IN" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metrics() -> None:
    text = SEED.read_text()
    assert "demand_coverage_pct" in text
    assert "buyer_pipeline_value" in text
    assert "market_penetration_pct" in text
    assert "demand_supply_gap_tonnes" in text
    assert "buyer_retention_rate" in text
    assert "demand_seasonality_index" in text
    assert "buyer_diversification_score" in text


def test_seed_has_buyer_signals() -> None:
    text = SEED.read_text()
    assert "Adelphi Fresh Buyers" in text
    assert "DirectFarm Dominican Republic" in text
    assert "Santo Domingo Market Cooperative" in text
    assert "Caribbean Greens Restaurant Group" in text
    assert "recurring_order" in text
    assert "firm" in text


def test_seed_has_market_size() -> None:
    text = SEED.read_text()
    assert "Lettuce Market" in text
    assert "Leafy Greens Market" in text
    assert "tam_value" in text
    assert "sam_value" in text
    assert "som_value" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def execute(self, query, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._single

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows, self._single)


def test_demand_forecast_no_data() -> None:
    result = compute_demand_forecast(_MockConn(rows=[]), "test-location")
    assert result["total_crops_forecasted"] == 0
    assert result["forecasts"] == []


def test_market_sizing_empty() -> None:
    result = compute_market_sizing(_MockConn(rows=[]), "test-location")
    assert result["total_estimates"] == 0
    assert result["total_tam_usd"] == 0


def test_demand_trends_no_data() -> None:
    result = compute_demand_trends(_MockConn(rows=[]), "test-location")
    assert result["total_crops_analyzed"] == 0


def test_buyer_segmentation_empty() -> None:
    result = compute_buyer_segmentation(_MockConn(rows=[]), "test-location")
    assert result["total_buyers"] == 0


def test_production_market_match_empty() -> None:
    result = compute_production_market_match(_MockConn(rows=[]), "test-location")
    assert result["total_crops_analyzed"] == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_check_constraints()
    test_schema_has_governed_columns()
    test_seed_has_metrics()
    test_seed_has_buyer_signals()
    test_seed_has_market_size()
    test_demand_forecast_no_data()
    test_market_sizing_empty()
    test_demand_trends_no_data()
    test_buyer_segmentation_empty()
    test_production_market_match_empty()
    print("All tests passed.")
