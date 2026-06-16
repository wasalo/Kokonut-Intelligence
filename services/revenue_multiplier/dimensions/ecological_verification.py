"""
Ecological Verification — Dimension 8

Evaluates ecological score verification status and trend.
Compares baseline vs current scores, estimates impact of maintaining/improving ecological health.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get MRV claims
    cur.execute("""
        SELECT
            mc.claim_type,
            mc.status,
            mc.claimed_value,
            mc.created_at
        FROM mrv_claim mc
        WHERE mc.location_id = %s
    """, (location_id,))
    claims = [dict(r) for r in cur.fetchall()]

    # Get ecological scores from fortune500
    cur.execute("""
        SELECT score_name, score_value
        FROM fortune500_score
        WHERE location_id = %s AND score_name IN ('ecological', 'carbon', 'biodiversity')
    """, (location_id,))
    scores = {r["score_name"]: float(r["score_value"] or 0) for r in cur.fetchall()}

    # Get baseline ecological score
    cur.execute("""
        SELECT metric_name, outputs
        FROM fortune500_output
        WHERE location_id = %s AND metric_name = 'ecological_score'
    """, (location_id,))
    baseline_row = cur.fetchone()
    baseline = float(dict(baseline_row)["outputs"].get("ecological_score", 0)) if baseline_row else 0

    # Get forecast: projected ecological score
    cur.execute("""
        SELECT metric_name, outputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'ecological_score_forecast'
        ORDER BY created_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_score = 0
    if forecast_row:
        outputs = dict(forecast_row)["outputs"] or {}
        forecast_score = float(outputs.get("ecological_score_forecast", 0) or 0)

    # Get carbon data
    cur.execute("""
        SELECT
            SUM(estimated_carbon_sequestered) as total_carbon
        FROM carbon_data
        WHERE location_id = %s
    """, (location_id,))
    carbon_row = cur.fetchone()
    total_carbon = float(dict(carbon_row)["total_carbon"] or 0) if carbon_row else 0

    # Get species observations
    cur.execute("""
        SELECT COUNT(DISTINCT species_name) as species_count
        FROM species_observation
        WHERE location_id = %s
    """, (location_id,))
    species_row = cur.fetchone()
    species_count = int(dict(species_row)["species_count"] or 0) if species_row else 0

    cur.close()

    # Current ecological score
    current_score = scores.get("ecological", baseline)

    # Scoring formula weights from config
    carbon_weight = float(get_config(conn, 'ecological_carbon_weight'))
    species_weight = float(get_config(conn, 'ecological_species_weight'))
    claims_weight = float(get_config(conn, 'ecological_claims_weight'))
    forecast_weight = float(get_config(conn, 'ecological_forecast_weight'))

    # Score: composite of data completeness and score quality
    data_score = 0
    if total_carbon > 0:
        data_score += carbon_weight
    if species_count > 0:
        data_score += species_weight
    verified_claims = [c for c in claims if c["status"] == "verified"]
    if verified_claims:
        data_score += claims_weight
    if forecast_score > 0:
        data_score += forecast_weight
    score = min(100, data_score)

    # Impact: value of ecological services
    # Carbon sequestration value
    carbon_price = float(get_config(conn, 'carbon_credit_price_usd'))
    carbon_value = total_carbon * carbon_price

    # Biodiversity value (species-based estimate)
    biodiversity_price = float(get_config(conn, 'biodiversity_credit_price_usd'))
    biodiversity_value = species_count * biodiversity_price

    impact = carbon_value + biodiversity_value

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_score > current_score:
        forecast_impact = (forecast_score - current_score) * carbon_price * 10

    details = {
        "current_ecological_score": round(current_score, 1),
        "baseline_score": round(baseline, 1),
        "forecast_score": round(forecast_score, 1),
        "carbon_sequestered_tonnes": round(total_carbon, 2),
        "species_count": species_count,
        "verified_claims": len(verified_claims),
        "total_claims": len(claims),
        "carbon_value_usd": round(carbon_value, 2),
        "biodiversity_value_usd": round(biodiversity_value, 2),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="ecological_verification",
        dimension_name="Ecological Verification",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if verified_claims else "medium",
        current_state=f"Score {current_score:.0f}, {total_carbon:.0f}t carbon, {species_count} species",
        recommendation=f"Maintain ecological score for ${impact:,.0f}/year in ecosystem services" if impact > 0 else "Establish ecological monitoring",
        data_points=len(claims) + species_count,
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No ecological data", recommendation="Set up ecological monitoring",
        data_points=0,
    )
