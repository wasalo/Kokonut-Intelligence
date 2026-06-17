"""
Bioinput Production — Dimension 6

Evaluates bioinput adoption vs conventional inputs.
Compares savings, sustainability benefits, and soil health impact.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get input usage
    cur.execute("""
        SELECT
            COALESCE(ee.subcategory, ee.category) as input_name,
            CASE
                WHEN LOWER(ee.category) IN ('bioinput', 'compost', 'biofertilizer', 'organic_fertilizer')
                     OR LOWER(COALESCE(ee.description, '')) LIKE '%%bio%%'
                     OR LOWER(COALESCE(ee.description, '')) LIKE '%%compost%%'
                THEN 'bioinput'
                ELSE ee.category
            END as category,
            'USD' as unit,
            COUNT(*) as total_quantity,
            SUM(ee.amount) as total_cost
        FROM expense_event ee
        WHERE ee.location_id = %s
          AND ee.status IN ('verified', 'published')
          AND LOWER(ee.category) IN ('seeds', 'fertilizer', 'pesticide', 'pesticides', 'bioinput', 'compost', 'irrigation', 'other')
        GROUP BY COALESCE(ee.subcategory, ee.category),
            CASE
                WHEN LOWER(ee.category) IN ('bioinput', 'compost', 'biofertilizer', 'organic_fertilizer')
                     OR LOWER(COALESCE(ee.description, '')) LIKE '%%bio%%'
                     OR LOWER(COALESCE(ee.description, '')) LIKE '%%compost%%'
                THEN 'bioinput'
                ELSE ee.category
            END
    """, (location_id,))
    inputs = [dict(r) for r in cur.fetchall()]

    # Get soil health data
    cur.execute("""
        SELECT
            sh.sample_date as observation_date,
            sh.ph as ph_level,
            sh.organic_matter_pct as organic_matter,
            sh.nitrogen_ppm
        FROM soil_sample sh
        WHERE sh.location_id = %s
        ORDER BY sh.sample_date DESC
        LIMIT 5
    """, (location_id,))
    soil = [dict(r) for r in cur.fetchall()]

    # Get forecast: projected yield (to estimate input value)
    cur.execute("""
        SELECT metric_name, inputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'projected_yield_tonnes'
        ORDER BY calculated_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_yield = 0
    if forecast_row:
        inputs_data = dict(forecast_row)["inputs"] or {}
        forecast_yield = float(inputs_data.get("area_ha", 0) or 0)

    cur.close()

    if not inputs:
        return _empty("bioinput_production", "Bioinput Production")

    # Separate bio vs conventional
    bio_inputs = [i for i in inputs if i["category"] == "bioinput"]
    conventional = [i for i in inputs if i["category"] != "bioinput"]

    bio_cost = sum(float(i["total_cost"] or 0) for i in bio_inputs)
    conventional_cost = sum(float(i["total_cost"] or 0) for i in conventional)
    total_cost = bio_cost + conventional_cost

    bio_share = bio_cost / max(total_cost, 1) * 100

    # Soil improvement trend
    soil_trend = "stable"
    if len(soil) >= 2:
        recent_om = float(soil[0]["organic_matter"] or 0)
        older_om = float(soil[-1]["organic_matter"] or 0)
        if recent_om > older_om * 1.05:
            soil_trend = "improving"
        elif recent_om < older_om * 0.95:
            soil_trend = "declining"

    # Config constants
    bioinput_share_multiplier = float(get_config(conn, 'bioinput_share_multiplier'))
    bioinput_biofactory_bonus = float(get_config(conn, 'bioinput_biofactory_bonus'))
    bioinput_default_capacity = float(get_config(conn, 'bioinput_default_capacity'))
    bioinput_savings_pct = float(get_config(conn, 'bioinput_savings_pct'))
    bioinput_switching_benefit_pct = float(get_config(conn, 'bioinput_switching_benefit_pct'))
    bioinput_switching_fallback = float(get_config(conn, 'bioinput_switching_fallback'))

    # Score: based on bio adoption and soil health
    score = min(100, max(0, bio_share * bioinput_share_multiplier))

    # Bonus if soil is improving with bio inputs
    if soil_trend == "improving" and bio_share > 30:
        score += bioinput_biofactory_bonus
        score = min(100, score)

    # Impact: savings from switching conventional to bio
    if conventional_cost > 0:
        impact = conventional_cost * (bioinput_savings_pct / 100) * (bioinput_switching_benefit_pct / 100)
    else:
        impact = conventional_cost * bioinput_switching_fallback

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_yield > 0:
        estimated_input_cost = forecast_yield * 50  # $50/tonne rough input cost
        forecast_impact = estimated_input_cost * (bioinput_savings_pct / 100) * 0.3

    details = {
        "bio_cost": round(bio_cost, 2),
        "conventional_cost": round(conventional_cost, 2),
        "bio_share_pct": round(bio_share, 1),
        "soil_trend": soil_trend,
        "soil_observations": len(soil),
        "input_categories": list(set(i["category"] for i in inputs)),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="bioinput_production",
        dimension_name="Bioinput Production",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if soil else "medium",
        current_state=f"{bio_share:.0f}% bio inputs, soil trend: {soil_trend}",
        recommendation=f"Increase bio share to {min(bio_share + 20, 100):.0f}% for +${impact:,.0f}/year savings" if impact > 0 else "Bio adoption at optimal level",
        data_points=len(inputs) + len(soil),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No input data", recommendation="Record crop inputs and soil health data",
        data_points=0,
    )
