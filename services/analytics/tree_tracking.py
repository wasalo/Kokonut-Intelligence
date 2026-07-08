"""Tree tracking analytics: density, growth rate, species richness."""

from __future__ import annotations

import math
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_tree_density(conn, location_id: str) -> dict[str, Any]:
    """Compute tree density per hectare per plot and overall.

    Returns per-plot density, species breakdown, and overall metrics.
    """
    cur = conn.cursor()

    # Per-plot density
    cur.execute(
        """
        SELECT t.plot_id, p.name AS plot_name, p.area_ha,
               COUNT(*) AS total_trees,
               COUNT(*) FILTER (WHERE t.status = 'alive') AS alive_trees,
               COUNT(*) FILTER (WHERE t.status = 'dead') AS dead_trees,
               COUNT(DISTINCT t.species_name) AS species_count
        FROM tree_record t
        JOIN plot p ON t.plot_id = p.id
        WHERE t.location_id = %s
        GROUP BY t.plot_id, p.name, p.area_ha
        ORDER BY p.name
        """,
        (location_id,),
    )
    plots = []
    for row in cur.fetchall():
        area_ha = float(row[2]) if row[2] else 0
        alive = row[4] or 0
        density = round(alive / area_ha, 2) if area_ha > 0 else 0
        plots.append({
            "plot_id": str(row[0]),
            "plot_name": row[1],
            "area_ha": area_ha,
            "total_trees": row[3],
            "alive_trees": alive,
            "dead_trees": row[5] or 0,
            "species_count": row[6],
            "trees_per_ha": density,
        })

    # Per-species summary
    cur.execute(
        """
        SELECT species_name, species_common_name,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'alive') AS alive,
               AVG(height_m) AS avg_height,
               AVG(canopy_diameter_m) AS avg_canopy,
               AVG(health_score) AS avg_health
        FROM tree_record
        WHERE location_id = %s
        GROUP BY species_name, species_common_name
        ORDER BY total DESC
        """,
        (location_id,),
    )
    species = [
        {
            "species_name": r[0],
            "species_common_name": r[1],
            "total_trees": r[2],
            "alive_trees": r[3],
            "avg_height_m": round(float(r[4]), 2) if r[4] else None,
            "avg_canopy_diameter_m": round(float(r[5]), 2) if r[5] else None,
            "avg_health_score": round(float(r[6]), 1) if r[6] else None,
        }
        for r in cur.fetchall()
    ]

    # Overall totals
    total_alive = sum(p["alive_trees"] for p in plots)
    total_area = sum(p["area_ha"] for p in plots)
    overall_density = round(total_alive / total_area, 2) if total_area > 0 else 0

    cur.close()

    result = {
        "location_id": location_id,
        "total_trees": sum(p["total_trees"] for p in plots),
        "total_alive": total_alive,
        "total_area_ha": round(total_area, 4),
        "overall_density_per_ha": overall_density,
        "total_species": len(species),
        "plots": plots,
        "species": species,
    }

    logger.info("Tree density for %s: %d alive trees, %.2f trees/ha", location_id, total_alive, overall_density)
    return result


