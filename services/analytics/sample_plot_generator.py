"""Sample plot generation: statistically valid plot designs for forest monitoring."""

from __future__ import annotations

import math
import random
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_optimal_plot_count(zone_area_ha: float, confidence_pct: float = 95.0, variance_pct: float = 30.0) -> int:
    """Compute optimal number of sample plots using Cochran's formula.

    n = (Z^2 * p * (1-p)) / E^2
    where Z = z-score for confidence level, p = estimated proportion, E = margin of error.

    Returns minimum 1 plot.
    """
    # Z-scores for common confidence levels
    z_scores = {90: 1.645, 95: 1.96, 99: 2.576}
    z = z_scores.get(confidence_pct, 1.96)

    # Use 0.5 for maximum variance (conservative)
    p = 0.5
    e = variance_pct / 100.0

    n = (z ** 2 * p * (1 - p)) / (e ** 2)

    # Adjust for finite population (zone area in hectares)
    # Assume each plot covers ~100 m2 = 0.01 ha
    plot_area_ha = 0.01
    population = zone_area_ha / plot_area_ha if zone_area_ha > 0 else 1000

    if population > 0:
        n = n / (1 + (n - 1) / population)

    return max(1, round(n))


def generate_sample_plots(
    conn,
    zone_id: str,
    location_id: str,
    design_id: str,
    method: str = "stratified_random",
    target_count: int | None = None,
    plot_area_m2: float = 100.0,
    min_distance_m: float = 10.0,
) -> dict[str, Any]:
    """Generate sample plot centers within a farm zone.

    Uses PostGIS ST_RandomPoint for random placement within zone geometry,
    filtered by minimum distance between plots.
    """
    cur = conn.cursor()

    # Get zone geometry and area
    cur.execute(
        """
        SELECT id, area_m2, ST_AsGeoJSON(geometry, 6) AS geojson
        FROM farm_zone
        WHERE id = %s AND geometry IS NOT NULL
        """,
        (zone_id,),
    )
    zone = cur.fetchone()
    if not zone:
        cur.close()
        return {"error": "Zone not found or has no geometry", "plots": []}

    zone_area_m2 = float(zone[1]) if zone[1] else 0
    zone_area_ha = zone_area_m2 / 10000

    # Compute target count if not provided
    if target_count is None:
        target_count = compute_optimal_plot_count(zone_area_ha)
        target_count = max(target_count, min(10, max(1, int(zone_area_ha * 10))))

    radius_m = math.sqrt(plot_area_m2 / math.pi)

    # Generate candidate points using PostGIS
    cur.execute(
        """
        SELECT ST_X(pt) AS longitude, ST_Y(pt) AS latitude
        FROM (
            SELECT (ST_DumpPoints(
                ST_GeneratePoints(geometry, %s)
            )).geom AS pt
            FROM farm_zone
            WHERE id = %s
        ) sub
        """,
        (target_count * 10, zone_id),  # Generate extra candidates
    )
    candidates = cur.fetchall()

    if not candidates:
        cur.close()
        return {"error": "Could not generate points within zone geometry", "plots": []}

    # Filter by minimum distance (greedy selection)
    selected: list[tuple[float, float]] = []
    for lon, lat in candidates:
        if len(selected) >= target_count:
            break
        too_close = False
        for sel_lon, sel_lat in selected:
            dist = _haversine_m(lat, lon, sel_lat, sel_lon)
            if dist < min_distance_m:
                too_close = True
                break
        if not too_close:
            selected.append((lon, lat))

    # If we don't have enough, relax distance constraint
    if len(selected) < target_count:
        for lon, lat in candidates:
            if len(selected) >= target_count:
                break
            if (lon, lat) not in selected:
                selected.append((lon, lat))

    # Assign strata based on existing tree density in zone
    strata = _assign_strata(cur, zone_id, selected)

    # Insert plots
    plots = []
    for i, (lon, lat) in enumerate(selected[:target_count]):
        plot_number = i + 1
        plot_label = f"SP-{plot_number:03d}"
        stratum = strata[i] if i < len(strata) else "default"

        cur.execute(
            """
            INSERT INTO sample_plot
                (design_id, zone_id, location_id, plot_number, plot_label,
                 center_latitude, center_longitude, plot_area_m2, radius_m, stratum,
                 source_system, source_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sample_plot_generator', %s)
            RETURNING id
            """,
            (design_id, zone_id, location_id, plot_number, plot_label,
             lat, lon, plot_area_m2, radius_m, stratum,
             f"sp-{zone_id[:8]}-{plot_number:03d}"),
        )
        plot_id = str(cur.fetchone()[0])
        plots.append({
            "plot_id": plot_id,
            "plot_number": plot_number,
            "plot_label": plot_label,
            "latitude": float(lat),
            "longitude": float(lon),
            "plot_area_m2": plot_area_m2,
            "radius_m": radius_m,
            "stratum": stratum,
        })

    # Update design with generated count
    cur.execute(
        "UPDATE sample_plot_design SET generated_plot_count = %s WHERE id = %s",
        (len(plots), design_id),
    )

    cur.close()

    logger.info("Generated %d sample plots for zone %s (target: %d)", len(plots), zone_id, target_count)
    return {
        "zone_id": zone_id,
        "design_id": design_id,
        "target_count": target_count,
        "generated_count": len(plots),
        "zone_area_m2": zone_area_m2,
        "zone_area_ha": zone_area_ha,
        "plot_area_m2": plot_area_m2,
        "radius_m": radius_m,
        "method": method,
        "plots": plots,
    }


