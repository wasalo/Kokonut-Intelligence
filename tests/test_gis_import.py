"""
GIS Import Tests

Unit tests for the GIS data ingestion module.
Does not require a running database.

Usage:
    python3 -m tests.test_gis_import
    python3 -m pytest tests/test_gis_import.py -v
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ingestion import gis_import
from services.ingestion.gis_import import (
    build_multipolygon_wkt,
    build_polygon_wkt,
    parse_csv_boundaries,
    parse_geojson,
    validate_boundary_wkt,
)


def test_parse_geojson_feature_collection():
    """Test parsing a GeoJSON FeatureCollection with Polygon geometry."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-1.23, 6.45],
                            [-1.22, 6.45],
                            [-1.22, 6.46],
                            [-1.23, 6.46],
                            [-1.23, 6.45],
                        ]
                    ],
                },
                "properties": {"slug": "test-farm", "name": "Test Farm"},
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(geojson, f)
        f.flush()
        records = parse_geojson(f.name)

    os.unlink(f.name)
    assert len(records) == 1
    assert records[0]["slug"] == "test-farm"
    assert records[0]["geom_type"] == "Polygon"
    assert len(records[0]["coordinates"]) == 1
    assert len(records[0]["coordinates"][0]) == 5


def test_parse_geojson_multipolygon():
    """Test parsing a GeoJSON Feature with MultiPolygon geometry."""
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [-1.23, 6.45],
                        [-1.22, 6.45],
                        [-1.22, 6.46],
                        [-1.23, 6.46],
                        [-1.23, 6.45],
                    ]
                ],
                [
                    [
                        [-1.20, 6.40],
                        [-1.19, 6.40],
                        [-1.19, 6.41],
                        [-1.20, 6.41],
                        [-1.20, 6.40],
                    ]
                ],
            ],
        },
        "properties": {"slug": "multi-farm", "name": "Multi Farm"},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(geojson, f)
        f.flush()
        records = parse_geojson(f.name)

    os.unlink(f.name)
    assert len(records) == 1
    assert records[0]["slug"] == "multi-farm"
    assert records[0]["geom_type"] == "MultiPolygon"
    assert len(records[0]["coordinates"]) == 2


def test_parse_geojson_skips_unclosed_or_out_of_range_rings():
    valid_ring = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    invalid_ring = [[0, 0], [1, 0], [1, 1], [0, 1]]
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [invalid_ring]},
                "properties": {"slug": "open-ring"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [181, 0], [1, 1], [0, 1], [0, 0]]],
                },
                "properties": {"slug": "out-of-range"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [valid_ring]},
                "properties": {"slug": "valid-ring"},
            },
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(geojson, f)
        f.flush()
        records = parse_geojson(f.name)

    os.unlink(f.name)
    assert [record["slug"] for record in records] == ["valid-ring"]


def test_import_preflight_rejects_invalid_target_before_database_access(monkeypatch):
    monkeypatch.setattr(gis_import, "get_db", lambda: pytest.fail("database must remain closed"))

    with pytest.raises(SystemExit):
        gis_import.run("boundaries.geojson", target="unsafe_table")


def test_import_preflight_rejects_unsupported_format_before_database_access(monkeypatch):
    monkeypatch.setattr(gis_import, "get_db", lambda: pytest.fail("database must remain closed"))

    with pytest.raises(SystemExit):
        gis_import.run("boundaries.kml", target="location")


def test_import_parse_error_occurs_before_database_access(monkeypatch, tmp_path):
    source = tmp_path / "invalid.geojson"
    source.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(gis_import, "get_db", lambda: pytest.fail("database must remain closed"))

    with pytest.raises(json.JSONDecodeError):
        gis_import.run(str(source), target="location")


def test_import_with_no_valid_records_does_not_open_database(monkeypatch, tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("slug,name,lat,lon\n", encoding="utf-8")
    monkeypatch.setattr(gis_import, "get_db", lambda: pytest.fail("database must remain closed"))

    gis_import.run(str(source), target="location")


def test_parse_geojson_auto_slug():
    """Test that auto-generated slugs are created when slug is missing."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-1.23, 6.45],
                            [-1.22, 6.45],
                            [-1.22, 6.46],
                            [-1.23, 6.46],
                            [-1.23, 6.45],
                        ]
                    ],
                },
                "properties": {"name": "My Farm"},
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(geojson, f)
        f.flush()
        records = parse_geojson(f.name)

    os.unlink(f.name)
    assert len(records) == 1
    assert records[0]["slug"] == "my-farm"
    assert records[0]["name"] == "My Farm"


def test_parse_geojson_skip_unsupported_geometry():
    """Test that unsupported geometry types are skipped."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-1.23, 6.45]},
                "properties": {"slug": "point-farm"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-1.23, 6.45],
                            [-1.22, 6.45],
                            [-1.22, 6.46],
                            [-1.23, 6.46],
                            [-1.23, 6.45],
                        ]
                    ],
                },
                "properties": {"slug": "poly-farm"},
            },
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(geojson, f)
        f.flush()
        records = parse_geojson(f.name)

    os.unlink(f.name)
    assert len(records) == 1
    assert records[0]["slug"] == "poly-farm"


