"""
Carbon Balance Analytics — GHG Emissions, Tree Carbon, Carbon Balance, Regenerative Scoring

Queries ghg_emissions_inventory, tree_inventory, soil_carbon_measurement,
regenerative_practice_checklist, and climate_impact_summary to produce
carbon balance, emissions breakdown, and regenerative practice reports.
"""

from typing import Dict, Any, List, Optional

import psycopg2
import psycopg2.extras


def compute_ghg_emissions(
    conn,
    location_id: str,
    period_start: str = None,
    period_end: str = None,
) -> Dict[str, Any]:
    """Aggregate GHG emissions by category for a location and period.

    Returns total emissions in tonnes CO2e and per-category breakdown.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
        SELECT
            category,
            COUNT(*) AS record_count,
            COALESCE(SUM(co2e_kg), 0) AS total_co2e_kg,
            COALESCE(SUM(co2e_tonnes), 0) AS total_co2e_tonnes
        FROM ghg_emissions_inventory
        WHERE location_id = %s
          AND status IN ('verified', 'published')
          AND (%s::date IS NULL OR reporting_date >= %s::date)
          AND (%s::date IS NULL OR reporting_date <= %s::date)
        GROUP BY category
        ORDER BY total_co2e_tonnes DESC
    """
    cur.execute(query, (location_id, period_start, period_start, period_end, period_end))
    rows = [dict(r) for r in cur.fetchall()]

    # Total across all categories
    total_kg = sum(float(r["total_co2e_kg"]) for r in rows)
    total_tonnes = sum(float(r["total_co2e_tonnes"]) for r in rows)

    # Detailed breakdown per category
    categories = []
    for row in rows:
        categories.append({
            "category": row["category"],
            "record_count": int(row["record_count"]),
            "total_co2e_kg": round(float(row["total_co2e_kg"]), 4),
            "total_co2e_tonnes": round(float(row["total_co2e_tonnes"]), 6),
        })

    cur.close()

    return {
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "categories": categories,
        "summary": {
            "total_co2e_kg": round(total_kg, 4),
            "total_co2e_tonnes": round(total_tonnes, 6),
            "record_count": sum(r["record_count"] for r in categories),
        },
    }


def compute_tree_carbon(conn, location_id: str) -> Dict[str, Any]:
    """Compute above-ground carbon from tree_inventory using allometric estimates.

    Returns per-species carbon and total above-ground carbon stock.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            species_name,
            COALESCE(SUM(tree_count), 0) AS total_trees,
            COALESCE(SUM(biomass_estimate_kg), 0) AS total_biomass_kg,
            COALESCE(SUM(carbon_estimate_tonnes), 0) AS total_carbon_tonnes,
            COALESCE(SUM(co2e_estimate_tonnes), 0) AS total_co2e_tonnes,
            COUNT(*) AS survey_count
        FROM tree_inventory
        WHERE location_id = %s
          AND status IN ('verified', 'published')
        GROUP BY species_name
        ORDER BY total_co2e_tonnes DESC
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    species = []
    total_trees = 0
    total_carbon = 0.0
    total_co2e = 0.0

    for row in rows:
        trees = int(row["total_trees"])
        carbon = float(row["total_carbon_tonnes"])
        co2e = float(row["total_co2e_tonnes"])
        total_trees += trees
        total_carbon += carbon
        total_co2e += co2e

        species.append({
            "species_name": row["species_name"],
            "total_trees": trees,
            "total_biomass_kg": round(float(row["total_biomass_kg"]), 2),
            "total_carbon_tonnes": round(carbon, 4),
            "total_co2e_tonnes": round(co2e, 4),
            "survey_count": int(row["survey_count"]),
        })

    return {
        "location_id": location_id,
        "species": species,
        "summary": {
            "total_trees": total_trees,
            "total_carbon_tonnes": round(total_carbon, 4),
            "total_co2e_tonnes": round(total_co2e, 4),
            "species_count": len(species),
        },
    }


def compute_carbon_balance(conn, location_id: str, year: int = None) -> Dict[str, Any]:
    """Compute carbon balance: sequestration vs emissions.

    Sources:
    - Above-ground: tree_inventory
    - Below-ground: soil_carbon_measurement delta (or climate_impact_summary)
    - Emissions: ghg_emissions_inventory
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Try climate_impact_summary first (authoritative annual record)
    if year:
        cur.execute("""
            SELECT * FROM climate_impact_summary
            WHERE location_id = %s AND reporting_year = %s
            LIMIT 1
        """, (location_id, year))
        summary_row = cur.fetchone()
    else:
        cur.execute("""
            SELECT * FROM climate_impact_summary
            WHERE location_id = %s
            ORDER BY reporting_year DESC
            LIMIT 1
        """, (location_id,))
        summary_row = cur.fetchone()

    if summary_row:
        summary = dict(summary_row)
        above_ground = float(summary.get("above_ground_carbon_tonnes") or 0)
        below_ground = float(summary.get("below_ground_carbon_tonnes") or 0)
        total_sequestration = float(summary.get("total_sequestration_tonnes_co2e") or 0)
        total_emissions = float(summary.get("total_emissions_tonnes_co2e") or 0)
        net_impact = float(summary.get("net_climate_impact_tonnes_co2e") or 0)
        reporting_year = int(summary.get("reporting_year") or 0)
    else:
        # Fallback: compute from live data
        reporting_year = year or 0

        # Above-ground from tree inventory
        cur.execute("""
            SELECT COALESCE(SUM(co2e_estimate_tonnes), 0) AS total_co2e
            FROM tree_inventory
            WHERE location_id = %s AND status IN ('verified', 'published')
        """, (location_id,))
        tree_row = cur.fetchone()
        above_ground = float(tree_row["total_co2e"]) if tree_row else 0

        # Below-ground from soil carbon delta
        cur.execute("""
            SELECT
                plot_id,
                carbon_tonnes_per_ha,
                measurement_date,
                is_baseline
            FROM soil_carbon_measurement
            WHERE location_id = %s
            ORDER BY measurement_date
        """, (location_id,))
        carbon_rows = [dict(r) for r in cur.fetchall()]

        below_ground = 0.0
        if carbon_rows:
            by_plot: Dict[str, list] = {}
            for cr in carbon_rows:
                pid = str(cr["plot_id"])
                by_plot.setdefault(pid, []).append(cr)
            for pid, measurements in by_plot.items():
                if len(measurements) >= 2:
                    baseline = measurements[0]["carbon_tonnes_per_ha"]
                    latest = measurements[-1]["carbon_tonnes_per_ha"]
                    delta = float(latest) - float(baseline)
                    below_ground += delta * 3.67  # carbon to CO2e

        total_sequestration = above_ground + below_ground

        # Emissions from inventory
        cur.execute("""
            SELECT COALESCE(SUM(co2e_tonnes), 0) AS total_emissions
            FROM ghg_emissions_inventory
            WHERE location_id = %s AND status IN ('verified', 'published')
        """, (location_id,))
        em_row = cur.fetchone()
        total_emissions = float(em_row["total_emissions"]) if em_row else 0

        net_impact = total_sequestration - total_emissions

    cur.close()

    position = "net_sequester" if net_impact > 0 else "net_emitter" if net_impact < 0 else "neutral"

    return {
        "location_id": location_id,
        "reporting_year": reporting_year,
        "above_ground_carbon_tonnes": round(above_ground, 4),
        "below_ground_carbon_tonnes": round(below_ground, 4),
        "total_sequestration_tonnes_co2e": round(total_sequestration, 4),
        "total_emissions_tonnes_co2e": round(total_emissions, 4),
        "net_climate_impact_tonnes_co2e": round(net_impact, 4),
        "carbon_position": position,
    }


