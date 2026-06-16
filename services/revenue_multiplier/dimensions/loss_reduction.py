"""
Loss-Rate Reduction — Dimension 2

Pareto analysis of losses by type, crop, and severity.
Identifies highest-impact reduction opportunities.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get loss events
    cur.execute("""
        SELECT
            le.loss_type,
            le.estimated_value,
            le.severity,
            le.cause,
            c.name as crop_name
        FROM loss_event le
        LEFT JOIN crop_cycle cc ON le.crop_cycle_id = cc.id
        LEFT JOIN crop c ON cc.crop_id = c.id
        WHERE le.location_id = %s
    """, (location_id,))
    losses = [dict(r) for r in cur.fetchall()]

    # Get harvest losses
    cur.execute("""
        SELECT
            he.loss_amount,
            he.loss_estimated_value,
            he.loss_reason,
            c.name as crop_name
        FROM harvest_event he
        JOIN crop_cycle cc ON he.crop_cycle_id = cc.id
        JOIN crop c ON cc.crop_id = c.id
        WHERE he.location_id = %s AND he.loss_amount > 0
    """, (location_id,))
    harvest_losses = [dict(r) for r in cur.fetchall()]

    # Get total revenue for context
    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0) as total_revenue
        FROM sales_event WHERE location_id = %s
    """, (location_id,))
    total_revenue = float(cur.fetchone()["total_revenue"])

    cur.close()

    if not losses and not harvest_losses:
        return OpportunityDimension(
            dimension_id="loss_rate_reduction", dimension_name="Loss-Rate Reduction",
            score=0, impact_usd=0, confidence="low",
            current_state="No loss data", recommendation="Start tracking losses",
            data_points=0,
        )

    # Aggregate losses by type
    loss_by_type = {}
    for loss in losses:
        lt = loss["loss_type"] or "unknown"
        val = float(loss["estimated_value"] or 0)
        if lt not in loss_by_type:
            loss_by_type[lt] = {"total": 0, "count": 0}
        loss_by_type[lt]["total"] += val
        loss_by_type[lt]["count"] += 1

    # Add harvest losses
    total_harvest_loss = sum(float(h["loss_estimated_value"] or 0) for h in harvest_losses)

    total_loss = sum(v["total"] for v in loss_by_type.values()) + total_harvest_loss
    loss_rate = (total_loss / total_revenue * 100) if total_revenue > 0 else 0

    # Pareto: top loss type
    if loss_by_type:
        top_type = max(loss_by_type, key=lambda k: loss_by_type[k]["total"])
        top_impact = loss_by_type[top_type]["total"]
    else:
        top_type = "harvest_handling"
        top_impact = total_harvest_loss

    # Score: lower loss rate = better, but high loss = high opportunity
    score = min(100, loss_rate * 5)  # 20% loss rate = 100 score

    # Impact: reducing top loss type by target percentage
    loss_reduction_target = float(get_config(conn, 'loss_reduction_target_pct')) / 100
    impact = top_impact * loss_reduction_target

    details = {
        "loss_by_type": loss_by_type,
        "total_harvest_loss": round(total_harvest_loss, 2),
        "loss_rate_pct": round(loss_rate, 2),
        "top_loss_type": top_type,
        "total_loss": round(total_loss, 2),
    }

    return OpportunityDimension(
        dimension_id="loss_rate_reduction",
        dimension_name="Loss-Rate Reduction",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if len(losses) >= 3 else "medium",
        current_state=f"Loss rate: {loss_rate:.1f}%, top type: {top_type} (${top_impact:,.0f})",
        recommendation=f"Target {top_type} losses for {float(get_config(conn, 'loss_reduction_target_pct')):.0f}% reduction = ${impact:,.0f}/year savings",
        data_points=len(losses) + len(harvest_losses),
        details=details,
    )
