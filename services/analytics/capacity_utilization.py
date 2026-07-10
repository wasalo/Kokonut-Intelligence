"""Capacity utilization analytics.

Tracks infrastructure usage rates, equipment OEE, capacity trends,
and overcapacity/undercapacity alerts.

Usage:
    python3 -m services.analytics --utilization-rate --asset-id UUID
    python3 -m services.analytics --equipment-oee --asset-id UUID
    python3 -m services.analytics --capacity-trend --asset-id UUID
    python3 -m services.analytics --underutilized --location-id UUID
    python3 -m services.analytics --overcapacity-risk --location-id UUID
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.capacity_utilization")


def compute_utilization_rate(conn, asset_id: str, days: int = 30) -> Dict[str, Any]:
    """Compute utilization rate for an asset over a period."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get asset details
    cur.execute("SELECT * FROM infrastructure_asset WHERE id = %s", (asset_id,))
    asset = cur.fetchone()
    if not asset:
        cur.close()
        return {"status": "error", "message": "Asset not found"}

    asset = dict(asset)
    total_capacity = float(asset.get("capacity", 0) or 0)

    # Get utilization observations
    cur.execute("""
        SELECT
            AVG(utilization_pct) AS avg_utilization,
            MAX(utilization_pct) AS max_utilization,
            MIN(utilization_pct) AS min_utilization,
            SUM(usage_hours) AS total_usage_hours,
            SUM(production_output) AS total_production,
            COUNT(*) AS observation_count
        FROM utilization_observation
        WHERE asset_id = %s
        AND observation_date >= CURRENT_DATE - INTERVAL '%s days'
    """, (asset_id, days))
    util = dict(cur.fetchone() or {})

    # Get threshold
    cur.execute("SELECT * FROM capacity_threshold WHERE asset_id = %s", (asset_id,))
    threshold = cur.fetchone()
    threshold = dict(threshold) if threshold else {}

    cur.close()

    avg_util = float(util.get("avg_utilization", 0) or 0)
    target = float(threshold.get("target_pct", 70) or 70)
    warning = float(threshold.get("warning_pct", 80) or 80)
    critical = float(threshold.get("critical_pct", 95) or 95)

    # Status determination
    if avg_util == 0:
        status = "inactive"
    elif avg_util >= critical:
        status = "overcapacity"
    elif avg_util >= warning:
        status = "high"
    elif avg_util >= float(threshold.get("min_pct", 20) or 20):
        status = "optimal"
    else:
        status = "underutilized"

    # Distance from target
    target_deviation = avg_util - target

    return {
        "asset_id": asset_id,
        "asset_name": asset["asset_name"],
        "asset_type": asset["asset_type"],
        "total_capacity": total_capacity,
        "capacity_unit": asset.get("capacity_unit"),
        "period_days": days,
        "avg_utilization_pct": round(avg_util, 1),
        "max_utilization_pct": round(float(util.get("max_utilization", 0) or 0), 1),
        "min_utilization_pct": round(float(util.get("min_utilization", 0) or 0), 1),
        "total_usage_hours": round(float(util.get("total_usage_hours", 0) or 0), 1),
        "total_production": round(float(util.get("total_production", 0) or 0), 2),
        "observation_count": int(util.get("observation_count", 0) or 0),
        "target_pct": target,
        "warning_pct": warning,
        "critical_pct": critical,
        "target_deviation": round(target_deviation, 1),
        "status": status,
    }


