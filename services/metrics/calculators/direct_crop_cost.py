"""
Direct Crop Cost Calculator

Formula: SUM(expense_event.amount) WHERE crop_cycle_id IS NOT NULL AND allocation_method = direct
Definition: Costs directly attributable to a crop/cycle
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_direct_crop_cost(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params = [location_id]
    if period_start:
        date_filter += " AND ee.expense_date >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND ee.expense_date <= %s"
        params.append(period_end)

    cur.execute(f"""
        SELECT
            COALESCE(SUM(ee.amount), 0) as direct_costs,
            COUNT(*) as expense_count
        FROM expense_event ee
        WHERE ee.location_id = %s
          AND ee.status IN ('verified', 'published')
          AND ee.crop_cycle_id IS NOT NULL
          {date_filter}
    """, params)
    row = dict(cur.fetchone())

    direct_costs = float(row["direct_costs"])
    cur.close()

    return {
        "value": round(direct_costs, 2),
        "computation_method": "SUM(expense_event.amount) WHERE crop_cycle_id IS NOT NULL",
        "source_record_ids": [],
        "metadata": {
            "direct_costs": round(direct_costs, 2),
            "expense_count": row["expense_count"],
        },
    }