def _assign_strata(cur, zone_id: str, points: list[tuple[float, float]]) -> list[str]:
    """Assign strata to points based on nearest existing tree species."""
    cur.execute(
        """
        SELECT DISTINCT ON (t.species_name)
            t.species_name, ST_X(t.point_geometry) AS lon, ST_Y(t.point_geometry) AS lat
        FROM tree_record t
        WHERE t.zone_id = %s AND t.status = 'alive'
        """,
        (zone_id,),
    )
    species = cur.fetchall()

    if not species:
        return ["default"] * len(points)

    strata = []
    for lon, lat in points:
        min_dist = float("inf")
        nearest = "default"
        for sp_name, sp_lon, sp_lat in species:
            dist = _haversine_m(lat, lon, sp_lat, sp_lon)
            if dist < min_dist:
                min_dist = dist
                nearest = sp_name
        strata.append(nearest)

    return strata


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_plot_summary(conn, design_id: str) -> dict[str, Any]:
    """Get summary of a sample plot design with its plots."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT spd.design_name, spd.sampling_method, spd.target_plot_count,
               spd.generated_plot_count, spd.zone_area_ha, spd.confidence_level,
               fz.name AS zone_name, fz.zone_type
        FROM sample_plot_design spd
        JOIN farm_zone fz ON spd.zone_id = fz.id
        WHERE spd.id = %s
        """,
        (design_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Design not found"}

    cur.execute(
        """
        SELECT plot_number, plot_label, center_latitude, center_longitude,
               plot_area_m2, radius_m, stratum
        FROM sample_plot
        WHERE design_id = %s
        ORDER BY plot_number
        """,
        (design_id,),
    )
    plots = [
        {
            "plot_number": r[0],
            "plot_label": r[1],
            "latitude": float(r[2]),
            "longitude": float(r[3]),
            "plot_area_m2": float(r[4]) if r[4] else None,
            "radius_m": float(r[5]) if r[5] else None,
            "stratum": r[6],
        }
        for r in cur.fetchall()
    ]
    cur.close()

    return {
        "design_id": design_id,
        "design_name": row[0],
        "sampling_method": row[1],
        "target_plot_count": row[2],
        "generated_plot_count": row[3],
        "zone_area_ha": float(row[4]) if row[4] else None,
        "confidence_level": float(row[5]) if row[5] else None,
        "zone_name": row[6],
        "zone_type": row[7],
        "plots": plots,
    }