def compute_oee(conn, asset_id: str, days: int = 30) -> Dict[str, Any]:
    """Compute Overall Equipment Effectiveness (OEE) for an asset.

    OEE = Availability × Performance × Quality
    - Availability: actual run time / planned run time
    - Performance: actual output / theoretical max output
    - Quality: good output / total output
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get asset capacity and planned hours
    cur.execute("SELECT * FROM infrastructure_asset WHERE id = %s", (asset_id,))
    asset = cur.fetchone()
    if not asset:
        cur.close()
        return {"status": "error", "message": "Asset not found"}

    asset = dict(asset)
    total_capacity = float(asset.get("capacity", 0) or 0)
    planned_hours = float(days * 8)  # Assume 8-hour work days

    # Get usage logs
    cur.execute("""
        SELECT
            COUNT(*) AS usage_count,
            COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(end_time, NOW()) - start_time)) / 3600), 0) AS actual_run_hours,
            COALESCE(SUM(production_output), 0) AS total_output,
            COALESCE(SUM(fuel_consumed), 0) AS total_fuel,
            COALESCE(SUM(energy_consumed_kwh), 0) AS total_energy
        FROM equipment_usage_log
        WHERE asset_id = %s
        AND start_time >= NOW() - INTERVAL '%s days'
    """, (asset_id, days))
    usage = dict(cur.fetchone() or {})

    # Get utilization observations for production target
    cur.execute("""
        SELECT AVG(production_output) AS avg_output_per_obs
        FROM utilization_observation
        WHERE asset_id = %s
        AND observation_date >= CURRENT_DATE - INTERVAL '%s days'
    """, (asset_id, days))
    util = dict(cur.fetchone() or {})

    cur.close()

    actual_run = float(usage.get("actual_run_hours", 0) or 0)
    total_output = float(usage.get("total_output", 0) or 0)

    # OEE components
    availability = min(1.0, actual_run / planned_hours) if planned_hours > 0 else 0
    # Performance: actual output vs theoretical max (capacity × run time)
    theoretical_max = total_capacity * actual_run if total_capacity > 0 and actual_run > 0 else 0
    performance = min(1.0, total_output / theoretical_max) if theoretical_max > 0 else 0
    # Quality: assume 100% good output (no reject tracking yet)
    quality = 1.0

    oee = availability * performance * quality

    return {
        "asset_id": asset_id,
        "asset_name": asset["asset_name"],
        "period_days": days,
        "planned_hours": planned_hours,
        "actual_run_hours": round(actual_run, 1),
        "availability": round(availability * 100, 1),
        "performance": round(performance * 100, 1),
        "quality": round(quality * 100, 1),
        "oee_pct": round(oee * 100, 1),
        "total_output": round(total_output, 2),
        "total_fuel": round(float(usage.get("total_fuel", 0) or 0), 2),
        "total_energy_kwh": round(float(usage.get("total_energy", 0) or 0), 2),
        "usage_events": int(usage.get("usage_count", 0) or 0),
    }


def compute_capacity_trend(conn, asset_id: str, periods: int = 6) -> List[Dict[str, Any]]:
    """Compute utilization trend over monthly periods."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            DATE_TRUNC('month', observation_date) AS month,
            AVG(utilization_pct) AS avg_utilization,
            SUM(production_output) AS total_production,
            SUM(usage_hours) AS total_usage_hours,
            COUNT(*) AS observations
        FROM utilization_observation
        WHERE asset_id = %s
        AND observation_date >= CURRENT_DATE - INTERVAL '%s months'
        GROUP BY DATE_TRUNC('month', observation_date)
        ORDER BY month
    """, (asset_id, periods))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Get target
    cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur2.execute("SELECT target_pct FROM capacity_threshold WHERE asset_id = %s", (asset_id,))
    target_row = cur2.fetchone()
    cur2.close()
    target = float(target_row["target_pct"]) if target_row else 70.0

    trend = []
    for row in rows:
        avg = float(row.get("avg_utilization", 0) or 0)
        trend.append({
            "month": str(row["month"]),
            "avg_utilization_pct": round(avg, 1),
            "total_production": round(float(row.get("total_production", 0) or 0), 2),
            "total_usage_hours": round(float(row.get("total_usage_hours", 0) or 0), 1),
            "observations": int(row.get("observations", 0) or 0),
            "vs_target": round(avg - target, 1),
        })

    return trend


def compute_underutilized_assets(conn, location_id: str, threshold_pct: float = 30.0) -> List[Dict[str, Any]]:
    """Find assets with utilization below threshold."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT DISTINCT ON (ia.id)
            ia.id AS asset_id,
            ia.asset_name,
            ia.asset_type,
            ia.capacity,
            ia.capacity_unit,
            uo.utilization_pct,
            uo.observation_date,
            ct.target_pct
        FROM infrastructure_asset ia
        LEFT JOIN LATERAL (
            SELECT utilization_pct, observation_date
            FROM utilization_observation uo
            WHERE uo.asset_id = ia.id
            ORDER BY uo.observation_date DESC
            LIMIT 1
        ) uo ON TRUE
        LEFT JOIN capacity_threshold ct ON ct.asset_id = ia.id
        WHERE ia.location_id = %s
        AND ia.status = 'active'
        AND (uo.utilization_pct IS NULL OR uo.utilization_pct < %s)
        ORDER BY ia.id, uo.observation_date DESC
    """, (location_id, threshold_pct))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    return [
        {
            "asset_id": r["asset_id"],
            "asset_name": r["asset_name"],
            "asset_type": r["asset_type"],
            "capacity": r["capacity"],
            "current_utilization": round(float(r.get("utilization_pct", 0) or 0), 1),
            "target_pct": float(r.get("target_pct", 70) or 70),
            "last_observed": str(r.get("observation_date")),
        }
        for r in rows
    ]


def compute_overcapacity_risk(conn, location_id: str) -> List[Dict[str, Any]]:
    """Find assets approaching or exceeding capacity."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT DISTINCT ON (ia.id)
            ia.id AS asset_id,
            ia.asset_name,
            ia.asset_type,
            ia.capacity,
            ia.capacity_unit,
            uo.utilization_pct,
            uo.observation_date,
            ct.warning_pct,
            ct.critical_pct
        FROM infrastructure_asset ia
        LEFT JOIN LATERAL (
            SELECT utilization_pct, observation_date
            FROM utilization_observation uo
            WHERE uo.asset_id = ia.id
            ORDER BY uo.observation_date DESC
            LIMIT 1
        ) uo ON TRUE
        LEFT JOIN capacity_threshold ct ON ct.asset_id = ia.id
        WHERE ia.location_id = %s
        AND ia.status = 'active'
        AND uo.utilization_pct IS NOT NULL
        AND uo.utilization_pct >= COALESCE(ct.warning_pct, 80)
        ORDER BY ia.id, uo.utilization_pct DESC
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    return [
        {
            "asset_id": r["asset_id"],
            "asset_name": r["asset_name"],
            "asset_type": r["asset_type"],
            "current_utilization": round(float(r.get("utilization_pct", 0) or 0), 1),
            "warning_pct": float(r.get("warning_pct", 80) or 80),
            "critical_pct": float(r.get("critical_pct", 95) or 95),
            "status": "critical" if float(r.get("utilization_pct", 0) or 0) >= float(r.get("critical_pct", 95) or 95) else "warning",
            "last_observed": str(r.get("observation_date")),
        }
        for r in rows
    ]
