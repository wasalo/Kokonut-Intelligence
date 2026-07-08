"""Gap closure analytics: yield delta, soil nutrient correlation, species richness, rainfall vs irrigation."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_yield_delta(conn, location_id: str) -> dict[str, Any]:
    """Compute actual vs predicted yield delta per crop cycle (Q1).

    Formula: actual_yield - predicted_yield_kg
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cc.id AS cycle_id,
               c.name AS crop_name,
               cc.cycle_name,
               cc.expected_yield AS predicted_yield,
               cc.expected_yield_unit AS unit,
               cc.actual_yield,
               cc.actual_harvest_date,
               CASE
                   WHEN cc.expected_yield IS NOT NULL AND cc.actual_yield IS NOT NULL
                   THEN cc.actual_yield - cc.expected_yield
                   ELSE NULL
               END AS yield_delta,
               CASE
                   WHEN cc.expected_yield IS NOT NULL AND cc.expected_yield > 0 AND cc.actual_yield IS NOT NULL
                   THEN ROUND(((cc.actual_yield - cc.expected_yield) / cc.expected_yield * 100)::numeric, 2)
                   ELSE NULL
               END AS yield_delta_pct,
               cc.status
        FROM crop_cycle cc
        JOIN crop c ON c.id = cc.crop_id
        WHERE cc.location_id = %s
          AND cc.status IN ('completed', 'harvested')
          AND cc.actual_yield IS NOT NULL
        ORDER BY cc.actual_harvest_date DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    cycles = []
    for row in rows:
        cycles.append({
            "cycle_id": str(row[0]),
            "crop_name": row[1],
            "cycle_name": row[2],
            "predicted_yield": float(row[3]) if row[3] is not None else None,
            "unit": row[4],
            "actual_yield": float(row[5]) if row[5] is not None else None,
            "actual_harvest_date": str(row[6]) if row[6] else None,
            "yield_delta": float(row[7]) if row[7] is not None else None,
            "yield_delta_pct": float(row[8]) if row[8] is not None else None,
            "status": row[9],
        })
    deltas = [c["yield_delta"] for c in cycles if c["yield_delta"] is not None]
    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    pct_deltas = [c["yield_delta_pct"] for c in cycles if c["yield_delta_pct"] is not None]
    avg_pct_delta = sum(pct_deltas) / len(pct_deltas) if pct_deltas else 0
    return {
        "location_id": location_id,
        "cycles": cycles,
        "total_completed_cycles": len(cycles),
        "avg_yield_delta": round(avg_delta, 4),
        "avg_yield_delta_pct": round(avg_pct_delta, 2),
        "underpredicted_count": sum(1 for d in deltas if d > 0),
        "overpredicted_count": sum(1 for d in deltas if d < 0),
    }


