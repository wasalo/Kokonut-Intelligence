"""
Regional Farm Clusters — Dimension 10

Evaluates proximity to other farms and shared infrastructure.
Analyzes cluster density, infrastructure sharing, and collective bargaining.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get nearby locations (within 50km)
    cur.execute("""
        SELECT
            l.id,
            l.name,
            l.latitude,
            l.longitude,
            ST_Distance(
                ST_SetSRID(ST_MakePoint(l.longitude, l.latitude), 4326)::geography,
                ST_SetSRID(ST_MakePoint(
                    (SELECT longitude FROM location WHERE id = %s),
                    (SELECT latitude FROM location WHERE id = %s)
                ), 4326)::geography
            ) / 1000 as distance_km
        FROM location l
        WHERE l.id != %s
          AND l.latitude IS NOT NULL
          AND l.longitude IS NOT NULL
        HAVING ST_Distance(
            ST_SetSRID(ST_MakePoint(l.longitude, l.latitude), 4326)::geography,
            ST_SetSRID(ST_MakePoint(
                (SELECT longitude FROM location WHERE id = %s),
                (SELECT latitude FROM location WHERE id = %s)
            ), 4326)::geography
        ) / 1000 <= 50
        ORDER BY distance_km
    """, (location_id, location_id, location_id, location_id, location_id))
    nearby = [dict(r) for r in cur.fetchall()]

    # Get shared infrastructure
    cur.execute("""
        SELECT
            sr.resource_type,
            sr.capacity,
            COUNT(sru.id) as usage_count
        FROM shared_resource sr
        LEFT JOIN shared_resource_usage sru ON sr.id = sru.shared_resource_id
        WHERE sr.owner_location_id = %s
        GROUP BY sr.id, sr.resource_type, sr.capacity
    """, (location_id,))
    infrastructure = [dict(r) for r in cur.fetchall()]

    # Get forecast: projected revenue (for collective bargaining estimate)
    cur.execute("""
        SELECT metric_name, outputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'projected_revenue_usd'
        ORDER BY created_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_revenue = 0
    if forecast_row:
        outputs = dict(forecast_row)["outputs"] or {}
        forecast_revenue = float(outputs.get("projected_revenue_usd", 0) or 0)

    cur.close()

    # Config constants
    nearby_multiplier = float(get_config(conn, 'regional_nearby_multiplier'))
    farm_multiplier = float(get_config(conn, 'regional_farm_multiplier'))
    ha_per_nearby = float(get_config(conn, 'regional_ha_per_nearby'))

    # Score: based on proximity and infrastructure sharing
    score = min(100, max(0, len(nearby) * nearby_multiplier))

    # Bonus for shared infrastructure
    if infrastructure:
        total_sharing = sum(i["usage_count"] for i in infrastructure)
        score = min(100, score + total_sharing * farm_multiplier)

    # Impact: collective bargaining and infrastructure sharing
    # Estimate total hectares in cluster
    cluster_ha = len(nearby) * ha_per_nearby + 1  # +1 for this farm

    # Collective price improvement (rough: $20/ha for bulk purchasing)
    collective_bargaining = cluster_ha * 20

    # Infrastructure sharing savings
    infra_sharing = sum(float(i["capacity"] or 0) * 10 for i in infrastructure)  # $10 per unit capacity

    impact = collective_bargaining + infra_sharing

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_revenue > 0 and len(nearby) > 0:
        bulk_discount = forecast_revenue * 0.02  # 2% bulk discount
        forecast_impact = bulk_discount

    details = {
        "nearby_farm_count": len(nearby),
        "nearest_farm_km": round(nearby[0]["distance_km"], 1) if nearby else None,
        "cluster_ha_estimate": round(cluster_ha, 0),
        "shared_infrastructure": len(infrastructure),
        "infrastructure_types": [i["resource_type"] for i in infrastructure],
        "total_sharing_uses": sum(i["usage_count"] for i in infrastructure),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="regional_farm_clusters",
        dimension_name="Regional Farm Clusters",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if nearby else "medium",
        current_state=f"{len(nearby)} nearby farms, {len(infrastructure)} shared resources",
        recommendation=f"Coordinate with {len(nearby)} nearby farms for +${impact:,.0f}/year collective value" if impact > 0 else "Map nearby farms for clustering",
        data_points=len(nearby) + len(infrastructure),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No location data", recommendation="Set GPS coordinates for proximity analysis",
        data_points=0,
    )
