#!/usr/bin/env python3
"""
GIS Data Ingestion — Spatial Boundaries

Imports GeoJSON and CSV boundary data into PostGIS columns
on location, farm, and plot tables.

Supported formats:
    - GeoJSON FeatureCollection / Feature (Polygon, MultiPolygon)
    - CSV with lat/lon columns (generates point geometries)
    - CSV with WKT geometry column

Usage:
    python3 -m services.ingestion.gis_import --file boundaries.geojson --target location
    python3 -m services.ingestion.gis_import --file coords.csv --target plot
    python3 -m services.ingestion.gis_import --file boundaries.csv --target farm
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone

from ..common.logging import get_logger
from .base import get_db, log_ingestion, hash_payload

logger = get_logger("ingestion.gis_import")

VALID_TARGETS = {"location", "farm", "plot"}
VALID_GEOM_TYPES = {"Polygon", "MultiPolygon"}

_MAX_COORDS = 10000
_MAX_AREA_HA = 1000000.0
_MIN_AREA_HA = 0.0001


def parse_geojson(filepath: str) -> list:
    """Parse a GeoJSON file and extract boundary records.

    Returns list of dicts with:
        slug, name, geom_type, coordinates, properties
    """
    with open(filepath, "r") as f:
        data = json.load(f)

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
            if lat and lon:
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
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
                    logger.warning("  Skipping row %d: invalid lat/lon: %s, %s", i + 1, lat, lon)
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

    GeoJSON Polygon coords: [[ [lon, lat], [lon, lat], ... ]]
    PostGIS WKT: SRID=4326;POLYGON((lon lat, lon lat, ...))
    """
    if not coords or not coords[0]:
        return ""

    ring = coords[0]
    points = ", ".join(f"{c[0]} {c[1]}" for c in ring)
    return f"SRID=4326;POLYGON(({points}))"


def build_multipolygon_wkt(coords: list) -> str:
    """Build PostGIS WKT for a MultiPolygon from GeoJSON coordinate array.

    GeoJSON MultiPolygon coords: [ [ [ [lon, lat], ... ] ], ... ]
    PostGIS WKT: SRID=4326;MULTIPOLYGON(((lon lat, ...)), ((lon lat, ...)))
    """
    if not coords:
        return ""

    polygons = []
    for polygon_coords in coords:
        if not polygon_coords or not polygon_coords[0]:
            continue
        ring = polygon_coords[0]
        points = ", ".join(f"{c[0]} {c[1]}" for c in ring)
        polygons.append(f"(({points}))")

    if not polygons:
        return ""

    return f"SRID=4326;MULTIPOLYGON({', '.join(polygons)})"


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
        logger.error("  Failed to update %s %s: %s", target, record_id, e)
        return False


def run(file_path: str, target: str = "location"):
    """Main ingestion entry point."""
    if target not in VALID_TARGETS:
        logger.error("Invalid target: %s. Must be one of: %s", target, ", ".join(VALID_TARGETS))
        sys.exit(1)

    db = get_db()
    success = 0
    errors = 0

    if file_path.endswith(".geojson") or file_path.endswith(".json"):
        records = parse_geojson(file_path)
    elif file_path.endswith(".csv"):
        records = parse_csv_boundaries(file_path)
    else:
        logger.error("Unsupported file format: %s", file_path)
        db.close()
        sys.exit(1)

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
            logger.error("  ✗ Row %d (%s): %s", i + 1, slug, e)
            log_ingestion(
                source_system="gis_import",
                source_table=f"{target}_geojson",
                source_id=slug,
                target_table=target,
                target_id=None,
                operation="update",
                payload_hash=hash_payload(rec),
                status="failed",
                error_message=str(e),
            )

    db.commit()
    db.close()
    logger.info("Done: %d success, %d errors", success, errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GIS boundary data ingestion")
    parser.add_argument("--file", required=True, help="Path to GeoJSON or CSV file")
    parser.add_argument(
        "--target",
        default="location",
        choices=["location", "farm", "plot"],
        help="Target table (default: location)",
    )
    args = parser.parse_args()
    run(file_path=args.file, target=args.target)
