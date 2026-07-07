"""Ecological modeling analytics v2: soil inputs, pest trends, biocontrol, resource efficiency."""

from __future__ import annotations

import math
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_soil_input_retention(conn, location_id: str) -> dict[str, Any]:
    """Compute organic input retention metrics over time."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT input_type, input_name,
               SUM(quantity_kg) AS total_kg,
               AVG(residual_pct) AS avg_residual_pct,
               COUNT(*) AS application_count,
               MIN(application_date) AS first_applied,
               MAX(residual_measurement_date) AS last_measured
        FROM soil_input_application
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY input_type, input_name
        ORDER BY total_kg DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    inputs = []
    for row in rows:
        inputs.append({
            "input_type": row[0],
            "input_name": row[1],
            "total_kg": float(row[2] or 0),
            "avg_residual_pct": round(float(row[3] or 0), 2),
            "application_count": row[4],
            "first_applied": str(row[5]) if row[5] else None,
            "last_measured": str(row[6]) if row[6] else None,
        })
    total_kg = sum(i["total_kg"] for i in inputs)
    weighted_residual = sum(i["total_kg"] * i["avg_residual_pct"] for i in inputs)
    overall_residual = weighted_residual / total_kg if total_kg > 0 else 0
    return {
        "location_id": location_id,
        "inputs": inputs,
        "total_input_kg": round(total_kg, 2),
        "weighted_avg_residual_pct": round(overall_residual, 2),
        "input_types_count": len(set(i["input_type"] for i in inputs)),
    }


def compute_pest_trends(conn, location_id: str) -> dict[str, Any]:
    """Compute pest incidence trends and outbreak probability over time."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DATE_TRUNC('month', observation_date) AS month,
               pest_species, pest_common_name, pest_category,
               COUNT(*) AS observation_count,
               AVG(outbreak_probability_pct) AS avg_outbreak_prob,
               AVG(affected_area_pct) AS avg_affected_area,
               SUM(CASE WHEN severity IN ('high', 'critical') THEN 1 ELSE 0 END) AS severe_count,
               AVG(incidence_count) AS avg_incidence,
               AVG(temperature_c) AS avg_temp,
               AVG(humidity_pct) AS avg_humidity,
               SUM(COALESCE(predator_count, 0)) AS total_predators,
               SUM(CASE WHEN natural_enemy_present THEN 1 ELSE 0 END) AS natural_enemy_count
        FROM pest_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY DATE_TRUNC('month', observation_date), pest_species, pest_common_name, pest_category
        ORDER BY month DESC, avg_outbreak_prob DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    trends = []
    for row in rows:
        trends.append({
            "month": str(row[0]) if row[0] else None,
            "pest_species": row[1],
            "pest_common_name": row[2],
            "pest_category": row[3],
            "observation_count": row[4],
            "avg_outbreak_probability_pct": round(float(row[5] or 0), 2),
            "avg_affected_area_pct": round(float(row[6] or 0), 2),
            "severe_count": row[7],
            "avg_incidence": round(float(row[8] or 0), 2),
            "avg_temperature_c": round(float(row[9] or 0), 1),
            "avg_humidity_pct": round(float(row[10] or 0), 1),
            "total_predators": row[11],
            "natural_enemy_present_count": row[12],
        })
    total_obs = sum(t["observation_count"] for t in trends)
    avg_prob = (
        sum(t["avg_outbreak_probability_pct"] * t["observation_count"] for t in trends)
        / total_obs if total_obs > 0 else 0
    )
    return {
        "location_id": location_id,
        "trends": trends,
        "total_observations": total_obs,
        "weighted_avg_outbreak_probability_pct": round(avg_prob, 2),
        "unique_pest_species": len(set(t["pest_species"] for t in trends)),
    }


