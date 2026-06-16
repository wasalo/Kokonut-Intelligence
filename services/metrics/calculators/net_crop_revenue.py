"""
Net Crop Revenue Calculator

Formula: crop_revenue - SUM(return_amount + discount_amount)
Definition: Crop revenue minus returns, discounts, and rejected sales
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_net_crop_revenue(
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

    cur.execute(f"""
        SELECT
            COALESCE(SUM(se.total_amount), 0) as gross_revenue,
            COALESCE(SUM(se.return_amount + se.discount_amount), 0) as returns_discounts,
            COUNT(*) as sales_count
        FROM sales_event se
        WHERE se.location_id = %s
          AND se.status IN ('verified', 'published')
          {date_filter}
    """, params)
    row = dict(cur.fetchone())

    gross_revenue = float(row["gross_revenue"])
    returns_discounts = float(row["returns_discounts"])
    net_revenue = gross_revenue - returns_discounts
    cur.close()

    return {
        "value": round(net_revenue, 2),
        "computation_method": "SUM(total_amount) - SUM(return_amount + discount_amount)",
        "source_record_ids": [],
        "metadata": {
            "gross_revenue": round(gross_revenue, 2),
            "returns_discounts": round(returns_discounts, 2),
            "net_revenue": round(net_revenue, 2),
            "sales_count": row["sales_count"],
        },
    }
