"""
Partner Sponsorship — Dimension 9

Evaluates partner/vendor/operator engagement and sponsorship value.
Analyzes partner diversity, revenue contribution, and network effects.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get partners (via capital sources and partner events)
    cur.execute("""
        SELECT
            ce.event_type,
            ce.amount,
            ce.counterparty_name,
            ce.counterparty_type,
            ce.status
        FROM capital_event ce
        WHERE ce.location_id = %s
          AND ce.counterparty_type IN ('vendor', 'operator', 'buyer')
    """, (location_id,))
    partners = [dict(r) for r in cur.fetchall()]

    # Get capital sources with partners
    cur.execute("""
        SELECT
            cs.source_type,
            cs.amount,
            cs.name,
            cs.status
        FROM capital_source cs
        WHERE cs.location_id = %s
          AND cs.source_type IN ('vendor_credit', 'operator_contract', 'partner_investment')
    """, (location_id,))
    capital_partners = [dict(r) for r in cur.fetchall()]

    # Get partner engagement scores
    cur.execute("""
        SELECT * FROM partner_engagement WHERE location_id = %s
    """, (location_id,))
    engagement = [dict(r) for r in cur.fetchall()]

    # Get forecast: projected revenue
    cur.execute("""
        SELECT metric_name, outputs
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'projected_revenue_usd'
        ORDER BY created_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_revenue = 0
    if forecast_row:
        outputs = dict(forecast_row)["outputs"] or {}
        forecast_revenue = float(outputs.get("projected_revenue_usd", 0) or 0)

    cur.close()

    # Count unique partners
    partner_names = set()
    for p in partners:
        if p["counterparty_name"]:
            partner_names.add(p["counterparty_name"])
    for cp in capital_partners:
        if cp["name"]:
            partner_names.add(cp["name"])

    total_partner_value = sum(float(p["amount"] or 0) for p in partners) + sum(float(cp["amount"] or 0) for cp in capital_partners)

    # Config constants
    partner_count_multiplier = float(get_config(conn, 'partner_count_multiplier'))
    partner_revenue_bonus = float(get_config(conn, 'partner_revenue_bonus'))

    # Score: based on partner diversity and value
    score = min(100, max(0, len(partner_names) * partner_count_multiplier))

    # Bonus for active partnerships
    active_partners = [p for p in partners if p["status"] in ("active", "completed")]
    if active_partners:
        score = min(100, score + partner_revenue_bonus)

    # Impact: sponsorship value and network effects
    # Each partner contributes an average of X to revenue
    avg_partner_value = total_partner_value / max(len(partner_names), 1)
    impact = avg_partner_value * len(partner_names) * 0.5  # 50% from network effects

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_revenue > 0:
        partner_share = total_partner_value / max(forecast_revenue, 1)
        forecast_impact = forecast_revenue * partner_share * 0.3  # 30% growth from partnerships

    details = {
        "partner_count": len(partner_names),
        "partner_names": list(partner_names)[:10],
        "total_partner_value": round(total_partner_value, 2),
        "avg_partner_value": round(avg_partner_value, 2),
        "active_partners": len(active_partners),
        "partner_types": list(set(p["counterparty_type"] for p in partners if p["counterparty_type"])),
        "engagement_scores": len(engagement),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="partner_sponsorship",
        dimension_name="Partner Sponsorship",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if engagement else "medium",
        current_state=f"{len(partner_names)} partners, ${total_partner_value:,.0f} total value",
        recommendation=f"Grow partner network by {max(1, 3 - len(partner_names))} for +${impact:,.0f}/year" if impact > 0 else "Maintain partner relationships",
        data_points=len(partners) + len(capital_partners) + len(engagement),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No partner data", recommendation="Track partner engagements and sponsorships",
        data_points=0,
    )
