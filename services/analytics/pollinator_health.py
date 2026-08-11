#!/usr/bin/env python3
"""
Pollinator Health

Tracks pollinator observations, habitats, pesticide impacts,
managed hive health, and produces a dashboard summary.

Usage:
    python -m services.analytics.pollinator_health record-observation --location-id UUID --type honeybee --count 50
    python -m services.analytics.pollinator_health create-habitat --location-id UUID --name "Wildflower Strip" --type wildflower --area 200
    python -m services.analytics.pollinator_health record-pesticide --location-id UUID --product "Chlorpyrifos" --toxicity high
    python -m services.analytics.pollinator_health add-hive --location-id UUID --hive-id H-001 --colony-strength 8
    python -m services.analytics.pollinator_health record-inspection --hive-id H-001 --colony-strength 9
    python -m services.analytics.pollinator_health summary --location-id UUID
    python -m services.analytics.pollinator_health habitat-inventory --location-id UUID
    python -m services.analytics.pollinator_health pesticide-risk --location-id UUID
    python -m services.analytics.pollinator_health hive-status --location-id UUID
    python -m services.analytics.pollinator_health dashboard --location-id UUID
"""

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.pollinator_health")

TOXICITY_RISK = {
    "low": {"risk": "low", "pollinator_harm": "minimal"},
    "moderate": {"risk": "moderate", "pollinator_harm": "sublethal effects possible"},
    "high": {"risk": "high", "pollinator_harm": "lethal to foragers"},
    "very_high": {"risk": "very_high", "pollinator_harm": "lethal to colony"},
}


# ============================================================
# Record Observation
# ============================================================

