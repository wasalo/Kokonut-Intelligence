"""Financial viability risk scoring module.

Adapted from SW-CRISP Section 4.  Estimates vintage-specific financial risk
using break-even analysis, revenue sustainability, cost structure, and
liquidity indicators.

Scoring approach:
1. Query financial sustainability plan, unit economics, revenue/expense data
2. Compute revenue risk, cost risk, market price risk, liquidity risk
3. Combine into composite financial risk factor (0-1)
4. Convert to 0-100 risk score
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

from .models import DimensionScore
from .normalization import clamp_risk_score


def _query_financial_sustainability(conn, location_id: str) -> Dict[str, Any]:
    """Get financial sustainability plan data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            status,
            revenue_streams,
            grant_dependency_pct,
            reinvestment_pct,
            break_even_month,
            runway_months,
            noi_projection_y1,
            noi_projection_y2,
            noi_projection_y3
        FROM financial_sustainability_plan
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_unit_economics(conn, location_id: str) -> Dict[str, Any]:
    """Get farm launch unit economics."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            cost_per_hectare_usd,
            cost_per_farm_usd,
            roi_pct,
            payback_months,
            break_even_month
        FROM farm_launch_unit_economics
        WHERE location_id = %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_revenue_summary(conn, location_id: str) -> Dict[str, Any]:
    """Aggregate revenue events."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS revenue_count,
            COALESCE(SUM(amount), 0) AS total_revenue,
            COALESCE(AVG(amount), 0) AS avg_revenue,
            COALESCE(STDDEV(amount), 0) AS revenue_stddev
        FROM revenue_event
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_expense_summary(conn, location_id: str) -> Dict[str, Any]:
    """Aggregate expense events."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS expense_count,
            COALESCE(SUM(amount), 0) AS total_expense,
            COALESCE(AVG(amount), 0) AS avg_expense,
            COALESCE(SUM(CASE WHEN category = 'labor' THEN amount ELSE 0 END), 0) AS labor_cost,
            COALESCE(SUM(CASE WHEN category = 'inputs' THEN amount ELSE 0 END), 0) AS input_cost
        FROM expense_event
        WHERE location_id = %s
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _compute_revenue_risk(
    revenue: Dict[str, Any],
    sustainability: Dict[str, Any],
) -> float:
    """Compute revenue risk factor (0-1, higher = more risk).

    Factors: revenue diversity, grant dependency, revenue volatility.
    """
    scores = []

    # Grant dependency risk
    grant_dep = float(sustainability.get("grant_dependency_pct", 50) or 50)
    if grant_dep > 80:
        scores.append(0.9)
    elif grant_dep > 60:
        scores.append(0.7)
    elif grant_dep > 40:
        scores.append(0.5)
    elif grant_dep > 20:
        scores.append(0.3)
    else:
        scores.append(0.1)

    # Revenue volatility (coefficient of variation)
    total = float(revenue.get("total_revenue", 0) or 0)
    stddev = float(revenue.get("revenue_stddev", 0) or 0)
    if total > 0 and stddev > 0:
        cv = stddev / (total / max(1, int(revenue.get("revenue_count", 1) or 1)))
        scores.append(min(1.0, cv))
    else:
        scores.append(0.5)  # Unknown = moderate

    # Revenue stream count
    streams = sustainability.get("revenue_streams", [])
    if isinstance(streams, list):
        stream_count = len(streams)
    elif streams:
        stream_count = 1
    else:
        stream_count = 0
    if stream_count > 3:
        scores.append(0.1)
    elif stream_count > 1:
        scores.append(0.3)
    elif stream_count == 1:
        scores.append(0.6)
    else:
        scores.append(0.8)

    return sum(scores) / len(scores) if scores else 0.5


def _compute_cost_risk(
    expense: Dict[str, Any],
    unit_economics: Dict[str, Any],
) -> float:
    """Compute cost risk factor (0-1, higher = more risk)."""
    scores = []

    # Cost overrun risk from payback period
    payback = float(unit_economics.get("payback_months", 36) or 36)
    if payback > 48:
        scores.append(0.8)
    elif payback > 36:
        scores.append(0.6)
    elif payback > 24:
        scores.append(0.4)
    elif payback > 12:
        scores.append(0.2)
    else:
        scores.append(0.1)

    # Labor + input cost as proportion of total
    total_exp = float(expense.get("total_expense", 0) or 0)
    labor = float(expense.get("labor_cost", 0) or 0)
    inputs = float(expense.get("input_cost", 0) or 0)
    if total_exp > 0:
        cost_concentration = (labor + inputs) / total_exp
        if cost_concentration > 0.8:
            scores.append(0.7)
        elif cost_concentration > 0.6:
            scores.append(0.5)
        else:
            scores.append(0.3)
    else:
        scores.append(0.5)

    return sum(scores) / len(scores) if scores else 0.5


def _compute_liquidity_risk(sustainability: Dict[str, Any]) -> float:
    """Compute liquidity risk factor (0-1, higher = more risk)."""
    runway = float(sustainability.get("runway_months", 12) or 12)
    if runway < 3:
        return 0.9
    elif runway < 6:
        return 0.7
    elif runway < 12:
        return 0.5
    elif runway < 24:
        return 0.3
    else:
        return 0.1


def _compute_market_price_risk(revenue: Dict[str, Any]) -> float:
    """Estimate market price risk from revenue volatility."""
    total = float(revenue.get("total_revenue", 0) or 0)
    count = int(revenue.get("revenue_count", 0) or 0)
    stddev = float(revenue.get("revenue_stddev", 0) or 0)

    if count < 3 or total == 0:
        return 0.5  # Insufficient data

    # Coefficient of variation as proxy for price instability
    avg = total / count
    if avg > 0:
        cv = stddev / avg
        return min(1.0, cv * 2)
    return 0.5


def compute_financial_risk(
    conn,
    location_id: str,
    vintage_year: Optional[int] = None,
) -> DimensionScore:
    """Compute financial viability risk score for a location.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        vintage_year: Optional vintage year for vintage-specific risk.

    Returns:
        DimensionScore with risk_score 0-100 (higher = more risk).
    """
    sustainability = _query_financial_sustainability(conn, location_id)
    unit_economics = _query_unit_economics(conn, location_id)
    revenue = _query_revenue_summary(conn, location_id)
    expense = _query_expense_summary(conn, location_id)

    revenue_risk = _compute_revenue_risk(revenue, sustainability)
    cost_risk = _compute_cost_risk(expense, unit_economics)
    liquidity_risk = _compute_liquidity_risk(sustainability)
    market_price_risk = _compute_market_price_risk(revenue)

    # Composite financial risk factor
    financial_risk_factor = (
        revenue_risk * 0.35
        + cost_risk * 0.25
        + liquidity_risk * 0.25
        + market_price_risk * 0.15
    )

    risk_score = clamp_risk_score(financial_risk_factor * 100)

    # Break-even estimation
    break_even = sustainability.get("break_even_month") or unit_economics.get("break_even_month")

    # Evidence maturity
    evidence_level = 1
    if sustainability:
        evidence_level = 3
    if unit_economics:
        evidence_level = min(evidence_level + 1, 6)
    if int(revenue.get("revenue_count", 0) or 0) > 0:
        evidence_level = min(evidence_level + 1, 6)

    from .config import CONFIDENCE_THRESHOLDS
    confidence = CONFIDENCE_THRESHOLDS.get(evidence_level, "insufficient_evidence")

    factors = {
        "revenue_risk": round(revenue_risk, 4),
        "cost_risk": round(cost_risk, 4),
        "liquidity_risk": round(liquidity_risk, 4),
        "market_price_risk": round(market_price_risk, 4),
        "financial_risk_factor": round(financial_risk_factor, 4),
        "grant_dependency_pct": float(sustainability.get("grant_dependency_pct", 0) or 0),
        "runway_months": float(sustainability.get("runway_months", 0) or 0),
        "break_even_month": break_even,
        "payback_months": unit_economics.get("payback_months"),
        "total_revenue": float(revenue.get("total_revenue", 0) or 0),
        "total_expense": float(expense.get("total_expense", 0) or 0),
    }

    return DimensionScore(
        dimension_key="financial",
        dimension_name="Financial Viability Risk",
        risk_score=clamp_risk_score(risk_score),
        confidence_level=confidence,
        evidence_maturity_level=evidence_level,
        weight=0.0,
        factors=factors,
        evidence_summary=f"Financial risk factor {financial_risk_factor:.2f} (revenue={revenue_risk:.2f}, cost={cost_risk:.2f}, liquidity={liquidity_risk:.2f}, market={market_price_risk:.2f})",
    )
