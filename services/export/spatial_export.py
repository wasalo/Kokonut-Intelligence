"""Spatial export: GeoJSON, KML, XML export for zones, trees, and boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from services.common.logging import get_logger

logger = get_logger(__name__)


def export_zone_geojson(conn, location_id: str) -> dict[str, Any]:
    """Export farm zones as GeoJSON FeatureCollection."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT zone_key, name, zone_type, area_m2, description, status,
               geometry_geojson, location_name, plot_name
        FROM v_spatial_zone_geojson
        WHERE location_id = %s
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    features = []
    for row in rows:
        geom = json.loads(row[6]) if row[6] else None
        feature = {
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "zone_key": row[0],
                "name": row[1],
                "zone_type": row[2],
                "area_m2": float(row[3]) if row[3] else None,
                "description": row[4],
                "status": row[5],
                "location_name": row[7],
                "plot_name": row[8],
            },
        }
        features.append(feature)

    collection = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "location_id": location_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(features),
        },
    }

    logger.info("Exported %d zone features as GeoJSON for location %s", len(features), location_id)
    return collection


def export_tree_geojson(conn, location_id: str) -> dict[str, Any]:
    """Export tree records as GeoJSON FeatureCollection."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, species_name, species_common_name, tree_tag,
               latitude, longitude, height_m, dbh_cm, canopy_diameter_m,
               health_score, maturity_stage, status, planting_date,
               geometry_geojson, zone_type, plot_name
        FROM v_spatial_tree_geojson
        WHERE location_id = %s
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    features = []
    for row in rows:
        geom = json.loads(row[13]) if row[13] else None
        feature = {
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "tree_id": str(row[0]),
                "species_name": row[1],
                "species_common_name": row[2],
                "tree_tag": row[3],
                "latitude": float(row[4]) if row[4] else None,
                "longitude": float(row[5]) if row[5] else None,
                "height_m": float(row[6]) if row[6] else None,
                "dbh_cm": float(row[7]) if row[7] else None,
                "canopy_diameter_m": float(row[8]) if row[8] else None,
                "health_score": float(row[9]) if row[9] else None,
                "maturity_stage": row[10],
                "status": row[11],
                "planting_date": str(row[12]) if row[12] else None,
                "zone_type": row[14],
                "plot_name": row[15],
            },
        }
        features.append(feature)

    collection = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "location_id": location_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(features),
        },
    }

    logger.info("Exported %d tree features as GeoJSON for location %s", len(features), location_id)
    return collection


def export_location_boundary_geojson(conn, location_id: str) -> dict[str, Any]:
    """Export location boundary as GeoJSON Feature."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT location_name, latitude, longitude, boundary_geojson,
               center_geojson, status, farm_registry_id, farm_name
        FROM v_spatial_location_geojson
        WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"type": "Feature", "geometry": None, "properties": {}}

    boundary = json.loads(row[3]) if row[3] else None
    return {
        "type": "Feature",
        "geometry": boundary,
        "properties": {
            "location_id": location_id,
            "location_name": row[0],
            "latitude": float(row[1]) if row[1] else None,
            "longitude": float(row[2]) if row[2] else None,
            "status": row[5],
            "farm_registry_id": str(row[6]) if row[6] else None,
            "farm_name": row[7],
        },
    }


def export_project_geojson(conn, location_id: str) -> dict[str, Any]:
    """Export complete project as GeoJSON with zones, trees, and boundary."""
    boundary = export_location_boundary_geojson(conn, location_id)
    zones = export_zone_geojson(conn, location_id)
    trees = export_tree_geojson(conn, location_id)

    features = [boundary] + zones.get("features", []) + trees.get("features", [])

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "location_id": location_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(features),
            "layers": {
                "boundary": 1 if boundary.get("geometry") else 0,
                "zones": len(zones.get("features", [])),
                "trees": len(trees.get("features", [])),
            },
        },
    }


