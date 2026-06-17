"""
Baseline Cost Calculator

Formula: location.baseline_cost
Definition: Pre-intervention operating costs
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_baseline_cost(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT baseline_cost FROM location WHERE id = %s",
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    value = float(row["baseline_cost"]) if row and row["baseline_cost"] else 0.0

    return {
        "value": value,
        "computation_method": "location.baseline_cost",
        "source_record_ids": [location_id],
        "metadata": {"source": "location"},
    }
