"""Tree tracking tests: schema, seeds, analytics, views, metrics."""

from datetime import date
from pathlib import Path

from services.analytics.tree_tracking import (
    compute_growth_rate,
    compute_species_richness,
    compute_tree_density,
)

SCHEMA = Path("schemas/postgres/057_tree_tracking.sql")
AREA_UNIT_MIGRATION = Path("schemas/postgres/462_tree_density_area_units.sql")
SEED = Path("schemas/seeds/057_tree_tracking.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS tree_record" in text
    assert "CREATE TABLE IF NOT EXISTS tree_measurement" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_public_tree_records" in text
    assert "CREATE OR REPLACE VIEW v_public_tree_density_map" in text


def test_density_view_migration_normalizes_supported_area_units() -> None:
    text = AREA_UNIT_MIGRATION.read_text()
    for unit in ["hectare", "hectares", "ha", "square_meter", "square_meters", "m2", "sqm", "acre", "acres"]:
        assert f"WHEN '{unit}'" in text
    assert "p.area / 10000.0" in text
    assert "p.area * 0.40468564224" in text
    assert "p.area <= 0" in text
    assert "ELSE NULL" in text


def test_schema_has_gis_trigger() -> None:
    text = SCHEMA.read_text()
    assert "fn_tree_record_compute_geometry" in text
    assert "ST_SetSRID(ST_MakePoint" in text
    assert "trg_tree_record_compute_geometry" in text


def test_schema_has_spatial_index() -> None:
    text = SCHEMA.read_text()
    assert "idx_tree_record_geometry" in text
    assert "USING GIST(point_geometry)" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (health_score >= 0 AND health_score <= 100)" in text
    assert "CHECK (maturity_stage IN" in text
    assert "CHECK (status IN" in text


def test_schema_has_unique_tag_constraint() -> None:
    text = SCHEMA.read_text()
    assert "idx_tree_record_tag_per_plot" in text
    assert "UNIQUE INDEX" in text or "UNIQUE" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


def test_schema_measurement_cascades() -> None:
    text = SCHEMA.read_text()
    assert "REFERENCES tree_record(id) ON DELETE CASCADE" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metric() -> None:
    text = SEED.read_text()
    assert "tree_density_per_ha" in text


def test_seed_has_pilot_trees() -> None:
    text = SEED.read_text()
    assert "AC-001" in text
    assert "AC-015" in text
    assert "SB-001" in text
    assert "AC-016" in text
    assert "Cocos nucifera" in text
    assert "Passiflora edulis" in text
    assert "Inga edulis" in text


def test_seed_has_measurements() -> None:
    text = SEED.read_text()
    assert "tree_measurement" in text
    assert "adelphi-meas-ac001-q1" in text
    assert "adelphi-meas-ac014-q3" in text


def test_seed_has_gps_coordinates() -> None:
    text = SEED.read_text()
    assert "18.5210000" in text
    assert "-69.9870000" in text


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


def test_tree_density_analytics() -> None:
    plot_rows = [
        ("plot1", "Syntropic Beds", 0.78, "hectares", 10, 9, 1, 2),
        ("plot2", "Agroforestry Corridor", 0.45, "hectares", 8, 7, 1, 2),
    ]
    species_rows = [
        ("Cocos nucifera", "Coconut Palm", 12, 11, 10.5, 6.5, 85.0),
        ("Passiflora edulis", "Passion Fruit", 3, 3, 3.0, 2.5, 83.0),
        ("Inga edulis", "Ice Cream Bean", 3, 2, 6.8, 4.8, 83.5),
    ]

    class _DensityConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    assert "p.area, p.area_unit" in query
                    assert "p.area_ha" not in query
                    c._rows = plot_rows
                elif self._calls == 2:
                    c._rows = species_rows
            c.execute = execute
            return c

    result = compute_tree_density(_DensityConn(), "test-location")
    assert result["total_trees"] == 18
    assert result["total_alive"] == 16
    assert result["total_species"] == 3
    assert len(result["plots"]) == 2
    assert len(result["species"]) == 3


def test_tree_density_converts_known_units_and_fails_closed_for_unknown_units() -> None:
    plot_rows = [
        ("acre-plot", "Acres", 1, "acre", 4, 3, 1, 1),
        ("sqm-plot", "Square meters", 10000, "square_meters", 5, 4, 1, 1),
        ("unknown-plot", "Unknown unit", 1, "furlong", 2, 2, 0, 1),
        ("zero-plot", "Zero area", 0, "hectares", 1, 1, 0, 1),
    ]

    class _DensityConn:
        def __init__(self):
            self._calls = 0

        def cursor(self, cursor_factory=None):
            cursor = _MockCursor()

            def execute(query, params=None):
                self._calls += 1
                cursor._rows = plot_rows if self._calls == 1 else []

            cursor.execute = execute
            return cursor

    result = compute_tree_density(_DensityConn(), "test-location")

    assert result["plots"][0]["area_ha"] == 0.40468564224
    assert result["plots"][0]["trees_per_ha"] == 7.41
    assert result["plots"][1]["area_ha"] == 1.0
    assert result["plots"][1]["trees_per_ha"] == 4.0
    assert result["plots"][2]["area_ha"] is None
    assert result["plots"][2]["trees_per_ha"] is None
    assert result["plots"][3]["area_ha"] is None
    assert result["plots"][3]["trees_per_ha"] is None
    assert result["total_area_ha"] is None
    assert result["overall_density_per_ha"] is None


def test_growth_rate_analytics() -> None:
    trees = [
        ("tree1", "AC-001", "Cocos nucifera", "Coconut", "2020-03-15", "mature", "alive"),
        ("tree2", "AC-002", "Cocos nucifera", "Coconut", "2020-03-15", "mature", "alive"),
    ]
    measurements_tree1 = [
        (date(2026, 1, 15), 12.0, 34.5, 7.8, 90.0),
        (date(2026, 6, 1), 12.5, 35.2, 8.0, 92.0),
    ]
    measurements_tree2 = [
        (date(2026, 1, 15), 11.3, 32.8, 7.2, 86.0),
    ]

    class _GrowthConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = trees
                elif self._calls == 2:
                    c._rows = measurements_tree1
                elif self._calls == 3:
                    c._rows = measurements_tree2
            c.execute = execute
            return c

    result = compute_growth_rate(_GrowthConn(), "test-location")
    assert result["total_trees_tracked"] == 2
    assert result["trees_with_measurements"] == 1
    assert result["avg_height_growth_m_per_year"] is not None
    assert result["avg_height_growth_m_per_year"] > 0


def test_growth_rates_preserve_zero_values_and_average_canopy_independently() -> None:
    trees = [
        ("tree1", "AC-001", "Cocos nucifera", "Coconut", None, "seedling", "alive"),
        ("tree2", "AC-002", "Inga edulis", "Ice Cream Bean", None, "juvenile", "alive"),
    ]
    zero_measurements = [
        (date(2025, 1, 1), 0.0, 0.0, 0.0, 0.0),
        (date(2026, 1, 1), 0.0, 0.0, 0.0, 0.0),
    ]
    canopy_only_measurements = [
        (date(2025, 1, 1), None, None, 2.0, None),
        (date(2026, 1, 1), None, None, 2.0, None),
    ]

    class _GrowthConn:
        def __init__(self):
            self._calls = 0

        def cursor(self, cursor_factory=None):
            cursor = _MockCursor()

            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    cursor._rows = trees
                elif self._calls == 2:
                    cursor._rows = zero_measurements
                elif self._calls == 3:
                    cursor._rows = canopy_only_measurements

            cursor.execute = execute
            return cursor

    result = compute_growth_rate(_GrowthConn(), "test-location")

    assert result["trees_with_measurements"] == 1
    assert result["trees"][0]["height_growth_m_per_year"] == 0.0
    assert result["trees"][0]["dbh_growth_cm_per_year"] == 0.0
    assert result["trees"][0]["canopy_growth_m_per_year"] == 0.0
    assert result["trees"][0]["health_trend"] == "stable"
    assert result["trees"][1]["height_growth_m_per_year"] is None
    assert result["avg_height_growth_m_per_year"] == 0.0
    assert result["avg_canopy_growth_m_per_year"] == 0.0


def test_species_richness_analytics() -> None:
    rows = [
        ("Cocos nucifera", 15),
        ("Passiflora edulis", 3),
        ("Inga edulis", 2),
    ]
    result = compute_species_richness(_MockConn(rows=rows), "test-location")
    assert result["total_trees"] == 20
    assert result["species_count"] == 3
    assert result["shannon_index"] > 0
    assert result["simpson_index"] > 0
    assert result["evenness"] > 0
    assert len(result["species"]) == 3


def test_species_richness_single_species() -> None:
    rows = [("Cocos nucifera", 20)]
    result = compute_species_richness(_MockConn(rows=rows), "test-location")
    assert result["species_count"] == 1
    assert result["shannon_index"] == 0.0
    assert result["simpson_index"] == 0.0
    assert result["evenness"] == 0.0


def test_species_richness_no_trees() -> None:
    result = compute_species_richness(_MockConn(rows=[]), "test-location")
    assert result["total_trees"] == 0
    assert result["species_count"] == 0
    assert result["shannon_index"] == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_gis_trigger()
    test_schema_has_spatial_index()
    test_schema_has_check_constraints()
    test_schema_has_unique_tag_constraint()
    test_schema_has_governed_columns()
    test_schema_measurement_cascades()
    test_seed_has_metric()
    test_seed_has_pilot_trees()
    test_seed_has_measurements()
    test_seed_has_gps_coordinates()
    test_tree_density_analytics()
    test_growth_rate_analytics()
    test_species_richness_analytics()
    test_species_richness_single_species()
    test_species_richness_no_trees()
    print("All tests passed.")
