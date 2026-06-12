"""
Bioinput Production — Dimension 6

Analyzes bioinput spending vs conventional, estimates on-farm production ROI.
"""

import psycopg2.extras
from ..models import OpportunityDimension


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get bioinput expenses
    cur.execute("""
        SELECT SUM(amount) as total_bioinput
        FROM expense_event
        WHERE location_id = %s AND category = 'Bioinputs & Compost'
    """, (location_id,))
    bioinput_cost = float(cur.fetchone()["total_bioinput"] or 0)

    # Get conventional input expenses
    cur.execute("""
        SELECT SUM(amount) as total_conventional
        FROM expense_event
        WHERE location_id = %s AND category IN ('Fertilizer & Soil Amendments', 'Pest & Disease Control')
    """, (location_id,))
    conventional_cost = float(cur.fetchone()["total_conventional"] or 0)

    # Get biofactory infrastructure
    cur.execute("""
        SELECT name, capacity, capacity_unit
        FROM infrastructure_asset
        WHERE location_id = %s AND asset_type = 'biofactory'
    """, (location_id,))
    biofactory = cur.fetchone()

    # Get soil health trajectory
    cur.execute("""
        SELECT
            AVG(organic_matter_pct) as avg_om,
            COUNT(*) as sample_count
        FROM soil_sample
        WHERE location_id = %s
    """, (location_id,))
    soil = dict(cur.fetchone()) if cur.rowcount else {}

    cur.close()

    total_input_cost = bioinput_cost + conventional_cost
    bioinput_share = (bioinput_cost / total_input_cost * 100) if total_input_cost > 0 else 0

    # Score: bioinput adoption level
    score = min(100, bioinput_share * 1.5 + (50 if biofactory else 0))

    # Impact: on-farm production savings (70% cost reduction vs purchased)
    if biofactory:
        # Estimate production capacity value
        capacity = float(biofactory["capacity"] or 500)
        production_value = bioinput_cost * 0.7  # 70% savings
        impact = production_value
    else:
        # Estimate benefit of switching to on-farm production
        impact = bioinput_cost * 0.5 if bioinput_cost > 0 else conventional_cost * 0.3

    details = {
        "bioinput_cost": round(bioinput_cost, 2),
        "conventional_cost": round(conventional_cost, 2),
        "bioinput_share_pct": round(bioinput_share, 1),
        "has_biofactory": biofactory is not None,
        "soil_organic_matter": float(soil.get("avg_om", 0)),
    }

    return OpportunityDimension(
        dimension_id="bioinput_production",
        dimension_name="Bioinput Production",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="medium" if biofactory else "low",
        current_state=f"Bioinput: ${bioinput_cost:,.0f} ({bioinput_share:.0f}% of inputs), {'Has' if biofactory else 'No'} biofactory",
        recommendation="Scale on-farm bioinput production" if biofactory else "Build biofactory for 70% input cost savings",
        data_points=2,
        details=details,
    )
