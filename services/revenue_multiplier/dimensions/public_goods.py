"""
Public Goods Funding Loop — Dimension 7

Evaluates public goods allocation from treasury.
Analyzes infrastructure sharing, community investment, and loop multiplier.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get treasury allocations (public goods funding)
    cur.execute("""
        SELECT
            ce.flow_type as event_type,
            ce.amount,
            ce.to_entity as allocated_to,
            CASE WHEN ce.verified THEN 'verified' ELSE 'draft' END as status,
            ce.created_at
        FROM value_flow_event ce
        WHERE ce.location_id = %s
          AND ce.flow_type IN ('allocation', 'public_goods')
          AND ce.verified = TRUE
    """, (location_id,))
    allocations = [dict(r) for r in cur.fetchall()]

    # Get treasury balance
    cur.execute("""
        SELECT
            cs.source_type,
            SUM(cs.amount) as total_amount
        FROM capital_source cs
        LEFT JOIN financial_transaction ft ON ft.capital_source_id = cs.id
        LEFT JOIN revenue_event re ON re.capital_source_id = cs.id
        WHERE (ft.location_id = %s OR re.location_id = %s) AND cs.source_type = 'treasury'
        GROUP BY cs.source_type
    """, (location_id, location_id))
    treasury_row = cur.fetchone()
    treasury_balance = float(dict(treasury_row)["total_amount"] or 0) if treasury_row else 0

    # Get infrastructure sharing
    cur.execute("""
        SELECT
            ia.asset_type as resource_type,
            ia.location_id as user_location_id,
            COUNT(*) as usage_count
        FROM infrastructure_asset ia
        WHERE ia.location_id = %s AND ia.status = 'active'
        GROUP BY ia.asset_type, ia.location_id
    """, (location_id,))
    sharing = [dict(r) for r in cur.fetchall()]

    # Get public goods from forecast
    cur.execute("""
        SELECT metric_name, inputs, value
        FROM forecast_output
        WHERE location_id = %s
          AND metric_name = 'public_goods_allocation_usd'
        ORDER BY calculated_at DESC LIMIT 1
    """, (location_id,))
    forecast_row = cur.fetchone()
    forecast_allocation = 0
    if forecast_row:
        forecast_allocation = float(dict(forecast_row).get("value") or 0)

    cur.close()

    # Total public goods allocated
    total_allocated = sum(float(a["amount"] or 0) for a in allocations)

    # Get config constants
    allocation_multiplier = float(get_config(conn, 'public_goods_allocation_multiplier'))
    target_pct = float(get_config(conn, 'public_goods_target_pct'))
    loop_multiplier = float(get_config(conn, 'loop_multiplier'))

    # Estimate revenue from revenue table (for % calculation)
    cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur2.execute("""
        SELECT SUM(amount) as total_revenue
        FROM revenue_event
        WHERE location_id = %s
    """, (location_id,))
    rev_row = cur2.fetchone()
    total_revenue = float(dict(rev_row)["total_revenue"] or 0) if rev_row else 0
    cur2.close()

    allocation_pct = (total_allocated / max(total_revenue, 1)) * 100

    # Score: based on allocation % and treasury health
    score = min(100, max(0, allocation_pct * allocation_multiplier))

    # Bonus if treasury is well-funded
    if treasury_balance > total_revenue * 0.1:
        score = min(100, score + 10)

    # Impact: loop multiplier on public goods allocation
    impact = total_allocated * loop_multiplier

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_allocation > 0:
        forecast_impact = forecast_allocation * loop_multiplier

    details = {
        "total_allocated": round(total_allocated, 2),
        "allocation_pct": round(allocation_pct, 1),
        "treasury_balance": round(treasury_balance, 2),
        "infrastructure_sharing": len(sharing),
        "shared_users": len(set(s["user_location_id"] for s in sharing)),
        "forecast_allocation": round(forecast_allocation, 2),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="public_goods_funding",
        dimension_name="Public Goods Funding Loop",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if allocations else "medium",
        current_state=f"${total_allocated:,.0f} allocated ({allocation_pct:.1f}% of revenue), treasury: ${treasury_balance:,.0f}",
        recommendation=f"Increase allocation to {target_pct * 100:.0f}% of revenue for +${impact:,.0f}/year loop value" if impact > 0 else "Public goods funding at target level",
        data_points=len(allocations) + len(sharing),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No public goods allocation data", recommendation="Set up treasury and allocation tracking",
        data_points=0,
    )
