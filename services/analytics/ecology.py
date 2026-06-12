"""
Ecology Analytics — Soil Carbon Comparison, Biodiversity Index, Impact Metrics

Queries soil_carbon_measurement and species_observation tables to produce
before/after comparisons and ecological health indicators.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import psycopg2
import psycopg2.extras


def compare_soil_carbon(conn, location_id: str) -> Dict[str, Any]:
    """Compare soil carbon before vs after intervention.

    Uses baseline (earliest) vs latest measurements per plot.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            plot_id,
            p.name as plot_name,
            measurement_date,
            carbon_tonnes_per_ha,
            methodology,
            depth_cm
        FROM soil_carbon_measurement sc
        LEFT JOIN plot p ON sc.plot_id = p.id
        WHERE sc.location_id = %s
        ORDER BY sc.plot_id, sc.measurement_date
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not rows:
        return {"location_id": location_id, "plots": [], "summary": None}

    # Group by plot
    by_plot: Dict[str, list] = {}
    for row in rows:
        pid = str(row["plot_id"])
        by_plot.setdefault(pid, []).append(row)

    plots = []
    total_baseline = 0.0
    total_latest = 0.0
    total_delta = 0.0
    count = 0

    for pid, measurements in by_plot.items():
        baseline = measurements[0]
        latest = measurements[-1]
        delta = latest["carbon_tonnes_per_ha"] - baseline["carbon_tonnes_per_ha"]
        pct_change = (delta / baseline["carbon_tonnes_per_ha"] * 100) if baseline["carbon_tonnes_per_ha"] else 0

        plots.append({
            "plot_id": pid,
            "plot_name": baseline.get("plot_name"),
            "baseline": {
                "date": baseline["measurement_date"].isoformat() if hasattr(baseline["measurement_date"], "isoformat") else str(baseline["measurement_date"]),
                "carbon_tonnes_per_ha": float(baseline["carbon_tonnes_per_ha"]),
                "methodology": baseline["methodology"],
                "depth_cm": baseline["depth_cm"],
            },
            "latest": {
                "date": latest["measurement_date"].isoformat() if hasattr(latest["measurement_date"], "isoformat") else str(latest["measurement_date"]),
                "carbon_tonnes_per_ha": float(latest["carbon_tonnes_per_ha"]),
                "methodology": latest["methodology"],
                "depth_cm": latest["depth_cm"],
            },
            "delta_tonnes_per_ha": round(delta, 4),
            "pct_change": round(pct_change, 2),
        })
        total_baseline += float(baseline["carbon_tonnes_per_ha"])
        total_latest += float(latest["carbon_tonnes_per_ha"])
        total_delta += delta
        count += 1

    overall_pct = (total_delta / total_baseline * 100) if total_baseline else 0

    return {
        "location_id": location_id,
        "plots": plots,
        "summary": {
            "plots_measured": count,
            "total_baseline_tonnes_per_ha": round(total_baseline, 4),
            "total_latest_tonnes_per_ha": round(total_latest, 4),
            "total_delta_tonnes_per_ha": round(total_delta, 4),
            "overall_pct_change": round(overall_pct, 2),
        },
    }


