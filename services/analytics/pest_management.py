#!/usr/bin/env python3
"""
Integrated Pest Management (IPM)

Records scouting observations, action thresholds, interventions,
pesticide applications, resistance monitoring, and degree-day modeling.

Usage:
    python -m services.analytics.pest_management record-scouting --location-id UUID --pest fall_armyworm --type insect --severity moderate
    python -m services.analytics.pest_management set-threshold --location-id UUID --pest fall_armyworm --crop maize --eil 2.0 --et 1.0
    python -m services.analytics.pest_management check-threshold --location-id UUID --pest fall_armyworm --crop maize --count 3
    python -m services.analytics.pest_management record-intervention --scouting-id UUID --type biological --method "Bt spray"
    python -m services.analytics.pest_management record-pesticide --product "Bt spray" --ingredient "Bacillus thuringiensis" --class bioinsecticide --rate 2.0 --area 1.0
    python -m services.analytics.pest_management record-resistance --pest fall_armyworm --class pyrethroid --level moderate
    python -m services.analytics.pest_management record-degree-day --pest fall_armyworm --base 10.0 --max 38.0 --min 25.0
    python -m services.analytics.pest_management summary --location-id UUID
    python -m services.analytics.pest_management pesticide-usage --location-id UUID --days 30
    python -m services.analytics.pest_management degree-day-tracking --location-id UUID --pest fall_armyworm
    python -m services.analytics.pest_management recommend --scouting-id UUID
    python -m services.analytics.pest_management dashboard --location-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.pest_management")


# ============================================================
# Scouting
# ============================================================

def record_scouting(
    conn,
    location_id: str,
    pest_name: str,
    pest_type: str = None,
    severity: str = None,
    incidence_pct: float = None,
    damage_pct: float = None,
    plot_id: str = None,
    zone_id: str = None,
    scout_date: date = None,
    beneficial_observed: str = None,
    weather_conditions: dict = None,
    photo_url: str = None,
    notes: str = None,
    source_type: str = "manual",
    source_system: str = None,
    source_id: str = None,
    metadata: dict = None,
) -> dict:
    """Record a field scouting observation."""
    cur = conn.cursor()
    record_id = str(uuid.uuid4())

    scout_date = scout_date or date.today()

    cur.execute(
        """
        INSERT INTO pest_scouting_record
            (id, location_id, plot_id, zone_id,
             scout_date, pest_name, pest_type, severity,
             incidence_pct, damage_pct,
             beneficial_observed, weather_conditions,
             photo_url, notes,
             source_type, source_system, source_id,
             status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, 'draft', %s::jsonb)
        RETURNING id
        """,
        (
            record_id, location_id, plot_id, zone_id,
            scout_date, pest_name, pest_type, severity,
            incidence_pct, damage_pct,
            beneficial_observed, json.dumps(weather_conditions or {}),
            photo_url, notes,
            source_type, source_system, source_id,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "scouting_id": record_id,
        "location_id": location_id,
        "pest_name": pest_name,
        "pest_type": pest_type,
        "severity": severity,
        "incidence_pct": incidence_pct,
        "damage_pct": damage_pct,
        "scout_date": scout_date.isoformat(),
    }


# ============================================================
# Action Thresholds
# ============================================================

def set_action_threshold(
    conn,
    location_id: str,
    pest_name: str,
    crop_name: str = None,
    economic_injury_level: float = None,
    economic_threshold: float = None,
    threshold_unit: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Set IPM action thresholds for a pest-crop combination."""
    cur = conn.cursor()
    threshold_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pest_action_threshold
            (id, location_id, pest_name, crop_name,
             economic_injury_level, economic_threshold, threshold_unit,
             notes, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s::jsonb)
        RETURNING id
        """,
        (
            threshold_id, location_id, pest_name, crop_name,
            economic_injury_level, economic_threshold, threshold_unit,
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "threshold_id": threshold_id,
        "location_id": location_id,
        "pest_name": pest_name,
        "crop_name": crop_name,
        "economic_injury_level": economic_injury_level,
        "economic_threshold": economic_threshold,
        "threshold_unit": threshold_unit,
    }


# ============================================================
# Threshold Check
# ============================================================

def check_threshold(
    conn,
    location_id: str,
    pest_name: str,
    crop_name: str = None,
    current_count: float = 0.0,
) -> dict:
    """Check if pest count exceeds economic threshold and recommend action."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, economic_injury_level, economic_threshold, threshold_unit, notes
        FROM pest_action_threshold
        WHERE location_id = %s
          AND pest_name = %s
          AND (%s IS NULL OR crop_name = %s)
          AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (location_id, pest_name, crop_name, crop_name),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return {
            "location_id": location_id,
            "pest_name": pest_name,
            "crop_name": crop_name,
            "current_count": current_count,
            "threshold_found": False,
            "action_recommended": "monitor",
            "message": "No active threshold defined for this pest-crop combination.",
        }

    threshold_id, eil, et, unit, notes = row
    above_et = et is not None and current_count >= et
    above_eil = eil is not None and current_count >= eil

    if above_eil:
        action = "immediate_intervention"
        message = f"Count {current_count} exceeds EIL ({eil}). Immediate control required."
    elif above_et:
        action = "intervention_recommended"
        message = f"Count {current_count} exceeds ET ({et}). Schedule intervention."
    else:
        action = "continue_monitoring"
        message = f"Count {current_count} below ET ({et}). Continue scouting."

    return {
        "location_id": location_id,
        "pest_name": pest_name,
        "crop_name": crop_name,
        "threshold_id": threshold_id,
        "current_count": current_count,
        "economic_threshold": et,
        "economic_injury_level": eil,
        "threshold_unit": unit,
        "above_threshold": above_et,
        "above_eil": above_eil,
        "action_recommended": action,
        "message": message,
    }


# ============================================================
# Interventions
# ============================================================

def record_intervention(
    conn,
    location_id: str,
    intervention_type: str,
    scouting_record_id: str = None,
    method_name: str = None,
    target_pest: str = None,
    application_rate: float = None,
    application_unit: str = None,
    area_ha: float = None,
    cost: float = None,
    effective: bool = None,
    effectiveness_pct: float = None,
    notes: str = None,
    intervention_date: date = None,
    metadata: dict = None,
) -> dict:
    """Record a pest control intervention."""
    cur = conn.cursor()
    intervention_id = str(uuid.uuid4())

    intervention_date = intervention_date or date.today()

    cur.execute(
        """
        INSERT INTO pest_intervention
            (id, location_id, scouting_record_id,
             intervention_date, intervention_type, method_name,
             target_pest, application_rate, application_unit,
             area_ha, cost, effective, effectiveness_pct,
             notes, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'applied', %s::jsonb)
        RETURNING id
        """,
        (
            intervention_id, location_id, scouting_record_id,
            intervention_date, intervention_type, method_name,
            target_pest, application_rate, application_unit,
            area_ha, cost, effective, effectiveness_pct,
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "intervention_id": intervention_id,
        "location_id": location_id,
        "scouting_record_id": scouting_record_id,
        "intervention_type": intervention_type,
        "method_name": method_name,
        "target_pest": target_pest,
        "intervention_date": intervention_date.isoformat(),
    }


# ============================================================
# Pesticide Application
# ============================================================

def record_pesticide_application(
    conn,
    location_id: str,
    product_name: str,
    active_ingredient: str = None,
    chemical_class: str = None,
    application_rate: float = None,
    rate_unit: str = None,
    area_ha: float = None,
    total_volume: float = None,
    volume_unit: str = None,
    target_pest: str = None,
    rei_days: int = None,
    phi_days: int = None,
    notes: str = None,
    application_date: date = None,
    metadata: dict = None,
) -> dict:
    """Log a pesticide/chemical application."""
    cur = conn.cursor()
    log_id = str(uuid.uuid4())

    application_date = application_date or date.today()

    cur.execute(
        """
        INSERT INTO pesticide_application_log
            (id, location_id, application_date,
             product_name, active_ingredient, chemical_class,
             application_rate, rate_unit, area_ha,
             total_volume, volume_unit,
             target_pest, rei_days, phi_days,
             notes, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'applied', %s::jsonb)
        RETURNING id
        """,
        (
            log_id, location_id, application_date,
            product_name, active_ingredient, chemical_class,
            application_rate, rate_unit, area_ha,
            total_volume, volume_unit,
            target_pest, rei_days, phi_days,
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "application_id": log_id,
        "location_id": location_id,
        "product_name": product_name,
        "active_ingredient": active_ingredient,
        "chemical_class": chemical_class,
        "area_ha": area_ha,
        "application_date": application_date.isoformat(),
    }


# ============================================================
# Resistance Monitoring
# ============================================================

def record_resistance(
    conn,
    location_id: str,
    pest_name: str,
    chemical_class: str,
    resistance_level: str,
    observation_date: date = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a pest resistance observation."""
    cur = conn.cursor()
    record_id = str(uuid.uuid4())

    observation_date = observation_date or date.today()

    cur.execute(
        """
        INSERT INTO pest_resistance_record
            (id, location_id, pest_name, chemical_class,
             resistance_level, observation_date, notes,
             status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s::jsonb)
        RETURNING id
        """,
        (
            record_id, location_id, pest_name, chemical_class,
            resistance_level, observation_date, notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "resistance_id": record_id,
        "location_id": location_id,
        "pest_name": pest_name,
        "chemical_class": chemical_class,
        "resistance_level": resistance_level,
        "observation_date": observation_date.isoformat(),
    }


# ============================================================
# Degree-Day Recording
# ============================================================

def record_degree_day(
    conn,
    location_id: str,
    pest_name: str,
    record_date: date = None,
    base_temp: float = 10.0,
    max_temp: float = None,
    min_temp: float = None,
    upper_temp: float = None,
    source: str = "sensor",
    metadata: dict = None,
) -> dict:
    """Record temperature data and compute daily degree-day accumulation."""
    cur = conn.cursor()
    dd_id = str(uuid.uuid4())

    record_date = record_date or date.today()

    degree_days = 0.0
    if max_temp is not None and min_temp is not None and base_temp is not None:
        t_upper = upper_temp or 38.0
        t_max = min(max_temp, t_upper)
        t_min = max(min_temp, base_temp)
        degree_days = max(0.0, ((t_max + t_min) / 2.0) - base_temp)

    cur.execute(
        """
        SELECT COALESCE(MAX(cumulative_degree_days), 0)
        FROM degree_day_record
        WHERE location_id = %s AND pest_name = %s
          AND record_date = (SELECT MAX(record_date) FROM degree_day_record WHERE location_id = %s AND pest_name = %s)
        """,
        (location_id, pest_name, location_id, pest_name),
    )
    prev_cumulative = cur.fetchone()[0] or 0.0
    cumulative = prev_cumulative + degree_days

    cur.execute(
        """
        SELECT stages FROM pest_degree_day_config WHERE pest_name = %s AND status = 'active' LIMIT 1
        """,
        (pest_name,),
    )
    config_row = cur.fetchone()
    lifecycle_stage = None
    if config_row:
        stages = config_row[0] or []
        for stage in stages:
            if stage.get("dd_start", 0) <= cumulative <= stage.get("dd_end", 9999):
                lifecycle_stage = stage.get("name")
                break

    cur.execute(
        """
        INSERT INTO degree_day_record
            (id, location_id, record_date, base_temp, upper_temp,
             max_temp, min_temp, degree_days, cumulative_degree_days,
             pest_name, lifecycle_stage, source, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'recorded', %s::jsonb)
        RETURNING id
        """,
        (
            dd_id, location_id, record_date, base_temp, upper_temp,
            max_temp, min_temp, round(degree_days, 2), round(cumulative, 2),
            pest_name, lifecycle_stage, source, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "degree_day_id": dd_id,
        "location_id": location_id,
        "pest_name": pest_name,
        "record_date": record_date.isoformat(),
        "degree_days": round(degree_days, 2),
        "cumulative_degree_days": round(cumulative, 2),
        "lifecycle_stage": lifecycle_stage,
    }


# ============================================================
# Scouting Summary
# ============================================================

def get_pest_summary(conn, location_id: str) -> dict:
    """Get pest scouting summary with intervention counts."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT pest_name, pest_type, severity,
               COUNT(*) AS observations,
               AVG(incidence_pct) AS avg_incidence,
               AVG(damage_pct) AS avg_damage,
               MAX(scout_date) AS last_scouted
        FROM pest_scouting_record
        WHERE location_id = %s AND status != 'draft'
        GROUP BY pest_name, pest_type, severity
        ORDER BY observations DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    pests = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT intervention_type, COUNT(*) AS count
        FROM pest_intervention
        WHERE location_id = %s AND status = 'applied'
        GROUP BY intervention_type
        """,
        (location_id,),
    )
    interventions = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_record
        WHERE location_id = %s AND severity IN ('high', 'severe')
        AND status != 'draft'
        """,
        (location_id,),
    )
    high_severity = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_resistance_record
        WHERE location_id = %s AND resistance_level IN ('high', 'confirmed')
        AND status = 'active'
        """,
        (location_id,),
    )
    resistance_alerts = cur.fetchone()[0]

    cur.close()

    return {
        "location_id": location_id,
        "pests": pests,
        "intervention_counts": interventions,
        "high_severity_count": high_severity,
        "resistance_alerts": resistance_alerts,
    }


# ============================================================
# Pesticide Usage
# ============================================================

def get_pesticide_usage(conn, location_id: str, days: int = 30) -> dict:
    """Get chemical use totals by period."""
    cur = conn.cursor()
    since = date.today() - timedelta(days=days)

    cur.execute(
        """
        SELECT chemical_class, product_name,
               COUNT(*) AS application_count,
               SUM(COALESCE(total_volume, 0)) AS total_volume,
               volume_unit,
               SUM(COALESCE(area_ha, 0)) AS total_area_treated,
               AVG(rei_days) AS avg_rei_days,
               AVG(phi_days) AS avg_phi_days
        FROM pesticide_application_log
        WHERE location_id = %s
          AND application_date >= %s
          AND status = 'applied'
        GROUP BY chemical_class, product_name, volume_unit
        ORDER BY total_volume DESC
        """,
        (location_id, since),
    )
    cols = [d[0] for d in cur.description]
    usage = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(total_volume), 0)
        FROM pesticide_application_log
        WHERE location_id = %s
          AND application_date >= %s
          AND status = 'applied'
        """,
        (location_id, since),
    )
    totals = cur.fetchone()

    cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "since": since.isoformat(),
        "total_applications": totals[0],
        "total_volume_used": float(totals[1]),
        "by_class_product": usage,
    }


