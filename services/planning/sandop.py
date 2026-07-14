"""Sales & Operations Planning (S&OP) cockpit (read-only).

Consolidates three EPS lenses for an organization into a single planning
picture: demand (production_market_match), capacity (utilization_observation),
and financials (financial_plan / budget_line actuals). This module never
writes; it is a read-only analytics surface over existing governed data.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List


def _coerce_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(str(value))


def _rows(cur, sql: str, params: tuple) -> List[Dict[str, Any]]:
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def cockpit(conn, organization_id: str) -> Dict[str, Any]:
    """Return a consolidated S&OP picture for an organization (read-only)."""
    oid = _coerce_uuid(organization_id)
    with conn.cursor() as cur:
        demand = _rows(
            cur,
            """
            SELECT location_id, crop_id, period_start, period_end,
                   projected_production_tonnes, confirmed_demand_tonnes,
                   total_demand_tonnes, supply_demand_gap_tonnes, gap_pct,
                   demand_coverage_pct, unfulfilled_demand_tonnes,
                   revenue_gap_usd, status
            FROM production_market_match
            WHERE location_id IN (SELECT id FROM location WHERE organization_id = %s)
            ORDER BY period_start DESC
            """,
            (oid,),
        )
        capacity = _rows(
            cur,
            """
            SELECT location_id, asset_id, observation_date,
                   capacity_used, total_capacity, utilization_pct,
                   production_output, production_unit
            FROM utilization_observation
            WHERE location_id IN (SELECT id FROM location WHERE organization_id = %s)
            ORDER BY observation_date DESC
            """,
            (oid,),
        )
        plans = _rows(
            cur,
            """
            SELECT id, name, version, status, currency
            FROM financial_plan
            WHERE organization_id = %s
            ORDER BY created_at DESC, version DESC
            """,
            (oid,),
        )
        plan_ids = [p["id"] for p in plans]
        lines: List[Dict[str, Any]] = []
        if plan_ids:
            cur.execute(
                """
                SELECT plan_id, category, period, planned_amount, actual_amount,
                       currency, status
                FROM budget_line
                WHERE plan_id = ANY(%s)
                ORDER BY plan_id, category, period
                """,
                (plan_ids,),
            )
            cols = [d[0] for d in cur.description]
            lines = [dict(zip(cols, row)) for row in cur.fetchall()]

    demand_gaps = [d for d in demand if (d.get("supply_demand_gap_tonnes") or 0) > 0]
    underutilized = [c for c in capacity if (c.get("utilization_pct") or 100) < 80]
    budget_variance = sum(
        (l.get("actual_amount") or 0) - (l.get("planned_amount") or 0) for l in lines
    )

    return {
        "organization_id": organization_id,
        "demand": demand,
        "capacity": capacity,
        "financial_plans": plans,
        "budget_lines": lines,
        "summary": {
            "demand_gap_records": len(demand_gaps),
            "underutilized_observations": len(underutilized),
            "budget_variance_total": round(budget_variance, 2),
            "active_plans": sum(1 for p in plans if p.get("status") == "active"),
        },
    }
