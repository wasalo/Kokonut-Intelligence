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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ingestion.gis_import import (
    parse_geojson,
    parse_csv_boundaries,
    validate_boundary_wkt,
    build_polygon_wkt,
    build_multipolygon_wkt,
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


def test_build_polygon_wkt_empty():
    """Test building WKT from empty coordinates returns empty string."""
    assert build_polygon_wkt([]) == ""
    assert build_polygon_wkt([[]]) == ""


def test_build_multipolygon_wkt_empty():
    """Test building WKT from empty MultiPolygon coordinates returns empty string."""
    assert build_multipolygon_wkt([]) == ""
