"""
Allocated Shared Cost Calculator

Formula: SUM(crop_cost_allocation.allocated_amount)
Definition: Shared costs allocated using governed allocation rules
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_allocated_shared_cost(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params = [location_id]
    if period_start:
        date_filter += " AND ca.created_at >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND ca.created_at <= %s"
        params.append(period_end)

    cur.execute(f"""
        SELECT
            COALESCE(SUM(ca.allocated_amount), 0) as shared_costs,
            COUNT(*) as allocation_count,
            COUNT(DISTINCT ca.crop_cycle_id) as cycles_allocated
        FROM crop_cost_allocation ca
        JOIN expense_event ee ON ca.expense_event_id = ee.id
        WHERE ee.location_id = %s
          AND ee.status IN ('verified', 'published')
          {date_filter}
    """, params)
    row = dict(cur.fetchone())

    shared_costs = float(row["shared_costs"])
    cur.close()

    return {
        "value": round(shared_costs, 2),
        "computation_method": "SUM(crop_cost_allocation.allocated_amount)",
        "source_record_ids": [],
        "metadata": {
            "shared_costs": round(shared_costs, 2),
            "allocation_count": row["allocation_count"],
            "cycles_allocated": row["cycles_allocated"],
        },
    }
