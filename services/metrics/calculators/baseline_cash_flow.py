"""
Baseline Cash Flow Calculator

Formula: location.baseline_cash_flow
Definition: Pre-intervention net cash flow
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_baseline_cash_flow(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT baseline_cash_flow FROM location WHERE id = %s",
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    value = float(row["baseline_cash_flow"]) if row and row["baseline_cash_flow"] else 0.0

    return {
        "value": value,
        "computation_method": "location.baseline_cash_flow",
        "source_record_ids": [location_id],
        "metadata": {"source": "location"},
    }