def test_parse_csv_lat_lon():
    """Test parsing CSV with lat/lon columns."""
    csv_content = "slug,name,lat,lon\nplot-a,Plot A,6.4500,-1.2300\nplot-b,Plot B,6.4600,-1.2200\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        records = parse_csv_boundaries(f.name)

    os.unlink(f.name)
    assert len(records) == 2
    assert records[0]["slug"] == "plot-a"
    assert records[0]["geom_type"] == "Point"
    assert "SRID=4326;POINT(-1.23 6.45)" == records[0]["wkt"]
    assert records[1]["slug"] == "plot-b"


def test_parse_csv_accepts_zero_and_skips_non_finite_or_out_of_range_coordinates():
    csv_content = (
        "slug,name,lat,lon\n"
        "origin,Origin,0,0\n"
        "nan-lat,Invalid,NaN,0\n"
        "bad-lat,Invalid,91,0\n"
        "bad-lon,Invalid,0,181\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        records = parse_csv_boundaries(f.name)

    os.unlink(f.name)
    assert len(records) == 1
    assert records[0]["slug"] == "origin"
    assert records[0]["wkt"] == "SRID=4326;POINT(0.0 0.0)"


def test_parse_csv_wkt_column():
    """Test parsing CSV with WKT geometry column."""
    csv_content = "slug,geometry\nfarm-a,SRID=4326;POLYGON((-1.23 6.45,-1.22 6.45,-1.22 6.46,-1.23 6.46,-1.23 6.45))\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        records = parse_csv_boundaries(f.name)

    os.unlink(f.name)
    assert len(records) == 1
    assert records[0]["slug"] == "farm-a"
    assert records[0]["geom_type"] == "WKT"
    assert "POLYGON" in records[0]["wkt"]


def test_validate_boundary_wkt_valid():
    """Test validation of valid WKT geometry."""
    wkt = "SRID=4326;POLYGON((-1.23 6.45,-1.22 6.45,-1.22 6.46,-1.23 6.46,-1.23 6.45))"
    errors = validate_boundary_wkt(wkt)
    assert len(errors) == 0


def test_validate_boundary_wkt_missing_srid():
    """Test validation catches missing SRID prefix."""
    wkt = "POLYGON((-1.23 6.45,-1.22 6.45,-1.22 6.46,-1.23 6.46,-1.23 6.45))"
    errors = validate_boundary_wkt(wkt)
    assert len(errors) == 1
    assert "missing SRID=4326" in errors[0]


def test_validate_boundary_wkt_empty():
    """Test validation catches empty WKT."""
    errors = validate_boundary_wkt("")
    assert len(errors) == 1
    assert "empty WKT" in errors[0]


def test_build_polygon_wkt():
    """Test building PostGIS WKT from GeoJSON Polygon coordinates."""
    coords = [
        [
            [-1.23, 6.45],
            [-1.22, 6.45],
            [-1.22, 6.46],
            [-1.23, 6.46],
            [-1.23, 6.45],
        ]
    ]
    wkt = build_polygon_wkt(coords)
    assert wkt == "SRID=4326;POLYGON((-1.23 6.45, -1.22 6.45, -1.22 6.46, -1.23 6.46, -1.23 6.45))"


def test_build_polygon_wkt_preserves_interior_rings():
    coordinates = [
        [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
        [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]],
    ]
    assert build_polygon_wkt(coordinates) == (
        "SRID=4326;POLYGON((0 0, 4 0, 4 4, 0 4, 0 0), "
        "(1 1, 1 2, 2 2, 2 1, 1 1))"
    )


def test_build_polygon_wkt_rejects_open_rings():
    with pytest.raises(ValueError, match="must be closed"):
        build_polygon_wkt([[[0, 0], [1, 0], [1, 1], [0, 1]]])


def test_build_multipolygon_wkt():
    """Test building PostGIS WKT from GeoJSON MultiPolygon coordinates."""
    coords = [
        [
            [
                [-1.23, 6.45],
                [-1.22, 6.45],
                [-1.22, 6.46],
                [-1.23, 6.46],
                [-1.23, 6.45],
            ]
        ],
        [
            [
                [-1.20, 6.40],
                [-1.19, 6.40],
                [-1.19, 6.41],
                [-1.20, 6.41],
                [-1.20, 6.40],
            ]
        ],
    ]
    wkt = build_multipolygon_wkt(coords)
    assert "MULTIPOLYGON" in wkt
    assert "-1.23 6.45" in wkt
    assert "-1.2 6.4" in wkt or "-1.20 6.40" in wkt


def test_build_multipolygon_wkt_preserves_holes_and_all_polygons():
    coordinates = [
        [
            [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
            [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]],
        ],
        [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]],
    ]
    assert build_multipolygon_wkt(coordinates) == (
        "SRID=4326;MULTIPOLYGON(((0 0, 4 0, 4 4, 0 4, 0 0), "
        "(1 1, 1 2, 2 2, 2 1, 1 1)), "
        "((10 10, 11 10, 11 11, 10 11, 10 10)))"
    )


def test_build_polygon_wkt_empty():
    """Test building WKT from empty coordinates returns empty string."""
    assert build_polygon_wkt([]) == ""
    assert build_polygon_wkt([[]]) == ""


def test_build_multipolygon_wkt_empty():
    """Test building WKT from empty MultiPolygon coordinates returns empty string."""
    assert build_multipolygon_wkt([]) == ""
