"""
Cost Forecasting Module

Projects operational costs based on historical data and scenario assumptions.
"""

from typing import Dict, Any, List
from .models import CostAssumptions, GrowthAssumptions


def get_historical_costs(location_id: str) -> Dict[str, float]:
    """Get total costs by category for a location from expense_event."""
    from ..ingestion.base import get_db
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT category, SUM(amount) as total
            FROM expense_event
            WHERE location_id = %s AND status IN ('approved', 'published')
            GROUP BY category
        """, (location_id,))
        rows = cur.fetchall()
    db.close()
    return {row[0]: float(row[1]) for row in rows}


def project_costs(
    historical_costs: Dict[str, float],
    cost_assumptions: CostAssumptions,
    growth: GrowthAssumptions,
    total_area_ha: float,
) -> Dict[str, Dict[str, float]]:
    """Project costs for next period."""
    area_multiplier = 1 + growth.area_growth_pct
    inflation = 1.05  # default 5% inflation

    direct_costs = {
        "seeds": cost_assumptions.seeds_usd_per_ha * total_area_ha * area_multiplier * inflation,
        "fertilizer": cost_assumptions.fertilizer_usd_per_ha * total_area_ha * area_multiplier * inflation,
        "labor_field": cost_assumptions.labor_usd_per_ha * total_area_ha * area_multiplier * inflation,
        "irrigation": cost_assumptions.irrigation_usd_per_ha * total_area_ha * area_multiplier * inflation,
    }

    # Shared costs from historical (adjusted for inflation)
    shared_cost_categories = [
        "Labor-Admin", "Equipment", "Transport", "Utilities",
        "Maintenance", "Packaging", "Insurance", "Marketing",
        "Rent", "Professional Services",
    ]
    shared_costs = {}
    total_shared = 0.0
    for cat in shared_cost_categories:
        hist = historical_costs.get(cat, 0)
        projected = hist * area_multiplier * inflation
        shared_costs[cat] = projected
        total_shared += projected

    total_direct = sum(direct_costs.values())

    return {
        "direct": direct_costs,
        "shared": shared_costs,
        "total_direct": total_direct,
        "total_shared": total_shared,
        "total_costs": total_direct + total_shared,
    }


def allocate_shared_costs(
    total_shared: float,
    crop_areas: Dict[str, Dict[str, float]],
) -> Dict[str, float]:
    """Allocate shared costs proportionally by crop area."""
    total_area = sum(v["area_ha"] for v in crop_areas.values())
    if total_area == 0:
        return {}
    return {
        crop: (data["area_ha"] / total_area) * total_shared
        for crop, data in crop_areas.items()
    }
