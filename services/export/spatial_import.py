"""Spatial import: KML/GeoJSON file parsing into farm_zone geometry."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from xml.etree.ElementTree import fromstring as xml_fromstring

from services.common.logging import get_logger

logger = get_logger(__name__)


def import_geojson(
    conn,
    location_id: str,
    geojson_data: str | dict,
    filename: str = "upload.geojson",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Import a GeoJSON FeatureCollection into farm_zone geometry records.

    Each Polygon/MultiPolygon feature becomes a farm_zone record.
    """
    if isinstance(geojson_data, str):
        geojson = json.loads(geojson_data)
    else:
        geojson = geojson_data

    content_hash = hashlib.sha256(
        json.dumps(geojson, sort_keys=True).encode()
    ).hexdigest()

    features = geojson.get("features", [])
    if not features:
        _log_import(conn, location_id, "geojson", filename, content_hash, 0, 0, 0, 0, [], "failed")
        return {"error": "No features found in GeoJSON", "zones_created": 0}

    cur = conn.cursor()
    errors = []
    zones_created = 0
    zones_updated = 0
    zones_skipped = 0

    for i, feature in enumerate(features):
        try:
            geom = feature.get("geometry")
            props = feature.get("properties", {})

            if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
                zones_skipped += 1
                continue

            # Build PostGIS geometry from GeoJSON
            geom_text = json.dumps(geom)
            zone_name = props.get("name") or props.get("zone_name") or f"Imported Zone {i + 1}"
            zone_type = props.get("zone_type") or props.get("type") or "imported"
            zone_key = _slugify(zone_name)

            # Check for existing zone with same name
            cur.execute(
                "SELECT id FROM farm_zone WHERE location_id = %s AND zone_key = %s",
                (location_id, zone_key),
            )
            existing = cur.fetchone()

            if existing and not overwrite:
                zones_skipped += 1
                continue

            # Compute area using PostGIS
            cur.execute(
                "SELECT ST_Area(ST_GeomFromGeoJSON(%s)::geography)",
                (geom_text,),
            )
            area_result = cur.fetchone()
            area_m2 = float(area_result[0]) if area_result and area_result[0] else None

            if existing and overwrite:
                cur.execute(
                    """
                    UPDATE farm_zone
                    SET geometry = ST_GeomFromGeoJSON(%s),
                        area_m2 = COALESCE(%s, area_m2),
                        description = COALESCE(%s, description),
                        metadata = metadata || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (geom_text, area_m2, props.get("description"),
                     json.dumps({"imported_from": "geojson", "import_filename": filename}),
                     existing[0]),
                )
                zones_updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO farm_zone
                        (location_id, zone_key, name, zone_type, area_m2,
                         geometry, description, metadata,
                         source_system, source_id)
                    VALUES (%s, %s, %s, %s, %s,
                            ST_GeomFromGeoJSON(%s), %s, %s::jsonb,
                            'geojson_import', %s)
                    RETURNING id
                    """,
                    (location_id, zone_key, zone_name, zone_type, area_m2,
                     geom_text, props.get("description"),
                     json.dumps({"imported_from": "geojson", "import_filename": filename}),
                     f"geojson-{i + 1}"),
                )
                zones_created += 1

        except Exception as e:
            errors.append({"feature_index": i, "error": str(e)})
            logger.warning("Failed to import feature %d: %s", i, e)

    cur.close()

    status = "success" if not errors else ("partial" if zones_created > 0 else "failed")
    _log_import(conn, location_id, "geojson", filename, content_hash,
                len(features), zones_created, zones_updated, zones_skipped, errors, status)

    logger.info("GeoJSON import for %s: %d created, %d updated, %d skipped, %d errors",
                location_id, zones_created, zones_updated, zones_skipped, len(errors))

    return {
        "location_id": location_id,
        "format": "geojson",
        "filename": filename,
        "feature_count": len(features),
        "zones_created": zones_created,
        "zones_updated": zones_updated,
        "zones_skipped": zones_skipped,
        "errors": errors,
        "status": status,
    }