def compute_regenerative_score(conn, location_id: str) -> Dict[str, Any]:
    """Compute regenerative practice score from checklist (0-25 across 5 principles).

    Returns per-principle scores, total, and percentage.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            rpc.principle_key,
            rp.name AS principle_name,
            rpc.score,
            rpc.assessment_date,
            rpc.evidence_path,
            rpc.notes
        FROM regenerative_practice_checklist rpc
        JOIN regeneration_principle rp ON rp.principle_key = rpc.principle_key
        WHERE rpc.location_id = %s
          AND rpc.status IN ('verified', 'published')
        ORDER BY rp.sort_order
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    principles = []
    total_score = 0
    max_score = 25  # 5 principles x 5 max each

    for row in rows:
        score = int(row["score"])
        total_score += score
        principles.append({
            "principle_key": row["principle_key"],
            "principle_name": row["principle_name"],
            "score": score,
            "max_score": 5,
            "assessment_date": str(row["assessment_date"]),
            "evidence_path": row.get("evidence_path"),
            "notes": row.get("notes"),
        })

    score_pct = round(total_score * 100.0 / max_score, 1) if max_score > 0 else 0

    return {
        "location_id": location_id,
        "principles": principles,
        "summary": {
            "total_score": total_score,
            "max_score": max_score,
            "score_pct": score_pct,
            "principles_assessed": len(principles),
            "last_assessment_date": principles[-1]["assessment_date"] if principles else None,
        },
    }


def list_emission_factors(conn, category: str = None, region: str = None) -> List[Dict[str, Any]]:
    """List available emission factors, optionally filtered by category and region."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = "SELECT * FROM ghg_emission_factor WHERE 1=1"
    params = []
    if category:
        query += " AND category = %s"
        params.append(category)
    if region:
        query += " AND region = %s"
        params.append(region)
    query += " ORDER BY category, subcategory"

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    return [
        {
            "factor_key": r["factor_key"],
            "category": r["category"],
            "subcategory": r["subcategory"],
            "emission_factor": float(r["emission_factor"]),
            "unit": r["unit"],
            "source": r["source"],
            "region": r["region"],
        }
        for r in rows
    ]


def list_carbon_benchmarks(conn, tree_system: str = None) -> List[Dict[str, Any]]:
    """List carbon benchmarks, optionally filtered by tree system."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = "SELECT * FROM carbon_benchmark WHERE 1=1"
    params = []
    if tree_system:
        query += " AND tree_system = %s"
        params.append(tree_system)
    query += " ORDER BY tree_system, name"

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    return [
        {
            "benchmark_key": r["benchmark_key"],
            "name": r["name"],
            "tree_system": r["tree_system"],
            "above_ground_carbon_tonnes_ha": float(r["above_ground_carbon_tonnes_ha"] or 0),
            "below_ground_carbon_tonnes_ha": float(r["below_ground_carbon_tonnes_ha"] or 0),
            "total_carbon_tonnes_ha": float(r["total_carbon_tonnes_ha"] or 0),
            "sequestration_rate_tonnes_co2e_ha_year": float(r["sequestration_rate_tonnes_co2e_ha_year"] or 0),
            "source": r["source"],
            "region": r["region"],
        }
        for r in rows
    ]
