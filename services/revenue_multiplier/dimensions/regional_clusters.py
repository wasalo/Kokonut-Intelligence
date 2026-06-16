"""
Regional Farm Clusters — Dimension 10

Analyzes cluster proximity, shared infrastructure opportunities,
and regional benchmarks.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get location info
    cur.execute("""
        SELECT id, name, region, sub_region, country, latitude, longitude
        FROM location WHERE id = %s
    """, (location_id,))
    loc = dict(cur.fetchone()) if cur.rowcount else {}

    # Get nearby locations (same region)
    if loc.get("region"):
        cur.execute("""
            SELECT id, name, region, sub_region
            FROM location
            WHERE region = %s AND id != %s
        """, (loc["region"], location_id))
        nearby = [dict(r) for r in cur.fetchall()]
    else:
        nearby = []

    # Get farms in the location
    cur.execute("""
        SELECT id, name, total_area, farm_type
        FROM farm WHERE location_id = %s
    """, (location_id,))
    farms = [dict(r) for r in cur.fetchall()]

    # Get infrastructure assets
    cur.execute("""
        SELECT name, asset_type, capacity, capacity_unit
        FROM infrastructure_asset
        WHERE location_id = %s
    """, (location_id,))
    infra = [dict(r) for r in cur.fetchall()]

    # Get shared cost allocations
    cur.execute("""
        SELECT allocation_method, SUM(allocated_amount) as total
        FROM crop_cost_allocation
        WHERE crop_cycle_id IN (
            SELECT id FROM crop_cycle WHERE location_id = %s
        )
        GROUP BY allocation_method
    """, (location_id,))
    allocations = [dict(r) for r in cur.fetchall()]

    cur.close()

    # Score: more farms nearby = higher cluster potential
    nearby_count = len(nearby)
    farm_count = len(farms)
    total_area = sum(float(f["total_area"] or 0) for f in farms)

    score = min(100, nearby_count * 20 + farm_count * 10)

    # Impact: shared infrastructure savings
    shared_savings_per_ha = float(get_config(conn, 'shared_savings_per_ha_usd'))
    cluster_area = total_area + sum(10 for _ in nearby)  # Estimate 10ha per nearby location
    impact = cluster_area * shared_savings_per_ha

    details = {
        "location_name": loc.get("name"),
        "region": loc.get("region"),
        "nearby_locations": nearby_count,
        "farm_count": farm_count,
        "total_area_ha": round(total_area, 2),
        "infrastructure": [i["name"] for i in infra],
        "cost_allocation_methods": [a["allocation_method"] for a in allocations],
    }

    return OpportunityDimension(
        dimension_id="regional_farm_clusters",
        dimension_name="Regional Farm Clusters",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="low" if nearby_count == 0 else "medium",
        current_state=f"{farm_count} farm(s), {nearby_count} nearby locations, {total_area:.1f}ha total",
        recommendation=f"Form cluster with {nearby_count} nearby farms for ${impact:,.0f} shared savings",
        data_points=farm_count + nearby_count,
        details=details,
    )
