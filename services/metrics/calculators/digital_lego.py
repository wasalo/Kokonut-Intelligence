"""
Digital Lego Usage Calculator

Formula: COUNT(DISTINCT protocol_id) WHERE verified = true
Definition: Protocol/tool usage linked to user, location, or operation
"""

from datetime import datetime
from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_digital_lego_usage(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params = [location_id]
    if period_start:
        date_filter += " AND dl.usage_date >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND dl.usage_date <= %s"
        params.append(period_end)

    cur.execute(f"""
        SELECT
            COUNT(DISTINCT dl.protocol_id) as unique_protocols,
            COUNT(*) as total_usages,
            SUM(dl.value_attributed) as total_value,
            COALESCE(ARRAY_AGG(DISTINCT p.name), '{{}}') as protocol_names
        FROM digital_lego_usage dl
        LEFT JOIN protocol p ON dl.protocol_id = p.id
        WHERE dl.location_id = %s
          AND dl.verified = TRUE
          {date_filter}
    """, params)
    row = dict(cur.fetchone())

    cur.execute(f"""
        SELECT ARRAY_AGG(dl.id) as record_ids
        FROM digital_lego_usage dl
        WHERE dl.location_id = %s
          AND dl.verified = TRUE
          {date_filter}
    """, params)
    ids_row = cur.fetchone()
    record_ids = ids_row["record_ids"] if ids_row and ids_row["record_ids"] else []

    cur.close()

    return {
        "value": float(row["unique_protocols"] or 0),
        "computation_method": "COUNT(DISTINCT protocol_id) WHERE verified",
        "source_record_ids": record_ids[:100],
        "metadata": {
            "unique_protocols": row["unique_protocols"],
            "total_usages": row["total_usages"],
            "total_value_attributed": float(row["total_value"] or 0),
            "protocol_names": row["protocol_names"] or [],
        },
    }