# ============================================================
# Degree-Day Tracking
# ============================================================

def get_degree_day_tracking(conn, location_id: str, pest_name: str) -> dict:
    """Get cumulative degree days and lifecycle stage."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT record_date, base_temp, upper_temp,
               max_temp, min_temp, degree_days,
               cumulative_degree_days, lifecycle_stage, source
        FROM degree_day_record
        WHERE location_id = %s AND pest_name = %s
        ORDER BY record_date DESC
        LIMIT 30
        """,
        (location_id, pest_name),
    )
    cols = [d[0] for d in cur.description]
    records = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT dd.total_degree_days, dd.stages
        FROM pest_degree_day_config dd
        WHERE dd.pest_name = %s AND dd.status = 'active'
        """,
        (pest_name,),
    )
    config_row = cur.fetchone()
    total_dd = config_row[0] if config_row else None
    stages = config_row[1] if config_row else []

    cur.execute(
        """
        SELECT tat.economic_threshold, tat.economic_injury_level
        FROM pest_action_threshold tat
        WHERE tat.location_id = %s AND tat.pest_name = %s AND tat.status = 'active'
        LIMIT 1
        """,
        (location_id, pest_name),
    )
    threshold_row = cur.fetchone()

    cur.close()

    current_cumulative = records[0]["cumulative_degree_days"] if records else 0.0
    current_stage = records[0]["lifecycle_stage"] if records else None

    return {
        "location_id": location_id,
        "pest_name": pest_name,
        "total_degree_days_for_lifecycle": float(total_dd) if total_dd else None,
        "current_cumulative": float(current_cumulative) if current_cumulative else 0.0,
        "current_stage": current_stage,
        "threshold": float(threshold_row[0]) if threshold_row and threshold_row[0] else None,
        "eil": float(threshold_row[1]) if threshold_row and threshold_row[1] else None,
        "stages": stages,
        "recent_records": records,
    }


# ============================================================
# Intervention Recommendation
# ============================================================

def recommend_intervention(conn, scouting_record_id: str) -> dict:
    """Recommend IPM intervention ladder based on scouting observation."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, location_id, pest_name, pest_type, severity,
               incidence_pct, damage_pct, beneficial_observed
        FROM pest_scouting_record
        WHERE id = %s
        """,
        (scouting_record_id,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": "Scouting record not found"}

    _, location_id, pest_name, pest_type, severity, incidence, damage, beneficials = row

    severity = severity or "low"
    incidence = float(incidence) if incidence else 0.0
    damage = float(damage) if damage else 0.0

    ladder = []

    if severity in ("none", "low") and incidence < 10:
        ladder.append({
            "priority": 1,
            "type": "cultural",
            "method": "Monitor and use resistant varieties",
            "rationale": "Low pressure; cultural practices sufficient.",
        })
    elif severity == "low" or (severity == "moderate" and incidence < 25):
        ladder.append({
            "priority": 1,
            "type": "biological",
            "method": "Conserve natural enemies; augment with parasitoids",
            "rationale": "Moderate pressure; biological control can suppress.",
        })
        ladder.append({
            "priority": 2,
            "type": "cultural",
            "method": "Trap crops, crop rotation, adjust planting date",
            "rationale": "Reduce pest habitat and breeding sites.",
        })
    elif severity == "moderate" or (severity == "high" and damage < 20):
        ladder.append({
            "priority": 1,
            "type": "biological",
            "method": "Augmentative biological control (Trichogramma, Beauveria)",
            "rationale": "Biological agents still viable at this level.",
        })
        ladder.append({
            "priority": 2,
            "type": "cultural",
            "method": "Trap crops, intercropping, sanitation",
            "rationale": "Cultural disruption of pest lifecycle.",
        })
        ladder.append({
            "priority": 3,
            "type": "mechanical",
            "method": "Hand-picking, barriers, pheromone traps",
            "rationale": "Direct reduction of pest population.",
        })
    else:
        ladder.append({
            "priority": 1,
            "type": "mechanical",
            "method": "Hand-picking, pruning affected parts, barriers",
            "rationale": "Immediate mechanical reduction before chemical option.",
        })
        ladder.append({
            "priority": 2,
            "type": "biological",
            "method": "Beauveria bassiana, Bt, or neem-based products",
            "rationale": "Biopesticides for moderate chemical reduction.",
        })
        ladder.append({
            "priority": 3,
            "type": "chemical",
            "method": "Targeted, narrow-spectrum application (rotate classes)",
            "rationale": "Last resort; use selective chemistry and rotate to delay resistance.",
            "caution": "Check resistance records before selecting chemical class.",
        })

    return {
        "scouting_record_id": scouting_record_id,
        "pest_name": pest_name,
        "severity": severity,
        "incidence_pct": incidence,
        "damage_pct": damage,
        "recommendations": ladder,
        "note": "Always apply the lowest-impact intervention first. Escalate only if monitoring shows continued increase.",
    }


# ============================================================
# Pest Dashboard
# ============================================================

def get_pest_dashboard(conn, location_id: str) -> dict:
    """Aggregated pest management dashboard."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT pest_name, pest_type, severity, COUNT(*) AS count,
               AVG(incidence_pct) AS avg_incidence,
               AVG(damage_pct) AS avg_damage,
               MAX(scout_date) AS last_scouted
        FROM pest_scouting_record
        WHERE location_id = %s AND status != 'draft'
        GROUP BY pest_name, pest_type, severity
        ORDER BY count DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    pest_activity = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT intervention_type, COUNT(*) AS count,
               AVG(effectiveness_pct) AS avg_effectiveness
        FROM pest_intervention
        WHERE location_id = %s AND status = 'applied'
        GROUP BY intervention_type
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    interventions = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT chemical_class, COUNT(*) AS applications,
               SUM(COALESCE(total_volume, 0)) AS total_volume,
               volume_unit
        FROM pesticide_application_log
        WHERE location_id = %s AND status = 'applied'
        GROUP BY chemical_class, volume_unit
        ORDER BY total_volume DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    chemical_use = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT pest_name, chemical_class, resistance_level
        FROM pest_resistance_record
        WHERE location_id = %s AND resistance_level IN ('high', 'confirmed')
        AND status = 'active'
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    resistance_alerts = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT pest_name,
               MAX(cumulative_degree_days) AS current_cdd,
               MAX(lifecycle_stage) AS current_stage,
               MAX(record_date) AS last_recorded
        FROM degree_day_record
        WHERE location_id = %s
        GROUP BY pest_name
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    degree_days = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_record
        WHERE location_id = %s AND severity IN ('high', 'severe') AND status != 'draft'
        """,
        (location_id,),
    )
    high_severity = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_intervention
        WHERE location_id = %s AND status = 'applied'
        """,
        (location_id,),
    )
    total_interventions = cur.fetchone()[0]

    cur.close()

    return {
        "location_id": location_id,
        "pest_activity": pest_activity,
        "interventions": interventions,
        "chemical_use": chemical_use,
        "resistance_alerts": resistance_alerts,
        "degree_days": degree_days,
        "high_severity_count": high_severity,
        "total_interventions": total_interventions,
    }


