"""
Crop Revenue Calculator

Formula: SUM(sales_event.total_amount) WHERE status = verified
Definition: Gross crop sales recognized for a crop and period
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_crop_revenue(
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
            COALESCE(SUM(se.total_amount), 0) as total_revenue,
            COUNT(*) as sales_count
        FROM sales_event se
        WHERE se.location_id = %s
          AND se.status IN ('verified', 'published')
          {date_filter}
    """, params)
    row = dict(cur.fetchone())

    total_revenue = float(row["total_revenue"])
    cur.close()

    return {
        "value": round(total_revenue, 2),
        "computation_method": "SUM(sales_event.total_amount) WHERE status IN ('verified', 'published')",
        "source_record_ids": [],
        "metadata": {
            "total_revenue": round(total_revenue, 2),
            "sales_count": row["sales_count"],
        },
    }