def import_kml(
    conn,
    location_id: str,
    kml_data: str,
    filename: str = "upload.kml",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Import a KML Document into farm_zone geometry records.

    Each Placemark with a Polygon becomes a farm_zone record.
    """
    content_hash = hashlib.sha256(kml_data.encode()).hexdigest()

    try:
        root = xml_fromstring(kml_data)
    except Exception as e:
        _log_import(conn, location_id, "kml", filename, content_hash, 0, 0, 0, 0, [], "failed")
        return {"error": f"Invalid KML XML: {e}", "zones_created": 0}

    # Handle KML namespace
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # Find all Placemarks
    placemarks = root.findall(".//kml:Placemark", ns)
    if not placemarks:
        # Try without namespace
        placemarks = root.findall(".//Placemark")

    if not placemarks:
        _log_import(conn, location_id, "kml", filename, content_hash, 0, 0, 0, 0, [], "failed")
        return {"error": "No Placemarks found in KML", "zones_created": 0}

    cur = conn.cursor()
    errors = []
    zones_created = 0
    zones_updated = 0
    zones_skipped = 0

    for i, pm in enumerate(placemarks):
        try:
            # Get name
            name_el = pm.find("kml:name", ns)
            if name_el is None:
                name_el = pm.find("name")
            zone_name = name_el.text if name_el is not None else f"Imported Zone {i + 1}"
            zone_key = _slugify(zone_name)

            # Get coordinates from Polygon
            coords_el = (
                pm.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
                or pm.find(".//Polygon/outerBoundaryIs/LinearRing/coordinates")
            )
            if coords_el is None or not coords_el.text:
                zones_skipped += 1
                continue

            # Parse KML coordinates (lon,lat,altitude tuples)
            coords_text = coords_text.strip() if (coords_text := coords_el.text) else ""
            ring_coords = []
            for token in coords_text.split():
                parts = token.split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    ring_coords.append((lon, lat))

            if len(ring_coords) < 3:
                zones_skipped += 1
                continue

            # Close the ring if needed
            if ring_coords[0] != ring_coords[-1]:
                ring_coords.append(ring_coords[0])

            # Build GeoJSON polygon for PostGIS
            geojson_geom = {
                "type": "Polygon",
                "coordinates": [[list(c) for c in ring_coords]],
            }
            geom_text = json.dumps(geojson_geom)

            # Compute area
            cur.execute(
                "SELECT ST_Area(ST_GeomFromGeoJSON(%s)::geography)",
                (geom_text,),
            )
            area_result = cur.fetchone()
            area_m2 = float(area_result[0]) if area_result and area_result[0] else None

            # Check for existing
            cur.execute(
                "SELECT id FROM farm_zone WHERE location_id = %s AND zone_key = %s",
                (location_id, zone_key),
            )
            existing = cur.fetchone()

            if existing and not overwrite:
                zones_skipped += 1
                continue

            description_el = pm.find("kml:description", ns) or pm.find("description")
            description = description_el.text if description_el is not None else None

            if existing and overwrite:
                cur.execute(
                    """
                    UPDATE farm_zone
                    SET geometry = ST_GeomFromGeoJSON(%s),
                        area_m2 = COALESCE(%s, area_m2),
                        description = COALESCE(%s, description),
                        metadata = metadata || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (geom_text, area_m2, description,
                     json.dumps({"imported_from": "kml", "import_filename": filename}),
                     existing[0]),
                )
                zones_updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO farm_zone
                        (location_id, zone_key, name, zone_type, area_m2,
                         geometry, description, metadata,
                         source_system, source_id)
                    VALUES (%s, %s, %s, 'imported', %s,
                            ST_GeomFromGeoJSON(%s), %s, %s::jsonb,
                            'kml_import', %s)
                    RETURNING id
                    """,
                    (location_id, zone_key, zone_name, area_m2,
                     geom_text, description,
                     json.dumps({"imported_from": "kml", "import_filename": filename}),
                     f"kml-{i + 1}"),
                )
                zones_created += 1

        except Exception as e:
            errors.append({"placemark_index": i, "error": str(e)})
            logger.warning("Failed to import Placemark %d: %s", i, e)

    cur.close()

    status = "success" if not errors else ("partial" if zones_created > 0 else "failed")
    _log_import(conn, location_id, "kml", filename, content_hash,
                len(placemarks), zones_created, zones_updated, zones_skipped, errors, status)

    logger.info("KML import for %s: %d created, %d updated, %d skipped, %d errors",
                location_id, zones_created, zones_updated, zones_skipped, len(errors))

    return {
        "location_id": location_id,
        "format": "kml",
        "filename": filename,
        "feature_count": len(placemarks),
        "zones_created": zones_created,
        "zones_updated": zones_updated,
        "zones_skipped": zones_skipped,
        "errors": errors,
        "status": status,
    }


def _log_import(
    conn, location_id: str, fmt: str, filename: str, content_hash: str,
    feature_count: int, created: int, updated: int, skipped: int,
    errors: list, status: str,
) -> None:
    """Log import to spatial_import_log."""
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO spatial_import_log
                (location_id, import_format, original_filename, raw_content_hash,
                 feature_count, zones_created, zones_updated, zones_skipped,
                 errors, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (location_id, fmt, filename, content_hash,
             feature_count, created, updated, skipped,
             json.dumps(errors), status),
        )
        cur.close()
    except Exception as e:
        logger.warning("Failed to log import: %s", e)


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:100]
