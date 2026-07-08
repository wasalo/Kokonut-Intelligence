"""Gap closure tests: Q1 yield delta, Q3 soil N correlation, Q4 retention in report, Q5 rainfall vs irrigation, Q11 species/ha."""

from pathlib import Path

from services.analytics.gap_closures import (
    compute_yield_delta,
    compute_soil_nutrient_input_correlation,
    compute_species_richness_per_ha,
    compute_rainfall_vs_irrigation,
)
from services.export.report_generator import REPORT_GENERATORS

SCHEMA = Path("schemas/postgres/051_gap_closures.sql")
SEED = Path("schemas/seeds/051_gap_closures.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_adds_irrigation_columns() -> None:
    text = SCHEMA.read_text()
    assert "irrigation_mm_used" in text
    assert "rainfall_mm_during_period" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_public_rainfall_vs_irrigation",
        "v_public_species_richness_per_ha",
        "v_public_location_species_richness",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text


def test_schema_has_gap_closure_version() -> None:
    text = SCHEMA.read_text()
    assert "gap-closures-v1" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metrics() -> None:
    text = SEED.read_text()
    for metric in [
        "yield_delta_kg",
        "species_richness_per_ha",
        "rainfall_irrigation_delta_mm",
    ]:
        assert metric in text


def test_seed_updates_irrigation_data() -> None:
    text = SEED.read_text()
    assert "irrigation_mm_used = 50.00" in text
    assert "rainfall_mm_during_period = 120.00" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single
        self._calls = 0

    def execute(self, query, params=None):
        self._calls += 1

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


def test_yield_delta_analytics() -> None:
    rows = [
        ("c1", "Lettuce", "Lettuce Cycle 1", 100.0, "tonnes", 90.0, "2025-12-20", -10.0, -10.0, "completed"),
        ("c2", "Coconut", "Coconut Cycle 1", 50.0, "tonnes", 55.0, "2025-12-15", 5.0, 10.0, "harvested"),
    ]
    result = compute_yield_delta(_MockConn(rows), "test-location")
    assert result["total_completed_cycles"] == 2
    assert result["avg_yield_delta"] == -2.5
    assert result["underpredicted_count"] == 1
    assert result["overpredicted_count"] == 1


def test_soil_nutrient_input_correlation_analytics() -> None:
    soil_rows = [
        ("p1", "Plot A", 30.0, 38.0, 8.0, "2025-10-01", "2026-03-01"),
    ]
    input_rows = [
        ("p1", "Plot A", "biochar", 120.0, 1, "2025-10-05", "2025-10-05"),
        ("p1", "Plot A", "compost", 80.0, 1, "2025-10-10", "2025-10-10"),
    ]

    class _Conn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            original_execute = c.execute
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = soil_rows
                elif self._calls == 2:
                    c._rows = input_rows
            c.execute = execute
            return c

    conn = _Conn()
    result = compute_soil_nutrient_input_correlation(conn, "test-location")
    assert result["plots_with_data"] == 1
    corr = result["correlations"][0]
    assert corr["nitrogen_delta_ppm"] == 8.0
    assert corr["total_biochar_kg"] == 120.0
    assert corr["total_compost_kg"] == 80.0
    assert corr["total_organic_input_kg"] == 200.0


def test_species_richness_per_ha_analytics() -> None:
    plot_rows = [
        ("p1", "Plot A", 0.5, 15, 20, "2026-03-01"),
        ("p2", "Plot B", 1.0, 25, 30, "2026-03-01"),
    ]
    loc_row = (40, 50, 1.5, "2026-03-01")

    class _Conn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = plot_rows
                elif self._calls == 2:
                    c._single = loc_row
            c.execute = execute
            return c

    conn = _Conn()
    result = compute_species_richness_per_ha(conn, "test-location")
    assert result["location_total_species"] == 40
    assert result["location_total_area_ha"] == 1.5
    assert result["location_species_per_hectare"] == round(40 / 1.5, 2)
    assert len(result["plots"]) == 2
    assert result["plots"][0]["species_per_hectare"] == 30.0


def test_rainfall_vs_irrigation_analytics() -> None:
    rows = [
        ("r1", "2025-10-01", "2025-12-31", 50.0, 120.0, 70.0, 2.4),
        ("r2", "2026-01-01", "2026-03-31", 40.0, 85.0, 45.0, 2.125),
    ]
    result = compute_rainfall_vs_irrigation(_MockConn(rows), "test-location")
    assert result["total_periods"] == 2
    assert result["total_rainfall_mm"] == 205.0
    assert result["total_irrigation_mm"] == 90.0
    assert result["net_rainfall_minus_irrigation_mm"] == 115.0


# ---------------------------------------------------------------------------
# Report tests
# ---------------------------------------------------------------------------

def test_ecological_modeling_report_includes_soil_inputs() -> None:
    """Verify the ecological_modeling report now includes soil input retention data."""
    import inspect
    from services.export.report_generator import generate_ecological_modeling
    source = inspect.getsource(generate_ecological_modeling)
    assert "v_public_soil_input_retention" in source
    assert "soil_inputs" in source
    assert "avg_residual_pct" in source


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_adds_irrigation_columns()
    test_schema_defines_views()
    test_schema_has_gap_closure_version()
    test_seed_has_metrics()
    test_seed_updates_irrigation_data()
    test_yield_delta_analytics()
    test_soil_nutrient_input_correlation_analytics()
    test_species_richness_per_ha_analytics()
    test_rainfall_vs_irrigation_analytics()
    test_ecological_modeling_report_includes_soil_inputs()
    print("All tests passed.")
