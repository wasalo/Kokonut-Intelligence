"""True Cost Accounting analytics: hidden costs, natural capital, social impact, human capital."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_true_cost_statement(conn, location_id: str) -> dict[str, Any]:
    """Compute true cost statement: market costs + hidden costs + capital values.

    Returns:
    - market_costs_usd: Total operating expenses
    - market_revenue_usd: Total revenue
    - market_profit_usd: Revenue - Costs
    - hidden_costs_usd: Sum of all hidden cost observations
    - natural_capital_value_usd: Sum of all natural capital valuations
    - social_capital_value_usd: Sum of all social impact valuations
    - true_profit_usd: Market profit - hidden costs + capital values
    """
    cur = conn.cursor()

    # Market costs
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expense_event WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    market_costs = float(cur.fetchone()[0] or 0)

    # Market revenue
    cur.execute(
        "SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_event WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    market_revenue = float(cur.fetchone()[0] or 0)

    # Hidden costs
    cur.execute(
        "SELECT COALESCE(SUM(monetary_estimate_usd), 0) FROM hidden_cost_observation WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    hidden_costs = float(cur.fetchone()[0] or 0)

    # Natural capital value
    cur.execute(
        "SELECT COALESCE(SUM(total_value_usd), 0) FROM natural_capital_valuation WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    natural_capital = float(cur.fetchone()[0] or 0)

    # Social capital value
    cur.execute(
        "SELECT COALESCE(SUM(monetary_value_usd), 0) FROM social_impact_valuation WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    social_capital = float(cur.fetchone()[0] or 0)

    cur.close()

    market_profit = market_revenue - market_costs
    true_profit = market_profit - hidden_costs + natural_capital + social_capital

    result = {
        "location_id": location_id,
        "market_costs_usd": round(market_costs, 2),
        "market_revenue_usd": round(market_revenue, 2),
        "market_profit_usd": round(market_profit, 2),
        "hidden_costs_usd": round(hidden_costs, 2),
        "natural_capital_value_usd": round(natural_capital, 2),
        "social_capital_value_usd": round(social_capital, 2),
        "true_profit_usd": round(true_profit, 2),
        "true_profit_margin_pct": round(true_profit / market_revenue * 100, 1) if market_revenue > 0 else 0,
        "hidden_cost_ratio_pct": round(hidden_costs / market_profit * 100, 1) if market_profit > 0 else 0,
    }

    logger.info("True cost statement for %s: market profit $%.2f, true profit $%.2f",
                location_id, market_profit, true_profit)
    return result


def compute_hidden_cost_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize hidden costs by category and subcategory."""
    cur = conn.cursor()

    # By category
    cur.execute(
        """
        SELECT cost_category, cost_subcategory,
               COUNT(*) AS count, SUM(monetary_estimate_usd) AS total_usd,
               AVG(monetary_estimate_usd) AS avg_usd
        FROM hidden_cost_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY cost_category, cost_subcategory
        ORDER BY total_usd DESC
        """,
        (location_id,),
    )
    costs = [
        {
            "category": r[0],
            "subcategory": r[1],
            "count": r[2],
            "total_usd": round(float(r[3]), 2),
            "avg_usd": round(float(r[4]), 2),
        }
        for r in cur.fetchall()
    ]

    # Totals
    cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(monetary_estimate_usd), 0) FROM hidden_cost_observation WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    totals = cur.fetchone()
    cur.close()

    # Aggregate by category
    categories: dict[str, float] = {}
    for cost in costs:
        categories[cost["category"]] = categories.get(cost["category"], 0) + cost["total_usd"]

    result = {
        "location_id": location_id,
        "total_hidden_costs_usd": round(float(totals[1]), 2),
        "total_observations": totals[0],
        "by_category": [
            {"category": k, "total_usd": round(v, 2)}
            for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)
        ],
        "details": costs,
    }

    logger.info("Hidden costs for %s: $%.2f across %d observations",
                location_id, result["total_hidden_costs_usd"], result["total_observations"])
    return result


