"""
Crop NOI Calculator (location-level aggregate)

Formula: net_crop_revenue - direct_crop_cost - allocated_shared_cost
Definition: Net crop revenue minus direct crop costs minus allocated shared operating costs

Note: this is the per-location aggregate metric (``metric_value`` rows). The
per-crop-cycle NOI formula lives in the shared PostgreSQL view
``v_crop_cycle_noi`` (migration 353), which the Directus hook
(``extensions/kokonut-hooks/src/metrics-calculator.ts``) reads — do not
re-implement the crop-cycle SQL here.
"""

from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

from .allocated_shared_cost import compute_allocated_shared_cost
from .direct_crop_cost import compute_direct_crop_cost
from .net_crop_revenue import compute_net_crop_revenue


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
