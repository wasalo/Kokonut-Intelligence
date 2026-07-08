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


def compute_habitat_connectivity(conn, location_id: str) -> dict[str, Any]:
    """Compute habitat connectivity score for a location.

    Evaluates spatial relationships between habitat zones (agroforestry, syntropic_plot)
    to determine how well new plantings connect to existing forest patches.

    Connectivity score (0-100) is based on:
    - Number of habitat zones (more zones = more potential connections)
    - Average nearest-neighbor distance (shorter = better connected)
    - Canopy continuity (adjacent zones with overlapping crown projections)
    - Strata diversity across connected zones
    """
    cur = conn.cursor()

    # Get habitat zones with geometry
    cur.execute(
        """
        SELECT id, zone_key, name, zone_type, area_m2, strata_layer
        FROM farm_zone
        WHERE location_id = %s AND geometry IS NOT NULL
          AND zone_type IN ('agroforestry', 'syntropic_plot')
        """,
        (location_id,),
    )
    habitat_zones = cur.fetchall()

    # Get all zones
    cur.execute(
        """
        SELECT id, zone_key, name, zone_type, area_m2, strata_layer
        FROM farm_zone
        WHERE location_id = %s AND geometry IS NOT NULL
        """,
        (location_id,),
    )
    all_zones = cur.fetchall()

    if len(habitat_zones) < 1:
        cur.close()
        return {
            "location_id": location_id,
            "connectivity_score": 0,
            "connectivity_status": "no_habitat_zones",
            "habitat_zone_count": 0,
            "nearest_neighbor_m": None,
            "message": "No habitat zones (agroforestry or syntropic_plot) found",
        }

    # Compute pairwise distances between habitat zones
    cur.execute(
        """
        SELECT
            a.id AS zone_a_id, a.name AS zone_a_name, a.zone_type AS zone_a_type,
            a.area_m2 AS zone_a_area_m2, a.strata_layer AS zone_a_strata,
            b.id AS zone_b_id, b.name AS zone_b_name, b.zone_type AS zone_b_type,
            b.area_m2 AS zone_b_area_m2, b.strata_layer AS zone_b_strata,
            ROUND(ST_Distance(a.geometry::geography, b.geometry::geography)::numeric, 2) AS distance_m
        FROM farm_zone a
        JOIN farm_zone b ON a.id < b.id
        WHERE a.location_id = %s
          AND a.geometry IS NOT NULL AND b.geometry IS NOT NULL
          AND a.zone_type IN ('agroforestry', 'syntropic_plot')
          AND b.zone_type IN ('agroforestry', 'syntropic_plot')
        ORDER BY distance_m
        """,
        (location_id,),
    )
    pairs = cur.fetchall()
    cur.close()

    # Compute nearest neighbor for each habitat zone
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT ON (a.id)
            a.id AS zone_id, a.name AS zone_name, a.zone_type,
            b.name AS nearest_name, b.zone_type AS nearest_type,
            ROUND(ST_Distance(a.geometry::geography, b.geometry::geography)::numeric, 2) AS distance_m
        FROM farm_zone a
        JOIN farm_zone b ON a.id != b.id
        WHERE a.location_id = %s
          AND a.geometry IS NOT NULL AND b.geometry IS NOT NULL
          AND a.zone_type IN ('agroforestry', 'syntropic_plot')
          AND b.zone_type IN ('agroforestry', 'syntropic_plot')
        ORDER BY a.id, ST_Distance(a.geometry::geography, b.geometry::geography)
        """,
        (location_id,),
    )
    nearest_neighbors = cur.fetchall()
    cur.close()

    # Compute connectivity score components
    habitat_count = len(habitat_zones)
    total_habitat_area_ha = sum(float(z[4]) / 10000 for z in habitat_zones if z[4])
    strata_in_habitat = set(z[5] for z in habitat_zones if z[5])

    # Nearest neighbor distances
    nn_distances = [float(nn[5]) for nn in nearest_neighbors if nn[5] is not None]
    avg_nn_distance = sum(nn_distances) / len(nn_distances) if nn_distances else 999
    min_nn_distance = min(nn_distances) if nn_distances else 999

    # Pair distances
    pair_distances = [float(p[10]) for p in pairs if p[10] is not None]
    adjacent_pairs = sum(1 for d in pair_distances if d <= 10)
    nearby_pairs = sum(1 for d in pair_distances if d <= 50)

    # Score components (each 0-25, total 0-100)
    # 1. Habitat zone count (more zones = better, max at 5)
    count_score = min(25, habitat_count * 5)

    # 2. Nearest neighbor distance (shorter = better, 0m=25, 100m+=0)
    if avg_nn_distance <= 10:
        distance_score = 25
    elif avg_nn_distance <= 50:
        distance_score = 25 - ((avg_nn_distance - 10) / 40) * 15
    elif avg_nn_distance <= 200:
        distance_score = 10 - ((avg_nn_distance - 50) / 150) * 10
    else:
        distance_score = 0

    # 3. Adjacency (more adjacent pairs = better)
    adjacency_score = min(25, adjacent_pairs * 10 + nearby_pairs * 3)

    # 4. Strata diversity (more vertical layers = better connectivity)
    strata_score = min(25, len(strata_in_habitat) * 6)

    connectivity_score = round(count_score + distance_score + adjacency_score + strata_score, 1)
    connectivity_score = min(100, max(0, connectivity_score))

    # Determine status
    if connectivity_score >= 75:
        status = "highly_connected"
    elif connectivity_score >= 50:
        status = "connected"
    elif connectivity_score >= 25:
        status = "moderately_connected"
    else:
        status = "fragmented"

    # Build pair details
    pair_details = []
    for p in pairs:
        pair_details.append({
            "zone_a": p[1],
            "zone_a_type": p[2],
            "zone_b": p[7],
            "zone_b_type": p[8],
            "distance_m": float(p[10]) if p[10] else None,
            "proximity": "adjacent" if float(p[10]) <= 10 else "nearby" if float(p[10]) <= 50 else "separated",
        })

    result = {
        "location_id": location_id,
        "connectivity_score": connectivity_score,
        "connectivity_status": status,
        "habitat_zone_count": habitat_count,
        "total_habitat_area_ha": round(total_habitat_area_ha, 4),
        "strata_represented": sorted(strata_in_habitat),
        "avg_nearest_neighbor_m": round(avg_nn_distance, 2),
        "min_nearest_neighbor_m": round(min_nn_distance, 2),
        "adjacent_pairs": adjacent_pairs,
        "nearby_pairs": nearby_pairs,
        "total_pairs": len(pairs),
        "score_breakdown": {
            "zone_count": round(count_score, 1),
            "nearest_neighbor": round(distance_score, 1),
            "adjacency": round(adjacency_score, 1),
            "strata_diversity": round(strata_score, 1),
        },
        "pairs": pair_details,
    }

    logger.info("Habitat connectivity for %s: score=%.1f, status=%s, %d habitat zones",
                location_id, connectivity_score, status, habitat_count)
    return result