def compute_natural_capital_valuation(conn, location_id: str) -> dict[str, Any]:
    """Summarize natural capital valuation by type."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT capital_type, COUNT(*) AS count,
               SUM(quantity) AS total_quantity,
               AVG(price_per_unit_usd) AS avg_price,
               SUM(total_value_usd) AS total_value
        FROM natural_capital_valuation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY capital_type
        ORDER BY total_value DESC
        """,
        (location_id,),
    )
    capitals = [
        {
            "capital_type": r[0],
            "count": r[1],
            "total_quantity": round(float(r[2]), 2),
            "avg_price_per_unit": round(float(r[3]), 2),
            "total_value_usd": round(float(r[4]), 2),
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        "SELECT COALESCE(SUM(total_value_usd), 0) FROM natural_capital_valuation WHERE location_id = %s AND status IN ('verified', 'published')",
        (location_id,),
    )
    total = float(cur.fetchone()[0] or 0)
    cur.close()

    result = {
        "location_id": location_id,
        "total_natural_capital_value_usd": round(total, 2),
        "by_type": capitals,
    }

    logger.info("Natural capital for %s: $%.2f", location_id, total)
    return result


def compute_social_impact_valuation(conn, location_id: str) -> dict[str, Any]:
    """Summarize social impact valuation by category."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT impact_category, COUNT(*) AS count,
               SUM(beneficiaries_count) AS total_beneficiaries,
               SUM(monetary_value_usd) AS total_value,
               AVG(monetary_value_usd) AS avg_value
        FROM social_impact_valuation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY impact_category
        ORDER BY total_value DESC
        """,
        (location_id,),
    )
    impacts = [
        {
            "category": r[0],
            "count": r[1],
            "total_beneficiaries": r[2],
            "total_value_usd": round(float(r[4]), 2),
            "avg_value_per_intervention": round(float(r[4]) / r[1], 2) if r[1] > 0 else 0,
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT COALESCE(SUM(monetary_value_usd), 0), COALESCE(SUM(beneficiaries_count), 0)
        FROM social_impact_valuation
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    totals = cur.fetchone()
    cur.close()

    result = {
        "location_id": location_id,
        "total_social_impact_value_usd": round(float(totals[0]), 2),
        "total_beneficiaries": totals[1],
        "by_category": impacts,
    }

    logger.info("Social impact for %s: $%.2f, %d beneficiaries",
                location_id, result["total_social_impact_value_usd"], result["total_beneficiaries"])
    return result


def compute_human_capital_score(conn, location_id: str) -> dict[str, Any]:
    """Compute human capital score (0-100) from training, safety, and wages."""
    cur = conn.cursor()

    # Training score (0-25): based on training hours and improvement
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(duration_hours), 0), COALESCE(AVG(improvement_pct), 0)
        FROM training_session
        WHERE location_id = %s AND status = 'published'
        """,
        (location_id,),
    )
    training = cur.fetchone()
    training_sessions = training[0] or 0
    training_hours = float(training[1] or 0)
    training_improvement = float(training[2] or 0)
    training_score = min(25, (training_sessions * 3) + (training_hours * 0.5) + (training_improvement * 0.1))

    # Safety score (0-25): fewer incidents = higher score
    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE severity IN ('serious', 'critical')),
               COUNT(*) FILTER (WHERE severity = 'moderate')
        FROM worker_safety_observation
        WHERE location_id = %s AND status IN ('resolved', 'closed')
        """,
        (location_id,),
    )
    safety = cur.fetchone()
    serious_incidents = safety[0] or 0
    moderate_incidents = safety[1] or 0
    safety_score = max(0, 25 - (serious_incidents * 10) - (moderate_incidents * 3))

    # Wage score (0-25): living wage ratio
    cur.execute(
        "SELECT living_wage_hourly_usd FROM living_wage_benchmark WHERE location_id = %s AND status = 'active' LIMIT 1",
        (location_id,),
    )
    lw_row = cur.fetchone()
    living_wage = float(lw_row[0]) if lw_row else 5.0

    cur.execute(
        "SELECT COALESCE(AVG(hourly_rate), 0) FROM labor_event WHERE location_id = %s AND status = 'published'",
        (location_id,),
    )
    avg_wage = float(cur.fetchone()[0] or 0)
    wage_ratio = avg_wage / living_wage if living_wage > 0 else 0
    wage_score = min(25, wage_ratio * 25)

    # Wellbeing score (0-25): based on wellbeing observations
    cur.execute(
        """
        SELECT COALESCE(AVG(assessment_score), 5)
        FROM wellbeing_metric_observation
        WHERE location_id = %s AND status = 'published'
        """,
        (location_id,),
    )
    wellbeing = cur.fetchone()
    wellbeing_score = min(25, float(wellbeing[0] or 5) * 2.5)

    cur.close()

    total_score = round(training_score + safety_score + wage_score + wellbeing_score, 1)

    result = {
        "location_id": location_id,
        "human_capital_score": min(100, total_score),
        "components": {
            "training_score": round(training_score, 1),
            "safety_score": round(safety_score, 1),
            "wage_score": round(wage_score, 1),
            "wellbeing_score": round(wellbeing_score, 1),
        },
        "training_sessions": training_sessions,
        "training_hours": training_hours,
        "training_improvement_pct": round(training_improvement, 1),
        "serious_safety_incidents": serious_incidents,
        "living_wage_ratio": round(wage_ratio, 2),
    }

    logger.info("Human capital score for %s: %.1f/100", location_id, result["human_capital_score"])
    return result
