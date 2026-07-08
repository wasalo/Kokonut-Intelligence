"""IRR/NPV Calculator: Internal Rate of Return, Net Present Value, Modified IRR."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_irr(cash_flows: list[float], guess: float = 0.1, max_iterations: int = 1000, tolerance: float = 1e-8) -> float | None:
    """Compute Internal Rate of Return using Newton-Raphson method.

    Args:
        cash_flows: List of cash flows where index 0 is the initial investment (negative).
                    Example: [-50000, 12000, 15000, 18000]
        guess: Initial guess for IRR (default 10%)
        max_iterations: Maximum Newton-Raphson iterations
        tolerance: Convergence tolerance

    Returns:
        IRR as a decimal (e.g., 0.12 for 12%), or None if no convergence.
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    rate = guess
    for _ in range(max_iterations):
        npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
        dnpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))

        if abs(dnpv) < tolerance:
            break

        rate -= npv / dnpv

    # Validate convergence
    final_npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
    if abs(final_npv) > 1e-6:
        return None  # Did not converge

    return rate


def compute_npv(cash_flows: list[float], discount_rate: float) -> float:
    """Compute Net Present Value at a given discount rate.

    Args:
        cash_flows: List of cash flows where index 0 is the initial investment.
        discount_rate: Discount rate as a decimal (e.g., 0.08 for 8%).

    Returns:
        NPV value.
    """
    return sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(cash_flows))


def compute_mirr(cash_flows: list[float], finance_rate: float = 0.08, reinvestment_rate: float = 0.08) -> float | None:
    """Compute Modified IRR separating finance and reinvestment rates.

    Args:
        cash_flows: List of cash flows.
        finance_rate: Rate for financing negative cash flows.
        reinvestment_rate: Rate for reinvesting positive cash flows.

    Returns:
        MIRR as a decimal, or None if no convergence.
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    # Separate negative and positive cash flows
    pv_negatives = sum(cf / (1 + finance_rate) ** t for t, cf in enumerate(cash_flows) if cf < 0)
    fv_positives = sum(cf * (1 + reinvestment_rate) ** (len(cash_flows) - 1 - t)
                       for t, cf in enumerate(cash_flows) if cf > 0)

    if pv_negatives == 0:
        return None

    n = len(cash_flows) - 1
    mirr = (fv_positives / abs(pv_negatives)) ** (1 / n) - 1

    return mirr


def compute_payback_period(cash_flows: list[float]) -> float | None:
    """Compute simple payback period (years to recover initial investment).

    Args:
        cash_flows: List of cash flows where index 0 is the initial investment.

    Returns:
        Payback period in periods (e.g., years), or None if never recovered.
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    cumulative = cash_flows[0]
    for t, cf in enumerate(cash_flows[1:], start=1):
        cumulative += cf
        if cumulative >= 0:
            # Linear interpolation within the period
            prev_cumulative = cumulative - cf
            fraction = -prev_cumulative / cf if cf != 0 else 0
            return t - 1 + fraction

    return None  # Never recovered


def compute_roi(cash_flows: list[float]) -> float:
    """Compute simple ROI (total return / initial investment).

    Args:
        cash_flows: List of cash flows where index 0 is the initial investment.

    Returns:
        ROI as a percentage.
    """
    if not cash_flows or cash_flows[0] == 0:
        return 0

    total_return = sum(cash_flows[1:])
    return (total_return / abs(cash_flows[0])) * 100


def compute_investment_analysis(conn, location_id: str) -> dict[str, Any]:
    """Compute comprehensive investment analysis with IRR, NPV, MIRR, payback, ROI.

    Uses forecast_output cash flow series or farm_launch_unit_economics.
    """
    cur = conn.cursor()

    # Try to get cash flow series from forecast_output
    cur.execute(
        """
        SELECT period_start, value
        FROM forecast_output
        WHERE location_id = %s AND metric_name = 'projected_noi_usd'
        ORDER BY period_start
        """,
        (location_id,),
    )
    forecast_rows = cur.fetchall()

    # Get launch economics
    cur.execute(
        """
        SELECT total_launch_cost_usd, projected_annual_noi_usd, projected_roi_pct,
               payback_months, discount_rate_pct, cash_flow_series
        FROM farm_launch_unit_economics
        WHERE location_id = %s
        LIMIT 1
        """,
        (location_id,),
    )
    launch = cur.fetchone()

    cur.close()

    cash_flows = []
    if forecast_rows and len(forecast_rows) >= 2:
        # Build cash flow series from forecast
        if launch and launch[0]:
            cash_flows.append(-float(launch[0]))  # Initial investment (negative)
        for row in forecast_rows:
            cash_flows.append(float(row[1] or 0))
    elif launch and launch[1]:
        # Fallback: simple 5-year projection from annual NOI
        annual_noi = float(launch[1])
        investment = float(launch[0] or 0)
        cash_flows = [-investment] + [annual_noi] * 5

    if not cash_flows or len(cash_flows) < 2:
        cur.close()
        return {"location_id": location_id, "status": "insufficient_data", "message": "No cash flow data available for IRR/NPV computation"}

    # Compute metrics
    irr = compute_irr(cash_flows)
    discount_rate = float(launch[4] or 0.08) if launch else 0.08
    npv = compute_npv(cash_flows, discount_rate)
    mirr = compute_mirr(cash_flows, discount_rate, discount_rate)
    payback = compute_payback_period(cash_flows)
    roi = compute_roi(cash_flows)

    # Build cash flow series for storage
    cash_flow_series = [
        {"period": t, "cash_flow": round(cf, 2)}
        for t, cf in enumerate(cash_flows)
    ]

    result = {
        "location_id": location_id,
        "cash_flows": cash_flows,
        "cash_flow_series": cash_flow_series,
        "irr_pct": round(irr * 100, 4) if irr is not None else None,
        "npv_usd": round(npv, 2),
        "mirr_pct": round(mirr * 100, 4) if mirr is not None else None,
        "payback_periods": round(payback, 2) if payback is not None else None,
        "roi_pct": round(roi, 2),
        "discount_rate_pct": round(discount_rate * 100, 2),
        "total_investment_usd": abs(cash_flows[0]) if cash_flows else 0,
        "total_return_usd": round(sum(cash_flows[1:]), 2) if len(cash_flows) > 1 else 0,
    }

    logger.info("Investment analysis for %s: IRR=%.2f%%, NPV=$%.2f",
                location_id, result["irr_pct"] or 0, result["npv_usd"])
    return result
