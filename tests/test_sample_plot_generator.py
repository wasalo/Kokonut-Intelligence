"""Sample plot generation tests: schema, seeds, analytics."""

import math
from pathlib import Path

from services.analytics.sample_plot_generator import (
    compute_optimal_plot_count,
    get_plot_summary,
)

SCHEMA = Path("schemas/postgres/071_sample_plot_design.sql")
SEED = Path("schemas/seeds/071_sample_plot_design.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS sample_plot_design" in text
    assert "CREATE TABLE IF NOT EXISTS sample_plot" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_public_sample_plot_designs" in text
    assert "CREATE OR REPLACE VIEW v_public_sample_plots" in text
    assert "CREATE OR REPLACE VIEW v_sample_plot_measurement_status" in text


def test_schema_has_gis_trigger() -> None:
    text = SCHEMA.read_text()
    assert "fn_sample_plot_compute_geometry" in text
    assert "ST_SetSRID(ST_MakePoint" in text
    assert "trg_sample_plot_compute_geometry" in text


def test_schema_has_spatial_index() -> None:
    text = SCHEMA.read_text()
    assert "idx_sample_plot_geometry" in text
    assert "USING GIST(center_geometry)" in text


def test_schema_has_unique_constraint() -> None:
    text = SCHEMA.read_text()
    assert "idx_sample_plot_number_per_design" in text
    assert "UNIQUE" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (sampling_method IN" in text
    assert "CHECK (target_plot_count > 0)" in text
    assert "CHECK (status IN ('draft', 'approved', 'superseded'))" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_design() -> None:
    text = SEED.read_text()
    assert "sample_plot_design" in text
    assert "stratified_random" in text
    assert "Agroforestry Corridor Stratified Random Design" in text


def test_seed_has_plots() -> None:
    text = SEED.read_text()
    assert "SP-AC-001" in text
    assert "SP-AC-005" in text
    assert "18.52118" in text
    assert "-69.98718" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

def test_optimal_plot_count_small_zone() -> None:
    count = compute_optimal_plot_count(0.5, 95.0, 30.0)
    assert count >= 1
    assert count <= 50


def test_optimal_plot_count_large_zone() -> None:
    count = compute_optimal_plot_count(10.0, 95.0, 30.0)
    assert count >= 1


def test_optimal_plot_count_high_confidence() -> None:
    count_95 = compute_optimal_plot_count(2.0, 95.0, 30.0)
    count_99 = compute_optimal_plot_count(2.0, 99.0, 30.0)
    assert count_99 >= count_95


def test_optimal_plot_count_low_variance() -> None:
    count_high_var = compute_optimal_plot_count(2.0, 95.0, 30.0)
    count_low_var = compute_optimal_plot_count(2.0, 95.0, 10.0)
    assert count_low_var >= count_high_var


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


def test_get_plot_summary() -> None:
    design_row = (
        "Test Design", "stratified_random", 5, 5, 0.45, 95.0,
        "Test Zone", "agroforestry",
    )
    plot_rows = [
        (1, "SP-001", 18.521, -69.987, 100.0, 5.64, "coconut"),
        (2, "SP-002", 18.522, -69.988, 100.0, 5.64, "passion_fruit"),
    ]

    class _SummaryConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = design_row
                elif self._calls == 2:
                    c._rows = plot_rows
            c.execute = execute
            return c

    result = get_plot_summary(_SummaryConn(), "test-design-id")
    assert result["design_name"] == "Test Design"
    assert result["generated_plot_count"] == 5
    assert len(result["plots"]) == 2
    assert result["plots"][0]["plot_label"] == "SP-001"


def test_get_plot_summary_not_found() -> None:
    class _EmptyConn:
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            c._single = None
            def execute(query, params=None):
                pass
            c.execute = execute
            return c

    result = get_plot_summary(_EmptyConn(), "nonexistent")
    assert "error" in result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_gis_trigger()
    test_schema_has_spatial_index()
    test_schema_has_unique_constraint()
    test_schema_has_check_constraints()
    test_schema_has_governed_columns()
    test_seed_has_design()
    test_seed_has_plots()
    test_optimal_plot_count_small_zone()
    test_optimal_plot_count_large_zone()
    test_optimal_plot_count_high_confidence()
    test_optimal_plot_count_low_variance()
    test_get_plot_summary()
    test_get_plot_summary_not_found()
    print("All tests passed.")
