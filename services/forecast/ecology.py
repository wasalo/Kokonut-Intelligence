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