def compute_soil_nutrient_input_correlation(conn, location_id: str) -> dict[str, Any]:
    """Compute correlation between soil nitrogen trends and organic input applications (Q3).

    Joins soil_sample nitrogen_ppm delta with soil_input_application biochar/compost quantities.
    """
    cur = conn.cursor()
    # Get soil nitrogen readings per plot with deltas
    cur.execute(
        """
        SELECT ss.plot_id,
               p.name AS plot_name,
               ss_first.nitrogen_ppm AS first_nitrogen_ppm,
               ss_last.nitrogen_ppm AS last_nitrogen_ppm,
               ss_last.nitrogen_ppm - ss_first.nitrogen_ppm AS nitrogen_delta_ppm,
               ss_first.sample_date AS first_date,
               ss_last.sample_date AS last_date
        FROM (
            SELECT plot_id,
                   nitrogen_ppm,
                   sample_date,
                   ROW_NUMBER() OVER (PARTITION BY plot_id ORDER BY sample_date ASC) AS rn_first,
                   ROW_NUMBER() OVER (PARTITION BY plot_id ORDER BY sample_date DESC) AS rn_last
            FROM soil_sample
            WHERE location_id = %s
              AND nitrogen_ppm IS NOT NULL
              AND status IS DISTINCT FROM 'rejected'
        ) ss_first
        JOIN (
            SELECT plot_id,
                   nitrogen_ppm,
                   sample_date,
                   ROW_NUMBER() OVER (PARTITION BY plot_id ORDER BY sample_date ASC) AS rn_first,
                   ROW_NUMBER() OVER (PARTITION BY plot_id ORDER BY sample_date DESC) AS rn_last
            FROM soil_sample
            WHERE location_id = %s
              AND nitrogen_ppm IS NOT NULL
              AND status IS DISTINCT FROM 'rejected'
        ) ss_last ON ss_first.plot_id = ss_last.plot_id
        JOIN plot p ON p.id = ss_first.plot_id
        WHERE ss_first.rn_first = 1 AND ss_last.rn_last = 1
          AND ss_first.plot_id = ss_last.plot_id
        """,
        (location_id, location_id),
    )
    soil_rows = cur.fetchall()
    # Get organic input applications per plot
    cur.execute(
        """
        SELECT sia.plot_id,
               p.name AS plot_name,
               sia.input_type,
               SUM(sia.quantity_kg) AS total_input_kg,
               COUNT(*) AS application_count,
               MIN(sia.application_date) AS first_application,
               MAX(sia.application_date) AS last_application
        FROM soil_input_application sia
        JOIN plot p ON p.id = sia.plot_id
        WHERE sia.location_id = %s
          AND sia.status IN ('verified', 'published')
          AND sia.input_type IN ('biochar', 'compost', 'vermicompost', 'leaf_litter')
        GROUP BY sia.plot_id, p.name, sia.input_type
        ORDER BY total_input_kg DESC
        """,
        (location_id,),
    )
    input_rows = cur.fetchall()
    cur.close()
    nitrogen_data = []
    for row in soil_rows:
        nitrogen_data.append({
            "plot_id": str(row[0]),
            "plot_name": row[1],
            "first_nitrogen_ppm": float(row[2]) if row[2] is not None else None,
            "last_nitrogen_ppm": float(row[3]) if row[3] is not None else None,
            "nitrogen_delta_ppm": float(row[4]) if row[4] is not None else None,
            "first_date": str(row[5]) if row[5] else None,
            "last_date": str(row[6]) if row[6] else None,
        })
    input_data = []
    for row in input_rows:
        input_data.append({
            "plot_id": str(row[0]),
            "plot_name": row[1],
            "input_type": row[2],
            "total_input_kg": float(row[3] or 0),
            "application_count": row[4],
            "first_application": str(row[5]) if row[5] else None,
            "last_application": str(row[6]) if row[6] else None,
        })
    # Match by plot_id
    correlations = []
    for n in nitrogen_data:
        plot_inputs = [i for i in input_data if i["plot_id"] == n["plot_id"]]
        total_biochar = sum(i["total_input_kg"] for i in plot_inputs if i["input_type"] == "biochar")
        total_compost = sum(i["total_input_kg"] for i in plot_inputs if i["input_type"] in ("compost", "vermicompost"))
        total_litter = sum(i["total_input_kg"] for i in plot_inputs if i["input_type"] == "leaf_litter")
        total_organic = total_biochar + total_compost + total_litter
        correlations.append({
            "plot_id": n["plot_id"],
            "plot_name": n["plot_name"],
            "nitrogen_delta_ppm": n["nitrogen_delta_ppm"],
            "total_biochar_kg": round(total_biochar, 2),
            "total_compost_kg": round(total_compost, 2),
            "total_leaf_litter_kg": round(total_litter, 2),
            "total_organic_input_kg": round(total_organic, 2),
            "nitrogen_per_input_kg": round(n["nitrogen_delta_ppm"] / total_organic, 4) if total_organic > 0 and n["nitrogen_delta_ppm"] is not None else None,
            "first_date": n["first_date"],
            "last_date": n["last_date"],
        })
    return {
        "location_id": location_id,
        "correlations": correlations,
        "plots_with_data": len(correlations),
    }


