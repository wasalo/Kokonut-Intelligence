"""Systems Thinking analytics: capital flows, cross-capital dependencies, resilience."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_capital_flow_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize capital flows between natural, human, social, produced, financial."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT from_capital, to_capital, flow_type,
               COUNT(*) AS count, SUM(flow_value_usd) AS total_value
        FROM capital_flow_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY from_capital, to_capital, flow_type
        ORDER BY total_value DESC
        """,
        (location_id,),
    )
    flows = [
        {
            "from_capital": r[0],
            "to_capital": r[1],
            "flow_type": r[2],
            "count": r[3],
            "total_value_usd": round(float(r[4]), 2),
        }
        for r in cur.fetchall()
    ]

    # Summaries by capital
    cur.execute(
        """
        SELECT from_capital, SUM(flow_value_usd) AS invested
        FROM capital_flow_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND flow_type = 'investment'
        GROUP BY from_capital
        """,
        (location_id,),
    )
    investments = {r[0]: round(float(r[1]), 2) for r in cur.fetchall()}

    cur.execute(
        """
        SELECT to_capital, SUM(flow_value_usd) AS received
        FROM capital_flow_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND flow_type IN ('regeneration', 'transfer')
        GROUP BY to_capital
        """,
        (location_id,),
    )
    returns = {r[0]: round(float(r[1]), 2) for r in cur.fetchall()}

    cur.close()

    total_flows = len(flows)
    total_value = sum(f["total_value_usd"] for f in flows)

    result = {
        "location_id": location_id,
        "total_flows": total_flows,
        "total_flow_value_usd": round(total_value, 2),
        "flows": flows,
        "investments_by_capital": investments,
        "returns_by_capital": returns,
    }

    logger.info("Capital flows for %s: %d flows, $%.2f total", location_id, total_flows, total_value)
    return result


def compute_cross_capital_dependencies(conn, location_id: str) -> dict[str, Any]:
    """Compute cross-capital dependencies — how investment in one capital affects others."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT from_capital, to_capital, flow_type,
               SUM(flow_value_usd) AS total_value
        FROM capital_flow_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY from_capital, to_capital, flow_type
        """,
        (location_id,),
    )
    flows = cur.fetchall()
    cur.close()

    # Build dependency matrix
    capitals = ["natural", "human", "social", "produced", "financial"]
    matrix: dict[str, dict[str, float]] = {c: {c2: 0 for c2 in capitals} for c in capitals}

    for row in flows:
        matrix[row[0]][row[1]] = round(float(row[3]), 2)

    # Compute interdependency score
    # Higher score = more cross-capital investment
    cross_capital_value = 0
    for f in capitals:
        for t in capitals:
            if f != t and matrix[f][t] > 0:
                cross_capital_value += matrix[f][t]

    total_value = sum(matrix[f][t] for f in capitals for t in capitals)
    interdependency_ratio = cross_capital_value / total_value if total_value > 0 else 0

    # Find key dependencies
    key_dependencies = []
    for f in capitals:
        for t in capitals:
            if f != t and matrix[f][t] > 0:
                key_dependencies.append({
                    "from": f,
                    "to": t,
                    "value_usd": matrix[f][t],
                })
    key_dependencies.sort(key=lambda x: x["value_usd"], reverse=True)

    result = {
        "location_id": location_id,
        "dependency_matrix": matrix,
        "cross_capital_value_usd": round(cross_capital_value, 2),
        "interdependency_ratio": round(interdependency_ratio, 4),
        "key_dependencies": key_dependencies[:5],
        "interdependency_score": round(interdependency_ratio * 100, 1),
    }

    logger.info("Cross-capital dependencies for %s: ratio %.4f", location_id, interdependency_ratio)
    return result


def compute_system_resilience(conn, location_id: str) -> dict[str, Any]:
    """Compute system resilience score across all capitals.

    Resilience is measured by:
    - Capital diversity (are multiple capitals present?)
    - Capital balance (are capitals balanced?)
    - Investment flow (is there active investment across capitals?)
    - Feedback loops (do capitals reinforce each other?)
    """
    cur = conn.cursor()

    # Natural capital score (0-25)
    cur.execute(
        "SELECT COALESCE(COUNT(DISTINCT capital_type), 0) FROM natural_capital_valuation WHERE location_id = %s AND status = 'published'",
        (location_id,),
    )
    nc_types = cur.fetchone()[0] or 0
    natural_score = min(25, nc_types * 6)

    # Human capital score (0-25)
    cur.execute(
        "SELECT COALESCE(COUNT(*), 0) FROM training_session WHERE location_id = %s AND status = 'published'",
        (location_id,),
    )
    training_count = cur.fetchone()[0] or 0
    cur.execute(
        "SELECT COALESCE(COUNT(*), 0) FROM staff WHERE location_id = %s AND is_active = TRUE",
        (location_id,),
    )
    staff_count = cur.fetchone()[0] or 0
    human_score = min(25, (training_count * 3) + (staff_count * 2))

    # Social capital score (0-25)
    cur.execute(
        "SELECT COALESCE(COUNT(DISTINCT impact_category), 0) FROM social_impact_valuation WHERE location_id = %s AND status = 'published'",
        (location_id,),
    )
    social_types = cur.fetchone()[0] or 0
    cur.execute(
        "SELECT COALESCE(COUNT(*), 0) FROM community_governance_mechanism WHERE location_id = %s AND status = 'published'",
        (location_id,),
    )
    governance_count = cur.fetchone()[0] or 0
    social_score = min(25, (social_types * 5) + (governance_count * 3))

    # Produced/Financial capital score (0-25)
    cur.execute(
        "SELECT COALESCE(COUNT(*), 0) FROM infrastructure_asset WHERE location_id = %s AND status = 'active'",
        (location_id,),
    )
    asset_count = cur.fetchone()[0] or 0
    cur.execute(
        "SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_event WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    revenue = float(cur.fetchone()[0] or 0)
    produced_score = min(25, (asset_count * 3) + (1 if revenue > 0 else 0) * 10)

    # Flow score (0-25): capital flow diversity
    cur.execute(
        "SELECT COALESCE(COUNT(DISTINCT from_capital || '->' || to_capital), 0) FROM capital_flow_observation WHERE location_id = %s AND status = 'published'",
        (location_id,),
    )
    flow_diversity = cur.fetchone()[0] or 0
    flow_score = min(25, flow_diversity * 5)

    cur.close()

    total_score = natural_score + human_score + social_score + produced_score + flow_score

    if total_score >= 80:
        status = "highly_resilient"
    elif total_score >= 60:
        status = "resilient"
    elif total_score >= 40:
        status = "moderately_resilient"
    elif total_score >= 20:
        status = "vulnerable"
    else:
        status = "critical"

    result = {
        "location_id": location_id,
        "system_resilience_score": round(total_score, 1),
        "status": status,
        "components": {
            "natural_capital_score": round(natural_score, 1),
            "human_capital_score": round(human_score, 1),
            "social_capital_score": round(social_score, 1),
            "produced_capital_score": round(produced_score, 1),
            "flow_score": round(flow_score, 1),
        },
        "capital_diversity": {
            "natural_capital_types": nc_types,
            "training_sessions": training_count,
            "social_impact_categories": social_types,
            "governance_mechanisms": governance_count,
            "infrastructure_assets": asset_count,
            "capital_flow_diversity": flow_diversity,
        },
    }

    logger.info("System resilience for %s: %.1f/100 (%s)", location_id, total_score, status)
    return result