def record_observation(
    conn,
    location_id: str,
    pollinator_type: str,
    count: int,
    observation_method: str = "visual",
    duration_minutes: int = 15,
    habitat_area_id: str = None,
    weather_conditions: str = None,
    temperature_c: float = None,
    notes: str = None,
    source_system: str = None,
    source_id: str = None,
    metadata: dict = None,
) -> dict:
    """Record a pollinator observation."""
    cur = conn.cursor()
    obs_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pollinator_observation
            (id, location_id, pollinator_type, count, observation_method,
             duration_minutes, habitat_area_id, weather_conditions,
             temperature_c, notes, source_system, source_id,
             metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
        RETURNING id
        """,
        (
            obs_id, location_id, pollinator_type, count, observation_method,
            duration_minutes, habitat_area_id, weather_conditions,
            temperature_c, notes, source_system, source_id,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info(
        "Recorded pollinator observation: type=%s count=%d location=%s",
        pollinator_type, count, location_id,
    )

    return {
        "observation_id": obs_id,
        "location_id": location_id,
        "pollinator_type": pollinator_type,
        "count": count,
        "observation_method": observation_method,
        "duration_minutes": duration_minutes,
    }


# ============================================================
# Create Habitat
# ============================================================

def create_habitat(
    conn,
    location_id: str,
    habitat_name: str,
    habitat_type: str,
    area_m2: float,
    plant_species: list = None,
    bloom_start_month: int = None,
    bloom_end_month: int = None,
    water_source: bool = False,
    nesting_sites: str = None,
    management_notes: str = None,
    metadata: dict = None,
) -> dict:
    """Create a pollinator habitat record."""
    cur = conn.cursor()
    habitat_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pollinator_habitat
            (id, location_id, habitat_name, habitat_type, area_m2,
             plant_species, bloom_start_month, bloom_end_month,
             water_source, nesting_sites, management_notes,
             metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
        RETURNING id
        """,
        (
            habitat_id, location_id, habitat_name, habitat_type, area_m2,
            json.dumps(plant_species or []),
            bloom_start_month, bloom_end_month,
            water_source, nesting_sites, management_notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info(
        "Created pollinator habitat: name=%s type=%s area=%.1f m2 location=%s",
        habitat_name, habitat_type, area_m2, location_id,
    )

    return {
        "habitat_id": habitat_id,
        "location_id": location_id,
        "habitat_name": habitat_name,
        "habitat_type": habitat_type,
        "area_m2": area_m2,
        "plant_species": plant_species or [],
        "water_source": water_source,
    }


# ============================================================
# Record Pesticide Impact
# ============================================================

def record_pesticide_impact(
    conn,
    location_id: str,
    application_date: date,
    product_name: str,
    active_ingredient: str,
    toxicity_class: str,
    application_rate: float = None,
    rate_unit: str = None,
    area_treated_m2: float = None,
    bloom_stage_at_application: str = None,
    pollinator_distance_m: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a pesticide application with pollinator risk assessment."""
    cur = conn.cursor()
    record_id = str(uuid.uuid4())

    toxicity_class = toxicity_class.lower()
    risk_info = TOXICITY_RISK.get(toxicity_class, {"risk": "unknown", "pollinator_harm": "unknown"})

    cur.execute(
        """
        INSERT INTO pollinator_pesticide_impact
            (id, location_id, application_date, product_name,
             active_ingredient, toxicity_class, application_rate,
             rate_unit, area_treated_m2, bloom_stage_at_application,
             pollinator_distance_m, pollinator_risk, pollinator_harm_description,
             notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
        RETURNING id
        """,
        (
            record_id, location_id, application_date, product_name,
            active_ingredient, toxicity_class, application_rate,
            rate_unit, area_treated_m2, bloom_stage_at_application,
            pollinator_distance_m, risk_info["risk"], risk_info["pollinator_harm"],
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info(
        "Recorded pesticide impact: product=%s toxicity=%s risk=%s location=%s",
        product_name, toxicity_class, risk_info["risk"], location_id,
    )

    return {
        "record_id": record_id,
        "location_id": location_id,
        "product_name": product_name,
        "active_ingredient": active_ingredient,
        "toxicity_class": toxicity_class,
        "pollinator_risk": risk_info["risk"],
        "pollinator_harm": risk_info["pollinator_harm"],
        "application_date": application_date.isoformat(),
    }


# ============================================================
# Add Hive
# ============================================================

def add_hive(
    conn,
    location_id: str,
    hive_id: str,
    colony_strength: int = 5,
    queen_status: str = "present",
    hive_type: str = "langstroth",
    frame_count: int = 10,
    queen_year: int = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Add a managed pollinator hive."""
    cur = conn.cursor()
    record_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pollinator_hive
            (id, location_id, hive_id, hive_type, colony_strength,
             queen_status, frame_count, queen_year, notes,
             metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
        RETURNING id
        """,
        (
            record_id, location_id, hive_id, hive_type, colony_strength,
            queen_status, frame_count, queen_year, notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info(
        "Added hive: hive_id=%s strength=%d queen=%s location=%s",
        hive_id, colony_strength, queen_status, location_id,
    )

    return {
        "record_id": record_id,
        "location_id": location_id,
        "hive_id": hive_id,
        "hive_type": hive_type,
        "colony_strength": colony_strength,
        "queen_status": queen_status,
        "frame_count": frame_count,
    }


# ============================================================
# Record Hive Inspection
# ============================================================

def record_hive_inspection(
    conn,
    hive_id: str,
    colony_strength: int = None,
    queen_status: str = None,
    queen_seen: bool = None,
    varroa_count: int = None,
    brood_pattern: str = None,
    honey_stores: str = None,
    disease_signs: str = None,
    temperament: str = None,
    population_estimate: int = None,
    swarm_cells: bool = False,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a hive inspection."""
    cur = conn.cursor()
    inspection_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pollinator_hive_inspection
            (id, hive_id, inspection_date, colony_strength, queen_status,
             queen_seen, varroa_count, brood_pattern, honey_stores,
             disease_signs, temperament, population_estimate,
             swarm_cells, notes, metadata, status)
        VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
        RETURNING id
        """,
        (
            inspection_id, hive_id, colony_strength, queen_status,
            queen_seen, varroa_count, brood_pattern, honey_stores,
            disease_signs, temperament, population_estimate,
            swarm_cells, notes, json.dumps(metadata or {}),
        ),
    )

    if colony_strength is not None:
        cur.execute(
            "UPDATE pollinator_hive SET colony_strength = %s WHERE hive_id = %s",
            (colony_strength, hive_id),
        )

    conn.commit()
    cur.close()

    logger.info(
        "Recorded hive inspection: hive_id=%s strength=%s varroa=%s",
        hive_id, colony_strength, varroa_count,
    )

    return {
        "inspection_id": inspection_id,
        "hive_id": hive_id,
        "colony_strength": colony_strength,
        "queen_status": queen_status,
        "queen_seen": queen_seen,
        "varroa_count": varroa_count,
        "brood_pattern": brood_pattern,
        "swarm_cells": swarm_cells,
    }


# ============================================================
# Get Pollinator Summary
# ============================================================

def get_pollinator_summary(conn, location_id: str, days: int = 30) -> dict:
    """Get pollinator counts by type and trend."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT pollinator_type,
               COUNT(*) AS observations,
               AVG(count) AS avg_count,
               MAX(count) AS max_count,
               MIN(observation_date) AS first_obs,
               MAX(observation_date) AS last_obs
        FROM pollinator_observation
        WHERE location_id = %s
          AND observation_date >= CURRENT_DATE - INTERVAL '%s days'
          AND status IN ('verified', 'published', 'draft')
        GROUP BY pollinator_type
        ORDER BY avg_count DESC
        """,
        (location_id, days),
    )
    cols = [d[0] for d in cur.description]
    by_type = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Trend: compare last half vs first half
    for ptype in by_type:
        cur.execute(
            """
            SELECT AVG(count) AS avg_count
            FROM pollinator_observation
            WHERE location_id = %s
              AND pollinator_type = %s
              AND observation_date >= CURRENT_DATE - INTERVAL '%s days'
              AND observation_date < CURRENT_DATE - INTERVAL '%s days'
              AND status IN ('verified', 'published', 'draft')
            """,
            (location_id, ptype["pollinator_type"], days, days // 2),
        )
        first_half = cur.fetchone()
        first_avg = float(first_half[0]) if first_half and first_half[0] else 0

        cur.execute(
            """
            SELECT AVG(count) AS avg_count
            FROM pollinator_observation
            WHERE location_id = %s
              AND pollinator_type = %s
              AND observation_date >= CURRENT_DATE - INTERVAL '%s days'
              AND status IN ('verified', 'published', 'draft')
            """,
            (location_id, ptype["pollinator_type"], days // 2),
        )
        second_half = cur.fetchone()
        second_avg = float(second_half[0]) if second_half and second_half[0] else 0

        if first_avg > 0:
            change_pct = (second_avg - first_avg) / first_avg * 100
            ptype["trend"] = "increasing" if change_pct > 10 else "decreasing" if change_pct < -10 else "stable"
            ptype["change_pct"] = round(change_pct, 1)
        else:
            ptype["trend"] = "insufficient_data"
            ptype["change_pct"] = 0

    cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "pollinator_types": by_type,
    }


# ============================================================
# Get Habitat Inventory
# ============================================================

def get_habitat_inventory(conn, location_id: str) -> dict:
    """Get pollinator habitat areas and their features."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, habitat_name, habitat_type, area_m2,
               plant_species, bloom_start_month, bloom_end_month,
               water_source, nesting_sites, management_notes
        FROM pollinator_habitat
        WHERE location_id = %s AND status = 'active'
        ORDER BY area_m2 DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    habitats = []
    for row in cur.fetchall():
        h = dict(zip(cols, row))
        h["plant_species"] = json.loads(h["plant_species"]) if isinstance(h["plant_species"], str) else (h["plant_species"] or [])
        habitats.append(h)

    total_area = sum(h["area_m2"] for h in habitats)

    cur.close()

    return {
        "location_id": location_id,
        "total_habitat_m2": round(total_area, 1),
        "habitat_count": len(habitats),
        "habitats": habitats,
    }


# ============================================================
# Get Pesticide Risk
# ============================================================

def get_pesticide_risk(conn, location_id: str, days: int = 90) -> dict:
    """Get recent pesticide applications with pollinator risk rating."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, application_date, product_name, active_ingredient,
               toxicity_class, application_rate, rate_unit,
               area_treated_m2, bloom_stage_at_application,
               pollinator_distance_m, pollinator_risk, pollinator_harm_description
        FROM pollinator_pesticide_impact
        WHERE location_id = %s
          AND application_date >= CURRENT_DATE - INTERVAL '%s days'
          AND status = 'recorded'
        ORDER BY application_date DESC
        """,
        (location_id, days),
    )
    cols = [d[0] for d in cur.description]
    applications = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT toxicity_class, COUNT(*) AS cnt
        FROM pollinator_pesticide_impact
        WHERE location_id = %s
          AND application_date >= CURRENT_DATE - INTERVAL '%s days'
          AND status = 'recorded'
        GROUP BY toxicity_class
        """,
        (location_id, days),
    )
    risk_counts = {row[0]: row[1] for row in cur.fetchall()}

    high_risk_count = sum(
        v for k, v in risk_counts.items() if k in ("high", "very_high")
    )
    overall_risk = (
        "critical" if high_risk_count >= 3
        else "elevated" if high_risk_count >= 1
        else "low"
    )

    cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "total_applications": len(applications),
        "overall_risk": overall_risk,
        "risk_distribution": risk_counts,
        "applications": applications,
    }


# ============================================================
# Get Hive Status
# ============================================================

def get_hive_status(conn, location_id: str) -> dict:
    """Get hive health and productivity."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT h.id, h.hive_id, h.hive_type, h.colony_strength,
               h.queen_status, h.frame_count, h.queen_year, h.status
        FROM pollinator_hive h
        WHERE h.location_id = %s
        ORDER BY h.hive_id
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    hives = [dict(zip(cols, row)) for row in cur.fetchall()]

    for hive in hives:
        cur.execute(
            """
            SELECT inspection_date, colony_strength, queen_status,
                   queen_seen, varroa_count, brood_pattern,
                   honey_stores, disease_signs, swarm_cells
            FROM pollinator_hive_inspection
            WHERE hive_id = %s
            ORDER BY inspection_date DESC
            LIMIT 1
            """,
            (hive["hive_id"],),
        )
        insp_cols = [d[0] for d in cur.description]
        insp_row = cur.fetchone()
        hive["last_inspection"] = dict(zip(insp_cols, insp_row)) if insp_row else None

        cur.execute(
            """
            SELECT AVG(count) AS avg_foragers
            FROM pollinator_observation
            WHERE location_id = %s
              AND pollinator_type = 'honeybee'
              AND observation_date >= CURRENT_DATE - INTERVAL '30 days'
              AND status IN ('verified', 'published', 'draft')
            """,
            (location_id,),
        )
        avg_row = cur.fetchone()
        hive["avg_daily_foragers"] = round(float(avg_row[0]), 1) if avg_row and avg_row[0] else None

    active = sum(1 for h in hives if h["status"] == "active")
    avg_strength = (
        sum(h["colony_strength"] for h in hives if h["colony_strength"]) / active
        if active else 0
    )

    cur.close()

    return {
        "location_id": location_id,
        "total_hives": len(hives),
        "active_hives": active,
        "avg_colony_strength": round(avg_strength, 1),
        "hives": hives,
    }


# ============================================================
# Pollinator Dashboard
# ============================================================

def get_pollinator_dashboard(conn, location_id: str) -> dict:
    """Dashboard with observations, habitats, pesticide risk, and hives."""
    observations = get_pollinator_summary(conn, location_id, days=30)
    habitats = get_habitat_inventory(conn, location_id)
    pesticide = get_pesticide_risk(conn, location_id, days=90)
    hives = get_hive_status(conn, location_id)

    total_obs = sum(p["observations"] for p in observations["pollinator_types"])
    total_count = sum(
        p["avg_count"] * p["observations"] for p in observations["pollinator_types"]
    )

    return {
        "location_id": location_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observations": {
            "total_observations": total_obs,
            "total_individuals": round(total_count, 0),
            "by_type": observations["pollinator_types"],
        },
        "habitats": {
            "total_area_m2": habitats["total_habitat_m2"],
            "count": habitats["habitat_count"],
            "details": habitats["habitats"],
        },
        "pesticide_risk": {
            "overall_risk": pesticide["overall_risk"],
            "recent_applications": pesticide["total_applications"],
            "risk_distribution": pesticide["risk_distribution"],
        },
        "hives": {
            "total": hives["total_hives"],
            "active": hives["active_hives"],
            "avg_strength": hives["avg_colony_strength"],
            "details": hives["hives"],
        },
    }


# ============================================================
# CLI
# ============================================================

cli = CommandLine("pollinator_health", "Pollinator health monitoring")


def _cmd_record_observation(db, a):
    return record_observation(
        db, a.location_id, a.pollinator_type, a.count,
        observation_method=a.observation_method,
        duration_minutes=a.duration_minutes,
        habitat_area_id=a.habitat_area_id,
        weather_conditions=a.weather,
        temperature_c=a.temperature,
        notes=a.notes,
    )


def _cmd_create_habitat(db, a):
    return create_habitat(
        db, a.location_id, a.name, a.habitat_type, a.area_m2,
        plant_species=a.plant_species,
        bloom_start_month=a.bloom_start_month,
        bloom_end_month=a.bloom_end_month,
        water_source=a.water_source,
        nesting_sites=a.nesting_sites,
        management_notes=a.management_notes,
    )


def _cmd_record_pesticide(db, a):
    app_date = date.fromisoformat(a.application_date)
    return record_pesticide_impact(
        db, a.location_id, app_date, a.product_name,
        a.active_ingredient, a.toxicity_class,
        application_rate=a.application_rate,
        rate_unit=a.rate_unit,
        area_treated_m2=a.area_treated_m2,
        bloom_stage_at_application=a.bloom_stage_at_application,
        pollinator_distance_m=a.pollinator_distance_m,
        notes=a.notes,
    )


def _cmd_add_hive(db, a):
    return add_hive(
        db, a.location_id, a.hive_id,
        colony_strength=a.colony_strength,
        queen_status=a.queen_status,
        hive_type=a.hive_type,
        frame_count=a.frame_count,
        queen_year=a.queen_year,
        notes=a.notes,
    )


def _cmd_record_inspection(db, a):
    return record_hive_inspection(
        db, a.hive_id,
        colony_strength=a.colony_strength,
        queen_status=a.queen_status,
        queen_seen=a.queen_seen,
        varroa_count=a.varroa_count,
        brood_pattern=a.brood_pattern,
        honey_stores=a.honey_stores,
        disease_signs=a.disease_signs,
        temperament=a.temperament,
        population_estimate=a.population_estimate,
        swarm_cells=a.swarm_cells,
        notes=a.notes,
    )


cli.subcommand("record-observation", "Record pollinator observation") \
    .add("--location-id", required=True) \
    .add("--type", required=True, dest="pollinator_type",
         help="Pollinator type (honeybee, bumblebee, butterfly, etc.)") \
    .add("--count", type=int, required=True) \
    .add("--method", default="visual", dest="observation_method") \
    .add("--duration", type=int, default=15, dest="duration_minutes") \
    .add("--habitat-area-id") \
    .add("--weather") \
    .add("--temperature", type=float) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_observation)

cli.subcommand("create-habitat", "Create pollinator habitat") \
    .add("--location-id", required=True) \
    .add("--name", required=True) \
    .add("--type", required=True, dest="habitat_type") \
    .add("--area", type=float, required=True, dest="area_m2") \
    .add("--plant-species", nargs="*", default=[]) \
    .add("--bloom-start", type=int, dest="bloom_start_month") \
    .add("--bloom-end", type=int, dest="bloom_end_month") \
    .add("--water-source", action="store_true") \
    .add("--nesting-sites") \
    .add("--notes", dest="management_notes") \
    .add("--json", action="store_true") \
    .run(_cmd_create_habitat)

cli.subcommand("record-pesticide", "Record pesticide impact") \
    .add("--location-id", required=True) \
    .add("--date", required=True, dest="application_date") \
    .add("--product", required=True, dest="product_name") \
    .add("--ingredient", required=True, dest="active_ingredient") \
    .add("--toxicity", required=True, dest="toxicity_class") \
    .add("--rate", type=float, dest="application_rate") \
    .add("--rate-unit", dest="rate_unit") \
    .add("--area", type=float, dest="area_treated_m2") \
    .add("--bloom-stage", dest="bloom_stage_at_application") \
    .add("--distance", type=float, dest="pollinator_distance_m") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_pesticide)

cli.subcommand("add-hive", "Add managed hive") \
    .add("--location-id", required=True) \
    .add("--hive-id", required=True) \
    .add("--colony-strength", type=int, default=5) \
    .add("--queen-status", default="present") \
    .add("--hive-type", default="langstroth") \
    .add("--frames", type=int, default=10, dest="frame_count") \
    .add("--queen-year", type=int) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_add_hive)

cli.subcommand("record-inspection", "Record hive inspection") \
    .add("--hive-id", required=True) \
    .add("--colony-strength", type=int) \
    .add("--queen-status") \
    .add("--queen-seen", type=bool) \
    .add("--varroa-count", type=int) \
    .add("--brood-pattern") \
    .add("--honey-stores") \
    .add("--disease-signs") \
    .add("--temperament") \
    .add("--population", type=int, dest="population_estimate") \
    .add("--swarm-cells", action="store_true") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_inspection)

cli.subcommand("summary", "Pollinator summary") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_pollinator_summary(db, a.location_id, a.days))

cli.subcommand("habitat-inventory", "Habitat inventory") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_habitat_inventory(db, a.location_id))

cli.subcommand("pesticide-risk", "Pesticide risk") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=90) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_pesticide_risk(db, a.location_id, a.days))

cli.subcommand("hive-status", "Hive status") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_hive_status(db, a.location_id))

cli.subcommand("dashboard", "Pollinator dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_pollinator_dashboard(db, a.location_id))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()
