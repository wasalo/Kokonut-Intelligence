"""Resource efficiency analytics: labor, energy, water intensity per kg of yield."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_labor_efficiency(conn, location_id: str) -> dict[str, Any]:
    """Compute labor hours per kg harvested and experience curve."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cc.id AS cycle_id,
               cc.cycle_name,
               c.name AS crop_name,
               cc.actual_harvest_date,
               SUM(he.quantity) AS harvest_kg,
               SUM(le.hours_worked) AS labor_hours
        FROM crop_cycle cc
        JOIN crop c ON c.id = cc.crop_cycle_id
        JOIN harvest_event he ON he.crop_cycle_id = cc.id AND he.status IN ('verified', 'published')
        LEFT JOIN labor_event le ON le.crop_cycle_id = cc.id AND le.status IN ('verified', 'published')
        WHERE cc.location_id = %s AND cc.status IN ('completed', 'harvested')
        GROUP BY cc.id, cc.cycle_name, c.name, cc.actual_harvest_date
        ORDER BY cc.actual_harvest_date
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    cycles = []
    for row in rows:
        harvest_kg = float(row[4] or 0)
        labor_hours = float(row[5] or 0)
        efficiency = harvest_kg / labor_hours if labor_hours > 0 else 0
        cycles.append({
            "cycle_id": str(row[0]),
            "cycle_name": row[1],
            "crop_name": row[2],
            "actual_harvest_date": str(row[3]) if row[3] else None,
            "harvest_kg": round(harvest_kg, 2),
            "labor_hours": round(labor_hours, 2),
            "kg_per_labor_hour": round(efficiency, 2),
        })
    total_harvest = sum(c["harvest_kg"] for c in cycles)
    total_labor = sum(c["labor_hours"] for c in cycles)
    overall_efficiency = total_harvest / total_labor if total_labor > 0 else 0
    experience_curve = []
    if len(cycles) >= 2:
        for i, c in enumerate(cycles):
            running_harvest = sum(x["harvest_kg"] for x in cycles[: i + 1])
            running_labor = sum(x["labor_hours"] for x in cycles[: i + 1])
            running_eff = running_harvest / running_labor if running_labor > 0 else 0
            experience_curve.append({
                "cycle_name": c["cycle_name"],
                "cumulative_kg_per_hour": round(running_eff, 2),
            })
    return {
        "location_id": location_id,
        "cycles": cycles,
        "total_harvest_kg": round(total_harvest, 2),
        "total_labor_hours": round(total_labor, 2),
        "overall_kg_per_labor_hour": round(overall_efficiency, 2),
        "experience_curve": experience_curve,
    }


def compute_resource_consumption_by_crop(conn, location_id: str) -> dict[str, Any]:
    """Compute resource consumption broken down by crop cycle."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rc.resource_type, rc.unit,
               cc.id AS cycle_id, c.name AS crop_name,
               SUM(rc.quantity) AS total_quantity
        FROM resource_consumption rc
        JOIN crop_cycle cc ON cc.id = rc.crop_cycle_id
        JOIN crop c ON c.id = cc.crop_id
        WHERE rc.location_id = %s AND rc.status IN ('verified', 'published')
        GROUP BY rc.resource_type, rc.unit, cc.id, c.name
        ORDER BY rc.resource_type, total_quantity DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    by_crop = {}
    for row in rows:
        rtype = row[0]
        crop = row[3]
        key = f"{rtype}|{crop}"
        if key not in by_crop:
            by_crop[key] = {
                "resource_type": rtype,
                "unit": row[1],
                "crop_name": crop,
                "total_quantity": 0,
            }
        by_crop[key]["total_quantity"] += float(row[4] or 0)
    results = list(by_crop.values())
    for r in results:
        r["total_quantity"] = round(r["total_quantity"], 2)
    return {
        "location_id": location_id,
        "by_crop": results,
    }
