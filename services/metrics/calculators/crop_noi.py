"""
Crop NOI Calculator

Formula: net_crop_revenue - direct_crop_cost - allocated_shared_cost
Definition: Net crop revenue minus direct crop costs minus allocated shared operating costs
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras

from .net_crop_revenue import compute_net_crop_revenue
from .direct_crop_cost import compute_direct_crop_cost
from .allocated_shared_cost import compute_allocated_shared_cost


def compute_crop_noi(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    net_rev = compute_net_crop_revenue(conn, location_id, period_start, period_end)
    direct_cost = compute_direct_crop_cost(conn, location_id, period_start, period_end)
    shared_cost = compute_allocated_shared_cost(conn, location_id, period_start, period_end)

    net_revenue = net_rev.get("value", 0)
    direct_costs = direct_cost.get("value", 0)
    allocated_shared = shared_cost.get("value", 0)
    noi = net_revenue - direct_costs - allocated_shared

    return {
        "value": round(noi, 2),
        "computation_method": "net_crop_revenue - direct_crop_cost - allocated_shared_cost",
        "source_record_ids": [],
        "metadata": {
            "net_revenue": round(net_revenue, 2),
            "direct_costs": round(direct_costs, 2),
            "allocated_shared_costs": round(allocated_shared, 2),
            "noi": round(noi, 2),
        },
    }
