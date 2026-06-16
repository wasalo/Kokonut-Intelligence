"""
Loss Rate % Calculator

Formula: 1 - (net_harvest / gross_harvest)
Definition: 1 - (saleable output / harvested output)
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_loss_rate_pct(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params = [location_id]
    if period_start:
        date_filter += " AND he.harvest_date >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND he.harvest_date <= %s"
        params.append(period_end)

    cur.execute(f"""
        SELECT
            COALESCE(SUM(he.quantity), 0) as gross_harvest,
            COALESCE(SUM(he.saleable_quantity), 0) as net_harvest,
            COUNT(*) as harvest_count
        FROM harvest_event he
        WHERE he.location_id = %s
          {date_filter}
    """, params)
    row = dict(cur.fetchone())

    gross_harvest = float(row["gross_harvest"])
    net_harvest = float(row["net_harvest"])
    loss_rate = (1 - (net_harvest / gross_harvest) * 100) if gross_harvest > 0 else 0.0
    cur.close()

    return {
        "value": round(loss_rate, 2),
        "computation_method": "(1 - (net_harvest / gross_harvest)) * 100",
        "source_record_ids": [],
        "metadata": {
            "gross_harvest": round(gross_harvest, 2),
            "net_harvest": round(net_harvest, 2),
            "loss_rate_pct": round(loss_rate, 2),
            "harvest_count": row["harvest_count"],
        },
    }
