#!/usr/bin/env python3
"""
Equipment Usage Logging and OEE Tracking

Logs equipment usage events, computes Overall Equipment Effectiveness (OEE),
and tracks maintenance schedules for farm infrastructure.

Usage:
    python -m services.analytics.equipment --log --location-id UUID --asset-id UUID
    python -m services.analytics.equipment --status --location-id UUID
    python -m services.analytics.equipment --oee --asset-id UUID
    python -m services.analytics.equipment --maintenance --location-id UUID
    python -m services.analytics.equipment --cost --location-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.equipment")


# ============================================================
# Usage Logging
# ============================================================

def log_equipment_usage(
    conn,
    location_id: str,
    asset_id: str,
    start_time: datetime,
    end_time: datetime = None,
    operation_type: str = None,
    output_produced: float = None,
    output_unit: str = None,
    fuel_consumed: float = None,
    energy_consumed_kwh: float = None,
    operator_name: str = None,
    operator_id: str = None,
    metadata: dict = None,
) -> dict:
    """Log an equipment usage event."""
    cur = conn.cursor()

    log_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO equipment_usage_log
            (id, location_id, asset_id, start_time, end_time, operation_type,
             output_produced, output_unit, fuel_consumed, energy_consumed_kwh,
             operator_name, operator_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            log_id, location_id, asset_id, start_time, end_time,
            operation_type, output_produced, output_unit,
            fuel_consumed, energy_consumed_kwh,
            operator_name, operator_id,
            json.dumps(metadata or {}),
        ),
    )

    # Also update utilization_observation aggregate
    if end_time and start_time:
        hours = (end_time - start_time).total_seconds() / 3600
        _update_utilization(conn, location_id, asset_id, start_time.date(), hours, output_produced)

    conn.commit()
    cur.close()

    return {
        "log_id": log_id,
        "location_id": location_id,
        "asset_id": asset_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat() if end_time else None,
        "hours": round(hours, 2) if end_time else None,
        "operation_type": operation_type,
    }


def _update_utilization(conn, location_id: str, asset_id: str,
                         obs_date: date, hours: float, output: float = None):
    """Update utilization_observation aggregate."""
    cur = conn.cursor()

    # Get asset capacity and available hours
    cur.execute(
        "SELECT capacity FROM infrastructure_asset WHERE id = %s",
        (asset_id,),
    )
    row = cur.fetchone()
    capacity = float(row[0]) if row and row[0] else 1.0

    # Assume 8h available per day
    available_hours = 8.0
    utilization_pct = min((hours / available_hours) * 100, 100) if available_hours > 0 else 0

    cur.execute(
        """
        INSERT INTO utilization_observation
            (id, location_id, asset_id, observation_date, utilization_pct,
             usage_hours, production_output, observed_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL)
        ON CONFLICT (location_id, asset_id, observation_date)
        DO UPDATE SET
            utilization_pct = utilization_observation.utilization_pct + EXCLUDED.utilization_pct,
            usage_hours = utilization_observation.usage_hours + EXCLUDED.usage_hours,
            production_output = COALESCE(utilization_observation.production_output, 0) + COALESCE(EXCLUDED.production_output, 0)
        """,
        (
            str(uuid.uuid4()), location_id, asset_id, obs_date,
            utilization_pct, hours, output,
        ),
    )
    conn.commit()
    cur.close()


# ============================================================
# Equipment Status
# ============================================================

def get_equipment_status(conn, location_id: str) -> list[dict]:
    """Get status of all equipment at a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ia.id, ia.name, ia.asset_type, ia.capacity,
               ia.condition_status, ia.last_inspection_date,
               ia.status,
               (SELECT utilization_pct FROM utilization_observation
                WHERE asset_id = ia.id ORDER BY observation_date DESC LIMIT 1) AS latest_utilization,
               (SELECT SUM(usage_hours) FROM utilization_observation
                WHERE asset_id = ia.id
                  AND observation_date >= DATE_TRUNC('month', CURRENT_DATE)) AS hours_this_month,
               (SELECT SUM(fuel_consumed) FROM equipment_usage_log
                WHERE asset_id = ia.id
                  AND start_time >= DATE_TRUNC('month', CURRENT_DATE)) AS fuel_this_month
        FROM infrastructure_asset ia
        WHERE ia.location_id = %s AND ia.status = 'active'
        ORDER BY ia.asset_type, ia.name
        """,
        (location_id,),
    )
    cols = [desc[0] for desc in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


# ============================================================
# OEE (Overall Equipment Effectiveness)
# ============================================================

def compute_oee(conn, asset_id: str, period_days: int = 30) -> dict:
    """Compute Overall Equipment Effectiveness for an asset.
    
    OEE = Availability × Performance × Quality
    """
    cur = conn.cursor()

    # Get asset info
    cur.execute(
        "SELECT name, asset_type, capacity FROM infrastructure_asset WHERE id = %s",
        (asset_id,),
    )
    asset_row = cur.fetchone()
    if not asset_row:
        cur.close()
        return {"error": "Asset not found"}

    name, asset_type, capacity = asset_row

    # Get usage logs in period
    cur.execute(
        """
        SELECT start_time, end_time, output_produced, fuel_consumed
        FROM equipment_usage_log
        WHERE asset_id = %s
          AND start_time >= NOW() - INTERVAL '%s days'
        ORDER BY start_time
        """,
        (asset_id, period_days),
    )
    logs = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    # Get utilization observations
    cur.execute(
        """
        SELECT observation_date, utilization_pct, usage_hours, production_output
        FROM utilization_observation
        WHERE asset_id = %s
          AND observation_date >= CURRENT_DATE - %s
        ORDER BY observation_date
        """,
        (asset_id, period_days),
    )
    observations = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    cur.close()

    if not logs and not observations:
        return {
            "asset_id": asset_id,
            "asset_name": name,
            "asset_type": asset_type,
            "period_days": period_days,
            "availability": 0,
            "performance": 0,
            "quality": 0,
            "oee": 0,
            "status": "no_data",
        }

    # Compute OEE components
    # Availability: actual operating time / planned production time
    total_hours = sum(
        (log["end_time"] - log["start_time"]).total_seconds() / 3600
        for log in logs if log.get("end_time") and log.get("start_time")
    )
    planned_hours = period_days * 8  # 8h/day planned
    availability = min(total_hours / max(planned_hours, 1), 1.0)

    # Performance: actual output rate / ideal output rate
    total_output = sum(log.get("output_produced") or 0 for log in logs)
    ideal_output = (capacity or 1) * total_hours if total_hours > 0 else 1
    performance = min(total_output / max(ideal_output, 1), 1.0)

    # Quality: good output / total output (assume all output is good for now)
    quality = 0.95 if total_output > 0 else 0

    oee = availability * performance * quality

    return {
        "asset_id": asset_id,
        "asset_name": name,
        "asset_type": asset_type,
        "period_days": period_days,
        "availability": round(availability * 100, 1),
        "performance": round(performance * 100, 1),
        "quality": round(quality * 100, 1),
        "oee": round(oee * 100, 1),
        "total_hours": round(total_hours, 1),
        "total_output": round(total_output, 1),
        "status": "computed",
    }


# ============================================================
# Maintenance Schedule
# ============================================================

def get_maintenance_schedule(conn, location_id: str) -> list[dict]:
    """Get upcoming maintenance needs for equipment."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ia.id, ia.name, ia.asset_type, ia.condition_status,
               ia.last_inspection_date,
               CURRENT_DATE - ia.last_inspection_date AS days_since_inspection
        FROM infrastructure_asset ia
        WHERE ia.location_id = %s AND ia.status = 'active'
        ORDER BY
            CASE ia.condition_status
                WHEN 'critical' THEN 1
                WHEN 'poor' THEN 2
                WHEN 'fair' THEN 3
                WHEN 'good' THEN 4
                WHEN 'excellent' THEN 5
                ELSE 6
            END,
            ia.last_inspection_date ASC NULLS FIRST
        """,
        (location_id,),
    )
    cols = [desc[0] for desc in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    # Flag overdue inspections (> 90 days)
    for r in results:
        days = r.get("days_since_inspection")
        if days is not None:
            r["inspection_overdue"] = int(days) > 90
            r["maintenance_urgency"] = (
                "critical" if r.get("condition_status") in ("critical", "poor")
                else "overdue" if int(days) > 90
                else "due_soon" if int(days) > 60
                else "ok"
            )
        else:
            r["inspection_overdue"] = True
            r["maintenance_urgency"] = "unknown"

    return results


# ============================================================
# Cost Analysis
# ============================================================

def equipment_cost_analysis(conn, location_id: str, period_days: int = 30) -> dict:
    """Analyze equipment costs over a period."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ia.id, ia.name, ia.asset_type,
               SUM(eul.fuel_consumed) AS total_fuel,
               SUM(eul.energy_consumed_kwh) AS total_energy,
               SUM(EXTRACT(EPOCH FROM (eul.end_time - eul.start_time)) / 3600) AS total_hours,
               COUNT(eul.id) AS usage_count
        FROM equipment_usage_log eul
        JOIN infrastructure_asset ia ON ia.id = eul.asset_id
        WHERE ia.location_id = %s
          AND eul.start_time >= NOW() - INTERVAL '%s days'
        GROUP BY ia.id, ia.name, ia.asset_type
        ORDER BY total_fuel DESC NULLS LAST
        """,
        (location_id, period_days),
    )
    cols = [desc[0] for desc in cur.description]
    asset_costs = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Get replacement costs for depreciation estimate
    cur.execute(
        """
        SELECT SUM(replacement_cost) FROM infrastructure_asset
        WHERE location_id = %s AND replacement_cost IS NOT NULL AND status = 'active'
        """,
        (location_id,),
    )
    row = cur.fetchone()
    total_replacement = float(row[0]) if row and row[0] else 0
    cur.close()

    # Estimate costs (fuel: $1.5/L, electricity: $0.12/kWh, depreciation: 10%/year)
    fuel_cost_per_liter = 1.50
    electricity_cost_per_kwh = 0.12
    annual_depreciation_rate = 0.10

    total_fuel_cost = 0
    total_electricity_cost = 0
    total_hours = 0

    for ac in asset_costs:
        fuel = float(ac.get("total_fuel") or 0)
        energy = float(ac.get("total_energy") or 0)
        hours = float(ac.get("total_hours") or 0)

        ac["fuel_cost_usd"] = round(fuel * fuel_cost_per_liter, 2)
        ac["electricity_cost_usd"] = round(energy * electricity_cost_per_kwh, 2)
        ac["total_cost_usd"] = round(ac["fuel_cost_usd"] + ac["electricity_cost_usd"], 2)
        ac["cost_per_hour"] = round(ac["total_cost_usd"] / max(hours, 0.1), 2)

        total_fuel_cost += ac["fuel_cost_usd"]
        total_electricity_cost += ac["electricity_cost_usd"]
        total_hours += hours

    daily_depreciation = total_replacement * annual_depreciation_rate / 365
    period_depreciation = daily_depreciation * period_days

    return {
        "location_id": location_id,
        "period_days": period_days,
        "total_fuel_cost_usd": round(total_fuel_cost, 2),
        "total_electricity_cost_usd": round(total_electricity_cost, 2),
        "total_operating_cost_usd": round(total_fuel_cost + total_electricity_cost, 2),
        "depreciation_estimate_usd": round(period_depreciation, 2),
        "total_cost_usd": round(total_fuel_cost + total_electricity_cost + period_depreciation, 2),
        "total_hours": round(total_hours, 1),
        "cost_per_hour": round((total_fuel_cost + total_electricity_cost) / max(total_hours, 0.1), 2),
        "asset_costs": asset_costs,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Equipment usage logging and OEE")
    sub = parser.add_subparsers(dest="command")

    # Log usage
    lg = sub.add_parser("log", help="Log equipment usage")
    lg.add_argument("--location-id", required=True)
    lg.add_argument("--asset-id", required=True)
    lg.add_argument("--start", required=True, help="ISO datetime")
    lg.add_argument("--end", help="ISO datetime")
    lg.add_argument("--operation", help="Operation type")
    lg.add_argument("--output", type=float, help="Output produced")
    lg.add_argument("--output-unit", help="Output unit")
    lg.add_argument("--fuel", type=float, help="Fuel consumed (liters)")
    lg.add_argument("--energy", type=float, help="Energy consumed (kWh)")
    lg.add_argument("--operator", help="Operator name")
    lg.add_argument("--json", action="store_true")

    # Status
    st = sub.add_parser("status", help="Equipment status")
    st.add_argument("--location-id", required=True)
    st.add_argument("--json", action="store_true")

    # OEE
    oee = sub.add_parser("oee", help="Compute OEE")
    oee.add_argument("--asset-id", required=True)
    oee.add_argument("--period", type=int, default=30)
    oee.add_argument("--json", action="store_true")

    # Maintenance
    mt = sub.add_parser("maintenance", help="Maintenance schedule")
    mt.add_argument("--location-id", required=True)
    mt.add_argument("--json", action="store_true")

    # Cost
    cs = sub.add_parser("cost", help="Cost analysis")
    cs.add_argument("--location-id", required=True)
    cs.add_argument("--period", type=int, default=30)
    cs.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from services.common.database import get_db

    if args.command in ("log", "status", "oee", "maintenance", "cost"):
        db = get_db()
    else:
        parser.print_help()
        return

    try:
        if args.command == "log":
            start = datetime.fromisoformat(args.start)
            end = datetime.fromisoformat(args.end) if args.end else None
            result = log_equipment_usage(
                db, args.location_id, args.asset_id, start, end,
                args.operation, args.output, args.output_unit,
                args.fuel, args.energy, args.operator,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_log(result)
            print(output)

        elif args.command == "status":
            results = get_equipment_status(db, args.location_id)
            output = json.dumps(results, indent=2, default=str) if args.json else _format_status(results)
            print(output)

        elif args.command == "oee":
            result = compute_oee(db, args.asset_id, args.period)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_oee(result)
            print(output)

        elif args.command == "maintenance":
            results = get_maintenance_schedule(db, args.location_id)
            output = json.dumps(results, indent=2, default=str) if args.json else _format_maintenance(results)
            print(output)

        elif args.command == "cost":
            result = equipment_cost_analysis(db, args.location_id, args.period)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_cost(result)
            print(output)

    finally:
        db.close()


def _format_log(r: dict) -> str:
    return f"Logged: {r['asset_id'][:8]}... | {r.get('hours', '?')}h | {r.get('operation_type', '?')}"


def _format_status(results: list) -> str:
    if not results:
        return "No active equipment."
    lines = []
    for r in results:
        util = f"{r['latest_utilization']:.0f}%" if r.get("latest_utilization") else "N/A"
        lines.append(f"  {r['name']:20s} {r['asset_type']:15s} {r['condition_status'] or 'unknown':10s} util={util}")
    return f"Equipment ({len(results)}):\n" + "\n".join(lines)


def _format_oee(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"OEE — {r['asset_name']} ({r['period_days']}d)\n"
        f"  Availability: {r['availability']}%\n"
        f"  Performance:  {r['performance']}%\n"
        f"  Quality:      {r['quality']}%\n"
        f"  OEE:          {r['oee']}%"
    )


def _format_maintenance(results: list) -> str:
    if not results:
        return "No maintenance needed."
    lines = []
    for r in results:
        icon = "🔴" if r.get("maintenance_urgency") == "critical" else "⚠" if r.get("maintenance_urgency") in ("overdue", "unknown") else "✓"
        days = r.get("days_since_inspection", "?")
        lines.append(f"  {icon} {r['name']:20s} {r['condition_status'] or 'unknown':10s} last_inspection={days}d ago")
    return f"Maintenance ({len(results)}):\n" + "\n".join(lines)


def _format_cost(r: dict) -> str:
    lines = [
        f"Cost Analysis ({r['period_days']}d):",
        f"  Fuel:      ${r['total_fuel_cost_usd']:.2f}",
        f"  Electric:  ${r['total_electricity_cost_usd']:.2f}",
        f"  Operating: ${r['total_operating_cost_usd']:.2f}",
        f"  Depreciation: ${r['depreciation_estimate_usd']:.2f}",
        f"  Total:     ${r['total_cost_usd']:.2f}",
        f"  Hours:     {r['total_hours']:.1f}",
        f"  $/hour:    ${r['cost_per_hour']:.2f}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
