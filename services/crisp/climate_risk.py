"""Climate catastrophe risk scoring module.

Adapted from SW-CRISP Annexure 2.  Estimates the probability of climate-related
events (drought, flood, heatwave, fire, storm, water stress) affecting project
outcomes using historical weather data and emergency incident records.

Scoring approach:
1. Query weather observations for anomaly patterns
2. Query emergency incidents for historical climate events
3. Compute per-hazard risk scores (0-3 each, max 15 total)
4. Apply mitigation factor from risk mitigation register
5. Convert natural risk rating to 0-100 risk score
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .models import DimensionScore
from .normalization import clamp_risk_score, hazard_score_to_risk


# Hazard severity thresholds (inspired by Verra AFOLU Non-Permanence Risk Tool)
HAZARD_THRESHOLDS = {
    "drought": {
        "low": 0.0,
        "medium": 1.0,
        "high": 2.0,
        "critical": 3.0,
    },
    "flood": {
        "low": 0.0,
        "medium": 1.0,
        "high": 2.0,
        "critical": 3.0,
    },
    "heatwave": {
        "low": 0.0,
        "medium": 1.0,
        "high": 2.0,
        "critical": 3.0,
    },
    "fire": {
        "low": 0.0,
        "medium": 1.0,
        "high": 2.0,
        "critical": 3.0,
    },
    "storm": {
        "low": 0.0,
        "medium": 1.0,
        "high": 2.0,
        "critical": 3.0,
    },
    "water_stress": {
        "low": 0.0,
        "medium": 1.0,
        "high": 2.0,
        "critical": 3.0,
    },
}


def _query_weather_patterns(conn, location_id: str) -> Dict[str, Any]:
    """Analyze weather observation patterns for climate risk."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS observation_count,
            COALESCE(AVG(temperature_celsius), 0) AS avg_temp,
            COALESCE(MAX(temperature_celsius), 0) AS max_temp,
            COALESCE(MIN(temperature_celsius), 0) AS min_temp,
            COALESCE(AVG(rainfall_mm), 0) AS avg_rainfall,
            COALESCE(SUM(CASE WHEN rainfall_mm = 0 THEN 1 ELSE 0 END), 0) AS dry_days,
            COALESCE(AVG(humidity_pct), 0) AS avg_humidity,
            COALESCE(MAX(wind_speed_kph), 0) AS max_wind
        FROM weather_observation
        WHERE location_id = %s
        AND observation_date >= NOW() - INTERVAL '3 years'
    """, (location_id,))
    row = dict(cur.fetchone() or {})
    cur.close()
    return row


def _query_emergency_incidents(conn, location_id: str) -> List[Dict[str, Any]]:
    """Query historical emergency incidents by type."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            incident_type,
            severity,
            COUNT(*) AS incident_count,
            MAX(incident_date) AS last_occurrence
        FROM emergency_incident
        WHERE location_id = %s
        GROUP BY incident_type, severity
        ORDER BY incident_count DESC
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def _query_climate_mitigation(conn, location_id: str) -> float:
    """Get mitigation factor from active climate risk mitigation measures."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT COUNT(*) AS mitigation_count
        FROM risk_mitigation_register
        WHERE location_id = %s
        AND risk_category = 'climate'
        AND status = 'published'
    """, (location_id,))
    row = cur.fetchone()
    cur.close()
    count = int(row["mitigation_count"] or 0) if row else 0
    # Each mitigation measure reduces risk by 5%, min 0.5
    return max(0.5, 1.0 - (count * 0.05))


def _score_drought(weather: Dict[str, Any], incidents: List[Dict[str, Any]]) -> float:
    """Score drought risk (0-3)."""
    score = 0.0

    # Dry day ratio
    total_obs = int(weather.get("observation_count", 0) or 0)
    dry_days = int(weather.get("dry_days", 0) or 0)
    if total_obs > 0:
        dry_ratio = dry_days / total_obs
        if dry_ratio > 0.6:
            score += 1.5
        elif dry_ratio > 0.4:
            score += 1.0
        elif dry_ratio > 0.2:
            score += 0.5

    # Low average rainfall
    avg_rain = float(weather.get("avg_rainfall", 0) or 0)
    if avg_rain < 30:
        score += 1.0
    elif avg_rain < 60:
        score += 0.5

    # Historical drought incidents
    for inc in incidents:
        if inc.get("incident_type") in ("drought", "water_crisis"):
            sev = inc.get("severity", "low")
            if sev == "critical":
                score += 1.5
            elif sev == "high":
                score += 1.0
            elif sev == "medium":
                score += 0.5
            break

    return min(3.0, score)


def _score_flood(weather: Dict[str, Any], incidents: List[Dict[str, Any]]) -> float:
    """Score flood risk (0-3)."""
    score = 0.0
    avg_rain = float(weather.get("avg_rainfall", 0) or 0)
    if avg_rain > 200:
        score += 1.5
    elif avg_rain > 120:
        score += 1.0
    elif avg_rain > 80:
        score += 0.5

    for inc in incidents:
        if inc.get("incident_type") == "flood":
            sev = inc.get("severity", "low")
            if sev == "critical":
                score += 1.5
            elif sev == "high":
                score += 1.0
            elif sev == "medium":
                score += 0.5
            break

    return min(3.0, score)


def _score_heatwave(weather: Dict[str, Any], incidents: List[Dict[str, Any]]) -> float:
    """Score heatwave risk (0-3)."""
    score = 0.0
    max_temp = float(weather.get("max_temp", 0) or 0)
    if max_temp > 45:
        score += 2.0
    elif max_temp > 40:
        score += 1.5
    elif max_temp > 35:
        score += 1.0

    for inc in incidents:
        if inc.get("incident_type") == "extreme_heat":
            sev = inc.get("severity", "low")
            if sev in ("critical", "high"):
                score += 1.0
            elif sev == "medium":
                score += 0.5
            break

    return min(3.0, score)


