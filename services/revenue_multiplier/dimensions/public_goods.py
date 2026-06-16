"""
Public-Goods Funding Loops — Dimension 7

Tracks actual vs forecasted allocations, shows funding→impact→funding cycle.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get public goods allocations
    cur.execute("""
        SELECT SUM(amount) as total_allocated
        FROM value_flow_event
        WHERE location_id = %s AND flow_type = 'public_goods' AND verified = TRUE
    """, (location_id,))
    actual = float(cur.fetchone()["total_allocated"] or 0)

    # Get total revenue
    cur.execute("""
        SELECT SUM(amount) as total_revenue
        FROM value_flow_event
        WHERE location_id = %s AND flow_type = 'revenue' AND verified = TRUE
    """, (location_id,))
    revenue = float(cur.fetchone()["total_revenue"] or 0)

    # Get treasury flows
    cur.execute("""
        SELECT flow_direction, SUM(usd_value) as total
        FROM treasury_event
        WHERE location_id = %s
        GROUP BY flow_direction
    """, (location_id,))
    treasury = {r["flow_direction"]: float(r["total"]) for r in cur.fetchall()}

    # Get cash flow snapshots
    cur.execute("""
        SELECT public_goods_allocation, total_revenue
        FROM cash_flow_snapshot
        WHERE location_id = %s
        ORDER BY period_end DESC LIMIT 1
    """, (location_id,))
    cf = dict(cur.fetchone()) if cur.rowcount else {}

    cur.close()

    # Calculate metrics
    allocation_rate = (actual / revenue * 100) if revenue > 0 else 0
    forecasted = float(cf.get("public_goods_allocation", 0))
    forecast_accuracy = (actual / forecasted * 100) if forecasted > 0 else 0

    # Score: actual allocation rate
    score = min(100, allocation_rate * 10)  # 10% allocation = 100 score

    # Impact: funding loop multiplier (every $1 public goods → $2 ecosystem value)
    loop_multiplier = float(get_config(conn, 'loop_multiplier'))
    impact = actual * (loop_multiplier - 1)  # Net new value from the loop

    details = {
        "actual_allocation": round(actual, 2),
        "forecasted_allocation": round(forecasted, 2),
        "total_revenue": round(revenue, 2),
        "allocation_rate_pct": round(allocation_rate, 1),
        "forecast_accuracy_pct": round(forecast_accuracy, 1),
        "loop_multiplier": loop_multiplier,
    }

    return OpportunityDimension(
        dimension_id="public_goods_funding",
        dimension_name="Public-Goods Funding Loops",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="high" if actual > 0 else "low",
        current_state=f"Allocated: ${actual:,.0f} ({allocation_rate:.1f}% of revenue), forecast: ${forecasted:,.0f}",
        recommendation=f"Increase allocation to 15% for +${revenue * 0.05 * (loop_multiplier - 1):,.0f} loop value",
        data_points=2,
        details=details,
    )
