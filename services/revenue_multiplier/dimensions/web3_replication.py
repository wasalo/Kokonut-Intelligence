"""
Web3-Funded Replication — Dimension 5

Analyzes on-chain funding, cost of capital, and replication model viability.
"""

import psycopg2.extras
from ..models import OpportunityDimension


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get treasury events
    cur.execute("""
        SELECT
            flow_direction,
            SUM(usd_value) as total_value,
            COUNT(*) as event_count
        FROM treasury_event
        WHERE location_id = %s
        GROUP BY flow_direction
    """, (location_id,))
    treasury = {r["flow_direction"]: float(r["total_value"]) for r in cur.fetchall()}

    # Get digital lego usage
    cur.execute("""
        SELECT
            protocol_id,
            SUM(value_attributed) as total_value,
            COUNT(*) as usage_count
        FROM digital_lego_usage
        WHERE location_id = %s
        GROUP BY protocol_id
    """, (location_id,))
    lego = [dict(r) for r in cur.fetchall()]

    # Get capital sources
    cur.execute("""
        SELECT source_type, SUM(amount) as total_amount
        FROM capital_source
        GROUP BY source_type
    """, (location_id,))
    capital = {r["source_type"]: float(r["total_amount"]) for r in cur.fetchall()}

    # Get value flows
    cur.execute("""
        SELECT flow_type, SUM(amount) as total_amount
        FROM value_flow_event
        WHERE location_id = %s AND verified = TRUE
        GROUP BY flow_type
    """, (location_id,))
    flows = {r["flow_type"]: float(r["total_amount"]) for r in cur.fetchall()}

    cur.close()

    # Calculate Web3 metrics
    inflows = treasury.get("inflow", 0) + sum(capital.values())
    outflows = treasury.get("outflow", 0)
    net_funding = inflows - outflows
    dao_share = capital.get("dao", 0) / max(inflows, 1) * 100
    lego_value = sum(l["total_value"] for l in lego)

    # Score: more funding sources = higher score
    funding_sources = len(capital)
    score = min(100, funding_sources * 20 + (1 if net_funding > 0 else 0) * 20)

    # Impact: replication cost estimate (assume $15,000 per new farm)
    REPLICATION_COST = 15000
    farms_replicable = net_funding / REPLICATION_COST if net_funding > REPLICATION_COST else 0

    details = {
        "treasury": treasury,
        "capital_sources": capital,
        "value_flows": flows,
        "lego_usage": lego,
        "net_funding": round(net_funding, 2),
        "dao_share_pct": round(dao_share, 1),
        "farms_replicable": round(farms_replicable, 1),
    }

    return OpportunityDimension(
        dimension_id="web3_funded_replication",
        dimension_name="Web3-Funded Replication",
        score=round(score, 1),
        impact_usd=round(farms_replicable * REPLICATION_COST, 2),
        confidence="medium",
        current_state=f"Inflows: ${inflows:,.0f}, DAO: {dao_share:.0f}%, Lego value: ${lego_value:,.0f}",
        recommendation=f"Scale to {farms_replicable:.0f} additional farms via DAO funding",
        data_points=len(lego) + len(capital),
        details=details,
    )
