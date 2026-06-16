"""
Yield Forecasting Module

Projects crop yields based on historical data and scenario assumptions.
"""

from typing import Dict, Any, List
from .models import YieldAssumptions, CropArea, GrowthAssumptions


def get_crop_areas_for_location(location_id: str) -> List[Dict[str, Any]]:
    """Get current crop areas and expected yields for a location."""
    from ..ingestion.base import get_db
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT c.name, c.id, cc.id as cycle_id, cc.area_planted,
                   cc.expected_yield, cc.expected_yield_unit
            FROM crop_cycle cc
            JOIN crop c ON cc.crop_id = c.id
            WHERE cc.location_id = %s AND cc.status = 'completed'
        """, (location_id,))
        rows = cur.fetchall()
    db.close()
    return [
        {"crop_name": r[0], "crop_id": r[1], "cycle_id": str(r[2]),
         "area": float(r[3] or 0), "yield": float(r[4] or 0), "unit": r[5]}
        for r in rows
    ]


def project_yields(
    crop_areas: List[Dict[str, Any]],
    yield_assumptions: YieldAssumptions,
    growth: GrowthAssumptions,
) -> Dict[str, Dict[str, float]]:
    """Project yields per crop for next period."""
    yield_map = {
        "Maize": yield_assumptions.maize_yield_tonne_ha,
        "Cassava": yield_assumptions.cassava_yield_tonne_ha,
        "Beans": yield_assumptions.beans_yield_tonne_ha,
        "Sweet Potato": yield_assumptions.sweet_potato_yield_tonne_ha,
    }

    results = {}
    seen_crops = set()
    for ca in crop_areas:
        name = ca["crop_name"]
        if name in seen_crops:
            continue
        seen_crops.add(name)

        base_yield = yield_map.get(name, ca.get("yield", 0) / max(ca.get("area", 1), 1))
        area = ca.get("area", 0) * (1 + growth.area_growth_pct)
        adjusted_yield = base_yield * (1 + growth.yield_improvement_pct)
        total = area * adjusted_yield

        results[name] = {
            "area_ha": area,
            "yield_per_ha": adjusted_yield,
            "total_yield_tonnes": total,
        }
    return results


def calculate_total_yield(projected: Dict[str, Dict[str, float]]) -> float:
    """Sum total yield across all crops."""
    return sum(v["total_yield_tonnes"] for v in projected.values())
