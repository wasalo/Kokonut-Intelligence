"""
Operating Margin Calculator

Formula: crop_noi / net_crop_revenue * 100
Definition: Operating income / net sales
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras

from .crop_noi import compute_crop_noi
from .net_crop_revenue import compute_net_crop_revenue


def compute_operating_margin(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    noi_result = compute_crop_noi(conn, location_id, period_start, period_end)
    revenue_result = compute_net_crop_revenue(conn, location_id, period_start, period_end)

    noi = noi_result.get("value", 0.0)
    net_revenue = revenue_result.get("value", 0.0)
    margin = (noi / net_revenue * 100) if net_revenue > 0 else 0.0

    return {
        "value": round(margin, 2),
        "computation_method": "crop_noi / net_crop_revenue * 100",
        "source_record_ids": (
            noi_result.get("source_record_ids", []) +
            revenue_result.get("source_record_ids", [])
        )[:100],
        "metadata": {
            "crop_noi": round(noi, 2),
            "net_crop_revenue": round(net_revenue, 2),
            "margin_pct": round(margin, 2),
        },
    }
