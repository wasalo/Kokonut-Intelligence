#!/usr/bin/env python3
"""
Precision Irrigation Automation

Manages irrigation zones, moisture targets, scheduling, events,
automation rules, and water-use efficiency tracking.

Usage:
    python -m services.analytics.precision_irrigation create-zone --location-id UUID --name "Zone A"
    python -m services.analytics.precision_irrigation set-target --zone-id UUID --crop-stage vegetative --target-min 50 --target-max 65 --trigger-pct 40 --refill-pct 65
    python -m services.analytics.precision_irrigation schedule --zone-id UUID --etc 4.5 --rainfall 2.0 --moisture 42
    python -m services.analytics.precision_irrigation record-event --zone-id UUID --volume 500 --duration 60 --method drip --moisture-before 38 --moisture-after 62
    python -m services.analytics.precision_irrigation create-rule --zone-id UUID --metric soil_moisture --operator lt --threshold 40 --action irrigate
    python -m services.analytics.precision_irrigation eval-rules --zone-id UUID --readings '{"soil_moisture": 35}'
    python -m services.analytics.precision_irrigation zone-status --zone-id UUID
    python -m services.analytics.precision_irrigation irrigation-status --location-id UUID
    python -m services.analytics.precision_irrigation water-efficiency --location-id UUID --days 30
    python -m services.analytics.precision_irrigation water-balance --zone-id UUID
    python -m services.analytics.precision_irrigation optimize --zone-id UUID
    python -m services.analytics.precision_irrigation efficiency-report --location-id UUID
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from ..common.logging import get_logger

logger = get_logger("analytics.precision_irrigation")


# ============================================================
# Zone Management
# ============================================================

def create_zone(
    conn,
    location_id: str,
    name: str,
    zone_code: str = None,
    soil_type: str = None,
    crop_name: str = None,
    area_ha: float = None,
    depth_cm: float = 30.0,
    field_capacity_pct: float = None,
    wilting_point_pct: float = None,
    bulk_density: float = None,
    sensor_id: str = None,
    actuator_id: str = None,
    plot_id: str = None,
    metadata: dict = None,
) -> dict:
    """Create an irrigation zone."""
    cur = conn.cursor()
    try:
        zone_id = str(uuid.uuid4())
        area_m2 = area_ha * 10000.0 if area_ha is not None else None

        cur.execute(
            """
            INSERT INTO irrigation_zone
                (id, location_id, plot_id, name, zone_code, soil_type,
                 area_m2, depth_cm, field_capacity_pct, wilting_point_pct,
                 bulk_density, sensor_device_id, actuator_device_id,
                 metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
            RETURNING id, created_at
            """,
            (
                zone_id, location_id, plot_id, name, zone_code, soil_type,
                area_m2, depth_cm, field_capacity_pct, wilting_point_pct,
                bulk_density, sensor_id, actuator_id,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        created_at = row[1]
        conn.commit()

        result = {
            "zone_id": zone_id,
            "location_id": location_id,
            "name": name,
            "zone_code": zone_code,
            "soil_type": soil_type,
            "area_ha": area_ha,
            "area_m2": area_m2,
            "depth_cm": depth_cm,
            "status": "active",
            "created_at": created_at.isoformat() if created_at else None,
        }
        logger.info("Created irrigation zone %s at location %s", zone_id, location_id)
        return result
    finally:
        cur.close()


def set_moisture_target(
    conn,
    zone_id: str,
    crop_stage: str,
    target_min: float,
    target_max: float,
    trigger_pct: float,
    refill_pct: float,
    crop_id: str = None,
    stress_threshold: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Set soil moisture targets for a zone and crop growth stage."""
    cur = conn.cursor()
    try:
        target_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO soil_moisture_target
                (id, zone_id, crop_id, growth_stage,
                 target_min_pct, target_max_pct, stress_threshold_pct,
                 irrigation_trigger_pct, refill_to_pct,
                 notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (zone_id, crop_id, growth_stage) DO UPDATE SET
                target_min_pct = EXCLUDED.target_min_pct,
                target_max_pct = EXCLUDED.target_max_pct,
                stress_threshold_pct = EXCLUDED.stress_threshold_pct,
                irrigation_trigger_pct = EXCLUDED.irrigation_trigger_pct,
                refill_to_pct = EXCLUDED.refill_to_pct,
                notes = EXCLUDED.notes,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id, created_at
            """,
            (
                target_id, zone_id, crop_id, crop_stage,
                target_min, target_max, stress_threshold,
                trigger_pct, refill_pct,
                notes, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        result = {
            "target_id": target_id,
            "zone_id": zone_id,
            "crop_id": crop_id,
            "crop_stage": crop_stage,
            "target_min_pct": target_min,
            "target_max_pct": target_max,
            "irrigation_trigger_pct": trigger_pct,
            "refill_to_pct": refill_pct,
            "stress_threshold_pct": stress_threshold,
        }
        logger.info("Set moisture target for zone %s stage %s", zone_id, crop_stage)
        return result
    finally:
        cur.close()


# ============================================================
# Irrigation Scheduling
# ============================================================

def generate_schedule(
    conn,
    zone_id: str,
    etc_mm: float,
    rainfall_forecast_mm: float = 0.0,
    current_moisture_pct: float = None,
    target_soil_moisture_pct: float = None,
    scheduled_start: datetime = None,
    triggered_by: str = "scheduled",
    crop_cycle_id: str = None,
    metadata: dict = None,
) -> dict:
    """Generate an irrigation schedule based on ETc, rainfall, and soil moisture."""
    cur = conn.cursor()
    try:
        schedule_id = str(uuid.uuid4())

        # Get zone area
        cur.execute(
            "SELECT area_m2, depth_cm FROM irrigation_zone WHERE id = %s",
            (zone_id,),
        )
        zone_row = cur.fetchone()
        if not zone_row:
            raise ValueError(f"Zone {zone_id} not found")
        area_m2 = float(zone_row[0]) if zone_row[0] else 0
        depth_cm = float(zone_row[1]) if zone_row[1] else 30.0

        # Net irrigation need (mm) = ETc - rainfall
        net_need_mm = max(etc_mm - rainfall_forecast_mm, 0)

        # Volume (liters) = net_need_mm × area_m2 (1 mm × 1 m² = 1 liter)
        volume_l = net_need_mm * area_m2

        # Estimate duration from volume (drip default ~2 L/min per emitter, rough)
        duration_min = max(int(volume_l / 2.0), 5) if volume_l > 0 else 0

        scheduled_start = scheduled_start or datetime.now(timezone.utc)
        scheduled_end = scheduled_start + timedelta(minutes=duration_min)

        reason_parts = []
        if etc_mm > 0:
            reason_parts.append(f"ETc={etc_mm:.1f}mm")
        if rainfall_forecast_mm > 0:
            reason_parts.append(f"rain={rainfall_forecast_mm:.1f}mm")
        reason = "Irrigation: " + ", ".join(reason_parts) if reason_parts else "Scheduled irrigation"

        cur.execute(
            """
            INSERT INTO irrigation_schedule
                (id, zone_id, crop_cycle_id, scheduled_start, scheduled_end,
                 planned_duration_min, planned_volume_l, reason,
                 etc_mm, rainfall_forecast_mm,
                 current_soil_moisture_pct, target_soil_moisture_pct,
                 status, triggered_by, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (
                schedule_id, zone_id, crop_cycle_id, scheduled_start, scheduled_end,
                duration_min, round(volume_l, 2), reason,
                etc_mm, rainfall_forecast_mm,
                current_moisture_pct, target_soil_moisture_pct,
                triggered_by, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        result = {
            "schedule_id": schedule_id,
            "zone_id": zone_id,
            "scheduled_start": scheduled_start.isoformat(),
            "scheduled_end": scheduled_end.isoformat(),
            "planned_duration_min": duration_min,
            "planned_volume_l": round(volume_l, 2),
            "etc_mm": etc_mm,
            "rainfall_forecast_mm": rainfall_forecast_mm,
            "net_need_mm": round(net_need_mm, 4),
            "current_moisture_pct": current_moisture_pct,
            "target_soil_moisture_pct": target_soil_moisture_pct,
            "status": "pending",
            "reason": reason,
        }
        logger.info("Generated schedule %s for zone %s: %.1f L", schedule_id, zone_id, volume_l)
        return result
    finally:
        cur.close()


def record_irrigation_event(
    conn,
    zone_id: str,
    volume_liters: float,
    duration_min: float,
    method: str,
    moisture_before: float,
    moisture_after: float,
    schedule_id: str = None,
    etc_mm: float = None,
    water_source: str = None,
    trigger_type: str = "manual",
    efficiency_pct: float = None,
    run_off_pct: float = 0.0,
    deep_percolation_pct: float = 0.0,
    energy_cost_usd: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record an actual irrigation event."""
    cur = conn.cursor()
    try:
        event_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        flow_rate = volume_liters / duration_min if duration_min > 0 else 0

        cur.execute(
            """
            INSERT INTO irrigation_event
                (id, schedule_id, zone_id, started_at, ended_at,
                 duration_min, volume_l, flow_rate_lpm,
                 soil_moisture_before_pct, soil_moisture_after_pct,
                 etc_mm, water_source, method, trigger_type,
                 efficiency_pct, run_off_pct, deep_percolation_pct,
                 energy_cost_usd, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (
                event_id, schedule_id, zone_id, started_at, started_at,
                duration_min, volume_liters, round(flow_rate, 2),
                moisture_before, moisture_after,
                etc_mm, water_source, method, trigger_type,
                efficiency_pct, run_off_pct, deep_percolation_pct,
                energy_cost_usd, notes, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()

        # Update schedule status if linked
        if schedule_id:
            cur.execute(
                "UPDATE irrigation_schedule SET status = 'completed', updated_at = NOW() WHERE id = %s",
                (schedule_id,),
            )

        conn.commit()

        result = {
            "event_id": event_id,
            "zone_id": zone_id,
            "schedule_id": schedule_id,
            "volume_liters": volume_liters,
            "duration_min": duration_min,
            "flow_rate_lpm": round(flow_rate, 2),
            "method": method,
            "moisture_before_pct": moisture_before,
            "moisture_after_pct": moisture_after,
            "moisture_change_pct": round(moisture_after - moisture_before, 2) if moisture_before is not None and moisture_after is not None else None,
            "trigger_type": trigger_type,
            "started_at": started_at.isoformat(),
        }
        logger.info("Recorded irrigation event %s: %.1f L over %s min", event_id, volume_liters, duration_min)
        return result
    finally:
        cur.close()


# ============================================================
# Automation Rules
# ============================================================

def create_automation_rule(
    conn,
    location_id: str,
    name: str,
    sensor_metric: str,
    operator: str,
    threshold: float,
    actuator_command: str = "irrigate",
    zone_id: str = None,
    description: str = None,
    unit: str = "%",
    threshold_high: float = None,
    action_params: dict = None,
    min_duration_min: int = 0,
    cooldown_min: int = 60,
    max_per_day: int = 5,
    time_window_start: str = None,
    time_window_end: str = None,
    requires_approval: bool = True,
    priority: int = 50,
    metadata: dict = None,
) -> dict:
    """Create an automation rule for an irrigation zone."""
    cur = conn.cursor()
    try:
        rule_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO automation_rule
                (id, location_id, zone_id, name, description,
                 sensor_metric, operator, threshold_low, threshold_high, unit,
                 action, action_params,
                 min_duration_min, cooldown_min, max_per_day,
                 time_window_start, time_window_end,
                 requires_approval, priority, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
            RETURNING id, created_at
            """,
            (
                rule_id, location_id, zone_id, name, description,
                sensor_metric, operator, threshold, threshold_high, unit,
                actuator_command, json.dumps(action_params or {}),
                min_duration_min, cooldown_min, max_per_day,
                time_window_start, time_window_end,
                requires_approval, priority, json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()

        result = {
            "rule_id": rule_id,
            "location_id": location_id,
            "zone_id": zone_id,
            "name": name,
            "sensor_metric": sensor_metric,
            "operator": operator,
            "threshold_low": threshold,
            "threshold_high": threshold_high,
            "unit": unit,
            "action": actuator_command,
            "priority": priority,
            "requires_approval": requires_approval,
            "status": "active",
        }
        logger.info("Created automation rule %s: %s %s %s", rule_id, sensor_metric, operator, threshold)
        return result
    finally:
        cur.close()


def evaluate_automation_rules(conn, zone_id: str, current_readings: dict) -> dict:
    """Evaluate automation rules against current sensor readings.

    Args:
        conn: Database connection.
        zone_id: Irrigation zone ID.
        current_readings: Dict of {metric_name: value}, e.g. {"soil_moisture": 35, "temperature": 28}.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name, sensor_metric, operator, threshold_low, threshold_high,
                   unit, action, action_params, cooldown_min, max_per_day,
                   time_window_start, time_window_end, requires_approval, priority
            FROM automation_rule
            WHERE zone_id = %s AND status = 'active'
            ORDER BY priority DESC
            """,
            (zone_id,),
        )
        cols = [d[0] for d in cur.description]
        rules = [dict(zip(cols, row)) for row in cur.fetchall()]

        triggered = []
        for rule in rules:
            metric = rule["sensor_metric"]
            if metric not in current_readings:
                continue

            value = current_readings[metric]
            op = rule["operator"]
            threshold_low = float(rule["threshold_low"])
            threshold_high = float(rule["threshold_high"]) if rule["threshold_high"] is not None else None

            condition_met = False
            if op == "lt" and value < threshold_low:
                condition_met = True
            elif op == "lte" and value <= threshold_low:
                condition_met = True
            elif op == "gt" and value > threshold_low:
                condition_met = True
            elif op == "gte" and value >= threshold_low:
                condition_met = True
            elif op == "eq" and value == threshold_low:
                condition_met = True
            elif op == "neq" and value != threshold_low:
                condition_met = True
            elif op == "between" and threshold_high is not None and threshold_low <= value <= threshold_high:
                condition_met = True

            if not condition_met:
                continue

            # Check cooldown: count recent events for this zone
            cur.execute(
                """
                SELECT COUNT(*) FROM irrigation_event
                WHERE zone_id = %s AND started_at > NOW() - INTERVAL '1 hour' * %s
                """,
                (zone_id, rule["cooldown_min"]),
            )
            recent_count = cur.fetchone()[0]
            if recent_count >= rule["max_per_day"]:
                continue

            # Check time window
            now_time = datetime.now(timezone.utc).time()
            if rule["time_window_start"] and rule["time_window_end"]:
                if not (rule["time_window_start"] <= now_time <= rule["time_window_end"]):
                    continue

            triggered.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "metric": metric,
                "current_value": value,
                "operator": op,
                "threshold": threshold_low,
                "action": rule["action"],
                "requires_approval": rule["requires_approval"],
                "priority": rule["priority"],
            })

        result = {
            "zone_id": zone_id,
            "readings": current_readings,
            "rules_evaluated": len(rules),
            "rules_triggered": len(triggered),
            "triggered": triggered,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Zone %s: %d/%d rules triggered",
            zone_id, len(triggered), len(rules),
        )
        return result
    finally:
        cur.close()


# ============================================================
# Status & Reporting
# ============================================================

def get_zone_status(conn, zone_id: str) -> dict:
    """Get current status for an irrigation zone."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT iz.id, iz.location_id, iz.name, iz.zone_code, iz.soil_type,
                   iz.area_m2, iz.depth_cm, iz.status,
                   sm.target_min_pct, sm.target_max_pct,
                   sm.irrigation_trigger_pct, sm.refill_to_pct,
                   sm.growth_stage,
                   lr.reading_value AS current_moisture_pct,
                   lr.reading_time AS last_moisture_reading,
                   ns.scheduled_start AS next_irrigation_start,
                   ns.planned_volume_l AS next_irrigation_volume_l,
                   ns.status AS next_irrigation_status,
                   le.started_at AS last_irrigation_at,
                   le.volume_l AS last_irrigation_volume_l
            FROM irrigation_zone iz
            LEFT JOIN LATERAL (
                SELECT target_min_pct, target_max_pct, irrigation_trigger_pct,
                       refill_to_pct, growth_stage
                FROM soil_moisture_target
                WHERE zone_id = iz.id
                ORDER BY created_at DESC LIMIT 1
            ) sm ON TRUE
            LEFT JOIN LATERAL (
                SELECT reading_value, reading_time
                FROM sensor_reading
                WHERE sensor_id = iz.sensor_device_id
                  AND sensor_type = 'soil_moisture'
                ORDER BY reading_time DESC LIMIT 1
            ) lr ON TRUE
            LEFT JOIN LATERAL (
                SELECT scheduled_start, planned_volume_l, status
                FROM irrigation_schedule
                WHERE zone_id = iz.id AND status = 'pending'
                ORDER BY scheduled_start ASC LIMIT 1
            ) ns ON TRUE
            LEFT JOIN LATERAL (
                SELECT started_at, volume_l
                FROM irrigation_event
                WHERE zone_id = iz.id
                ORDER BY started_at DESC LIMIT 1
            ) le ON TRUE
            WHERE iz.id = %s
            """,
            (zone_id,),
        )
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        if not row:
            return {"zone_id": zone_id, "error": "zone_not_found"}

        r = dict(zip(cols, row))

        # Determine moisture status
        current_moisture = float(r["current_moisture_pct"]) if r["current_moisture_pct"] else None
        trigger_pct = float(r["irrigation_trigger_pct"]) if r["irrigation_trigger_pct"] else None
        target_min = float(r["target_min_pct"]) if r["target_min_pct"] else None
        target_max = float(r["target_max_pct"]) if r["target_max_pct"] else None

        if current_moisture is None:
            moisture_status = "no_data"
        elif trigger_pct is not None and current_moisture < trigger_pct:
            moisture_status = "below_trigger"
        elif target_min is not None and current_moisture < target_min:
            moisture_status = "below_target"
        elif target_min is not None and target_max is not None and target_min <= current_moisture <= target_max:
            moisture_status = "in_range"
        else:
            moisture_status = "above_target"

        result = {
            "zone_id": zone_id,
            "location_id": r["location_id"],
            "name": r["name"],
            "zone_code": r["zone_code"],
            "soil_type": r["soil_type"],
            "area_m2": float(r["area_m2"]) if r["area_m2"] else None,
            "depth_cm": float(r["depth_cm"]) if r["depth_cm"] else None,
            "zone_status": r["status"],
            "current_moisture_pct": current_moisture,
            "last_moisture_reading": r["last_moisture_reading"].isoformat() if r["last_moisture_reading"] else None,
            "moisture_status": moisture_status,
            "target_min_pct": target_min,
            "target_max_pct": target_max,
            "irrigation_trigger_pct": trigger_pct,
            "refill_to_pct": float(r["refill_to_pct"]) if r["refill_to_pct"] else None,
            "growth_stage": r["growth_stage"],
            "next_irrigation_start": r["next_irrigation_start"].isoformat() if r["next_irrigation_start"] else None,
            "next_irrigation_volume_l": float(r["next_irrigation_volume_l"]) if r["next_irrigation_volume_l"] else None,
            "next_irrigation_status": r["next_irrigation_status"],
            "last_irrigation_at": r["last_irrigation_at"].isoformat() if r["last_irrigation_at"] else None,
            "last_irrigation_volume_l": float(r["last_irrigation_volume_l"]) if r["last_irrigation_volume_l"] else None,
        }
        return result
    finally:
        cur.close()


def get_irrigation_status(conn, location_id: str) -> dict:
    """Get all zones status for a location."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM irrigation_zone
            WHERE location_id = %s AND status = 'active'
            ORDER BY name
            """,
            (location_id,),
        )
        zone_ids = [row[0] for row in cur.fetchall()]
    finally:
        cur.close()

    zones = []
    for zid in zone_ids:
        zones.append(get_zone_status(conn, zid))

    return {
        "location_id": location_id,
        "zone_count": len(zones),
        "zones": zones,
    }


def get_water_efficiency(conn, location_id: str, days: int = 30) -> dict:
    """Get water efficiency metrics for a location."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                wlog.zone_id,
                iz.name AS zone_name,
                COUNT(*) AS event_count,
                SUM(wlog.volume_l) AS total_volume_l,
                AVG(wlog.volume_l) AS avg_volume_l,
                AVG(wlog.application_efficiency_pct) AS avg_efficiency_pct,
                AVG(wlog.distribution_uniformity) AS avg_uniformity,
                AVG(wlog.water_productivity_kg_m3) AS avg_water_productivity,
                SUM(wlog.yield_kg) AS total_yield_kg,
                SUM(wlog.effective_volume_l) AS total_effective_l
            FROM water_efficiency_log wlog
            JOIN irrigation_zone iz ON iz.id = wlog.zone_id
            WHERE iz.location_id = %s
              AND wlog.logged_at >= NOW() - INTERVAL '1 day' * %s
            GROUP BY wlog.zone_id, iz.name
            ORDER BY total_volume_l DESC
            """,
            (location_id, days),
        )
        cols = [d[0] for d in cur.description]
        zones = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Overall totals
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                COALESCE(SUM(volume_l), 0) AS total_volume_l,
                AVG(application_efficiency_pct) AS avg_efficiency_pct,
                AVG(distribution_uniformity) AS avg_uniformity,
                AVG(water_productivity_kg_m3) AS avg_water_productivity
            FROM water_efficiency_log wlog
            JOIN irrigation_zone iz ON iz.id = wlog.zone_id
            WHERE iz.location_id = %s
              AND wlog.logged_at >= NOW() - INTERVAL '1 day' * %s
            """,
            (location_id, days),
        )
        cols = [d[0] for d in cur.description]
        overall = dict(zip(cols, cur.fetchone()))
    finally:
        cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "overall": {
            "total_events": int(overall["total_events"]) if overall["total_events"] else 0,
            "total_volume_l": float(overall["total_volume_l"]) if overall["total_volume_l"] else 0,
            "avg_efficiency_pct": round(float(overall["avg_efficiency_pct"]), 2) if overall["avg_efficiency_pct"] else None,
            "avg_uniformity": round(float(overall["avg_uniformity"]), 2) if overall["avg_uniformity"] else None,
            "avg_water_productivity": round(float(overall["avg_water_productivity"]), 4) if overall["avg_water_productivity"] else None,
        },
        "zones": [
            {
                "zone_id": z["zone_id"],
                "zone_name": z["zone_name"],
                "event_count": int(z["event_count"]),
                "total_volume_l": float(z["total_volume_l"]) if z["total_volume_l"] else 0,
                "avg_volume_l": round(float(z["avg_volume_l"]), 2) if z["avg_volume_l"] else None,
                "avg_efficiency_pct": round(float(z["avg_efficiency_pct"]), 2) if z["avg_efficiency_pct"] else None,
                "avg_uniformity": round(float(z["avg_uniformity"]), 2) if z["avg_uniformity"] else None,
                "avg_water_productivity": round(float(z["avg_water_productivity"]), 4) if z["avg_water_productivity"] else None,
            }
            for z in zones
        ],
    }


def compute_water_balance(conn, zone_id: str) -> dict:
    """Compute water balance: ETc - rainfall - irrigation for a zone."""
    cur = conn.cursor()
    try:
        # Get zone info
        cur.execute(
            "SELECT id, location_id, name, area_m2, depth_cm FROM irrigation_zone WHERE id = %s",
            (zone_id,),
        )
        zone_row = cur.fetchone()
        if not zone_row:
            return {"zone_id": zone_id, "error": "zone_not_found"}
        area_m2 = float(zone_row[3]) if zone_row[3] else 0
        location_id = zone_row[1]

        # Get total irrigation volume in last 7 days
        cur.execute(
            """
            SELECT COALESCE(SUM(volume_l), 0)
            FROM irrigation_event
            WHERE zone_id = %s AND started_at >= NOW() - INTERVAL '7 days'
            """,
            (zone_id,),
        )
        irrigation_l = float(cur.fetchone()[0])

        # Get total rainfall in last 7 days (mm) for this location
        cur.execute(
            """
            SELECT COALESCE(SUM(precipitation_mm), 0)
            FROM weather_observation
            WHERE location_id = %s
              AND observation_date >= CURRENT_DATE - 7
            """,
            (location_id,),
        )
        rainfall_mm = float(cur.fetchone()[0])
        rainfall_l = rainfall_mm * area_m2  # Convert mm over area to liters

        # Get estimated ETc in last 7 days
        cur.execute(
            """
            SELECT COALESCE(SUM(etc_mm), 0)
            FROM irrigation_event
            WHERE zone_id = %s AND started_at >= NOW() - INTERVAL '7 days'
              AND etc_mm IS NOT NULL
            """,
            (zone_id,),
        )
        etc_mm_total = float(cur.fetchone()[0])
        etc_l = etc_mm_total * area_m2

        # Get current soil moisture
        cur.execute(
            """
            SELECT reading_value
            FROM sensor_reading sr
            JOIN irrigation_zone iz ON iz.sensor_device_id = sr.sensor_id
            WHERE iz.id = %s AND sr.sensor_type = 'soil_moisture'
            ORDER BY sr.reading_time DESC LIMIT 1
            """,
            (zone_id,),
        )
        moisture_row = cur.fetchone()
        current_moisture = float(moisture_row[0]) if moisture_row and moisture_row[0] else None
    finally:
        cur.close()

    # Water balance = irrigation + rainfall - ETc (in liters)
    net_balance_l = irrigation_l + rainfall_l - etc_l

    return {
        "zone_id": zone_id,
        "period_days": 7,
        "irrigation_liters": round(irrigation_l, 2),
        "rainfall_mm": round(rainfall_mm, 2),
        "rainfall_liters": round(rainfall_l, 2),
        "etc_mm": round(etc_mm_total, 4),
        "etc_liters": round(etc_l, 2),
        "net_balance_liters": round(net_balance_l, 2),
        "current_moisture_pct": current_moisture,
        "area_m2": area_m2,
        "status": "surplus" if net_balance_l > 0 else "deficit" if net_balance_l < 0 else "balanced",
    }


def optimize_schedule(conn, zone_id: str) -> dict:
    """Optimize irrigation schedule using ETc and soil moisture balance."""
    cur = conn.cursor()
    try:
        # Get current schedule
        cur.execute(
            """
            SELECT id, scheduled_start, planned_volume_l, etc_mm,
                   rainfall_forecast_mm, current_soil_moisture_pct
            FROM irrigation_schedule
            WHERE zone_id = %s AND status = 'pending'
            ORDER BY scheduled_start ASC LIMIT 1
            """,
            (zone_id,),
        )
        cols = [d[0] for d in cur.description]
        schedule_row = cur.fetchone()
        schedule = dict(zip(cols, schedule_row)) if schedule_row else None

        # Get active moisture target
        cur.execute(
            """
            SELECT target_min_pct, target_max_pct, irrigation_trigger_pct, refill_to_pct
            FROM soil_moisture_target
            WHERE zone_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (zone_id,),
        )
        cols = [d[0] for d in cur.description]
        target_row = cur.fetchone()
        target = dict(zip(cols, target_row)) if target_row else None

        # Get zone area
        cur.execute("SELECT area_m2 FROM irrigation_zone WHERE id = %s", (zone_id,))
        zone_row = cur.fetchone()
        area_m2 = float(zone_row[0]) if zone_row and zone_row[0] else 0
    finally:
        cur.close()

    if not target:
        return {
            "zone_id": zone_id,
            "optimized": False,
            "reason": "no_moisture_target",
        }

    current_moisture = float(schedule["current_soil_moisture_pct"]) if schedule and schedule["current_soil_moisture_pct"] else None
    target_min = float(target["target_min_pct"])
    target_max = float(target["target_max_pct"])
    trigger_pct = float(target["irrigation_trigger_pct"])
    refill_pct = float(target["refill_to_pct"])

    if current_moisture is None:
        return {
            "zone_id": zone_id,
            "optimized": False,
            "reason": "no_current_moisture",
        }

    # Calculate deficit from target
    deficit_pct = max(target_min - current_moisture, 0)

    # Convert % deficit to mm: deficit% × depth_cm × 10 (mm per cm)
    depth_cm = 30.0  # default
    deficit_mm = deficit_pct / 100.0 * depth_cm * 10

    # Optimal volume (liters) = deficit_mm × area_m2
    optimal_volume_l = deficit_mm * area_m2

    # Consider current schedule
    current_volume = float(schedule["planned_volume_l"]) if schedule and schedule["planned_volume_l"] else 0
    savings_l = current_volume - optimal_volume_l if current_volume > 0 else 0

    # Determine action
    if current_moisture < trigger_pct:
        action = "irrigate"
        urgency = "high"
    elif current_moisture < target_min:
        action = "irrigate"
        urgency = "medium"
    elif current_moisture > target_max:
        action = "skip"
        urgency = "low"
    else:
        action = "hold"
        urgency = "low"

    result = {
        "zone_id": zone_id,
        "optimized": True,
        "current_moisture_pct": current_moisture,
        "target_range": {"min": target_min, "max": target_max},
        "trigger_pct": trigger_pct,
        "refill_to_pct": refill_pct,
        "deficit_pct": round(deficit_pct, 2),
        "optimal_volume_l": round(optimal_volume_l, 2),
        "current_scheduled_volume_l": current_volume,
        "savings_liters": round(max(savings_l, 0), 2),
        "action": action,
        "urgency": urgency,
    }
    logger.info("Optimized zone %s: %s (%.1f L)", zone_id, action, optimal_volume_l)
    return result


def get_efficiency_report(conn, location_id: str) -> dict:
    """Report on water use efficiency trends for a location."""
    cur = conn.cursor()
    try:
        # Weekly efficiency trends
        cur.execute(
            """
            SELECT
                DATE_TRUNC('week', wlog.logged_at) AS week,
                COUNT(*) AS event_count,
                SUM(wlog.volume_l) AS total_volume_l,
                AVG(wlog.application_efficiency_pct) AS avg_efficiency,
                AVG(wlog.distribution_uniformity) AS avg_uniformity,
                AVG(wlog.water_productivity_kg_m3) AS avg_productivity,
                SUM(wlog.yield_kg) AS total_yield_kg
            FROM water_efficiency_log wlog
            JOIN irrigation_zone iz ON iz.id = wlog.zone_id
            WHERE iz.location_id = %s
            GROUP BY DATE_TRUNC('week', wlog.logged_at)
            ORDER BY week DESC
            LIMIT 12
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        weekly = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Total irrigation volume by zone
        cur.execute(
            """
            SELECT
                iz.id AS zone_id,
                iz.name AS zone_name,
                COALESCE(SUM(ie.volume_l), 0) AS total_irrigated_l,
                COUNT(ie.id) AS total_events
            FROM irrigation_zone iz
            LEFT JOIN irrigation_event ie ON ie.zone_id = iz.id
            WHERE iz.location_id = %s
            GROUP BY iz.id, iz.name
            ORDER BY total_irrigated_l DESC
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        by_zone = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Efficiency summary
        cur.execute(
            """
            SELECT
                AVG(wlog.application_efficiency_pct) AS overall_efficiency,
                AVG(wlog.distribution_uniformity) AS overall_uniformity,
                AVG(wlog.water_productivity_kg_m3) AS overall_productivity,
                SUM(wlog.volume_l) AS total_volume_l,
                SUM(wlog.yield_kg) AS total_yield_kg
            FROM water_efficiency_log wlog
            JOIN irrigation_zone iz ON iz.id = wlog.zone_id
            WHERE iz.location_id = %s
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        summary = dict(zip(cols, cur.fetchone()))
    finally:
        cur.close()

    return {
        "location_id": location_id,
        "summary": {
            "overall_efficiency_pct": round(float(summary["overall_efficiency"]), 2) if summary["overall_efficiency"] else None,
            "overall_uniformity": round(float(summary["overall_uniformity"]), 2) if summary["overall_uniformity"] else None,
            "overall_water_productivity": round(float(summary["overall_productivity"]), 4) if summary["overall_productivity"] else None,
            "total_volume_l": round(float(summary["total_volume_l"]), 2) if summary["total_volume_l"] else 0,
            "total_yield_kg": round(float(summary["total_yield_kg"]), 2) if summary["total_yield_kg"] else 0,
        },
        "by_zone": [
            {
                "zone_id": z["zone_id"],
                "zone_name": z["zone_name"],
                "total_irrigated_l": round(float(z["total_irrigated_l"]), 2),
                "total_events": int(z["total_events"]),
            }
            for z in by_zone
        ],
        "weekly_trends": [
            {
                "week": w["week"].isoformat() if w["week"] else None,
                "event_count": int(w["event_count"]),
                "total_volume_l": round(float(w["total_volume_l"]), 2) if w["total_volume_l"] else 0,
                "avg_efficiency_pct": round(float(w["avg_efficiency"]), 2) if w["avg_efficiency"] else None,
                "avg_uniformity": round(float(w["avg_uniformity"]), 2) if w["avg_uniformity"] else None,
                "avg_water_productivity": round(float(w["avg_productivity"]), 4) if w["avg_productivity"] else None,
            }
            for w in weekly
        ],
    }
