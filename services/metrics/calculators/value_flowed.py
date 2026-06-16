"""
Value Flowed Calculator

Formula: SUM(value_flow_event.amount) WHERE verified = true AND is_excluded = false
Exclusions: Failed rounds, returned funds, excluded fees, double-counted flows
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

import psycopg2
import psycopg2.extras


def compute_value_flowed(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params: List[Any] = [location_id]
    if period_start:
        date_filter += " AND flow_date >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND flow_date <= %s"
        params.append(period_end)

    cur.execute(f"""
        SELECT
            flow_type,
            SUM(amount) as total_amount,
            COUNT(*) as flow_count,
            ARRAY_AGG(id) as record_ids
        FROM value_flow_event
        WHERE location_id = %s
          AND verified = TRUE
          AND (is_excluded = FALSE OR is_excluded IS NULL)
          {date_filter}
        GROUP BY flow_type
        ORDER BY total_amount DESC
    """, params)
    flows = [dict(r) for r in cur.fetchall()]

    total = sum(float(f["total_amount"]) for f in flows)
    total_count = sum(f["flow_count"] for f in flows)
    all_ids = []
    for f in flows:
        all_ids.extend(f["record_ids"] or [])

    # Also count excluded flows for transparency
    cur.execute(f"""
        SELECT COUNT(*) as excluded_count, SUM(amount) as excluded_amount
        FROM value_flow_event
        WHERE location_id = %s
          AND is_excluded = TRUE
          {date_filter}
    """, params)
    excluded = dict(cur.fetchone())
    cur.close()

    return {
        "value": round(total, 2),
        "computation_method": "SUM(value_flow_event.amount) WHERE verified AND NOT is_excluded",
        "source_record_ids": all_ids[:100],  # cap at 100 for storage
        "metadata": {
            "flow_breakdown": {f["flow_type"]: float(f["total_amount"]) for f in flows},
            "total_flows": total_count,
            "excluded_flows": excluded.get("excluded_count", 0),
            "excluded_amount": float(excluded.get("excluded_amount") or 0),
        },
    }
