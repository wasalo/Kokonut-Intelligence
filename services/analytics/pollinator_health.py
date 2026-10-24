#!/usr/bin/env python3
"""Location-scoped pollinator observations, habitat, pesticide and hive records."""

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from ..common.logging import get_logger

logger = get_logger("analytics.pollinator_health")

TOXICITY_RISK = {
    "low": {"risk": "low", "pollinator_harm": "minimal"},
    "moderate": {"risk": "moderate", "pollinator_harm": "sublethal effects possible"},
    "high": {"risk": "high", "pollinator_harm": "lethal to foragers"},
    "very_high": {"risk": "very_high", "pollinator_harm": "lethal to colony"},
}

_POLLINATOR_TYPES = {
    "honeybee", "wild_bee", "butterfly", "moth", "beetle", "fly", "bird", "bat", "other",
}
_OBSERVATION_METHODS = {"transect", "pan_trap", "visual_count", "hive_weight", "other"}
_HABITAT_TYPES = {
    "wildflower_strip", "hedgerow", "nesting_site", "water_source",
    "cover_crop", "native_planting", "other",
}
_HABITAT_ALIASES = {
    "wildflower": "wildflower_strip", "nesting": "nesting_site", "water": "water_source",
}
_HIVE_STRENGTHS = {"strong", "moderate", "weak", "dead"}
_QUEEN_STATUSES = {"present", "absent", "replaced", "unknown"}
_MAX_DETAIL_ROWS = 500


def _json_value(value, *, text_key: str | None = None):
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {text_key: value} if text_key else value
    return value


def _strength_values(value):
    """Keep categorical strength and the legacy 0–10 score distinct."""
    if isinstance(value, bool):
        raise ValueError("Colony strength must be a category or a score from 0 to 10")
    if isinstance(value, int):
        if not 0 <= value <= 10:
            raise ValueError("Colony strength score must be between 0 and 10")
        return None, value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized.isdigit():
            return _strength_values(int(normalized))
        if normalized in _HIVE_STRENGTHS:
            return normalized, None
    raise ValueError("Colony strength must be strong, moderate, weak, dead, or a score from 0 to 10")


def _days(value: int, *, maximum: int = 3650) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"days must be between 1 and {maximum}")
    return value


def _number(value):
    return float(value) if isinstance(value, (int, float, Decimal)) else value


