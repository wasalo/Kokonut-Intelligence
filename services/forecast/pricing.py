"""
Pricing Module

Pulls historical prices from price_observation and applies
scenario assumptions to project future prices.
"""

import psycopg2
from typing import Dict, Optional
from ..ingestion.base import get_db
from .models import PriceAssumptions


def get_latest_prices(location_id: str) -> Dict[str, float]:
    """Get latest price per tonne for each crop at a location."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT c.name, AVG(po.price_per_unit) as avg_price
            FROM price_observation po
            JOIN crop c ON po.crop_id = c.id
            WHERE po.price_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY c.name
        """)
        rows = cur.fetchall()
    db.close()
    return {row[0]: float(row[1]) for row in rows if row[1]}


def get_historical_avg_prices(months: int = 12, location_id: Optional[str] = None) -> Dict[str, float]:
    """Get average prices over last N months for each crop.

    If location_id is provided, only include price observations for crops
    grown at that location (via crop_cycle). Otherwise returns global averages.
    """
    db = get_db()
    with db.cursor() as cur:
        if location_id:
            cur.execute("""
                SELECT c.name, AVG(po.price_per_unit) as avg_price
                FROM price_observation po
                JOIN crop c ON po.crop_id = c.id
                WHERE po.price_date >= CURRENT_DATE - INTERVAL '%s months'
                  AND po.crop_id IN (
                      SELECT DISTINCT cc.crop_id
                      FROM crop_cycle cc
                      WHERE cc.location_id = %s
                  )
                GROUP BY c.name
            """, (months, location_id))
        else:
            cur.execute("""
                SELECT c.name, AVG(po.price_per_unit) as avg_price
                FROM price_observation po
                JOIN crop c ON po.crop_id = c.id
                WHERE po.price_date >= CURRENT_DATE - INTERVAL '%s months'
                GROUP BY c.name
            """, (months,))
        rows = cur.fetchall()
    db.close()
    return {row[0]: float(row[1]) for row in rows if row[1]}


def project_prices(
    base_prices: Dict[str, float],
    assumptions: PriceAssumptions,
    growth: float = 0.0,
) -> Dict[str, float]:
    """Project prices forward using scenario assumptions."""
    projected = {}
    crop_map = {
        "Maize": assumptions.maize_per_tonne_usd,
        "Cassava": assumptions.cassava_per_tonne_usd,
        "Beans": assumptions.beans_per_tonne_usd,
        "Sweet Potato": assumptions.sweet_potato_per_tonne_usd,
    }
    for crop_name, fallback_price in crop_map.items():
        base = base_prices.get(crop_name, fallback_price)
        projected[crop_name] = base * (1 + growth)
    return projected


def get_price_assumptions_from_scenario(scenario: dict) -> PriceAssumptions:
    """Extract price assumptions from a scenario record."""
    pa = scenario.get("price_assumptions", {})
    if pa:
        return PriceAssumptions.from_dict(pa)
    return PriceAssumptions()