def _score_fire(weather: Dict[str, Any], incidents: List[Dict[str, Any]]) -> float:
    """Score fire risk (0-3)."""
    score = 0.0
    # Dry + hot = fire risk
    dry_days = int(weather.get("dry_days", 0) or 0)
    total_obs = int(weather.get("observation_count", 0) or 0)
    max_temp = float(weather.get("max_temp", 0) or 0)

    if total_obs > 0 and dry_days / total_obs > 0.5 and max_temp > 35:
        score += 1.5
    elif total_obs > 0 and dry_days / total_obs > 0.3:
        score += 0.5

    for inc in incidents:
        if inc.get("incident_type") == "fire":
            sev = inc.get("severity", "low")
            if sev == "critical":
                score += 2.0
            elif sev == "high":
                score += 1.5
            elif sev == "medium":
                score += 0.5
            break

    return min(3.0, score)


def _score_storm(weather: Dict[str, Any], incidents: List[Dict[str, Any]]) -> float:
    """Score storm/cyclone risk (0-3)."""
    score = 0.0
    max_wind = float(weather.get("max_wind", 0) or 0)
    if max_wind > 100:
        score += 2.0
    elif max_wind > 60:
        score += 1.5
    elif max_wind > 40:
        score += 0.5

    for inc in incidents:
        if inc.get("incident_type") in ("storm", "cyclone"):
            sev = inc.get("severity", "low")
            if sev in ("critical", "high"):
                score += 1.5
            elif sev == "medium":
                score += 0.5
            break

    return min(3.0, score)


def _score_water_stress(weather: Dict[str, Any], incidents: List[Dict[str, Any]]) -> float:
    """Score water stress risk (0-3)."""
    score = 0.0
    avg_rain = float(weather.get("avg_rainfall", 0) or 0)
    avg_humidity = float(weather.get("avg_humidity", 0) or 0)

    if avg_rain < 30 and avg_humidity < 40:
        score += 2.0
    elif avg_rain < 60 or avg_humidity < 30:
        score += 1.0

    for inc in incidents:
        if inc.get("incident_type") in ("water_crisis", "drought"):
            sev = inc.get("severity", "low")
            if sev in ("critical", "high"):
                score += 1.0
            elif sev == "medium":
                score += 0.5
            break

    return min(3.0, score)


def compute_climate_risk(
    conn,
    location_id: str,
    ssp_scenario: str = "SSP2",
) -> DimensionScore:
    """Compute climate catastrophe risk score for a location.

    Args:
        conn: PostgreSQL connection.
        location_id: Location UUID.
        ssp_scenario: Shared Socioeconomic Pathway (SSP1, SSP2, SSP5).

    Returns:
        DimensionScore with risk_score 0-100 (higher = more risk).
    """
    weather = _query_weather_patterns(conn, location_id)
    incidents = _query_emergency_incidents(conn, location_id)
    mitigation_factor = _query_climate_mitigation(conn, location_id)

    # Compute per-hazard scores
    drought = _score_drought(weather, incidents)
    flood = _score_flood(weather, incidents)
    heatwave = _score_heatwave(weather, incidents)
    fire = _score_fire(weather, incidents)
    storm = _score_storm(weather, incidents)
    water_stress = _score_water_stress(weather, incidents)

    natural_risk_rating = drought + flood + heatwave + fire + storm + water_stress
    # Apply mitigation
    mitigated_rating = natural_risk_rating * mitigation_factor
    mitigated_rating = min(15.0, mitigated_rating)

    # Convert to 0-1 risk factor
    catastrophe_factor = mitigated_rating / 15.0
    risk_score = hazard_score_to_risk(natural_risk_rating, 15.0)

    # Evidence maturity
    total_obs = int(weather.get("observation_count", 0) or 0)
    incident_count = len(incidents)
    evidence_level = 1
    if total_obs > 10:
        evidence_level = 3
    if total_obs > 50:
        evidence_level = 4
    if incident_count > 0:
        evidence_level = min(evidence_level + 1, 6)

    from .config import CONFIDENCE_THRESHOLDS
    confidence = CONFIDENCE_THRESHOLDS.get(evidence_level, "insufficient_evidence")

    historical_events = [
        {"type": inc["incident_type"], "severity": inc["severity"],
         "count": inc["incident_count"], "last": str(inc.get("last_occurrence", ""))}
        for inc in incidents
    ]

    factors = {
        "drought_score": round(drought, 2),
        "flood_score": round(flood, 2),
        "heatwave_score": round(heatwave, 2),
        "fire_score": round(fire, 2),
        "storm_score": round(storm, 2),
        "water_stress_score": round(water_stress, 2),
        "natural_risk_rating": round(natural_risk_rating, 2),
        "mitigation_factor": round(mitigation_factor, 2),
        "mitigated_rating": round(mitigated_rating, 2),
        "weather_observations": total_obs,
        "historical_incidents": incident_count,
        "ssp_scenario": ssp_scenario,
    }

    return DimensionScore(
        dimension_key="climate",
        dimension_name="Climate Catastrophe Risk",
        risk_score=clamp_risk_score(risk_score),
        confidence_level=confidence,
        evidence_maturity_level=evidence_level,
        weight=0.0,
        factors=factors,
        evidence_summary=f"Natural risk rating {natural_risk_rating:.1f}/15 (mitigated: {mitigated_rating:.1f}), factor {catastrophe_factor:.2f}",
        uncertainty_notes=f"SSP scenario: {ssp_scenario}" if ssp_scenario != "SSP2" else None,
    )