# ============================================================
# Pest Biology Reference
# ============================================================

def add_pest_reference(
    conn,
    pest_name: str,
    scientific_name: str = None,
    common_name: str = None,
    pest_category: str = None,
    base_temp: float = None,
    upper_temp: float = None,
    total_degree_days: float = None,
    stages: list = None,
    host_crops: list = None,
    natural_enemies: list = None,
    damage_description: str = None,
    economic_importance: str = None,
    geographic_range: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Add a pest biology reference record."""
    cur = conn.cursor()
    ref_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pest_biology_reference
            (id, pest_name, scientific_name, common_name, pest_category,
             base_temp, upper_temp, total_degree_days, stages,
             host_crops, natural_enemies, damage_description,
             economic_importance, geographic_range, notes, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (pest_name) DO UPDATE SET
            scientific_name = EXCLUDED.scientific_name,
            common_name = EXCLUDED.common_name,
            pest_category = EXCLUDED.pest_category,
            base_temp = EXCLUDED.base_temp,
            upper_temp = EXCLUDED.upper_temp,
            total_degree_days = EXCLUDED.total_degree_days,
            stages = EXCLUDED.stages,
            host_crops = EXCLUDED.host_crops,
            natural_enemies = EXCLUDED.natural_enemies,
            damage_description = EXCLUDED.damage_description,
            economic_importance = EXCLUDED.economic_importance,
            geographic_range = EXCLUDED.geographic_range,
            updated_at = NOW()
        RETURNING id
        """,
        (
            ref_id, pest_name, scientific_name, common_name, pest_category,
            base_temp, upper_temp, total_degree_days,
            json.dumps(stages or []),
            json.dumps(host_crops or []),
            json.dumps(natural_enemies or []),
            damage_description, economic_importance, geographic_range,
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "reference_id": ref_id,
        "pest_name": pest_name,
        "scientific_name": scientific_name,
        "common_name": common_name,
    }


def get_pest_reference(conn, pest_name: str) -> dict:
    """Look up a pest biology reference by name."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, pest_name, scientific_name, common_name, pest_category,
               base_temp, upper_temp, total_degree_days, stages,
               host_crops, natural_enemies, damage_description,
               economic_importance, geographic_range
        FROM pest_biology_reference
        WHERE pest_name = %s AND status = 'active'
        """,
        (pest_name,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": f"Reference not found for {pest_name}"}

    return {
        "reference_id": row[0],
        "pest_name": row[1],
        "scientific_name": row[2],
        "common_name": row[3],
        "pest_category": row[4],
        "base_temp": float(row[5]) if row[5] else None,
        "upper_temp": float(row[6]) if row[6] else None,
        "total_degree_days": float(row[7]) if row[7] else None,
        "stages": row[8] or [],
        "host_crops": row[9] or [],
        "natural_enemies": row[10] or [],
        "damage_description": row[11],
        "economic_importance": row[12],
        "geographic_range": row[13],
    }


def list_pest_references(conn, pest_category: str = None, host_crop: str = None) -> dict:
    """List pest biology references, optionally filtered by category or host crop."""
    cur = conn.cursor()

    conditions = ["status = 'active'"]
    params = []

    if pest_category:
        conditions.append("pest_category = %s")
        params.append(pest_category)

    if host_crop:
        conditions.append("host_crops @> %s::jsonb")
        params.append(json.dumps([host_crop]))

    where = " AND ".join(conditions)

    cur.execute(
        f"""
        SELECT pest_name, scientific_name, common_name, pest_category,
               economic_importance, host_crops
        FROM pest_biology_reference
        WHERE {where}
        ORDER BY economic_importance, pest_name
        """,
        params,
    )
    cols = [d[0] for d in cur.description]
    refs = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    return {
        "total": len(refs),
        "pest_category": pest_category,
        "host_crop": host_crop,
        "references": refs,
    }


# ============================================================
# Scouting Schedules
# ============================================================

def create_scouting_schedule(
    conn,
    location_id: str,
    pest_name: str,
    frequency_days: int = 7,
    crop_name: str = None,
    growth_stages: list = None,
    method: str = None,
    sample_size: int = None,
    assigned_to: str = None,
    start_date: date = None,
    end_date: date = None,
    metadata: dict = None,
) -> dict:
    """Create a scouting schedule for a pest at a location."""
    cur = conn.cursor()
    schedule_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pest_scouting_schedule
            (id, location_id, pest_name, crop_name, frequency_days,
             growth_stages, method, sample_size, assigned_to,
             start_date, end_date, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, 'active', %s::jsonb)
        RETURNING id
        """,
        (
            schedule_id, location_id, pest_name, crop_name, frequency_days,
            json.dumps(growth_stages or []), method, sample_size, assigned_to,
            start_date, end_date, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "schedule_id": schedule_id,
        "location_id": location_id,
        "pest_name": pest_name,
        "frequency_days": frequency_days,
        "status": "active",
    }


def get_due_scouting(conn, location_id: str) -> dict:
    """Get scouting schedules that are due or overdue."""
    cur = conn.cursor()
    today = date.today()

    cur.execute(
        """
        SELECT id, pest_name, crop_name, frequency_days, assigned_to,
               start_date, end_date,
               (SELECT MAX(scout_date) FROM pest_scouting_compliance psc
                WHERE psc.schedule_id = pss.id) AS last_scouted
        FROM pest_scouting_schedule pss
        WHERE pss.location_id = %s AND pss.status = 'active'
          AND (pss.end_date IS NULL OR pss.end_date >= %s)
        ORDER BY pest_name
        """,
        (location_id, today),
    )
    cols = [d[0] for d in cur.description]
    schedules = []
    for row in cur.fetchall():
        row_dict = dict(zip(cols, row))
        last_scouted = row_dict["last_scouted"]
        freq = row_dict["frequency_days"]
        if last_scouted:
            days_since = (today - last_scouted).days
            row_dict["days_since_last_scout"] = days_since
            row_dict["overdue"] = days_since >= freq
            row_dict["next_due"] = (last_scouted + timedelta(days=freq)).isoformat()
        else:
            row_dict["days_since_last_scout"] = None
            row_dict["overdue"] = True
            row_dict["next_due"] = (row_dict["start_date"] or today).isoformat()
        row_dict["schedule_id"] = row_dict.pop("id")
        schedules.append(row_dict)

    cur.close()

    return {
        "location_id": location_id,
        "date": today.isoformat(),
        "total_schedules": len(schedules),
        "overdue_count": sum(1 for s in schedules if s["overdue"]),
        "schedules": schedules,
    }


def record_scouting_completion(
    conn,
    schedule_id: str,
    scouting_record_id: str,
    scout_date: date = None,
    notes: str = None,
) -> dict:
    """Mark a scheduled scouting as completed and update compliance."""
    cur = conn.cursor()
    compliance_id = str(uuid.uuid4())
    scout_date = scout_date or date.today()

    cur.execute(
        """
        SELECT id, frequency_days FROM pest_scouting_schedule
        WHERE id = %s AND status = 'active'
        """,
        (schedule_id,),
    )
    schedule_row = cur.fetchone()
    if not schedule_row:
        cur.close()
        return {"error": "Schedule not found"}

    cur.execute(
        """
        SELECT MAX(scout_date) FROM pest_scouting_compliance
        WHERE schedule_id = %s AND status != 'skipped'
        """,
        (schedule_id,),
    )
    last_row = cur.fetchone()
    last_date = last_row[0] if last_row and last_row[0] else None

    if last_date:
        days_diff = (scout_date - last_date).days
        freq = schedule_row[1]
        if days_diff <= freq:
            compliance_status = "on_time"
        elif days_diff <= freq + 3:
            compliance_status = "late"
        else:
            compliance_status = "late"
    else:
        compliance_status = "on_time"

    expected_date = last_date + timedelta(days=schedule_row[1]) if last_date else scout_date

    cur.execute(
        """
        INSERT INTO pest_scouting_compliance
            (id, schedule_id, scout_date, expected_date, status,
             scouting_record_id, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (compliance_id, schedule_id, scout_date, expected_date,
         compliance_status, scouting_record_id, notes),
    )
    conn.commit()
    cur.close()

    return {
        "compliance_id": compliance_id,
        "schedule_id": schedule_id,
        "scouting_record_id": scouting_record_id,
        "scout_date": scout_date.isoformat(),
        "status": compliance_status,
    }


def get_scouting_compliance(conn, location_id: str, days: int = 30) -> dict:
    """Get scouting compliance statistics for a location."""
    cur = conn.cursor()
    since = date.today() - timedelta(days=days)

    cur.execute(
        """
        SELECT
            pss.pest_name,
            pss.crop_name,
            pss.frequency_days,
            COUNT(psc.id) AS total_scheduled,
            COUNT(psc.id) FILTER (WHERE psc.status = 'on_time') AS on_time,
            COUNT(psc.id) FILTER (WHERE psc.status = 'late') AS late,
            COUNT(psc.id) FILTER (WHERE psc.status = 'missed') AS missed,
            COUNT(psc.id) FILTER (WHERE psc.status = 'skipped') AS skipped,
            CASE WHEN COUNT(psc.id) > 0 THEN
                ROUND(100.0 * COUNT(psc.id) FILTER (WHERE psc.status = 'on_time') / COUNT(psc.id), 1)
            ELSE NULL END AS compliance_pct
        FROM pest_scouting_schedule pss
        LEFT JOIN pest_scouting_compliance psc ON psc.schedule_id = pss.id
            AND psc.scout_date >= %s
        WHERE pss.location_id = %s AND pss.status = 'active'
        GROUP BY pss.id, pss.pest_name, pss.crop_name, pss.frequency_days
        ORDER BY pss.pest_name
        """,
        (since, location_id),
    )
    cols = [d[0] for d in cur.description]
    compliance = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    total = sum(c["total_scheduled"] for c in compliance)
    on_time = sum(c["on_time"] for c in compliance)
    overall_pct = round(100.0 * on_time / total, 1) if total > 0 else None

    return {
        "location_id": location_id,
        "period_days": days,
        "overall_compliance_pct": overall_pct,
        "by_pest": compliance,
    }


# ============================================================
# Re-Scout and Intervention Evaluation
# ============================================================

def schedule_re_scout(
    conn,
    intervention_id: str,
    re_scout_date: date,
) -> dict:
    """Set a follow-up re-scout date for an intervention."""
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE pest_intervention
        SET re_scout_date = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """,
        (re_scout_date, intervention_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"error": "Intervention not found"}

    return {
        "intervention_id": intervention_id,
        "re_scout_date": re_scout_date.isoformat(),
    }


def evaluate_intervention(
    conn,
    intervention_id: str,
    re_scout_record_id: str,
    effectiveness_pct: float,
) -> dict:
    """Evaluate intervention effectiveness using a re-scout record."""
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE pest_intervention
        SET re_scout_record_id = %s,
            actual_effectiveness_pct = %s,
            effective = (%s >= 50),
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, intervention_type, target_pest, effectiveness_pct
        """,
        (re_scout_record_id, effectiveness_pct, effectiveness_pct, intervention_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"error": "Intervention not found"}

    return {
        "intervention_id": intervention_id,
        "re_scout_record_id": re_scout_record_id,
        "actual_effectiveness_pct": effectiveness_pct,
        "effective": effectiveness_pct >= 50,
    }


# ============================================================
# IPM Compliance Score
# ============================================================

def compute_ipm_compliance_score(
    conn,
    location_id: str,
    period_start: date = None,
    period_end: date = None,
) -> dict:
    """Compute 0-100 IPM compliance score from scouting, thresholds, ladder, records."""
    cur = conn.cursor()

    period_end = period_end or date.today()
    period_start = period_start or (period_end - timedelta(days=90))

    scouting_score = 0.0
    threshold_score = 0.0
    ladder_score = 0.0
    completeness_score = 0.0

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_record
        WHERE location_id = %s AND scout_date BETWEEN %s AND %s AND status != 'draft'
        """,
        (location_id, period_start, period_end),
    )
    total_scouts = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_schedule
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    total_schedules = cur.fetchone()[0]

    if total_schedules > 0:
        cur.execute(
            """
            SELECT COUNT(*) FROM pest_scouting_compliance psc
            JOIN pest_scouting_schedule pss ON pss.id = psc.schedule_id
            WHERE pss.location_id = %s AND psc.scout_date BETWEEN %s AND %s
              AND psc.status = 'on_time'
            """,
            (location_id, period_start, period_end),
        )
        on_time = cur.fetchone()[0]
        expected = total_schedules * max(1, (period_end - period_start).days // 7)
        scouting_score = min(100.0, 100.0 * on_time / max(1, expected))
    elif total_scouts > 0:
        scouting_score = 70.0

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_intervention pi
        WHERE pi.location_id = %s
          AND pi.intervention_date BETWEEN %s AND %s
          AND pi.intervention_type = 'chemical'
          AND EXISTS (
              SELECT 1 FROM pest_scouting_record psr
              WHERE psr.id = pi.scouting_record_id
                AND psr.severity IN ('none', 'low')
                AND COALESCE(psr.incidence_pct, 0) < 10
          )
        """,
        (location_id, period_start, period_end),
    )
    premature_chem = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_intervention
        WHERE location_id = %s
          AND intervention_date BETWEEN %s AND %s
          AND status = 'applied'
        """,
        (location_id, period_start, period_end),
    )
    total_interventions = cur.fetchone()[0]

    if total_interventions > 0:
        threshold_score = max(0, 100.0 - (100.0 * premature_chem / total_interventions))
    else:
        threshold_score = 80.0

    cur.execute(
        """
        SELECT intervention_type FROM pest_intervention
        WHERE location_id = %s
          AND intervention_date BETWEEN %s AND %s
          AND status = 'applied'
        ORDER BY intervention_date
        """,
        (location_id, period_start, period_end),
    )
    types_used = [row[0] for row in cur.fetchall()]

    if types_used:
        chem_count = types_used.count("chemical")
        non_chem = len(types_used) - chem_count
        if chem_count == 0:
            ladder_score = 100.0
        elif non_chem >= chem_count:
            ladder_score = 70.0
        else:
            ladder_score = max(20.0, 70.0 - 20.0 * (chem_count - non_chem) / len(types_used))
    else:
        ladder_score = 80.0

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_record
        WHERE location_id = %s AND scout_date BETWEEN %s AND %s
          AND status != 'draft'
          AND severity IS NOT NULL
          AND (photo_url IS NOT NULL OR notes IS NOT NULL)
        """,
        (location_id, period_start, period_end),
    )
    with_evidence = cur.fetchone()[0]

    if total_scouts > 0:
        completeness_score = min(100.0, 100.0 * with_evidence / total_scouts)
    else:
        completeness_score = 50.0

    overall = round(
        0.25 * scouting_score
        + 0.25 * threshold_score
        + 0.25 * ladder_score
        + 0.25 * completeness_score,
        1,
    )

    cur.close()

    return {
        "location_id": location_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "scouting_score": round(scouting_score, 1),
        "threshold_adherence_score": round(threshold_score, 1),
        "ladder_compliance_score": round(ladder_score, 1),
        "record_completeness_score": round(completeness_score, 1),
        "overall_compliance_score": overall,
        "total_scouts": total_scouts,
        "total_interventions": total_interventions,
    }


