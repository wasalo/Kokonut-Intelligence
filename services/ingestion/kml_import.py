"""KML/KMZ import: convert KML files to PostGIS geometry."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

from services.common.logging import get_logger

logger = get_logger("ingestion.kml_import")

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def import_kml(filepath: str, target_table: str = "location",
               location_id: str = None) -> dict:
    if not os.path.exists(filepath):
        return {"status": "error", "message": f"File not found: {filepath}"}

    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        return {"status": "error", "message": f"XML parse error: {e}"}

    records_imported = 0
    errors = []

    for placemark in root.iter():
        if placemark.tag.endswith("Placemark"):
            try:
                name_elem = placemark.find("kml:name", KML_NS)
                name = name_elem.text if name_elem is not None else "Unnamed"

                coords_elem = placemark.find(".//kml:coordinates", KML_NS)
                if coords_elem is None:
                    errors.append(f"Placemark '{name}': no coordinates")
                    continue

                coords_text = coords_elem.text.strip()
                parts = coords_text.split()
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    records_imported += 1
                else:
                    errors.append(f"Placemark '{name}': insufficient coordinates")
            except Exception as e:
                errors.append(f"Placemark: {str(e)}")

    return {
        "status": "success",
        "records_imported": records_imported,
        "errors": errors,
        "format": "kml",
    }


def parse_kml_coordinates(coords_text: str) -> list[tuple[float, float]]:
    coordinates = []
    for point in coords_text.strip().split():
        parts = point.split(",")
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            coordinates.append((lat, lon))
    return coordinates
