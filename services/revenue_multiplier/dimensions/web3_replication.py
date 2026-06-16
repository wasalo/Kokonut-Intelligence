"""
Web3-Funded Replication — Dimension 5

Evaluates capital sources and funding for farm expansion.
Analyzes treasury reserves, grants, DeFi protocols, and token launches.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get capital sources
    cur.execute("""
        SELECT
            cs.source_type,
            cs.amount,
            cs.status,
            cs.name
        FROM capital_source cs
        WHERE cs.location_id = %s AND cs.status IN ('active', 'completed', 'received')
    """, (location_id,))
    sources = [dict(r) for r in cur.fetchall()]

    # Get capital events
    cur.execute("""
        SELECT
            ce.event_type,
            ce.amount,
            ce.status
        FROM capital_event ce
        WHERE ce.location_id = %s
    """, (location_id,))
    events = [dict(r) for r in cur.fetchall()]

    # Get digital lego usage (DeFi, token, attestations)
    cur.execute("""
        SELECT
            dl.protocol,
            dl.amount,
            dl.status
        FROM digital_lego_usage dl
        WHERE dl.location_id = %s AND dl.status IN ('active', 'completed')
    """, (location_id,))
    defi = [dict(r) for r in cur.fetchall()]

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

    # Capital composition
    source_types = {}
    total_capital = 0
    for src in sources:
        t = src["source_type"]
        amt = float(src["amount"] or 0)
        source_types[t] = source_types.get(t, 0) + amt
        total_capital += amt

    # Event-based capital
    for evt in events:
        amt = float(evt["amount"] or 0)
        total_capital += amt

    # DeFi-based capital
    defi_count = len(defi)
    total_defi = sum(float(d["amount"] or 0) for d in defi)

    # Replication cost from config
    replication_cost = float(get_config(conn, 'replication_cost_usd'))
    loop_multiplier = float(get_config(conn, 'loop_multiplier'))
    funding_sources_multiplier = float(get_config(conn, 'web3_funding_sources_multiplier'))
    funding_bonus = float(get_config(conn, 'web3_funding_bonus'))

    # Score: based on funding diversity and amount
    score = min(100, max(0, len(source_types) * funding_sources_multiplier))

    # Bonus for positive net funding
    if total_capital > replication_cost:
        score += funding_bonus
        score = min(100, score)

    # Impact: how many farms could be funded
    farms_funded = total_capital / max(replication_cost, 1)
    if farms_funded > 1:
        impact = (farms_funded - 1) * loop_multiplier * replication_cost
    else:
        impact = 0

    # Forecast-adjusted impact
    forecast_impact = 0
    if forecast_revenue > 0:
        savings_for_replication = forecast_revenue * 0.05  # 5% savings
        forecast_impact = savings_for_replication * loop_multiplier

    details = {
        "total_capital_raised": round(total_capital, 2),
        "capital_by_type": {k: round(v, 2) for k, v in source_types.items()},
        "defi_protocols": defi_count,
        "defi_total_value": round(total_defi, 2),
        "replication_cost": replication_cost,
        "loop_multiplier": loop_multiplier,
        "farms_funded": round(farms_funded, 1),
        "forecast_impact_usd": round(forecast_impact, 2),
    }

    impact = max(impact, forecast_impact)

    return OpportunityDimension(
        dimension_id="web3_funded_replication",
        dimension_name="Web3-Funded Replication",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="medium" if sources else "low",
        current_state=f"${total_capital:,.0f} raised, {len(source_types)} sources, {farms_funded:.1f} farms",
        recommendation=f"Raise ${replication_cost - total_capital:,.0f} more for 1 full farm replication" if total_capital < replication_cost else f"Ready to replicate {farms_funded:.0f} farms",
        data_points=len(sources) + len(events) + len(defi),
        details=details,
    )


def _empty(dim_id, dim_name):
    return OpportunityDimension(
        dimension_id=dim_id, dimension_name=dim_name,
        score=0, impact_usd=0, confidence="low",
        current_state="No capital sources", recommendation="Set up treasury and capital tracking",
        data_points=0,
    )
