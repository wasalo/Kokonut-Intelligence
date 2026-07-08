"""Drone & raster integration tests: schema, seeds, spatial analytics."""

import json
from pathlib import Path

from services.analytics.spatial_analytics import (
    compute_canopy_analysis,
    compute_gap_detection,
    compute_pest_hotspots,
    compute_spatial_clusters,
)

SCHEMA = Path("schemas/postgres/059_drone_raster_integration.sql")
SEED = Path("schemas/seeds/059_drone_raster_integration.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_adds_msavi() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS msavi" in text


def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS raster_metadata" in text
    assert "CREATE TABLE IF NOT EXISTS spatial_cluster" in text
    assert "CREATE TABLE IF NOT EXISTS pest_hotspot" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_public_spatial_clusters" in text
    assert "CREATE OR REPLACE VIEW v_public_pest_hotspots" in text
    assert "CREATE OR REPLACE VIEW v_public_canopy_analysis" in text


def test_schema_has_spatial_indexes() -> None:
    text = SCHEMA.read_text()
    assert "idx_spatial_cluster_centroid" in text
    assert "idx_spatial_cluster_hull" in text
    assert "idx_pest_hotspot_centroid" in text
    assert "USING GIST" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (raster_type IN" in text
    assert "CHECK (file_format IN" in text
    assert "CHECK (cluster_method IN" in text
    assert "CHECK (cluster_type IN" in text
    assert "CHECK (confidence_score >= 0 AND confidence_score <= 100)" in text
    assert "CHECK (status IN ('active', 'treated', 'monitoring', 'resolved', 'escalated'))" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_raster_metadata() -> None:
    text = SEED.read_text()
    assert "orthomosaic" in text
    assert "ndvi_raster" in text
    assert "geotiff" in text
    assert "DJI Phantom 4 RTK" in text
    assert "Pix4Dmapper" in text


def test_seed_has_spatial_clusters() -> None:
    text = SEED.read_text()
    assert "Mature Coconut Group" in text
    assert "Juvenile Coconut Group" in text
    assert "Passion Fruit Bed" in text
    assert "dbscan" in text
    assert "ST_SetSRID" in text


def test_seed_has_pest_hotspot() -> None:
    text = SEED.read_text()
    assert "Aphid" in text
    assert "monitoring" in text
    assert "neem oil" in text
    assert "85.0" in text


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


def test_spatial_clusters_analytics() -> None:
    rows = [
        ("c1", "dbscan", "Mature Group", "species_group", 8, 90.5, "Cocos nucifera", 12.3,
         0.85, 50.0, 3, '{"type":"Point","coordinates":[-69.987,18.521]}', None, "active"),
        ("c2", "dbscan", "Juvenile Group", "age_group", 5, 71.0, "Cocos nucifera", 6.8,
         0.78, 40.0, 3, '{"type":"Point","coordinates":[-69.987,18.522]}', None, "active"),
    ]
    result = compute_spatial_clusters(_MockConn(rows=rows), "test-location")
    assert result["total_clusters"] == 2
    assert result["total_trees_in_clusters"] == 13
    assert result["avg_cluster_health"] is not None


def test_pest_hotspots_analytics() -> None:
    rows = [
        ("h1", "Aphid Cluster", "Aphid", 2, 25.0, 15.0, 707.0, 85.0,
         "2026-06-01", "field_observation", "Monitor", "active",
         '{"type":"Point","coordinates":[-69.987,18.521]}'),
    ]
    result = compute_pest_hotspots(_MockConn(rows=rows), "test-location")
    assert result["total_hotspots"] == 1
    assert result["active_hotspots"] == 1
    assert result["total_trees_affected"] == 2


def test_canopy_analysis_analytics() -> None:
    rows = [
        ("z1", "Syntropic Beds", "syntropic_plot", 7838.0, 10, 7.5, 44.2, 56.3),
        ("z2", "Agro Corridor", "agroforestry", 4500.0, 8, 6.0, 28.3, 50.3),
    ]
    result = compute_canopy_analysis(_MockConn(rows=rows), "test-location")
    assert result["total_zones"] == 2
    assert result["weighted_avg_canopy_cover_pct"] is not None


def test_gap_detection_analytics() -> None:
    rows = [
        ("z1", "syntropic_plot", "Syntropic Beds", 7838.0, 3),
        ("z2", "agroforestry", "Agro Corridor", 4500.0, 8),
    ]
    result = compute_gap_detection(_MockConn(rows=rows), "test-location")
    assert result["total_zones_analyzed"] == 2
    # Syntropic beds: 3 trees / 0.7838 ha = 3.8 trees/ha vs expected 250 = 98.5% gap
    assert result["zones_with_gaps"] >= 1


def test_pest_hotspots_no_hotspots() -> None:
    result = compute_pest_hotspots(_MockConn(rows=[]), "test-location")
    assert result["total_hotspots"] == 0
    assert result["total_trees_affected"] == 0


def test_spatial_clusters_no_clusters() -> None:
    result = compute_spatial_clusters(_MockConn(rows=[]), "test-location")
    assert result["total_clusters"] == 0
    assert result["total_trees_in_clusters"] == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_adds_msavi()
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_spatial_indexes()
    test_schema_has_check_constraints()
    test_schema_has_governed_columns()
    test_seed_has_raster_metadata()
    test_seed_has_spatial_clusters()
    test_seed_has_pest_hotspot()
    test_spatial_clusters_analytics()
    test_pest_hotspots_analytics()
    test_canopy_analysis_analytics()
    test_gap_detection_analytics()
    test_pest_hotspots_no_hotspots()
    test_spatial_clusters_no_clusters()
    print("All tests passed.")
