"""
Loss Reduction — Dimension 2

Evaluates whether farm's loss reduction potential is captured.
Compares historical loss rates vs targets, estimates upside from reducing losses.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get crop cycles with yield data
    cur.execute("""
        SELECT
            c.name as crop_name,
            cc.id as cycle_id,
            cc.area_planted,
            cc.actual_yield,
            cc.expected_yield,
            cc.actual_revenue
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        WHERE cc.location_id = %s
    """, (location_id,))
    cycles = [dict(r) for r in cur.fetchall()]

    # Get loss events
    cur.execute("""
        SELECT le.*, c.name as crop_name
        FROM loss_event le
        JOIN crop_cycle cc ON le.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE cc.location_id = %s
    """, (location_id,))
    losses = [dict(r) for r in cur.fetchall()]

    # Get forecast: projected yield and loss-adjusted yield
    cur.execute("""
        SELECT metric_name, inputs, outputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name IN ('projected_yield_tonnes', 'loss_adjusted_yield_tonnes')
        ORDER BY created_at DESC LIMIT 2
    """, (location_id,))
    forecasts = {r["metric_name"]: r for r in cur.fetchall()}

    cur.close()

    if not cycles:
        return _empty("loss_reduction", "Loss Reduction")

    # Calculate historical loss rates
    loss_rates = []
    for cycle in cycles:
        expected = float(cycle["expected_yield"] or 0)
        actual = float(cycle["actual_yield"] or 0)
        if expected > 0:
            loss_pct = ((expected - actual) / expected) * 100
            loss_rates.append(loss_pct)

    avg_loss_rate = sum(loss_rates) / len(loss_rates) if loss_rates else 0

    # Get target loss reduction from config
    target_loss_pct = float(get_config(conn, 'loss_reduction_target_pct'))

    # Calculate score
    # If loss rate > target: room for improvement = higher score
    score_multiplier = float(get_config(conn, 'loss_rate_score_multiplier'))
    score = min(100, max(0, avg_loss_rate * score_multiplier))

    # Estimate impact: value of reducing losses to target
    total_revenue = sum(float(c["actual_revenue"] or 0) for c in cycles)
    total_area = sum(float(c["area_planted"] or 0) for c in cycles)
    potential_savings = (total_revenue * (avg_loss_rate - target_loss_pct) / 100) if avg_loss_rate > target_loss_pct else 0

    # Forecast-adjusted impact
    forecast_impact = 0
    if "projected_yield_tonnes" in forecasts and "loss_adjusted_yield_tonnes" in forecasts:
        proj = forecasts["projected_yield_tonnes"]
        loss_adj = forecasts["loss_adjusted_yield_tonnes"]
        proj_yield = float(proj.get("outputs", {}).get("projected_yield_tonnes", 0) or 0)
        loss_adj_yield = float(loss_adj.get("outputs", {}).get("loss_adjusted_yield_tonnes", 0) or 0)
        forecast_impact = (proj_yield - loss_adj_yield) * total_revenue / max(total_area, 0.01)

    confidence_threshold = int(get_config(conn, 'loss_rate_confidence_threshold'))
    details = {
        "avg_loss_rate_pct": round(avg_loss_rate, 1),
        "target_loss_pct": target_loss_pct,
        "total_loss_events": len(losses),
        "losses_by_crop": {},
        "potential_savings_usd": round(potential_savings, 2),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    # Group losses by crop
    for loss in losses:
        crop = loss["crop_name"]
        if crop not in details["losses_by_crop"]:
            details["losses_by_crop"][crop] = 0
        details["losses_by_crop"][crop] += 1

    impact = max(potential_savings, forecast_impact)

    return OpportunityDimension(
        dimension_id="loss_reduction",
        dimension_name="Loss Reduction",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if len(losses) >= confidence_threshold else "medium",
        current_state=f"Avg loss rate: {avg_loss_rate:.1f}% (target: {target_loss_pct}%)",
        recommendation=f"Reduce loss rate by {avg_loss_rate - target_loss_pct:.1f}% for +${impact:,.0f}/year" if impact > 0 else "Loss rate at target",
        data_points=len(cycles) + len(losses),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No crop cycle data", recommendation="Complete crop cycles first",
        data_points=0,
    )