# ============================================================
# Pest-Crop Interactions
# ============================================================

def add_pest_crop_interaction(
    conn,
    pest_name: str,
    crop_name: str,
    damage_type: str = None,
    severity_by_stage: dict = None,
    yield_loss_potential: float = None,
    peak_risk_stage: str = None,
    preferred_management: list = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Add or update a pest-crop interaction record."""
    cur = conn.cursor()
    interaction_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pest_crop_interaction
            (id, pest_name, crop_name, damage_type, severity_by_stage,
             yield_loss_potential, peak_risk_stage, preferred_management, notes, metadata)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)
        ON CONFLICT (pest_name, crop_name) DO UPDATE SET
            damage_type = EXCLUDED.damage_type,
            severity_by_stage = EXCLUDED.severity_by_stage,
            yield_loss_potential = EXCLUDED.yield_loss_potential,
            peak_risk_stage = EXCLUDED.peak_risk_stage,
            preferred_management = EXCLUDED.preferred_management
        RETURNING id
        """,
        (
            interaction_id, pest_name, crop_name, damage_type,
            json.dumps(severity_by_stage or {}),
            yield_loss_potential, peak_risk_stage,
            json.dumps(preferred_management or []),
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "interaction_id": interaction_id,
        "pest_name": pest_name,
        "crop_name": crop_name,
        "yield_loss_potential": yield_loss_potential,
    }


def get_pest_crop_interactions(
    conn,
    crop_name: str = None,
    pest_name: str = None,
) -> dict:
    """Look up pest-crop interactions."""
    cur = conn.cursor()

    conditions = ["status = 'active'"]
    params = []
    if crop_name:
        conditions.append("crop_name = %s")
        params.append(crop_name)
    if pest_name:
        conditions.append("pest_name = %s")
        params.append(pest_name)

    where = " AND ".join(conditions)

    cur.execute(
        f"""
        SELECT pest_name, crop_name, damage_type, severity_by_stage,
               yield_loss_potential, peak_risk_stage, preferred_management
        FROM pest_crop_interaction
        WHERE {where}
        ORDER BY yield_loss_potential DESC
        """,
        params,
    )
    cols = [d[0] for d in cur.description]
    interactions = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    return {
        "total": len(interactions),
        "interactions": interactions,
    }


def recommend_management_for_crop(
    conn,
    crop_name: str,
    growth_stage: str,
) -> dict:
    """Recommend ranked management options for a crop at a given growth stage."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT pest_name, damage_type, severity_by_stage,
               yield_loss_potential, preferred_management
        FROM pest_crop_interaction
        WHERE crop_name = %s AND status = 'active'
        ORDER BY yield_loss_potential DESC
        """,
        (crop_name,),
    )
    cols = [d[0] for d in cur.description]
    interactions = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    recommendations = []
    for ix in interactions:
        severity_map = ix["severity_by_stage"] or {}
        stage_severity = severity_map.get(growth_stage, "low")
        mgmt = ix["preferred_management"] or []

        if stage_severity in ("high", "critical"):
            priority = 1
        elif stage_severity == "moderate":
            priority = 2
        else:
            priority = 3

        recommendations.append({
            "pest_name": ix["pest_name"],
            "damage_type": ix["damage_type"],
            "stage_severity": stage_severity,
            "yield_loss_potential": float(ix["yield_loss_potential"]) if ix["yield_loss_potential"] else None,
            "preferred_management": mgmt,
            "priority": priority,
        })

    recommendations.sort(key=lambda x: (-x["priority"], -(x["yield_loss_potential"] or 0)))

    return {
        "crop_name": crop_name,
        "growth_stage": growth_stage,
        "pest_count": len(recommendations),
        "recommendations": recommendations,
    }


# ============================================================
# Trap Monitoring
# ============================================================

