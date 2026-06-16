"""
Operating Margin Calculator

Formula: crop_noi / net_crop_revenue * 100
Definition: Operating income / net sales
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_operating_margin(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params = [location_id]
    if period_start:
        date_filter += " AND se.sale_date >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND se.sale_date <= %s"
        params.append(period_end)

    # Net revenue from sales
    cur.execute(f"""
        SELECT
            COALESCE(SUM(se.net_amount), 0) as net_revenue,
            COUNT(*) as sales_count
        FROM sales_event se
        WHERE se.location_id = %s
          AND se.status IN ('verified', 'published')
          {date_filter}
    """, params)
    revenue = dict(cur.fetchone())

    # Direct costs from expenses
    cur.execute(f"""
        SELECT
            COALESCE(SUM(ex.amount), 0) as direct_costs,
            COUNT(*) as expense_count
        FROM expense_event ex
        WHERE ex.location_id = %s
          AND ex.status IN ('verified', 'published')
          {date_filter}
    """, params)
    costs = dict(cur.fetchone())

    net_revenue = float(revenue["net_revenue"])
    direct_costs = float(costs["direct_costs"])
    noi = net_revenue - direct_costs
    margin = (noi / net_revenue * 100) if net_revenue > 0 else 0.0

    cur.close()

    return {
        "value": round(margin, 2),
        "computation_method": "(net_revenue - direct_costs) / net_revenue * 100",
        "source_record_ids": [],
        "metadata": {
            "net_revenue": round(net_revenue, 2),
            "direct_costs": round(direct_costs, 2),
            "noi": round(noi, 2),
            "sales_count": revenue["sales_count"],
            "expense_count": costs["expense_count"],
        },
    }