def compute_growth_rate(conn, location_id: str) -> dict[str, Any]:
    """Compute growth rate per tree from successive measurements.

    Returns height growth rate (m/year) and canopy growth rate (m/year) for trees with 2+ measurements.
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT t.id, t.tree_tag, t.species_name, t.species_common_name,
               t.planting_date, t.maturity_stage, t.status
        FROM tree_record t
        WHERE t.location_id = %s AND t.status = 'alive'
        ORDER BY t.tree_tag
        """,
        (location_id,),
    )
    trees = cur.fetchall()

    growth_data = []
    for tree in trees:
        tree_id = tree[0]
        cur.execute(
            """
            SELECT measurement_date, height_m, dbh_cm, canopy_diameter_m, health_score
            FROM tree_measurement
            WHERE tree_record_id = %s
            ORDER BY measurement_date ASC
            """,
            (tree_id,),
        )
        measurements = cur.fetchall()

        if len(measurements) < 2:
            growth_data.append({
                "tree_id": str(tree_id),
                "tree_tag": tree[1],
                "species_name": tree[2],
                "species_common_name": tree[3],
                "maturity_stage": tree[5],
                "measurement_count": len(measurements),
                "height_growth_m_per_year": None,
                "canopy_growth_m_per_year": None,
                "dbh_growth_cm_per_year": None,
                "health_trend": None,
            })
            continue

        first = measurements[0]
        last = measurements[-1]
        days = (last[0] - first[0]).days
        years = days / 365.25 if days > 0 else 0

        height_delta = (float(last[1]) - float(first[1])) if first[1] and last[1] else None
        canopy_delta = (float(last[3]) - float(first[3])) if first[3] and last[3] else None
        dbh_delta = (float(last[2]) - float(first[2])) if first[2] and last[2] else None
        health_delta = (float(last[4]) - float(first[4])) if first[4] and last[4] else None

        height_rate = round(height_delta / years, 3) if height_delta is not None and years > 0 else None
        canopy_rate = round(canopy_delta / years, 3) if canopy_delta is not None and years > 0 else None
        dbh_rate = round(dbh_delta / years, 3) if dbh_delta is not None and years > 0 else None

        if health_delta is not None:
            health_trend = "improving" if health_delta > 2 else "declining" if health_delta < -2 else "stable"
        else:
            health_trend = None

        growth_data.append({
            "tree_id": str(tree_id),
            "tree_tag": tree[1],
            "species_name": tree[2],
            "species_common_name": tree[3],
            "maturity_stage": tree[5],
            "measurement_count": len(measurements),
            "first_measurement": str(first[0]),
            "last_measurement": str(last[0]),
            "measurement_period_days": days,
            "height_growth_m_per_year": height_rate,
            "canopy_growth_m_per_year": canopy_rate,
            "dbh_growth_cm_per_year": dbh_rate,
            "health_trend": health_trend,
        })

    # Summary stats
    trees_with_growth = [g for g in growth_data if g["height_growth_m_per_year"] is not None]
    avg_height_rate = (
        sum(g["height_growth_m_per_year"] for g in trees_with_growth) / len(trees_with_growth)
        if trees_with_growth else None
    )
    avg_canopy_rate = (
        sum(g["canopy_growth_m_per_year"] for g in trees_with_growth if g["canopy_growth_m_per_year"] is not None)
        / len([g for g in trees_with_growth if g["canopy_growth_m_per_year"] is not None])
        if any(g["canopy_growth_m_per_year"] for g in trees_with_growth) else None
    )

    cur.close()

    result = {
        "location_id": location_id,
        "total_trees_tracked": len(trees),
        "trees_with_measurements": len(trees_with_growth),
        "avg_height_growth_m_per_year": round(avg_height_rate, 3) if avg_height_rate is not None else None,
        "avg_canopy_growth_m_per_year": round(avg_canopy_rate, 3) if avg_canopy_rate is not None else None,
        "trees": growth_data,
    }

    logger.info("Growth rate for %s: %d trees tracked, avg height growth %.3f m/yr",
                location_id, len(trees), avg_height_rate or 0)
    return result


def compute_species_richness(conn, location_id: str) -> dict[str, Any]:
    """Compute Shannon and Simpson diversity indices from individual tree records.

    Returns species counts, Shannon H', Simpson D, and evenness.
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT species_name, COUNT(*) AS count
        FROM tree_record
        WHERE location_id = %s AND status = 'alive'
        GROUP BY species_name
        ORDER BY count DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    total = sum(r[1] for r in rows)
    species_count = len(rows)

    if total == 0 or species_count == 0:
        return {
            "location_id": location_id,
            "total_trees": 0,
            "species_count": 0,
            "shannon_index": 0,
            "simpson_index": 0,
            "evenness": 0,
            "species": [],
        }

    # Shannon H' = -sum(p_i * ln(p_i))
    shannon = 0.0
    # Simpson D = 1 - sum(p_i^2)
    simpson_sum = 0.0

    species = []
    for name, count in rows:
        p = count / total
        shannon -= p * math.log(p) if p > 0 else 0
        simpson_sum += p * p
        species.append({
            "species_name": name,
            "count": count,
            "proportion": round(p, 4),
        })

    simpson = 1 - simpson_sum
    # Evenness J = H' / ln(S)
    evenness = shannon / math.log(species_count) if species_count > 1 else 0

    result = {
        "location_id": location_id,
        "total_trees": total,
        "species_count": species_count,
        "shannon_index": round(shannon, 4),
        "simpson_index": round(simpson, 4),
        "evenness": round(evenness, 4),
        "species": species,
    }

    logger.info("Species richness for %s: %d species, Shannon=%.4f, Simpson=%.4f",
                location_id, species_count, shannon, simpson)
    return result