def add_trap(
    conn,
    location_id: str,
    trap_name: str,
    trap_type: str,
    target_pest: str = None,
    lure_type: str = None,
    plot_id: str = None,
    lat: float = None,
    lon: float = None,
    install_date: date = None,
    metadata: dict = None,
) -> dict:
    """Register a monitoring trap."""
    cur = conn.cursor()
    trap_id = str(uuid.uuid4())

    install_date = install_date or date.today()

    cur.execute(
        """
        INSERT INTO pest_trap
            (id, location_id, plot_id, trap_name, trap_type, target_pest,
             lure_type, install_date, lat, lon, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s::jsonb)
        RETURNING id
        """,
        (
            trap_id, location_id, plot_id, trap_name, trap_type, target_pest,
            lure_type, install_date, lat, lon, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "trap_id": trap_id,
        "location_id": location_id,
        "trap_name": trap_name,
        "trap_type": trap_type,
        "status": "active",
    }


def record_trap_catch(
    conn,
    trap_id: str,
    check_date: date = None,
    pest_count: int = 0,
    bycatch_count: int = 0,
    beneficial_count: int = 0,
    trap_condition: str = None,
    notes: str = None,
    scouting_record_id: str = None,
    metadata: dict = None,
) -> dict:
    """Log a trap catch observation."""
    cur = conn.cursor()
    catch_id = str(uuid.uuid4())

    check_date = check_date or date.today()

    cur.execute(
        """
        INSERT INTO pest_trap_catch
            (id, trap_id, check_date, pest_count, bycatch_count,
             beneficial_count, trap_condition, notes,
             scouting_record_id, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'recorded', %s::jsonb)
        RETURNING id
        """,
        (
            catch_id, trap_id, check_date, pest_count, bycatch_count,
            beneficial_count, trap_condition, notes,
            scouting_record_id, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "catch_id": catch_id,
        "trap_id": trap_id,
        "check_date": check_date.isoformat(),
        "pest_count": pest_count,
        "bycatch_count": bycatch_count,
        "beneficial_count": beneficial_count,
    }


def get_trap_trends(
    conn,
    trap_id: str,
    days: int = 30,
) -> dict:
    """Get time series of trap catches."""
    cur = conn.cursor()
    since = date.today() - timedelta(days=days)

    cur.execute(
        """
        SELECT pt.trap_name, pt.trap_type, pt.target_pest,
               ptc.check_date, ptc.pest_count, ptc.beneficial_count,
               ptc.bycatch_count, ptc.trap_condition
        FROM pest_trap_catch ptc
        JOIN pest_trap pt ON pt.id = ptc.trap_id
        WHERE ptc.trap_id = %s AND ptc.check_date >= %s
        ORDER BY ptc.check_date DESC
        """,
        (trap_id, since),
    )
    cols = [d[0] for d in cur.description]
    catches = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    if catches:
        total_pest = sum(c["pest_count"] for c in catches)
        total_beneficial = sum(c["beneficial_count"] for c in catches)
        avg_pest = round(total_pest / len(catches), 1) if catches else 0
    else:
        total_pest = 0
        total_beneficial = 0
        avg_pest = 0

    return {
        "trap_id": trap_id,
        "period_days": days,
        "total_catches": len(catches),
        "total_pest_count": total_pest,
        "total_beneficial_count": total_beneficial,
        "avg_pest_per_check": avg_pest,
        "catches": catches,
    }


def check_trap_threshold(conn, trap_id: str) -> dict:
    """Compare trap catch to economic threshold from pest_action_threshold."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT target_pest, location_id FROM pest_trap
        WHERE id = %s
        """,
        (trap_id,),
    )
    trap_row = cur.fetchone()
    if not trap_row:
        cur.close()
        return {"error": "Trap not found"}

    target_pest = trap_row[0]
    location_id = trap_row[1]

    cur.execute(
        """
        SELECT pest_count FROM pest_trap_catch
        WHERE trap_id = %s
        ORDER BY check_date DESC
        LIMIT 1
        """,
        (trap_id,),
    )
    latest_row = cur.fetchone()
    latest_count = latest_row[0] if latest_row else 0

    cur.execute(
        """
        SELECT economic_threshold, economic_injury_level, threshold_unit
        FROM pest_action_threshold
        WHERE location_id = %s AND pest_name = %s AND status = 'active'
        LIMIT 1
        """,
        (location_id, target_pest),
    )
    threshold_row = cur.fetchone()
    cur.close()

    if not threshold_row:
        return {
            "trap_id": trap_id,
            "target_pest": target_pest,
            "latest_count": latest_count,
            "threshold_found": False,
            "action": "monitor",
        }

    et = float(threshold_row[0]) if threshold_row[0] else None
    eil = float(threshold_row[1]) if threshold_row[1] else None

    if eil and latest_count >= eil:
        action = "immediate_intervention"
    elif et and latest_count >= et:
        action = "intervention_recommended"
    else:
        action = "continue_monitoring"

    return {
        "trap_id": trap_id,
        "target_pest": target_pest,
        "latest_count": latest_count,
        "economic_threshold": et,
        "economic_injury_level": eil,
        "action": action,
    }


# ============================================================
# Mode of Action Rotation
# ============================================================

def add_mode_of_action(
    conn,
    chemical_class: str,
    moa_code: str,
    mode_of_action: str,
    irac_group: str = None,
    frac_group: str = None,
    hrac_group: str = None,
    cross_resistance: list = None,
    rotation_compatibility: list = None,
    metadata: dict = None,
) -> dict:
    """Add or update a mode of action reference record."""
    cur = conn.cursor()
    moa_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pest_mode_of_action
            (id, chemical_class, moa_code, irac_group, frac_group, hrac_group,
             mode_of_action, cross_resistance, rotation_compatibility, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        ON CONFLICT (chemical_class) DO UPDATE SET
            moa_code = EXCLUDED.moa_code,
            irac_group = EXCLUDED.irac_group,
            frac_group = EXCLUDED.frac_group,
            hrac_group = EXCLUDED.hrac_group,
            mode_of_action = EXCLUDED.mode_of_action,
            cross_resistance = EXCLUDED.cross_resistance,
            rotation_compatibility = EXCLUDED.rotation_compatibility
        RETURNING id
        """,
        (
            moa_id, chemical_class, moa_code, irac_group, frac_group, hrac_group,
            mode_of_action, json.dumps(cross_resistance or []),
            json.dumps(rotation_compatibility or []),
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "moa_id": moa_id,
        "chemical_class": chemical_class,
        "moa_code": moa_code,
        "mode_of_action": mode_of_action,
    }


def check_rotation(
    conn,
    location_id: str,
    chemical_class: str,
    min_days: int = 14,
) -> dict:
    """Verify chemical class rotation compliance for resistance management."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT application_date, product_name
        FROM pesticide_application_log
        WHERE location_id = %s AND status = 'applied'
        ORDER BY application_date DESC
        LIMIT 5
        """,
        (location_id,),
    )
    recent = cur.fetchall()

    if not recent:
        cur.close()
        return {
            "location_id": location_id,
            "chemical_class": chemical_class,
            "rotation_ok": True,
            "message": "No previous applications found",
        }

    cur.execute(
        """
        SELECT moa_code, rotation_compatibility, cross_resistance
        FROM pest_mode_of_action
        WHERE chemical_class = %s
        """,
        (chemical_class,),
    )
    moa_row = cur.fetchone()

    cur.execute(
        """
        SELECT chemical_class FROM pesticide_application_log
        WHERE location_id = %s AND status = 'applied'
        ORDER BY application_date DESC
        LIMIT 1
        """,
        (location_id,),
    )
    prev_class_row = cur.fetchone()
    prev_class = prev_class_row[0] if prev_class_row else None

    if recent:
        last_date = recent[0][0]
        days_since = (date.today() - last_date).days if last_date else 999
    else:
        last_date = None
        days_since = 999

    rotation_ok = True
    recommendation = None

    if prev_class == chemical_class:
        rotation_ok = False
        recommendation = f"Same class ({chemical_class}) used consecutively. Rotate to a different mode of action."
    elif moa_row:
        cross_resistance = moa_row[2] or []
        if prev_class in cross_resistance:
            rotation_ok = False
            recommendation = f"Cross-resistance detected between {chemical_class} and {prev_class}. Avoid rotation between these classes."
    if days_since < min_days and not rotation_ok:
        recommendation = f"Only {days_since} days since last application (minimum {min_days})."

    cur.close()

    check_id = str(uuid.uuid4())
    cur2 = conn.cursor()
    cur2.execute(
        """
        INSERT INTO pest_rotation_check
            (id, location_id, check_date, chemical_class_used,
             previous_class, rotation_ok, days_since_last_class, recommendation)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (check_id, location_id, date.today(), chemical_class,
         prev_class, rotation_ok, days_since, recommendation),
    )
    conn.commit()
    cur2.close()

    return {
        "check_id": check_id,
        "location_id": location_id,
        "chemical_class": chemical_class,
        "previous_class": prev_class,
        "days_since_last_application": days_since,
        "rotation_ok": rotation_ok,
        "recommendation": recommendation,
    }


def get_rotation_history(
    conn,
    location_id: str,
    days: int = 90,
) -> dict:
    """Get chemical class usage timeline for rotation analysis."""
    cur = conn.cursor()
    since = date.today() - timedelta(days=days)

    cur.execute(
        """
        SELECT application_date, chemical_class, product_name, active_ingredient
        FROM pesticide_application_log
        WHERE location_id = %s AND application_date >= %s AND status = 'applied'
        ORDER BY application_date
        """,
        (location_id, since),
    )
    cols = [d[0] for d in cur.description]
    history = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    class_sequence = [h["chemical_class"] for h in history if h["chemical_class"]]
    unique_classes = list(dict.fromkeys(class_sequence))

    return {
        "location_id": location_id,
        "period_days": days,
        "total_applications": len(history),
        "unique_classes_used": unique_classes,
        "class_sequence": class_sequence,
        "history": history,
    }


# ============================================================
# Spray Window Prediction
# ============================================================

def get_optimal_spray_windows(
    conn,
    location_id: str,
    pest_name: str,
    days_ahead: int = 7,
) -> dict:
    """Cross-reference weather forecast spray windows with pest lifecycle and thresholds."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT lifecycle_stage, cumulative_degree_days
        FROM degree_day_record
        WHERE location_id = %s AND pest_name = %s
        ORDER BY record_date DESC LIMIT 1
        """,
        (location_id, pest_name),
    )
    dd_row = cur.fetchone()
    current_stage = dd_row[0] if dd_row else None
    current_dd = float(dd_row[1]) if dd_row and dd_row[1] else 0.0

    cur.execute(
        """
        SELECT economic_threshold, economic_injury_level
        FROM pest_action_threshold
        WHERE location_id = %s AND pest_name = %s AND status = 'active'
        LIMIT 1
        """,
        (location_id, pest_name),
    )
    threshold_row = cur.fetchone()
    et = float(threshold_row[0]) if threshold_row and threshold_row[0] else None
    eil = float(threshold_row[1]) if threshold_row and threshold_row[1] else None

    try:
        cur.execute(
            """
            SELECT forecast_date, spray_suitability
            FROM v_spray_window
            WHERE location_id = %s AND forecast_date <= CURRENT_DATE + INTERVAL '%s days'
            ORDER BY forecast_date
            """,
            (location_id, days_ahead),
        )
        windows = cur.fetchall()
    except Exception:
        windows = []

    cur.close()

    recommendations = []
    for w in windows:
        w_date, suitability = w
        if suitability in ("suitable", "marginal"):
            priority = 1 if suitability == "suitable" else 2
            recommendations.append({
                "date": w_date.isoformat() if hasattr(w_date, 'isoformat') else str(w_date),
                "spray_suitability": suitability,
                "priority": priority,
                "current_stage": current_stage,
            })

    recommendations.sort(key=lambda x: x["priority"])

    return {
        "location_id": location_id,
        "pest_name": pest_name,
        "current_lifecycle_stage": current_stage,
        "current_cumulative_dd": current_dd,
        "economic_threshold": et,
        "economic_injury_level": eil,
        "windows_ahead": len(recommendations),
        "recommendations": recommendations,
    }


