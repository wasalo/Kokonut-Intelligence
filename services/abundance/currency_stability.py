"""Currency stability model — monitoring and suggestions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.currency_stability")


def compute_value_stability(conn, period_start: str, period_end: str, location_id: str = None) -> Dict[str, Any]:
    """Measure coin value vs economic capacity.

    Since we model stability without deploying a token, we estimate
    value from economic indicators.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Total coins issued
    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total_issued FROM coin_inflation_event WHERE status = 'issued'")
    total_issued = float(cur.fetchone()["total_issued"] or 0)

    # Total impact validated
    cur.execute("SELECT COALESCE(SUM(basis_impact_score), 0) AS total_impact FROM coin_inflation_event WHERE status = 'issued'")
    total_impact = float(cur.fetchone()["total_impact"] or 0)

    # Economic capacity estimate (from revenue + natural capital)
    cur.execute("""
        SELECT COALESCE(SUM(re.amount), 0) AS total_revenue
        FROM revenue_event re
        WHERE re.location_id = COALESCE(%s, re.location_id)
    """, (location_id,))
    revenue = float(cur.fetchone()["total_revenue"] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(total_value_usd), 0) AS natural_capital
        FROM natural_capital_valuation
        WHERE location_id = COALESCE(%s, location_id)
    """, (location_id,))
    nc = float(cur.fetchone()["natural_capital"] or 0)

    economic_capacity = revenue + nc

    # Inflation schedule
    cur.execute("SELECT * FROM inflation_schedule WHERE status = 'active' LIMIT 1")
    schedule = cur.fetchone()
    inflation_rate = float(schedule["initial_inflation_rate"]) if schedule else 0
    target_growth = float(schedule["target_value_growth_pct"]) if schedule else 0

    # Compute metrics
    if total_impact > 0:
        coins_per_capacity = total_issued / economic_capacity if economic_capacity > 0 else 0
    else:
        coins_per_capacity = 0

    # Deviation from target (should be ~0 if inflation matches growth)
    deviation = inflation_rate - (target_growth / 100) if target_growth else 0

    cur.execute("""
        INSERT INTO value_stability_metric
            (location_id, period_start, period_end, coin_value_estimate,
             economic_capacity_estimate, coins_per_capacity_ratio,
             inflation_rate, economic_growth_rate, deviation_from_target,
             target_value_growth_pct)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        location_id, period_start, period_end,
        total_issued / max(total_impact, 1),  # Coin value per impact
        economic_capacity, coins_per_capacity,
        inflation_rate, target_growth / 100, deviation, target_growth,
    ))
    metric_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    return {
        "metric_id": metric_id,
        "total_coins_issued": round(total_issued, 8),
        "total_impact_validated": round(total_impact, 4),
        "economic_capacity": round(economic_capacity, 2),
        "coins_per_capacity": round(coins_per_capacity, 6),
        "inflation_rate": inflation_rate,
        "target_growth_pct": target_growth,
        "deviation": round(deviation, 6),
    }


def suggest_inflation_adjustment(conn) -> Dict[str, Any]:
    """Recommend inflation rate changes to maintain value stability."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get latest stability metric
    cur.execute("""
        SELECT * FROM value_stability_metric
        ORDER BY computed_at DESC LIMIT 1
    """)
    metric = cur.fetchone()

    if not metric:
        cur.close()
        return {"status": "error", "message": "No stability metrics computed"}

    metric = dict(metric)
    deviation = float(metric.get("deviation_from_target", 0) or 0)
    current_rate = float(metric.get("inflation_rate", 0) or 0)
    target_growth = float(metric.get("target_value_growth_pct", 0) or 0)

    # Suggest adjustment: if inflation > growth, reduce rate; if inflation < growth, increase
    if abs(deviation) < 0.01:
        suggestion = "maintain"
        new_rate = current_rate
    elif deviation > 0:
        # Inflation too high — reduce rate
        new_rate = max(0.001, current_rate - abs(deviation) * 0.5)
        suggestion = "decrease"
    else:
        # Inflation too low — increase rate
        new_rate = current_rate + abs(deviation) * 0.5
        suggestion = "increase"

    return {
        "current_rate": current_rate,
        "target_growth_pct": target_growth,
        "deviation": round(deviation, 6),
        "suggestion": suggestion,
        "suggested_rate": round(new_rate, 6),
        "adjustment_needed": abs(deviation) > 0.01,
    }


def track_supply_metrics(conn) -> Dict[str, Any]:
    """Track total supply, circulation, and burn rate."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total_issued FROM coin_inflation_event WHERE status = 'issued'")
    total = float(cur.fetchone()["total_issued"] or 0)

    cur.execute("SELECT COUNT(*) AS events FROM coin_inflation_event WHERE status = 'issued'")
    events = int(cur.fetchone()["events"] or 0)

    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total_retired FROM credit_retirement WHERE status = 'published'")
    retired = float(cur.fetchone()["total_retired"] or 0)

    cur.close()

    return {
        "total_issued": round(total, 8),
        "issuance_events": events,
        "total_retired": round(retired, 8),
        "net_supply": round(total - retired, 8),
    }


def compute_economic_capacity(conn, location_id: str = None) -> Dict[str, Any]:
    """Estimate ecosystem economic capacity from revenue + natural capital."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT COALESCE(SUM(re.amount), 0) AS revenue
        FROM revenue_event re
        WHERE re.location_id = COALESCE(%s, re.location_id)
    """, (location_id,))
    rev = float(cur.fetchone()["revenue"] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(total_value_usd), 0) AS natural_capital
        FROM natural_capital_valuation
        WHERE location_id = COALESCE(%s, location_id)
    """, (location_id,))
    nc = float(cur.fetchone()["natural_capital"] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(estimated_value_usd), 0) AS social_capital
        FROM social_impact_valuation
        WHERE location_id = COALESCE(%s, location_id)
    """, (location_id,))
    sc = float(cur.fetchone()["social_capital"] or 0)

    cur.close()

    return {
        "revenue": round(rev, 2),
        "natural_capital": round(nc, 2),
        "social_capital": round(sc, 2),
        "total_economic_capacity": round(rev + nc + sc, 2),
    }
