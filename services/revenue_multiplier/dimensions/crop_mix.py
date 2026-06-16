"""
Crop Mix Optimization — Dimension 1

Analyzes NOI per hectare by crop, recommends reallocation based on
soil type, water availability, and market prices.
"""

import psycopg2.extras
from ..models import OpportunityDimension


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get crop cycles with revenue and costs
    cur.execute("""
        SELECT
            c.name as crop_name,
            cc.id as cycle_id,
            cc.area_planted,
            cc.actual_yield,
            cc.actual_revenue,
            p.name as plot_name,
            p.soil_type,
            p.water_source
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s AND cc.status = 'completed'
    """, (location_id,))
    cycles = [dict(r) for r in cur.fetchall()]

    # Get NOI snapshots
    cur.execute("""
        SELECT ns.*, c.name as crop_name
        FROM noi_snapshot ns
        JOIN crop_cycle cc ON ns.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE ns.location_id = %s
    """, (location_id,))
    noi_data = [dict(r) for r in cur.fetchall()]

    # Get price observations
    cur.execute("""
        SELECT c.name as crop_name, po.price_per_unit, po.market_name
        FROM price_observation po
        JOIN crop c ON po.crop_id = c.id
        ORDER BY po.price_date DESC
    """)
    prices = [dict(r) for r in cur.fetchall()]

    # Get forecast projections for forward-looking analysis
    cur.execute("""
        SELECT metric_name, inputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name IN ('projected_revenue_usd', 'projected_noi_usd')
        ORDER BY created_at DESC LIMIT 2
    """, (location_id,))
    forecasts = {r["metric_name"]: r["inputs"] for r in cur.fetchall()}

    cur.close()

    if not cycles:
        return _empty("crop_mix_optimization", "Crop Mix Optimization")

    # Calculate revenue per hectare by crop
    crop_metrics = {}
    for cycle in cycles:
        crop = cycle["crop_name"]
        area = float(cycle["area_planted"] or 0)
        revenue = float(cycle["actual_revenue"] or 0)
        if area > 0:
            if crop not in crop_metrics:
                crop_metrics[crop] = {"total_revenue": 0, "total_area": 0, "count": 0}
            crop_metrics[crop]["total_revenue"] += revenue
            crop_metrics[crop]["total_area"] += area
            crop_metrics[crop]["count"] += 1

    # Calculate NOI per hectare
    noi_per_ha = {}
    for noi in noi_data:
        crop = noi["crop_name"]
        area = float(cycles[0]["area_planted"] or 1) if cycles else 1
        noi_val = float(noi["noi"] or 0)
        if crop not in noi_per_ha:
            noi_per_ha[crop] = []
        noi_per_ha[crop].append(noi_val / max(area, 0.01))

    # Find best and worst crops
    avg_noi_per_ha = {c: sum(v)/len(v) for c, v in noi_per_ha.items()}
    if not avg_noi_per_ha:
        return _empty("crop_mix_optimization", "Crop Mix Optimization")

    best_crop = max(avg_noi_per_ha, key=avg_noi_per_ha.get)
    worst_crop = min(avg_noi_per_ha, key=avg_noi_per_ha.get)
    best_noi = avg_noi_per_ha[best_crop]
    worst_noi = avg_noi_per_ha[worst_crop]

    # Score: higher if there's a big gap between best and worst
    gap = best_noi - worst_noi
    score = min(100, max(0, gap / 10))  # $10/ha gap = 10 points

    # Estimate impact: reallocating worst crop area to best crop
    worst_area = crop_metrics.get(worst_crop, {}).get("total_area", 0)
    impact = gap * worst_area

    # Enrich with forecast projections if available
    projected_revenue_by_crop = {}
    projected_noi_by_crop = {}
    if "projected_revenue_usd" in forecasts:
        inputs = forecasts["projected_revenue_usd"]
        if isinstance(inputs, dict):
            projected_revenue_by_crop = inputs.get("revenue_by_crop", {})
    if "projected_noi_usd" in forecasts:
        inputs = forecasts["projected_noi_usd"]
        if isinstance(inputs, dict):
            projected_noi_by_crop = inputs.get("noi_by_crop", {})

    # Price trends
    price_by_crop = {}
    for p in prices:
        crop = p["crop_name"]
        if crop not in price_by_crop:
            price_by_crop[crop] = []
        price_by_crop[crop].append(float(p["price_per_unit"]))

    details = {
        "revenue_per_ha": {c: round(m["total_revenue"] / max(m["total_area"], 0.01), 2) for c, m in crop_metrics.items()},
        "noi_per_ha": {c: round(v, 2) for c, v in avg_noi_per_ha.items()},
        "best_crop": best_crop,
        "worst_crop": worst_crop,
        "price_trends": {c: {"latest": v[0] if v else 0, "count": len(v)} for c, v in price_by_crop.items()},
        "projected_revenue_by_crop": projected_revenue_by_crop,
        "projected_noi_by_crop": projected_noi_by_crop,
    }

    return OpportunityDimension(
        dimension_id="crop_mix_optimization",
        dimension_name="Crop Mix Optimization",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if len(cycles) >= 4 else "medium",
        current_state=f"4 crops, best={best_crop} (${best_noi:.0f}/ha), worst={worst_crop} (${worst_noi:.0f}/ha)",
        recommendation=f"Shift {worst_area:.1f}ha from {worst_crop} to {best_crop} for +${impact:,.0f}/year",
        data_points=len(cycles),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No crop cycle data", recommendation="Complete crop cycles first",
        data_points=0,
    )