# ============================================================
# Organic Certification IPM Score
# ============================================================

def compute_organic_pest_score(
    conn,
    location_id: str,
    period_start: date = None,
    period_end: date = None,
) -> dict:
    """Compute 0-100 IPM score for organic certification readiness."""
    cur = conn.cursor()

    period_end = period_end or date.today()
    period_start = period_start or (period_end - timedelta(days=365))

    biocontrol_score = 0.0
    chemical_reduction_score = 0.0
    ladder_score = 0.0
    scouting_score = 0.0

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_intervention
        WHERE location_id = %s AND intervention_date BETWEEN %s AND %s
          AND intervention_type = 'biological'
        """,
        (location_id, period_start, period_end),
    )
    bio_count = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_intervention
        WHERE location_id = %s AND intervention_date BETWEEN %s AND %s
          AND intervention_type = 'chemical'
        """,
        (location_id, period_start, period_end),
    )
    chem_count = cur.fetchone()[0]

    total = bio_count + chem_count
    if total > 0:
        biocontrol_score = min(100.0, 100.0 * bio_count / total)
    else:
        biocontrol_score = 60.0

    cur.execute(
        """
        SELECT COUNT(*) FROM pesticide_application_log
        WHERE location_id = %s AND application_date BETWEEN %s AND %s AND status = 'applied'
        """,
        (location_id, period_start, period_end),
    )
    chem_total = cur.fetchone()[0]

    half_period = period_start + (period_end - period_start) / 2
    cur.execute(
        """
        SELECT COUNT(*) FROM pesticide_application_log
        WHERE location_id = %s AND application_date BETWEEN %s AND %s AND status = 'applied'
        """,
        (location_id, half_period, period_end),
    )
    chem_second_half = cur.fetchone()[0]

    if chem_total > 0:
        if chem_second_half < chem_total / 2:
            chemical_reduction_score = 80.0
        else:
            chemical_reduction_score = 40.0
    else:
        chemical_reduction_score = 100.0

    cur.execute(
        """
        SELECT intervention_type FROM pest_intervention
        WHERE location_id = %s AND intervention_date BETWEEN %s AND %s
          AND status = 'applied'
        """,
        (location_id, period_start, period_end),
    )
    all_types = [r[0] for r in cur.fetchall()]

    if all_types:
        chemical = all_types.count("chemical")
        non_chemical = len(all_types) - chemical
        if chemical == 0:
            ladder_score = 100.0
        else:
            ratio = non_chemical / len(all_types)
            ladder_score = min(100.0, ratio * 100 + 20)
    else:
        ladder_score = 50.0

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_record
        WHERE location_id = %s AND scout_date BETWEEN %s AND %s AND status != 'draft'
        """,
        (location_id, period_start, period_end),
    )
    scouts = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_scouting_schedule
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    schedules = cur.fetchone()[0]

    if schedules > 0:
        expected = schedules * ((period_end - period_start).days // 7)
        scouting_score = min(100.0, 100.0 * scouts / max(1, expected))
    elif scouts > 0:
        scouting_score = 70.0
    else:
        scouting_score = 20.0

    overall = round(
        0.25 * biocontrol_score
        + 0.25 * chemical_reduction_score
        + 0.25 * ladder_score
        + 0.25 * scouting_score,
        1,
    )

    cur.close()

    return {
        "location_id": location_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "biocontrol_ratio_score": round(biocontrol_score, 1),
        "chemical_reduction_score": round(chemical_reduction_score, 1),
        "ipm_ladder_score": round(ladder_score, 1),
        "scouting_thoroughness_score": round(scouting_score, 1),
        "organic_pest_score": overall,
        "biocontrol_applications": bio_count,
        "chemical_applications": chem_count,
    }


# ============================================================
# Pollinator Auto-Link
# ============================================================

_TOXIC_CLASSES = {"neonicotinoid", "organophosphate", "carbamate", "pyrethroid"}
_TOXICITY_MAP = {
    "neonicotinoid": "high",
    "organophosphate": "high",
    "carbamate": "moderate",
    "pyrethroid": "moderate",
}


def auto_link_pollinator_impact(conn, application_id: str) -> dict:
    """Auto-create pollinator_pesticide_impact if chemical class is toxic to pollinators."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, location_id, chemical_class, product_name, application_date
        FROM pesticide_application_log
        WHERE id = %s
        """,
        (application_id,),
    )
    app_row = cur.fetchone()
    if not app_row:
        cur.close()
        return {"error": "Application not found"}

    chem_class = app_row[2]
    if not chem_class or chem_class.lower() not in _TOXIC_CLASSES:
        cur.close()
        return {
            "application_id": application_id,
            "linked": False,
            "message": f"Chemical class '{chem_class}' not flagged as pollinator-toxic",
        }

    toxicity = _TOXICITY_MAP.get(chem_class.lower(), "moderate")
    impact_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO pollinator_pesticide_impact
                (id, location_id, pesticide_class, toxicity_level,
                 application_date, source_application_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'recorded')
            """,
            (impact_id, app_row[1], chem_class, toxicity, app_row[4], application_id),
        )
        conn.commit()
        linked = True
    except Exception:
        linked = False
        impact_id = None

    cur.close()

    return {
        "application_id": application_id,
        "linked": linked,
        "impact_id": impact_id,
        "chemical_class": chem_class,
        "toxicity_level": toxicity if linked else None,
    }


# ============================================================
# IPM Audit Report
# ============================================================