def compute_species_richness_per_ha(conn, location_id: str) -> dict[str, Any]:
    """Compute species richness per hectare (Q11).

    Formula: count_unique_species / area_hectares
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT so.plot_id,
               p.name AS plot_name,
               p.area AS plot_area_ha,
               COUNT(DISTINCT so.species_name) AS unique_species,
               COUNT(*) AS total_observations,
               MAX(so.observation_date) AS last_observation
        FROM species_observation so
        LEFT JOIN plot p ON p.id = so.plot_id
        WHERE so.location_id = %s
          AND so.status IN ('verified', 'published')
        GROUP BY so.plot_id, p.name, p.area
        """,
        (location_id,),
    )
    plot_rows = cur.fetchall()
    cur.execute(
        """
        SELECT COUNT(DISTINCT so.species_name) AS unique_species,
               COUNT(*) AS total_observations,
               COALESCE(SUM(p.area), 0) AS total_area_ha,
               MAX(so.observation_date) AS last_observation
        FROM species_observation so
        LEFT JOIN plot p ON p.id = so.plot_id
        WHERE so.location_id = %s
          AND so.status IN ('verified', 'published')
        """,
        (location_id,),
    )
    location_row = cur.fetchone()
    cur.close()
    plots = []
    for row in plot_rows:
        area = float(row[2]) if row[2] is not None else 0
        species = row[3]
        richness = round(species / area, 2) if area > 0 else None
        plots.append({
            "plot_id": str(row[0]),
            "plot_name": row[1],
            "plot_area_ha": round(area, 4) if row[2] is not None else None,
            "unique_species": species,
            "species_per_hectare": richness,
            "total_observations": row[4],
            "last_observation": str(row[5]) if row[5] else None,
        })
    loc_species = location_row[0] if location_row else 0
    loc_area = float(location_row[2]) if location_row and location_row[2] else 0
    loc_richness = round(loc_species / loc_area, 2) if loc_area > 0 else None
    return {
        "location_id": location_id,
        "plots": plots,
        "location_total_species": loc_species,
        "location_total_area_ha": round(loc_area, 4),
        "location_species_per_hectare": loc_richness,
        "location_total_observations": location_row[1] if location_row else 0,
    }


def compute_rainfall_vs_irrigation(conn, location_id: str) -> dict[str, Any]:
    """Compute rainfall vs irrigation comparison (Q5).

    Formula: rainfall_mm - irrigation_mm_used
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rc.id,
               rc.period_start,
               rc.period_end,
               rc.irrigation_mm_used,
               rc.rainfall_mm_during_period,
               CASE
                   WHEN rc.irrigation_mm_used IS NOT NULL AND rc.rainfall_mm_during_period IS NOT NULL
                   THEN rc.rainfall_mm_during_period - rc.irrigation_mm_used
                   ELSE NULL
               END AS delta_mm,
               CASE
                   WHEN rc.irrigation_mm_used IS NOT NULL AND rc.irrigation_mm_used > 0
                   THEN ROUND((rc.rainfall_mm_during_period / rc.irrigation_mm_used)::numeric, 2)
                   ELSE NULL
               END AS rainfall_to_irrigation_ratio
        FROM resource_consumption rc
        WHERE rc.location_id = %s
          AND rc.status IN ('verified', 'published')
          AND rc.irrigation_mm_used IS NOT NULL
        ORDER BY rc.period_start DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    periods = []
    for row in rows:
        periods.append({
            "id": str(row[0]),
            "period_start": str(row[1]) if row[1] else None,
            "period_end": str(row[2]) if row[2] else None,
            "irrigation_mm_used": float(row[3]) if row[3] is not None else None,
            "rainfall_mm": float(row[4]) if row[4] is not None else None,
            "rainfall_irrigation_delta_mm": float(row[5]) if row[5] is not None else None,
            "rainfall_to_irrigation_ratio": float(row[6]) if row[6] is not None else None,
        })
    total_rainfall = sum(p["rainfall_mm"] or 0 for p in periods)
    total_irrigation = sum(p["irrigation_mm_used"] or 0 for p in periods)
    return {
        "location_id": location_id,
        "periods": periods,
        "total_periods": len(periods),
        "total_rainfall_mm": round(total_rainfall, 2),
        "total_irrigation_mm": round(total_irrigation, 2),
        "net_rainfall_minus_irrigation_mm": round(total_rainfall - total_irrigation, 2),
    }
