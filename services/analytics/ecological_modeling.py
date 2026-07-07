"""Ecological modeling analytics: trophic interactions, energy flow, population dynamics."""

from __future__ import annotations

import math
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_trophic_balance(conn, location_id: str) -> dict[str, Any]:
    """Compute trophic balance metrics from ecological interactions."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT interaction_type, COUNT(*) AS cnt, AVG(interaction_strength) AS avg_strength
        FROM ecological_interaction
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY interaction_type
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    counts = {row[0]: row[1] for row in rows}
    strengths = {row[0]: float(row[2] or 0) for row in rows}
    mutualism_count = counts.get("mutualism", 0)
    competition_count = counts.get("competition", 0)
    predation_count = counts.get("predation", 0)
    facilitation_count = counts.get("facilitation", 0)
    total = sum(counts.values())
    trophic_balance = mutualism_count / max(mutualism_count + competition_count, 1)
    return {
        "location_id": location_id,
        "total_interactions": total,
        "mutualism_count": mutualism_count,
        "competition_count": competition_count,
        "predation_count": predation_count,
        "facilitation_count": facilitation_count,
        "trophic_balance_index": round(trophic_balance, 3),
        "avg_interaction_strength": round(
            sum(strengths.values()) / max(len(strengths), 1), 3
        ),
    }


def compute_energy_flow_efficiency(conn, location_id: str) -> dict[str, Any]:
    """Compute energy flow efficiency across trophic transfers."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT from_trophic_level, to_trophic_level,
               SUM(biomass_transferred_kg) AS total_kg,
               AVG(conversion_efficiency_pct) AS avg_efficiency,
               COUNT(*) AS measurements
        FROM energy_flow_measurement
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY from_trophic_level, to_trophic_level
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    transfers = []
    for row in rows:
        transfers.append({
            "from_level": row[0],
            "to_level": row[1],
            "total_biomass_kg": float(row[2] or 0),
            "avg_efficiency_pct": round(float(row[3] or 0), 2),
            "measurement_count": row[4],
        })
    overall_efficiency = 0.0
    total_kg = sum(t["total_biomass_kg"] for t in transfers)
    if total_kg > 0:
        weighted = sum(t["total_biomass_kg"] * t["avg_efficiency_pct"] for t in transfers)
        overall_efficiency = weighted / total_kg
    return {
        "location_id": location_id,
        "transfers": transfers,
        "total_transfers": len(transfers),
        "total_biomass_kg": round(total_kg, 2),
        "overall_efficiency_pct": round(overall_efficiency, 2),
    }


def compute_population_stability(conn, location_id: str) -> dict[str, Any]:
    """Compute population stability index from population dynamics records."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT species_name, species_common_name, trophic_level,
               COUNT(*) AS obs_count,
               AVG(population_count) AS avg_pop,
               STDDEV(population_count) AS stddev_pop,
               MIN(population_count) AS min_pop,
               MAX(population_count) AS max_pop,
               MIN(record_date) AS first_date,
               MAX(record_date) AS last_date
        FROM population_dynamics_record
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY species_name, species_common_name, trophic_level
        HAVING COUNT(*) >= 2
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    species_stability = []
    for row in rows:
        avg = float(row[4] or 0)
        stddev = float(row[5] or 0)
        cv = stddev / avg if avg > 0 else 0
        species_stability.append({
            "species_name": row[0],
            "species_common_name": row[1],
            "trophic_level": row[2],
            "observation_count": row[3],
            "avg_population": round(avg, 2),
            "stddev_population": round(stddev, 2),
            "coefficient_of_variation": round(cv, 3),
            "min_population": row[6],
            "max_population": row[7],
            "first_observed": str(row[8]) if row[8] else None,
            "last_observed": str(row[9]) if row[9] else None,
        })
    overall_stability = 0.0
    if species_stability:
        cvs = [s["coefficient_of_variation"] for s in species_stability]
        overall_stability = 1.0 - (sum(cvs) / len(cvs))
        overall_stability = max(0.0, min(1.0, overall_stability))
    return {
        "location_id": location_id,
        "species_stability": species_stability,
        "species_with_sufficient_data": len(species_stability),
        "population_stability_index": round(overall_stability, 3),
    }


def trophic_pyramid_summary(conn, location_id: str) -> dict[str, Any]:
    """Summarize species counts by trophic level for pyramid visualization."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT trophic_level, COUNT(DISTINCT species_name) AS species_count,
               SUM(population_count) AS total_individuals
        FROM population_dynamics_record
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY trophic_level
        ORDER BY CASE trophic_level
            WHEN 'producer' THEN 1
            WHEN 'primary_consumer' THEN 2
            WHEN 'secondary_consumer' THEN 3
            WHEN 'decomposer' THEN 4
            WHEN 'omnivore' THEN 5
        END
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    levels = []
    for row in rows:
        levels.append({
            "trophic_level": row[0],
            "species_count": row[1],
            "total_individuals": row[2],
        })
    return {
        "location_id": location_id,
        "trophic_levels": levels,
        "total_levels": len(levels),
    }