def generate_ipm_audit(
    conn,
    location_id: str,
    period_start: date = None,
    period_end: date = None,
) -> dict:
    """Generate comprehensive IPM audit report for organic certification."""
    cur = conn.cursor()

    period_end = period_end or date.today()
    period_start = period_start or (period_end - timedelta(days=365))

    cur.execute(
        """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE severity IN ('high', 'severe'))
        FROM pest_scouting_record
        WHERE location_id = %s AND scout_date BETWEEN %s AND %s AND status != 'draft'
        """,
        (location_id, period_start, period_end),
    )
    scout_row = cur.fetchone()
    total_scouts = scout_row[0]
    high_severity_scouts = scout_row[1]

    cur.execute(
        """
        SELECT intervention_type, COUNT(*), AVG(effectiveness_pct)
        FROM pest_intervention
        WHERE location_id = %s AND intervention_date BETWEEN %s AND %s
          AND status = 'applied'
        GROUP BY intervention_type
        """,
        (location_id, period_start, period_end),
    )
    cols = [d[0] for d in cur.description]
    interventions = [dict(zip(cols, row)) for row in cur.fetchall()]
    total_interventions = sum(i["count"] for i in interventions)
    chem_interventions = next((i["count"] for i in interventions if i["intervention_type"] == "chemical"), 0)

    cur.execute(
        """
        SELECT chemical_class, product_name, SUM(total_volume) AS total_vol,
               COUNT(*) AS apps
        FROM pesticide_application_log
        WHERE location_id = %s AND application_date BETWEEN %s AND %s AND status = 'applied'
        GROUP BY chemical_class, product_name
        ORDER BY total_vol DESC
        """,
        (location_id, period_start, period_end),
    )
    cols = [d[0] for d in cur.description]
    chemicals = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_intervention pi
        WHERE pi.location_id = %s
          AND pi.intervention_date BETWEEN %s AND %s
          AND pi.intervention_type = 'chemical'
          AND EXISTS (
              SELECT 1 FROM pest_scouting_record psr
              WHERE psr.id = pi.scouting_record_id
                AND psr.severity IN ('none', 'low')
          )
        """,
        (location_id, period_start, period_end),
    )
    premature_chem = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM pest_resistance_record
        WHERE location_id = %s AND resistance_level IN ('high', 'confirmed')
          AND status = 'active'
        """,
        (location_id,),
    )
    resistance_alerts = cur.fetchone()[0]

    compliance = compute_ipm_compliance_score(conn, location_id, period_start, period_end)

    ladder_types = [i["intervention_type"] for i in interventions]
    ipm_ladder_ok = chem_interventions <= total_interventions * 0.5 if total_interventions > 0 else True

    rotation_check = check_rotation(conn, location_id, "unknown")
    rotation_ok = rotation_check.get("rotation_ok", True)

    cur.close()

    findings = []
    if premature_chem > 0:
        findings.append(f"{premature_chem} chemical intervention(s) triggered below economic threshold")
    if resistance_alerts > 0:
        findings.append(f"{resistance_alerts} active resistance alert(s)")
    if not ipm_ladder_ok:
        findings.append("Chemical interventions exceed 50% of total interventions")
    if not rotation_ok:
        findings.append(rotation_check.get("recommendation", "Rotation compliance issue"))
    if high_severity_scouts > total_scouts * 0.3 if total_scouts > 0 else False:
        findings.append("High proportion of high-severity scouting observations")

    return {
        "location_id": location_id,
        "audit_period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "scouting_summary": {
            "total_scouts": total_scouts,
            "high_severity_scouts": high_severity_scouts,
        },
        "intervention_summary": {
            "total": total_interventions,
            "by_type": interventions,
        },
        "chemical_summary": {
            "total_applications": chem_interventions,
            "by_product": chemicals,
        },
        "resistance_alerts": resistance_alerts,
        "ipm_compliance_score": compliance["overall_compliance_score"],
        "ipm_ladder_compliant": ipm_ladder_ok,
        "rotation_compliant": rotation_ok,
        "findings": findings,
        "overall_status": "pass" if not findings else "review_required",
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Integrated Pest Management")
    sub = parser.add_subparsers(dest="command")

    # record-scouting
    rs = sub.add_parser("record-scouting", help="Record scouting observation")
    rs.add_argument("--location-id", required=True)
    rs.add_argument("--pest", required=True)
    rs.add_argument("--type", dest="pest_type", choices=["insect", "weed", "disease", "nematode", "other"])
    rs.add_argument("--severity", choices=["none", "low", "moderate", "high", "severe"])
    rs.add_argument("--incidence", type=float, help="Incidence percentage")
    rs.add_argument("--damage", type=float, help="Damage percentage")
    rs.add_argument("--plot-id")
    rs.add_argument("--zone-id")
    rs.add_argument("--date", help="Scout date YYYY-MM-DD")
    rs.add_argument("--beneficials", help="Beneficial insects observed")
    rs.add_argument("--notes")
    rs.add_argument("--json", action="store_true")

    # set-threshold
    st = sub.add_parser("set-threshold", help="Set action threshold")
    st.add_argument("--location-id", required=True)
    st.add_argument("--pest", required=True)
    st.add_argument("--crop")
    st.add_argument("--eil", type=float, help="Economic injury level")
    st.add_argument("--et", type=float, help="Economic threshold")
    st.add_argument("--unit", help="Threshold unit (per_plant, per_leaf, etc.)")
    st.add_argument("--notes")
    st.add_argument("--json", action="store_true")

    # check-threshold
    ct = sub.add_parser("check-threshold", help="Check threshold")
    ct.add_argument("--location-id", required=True)
    ct.add_argument("--pest", required=True)
    ct.add_argument("--crop")
    ct.add_argument("--count", type=float, required=True, help="Current pest count")
    ct.add_argument("--json", action="store_true")

    # record-intervention
    ri = sub.add_parser("record-intervention", help="Record intervention")
    ri.add_argument("--location-id", required=True)
    ri.add_argument("--scouting-id")
    ri.add_argument("--type", dest="intervention_type", required=True,
                    choices=["biological", "cultural", "mechanical", "chemical", "semiochemical", "genetic"])
    ri.add_argument("--method")
    ri.add_argument("--pest", dest="target_pest")
    ri.add_argument("--rate", type=float)
    ri.add_argument("--unit")
    ri.add_argument("--area", type=float, help="Area in hectares")
    ri.add_argument("--cost", type=float)
    ri.add_argument("--date", help="Intervention date YYYY-MM-DD")
    ri.add_argument("--notes")
    ri.add_argument("--json", action="store_true")

    # record-pesticide
    rp = sub.add_parser("record-pesticide", help="Log pesticide application")
    rp.add_argument("--location-id", required=True)
    rp.add_argument("--product", required=True)
    rp.add_argument("--ingredient")
    rp.add_argument("--class", dest="chemical_class")
    rp.add_argument("--rate", type=float)
    rp.add_argument("--rate-unit")
    rp.add_argument("--area", type=float, help="Area in hectares")
    rp.add_argument("--volume", type=float)
    rp.add_argument("--volume-unit")
    rp.add_argument("--pest", dest="target_pest")
    rp.add_argument("--rei", type=int, help="Re-entry interval days")
    rp.add_argument("--phi", type=int, help="Pre-harvest interval days")
    rp.add_argument("--notes")
    rp.add_argument("--date", help="Application date YYYY-MM-DD")
    rp.add_argument("--json", action="store_true")

    # record-resistance
    rr = sub.add_parser("record-resistance", help="Record resistance observation")
    rr.add_argument("--location-id", required=True)
    rr.add_argument("--pest", required=True)
    rr.add_argument("--class", dest="chemical_class", required=True)
    rr.add_argument("--level", required=True, choices=["susceptible", "low", "moderate", "high", "confirmed"])
    rr.add_argument("--date", help="Observation date YYYY-MM-DD")
    rr.add_argument("--notes")
    rr.add_argument("--json", action="store_true")

    # record-degree-day
    rdd = sub.add_parser("record-degree-day", help="Record temperature and compute degree days")
    rdd.add_argument("--location-id", required=True)
    rdd.add_argument("--pest", required=True)
    rdd.add_argument("--base", type=float, default=10.0, help="Base temperature")
    rdd.add_argument("--max", type=float, dest="max_temp", help="Max temperature")
    rdd.add_argument("--min", type=float, dest="min_temp", help="Min temperature")
    rdd.add_argument("--upper", type=float, help="Upper developmental threshold")
    rdd.add_argument("--date", help="Record date YYYY-MM-DD")
    rdd.add_argument("--source", default="sensor")
    rdd.add_argument("--json", action="store_true")

    # summary
    sm = sub.add_parser("summary", help="Pest scouting summary")
    sm.add_argument("--location-id", required=True)
    sm.add_argument("--json", action="store_true")

    # pesticide-usage
    pu = sub.add_parser("pesticide-usage", help="Chemical use totals")
    pu.add_argument("--location-id", required=True)
    pu.add_argument("--days", type=int, default=30)
    pu.add_argument("--json", action="store_true")

    # degree-day-tracking
    ddt = sub.add_parser("degree-day-tracking", help="Cumulative degree days and lifecycle stage")
    ddt.add_argument("--location-id", required=True)
    ddt.add_argument("--pest", required=True)
    ddt.add_argument("--json", action="store_true")

    # recommend
    rc = sub.add_parser("recommend", help="Recommend IPM intervention")
    rc.add_argument("--scouting-id", required=True)
    rc.add_argument("--json", action="store_true")

    # dashboard
    db = sub.add_parser("dashboard", help="Aggregated pest management dashboard")
    db.add_argument("--location-id", required=True)
    db.add_argument("--json", action="store_true")

    # --- Phase 13A: Biology Reference ---
    arp = sub.add_parser("add-reference", help="Add pest biology reference")
    arp.add_argument("--pest", required=True)
    arp.add_argument("--scientific-name")
    arp.add_argument("--common-name")
    arp.add_argument("--category", dest="pest_category",
                     choices=["insect", "mite", "nematode", "fungal", "bacterial", "viral", "weed", "rodent", "other"])
    arp.add_argument("--base-temp", type=float)
    arp.add_argument("--upper-temp", type=float)
    arp.add_argument("--total-dd", type=float, dest="total_degree_days")
    arp.add_argument("--hosts", nargs="*", help="Host crops")
    arp.add_argument("--enemies", nargs="*", help="Natural enemies")
    arp.add_argument("--importance", choices=["critical", "high", "moderate", "low"])
    arp.add_argument("--json", action="store_true")

    grp = sub.add_parser("get-reference", help="Look up pest biology reference")
    grp.add_argument("--pest", required=True)
    grp.add_argument("--json", action="store_true")

    lr = sub.add_parser("list-references", help="List pest biology references")
    lr.add_argument("--category", dest="pest_category")
    lr.add_argument("--host", dest="host_crop")
    lr.add_argument("--json", action="store_true")

    # --- Phase 13A: Scouting Schedules ---
    cs = sub.add_parser("create-schedule", help="Create scouting schedule")
    cs.add_argument("--location-id", required=True)
    cs.add_argument("--pest", required=True)
    cs.add_argument("--crop")
    cs.add_argument("--frequency", type=int, default=7, dest="frequency_days")
    cs.add_argument("--method")
    cs.add_argument("--sample-size", type=int)
    cs.add_argument("--assigned-to")
    cs.add_argument("--start-date")
    cs.add_argument("--end-date")
    cs.add_argument("--json", action="store_true")

    ds = sub.add_parser("due-scouting", help="Get due/overdue scouting schedules")
    ds.add_argument("--location-id", required=True)
    ds.add_argument("--json", action="store_true")

    rc2 = sub.add_parser("record-compliance", help="Record scouting completion")
    rc2.add_argument("--schedule-id", required=True)
    rc2.add_argument("--scouting-id", required=True)
    rc2.add_argument("--date", dest="scout_date")
    rc2.add_argument("--notes")
    rc2.add_argument("--json", action="store_true")

    cr = sub.add_parser("compliance-report", help="Scouting compliance statistics")
    cr.add_argument("--location-id", required=True)
    cr.add_argument("--days", type=int, default=30)
    cr.add_argument("--json", action="store_true")

    # --- Phase 13A: Re-scout & Evaluation ---
    sr = sub.add_parser("schedule-re-scout", help="Schedule follow-up re-scout")
    sr.add_argument("--intervention-id", required=True)
    sr.add_argument("--date", required=True, dest="re_scout_date")
    sr.add_argument("--json", action="store_true")

    ei = sub.add_parser("evaluate-intervention", help="Evaluate intervention effectiveness")
    ei.add_argument("--intervention-id", required=True)
    ei.add_argument("--scouting-id", required=True, dest="re_scout_record_id")
    ei.add_argument("--effectiveness", type=float, required=True)
    ei.add_argument("--json", action="store_true")

    # --- Phase 13A: Compliance Score ---
    ics = sub.add_parser("compliance-score", help="Compute IPM compliance score")
    ics.add_argument("--location-id", required=True)
    ics.add_argument("--period-start")
    ics.add_argument("--period-end")
    ics.add_argument("--json", action="store_true")

    # --- Phase 13B: Pest-Crop Interactions ---
    aci = sub.add_parser("add-interaction", help="Add pest-crop interaction")
    aci.add_argument("--pest", required=True)
    aci.add_argument("--crop", required=True)
    aci.add_argument("--damage-type")
    aci.add_argument("--loss-potential", type=float, dest="yield_loss_potential")
    aci.add_argument("--peak-stage")
    aci.add_argument("--management", nargs="*")
    aci.add_argument("--json", action="store_true")

    gci = sub.add_parser("get-interactions", help="Get pest-crop interactions")
    gci.add_argument("--crop")
    gci.add_argument("--pest")
    gci.add_argument("--json", action="store_true")

    rmc = sub.add_parser("recommend-for-crop", help="Recommend management for crop/stage")
    rmc.add_argument("--crop", required=True)
    rmc.add_argument("--stage", required=True)
    rmc.add_argument("--json", action="store_true")

    # --- Phase 13B: Trap Monitoring ---
    at = sub.add_parser("add-trap", help="Register monitoring trap")
    at.add_argument("--location-id", required=True)
    at.add_argument("--name", required=True, dest="trap_name")
    at.add_argument("--type", required=True, dest="trap_type",
                    choices=["pheromone", "sticky", "light", "pitfall", "sweep_net"])
    at.add_argument("--pest", dest="target_pest")
    at.add_argument("--lure")
    at.add_argument("--plot-id")
    at.add_argument("--lat", type=float)
    at.add_argument("--lon", type=float)
    at.add_argument("--date")
    at.add_argument("--json", action="store_true")

    tc = sub.add_parser("record-catch", help="Log trap catch")
    tc.add_argument("--trap-id", required=True)
    tc.add_argument("--date", dest="check_date")
    tc.add_argument("--pest-count", type=int, default=0)
    tc.add_argument("--bycatch", type=int, default=0)
    tc.add_argument("--beneficial", type=int, default=0)
    tc.add_argument("--condition", dest="trap_condition")
    tc.add_argument("--notes")
    tc.add_argument("--json", action="store_true")

    tt = sub.add_parser("trap-trends", help="Trap catch time series")
    tt.add_argument("--trap-id", required=True)
    tt.add_argument("--days", type=int, default=30)
    tt.add_argument("--json", action="store_true")

    ctt = sub.add_parser("check-trap-threshold", help="Compare trap catch to ET")
    ctt.add_argument("--trap-id", required=True)
    ctt.add_argument("--json", action="store_true")

    # --- Phase 13B: MoA Rotation ---
    amo = sub.add_parser("add-moa", help="Add mode of action reference")
    amo.add_argument("--class", dest="chemical_class", required=True)
    amo.add_argument("--code", dest="moa_code", required=True)
    amo.add_argument("--action", required=True, dest="mode_of_action")
    amo.add_argument("--irac")
    amo.add_argument("--frac")
    amo.add_argument("--hrac")
    amo.add_argument("--cross-resistance", nargs="*")
    amo.add_argument("--compatible", nargs="*")
    amo.add_argument("--json", action="store_true")

    cro = sub.add_parser("check-rotation", help="Verify MoA rotation compliance")
    cro.add_argument("--location-id", required=True)
    cro.add_argument("--class", dest="chemical_class", required=True)
    cro.add_argument("--min-days", type=int, default=14)
    cro.add_argument("--json", action="store_true")

    rh = sub.add_parser("rotation-history", help="Chemical class usage timeline")
    rh.add_argument("--location-id", required=True)
    rh.add_argument("--days", type=int, default=90)
    rh.add_argument("--json", action="store_true")

    # --- Phase 13B: Spray Window ---
    sw = sub.add_parser("spray-windows", help="Optimal spray windows from forecast")
    sw.add_argument("--location-id", required=True)
    sw.add_argument("--pest", required=True)
    sw.add_argument("--days-ahead", type=int, default=7)
    sw.add_argument("--json", action="store_true")

    # --- Phase 13C: Organic Pest Score ---
    ops = sub.add_parser("organic-pest-score", help="IPM score for organic certification")
    ops.add_argument("--location-id", required=True)
    ops.add_argument("--period-start")
    ops.add_argument("--period-end")
    ops.add_argument("--json", action="store_true")

    # --- Phase 13C: IPM Audit ---
    ia = sub.add_parser("generate-audit", help="Generate IPM audit report")
    ia.add_argument("--location-id", required=True)
    ia.add_argument("--period-start")
    ia.add_argument("--period-end")
    ia.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command is None:
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "record-scouting":
            sd = date.fromisoformat(args.date) if args.date else None
            result = record_scouting(
                db, args.location_id, args.pest,
                pest_type=args.pest_type, severity=args.severity,
                incidence_pct=args.incidence, damage_pct=args.damage,
                plot_id=args.plot_id, zone_id=args.zone_id,
                scout_date=sd, beneficial_observed=args.beneficials,
                notes=args.notes,
            )

        elif args.command == "set-threshold":
            result = set_action_threshold(
                db, args.location_id, args.pest, crop_name=args.crop,
                economic_injury_level=args.eil, economic_threshold=args.et,
                threshold_unit=args.unit, notes=args.notes,
            )

        elif args.command == "check-threshold":
            result = check_threshold(
                db, args.location_id, args.pest, crop_name=args.crop,
                current_count=args.count,
            )

        elif args.command == "record-intervention":
            idate = date.fromisoformat(args.date) if args.date else None
            result = record_intervention(
                db, args.location_id, args.intervention_type,
                scouting_record_id=args.scouting_id,
                method_name=args.method, target_pest=args.target_pest,
                application_rate=args.rate, application_unit=args.unit,
                area_ha=args.area, cost=args.cost,
                notes=args.notes, intervention_date=idate,
            )

        elif args.command == "record-pesticide":
            adate = date.fromisoformat(args.date) if args.date else None
            result = record_pesticide_application(
                db, args.location_id, args.product,
                active_ingredient=args.ingredient,
                chemical_class=args.chemical_class,
                application_rate=args.rate, rate_unit=args.rate_unit,
                area_ha=args.area, total_volume=args.volume,
                volume_unit=args.volume_unit, target_pest=args.target_pest,
                rei_days=args.rei, phi_days=args.phi,
                notes=args.notes, application_date=adate,
            )

        elif args.command == "record-resistance":
            odate = date.fromisoformat(args.date) if args.date else None
            result = record_resistance(
                db, args.location_id, args.pest, args.chemical_class,
                args.level, observation_date=odate, notes=args.notes,
            )

        elif args.command == "record-degree-day":
            rdate = date.fromisoformat(args.date) if args.date else None
            result = record_degree_day(
                db, args.location_id, args.pest,
                record_date=rdate, base_temp=args.base,
                max_temp=args.max_temp, min_temp=args.min_temp,
                upper_temp=args.upper, source=args.source,
            )

        elif args.command == "summary":
            result = get_pest_summary(db, args.location_id)

        elif args.command == "pesticide-usage":
            result = get_pesticide_usage(db, args.location_id, days=args.days)

        elif args.command == "degree-day-tracking":
            result = get_degree_day_tracking(db, args.location_id, args.pest)

        elif args.command == "recommend":
            result = recommend_intervention(db, args.scouting_id)

        elif args.command == "dashboard":
            result = get_pest_dashboard(db, args.location_id)

        elif args.command == "add-reference":
            result = add_pest_reference(
                db, args.pest, scientific_name=args.scientific_name,
                common_name=args.common_name, pest_category=args.pest_category,
                base_temp=args.base_temp, upper_temp=args.upper_temp,
                total_degree_days=args.total_degree_days,
                host_crops=args.hosts, importance=args.importance,
            )

        elif args.command == "get-reference":
            result = get_pest_reference(db, args.pest)

        elif args.command == "list-references":
            result = list_pest_references(
                db, pest_category=getattr(args, 'pest_category', None),
                host_crop=getattr(args, 'host_crop', None),
            )

        elif args.command == "create-schedule":
            sd = date.fromisoformat(args.start_date) if args.start_date else None
            ed = date.fromisoformat(args.end_date) if args.end_date else None
            result = create_scouting_schedule(
                db, args.location_id, args.pest,
                frequency_days=args.frequency_days, crop_name=args.crop,
                method=args.method, sample_size=args.sample_size,
                assigned_to=args.assigned_to, start_date=sd, end_date=ed,
            )

        elif args.command == "due-scouting":
            result = get_due_scouting(db, args.location_id)

        elif args.command == "record-compliance":
            sd = date.fromisoformat(args.scout_date) if args.scout_date else None
            result = record_scouting_completion(
                db, args.schedule_id, args.scouting_id,
                scout_date=sd, notes=args.notes,
            )

        elif args.command == "compliance-report":
            result = get_scouting_compliance(db, args.location_id, days=args.days)

        elif args.command == "schedule-re-scout":
            rsd = date.fromisoformat(args.re_scout_date)
            result = schedule_re_scout(db, args.intervention_id, rsd)

        elif args.command == "evaluate-intervention":
            result = evaluate_intervention(
                db, args.intervention_id, args.re_scout_record_id,
                args.effectiveness,
            )

        elif args.command == "compliance-score":
            ps = date.fromisoformat(args.period_start) if args.period_start else None
            pe = date.fromisoformat(args.period_end) if args.period_end else None
            result = compute_ipm_compliance_score(db, args.location_id, ps, pe)

        elif args.command == "add-interaction":
            result = add_pest_crop_interaction(
                db, args.pest, args.crop,
                damage_type=args.damage_type,
                yield_loss_potential=args.yield_loss_potential,
                peak_risk_stage=args.peak_stage,
                preferred_management=args.management,
            )

        elif args.command == "get-interactions":
            result = get_pest_crop_interactions(
                db, crop_name=args.crop, pest_name=args.pest,
            )

        elif args.command == "recommend-for-crop":
            result = recommend_management_for_crop(db, args.crop, args.stage)

        elif args.command == "add-trap":
            idate = date.fromisoformat(args.date) if args.date else None
            result = add_trap(
                db, args.location_id, args.trap_name, args.trap_type,
                target_pest=args.target_pest, lure_type=args.lure,
                plot_id=args.plot_id, lat=args.lat, lon=args.lon,
                install_date=idate,
            )

        elif args.command == "record-catch":
            cd = date.fromisoformat(args.check_date) if args.check_date else None
            result = record_trap_catch(
                db, args.trap_id, check_date=cd,
                pest_count=args.pest_count, bycatch_count=args.bycatch,
                beneficial_count=args.beneficial,
                trap_condition=args.condition, notes=args.notes,
            )

        elif args.command == "trap-trends":
            result = get_trap_trends(db, args.trap_id, days=args.days)

        elif args.command == "check-trap-threshold":
            result = check_trap_threshold(db, args.trap_id)

        elif args.command == "add-moa":
            result = add_mode_of_action(
                db, args.chemical_class, args.moa_code, args.mode_of_action,
                irac_group=args.irac, frac_group=args.frac, hrac_group=args.hrac,
                cross_resistance=args.cross_resistance,
                rotation_compatibility=args.compatible,
            )

        elif args.command == "check-rotation":
            result = check_rotation(
                db, args.location_id, args.chemical_class,
                min_days=args.min_days,
            )

        elif args.command == "rotation-history":
            result = get_rotation_history(db, args.location_id, days=args.days)

        elif args.command == "spray-windows":
            result = get_optimal_spray_windows(
                db, args.location_id, args.pest,
                days_ahead=args.days_ahead,
            )

        elif args.command == "organic-pest-score":
            ps = date.fromisoformat(args.period_start) if args.period_start else None
            pe = date.fromisoformat(args.period_end) if args.period_end else None
            result = compute_organic_pest_score(db, args.location_id, ps, pe)

        elif args.command == "generate-audit":
            ps = date.fromisoformat(args.period_start) if args.period_start else None
            pe = date.fromisoformat(args.period_end) if args.period_end else None
            result = generate_ipm_audit(db, args.location_id, ps, pe)

        else:
            parser.print_help()
            return

        print(json.dumps(result, indent=2, default=str))

    finally:
        db.close()


if __name__ == "__main__":
    main()
