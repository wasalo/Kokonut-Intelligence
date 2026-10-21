#!/usr/bin/env python3
"""
GIS Data Ingestion — Spatial Boundaries

Imports GeoJSON and CSV boundary data into PostGIS columns
on location, farm, and plot tables.

Supported formats:
    - GeoJSON FeatureCollection / Feature (Polygon, MultiPolygon)
    - CSV with lat/lon columns (generates point geometries)
    - CSV with WKT geometry column
    - KML Placemark Polygon and MultiGeometry polygon boundaries

Usage:
    python3 -m services.ingestion.gis_import --file boundaries.geojson --target location
    python3 -m services.ingestion.gis_import --file coords.csv --target plot
    python3 -m services.ingestion.gis_import --file boundaries.csv --target farm
    python3 -m services.ingestion.gis_import --file boundaries.kml --target location
"""

import argparse
import csv
import json
import math
import sys

from defusedxml import ElementTree as SafeET

from ..common.logging import get_logger
from .base import get_db, hash_payload, log_ingestion

logger = get_logger("ingestion.gis_import")

VALID_TARGETS = {"location", "farm", "plot"}
VALID_GEOM_TYPES = {"Polygon", "MultiPolygon"}

_MAX_COORDS = 10000
_MAX_AREA_HA = 1000000.0
_MIN_AREA_HA = 0.0001


def _normalize_position(position: list | tuple) -> tuple[float, float]:
    """Return a validated WGS84 longitude/latitude pair for a boundary ring."""
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        raise ValueError("position must contain longitude and latitude")

    longitude, latitude = position[:2]
    if (
        isinstance(longitude, bool)
        or isinstance(latitude, bool)
        or not isinstance(longitude, (int, float))
        or not isinstance(latitude, (int, float))
    ):
        raise ValueError("longitude and latitude must be numeric")

    longitude = float(longitude)
    latitude = float(latitude)
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise ValueError("longitude and latitude must be finite")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("coordinate is outside WGS84 longitude/latitude bounds")
    return longitude, latitude


def _normalize_ring(ring: list | tuple) -> list[tuple[float, float]]:
    if not isinstance(ring, (list, tuple)) or len(ring) < 4:
        raise ValueError("linear ring must contain at least four positions")
    if len(ring) > _MAX_COORDS:
        raise ValueError("linear ring exceeds maximum coordinate count")

    positions = [_normalize_position(position) for position in ring]
    if positions[0] != positions[-1]:
        raise ValueError("linear ring must be closed")
    return positions


def _normalize_polygon_rings(coordinates: list | tuple) -> list[list[tuple[float, float]]]:
    if not isinstance(coordinates, (list, tuple)) or not coordinates:
        raise ValueError("polygon must contain an exterior ring")

    rings = []
    coordinate_count = 0
    for ring in coordinates:
        normalized_ring = _normalize_ring(ring)
        coordinate_count += len(normalized_ring)
        if coordinate_count > _MAX_COORDS:
            raise ValueError("polygon exceeds maximum coordinate count")
        rings.append(normalized_ring)
    return rings


def _normalize_multipolygon_rings(
    coordinates: list | tuple,
) -> list[list[list[tuple[float, float]]]]:
    if not isinstance(coordinates, (list, tuple)) or not coordinates:
        raise ValueError("multipolygon must contain at least one polygon")

    polygons = []
    coordinate_count = 0
    for polygon in coordinates:
        rings = _normalize_polygon_rings(polygon)
        coordinate_count += sum(len(ring) for ring in rings)
        if coordinate_count > _MAX_COORDS:
            raise ValueError("multipolygon exceeds maximum coordinate count")
        polygons.append(rings)
    return polygons


def _ring_to_wkt(ring: list[tuple[float, float]]) -> str:
    points = ", ".join(f"{longitude:g} {latitude:g}" for longitude, latitude in ring)
    return f"({points})"


