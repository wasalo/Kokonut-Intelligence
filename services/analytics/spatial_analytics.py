"""Spatial analytics: clustering, pest hotspots, canopy analysis."""

from __future__ import annotations

import math
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_spatial_clusters(conn, location_id: str) -> dict[str, Any]:
    """Retrieve and summarize spatial clusters for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, cluster_method, cluster_name, cluster_type,
               tree_count, avg_health_score, dominant_species, avg_height_m,
               compactness, eps_m, min_samples, centroid_geojson, hull_geojson, status
        FROM v_public_spatial_clusters
        WHERE location_id = %s
        ORDER BY tree_count DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    clusters = []
    for row in rows:
        clusters.append({
            "id": str(row[0]),
            "cluster_method": row[1],
            "cluster_name": row[2],
            "cluster_type": row[3],
            "tree_count": row[4],
            "avg_health_score": float(row[5]) if row[5] else None,
            "dominant_species": row[6],
            "avg_height_m": float(row[7]) if row[7] else None,
            "compactness": float(row[8]) if row[8] else None,
            "eps_m": float(row[9]) if row[9] else None,
            "min_samples": row[10],
            "centroid": row[11],
            "hull": row[12],
            "status": row[13],
        })

    total_trees_in_clusters = sum(c["tree_count"] for c in clusters)
    avg_health = (
        sum(c["avg_health_score"] * c["tree_count"] for c in clusters if c["avg_health_score"])
        / total_trees_in_clusters
        if total_trees_in_clusters > 0 else None
    )

    result = {
        "location_id": location_id,
        "total_clusters": len(clusters),
        "total_trees_in_clusters": total_trees_in_clusters,
        "avg_cluster_health": round(avg_health, 1) if avg_health else None,
        "clusters": clusters,
    }

    logger.info("Spatial clusters for %s: %d clusters, %d trees", location_id, len(clusters), total_trees_in_clusters)
    return result


def compute_pest_hotspots(conn, location_id: str) -> dict[str, Any]:
    """Retrieve and summarize pest hotspots for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, hotspot_name, pest_or_disease, tree_count_affected,
               avg_severity, radius_m, area_m2, confidence_score,
               detection_date, detection_method, recommended_action,
               status, centroid_geojson
        FROM v_public_pest_hotspots
        WHERE location_id = %s
        ORDER BY confidence_score DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    hotspots = []
    for row in rows:
        hotspots.append({
            "id": str(row[0]),
            "hotspot_name": row[1],
            "pest_or_disease": row[2],
            "tree_count_affected": row[3],
            "avg_severity": float(row[4]) if row[4] else None,
            "radius_m": float(row[5]) if row[5] else None,
            "area_m2": float(row[6]) if row[6] else None,
            "confidence_score": float(row[7]) if row[7] else None,
            "detection_date": str(row[8]) if row[8] else None,
            "detection_method": row[9],
            "recommended_action": row[10],
            "status": row[11],
            "centroid": row[12],
        })

    total_affected = sum(h["tree_count_affected"] for h in hotspots)
    active_hotspots = [h for h in hotspots if h["status"] == "active"]

    result = {
        "location_id": location_id,
        "total_hotspots": len(hotspots),
        "active_hotspots": len(active_hotspots),
        "total_trees_affected": total_affected,
        "hotspots": hotspots,
    }

    logger.info("Pest hotspots for %s: %d hotspots, %d trees affected", location_id, len(hotspots), total_affected)
    return result


def compute_canopy_analysis(conn, location_id: str) -> dict[str, Any]:
    """Compute canopy coverage analysis per zone."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT zone_id, zone_name, zone_type, zone_area_m2,
               alive_trees, avg_canopy_diameter_m, avg_crown_area_m2,
               estimated_canopy_cover_pct
        FROM v_public_canopy_analysis
        WHERE location_id = %s
        ORDER BY estimated_canopy_cover_pct DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    zones = []
    for row in rows:
        zones.append({
            "zone_id": str(row[0]),
            "zone_name": row[1],
            "zone_type": row[2],
            "zone_area_m2": float(row[3]) if row[3] else 0,
            "alive_trees": row[4],
            "avg_canopy_diameter_m": float(row[5]) if row[5] else None,
            "avg_crown_area_m2": float(row[6]) if row[6] else None,
            "estimated_canopy_cover_pct": float(row[7]) if row[7] else None,
        })

    total_area = sum(z["zone_area_m2"] for z in zones)
    weighted_cover = (
        sum(z["estimated_canopy_cover_pct"] * z["zone_area_m2"] for z in zones if z["estimated_canopy_cover_pct"])
        / total_area
        if total_area > 0 else None
    )

    result = {
        "location_id": location_id,
        "total_zones": len(zones),
        "total_area_m2": round(total_area, 2),
        "weighted_avg_canopy_cover_pct": round(weighted_cover, 1) if weighted_cover else None,
        "zones": zones,
    }

    logger.info("Canopy analysis for %s: %d zones, %.1f%% avg cover", location_id, len(zones), weighted_cover or 0)
    return result


def compute_gap_detection(conn, location_id: str) -> dict[str, Any]:
    """Detect gaps (missing trees or low-density areas) in the plantation.

    A gap is defined as a zone where the tree count is significantly below
    the expected density for the zone type.
    """
    cur = conn.cursor()

    # Expected density by zone type (trees per hectare)
    expected_density = {
        "syntropic_plot": 250,
        "agroforestry": 150,
        "nursery": 100,
        "biofactory": 50,
        "poultry": 0,
    }

    cur.execute(
        """
        SELECT t.zone_id, fz.zone_type, fz.name AS zone_name, fz.area_m2,
               COUNT(*) FILTER (WHERE t.status = 'alive') AS alive_trees
        FROM tree_record t
        JOIN farm_zone fz ON t.zone_id = fz.id
        WHERE t.location_id = %s AND fz.area_m2 IS NOT NULL
        GROUP BY t.zone_id, fz.zone_type, fz.name, fz.area_m2
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    gaps = []
    for row in rows:
        zone_id = str(row[0])
        zone_type = row[1]
        zone_name = row[2]
        area_m2 = float(row[3]) if row[3] else 0
        area_ha = area_m2 / 10000
        alive_trees = row[4] or 0
        actual_density = alive_trees / area_ha if area_ha > 0 else 0
        expected = expected_density.get(zone_type, 100)
        gap_pct = ((expected - actual_density) / expected * 100) if expected > 0 else 0

        if gap_pct > 20:  # More than 20% below expected density
            gaps.append({
                "zone_id": zone_id,
                "zone_name": zone_name,
                "zone_type": zone_type,
                "area_ha": round(area_ha, 4),
                "alive_trees": alive_trees,
                "actual_density_per_ha": round(actual_density, 1),
                "expected_density_per_ha": expected,
                "gap_pct": round(gap_pct, 1),
                "missing_trees_estimate": max(0, round((expected - actual_density) * area_ha)),
            })

    result = {
        "location_id": location_id,
        "total_zones_analyzed": len(rows),
        "zones_with_gaps": len(gaps),
        "gaps": sorted(gaps, key=lambda x: x["gap_pct"], reverse=True),
    }

    logger.info("Gap detection for %s: %d gaps found in %d zones", location_id, len(gaps), len(rows))
    return result
