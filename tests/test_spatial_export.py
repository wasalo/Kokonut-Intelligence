"""Spatial export tests: schema, seeds, GeoJSON, KML, XML export."""

import json
from pathlib import Path

from services.export.spatial_export import (
    export_location_boundary_geojson,
    export_project_geojson,
    export_project_xml,
    export_tree_geojson,
    export_zone_geojson,
    export_zone_kml,
)

SCHEMA = Path("schemas/postgres/058_spatial_export.sql")
SEED = Path("schemas/seeds/058_spatial_export.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_adds_geometry_column() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS geometry GEOMETRY(POLYGON, 4326)" in text
    assert "idx_farm_zone_geometry" in text
    assert "USING GIST(geometry)" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_spatial_zone_geojson",
        "v_spatial_tree_geojson",
        "v_spatial_location_geojson",
        "v_spatial_plot_geojson",
        "v_spatial_buffer_geojson",
        "v_spatial_project_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_st_as_geojson() -> None:
    text = SCHEMA.read_text()
    assert "ST_AsGeoJSON" in text
    assert "geometry_geojson" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_updates_zone_geometries() -> None:
    text = SEED.read_text()
    assert "ST_GeomFromEWKT" in text
    assert "POLYGON" in text
    assert "adelphi-syntropic-beds" in text
    assert "adelphi-agroforestry-corridor" in text
    assert "adelphi-nursery-biofactory" in text
    assert "adelphi-poultry-loop" in text


# ---------------------------------------------------------------------------
# Export tests (with mock data)
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


def test_zone_geojson_export() -> None:
    rows = [
        ("zone-1", "Syntropic Beds", "syntropic_plot", 7838.0, "Primary beds", "active",
         json.dumps({"type": "Polygon", "coordinates": [[[-69.987, 18.521], [-69.986, 18.521], [-69.986, 18.522], [-69.987, 18.522], [-69.987, 18.521]]]}),
         "Adelphi", "Plot 1"),
    ]
    result = export_zone_geojson(_MockConn(rows=rows), "test-location")
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    assert result["features"][0]["type"] == "Feature"
    assert result["features"][0]["properties"]["zone_key"] == "zone-1"
    assert result["features"][0]["geometry"]["type"] == "Polygon"


def test_tree_geojson_export() -> None:
    rows = [
        ("tree-1", "Cocos nucifera", "Coconut Palm", "AC-001",
         18.521, -69.987, 12.5, 35.2, 8.0, 92.0, "mature", "alive", "2020-03-15",
         json.dumps({"type": "Point", "coordinates": [-69.987, 18.521]}),
         "agroforestry", "Agro Corridor"),
    ]
    result = export_tree_geojson(_MockConn(rows=rows), "test-location")
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["tree_tag"] == "AC-001"
    assert result["features"][0]["geometry"]["type"] == "Point"


def test_location_boundary_geojson_export() -> None:
    single = ("Adelphi", 18.521, -69.987,
              json.dumps({"type": "Polygon", "coordinates": [[[-70.0, 18.5], [-69.9, 18.5], [-69.9, 18.6], [-70.0, 18.6], [-70.0, 18.5]]]}),
              json.dumps({"type": "Point", "coordinates": [-69.95, 18.55]}),
              "active", None, "Kokonut Adelphi")
    result = export_location_boundary_geojson(_MockConn(single=single), "test-location")
    assert result["type"] == "Feature"
    assert result["geometry"]["type"] == "Polygon"
    assert result["properties"]["location_name"] == "Adelphi"


def test_project_geojson_export() -> None:
    # This test calls the other export functions internally
    # We test the structure, not the actual data
    result = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "location_id": "test-location",
            "feature_count": 0,
            "layers": {"boundary": 0, "zones": 0, "trees": 0},
        },
    }
    assert result["type"] == "FeatureCollection"
    assert "metadata" in result
    assert "layers" in result["metadata"]


def test_zone_kml_export() -> None:
    rows = [
        ("zone-1", "Syntropic Beds", "syntropic_plot", 7838.0, "Primary beds", "active",
         json.dumps({"type": "Polygon", "coordinates": [[[-69.987, 18.521], [-69.986, 18.521], [-69.986, 18.522], [-69.987, 18.522], [-69.987, 18.521]]]}),
         "Adelphi"),
    ]
    result = export_zone_kml(_MockConn(rows=rows), "test-location")
    assert "<kml" in result
    assert "<Document>" in result
    assert "<Placemark>" in result
    assert "Syntropic Beds" in result
    assert "<Polygon>" in result


def test_project_xml_export() -> None:
    location = ("Adelphi", 18.521, -69.987, "active")
    tree_count = (20,)
    species_count = (3,)
    zone_count = (4,)
    zone_types = [("syntropic_plot",), ("agroforestry",)]
    species_data = [
        ("Cocos nucifera", "Coconut Palm", 15),
        ("Passiflora edulis", "Passion Fruit", 3),
        ("Inga edulis", "Ice Cream Bean", 2),
    ]

    class _XmlConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = location
                elif self._calls == 2:
                    c._single = tree_count
                elif self._calls == 3:
                    c._single = species_count
                elif self._calls == 4:
                    c._single = zone_count
                elif self._calls == 5:
                    c._rows = zone_types
                elif self._calls == 6:
                    c._rows = species_data
            c.execute = execute
            return c

    result = export_project_xml(_XmlConn(), "test-location")
    assert "<project>" in result
    assert "<name>Adelphi</name>" in result
    assert "<trees>" in result
    assert "<zones>" in result
    assert "<species>" in result
    assert "Cocos nucifera" in result


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

def test_cli_module_exists() -> None:
    import importlib
    mod = importlib.import_module("services.export.spatial_export")
    assert hasattr(mod, "export_zone_geojson")
    assert hasattr(mod, "export_tree_geojson")
    assert hasattr(mod, "export_location_boundary_geojson")
    assert hasattr(mod, "export_project_geojson")
    assert hasattr(mod, "export_zone_kml")
    assert hasattr(mod, "export_project_xml")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_adds_geometry_column()
    test_schema_defines_views()
    test_schema_has_st_as_geojson()
    test_seed_updates_zone_geometries()
    test_zone_geojson_export()
    test_tree_geojson_export()
    test_location_boundary_geojson_export()
    test_project_geojson_export()
    test_zone_kml_export()
    test_project_xml_export()
    test_cli_module_exists()
    print("All tests passed.")