def export_zone_kml(conn, location_id: str) -> str:
    """Export farm zones as KML string."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT zone_key, name, zone_type, area_m2, description, status,
               geometry_geojson, location_name
        FROM v_spatial_zone_geojson
        WHERE location_id = %s
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = SubElement(kml, "Document")
    doc_name = SubElement(document, "name")
    doc_name.text = f"Kokonut Network Zones — {location_id}"

    for row in rows:
        placemark = SubElement(document, "Placemark")
        pm_name = SubElement(placemark, "name")
        pm_name.text = row[1]  # zone name

        description = SubElement(placemark, "description")
        description.text = f"Type: {row[2]}\nArea: {row[3]} m²\nStatus: {row[5]}"

        # Parse GeoJSON geometry to KML coordinates
        if row[6]:
            geom = json.loads(row[6])
            coords_text = _geojson_coords_to_kml(geom)
            if coords_text:
                polygon = SubElement(placemark, "Polygon")
                outer = SubElement(polygon, "outerBoundaryIs")
                ring = SubElement(outer, "LinearRing")
                coords = SubElement(ring, "coordinates")
                coords.text = coords_text

    xml_str = tostring(kml, encoding="unicode")
    pretty = parseString(xml_str).toprettyxml(indent="  ")
    # Remove extra XML declaration
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    result = "\n".join(lines)

    logger.info("Exported %d zones as KML for location %s", len(rows), location_id)
    return result


def export_project_xml(conn, location_id: str) -> str:
    """Export project summary as XML (for Silvi API integration)."""
    cur = conn.cursor()

    # Location info
    cur.execute(
        "SELECT name, latitude, longitude, status FROM location WHERE id = %s",
        (location_id,),
    )
    loc = cur.fetchone()

    # Tree count
    cur.execute(
        "SELECT COUNT(*) FROM tree_record WHERE location_id = %s AND status = 'alive'",
        (location_id,),
    )
    tree_count = cur.fetchone()[0]

    # Species count
    cur.execute(
        "SELECT COUNT(DISTINCT species_name) FROM tree_record WHERE location_id = %s AND status = 'alive'",
        (location_id,),
    )
    species_count = cur.fetchone()[0]

    # Zone count
    cur.execute(
        "SELECT COUNT(*) FROM farm_zone WHERE location_id = %s AND geometry IS NOT NULL",
        (location_id,),
    )
    zone_count = cur.fetchone()[0]

    # Zone types
    cur.execute(
        "SELECT DISTINCT zone_type FROM farm_zone WHERE location_id = %s",
        (location_id,),
    )
    zone_types = [r[0] for r in cur.fetchall()]

    # Tree species breakdown
    cur.execute(
        """
        SELECT species_name, species_common_name, COUNT(*) AS count
        FROM tree_record
        WHERE location_id = %s AND status = 'alive'
        GROUP BY species_name, species_common_name
        ORDER BY count DESC
        """,
        (location_id,),
    )
    species_data = cur.fetchall()

    cur.close()

    # Build XML
    project = Element("project")
    proj_id = SubElement(project, "id")
    proj_id.text = location_id

    proj_name = SubElement(project, "name")
    proj_name.text = loc[0] if loc else "Unknown"

    coords = SubElement(project, "coordinates")
    lat = SubElement(coords, "latitude")
    lat.text = str(float(loc[1])) if loc and loc[1] else "0"
    lon = SubElement(coords, "longitude")
    lon.text = str(float(loc[2])) if loc and loc[2] else "0"

    status = SubElement(project, "status")
    status.text = loc[3] if loc else "unknown"

    trees_el = SubElement(project, "trees")
    total = SubElement(trees_el, "total")
    total.text = str(tree_count)
    species_total = SubElement(trees_el, "species_count")
    species_total.text = str(species_count)

    species_list = SubElement(trees_el, "species")
    for sp_name, sp_common, sp_count in species_data:
        sp = SubElement(species_list, "species")
        sp_name_el = SubElement(sp, "name")
        sp_name_el.text = sp_name
        sp_common_el = SubElement(sp, "common_name")
        sp_common_el.text = sp_common or ""
        sp_count_el = SubElement(sp, "count")
        sp_count_el.text = str(sp_count)

    zones_el = SubElement(project, "zones")
    zone_total = SubElement(zones_el, "total")
    zone_total.text = str(zone_count)
    for zt in zone_types:
        zt_el = SubElement(zones_el, "type")
        zt_el.text = zt

    generated = SubElement(project, "generated_at")
    generated.text = datetime.now(timezone.utc).isoformat()

    xml_str = tostring(project, encoding="unicode")
    pretty = parseString(xml_str).toprettyxml(indent="  ")
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    result = "\n".join(lines)

    logger.info("Exported project XML for location %s", location_id)
    return result


def _geojson_coords_to_kml(geom: dict) -> str | None:
    """Convert GeoJSON coordinates to KML coordinate string (lon,lat,altitude)."""
    if not geom:
        return None

    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    if geom_type == "Polygon" and coords:
        # KML uses exterior ring only
        ring = coords[0]
        return " ".join(f"{c[0]},{c[1]},0" for c in ring)
    elif geom_type == "Point" and coords:
        return f"{coords[0]},{coords[1]},0"

    return None
