"""
Baseline Asset Value Calculator

Formula: location.baseline_asset_value
Definition: Estimated starting asset or productive value
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_baseline_asset_value(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT baseline_asset_value FROM location WHERE id = %s",
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    value = float(row["baseline_asset_value"]) if row and row["baseline_asset_value"] else 0.0

    return {
        "value": value,
        "computation_method": "location.baseline_asset_value",
        "source_record_ids": [location_id],
        "metadata": {"source": "location"},
    }
