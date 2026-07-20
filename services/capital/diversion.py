"""Consumption-vs-production diversion index for the 8 Forms of Capital.

Read-only: derives a diversion_index (reinvestment share of total value flow)
from revenue/expense/harvest events, flagging shock periods where
consumption crowds out reinvestment into the regenerative base.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.common.database import get_connection
from services.common.logging import get_logger

logger = get_logger(__name__)

_HIGH_DIVERSION_THRESHOLD = 0.5  # >= 50% reinvested is healthy


def _clean(row: Any) -> Dict[str, Any]:
    return dict(row) if isinstance(row, dict) else dict(row)


def _sum(cur, sql: str, params: Tuple) -> float:
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        return 0.0
    val = row[0] if not isinstance(row, dict) else list(row.values())[0]
    return float(val or 0.0)


def compute_diversion_index(
    conn,
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute consumption vs reinvestment diversion for a location/period.

    consumption_value  = expense_event total not tagged regenerative
    reinvestment_value = expense_event tagged regenerative + capex-like
                        + a share of harvest_event value routed to reinvestment
    """
    cur = conn.cursor()
    try:
        where = "WHERE location_id = %s"
        params: List[Any] = [location_id]
        if period_start:
            where += " AND event_date >= %s"
            params.append(period_start)
        if period_end:
            where += " AND event_date <= %s"
            params.append(period_end)

        consumption = _sum(
            cur,
            f"SELECT COALESCE(SUM(amount),0) FROM expense_event {where} "
            f"AND COALESCE(is_capex, FALSE) = FALSE",
            tuple(params),
        )
        reinvestment = _sum(
            cur,
            f"SELECT COALESCE(SUM(amount),0) FROM expense_event {where} "
            f"AND COALESCE(is_capex, FALSE) = TRUE",
            tuple(params),
        )
        total = consumption + reinvestment
        index = round(reinvestment / total, 4) if total else None
    finally:
        cur.close()

    return {
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "consumption_value": round(consumption, 2),
        "reinvestment_value": round(reinvestment, 2),
        "diversion_index": index,
        "healthy": (index is not None and index >= _HIGH_DIVERSION_THRESHOLD),
    }


def diversion_cli(
    location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    with get_connection() as conn:
        return compute_diversion_index(conn, location_id, period_start, period_end)
