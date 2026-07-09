"""Spatial import tests: schema, GeoJSON/KML parsing, validation."""

import json
from pathlib import Path

from services.export.spatial_import import (
    _slugify,
    import_geojson,
    import_kml,
)

SCHEMA = Path("schemas/postgres/072_spatial_import.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_table() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS spatial_import_log" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (import_format IN ('geojson', 'kml'))" in text
    assert "CHECK (status IN ('success', 'partial', 'failed'))" in text


def test_schema_has_indexes() -> None:
    text = SCHEMA.read_text()
    assert "idx_spatial_import_location" in text
    assert "idx_spatial_import_format" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    assert "created_at" in text
    assert "imported_by" in text


# ---------------------------------------------------------------------------
# Slugify tests
# ---------------------------------------------------------------------------

def test_slugify_simple() -> None:
    assert _slugify("Hello World") == "hello-world"


def test_slugify_special_chars() -> None:
    assert _slugify("Zone #1 (Agroforestry)") == "zone-1-agroforestry"


def test_slugify_multiple_dashes() -> None:
    assert _slugify("a---b") == "a-b"


# ---------------------------------------------------------------------------
# GeoJSON import tests
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


def test_geojson_empty_features() -> None:
    geojson = {"type": "FeatureCollection", "features": []}
    result = import_geojson(_MockConn(), "loc-1", geojson)
    assert result["zones_created"] == 0
    assert result["error"] == "No features found in GeoJSON"


def test_geojson_single_polygon() -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-69.987, 18.521],
                        [-69.986, 18.521],
                        [-69.986, 18.522],
                        [-69.987, 18.522],
                        [-69.987, 18.521],
                    ]],
                },
                "properties": {"name": "Test Zone", "zone_type": "agroforestry"},
            }
        ],
    }

    class _ImportConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = None  # No existing zone
                elif self._calls == 2:
                    c._single = (1234.5,)  # Area result
                elif self._calls == 3:
                    c._single = ("new-zone-id",)  # INSERT result
            c.execute = execute
            return c

    result = import_geojson(_ImportConn(), "loc-1", geojson, filename="test.geojson")
    assert result["zones_created"] == 1
    assert result["feature_count"] == 1


def test_geojson_non_polygon_skipped() -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-69.987, 18.521]},
                "properties": {"name": "Point Feature"},
            }
        ],
    }
    result = import_geojson(_MockConn(), "loc-1", geojson)
    assert result["zones_created"] == 0
    assert result["zones_skipped"] == 1


def test_geojson_string_input() -> None:
    geojson_str = json.dumps({
        "type": "FeatureCollection",
        "features": [],
    })
    result = import_geojson(_MockConn(), "loc-1", geojson_str)
    assert result["zones_created"] == 0
    assert result["error"] == "No features found in GeoJSON"


# ---------------------------------------------------------------------------
# KML import tests
# ---------------------------------------------------------------------------

def test_kml_empty() -> None:
    kml = '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document></Document></kml>'
    result = import_kml(_MockConn(), "loc-1", kml)
    assert result["zones_created"] == 0
    assert result["error"] == "No Placemarks found in KML"


def test_kml_invalid_xml() -> None:
    result = import_kml(_MockConn(), "loc-1", "not xml at all")
    assert result["zones_created"] == 0
    assert "Invalid KML XML" in result["error"]


def test_kml_single_placemark() -> None:
    kml = """<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <Placemark>
    <name>Test Zone</name>
    <description>A test zone</description>
    <Polygon>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>
            -69.987,18.521,0
            -69.986,18.521,0
            -69.986,18.522,0
            -69.987,18.522,0
            -69.987,18.521,0
          </coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>
</Document>
</kml>"""

    # Verify parsing works (KML import with mock DB is tested by structure)
    from xml.etree.ElementTree import fromstring
    root = fromstring(kml)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    placemarks = root.findall(".//kml:Placemark", ns)
    assert len(placemarks) == 1

    pm = placemarks[0]
    name_el = pm.find("kml:name", ns)
    assert name_el is not None and name_el.text == "Test Zone"

    coords_el = pm.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
    assert coords_el is not None and coords_el.text is not None
    coords_text = coords_el.text.strip()
    tokens = coords_text.split()
    assert len(tokens) == 5  # 5 coordinate tuples

    # Verify result structure
    result = import_kml(_MockConn(), "loc-1", kml, filename="test.kml")
    assert result["format"] == "kml"
    assert result["feature_count"] == 1


def test_kml_placemark_without_polygon_skipped() -> None:
    kml = """<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <Placemark>
    <name>Point Placemark</name>
    <Point><coordinates>-69.987,18.521,0</coordinates></Point>
  </Placemark>
</Document>
</kml>"""
    result = import_kml(_MockConn(), "loc-1", kml)
    assert result["zones_created"] == 0
    assert result["zones_skipped"] == 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_table()
    test_schema_has_check_constraints()
    test_schema_has_indexes()
    test_schema_has_governed_columns()
    test_slugify_simple()
    test_slugify_special_chars()
    test_slugify_multiple_dashes()
    test_geojson_empty_features()
    test_geojson_single_polygon()
    test_geojson_non_polygon_skipped()
    test_geojson_string_input()
    test_kml_empty()
    test_kml_invalid_xml()
    test_kml_single_placemark()
    test_kml_placemark_without_polygon_skipped()
    print("All tests passed.")