def parse_geojson(filepath: str) -> list:
    """Parse a GeoJSON file and extract boundary records.

    Returns list of dicts with:
        slug, name, geom_type, coordinates, properties
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("GeoJSON root must be an object")

    features = []
    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
    elif data.get("type") == "Feature":
        features = [data]

    records = []
    for i, feature in enumerate(features):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})

        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if geom_type not in VALID_GEOM_TYPES:
            logger.warning("  Skipping feature %d: unsupported geometry type %s", i + 1, geom_type)
            continue

        if not coords:
            logger.warning("  Skipping feature %d: empty coordinates", i + 1)
            continue

        try:
            if geom_type == "Polygon":
                _normalize_polygon_rings(coords)
            else:
                _normalize_multipolygon_rings(coords)
        except ValueError as exc:
            logger.warning("  Skipping feature %d: invalid coordinates (%s)", i + 1, exc)
            continue

        slug = props.get("slug") or props.get("name", f"import-{i + 1}").lower().replace(" ", "-")
        name = props.get("name", slug)

        records.append({
            "slug": slug,
            "name": name,
            "geom_type": geom_type,
            "coordinates": coords,
            "properties": props,
        })

    return records


def _local_xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_child_text(element, child_name: str) -> str | None:
    for child in element:
        if _local_xml_name(child.tag) == child_name:
            return (child.text or "").strip()
    return None


def _kml_coordinates(text: str | None) -> list[tuple[float, float]]:
    if not text:
        raise ValueError("LinearRing has no coordinates")

    positions = []
    for coordinate in text.split():
        parts = coordinate.split(",")
        if len(parts) < 2:
            raise ValueError("KML coordinate must contain longitude and latitude")
        try:
            positions.append((float(parts[0]), float(parts[1])))
        except ValueError as exc:
            raise ValueError("KML coordinate contains a non-numeric value") from exc
    return positions


def _kml_polygon_rings(polygon) -> list[list[tuple[float, float]]]:
    rings = []
    for boundary in polygon:
        boundary_name = _local_xml_name(boundary.tag)
        if boundary_name not in {"outerBoundaryIs", "innerBoundaryIs"}:
            continue
        linear_ring = next(
            (element for element in boundary.iter() if _local_xml_name(element.tag) == "LinearRing"),
            None,
        )
        if linear_ring is None:
            raise ValueError("KML boundary is missing a LinearRing")
        coordinate_element = next(
            (element for element in linear_ring if _local_xml_name(element.tag) == "coordinates"),
            None,
        )
        coordinates = _kml_coordinates(
            coordinate_element.text if coordinate_element is not None else None
        )
        rings.append(_normalize_ring(coordinates))

    if not rings:
        raise ValueError("KML Polygon has no boundary rings")
    return rings


def parse_kml(filepath: str) -> list:
    """Parse KML Placemark polygons into the shared GIS-import record shape."""
    root = SafeET.parse(filepath).getroot()
    placemarks = [element for element in root.iter() if _local_xml_name(element.tag) == "Placemark"]
    records = []

    for index, placemark in enumerate(placemarks, start=1):
        properties = {}
        for element in placemark.iter():
            tag_name = _local_xml_name(element.tag)
            if tag_name == "Data" and element.get("name"):
                value = _direct_child_text(element, "value")
                if value is not None:
                    properties[element.get("name")] = value
            elif tag_name == "SimpleData" and element.get("name"):
                properties[element.get("name")] = (element.text or "").strip()

        polygon_coordinates = []
        try:
            for element in placemark.iter():
                if _local_xml_name(element.tag) == "Polygon":
                    polygon_coordinates.append(_kml_polygon_rings(element))
            if not polygon_coordinates:
                logger.warning("  Skipping KML Placemark %d: no Polygon geometry", index)
                continue
            if len(polygon_coordinates) == 1:
                geometry_type = "Polygon"
                coordinates = _normalize_polygon_rings(polygon_coordinates[0])
            else:
                geometry_type = "MultiPolygon"
                coordinates = _normalize_multipolygon_rings(polygon_coordinates)
        except ValueError as exc:
            logger.warning("  Skipping KML Placemark %d: invalid coordinates (%s)", index, exc)
            continue

        name = _direct_child_text(placemark, "name") or properties.get("name") or f"import-{index}"
        slug = properties.get("slug") or name.lower().replace(" ", "-")
        properties.setdefault("name", name)
        records.append(
            {
                "slug": slug,
                "name": name,
                "geom_type": geometry_type,
                "coordinates": coordinates,
                "properties": properties,
            }
        )

    return records


def parse_csv_boundaries(filepath: str) -> list:
    """Parse a CSV file with boundary data.

    Supported column patterns:
        - slug, lat, lon → point geometry
        - slug, name, lat, lon → point geometry
        - slug, geometry (WKT) → direct WKT passthrough
        - id, boundary_wkt → direct WKT passthrough
    """
    records = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            slug = row.get("slug") or row.get("id") or f"import-{i + 1}"
            name = row.get("name", slug)

            wkt = row.get("geometry") or row.get("boundary_wkt") or row.get("wkt")
            if wkt:
                records.append({
                    "slug": slug,
                    "name": name,
                    "geom_type": "WKT",
                    "wkt": wkt.strip(),
                    "properties": dict(row),
                })
                continue

            lat = row.get("lat") or row.get("latitude")
            lon = row.get("lon") or row.get("longitude") or row.get("lng")
            if (
                lat is not None
                and lon is not None
                and str(lat).strip() != ""
                and str(lon).strip() != ""
            ):
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    if not math.isfinite(lat_f) or not math.isfinite(lon_f):
                        raise ValueError("coordinates must be finite")
                    if not -90 <= lat_f <= 90 or not -180 <= lon_f <= 180:
                        raise ValueError("coordinates are outside WGS84 bounds")
                    wkt_point = f"SRID=4326;POINT({lon_f} {lat_f})"
                    records.append({
                        "slug": slug,
                        "name": name,
                        "geom_type": "Point",
                        "wkt": wkt_point,
                        "lat": lat_f,
                        "lon": lon_f,
                        "properties": dict(row),
                    })
                except (ValueError, TypeError):
                    logger.warning("  Skipping row %d: invalid latitude/longitude", i + 1)
                continue

            logger.warning("  Skipping row %d: no geometry, lat/lon, or WKT found", i + 1)

    return records


def validate_boundary_wkt(wkt: str) -> list:
    """Validate a WKT geometry string. Returns list of errors."""
    errors = []
    if not wkt or not wkt.strip():
        errors.append("empty WKT")
        return errors

    if not wkt.upper().startswith("SRID=4326;"):
        errors.append("missing SRID=4326 prefix")

    geom_part = wkt.split(";", 1)[1] if ";" in wkt else wkt
    geom_type = geom_part.split("(")[0].strip()

    if geom_type not in ("POLYGON", "MULTIPOLYGON", "POINT"):
        errors.append(f"unsupported geometry type: {geom_type}")

    if len(wkt) > _MAX_COORDS * 50:
        errors.append("WKT exceeds maximum coordinate count")

    return errors


def build_polygon_wkt(coords: list) -> str:
    """Build PostGIS WKT for a Polygon from GeoJSON coordinate array.

    GeoJSON Polygon coords contain an exterior ring followed by optional holes.
    All rings are preserved in the generated PostGIS WKT.
    """
    if not coords or (len(coords) == 1 and not coords[0]):
        return ""

    rings = _normalize_polygon_rings(coords)
    return f"SRID=4326;POLYGON({', '.join(_ring_to_wkt(ring) for ring in rings)})"


def build_multipolygon_wkt(coords: list) -> str:
    """Build PostGIS WKT for a MultiPolygon from GeoJSON coordinate array.

    GeoJSON MultiPolygon coords contain polygons with exterior and optional
    interior rings; all rings are preserved in the generated PostGIS WKT.
    """
    if not coords:
        return ""

    polygons = _normalize_multipolygon_rings(coords)
    polygon_wkts = [
        f"({', '.join(_ring_to_wkt(ring) for ring in rings)})" for rings in polygons
    ]
    return f"SRID=4326;MULTIPOLYGON({', '.join(polygon_wkts)})"


def compute_center(wkt: str) -> str:
    """Compute center point WKT from a polygon WKT using ST_Centroid."""
    return f"ST_Centroid(ST_GeomFromEWKT('{wkt}'))"


def resolve_target_record(db, slug: str, target: str) -> str:
    """Look up a record ID by slug from the target table. Returns UUID or None."""
    with db.cursor() as cur:
        cur.execute(
            f"SELECT id FROM {target} WHERE slug = %s LIMIT 1",
            (slug,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def import_record(db, record_id: str, target: str, wkt: str, lat: float = None, lon: float = None) -> bool:
    """Update a record with boundary geometry, center, and lat/lon.

    Returns True if the record was updated.
    """
    try:
        with db.cursor() as cur:
            if lat is not None and lon is not None:
                cur.execute(
                    f"""
                    UPDATE {target}
                    SET boundary = ST_GeomFromEWKT(%s),
                        center = ST_Centroid(ST_GeomFromEWKT(%s)),
                        latitude = %s,
                        longitude = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (wkt, wkt, lat, lon, record_id),
                )
            else:
                cur.execute(
                    f"""
                    UPDATE {target}
                    SET boundary = ST_GeomFromEWKT(%s),
                        center = ST_Centroid(ST_GeomFromEWKT(%s)),
                        latitude = ST_Y(ST_Centroid(ST_GeomFromEWKT(%s))),
                        longitude = ST_X(ST_Centroid(ST_GeomFromEWKT(%s))),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (wkt, wkt, wkt, wkt, record_id),
                )
        return cur.rowcount > 0
    except Exception as e:
        logger.error("  Failed to update %s %s (%s)", target, record_id, type(e).__name__)
        return False


def run(file_path: str, target: str = "location"):
    """Main ingestion entry point."""
    if target not in VALID_TARGETS:
        logger.error("Invalid target: %s. Must be one of: %s", target, ", ".join(VALID_TARGETS))
        sys.exit(1)

    if file_path.lower().endswith((".geojson", ".json")):
        records = parse_geojson(file_path)
    elif file_path.lower().endswith(".csv"):
        records = parse_csv_boundaries(file_path)
    elif file_path.lower().endswith(".kml"):
        records = parse_kml(file_path)
    else:
        logger.error("Unsupported file format: %s", file_path)
        sys.exit(1)

    if not records:
        logger.info("No valid boundary records to import from %s", file_path)
        return

    db = get_db()
    success = 0
    errors = 0
    logger.info("Processing %d records from %s (target: %s)...", len(records), file_path, target)

    for i, rec in enumerate(records):
        slug = rec["slug"]

        try:
            record_id = resolve_target_record(db, slug, target)
            if not record_id:
                errors += 1
                logger.warning("  ✗ Record not found: %s (slug: %s)", target, slug)
                log_ingestion(
                    source_system="gis_import",
                    source_table=f"{target}_geojson",
                    source_id=slug,
                    target_table=target,
                    target_id=None,
                    operation="update",
                    payload_hash=hash_payload(rec),
                    status="failed",
                    error_message=f"Record not found: {slug}",
                )
                continue

            if rec["geom_type"] == "WKT":
                wkt = rec["wkt"]
                lat = None
                lon = None
            elif rec["geom_type"] == "Point":
                wkt = rec["wkt"]
                lat = rec.get("lat")
                lon = rec.get("lon")
            elif rec["geom_type"] == "Polygon":
                wkt = build_polygon_wkt(rec["coordinates"])
                lat = None
                lon = None
            elif rec["geom_type"] == "MultiPolygon":
                wkt = build_multipolygon_wkt(rec["coordinates"])
                lat = None
                lon = None
            else:
                errors += 1
                logger.warning("  ✗ Unsupported geometry type: %s", rec["geom_type"])
                continue

            validation_errors = validate_boundary_wkt(wkt)
            if validation_errors:
                errors += 1
                logger.warning("  ✗ Invalid boundary for %s: %s", slug, ", ".join(validation_errors))
                log_ingestion(
                    source_system="gis_import",
                    source_table=f"{target}_geojson",
                    source_id=slug,
                    target_table=target,
                    target_id=record_id,
                    operation="update",
                    payload_hash=hash_payload(rec),
                    status="failed",
                    error_message=", ".join(validation_errors),
                )
                continue

            updated = import_record(db, record_id, target, wkt, lat, lon)
            if updated:
                success += 1
                logger.info("  ✓ %s: %s boundary updated", target, slug)
                log_ingestion(
                    source_system="gis_import",
                    source_table=f"{target}_geojson",
                    source_id=slug,
                    target_table=target,
                    target_id=record_id,
                    operation="update",
                    payload_hash=hash_payload(rec),
                    status="success",
                    rows_affected=1,
                )
            else:
                errors += 1
                logger.warning("  ✗ %s: no rows updated for %s", target, slug)

        except Exception as e:
            errors += 1
            logger.error("  ✗ Row %d (%s) failed (%s)", i + 1, slug, type(e).__name__)
            log_ingestion(
                source_system="gis_import",
                source_table=f"{target}_geojson",
                source_id=slug,
                target_table=target,
                target_id=None,
                operation="update",
                payload_hash=hash_payload(rec),
                status="failed",
                error_message=f"boundary import failed ({type(e).__name__})",
            )

    db.commit()
    db.close()
    logger.info("Done: %d success, %d errors", success, errors)


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone and unified CLI parser."""
    parser = argparse.ArgumentParser(
        prog="gis_import.py",
        description="GIS boundary data ingestion",
    )
    parser.add_argument("--file", required=True, help="Path to GeoJSON, CSV, or KML file")
    parser.add_argument(
        "--target",
        default="location",
        choices=["location", "farm", "plot"],
        help="Target table (default: location)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run a GIS boundary import."""
    args = build_parser().parse_args(argv)
    run(file_path=args.file, target=args.target)


if __name__ == "__main__":
    main()