def _write(conn, sql: str, params: tuple):
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def record_observation(
    conn,
    location_id: str,
    pollinator_type: str,
    count: int,
    observation_method: str = "visual_count",
    duration_minutes: int = 15,
    habitat_area_id: str = None,
    weather_conditions: str | dict = None,
    temperature_c: float = None,
    notes: str = None,
    source_system: str = None,
    source_id: str = None,
    metadata: dict = None,
    observation_date: date = None,
    species_name: str = None,
    hive_record_id: str = None,
) -> dict:
    """Record a location observation in the source schema's review state."""
    if pollinator_type not in _POLLINATOR_TYPES:
        raise ValueError(f"pollinator_type must be one of {', '.join(sorted(_POLLINATOR_TYPES))}")
    if observation_method == "visual":  # Legacy CLI spelling.
        observation_method = "visual_count"
    if observation_method not in _OBSERVATION_METHODS:
        raise ValueError(f"observation_method must be one of {', '.join(sorted(_OBSERVATION_METHODS))}")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("Observation count must be a non-negative integer")
    if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes < 0:
        raise ValueError("Observation duration must be a non-negative integer")
    if temperature_c is not None and not -100 <= temperature_c <= 100:
        raise ValueError("temperature_c must be between -100 and 100")
    observed_on = observation_date or date.today()
    obs_id = str(uuid.uuid4())
    weather_payload = _json_value(weather_conditions, text_key="description")
    _write(
        conn,
        """
        INSERT INTO pollinator_observation
            (id, location_id, plot_id, observation_date, pollinator_type,
             species_name, count, observation_method, duration_minutes,
             weather_conditions, temperature_c, hive_record_id, notes,
             source_system, source_id, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s,
                %s, %s, %s, %s::jsonb, 'recorded')
        """,
        (
            obs_id, location_id, habitat_area_id, observed_on, pollinator_type,
            species_name, count, observation_method, duration_minutes,
            json.dumps(weather_payload), temperature_c, hive_record_id, notes,
            source_system, source_id, json.dumps(metadata or {}),
        ),
    )
    logger.info("Recorded pollinator observation: type=%s count=%d location=%s", pollinator_type, count, location_id)
    return {
        "observation_id": obs_id,
        "location_id": location_id,
        "pollinator_type": pollinator_type,
        "count": count,
        "observation_method": observation_method,
        "observation_date": observed_on.isoformat(),
        "duration_minutes": duration_minutes,
        "status": "recorded",
    }


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
    """Create a pollinator habitat using the canonical habitat type values."""
    habitat_type = _HABITAT_ALIASES.get(habitat_type, habitat_type)
    if habitat_type not in _HABITAT_TYPES:
        raise ValueError(f"habitat_type must be one of {', '.join(sorted(_HABITAT_TYPES))}")
    if area_m2 < 0:
        raise ValueError("Habitat area cannot be negative")
    for month in (bloom_start_month, bloom_end_month):
        if month is not None and not 1 <= month <= 12:
            raise ValueError("Bloom months must be between 1 and 12")
    habitat_id = str(uuid.uuid4())
    _write(
        conn,
        """
        INSERT INTO pollinator_habitat
            (id, location_id, habitat_name, habitat_type, area_m2,
             plant_species, bloom_start_month, bloom_end_month, water_source,
             nesting_sites, notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, 'active')
        """,
        (
            habitat_id, location_id, habitat_name, habitat_type, area_m2,
            json.dumps(plant_species or []), bloom_start_month, bloom_end_month,
            water_source, nesting_sites, management_notes, json.dumps(metadata or {}),
        ),
    )
    logger.info("Created pollinator habitat: name=%s type=%s location=%s", habitat_name, habitat_type, location_id)
    return {
        "habitat_id": habitat_id,
        "location_id": location_id,
        "habitat_name": habitat_name,
        "habitat_type": habitat_type,
        "area_m2": area_m2,
        "plant_species": plant_species or [],
        "water_source": water_source,
        "bloom_start_month": bloom_start_month,
        "bloom_end_month": bloom_end_month,
        "nesting_sites": nesting_sites,
        "status": "active",
    }


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
    pollinator_safe_period_days: int = None,
    pollinator_mortality_observed: bool = False,
    mortality_pct: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a pesticide application; the risk label is an advisory heuristic."""
    toxicity_class = toxicity_class.lower()
    if toxicity_class not in TOXICITY_RISK:
        raise ValueError("toxicity_class must be low, moderate, high, or very_high")
    if any(value is not None and value < 0 for value in (application_rate, area_treated_m2, pollinator_distance_m)):
        raise ValueError("Application rate, treated area, and pollinator distance cannot be negative")
    if pollinator_safe_period_days is not None and pollinator_safe_period_days < 0:
        raise ValueError("Pollinator safe-period days cannot be negative")
    if mortality_pct is not None and not 0 <= mortality_pct <= 100:
        raise ValueError("Mortality percentage must be between 0 and 100")
    record_id = str(uuid.uuid4())
    _write(
        conn,
        """
        INSERT INTO pesticide_impact_log
            (id, location_id, application_date, product_name, active_ingredient,
             toxicity_class, application_rate, rate_unit, area_treated_m2,
             bloom_stage_at_application, pollinator_distance_m,
             pollinator_safe_period_days, pollinator_mortality_observed,
             mortality_pct, notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
        """,
        (
            record_id, location_id, application_date, product_name, active_ingredient,
            toxicity_class, application_rate, rate_unit, area_treated_m2,
            bloom_stage_at_application, pollinator_distance_m, pollinator_safe_period_days,
            pollinator_mortality_observed, mortality_pct, notes, json.dumps(metadata or {}),
        ),
    )
    risk_info = TOXICITY_RISK[toxicity_class]
    logger.info("Recorded pesticide impact: product=%s toxicity=%s location=%s", product_name, toxicity_class, location_id)
    return {
        "record_id": record_id,
        "location_id": location_id,
        "product_name": product_name,
        "active_ingredient": active_ingredient,
        "toxicity_class": toxicity_class,
        "pollinator_risk": risk_info["risk"],
        "pollinator_harm": risk_info["pollinator_harm"],
        "application_date": application_date.isoformat(),
        "status": "recorded",
    }


def add_hive(
    conn,
    location_id: str,
    hive_id: str,
    colony_strength: int | str = 5,
    queen_status: str = "present",
    hive_type: str = "langstroth",
    frame_count: int = 10,
    queen_year: int = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Add a managed hive; numeric scores remain separate from category."""
    strength_category, strength_score = _strength_values(colony_strength)
    if queen_status not in _QUEEN_STATUSES:
        raise ValueError("queen_status must be present, absent, replaced, or unknown")
    if isinstance(frame_count, bool) or frame_count < 0:
        raise ValueError("frame_count cannot be negative")
    record_id = str(uuid.uuid4())
    _write(
        conn,
        """
        INSERT INTO hive_record
            (id, location_id, hive_id, hive_type, colony_strength,
             colony_strength_score, queen_status, frame_count, queen_year,
             notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
        """,
        (
            record_id, location_id, hive_id, hive_type, strength_category,
            strength_score, queen_status, frame_count, queen_year, notes, json.dumps(metadata or {}),
        ),
    )
    logger.info("Added hive: hive_id=%s location=%s", hive_id, location_id)
    return {
        "record_id": record_id,
        "location_id": location_id,
        "hive_id": hive_id,
        "hive_type": hive_type,
        "colony_strength": strength_category,
        "colony_strength_score": strength_score,
        "queen_status": queen_status,
        "frame_count": frame_count,
    }


def record_hive_inspection(
    conn,
    location_id: str,
    hive_id: str,
    colony_strength: int | str = None,
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
    """Append a location-bound inspection and refresh the hive snapshot atomically."""
    strength_category, strength_score = _strength_values(colony_strength) if colony_strength is not None else (None, None)
    if queen_status is not None and queen_status not in _QUEEN_STATUSES:
        raise ValueError("queen_status must be present, absent, replaced, or unknown")
    if any(value is not None and value < 0 for value in (varroa_count, population_estimate)):
        raise ValueError("Varroa count and population estimate cannot be negative")
    inspection_id = str(uuid.uuid4())
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM hive_record WHERE location_id = %s AND hive_id = %s FOR UPDATE",
            (location_id, hive_id),
        )
        hive_rows = cur.fetchall()
        if len(hive_rows) != 1:
            raise ValueError("Hive identifier is missing or ambiguous within this location")
        hive_record_id = str(hive_rows[0][0])
        cur.execute(
            """
            INSERT INTO pollinator_hive_inspection
                (id, location_id, hive_record_id, inspection_date,
                 colony_strength, colony_strength_score, queen_status,
                 queen_seen, varroa_count, brood_pattern, honey_stores,
                 disease_signs, temperament, population_estimate,
                 swarm_cells, notes, metadata, status)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
            """,
            (
                inspection_id, location_id, hive_record_id, strength_category,
                strength_score, queen_status, queen_seen, varroa_count,
                brood_pattern, honey_stores, disease_signs, temperament,
                population_estimate, swarm_cells, notes, json.dumps(metadata or {}),
            ),
        )
        cur.execute(
            """
            UPDATE hive_record
               SET colony_strength = CASE
                       WHEN %s IS NOT NULL OR %s IS NOT NULL THEN %s
                       ELSE colony_strength
                   END,
                   colony_strength_score = CASE
                       WHEN %s IS NOT NULL OR %s IS NOT NULL THEN %s
                       ELSE colony_strength_score
                   END,
                   queen_status = COALESCE(%s, queen_status),
                   varroa_count = COALESCE(%s, varroa_count),
                   inspection_date = CURRENT_DATE, updated_at = NOW()
             WHERE id = %s::uuid AND location_id = %s::uuid
            """,
            (
                strength_category, strength_score, strength_category,
                strength_category, strength_score, strength_score,
                queen_status, varroa_count, hive_record_id, location_id,
            ),
        )
        if cur.rowcount != 1:
            raise ValueError("Hive changed or left the selected location during inspection")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
    return {
        "inspection_id": inspection_id,
        "location_id": location_id,
        "hive_id": hive_id,
        "colony_strength": colony_strength,
        "queen_status": queen_status,
        "queen_seen": queen_seen,
        "varroa_count": varroa_count,
        "brood_pattern": brood_pattern,
        "swarm_cells": swarm_cells,
    }


def get_pollinator_summary(conn, location_id: str, days: int = 30) -> dict:
    """Summarize reviewed observations and compare equal recent time windows."""
    days = _days(days)
    half_days = max(1, days // 2)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT pollinator_type, COUNT(*) AS observations,
                   AVG(count) AS avg_count, MAX(count) AS max_count,
                   MIN(observation_date) AS first_obs, MAX(observation_date) AS last_obs,
                   AVG(count) FILTER (WHERE observation_date < CURRENT_DATE - (%s * INTERVAL '1 day')) AS first_half_avg,
                   AVG(count) FILTER (WHERE observation_date >= CURRENT_DATE - (%s * INTERVAL '1 day')) AS second_half_avg,
                   SUM(count) AS total_count
            FROM pollinator_observation
            WHERE location_id = %s
              AND observation_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
              AND status IN ('verified', 'reviewed')
            GROUP BY pollinator_type
            ORDER BY avg_count DESC NULLS LAST, pollinator_type
            """,
            (half_days, half_days, location_id, days),
        )
        cols = [d[0] for d in cur.description]
        by_type = []
        for row in cur.fetchall():
            item = dict(zip(cols, row))
            first_avg, second_avg = _number(item.pop("first_half_avg")), _number(item.pop("second_half_avg"))
            item["avg_count"] = _number(item["avg_count"])
            item["total_count"] = _number(item["total_count"])
            if first_avg is not None and first_avg > 0 and second_avg is not None:
                change = (second_avg - first_avg) / first_avg * 100
                item["trend"] = "increasing" if change > 10 else "decreasing" if change < -10 else "stable"
                item["change_pct"] = round(change, 1)
            else:
                item["trend"] = "insufficient_data"
                item["change_pct"] = 0
            by_type.append(item)
    finally:
        cur.close()
    return {"location_id": location_id, "period_days": days, "pollinator_types": by_type}


def get_habitat_inventory(conn, location_id: str) -> dict:
    """Get the active habitat inventory with source units and features."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, habitat_name, habitat_type, area_m2, plant_species,
                   bloom_period, bloom_start_month, bloom_end_month,
                   water_source, nesting_features, nesting_sites, condition,
                   last_maintenance, notes
            FROM pollinator_habitat
            WHERE location_id = %s AND status = 'active'
            ORDER BY area_m2 DESC NULLS LAST, habitat_name
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        habitats = []
        for row in cur.fetchall():
            habitat = dict(zip(cols, row))
            habitat["plant_species"] = _json_value(habitat["plant_species"])
            habitat["nesting_features"] = _json_value(habitat["nesting_features"])
            habitat["area_m2"] = _number(habitat["area_m2"])
            habitats.append(habitat)
    finally:
        cur.close()
    total_area = sum(h["area_m2"] or 0 for h in habitats)
    return {
        "location_id": location_id,
        "total_habitat_m2": round(total_area, 1),
        "habitat_count": len(habitats),
        "habitats": habitats,
    }


def get_pesticide_risk(conn, location_id: str, days: int = 90) -> dict:
    """Return bounded recent applications and advisory toxicity distribution."""
    days = _days(days)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, application_date, product_name, active_ingredient,
                   toxicity_class, application_rate, rate_unit, area_treated_m2,
                   bloom_stage_at_application, pollinator_distance_m,
                   pollinator_safe_period_days, pollinator_mortality_observed,
                   mortality_pct, status, COUNT(*) OVER () AS total_matching
            FROM pesticide_impact_log
            WHERE location_id = %s
              AND application_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
              AND status IN ('recorded', 'verified', 'reviewed')
            ORDER BY application_date DESC, id
            LIMIT %s
            """,
            (location_id, days, _MAX_DETAIL_ROWS),
        )
        cols = [d[0] for d in cur.description]
        raw_applications = [dict(zip(cols, row)) for row in cur.fetchall()]
        total_applications = raw_applications[0]["total_matching"] if raw_applications else 0
        applications = []
        for row in raw_applications:
            row.pop("total_matching", None)
            row["application_rate"] = _number(row["application_rate"])
            row["area_treated_m2"] = _number(row["area_treated_m2"])
            row["pollinator_distance_m"] = _number(row["pollinator_distance_m"])
            row["mortality_pct"] = _number(row["mortality_pct"])
            info = TOXICITY_RISK.get(row["toxicity_class"])
            row["pollinator_risk"] = info["risk"] if info else "unknown"
            row["pollinator_harm_description"] = info["pollinator_harm"] if info else "unknown"
            applications.append(row)
        cur.execute(
            """
            SELECT toxicity_class, COUNT(*) AS cnt,
                   COUNT(*) FILTER (WHERE pollinator_mortality_observed) AS mortality_events
            FROM pesticide_impact_log
            WHERE location_id = %s
              AND application_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
              AND status IN ('recorded', 'verified', 'reviewed')
            GROUP BY toxicity_class
            """,
            (location_id, days),
        )
        distribution_rows = cur.fetchall()
    finally:
        cur.close()
    risk_counts = {row[0]: row[1] for row in distribution_rows}
    high_risk_count = sum(v for k, v in risk_counts.items() if k in ("high", "very_high"))
    mortality_events = sum(row[2] for row in distribution_rows)
    overall_risk = "critical" if mortality_events or high_risk_count >= 3 else "elevated" if high_risk_count else "low"
    return {
        "location_id": location_id,
        "period_days": days,
        "total_applications": total_applications,
        "applications_truncated": total_applications > _MAX_DETAIL_ROWS,
        "overall_risk": overall_risk,
        "risk_distribution": risk_counts,
        "mortality_events": mortality_events,
        "applications": applications,
    }


def get_hive_status(conn, location_id: str) -> dict:
    """Read active hive snapshots and the latest location-bound inspection."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT h.id, h.hive_id, h.hive_type, h.colony_strength,
                   h.colony_strength_score, h.queen_status, h.frame_count,
                   h.queen_year, h.honey_yield_kg, h.inspection_date,
                   h.varroa_count, h.status, f.avg_daily_foragers,
                   i.id AS inspection_id, i.inspection_date AS last_inspection_date,
                   i.colony_strength AS last_colony_strength,
                   i.colony_strength_score AS last_colony_strength_score,
                   i.queen_status AS last_queen_status, i.queen_seen,
                   i.varroa_count AS last_varroa_count, i.brood_pattern,
                   i.honey_stores, i.disease_signs, i.temperament,
                   i.population_estimate, i.swarm_cells, i.status AS inspection_status
            FROM hive_record h
            LEFT JOIN LATERAL (
                SELECT pi.* FROM pollinator_hive_inspection pi
                WHERE pi.location_id = h.location_id AND pi.hive_record_id = h.id
                  AND pi.status IN ('verified', 'reviewed')
                ORDER BY pi.inspection_date DESC, pi.created_at DESC, pi.id DESC
                LIMIT 1
            ) i ON TRUE
            LEFT JOIN LATERAL (
                SELECT AVG(daily_count) AS avg_daily_foragers
                FROM (
                    SELECT po.observation_date, SUM(po.count)::numeric AS daily_count
                    FROM pollinator_observation po
                    WHERE po.location_id = h.location_id
                      AND po.hive_record_id = h.id
                      AND po.observation_date >= CURRENT_DATE - INTERVAL '30 days'
                      AND po.status IN ('verified', 'reviewed')
                    GROUP BY po.observation_date
                ) daily_counts
            ) f ON TRUE
            WHERE h.location_id = %s
            ORDER BY h.hive_id, h.id
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        hives = []
        for row in rows:
            inspection_id = row.pop("inspection_id")
            inspection = None
            if inspection_id is not None:
                inspection = {
                    key.removeprefix("last_"): row.pop(key)
                    for key in (
                        "last_inspection_date", "last_colony_strength", "last_colony_strength_score",
                        "last_queen_status", "queen_seen", "last_varroa_count", "brood_pattern",
                        "honey_stores", "disease_signs", "temperament", "population_estimate",
                        "swarm_cells", "inspection_status",
                    )
                }
                # Preserve the review state under a descriptive key.
                inspection["status"] = inspection.pop("inspection_status")
            else:
                for key in (
                    "last_inspection_date", "last_colony_strength", "last_colony_strength_score",
                    "last_queen_status", "queen_seen", "last_varroa_count", "brood_pattern",
                    "honey_stores", "disease_signs", "temperament", "population_estimate",
                    "swarm_cells", "inspection_status",
                ):
                    row.pop(key, None)
            row["last_inspection"] = inspection
            for key in ("colony_strength_score", "honey_yield_kg"):
                row[key] = _number(row[key])
            row["avg_daily_foragers"] = _number(row["avg_daily_foragers"])
            hives.append(row)
        cur.execute(
            """
            SELECT AVG(colony_strength_score)
            FROM hive_record
            WHERE location_id = %s AND status = 'active' AND colony_strength_score IS NOT NULL
            """,
            (location_id,),
        )
        avg_row = cur.fetchone()
    finally:
        cur.close()
    active = sum(1 for hive in hives if hive["status"] == "active")
    avg_strength = _number(avg_row[0]) if avg_row and avg_row[0] is not None else None
    return {
        "location_id": location_id,
        "total_hives": len(hives),
        "active_hives": active,
        "avg_colony_strength": round(avg_strength, 1) if avg_strength is not None else None,
        "hives": hives,
    }


def get_pollinator_dashboard(conn, location_id: str) -> dict:
    """Build the legacy dashboard response from schema-aligned bounded reads."""
    observations = get_pollinator_summary(conn, location_id, days=30)
    habitats = get_habitat_inventory(conn, location_id)
    pesticide = get_pesticide_risk(conn, location_id, days=90)
    hives = get_hive_status(conn, location_id)
    total_obs = sum(p["observations"] for p in observations["pollinator_types"])
    total_count = sum(p["total_count"] or 0 for p in observations["pollinator_types"])
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
