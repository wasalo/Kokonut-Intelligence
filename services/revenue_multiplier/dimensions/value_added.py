"""
Value-Added Processing — Dimension 4

Compares raw commodity prices vs potential processed product prices.
Estimates processing ROI.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get crop sales data
    cur.execute("""
        SELECT
            c.name as crop_name,
            SUM(he.quantity) as total_yield,
            AVG(se.price_per_unit) as avg_price,
            COUNT(DISTINCT he.crop_cycle_id) as cycles
        FROM harvest_event he
        JOIN crop_cycle cc ON he.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        LEFT JOIN sales_event se ON se.crop_cycle_id = cc.id
        WHERE he.location_id = %s
        GROUP BY c.name
    """, (location_id,))
    crops = [dict(r) for r in cur.fetchall()]

    # Get infrastructure
    cur.execute("""
        SELECT name, asset_type, capacity, capacity_unit
        FROM infrastructure_asset
        WHERE location_id = %s AND asset_type IN ('biofactory', 'processing', 'storage')
    """, (location_id,))
    infra = [dict(r) for r in cur.fetchall()]

    # Get processing-related expenses
    cur.execute("""
        SELECT SUM(amount) as processing_costs
        FROM expense_event
        WHERE location_id = %s AND category = 'Packaging & Processing'
    """, (location_id,))
    proc_costs = float(cur.fetchone()["processing_costs"] or 0)

    cur.close()

    if not crops:
        return OpportunityDimension(
            dimension_id="value_added_processing", dimension_name="Value-Added Processing",
            score=0, impact_usd=0, confidence="low",
            current_state="No crop data", recommendation="Establish baseline crop data first",
            data_points=0,
        )

    # Calculate potential value uplift
    total_raw_value = 0
    total_processed_value = 0
    crop_uplifts = {}

    for crop in crops:
        name = crop["crop_name"]
        yield_t = float(crop["total_yield"] or 0)
        price = float(crop["avg_price"] or 0)
        raw_value = yield_t * price

        uplifts = get_config(conn, 'processing_uplift').get(name, {"basic": get_config(conn, 'default_processing_uplift')})
        best_process = max(uplifts, key=uplifts.get)
        best_multiplier = uplifts[best_process]
        processed_value = raw_value * best_multiplier

        total_raw_value += raw_value
        total_processed_value += processed_value
        crop_uplifts[name] = {
            "raw_value": round(raw_value, 2),
            "best_processing": best_process,
            "multiplier": best_multiplier,
            "processed_value": round(processed_value, 2),
        }

    potential_uplift = total_processed_value - total_raw_value

    # Score based on uplift potential and existing infrastructure
    has_infra = len(infra) > 0
    score = min(100, (potential_uplift / max(total_raw_value, 1)) * 30)
    if has_infra:
        score = min(100, score * 1.3)

    # Impact: uplift minus processing costs
    impact = potential_uplift - proc_costs * 0.5  # Assume 50% cost increase for processing

    details = {
        "crop_uplifts": crop_uplifts,
        "total_raw_value": round(total_raw_value, 2),
        "total_processed_value": round(total_processed_value, 2),
        "potential_uplift": round(potential_uplift, 2),
        "has_processing_infra": has_infra,
        "existing_processing_costs": round(proc_costs, 2),
    }

    return OpportunityDimension(
        dimension_id="value_added_processing",
        dimension_name="Value-Added Processing",
        score=round(score, 1),
        impact_usd=round(max(0, impact), 2),
        confidence="medium",
        current_state=f"Raw value: ${total_raw_value:,.0f}, processed potential: ${total_processed_value:,.0f}",
        recommendation=f"Process into {max(crop_uplifts.values(), key=lambda x: x['multiplier'])['best_processing']} for +${potential_uplift:,.0f}",
        data_points=len(crops),
        details=details,
    )
