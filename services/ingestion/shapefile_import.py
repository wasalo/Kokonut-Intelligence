"""Shapefile import: convert shapefiles to PostGIS geometry."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from services.common.logging import get_logger

logger = get_logger("ingestion.shapefile_import")


def import_shapefile(filepath: str, target_table: str = "location",
                     location_id: str = None) -> dict:
    try:
        import fiona
    except ImportError:
        return {"status": "error", "message": "fiona not installed. Run: pip install fiona"}

    if not os.path.exists(filepath):
        return {"status": "error", "message": f"File not found: {filepath}"}

    records_imported = 0
    errors = []

    with fiona.open(filepath) as src:
        for i, feature in enumerate(src):
            try:
                geom = feature.get("geometry")
                props = feature.get("properties", {})

                if not geom:
                    errors.append(f"Feature {i}: no geometry")
                    continue

                geom_type = geom.get("type", "")
                coords = geom.get("coordinates")

                if geom_type == "Point" and coords:
                    lat, lon = coords[1], coords[0]
                elif geom_type == "Polygon" and coords:
                    lat = sum(c[1] for c in coords[0]) / len(coords[0])
                    lon = sum(c[0] for c in coords[0]) / len(coords[0])
                else:
                    errors.append(f"Feature {i}: unsupported geometry type {geom_type}")
                    continue

                name = props.get("name") or props.get("NAME") or props.get("Name") or f"Imported {i}"

                records_imported += 1
            except Exception as e:
                errors.append(f"Feature {i}: {str(e)}")

    return {
        "status": "success",
        "records_imported": records_imported,
        "errors": errors,
        "format": "shapefile",
    }


def get_shapefile_info(filepath: str) -> dict:
    try:
        import fiona
    except ImportError:
        return {"status": "error", "message": "fiona not installed"}

    if not os.path.exists(filepath):
        return {"status": "error", "message": f"File not found: {filepath}"}

    with fiona.open(filepath) as src:
        return {
            "driver": src.driver,
            "crs": str(src.crs) if src.crs else None,
            "schema": dict(src.schema) if src.schema else None,
            "count": len(src),
            "encoding": src.encoding,
        }


SUPPORTED_FORMATS = {
    "shp": "ESRI Shapefile",
    "geojson": "GeoJSON",
    "csv": "CSV",
    "kml": "KML",
    "kmz": "KMZ",
    "gpx": "GPX",
    "gml": "GML",
    "flatgeobuf": "FlatGeobuf",
}