def compute_biocontrol_effectiveness(conn, location_id: str) -> dict[str, Any]:
    """Compute biocontrol release effectiveness metrics."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT predator_species, predator_common_name, predator_category,
               target_pest,
               COUNT(*) AS release_count,
               SUM(release_count) AS total_released,
               AVG(effectiveness_pct) AS avg_effectiveness,
               AVG(pest_reduction_pct) AS avg_pest_reduction,
               AVG(release_density_per_m2) AS avg_density,
               MIN(release_date) AS first_release,
               MAX(follow_up_date) AS last_follow_up
        FROM biocontrol_release
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY predator_species, predator_common_name, predator_category, target_pest
        ORDER BY avg_pest_reduction DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    releases = []
    for row in rows:
        releases.append({
            "predator_species": row[0],
            "predator_common_name": row[1],
            "predator_category": row[2],
            "target_pest": row[3],
            "release_count": row[4],
            "total_released": row[5],
            "avg_effectiveness_pct": round(float(row[6] or 0), 2),
            "avg_pest_reduction_pct": round(float(row[7] or 0), 2),
            "avg_density_per_m2": round(float(row[8] or 0), 4),
            "first_release": str(row[9]) if row[9] else None,
            "last_follow_up": str(row[10]) if row[10] else None,
        })
    total_released = sum(r["total_released"] or 0 for r in releases)
    avg_reduction = (
        sum((r["avg_pest_reduction_pct"] or 0) * (r["release_count"] or 0) for r in releases)
        / max(sum(r["release_count"] or 0 for r in releases), 1)
    )
    return {
        "location_id": location_id,
        "releases": releases,
        "total_release_events": len(releases),
        "total_organisms_released": total_released,
        "weighted_avg_pest_reduction_pct": round(avg_reduction, 2),
    }


def compute_resource_efficiency(conn, location_id: str) -> dict[str, Any]:
    """Compute resource consumption efficiency (labor, energy, water per kg yield)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT resource_type, unit, component,
               SUM(quantity) AS total_quantity,
               AVG(quantity) AS avg_per_period,
               COUNT(*) AS record_count,
               SUM(CASE WHEN is_estimated THEN 1 ELSE 0 END) AS estimated_count
        FROM resource_consumption
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY resource_type, unit, component
        ORDER BY resource_type, total_quantity DESC
        """,
        (location_id,),
    )
    resource_rows = cur.fetchall()
    cur.execute(
        """
        SELECT SUM(he.quantity) AS total_harvest_kg
        FROM harvest_event he
        JOIN location l ON l.id = he.location_id
        WHERE he.location_id = %s AND he.status IN ('verified', 'published')
        """,
        (location_id,),
    )
    harvest_row = cur.fetchone()
    cur.close()
    total_harvest_kg = float(harvest_row[0] or 0) if harvest_row else 0
    resources = []
    for row in resource_rows:
        total_qty = float(row[3] or 0)
        per_kg = total_qty / total_harvest_kg if total_harvest_kg > 0 else 0
        resources.append({
            "resource_type": row[0],
            "unit": row[1],
            "component": row[2],
            "total_quantity": round(total_qty, 2),
            "avg_per_period": round(float(row[4] or 0), 2),
            "record_count": row[5],
            "estimated_count": row[6],
            "quantity_per_kg_yield": round(per_kg, 4),
        })
    labor = next((r for r in resources if r["resource_type"] == "labor_hours"), None)
    energy = next((r for r in resources if r["resource_type"] == "energy_kwh"), None)
    water = next((r for r in resources if r["resource_type"] == "water_liters"), None)
    return {
        "location_id": location_id,
        "resources": resources,
        "total_harvest_kg": round(total_harvest_kg, 2),
        "labor_hours_per_kg": labor["quantity_per_kg_yield"] if labor else None,
        "energy_kwh_per_kg": energy["quantity_per_kg_yield"] if energy else None,
        "water_liters_per_kg": water["quantity_per_kg_yield"] if water else None,
    }


def compute_conservation_status_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize species by conservation status for a location."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT conservation_status,
               COUNT(DISTINCT species_name) AS species_count,
               SUM(count) AS total_individuals
        FROM species_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND conservation_status IS NOT NULL
        GROUP BY conservation_status
        ORDER BY CASE conservation_status
            WHEN 'critically_endangered' THEN 1
            WHEN 'endangered' THEN 2
            WHEN 'vulnerable' THEN 3
            WHEN 'near_threatened' THEN 4
            WHEN 'least_concern' THEN 5
            WHEN 'data_deficient' THEN 6
            WHEN 'not_evaluated' THEN 7
        END
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    statuses = []
    for row in rows:
        statuses.append({
            "conservation_status": row[0],
            "species_count": row[1],
            "total_individuals": row[2],
        })
    total_species = sum(s["species_count"] for s in statuses)
    return {
        "location_id": location_id,
        "conservation_statuses": statuses,
        "total_species_with_status": total_species,
    }
