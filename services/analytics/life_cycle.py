"""Life Cycle Assessment analytics: product footprint, water footprint, LCA summary."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_product_carbon_footprint(conn, location_id: str, crop_cycle_id: str | None = None) -> dict[str, Any]:
    """Compute carbon footprint per kg of product across lifecycle stages."""
    cur = conn.cursor()

    where_clause = "WHERE lca.location_id = %s AND lca.status IN ('verified', 'published')"
    params = [location_id]
    if crop_cycle_id:
        where_clause += " AND lca.crop_cycle_id = %s"
        params.append(crop_cycle_id)

    cur.execute(
        f"""
        SELECT lifecycle_stage,
               SUM(carbon_footprint_kg_co2e) AS total_co2e,
               SUM(quantity) AS total_quantity,
               SUM(water_footprint_liters) AS total_water,
               SUM(energy_footprint_kwh) AS total_energy,
               SUM(waste_generated_kg) AS total_waste
        FROM lca_assessment lca
        {where_clause}
        GROUP BY lifecycle_stage
        ORDER BY total_co2e DESC
        """,
        params,
    )
    stages = [
        {
            "stage": r[0],
            "carbon_kg_co2e": round(float(r[1]), 2),
            "quantity": round(float(r[2]), 2),
            "water_liters": round(float(r[3]), 2),
            "energy_kwh": round(float(r[4]), 2),
            "waste_kg": round(float(r[5]), 2),
        }
        for r in cur.fetchall()
    ]

    total_co2e = sum(s["carbon_kg_co2e"] for s in stages)
    total_water = sum(s["water_liters"] for s in stages)
    total_energy = sum(s["energy_kwh"] for s in stages)
    total_waste = sum(s["waste_kg"] for s in stages)
    total_quantity = sum(s["quantity"] for s in stages)

    cur.close()

    result = {
        "location_id": location_id,
        "crop_cycle_id": crop_cycle_id,
        "total_carbon_kg_co2e": round(total_co2e, 2),
        "total_water_liters": round(total_water, 2),
        "total_energy_kwh": round(total_energy, 2),
        "total_waste_kg": round(total_waste, 2),
        "carbon_per_unit": round(total_co2e / total_quantity, 4) if total_quantity > 0 else 0,
        "water_per_unit": round(total_water / total_quantity, 2) if total_quantity > 0 else 0,
        "energy_per_unit": round(total_energy / total_quantity, 4) if total_quantity > 0 else 0,
        "waste_per_unit": round(total_waste / total_quantity, 4) if total_quantity > 0 else 0,
        "stages": stages,
    }

    logger.info("Product carbon footprint for %s: %.2f kg CO2e", location_id, total_co2e)
    return result


def compute_water_footprint(conn, location_id: str) -> dict[str, Any]:
    """Compute water footprint across lifecycle stages."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT lifecycle_stage,
               SUM(water_footprint_liters) AS total_water,
               SUM(quantity) AS total_quantity
        FROM lca_assessment
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY lifecycle_stage
        ORDER BY total_water DESC
        """,
        (location_id,),
    )
    stages = [
        {
            "stage": r[0],
            "water_liters": round(float(r[1]), 2),
            "quantity": round(float(r[2]), 2),
        }
        for r in cur.fetchall()
    ]

    total_water = sum(s["water_liters"] for s in stages)

    # Also get water access data
    cur.execute(
        """
        SELECT source_type, capacity_liters, reliability_score, quality_score
        FROM water_access
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    water_sources = [
        {
            "source_type": r[0],
            "capacity_liters": float(r[1]) if r[1] else 0,
            "reliability_score": float(r[2]) if r[2] else 0,
            "quality_score": float(r[3]) if r[3] else 0,
        }
        for r in cur.fetchall()
    ]

    cur.close()

    result = {
        "location_id": location_id,
        "total_water_footprint_liters": round(total_water, 2),
        "water_sources": water_sources,
        "stages": stages,
    }

    logger.info("Water footprint for %s: %.2f liters", location_id, total_water)
    return result


def compute_lca_summary(conn, location_id: str) -> dict[str, Any]:
    """Compute full LCA summary across all lifecycle stages."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT lifecycle_stage,
               COUNT(*) AS assessment_count,
               SUM(quantity) AS total_quantity,
               SUM(carbon_footprint_kg_co2e) AS total_co2e,
               SUM(water_footprint_liters) AS total_water,
               SUM(energy_footprint_kwh) AS total_energy,
               SUM(waste_generated_kg) AS total_waste
        FROM lca_assessment
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY lifecycle_stage
        ORDER BY total_co2e DESC
        """,
        (location_id,),
    )
    stages = [
        {
            "stage": r[0],
            "assessment_count": r[1],
            "total_quantity": round(float(r[2]), 2),
            "carbon_kg_co2e": round(float(r[3]), 2),
            "water_liters": round(float(r[4]), 2),
            "energy_kwh": round(float(r[5]), 2),
            "waste_kg": round(float(r[6]), 2),
        }
        for r in cur.fetchall()
    ]

    total_co2e = sum(s["carbon_kg_co2e"] for s in stages)
    total_water = sum(s["water_liters"] for s in stages)
    total_energy = sum(s["energy_kwh"] for s in stages)
    total_waste = sum(s["waste_kg"] for s in stages)
    total_assessments = sum(s["assessment_count"] for s in stages)

    cur.close()

    result = {
        "location_id": location_id,
        "total_assessments": total_assessments,
        "total_carbon_kg_co2e": round(total_co2e, 2),
        "total_water_liters": round(total_water, 2),
        "total_energy_kwh": round(total_energy, 2),
        "total_waste_kg": round(total_waste, 2),
        "carbon_intensity": round(total_co2e / total_assessments, 2) if total_assessments > 0 else 0,
        "stages": stages,
    }

    logger.info("LCA summary for %s: %d assessments, %.2f kg CO2e", location_id, total_assessments, total_co2e)
    return result