def compute_biodiversity(conn, location_id: str) -> Dict[str, Any]:
    """Compute biodiversity metrics from species observations.

    Returns species count and Shannon diversity index per observation date.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            observation_date,
            plot_id,
            species_list,
            count,
            habitat_type,
            notes
        FROM species_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not rows:
        return {"location_id": location_id, "observations": [], "summary": None}

    observations = []
    for row in rows:
        species_list = row.get("species_list") or []
        count = row.get("count", 0) or 0

        # Shannon diversity index: H = -sum(p_i * ln(p_i))
        shannon = 0.0
        if species_list and count > 0:
            # Count individuals per species
            sp_counts: Dict[str, int] = {}
            for sp in species_list:
                sp_counts[sp] = sp_counts.get(sp, 0) + 1
            total = sum(sp_counts.values())
            if total > 0:
                for sp_count in sp_counts.values():
                    if sp_count > 0:
                        p = sp_count / total
                        shannon -= p * math.log(p)

        observations.append({
            "observation_date": row["observation_date"].isoformat() if hasattr(row["observation_date"], "isoformat") else str(row["observation_date"]),
            "plot_id": str(row["plot_id"]) if row.get("plot_id") else None,
            "species_count": count,
            "unique_species": len(species_list) if species_list else 0,
            "shannon_index": round(shannon, 4),
            "habitat_type": row.get("habitat_type"),
        })

    # Summary: compare earliest vs latest
    earliest = observations[0]
    latest = observations[-1]

    return {
        "location_id": location_id,
        "observations": observations,
        "summary": {
            "total_observations": len(observations),
            "earliest": earliest,
            "latest": latest,
            "species_count_delta": latest["species_count"] - earliest["species_count"],
            "shannon_index_delta": round(latest["shannon_index"] - earliest["shannon_index"], 4),
        },
    }


def compare_scenarios(scenario_ids: List[str]) -> Dict[str, Any]:
    """Compare forecast outputs side-by-side for multiple scenarios."""
    from ..ingestion.base import get_db

    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        scenarios = []
        all_metrics = set()
        for sid in scenario_ids:
            cur.execute("SELECT id, name, scenario_type, status FROM forecast_scenario WHERE id = %s", (sid,))
            sc = dict(cur.fetchone()) if cur.rowcount else None
            if not sc:
                continue

            cur.execute("""
                SELECT metric_name, value, unit, confidence_low, confidence_high
                FROM forecast_output WHERE scenario_id = %s ORDER BY metric_name
            """, (sid,))
            outputs = [dict(r) for r in cur.fetchall()]

            by_metric = {}
            for o in outputs:
                by_metric[o["metric_name"]] = o
                all_metrics.add(o["metric_name"])

            sc["outputs"] = by_metric
            scenarios.append(sc)
    db.close()

    comparison = []
    for metric in sorted(all_metrics):
        row = {"metric": metric}
        for sc in scenarios:
            key = sc["name"]
            o = sc["outputs"].get(metric, {})
            row[key] = {
                "value": o.get("value"),
                "unit": o.get("unit"),
                "confidence_low": o.get("confidence_low"),
                "confidence_high": o.get("confidence_high"),
            }
        comparison.append(row)

    return {
        "scenarios": [{"id": s["id"], "name": s["name"], "type": s["scenario_type"]} for s in scenarios],
        "metrics": comparison,
    }


def sensitivity_analysis(
    scenario_id: str,
    variable: str,
    range_pct: float = 20.0,
    steps: int = 5,
) -> Dict[str, Any]:
    """Run sensitivity analysis by varying one scenario variable.

    Supported variables: price, yield, cost
    """
    from ..forecast.engine import load_scenario, run_forecast
    from ..ingestion.base import get_db
    import copy

    scenario = load_scenario(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")

    results = []
    for i in range(steps + 1):
        factor = 1.0 + (range_pct / 100) * (i / steps - 0.5)
        modified = copy.deepcopy(scenario)

        if variable == "price":
            pa = modified.get("price_assumptions", {})
            for crop in pa:
                if isinstance(pa[crop], dict):
                    pa[crop]["price_per_tonne"] = pa[crop].get("price_per_tonne", 0) * factor
            modified["price_assumptions"] = pa
        elif variable == "yield":
            ya = modified.get("yield_assumptions", {})
            for crop in ya:
                if isinstance(ya[crop], dict):
                    ya[crop]["yield_tonnes_per_ha"] = ya[crop].get("yield_tonnes_per_ha", 0) * factor
            modified["yield_assumptions"] = ya
        elif variable == "cost":
            ca = modified.get("cost_assumptions", {})
            for key in ca:
                if isinstance(ca[key], (int, float)):
                    ca[key] = ca[key] * factor
            modified["cost_assumptions"] = ca

        # Calculate NOI delta without writing to DB
        noi_estimate = _estimate_noi(modified)
        results.append({
            "variable_value": round(factor * 100, 1),
            "factor": round(factor, 4),
            "estimated_noi": round(noi_estimate, 2),
        })

    return {
        "scenario_id": scenario_id,
        "variable": variable,
        "range_pct": range_pct,
        "steps": steps,
        "results": results,
    }


def _estimate_noi(scenario: Dict[str, Any]) -> float:
    """Quick NOI estimate without DB writes."""
    from .forecast.pricing import project_prices
    from .forecast.yield_forecast import project_yields
    from .forecast.cost_forecast import project_costs

    # Simplified calculation
    pa = scenario.get("price_assumptions", {})
    ya = scenario.get("yield_assumptions", {})
    ga = scenario.get("growth_assumptions", {})

    # Estimate total revenue and costs
    total_revenue = 0.0
    for crop, data in pa.items():
        if isinstance(data, dict):
            price = data.get("price_per_tonne", 0)
        else:
            price = float(data) if data else 0
        # Rough yield estimate
        yld_data = ya.get(crop, {})
        if isinstance(yld_data, dict):
            yld = yld_data.get("yield_tonnes_per_ha", 0) * 5  # rough area
        else:
            yld = float(yld_data) * 5 if yld_data else 0
        total_revenue += price * yld

    # Rough cost estimate (assume 60% of revenue)
    total_costs = total_revenue * 0.6

    return total_revenue - total_costs
