"""
Ecological Forecast Module

Projects ecological outcomes based on historical remote sensing
and soil data.
"""

from typing import Dict, Any
from ..ingestion.base import get_db


def get_ecological_baseline(location_id: str) -> Dict[str, float]:
    """Get current ecological indicators for a location."""
    db = get_db()
    result = {}
    with db.cursor() as cur:
        cur.execute("""
            SELECT AVG(ndvi), AVG(canopy_cover_pct)
            FROM remote_sensing_observation
            WHERE location_id = %s
        """, (location_id,))
        row = cur.fetchone()
        if row:
            result["avg_ndvi"] = float(row[0] or 0.5)
            result["avg_canopy_cover_pct"] = float(row[1] or 50.0)

        cur.execute("""
            SELECT AVG(organic_matter_pct), AVG(ph)
            FROM soil_sample
            WHERE location_id = %s
        """, (location_id,))
        row = cur.fetchone()
        if row:
            result["soil_organic_matter_pct"] = float(row[0] or 3.0)
            result["soil_ph"] = float(row[1] or 6.0)
    db.close()
    return result


def project_ecological_score(
    baseline: Dict[str, float],
    regenerative_practices: bool = True,
) -> Dict[str, Any]:
    """Project ecological score (0-100) for next period."""
    ndvi = baseline.get("avg_ndvi", 0.5)
    som = baseline.get("soil_organic_matter_pct", 3.0)
    canopy = baseline.get("avg_canopy_cover_pct", 50.0)

    # Simple scoring model
    ndvi_score = min(100, max(0, (ndvi / 0.8) * 100))
    som_score = min(100, max(0, (som / 5.0) * 100))
    canopy_score = min(100, max(0, (canopy / 80.0) * 100))

    base_score = (ndvi_score * 0.4 + som_score * 0.35 + canopy_score * 0.25)

    if regenerative_practices:
        projected_score = min(100, base_score * 1.08)
    else:
        projected_score = base_score * 0.97

    return {
        "ecological_score": round(projected_score, 1),
        "ndvi_projected": round(ndvi * 1.05 if regenerative_practices else ndvi * 0.98, 4),
        "som_projected": round(som * 1.03 if regenerative_practices else som * 0.99, 2),
        "confidence": 0.75,
    }


def estimate_carbon_sequestration(
    area_ha: float,
    som_change_pct: float = 0.3,
) -> float:
    """Rough estimate of carbon sequestration in tonnes CO2e."""
    # ~10 tonnes CO2e per hectare per 1% SOM increase
    return area_ha * som_change_pct * 10


def estimate_biodiversity_value(conn, location_id: str) -> Dict[str, Any]:
    """Estimate biodiversity credit value from species observations.

    Returns dict with species_count, credit_price, and total_value.
    """
    from ..revenue_multiplier.config import get_config

    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT species_name) as species_count
        FROM species_observation
        WHERE location_id = %s
    """, (location_id,))
    row = cur.fetchone()
    species_count = int(row[0] or 0) if row else 0

    # Also get Shannon diversity index if available
    cur.execute("""
        SELECT
            COUNT(DISTINCT species_name) as total_species,
            COUNT(*) as total_observations
        FROM species_observation
        WHERE location_id = %s
    """, (location_id,))
    diversity_row = cur.fetchone()
    total_observations = int(diversity_row[1] or 0) if diversity_row else 0
    cur.close()

    # Shannon diversity index (H') — higher = more diverse
    shannon_index = 0.0
    if total_observations > 0 and species_count > 0:
        # Approximate from species count and observation distribution
        # H' = -sum(p_i * ln(p_i)); for even distribution: H' = ln(S)
        import math
        shannon_index = round(math.log(species_count), 2) if species_count > 1 else 0.0

    credit_price = float(get_config(conn, 'biodiversity_credit_price_usd'))
    total_value = species_count * credit_price

    return {
        "species_count": species_count,
        "shannon_index": shannon_index,
        "credit_price_per_species": credit_price,
        "total_value_usd": round(total_value, 2),
    }
