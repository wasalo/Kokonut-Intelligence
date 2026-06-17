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


def get_historical_loss_rate(location_id: str) -> float:
    """Get average historical loss rate for a location (0.0-1.0)."""
    from ..ingestion.base import get_db
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(
                AVG(CASE WHEN quantity > 0 THEN loss_amount / quantity ELSE 0 END),
                0.05
            )
            FROM harvest_event
            WHERE location_id = %s AND quantity > 0
        """, (location_id,))
        row = cur.fetchone()
    db.close()
    return float(row[0]) if row else 0.05


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


def apply_loss_adjustment(
    projected: Dict[str, Dict[str, float]],
    loss_rate: float,
) -> Dict[str, Dict[str, float]]:
    """Apply post-harvest loss adjustment to projected yields.

    Args:
        projected: Output of project_yields().
        loss_rate: Historical loss rate (0.0-1.0), e.g. 0.05 = 5% loss.

    Returns:
        Same dict with loss_adjusted_yield_tonnes added per crop.
    """
    for crop_name, data in projected.items():
        gross = data["total_yield_tonnes"]
        data["loss_adjusted_yield_tonnes"] = round(gross * (1 - loss_rate), 4)
    return projected


def get_bed_areas_for_location(location_id: str) -> Dict[str, Any]:
    """Get bed-level area data for all plots at a location.

    Returns dict with per-plot bed data and total bed area in m².
    Returns empty/zero values if no bed data exists (fallback to ha-based model).
    """
    from ..ingestion.base import get_db
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT
                p.name as plot_name,
                p.bed_count,
                p.bed_area_sqm,
                cc.id as cycle_id,
                c.name as crop_name
            FROM plot p
            JOIN crop_cycle cc ON cc.plot_id = p.id
            JOIN crop c ON cc.crop_id = c.id
            WHERE p.location_id = %s
              AND p.bed_count IS NOT NULL
              AND p.bed_area_sqm IS NOT NULL
              AND cc.status = 'completed'
        """, (location_id,))
        rows = cur.fetchall()
    db.close()

    plots = {}
    total_bed_area_sqm = 0.0
    for row in rows:
        plot_name = row[0]
        bed_count = int(row[1] or 0)
        bed_area_sqm = float(row[2] or 0)
        total_sqm = bed_count * bed_area_sqm
        if plot_name not in plots:
            plots[plot_name] = {
                "bed_count": bed_count,
                "bed_area_sqm": bed_area_sqm,
                "total_bed_area_sqm": total_sqm,
                "cycle_ids": [],
                "crops": [],
            }
        plots[plot_name]["cycle_ids"].append(str(row[3]))
        plots[plot_name]["crops"].append(row[4])
        total_bed_area_sqm += total_sqm

    return {
        "plots": plots,
        "total_bed_area_sqm": total_bed_area_sqm,
        "plot_count": len(plots),
        "has_bed_data": len(plots) > 0,
    }


def project_yields_per_sqm(
    planting_density_per_sqm: float,
    bed_area_sqm: float,
    bed_count: int,
    plot_count: int,
    loss_rate: float,
    yield_per_ha: float = 0.0,
) -> Dict[str, Any]:
    """Compute total production using per-square-meter formula.

    Formula:
        Total Production = Planting Density/m² × Bed Area m² × Beds/Plot × Plots × (1 − Loss Rate)

    When yield_per_ha is provided, also converts to tonnes using ha conversion.
    When planting_density_per_sqm is provided, uses it to estimate plant count.

    Args:
        planting_density_per_sqm: Plants per square meter (from crop_cycle.planting_density)
        bed_area_sqm: Area per bed in m² (from plot.bed_area_sqm)
        bed_count: Number of beds per plot (from plot.bed_count)
        plot_count: Number of plots with this crop
        loss_rate: Historical loss rate (0.0-1.0)
        yield_per_ha: Expected yield in tonnes/ha (from crop or assumptions)

    Returns:
        Dict with total_bed_area_sqm, total_plants, total_yield_tonnes, yield_per_sqm
    """
    total_bed_area_sqm = bed_area_sqm * bed_count * plot_count
    total_plants = planting_density_per_sqm * total_bed_area_sqm

    # Convert yield from tonnes/ha to tonnes/m² for calculation
    # 1 ha = 10,000 m²
    yield_per_sqm = yield_per_ha / 10000 if yield_per_ha > 0 else 0

    # Total yield from bed area
    total_yield_tonnes = total_bed_area_sqm * yield_per_sqm

    # Apply loss adjustment
    adjusted_yield = total_yield_tonnes * (1 - loss_rate)

    # Revenue per m² (requires price, computed externally)
    # production_per_sqm is the yield density
    production_per_sqm = adjusted_yield / total_bed_area_sqm if total_bed_area_sqm > 0 else 0

    return {
        "total_bed_area_sqm": round(total_bed_area_sqm, 2),
        "total_plants": round(total_plants, 0),
        "total_yield_tonnes_raw": round(total_yield_tonnes, 4),
        "total_yield_tonnes": round(adjusted_yield, 4),
        "yield_per_sqm": round(production_per_sqm, 6),
        "yield_per_ha": yield_per_ha,
        "loss_rate": loss_rate,
        "bed_area_sqm": bed_area_sqm,
        "bed_count": bed_count,
        "plot_count": plot_count,
        "planting_density_per_sqm": planting_density_per_sqm,
    }
