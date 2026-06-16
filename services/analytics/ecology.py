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
            measurement_method,
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
                "measurement_method": baseline["measurement_method"],
                "depth_cm": baseline["depth_cm"],
            },
            "latest": {
                "date": latest["measurement_date"].isoformat() if hasattr(latest["measurement_date"], "isoformat") else str(latest["measurement_date"]),
                "carbon_tonnes_per_ha": float(latest["carbon_tonnes_per_ha"]),
                "measurement_method": latest["measurement_method"],
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
            species_name,
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

    # Aggregate species counts across all observations for Shannon index
    species_totals: Dict[str, int] = {}
    for row in rows:
        species_name = row.get("species_name") or ""
        count = row.get("count", 0) or 0
        if species_name and count > 0:
            species_totals[species_name] = species_totals.get(species_name, 0) + count

    # Calculate Shannon diversity index: H = -sum(p_i * ln(p_i))
    shannon_index = 0.0
    total_individuals = sum(species_totals.values())
    if total_individuals > 0:
        for sp_count in species_totals.values():
            if sp_count > 0:
                p = sp_count / total_individuals
                shannon_index -= p * math.log(p)

    observations = []
    for row in rows:
        species_name = row.get("species_name") or ""
        count = row.get("count", 0) or 0

        observations.append({
            "observation_date": row["observation_date"].isoformat() if hasattr(row["observation_date"], "isoformat") else str(row["observation_date"]),
            "plot_id": str(row["plot_id"]) if row.get("plot_id") else None,
            "species_count": count,
            "unique_species": len(species_totals),
            "shannon_index": round(shannon_index, 4),
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
    from services.forecast.pricing import project_prices
    from services.forecast.yield_forecast import project_yields
    from services.forecast.cost_forecast import project_costs

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


def ndvi_trends(conn, location_id: str) -> Dict[str, Any]:
    """Query remote_sensing_observation for NDVI over time per plot.

    Computes per-plot trajectory and overall summary.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            plot_id,
            p.name as plot_name,
            observation_date,
            ndvi,
            ndwi
        FROM remote_sensing_observation rs
        LEFT JOIN plot p ON rs.plot_id = p.id
        WHERE rs.location_id = %s AND rs.ndvi IS NOT NULL
        ORDER BY rs.plot_id, rs.observation_date
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not rows:
        return {"location_id": location_id, "plots": [], "summary": None}

    by_plot: Dict[str, list] = {}
    for row in rows:
        pid = str(row["plot_id"])
        by_plot.setdefault(pid, []).append(row)

    plots = []
    ndvi_changes = []

    for pid, observations in by_plot.items():
        first = observations[0]
        last = observations[-1]
        first_ndvi = float(first["ndvi"])
        last_ndvi = float(last["ndvi"])
        delta = last_ndvi - first_ndvi

        # Compute months spanned
        first_date = first["observation_date"]
        last_date = last["observation_date"]
        if hasattr(first_date, "isoformat"):
            first_dt = first_date
        else:
            first_dt = datetime.strptime(str(first_date), "%Y-%m-%d")
        if hasattr(last_date, "isoformat"):
            last_dt = last_date
        else:
            last_dt = datetime.strptime(str(last_date), "%Y-%m-%d")
        months = max((last_dt - first_dt).days / 30.44, 1.0)
        rate_per_month = delta / months

        if rate_per_month > 0.01:
            trend = "increasing"
        elif rate_per_month < -0.01:
            trend = "decreasing"
        else:
            trend = "stable"

        ndvi_changes.append((pid, delta))
        plots.append({
            "plot_id": pid,
            "plot_name": first.get("plot_name"),
            "first_ndvi": round(first_ndvi, 4),
            "last_ndvi": round(last_ndvi, 4),
            "delta": round(delta, 4),
            "rate_per_month": round(rate_per_month, 4),
            "trend": trend,
            "observations_count": len(observations),
        })

    avg_delta = sum(d for _, d in ndvi_changes) / len(ndvi_changes) if ndvi_changes else 0.0
    best_plot = max(ndvi_changes, key=lambda x: x[1]) if ndvi_changes else None
    worst_plot = min(ndvi_changes, key=lambda x: x[1]) if ndvi_changes else None

    if avg_delta > 0.01:
        overall_trend = "increasing"
    elif avg_delta < -0.01:
        overall_trend = "decreasing"
    else:
        overall_trend = "stable"

    return {
        "location_id": location_id,
        "plots": plots,
        "summary": {
            "avg_ndvi_change": round(avg_delta, 4),
            "trend_direction": overall_trend,
            "best_plot": best_plot[0] if best_plot else None,
            "worst_plot": worst_plot[0] if worst_plot else None,
        },
    }


def water_resilience(conn, location_id: str) -> Dict[str, Any]:
    """Aggregate water-related data to compute a water stress resilience index."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Rainfall from weather_observation
    cur.execute("""
        SELECT
            EXTRACT(MONTH FROM observation_date) as month,
            precipitation_mm
        FROM weather_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """, (location_id,))
    weather_rows = [dict(r) for r in cur.fetchall()]

    total_rainfall = sum(float(r["precipitation_mm"] or 0) for r in weather_rows)
    drought_months = sum(1 for r in weather_rows if float(r.get("precipitation_mm") or 0) < 50)
    total_months = max(len(weather_rows), 1)
    rainfall_distribution = round(1.0 - (drought_months / total_months), 4) if total_months else 0.0

    # Soil moisture from sensor_reading
    cur.execute("""
        SELECT AVG(value) as avg_moisture
        FROM sensor_reading
        WHERE location_id = %s AND sensor_type = 'soil_moisture'
    """, (location_id,))
    sm_row = cur.fetchone()
    avg_soil_moisture = float(sm_row["avg_moisture"] or 0) if sm_row and sm_row["avg_moisture"] else 0.0

    # Infrastructure: tanks, pumps, reservoirs
    cur.execute("""
        SELECT asset_type, condition_status
        FROM infrastructure_asset
        WHERE location_id = %s
          AND asset_type IN ('tank', 'pump', 'reservoir')
    """, (location_id,))
    infra_rows = [dict(r) for r in cur.fetchall()]
    infra_count = len(infra_rows)
    infra_conditions = [r.get("condition_rating") for r in infra_rows if r.get("condition_rating")]

    # NDWI trend from remote_sensing_observation
    cur.execute("""
        SELECT
            observation_date,
            ndwi
        FROM remote_sensing_observation
        WHERE location_id = %s AND ndwi IS NOT NULL
        ORDER BY observation_date
    """, (location_id,))
    ndwi_rows = [dict(r) for r in cur.fetchall()]
    ndwi_trend = None
    if len(ndwi_rows) >= 2:
        first_ndwi = float(ndwi_rows[0]["ndwi"])
        last_ndwi = float(ndwi_rows[-1]["ndwi"])
        ndwi_trend = round(last_ndwi - first_ndwi, 4)

    cur.close()

    # Water stress index (0-100, higher = more resilient)
    # Components: rainfall adequacy (0-30), soil moisture (0-30), infrastructure (0-20), ndwi (0-20)
    rainfall_score = min(30.0, (total_rainfall / 1500.0) * 30.0) if total_rainfall > 0 else 0.0
    moisture_score = min(30.0, (avg_soil_moisture / 100.0) * 30.0) if avg_soil_moisture > 0 else 0.0
    infra_score = min(20.0, (infra_count / 5.0) * 20.0)
    ndwi_score = 10.0
    if ndwi_trend is not None:
        ndwi_score = max(0.0, min(20.0, 10.0 + ndwi_trend * 20.0))

    water_stress_index = round(rainfall_score + moisture_score + infra_score + ndwi_score, 2)

    return {
        "location_id": location_id,
        "water_stress_index": water_stress_index,
        "rainfall_summary": {
            "total_mm": round(total_rainfall, 2),
            "drought_months": drought_months,
            "distribution_score": rainfall_distribution,
        },
        "soil_moisture": {
            "avg_moisture": round(avg_soil_moisture, 4),
        },
        "infrastructure": {
            "count": infra_count,
            "conditions": infra_conditions,
        },
        "ndwi_trend": ndwi_trend,
    }


def crop_diversity(conn, location_id: str) -> Dict[str, Any]:
    """Compute crop diversity using Shannon index from crop_cycle joined with crop."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            cc.plot_id,
            p.name as plot_name,
            cc.season,
            c.name as crop_name
        FROM crop_cycle cc
        LEFT JOIN crop c ON cc.crop_id = c.id
        LEFT JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s
        ORDER BY cc.season, cc.plot_id
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not rows:
        return {"location_id": location_id, "per_plot": [], "summary": None}

    # Group by plot, then by season
    plot_seasons: Dict[str, Dict[str, List[str]]] = {}
    for row in rows:
        pid = str(row["plot_id"])
        season = str(row.get("season", "unknown"))
        crop = row.get("crop_name") or "unknown"
        plot_seasons.setdefault(pid, {}).setdefault(season, []).append(crop)

    def shannon_index(species_list: List[str]) -> float:
        totals: Dict[str, int] = {}
        for sp in species_list:
            totals[sp] = totals.get(sp, 0) + 1
        total = sum(totals.values())
        if total == 0:
            return 0.0
        h = 0.0
        for count in totals.values():
            p = count / total
            if p > 0:
                h -= p * math.log(p)
        return h

    per_plot = []
    all_crops: List[str] = []
    baseline_shannon_values = []
    latest_shannon_values = []

    for pid, seasons in plot_seasons.items():
        sorted_seasons = sorted(seasons.keys())
        first_season = sorted_seasons[0]
        last_season = sorted_seasons[-1]

        first_crops = seasons[first_season]
        last_crops = seasons[last_season]

        first_shannon = shannon_index(first_crops)
        last_shannon = shannon_index(last_crops)

        all_crops.extend(last_crops)
        baseline_shannon_values.append(first_shannon)
        latest_shannon_values.append(last_shannon)

        plot_name = None
        for row in rows:
            if str(row["plot_id"]) == pid:
                plot_name = row.get("plot_name")
                break

        per_plot.append({
            "plot_id": pid,
            "plot_name": plot_name,
            "baseline_season": first_season,
            "baseline_shannon": round(first_shannon, 4),
            "latest_season": last_season,
            "latest_shannon": round(last_shannon, 4),
            "delta": round(last_shannon - first_shannon, 4),
            "species_richness": len(set(last_crops)),
        })

    overall_shannon = shannon_index(all_crops) if all_crops else 0.0
    baseline_shannon = (sum(baseline_shannon_values) / len(baseline_shannon_values)) if baseline_shannon_values else 0.0

    return {
        "location_id": location_id,
        "per_plot": per_plot,
        "summary": {
            "overall_shannon": round(overall_shannon, 4),
            "baseline_shannon": round(baseline_shannon, 4),
            "delta": round(overall_shannon - baseline_shannon, 4),
            "total_species_richness": len(set(all_crops)),
        },
    }


def intervention_impact(conn, location_id: str) -> Dict[str, Any]:
    """Analyze intervention impact from farm_activity records."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            activity_type,
            COUNT(*) as intervention_count,
            COALESCE(SUM(labor_hours), 0) as total_hours,
            COALESCE(SUM(labor_cost), 0) as total_cost
        FROM farm_activity
        WHERE location_id = %s
          AND activity_type IN ('irrigation', 'planting', 'spraying')
        GROUP BY activity_type
        ORDER BY activity_type
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    interventions = []
    total_interventions = 0
    total_cost = 0.0

    for row in rows:
        count = int(row["intervention_count"])
        hours = float(row["total_hours"])
        cost = float(row["total_cost"])
        total_interventions += count
        total_cost += cost

        interventions.append({
            "type": row["activity_type"],
            "count": count,
            "total_hours": round(hours, 2),
            "total_cost": round(cost, 2),
        })

    return {
        "location_id": location_id,
        "interventions": interventions,
        "total_interventions": total_interventions,
        "total_cost": round(total_cost, 2),
    }


def soil_health(conn, location_id: str) -> Dict[str, Any]:
    """Analyze soil health from soil_sample data.

    Computes per-plot averages for pH, organic matter, NPK, and CEC.
    Compares baseline vs latest observations and produces a health score (0-100).
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Latest soil samples per plot
    cur.execute("""
        SELECT
            p.name as plot_name,
            ss.ph,
            ss.organic_matter_pct,
            ss.nitrogen_ppm,
            ss.phosphorus_ppm,
            ss.potassium_ppm,
            ss.cec,
            ss.texture,
            ss.sample_date
        FROM soil_sample ss
        JOIN plot p ON ss.plot_id = p.id
        WHERE ss.location_id = %s
        ORDER BY ss.sample_date DESC
    """, (location_id,))
    latest = [dict(r) for r in cur.fetchall()]

    # Baseline soil samples (earliest per plot)
    cur.execute("""
        SELECT
            p.name as plot_name,
            ss.ph,
            ss.organic_matter_pct,
            ss.nitrogen_ppm,
            ss.phosphorus_ppm,
            ss.potassium_ppm,
            ss.sample_date
        FROM soil_sample ss
        JOIN plot p ON ss.plot_id = p.id
        WHERE ss.location_id = %s
        ORDER BY ss.sample_date ASC
    """, (location_id,))
    baseline = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not latest:
        return {"location_id": location_id, "plots": [], "health_score": 0, "summary": "No soil samples found"}

    # Per-plot latest values
    plots = {}
    for row in latest:
        name = row["plot_name"]
        if name not in plots:
            plots[name] = {
                "ph": float(row["ph"] or 0),
                "organic_matter_pct": float(row["organic_matter_pct"] or 0),
                "nitrogen_ppm": float(row["nitrogen_ppm"] or 0),
                "phosphorus_ppm": float(row["phosphorus_ppm"] or 0),
                "potassium_ppm": float(row["potassium_ppm"] or 0),
                "cec": float(row["cec"] or 0),
                "texture": row["texture"],
                "sample_date": str(row["sample_date"]),
            }

    # Baseline per-plot (earliest)
    baseline_plots = {}
    for row in baseline:
        name = row["plot_name"]
        if name not in baseline_plots:
            baseline_plots[name] = {
                "ph": float(row["ph"] or 0),
                "organic_matter_pct": float(row["organic_matter_pct"] or 0),
                "nitrogen_ppm": float(row["nitrogen_ppm"] or 0),
                "phosphorus_ppm": float(row["phosphorus_ppm"] or 0),
                "potassium_ppm": float(row["potassium_ppm"] or 0),
                "sample_date": str(row["sample_date"]),
            }

    # Health score: weighted composite
    # pH optimal: 6.0-7.0 (score 100 if in range, linear falloff)
    # OM optimal: >3% (score 100 if >=3, linear falloff)
    # N optimal: >20ppm, P optimal: >15ppm, K optimal: >150ppm
    plot_scores = {}
    for name, vals in plots.items():
        ph = vals["ph"]
        om = vals["organic_matter_pct"]
        n = vals["nitrogen_ppm"]
        p = vals["phosphorus_ppm"]
        k = vals["potassium_ppm"]

        # pH score (optimal 6.0-7.0)
        if 6.0 <= ph <= 7.0:
            ph_score = 100
        elif ph < 6.0:
            ph_score = max(0, (ph / 6.0) * 100)
        else:
            ph_score = max(0, ((14 - ph) / 7.0) * 100)

        # Organic matter score (optimal >=3%)
        om_score = min(100, (om / 3.0) * 100)

        # NPK scores
        n_score = min(100, (n / 20.0) * 100)
        p_score = min(100, (p / 15.0) * 100)
        k_score = min(100, (k / 150.0) * 100)

        # Weighted: pH 20%, OM 30%, N 20%, P 15%, K 15%
        health = (ph_score * 0.20 + om_score * 0.30 + n_score * 0.20 +
                  p_score * 0.15 + k_score * 0.15)
        plot_scores[name] = round(health, 1)

    overall_score = round(sum(plot_scores.values()) / max(len(plot_scores), 1), 1)

    # Build per-plot results with deltas
    plot_results = []
    for name, vals in plots.items():
        base = baseline_plots.get(name, {})
        result = {
            "plot_name": name,
            "health_score": plot_scores.get(name, 0),
            "current": vals,
        }
        if base:
            result["baseline"] = base
            result["delta"] = {
                "ph": round(vals["ph"] - base["ph"], 2),
                "organic_matter_pct": round(vals["organic_matter_pct"] - base["organic_matter_pct"], 3),
                "nitrogen_ppm": round(vals["nitrogen_ppm"] - base["nitrogen_ppm"], 3),
                "phosphorus_ppm": round(vals["phosphorus_ppm"] - base["phosphorus_ppm"], 3),
                "potassium_ppm": round(vals["potassium_ppm"] - base["potassium_ppm"], 3),
            }
        plot_results.append(result)

    return {
        "location_id": location_id,
        "plots": plot_results,
        "health_score": overall_score,
        "plot_count": len(plot_results),
        "summary": f"{len(plot_results)} plots, overall health score: {overall_score}/100",
    }


def water_access_summary(conn, location_id: str) -> Dict[str, Any]:
    """Summarize water access infrastructure from the water_access table.

    Computes source types, reliability/quality averages, total monthly cost,
    and an accessibility score (0-100).
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            source_type,
            source_name,
            reliability_score,
            quality_score,
            distance_km,
            monthly_cost_usd,
            capacity_liters,
            status
        FROM water_access
        WHERE location_id = %s
        ORDER BY reliability_score DESC
    """, (location_id,))
    sources = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not sources:
        return {
            "location_id": location_id,
            "sources": [],
            "source_count": 0,
            "accessibility_score": 0,
            "summary": "No water access records found",
        }

    # Per-source details
    source_details = []
    for s in sources:
        reliability = float(s["reliability_score"] or 0)
        quality = float(s["quality_score"] or 0)
        distance = float(s["distance_km"] or 0)
        cost = float(s["monthly_cost_usd"] or 0)
        capacity = float(s["capacity_liters"] or 0)

        # Accessibility score: reliability 40%, quality 30%, distance 20%, capacity 10%
        dist_score = max(0, 100 - (distance * 10))  # 0km=100, 10km=0
        cap_score = min(100, (capacity / 10000) * 100)  # 10k liters = 100
        accessibility = (reliability * 0.40 + quality * 0.30 +
                         dist_score * 0.20 + cap_score * 0.10)

        source_details.append({
            "source_type": s["source_type"],
            "source_name": s["source_name"],
            "reliability_score": reliability,
            "quality_score": quality,
            "distance_km": distance,
            "monthly_cost_usd": cost,
            "capacity_liters": capacity,
            "status": s["status"],
            "accessibility_score": round(accessibility, 1),
        })

    # Aggregate metrics
    total_monthly_cost = sum(s["monthly_cost_usd"] for s in source_details)
    avg_reliability = sum(s["reliability_score"] for s in source_details) / len(source_details)
    avg_quality = sum(s["quality_score"] for s in source_details) / len(source_details)
    active_sources = [s for s in source_details if s["status"] == "active"]
    overall_score = round(sum(s["accessibility_score"] for s in source_details) / len(source_details), 1)

    return {
        "location_id": location_id,
        "sources": source_details,
        "source_count": len(source_details),
        "active_source_count": len(active_sources),
        "avg_reliability": round(avg_reliability, 1),
        "avg_quality": round(avg_quality, 1),
        "total_monthly_cost_usd": round(total_monthly_cost, 2),
        "accessibility_score": overall_score,
        "summary": f"{len(source_details)} sources ({len(active_sources)} active), score: {overall_score}/100, ${total_monthly_cost:.0f}/month",
    }


def environmental_baseline(conn, location_id: str) -> Dict[str, Any]:
    """Retrieve and summarize environmental baselines from the environmental_baseline table.

    Shows current baseline values and compares to latest measurements where available.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get baselines
    cur.execute("""
        SELECT metric_name, metric_value, unit, measurement_date, source
        FROM environmental_baseline
        WHERE location_id = %s
        ORDER BY metric_name
    """, (location_id,))
    baselines = [dict(r) for r in cur.fetchall()]

    # Get latest soil carbon for comparison
    cur.execute("""
        SELECT AVG(carbon_tonnes_per_ha) as latest_carbon
        FROM soil_carbon_measurement
        WHERE location_id = %s
    """, (location_id,))
    carbon_row = cur.fetchone()
    latest_carbon = float(dict(carbon_row)["latest_carbon"] or 0) if carbon_row else 0

    # Get latest species count for comparison
    cur.execute("""
        SELECT COUNT(DISTINCT species_name) as latest_species
        FROM species_observation
        WHERE location_id = %s
    """, (location_id,))
    species_row = cur.fetchone()
    latest_species = int(dict(species_row)["latest_species"] or 0) if species_row else 0

    # Get latest NDVI for comparison
    cur.execute("""
        SELECT AVG(ndvi) as latest_ndvi
        FROM remote_sensing_observation
        WHERE location_id = %s
    """, (location_id,))
    ndvi_row = cur.fetchone()
    latest_ndvi = float(dict(ndvi_row)["latest_ndvi"] or 0) if ndvi_row else 0

    cur.close()

    # Build baseline map
    baseline_map = {}
    for b in baselines:
        baseline_map[b["metric_name"]] = {
            "value": float(b["metric_value"] or 0),
            "unit": b["unit"],
            "date": str(b["measurement_date"]),
            "source": b["source"],
        }

    # Compare baselines to latest
    comparisons = {}
    if "soil_carbon_tonnes_per_ha" in baseline_map:
        base_val = baseline_map["soil_carbon_tonnes_per_ha"]["value"]
        comparisons["soil_carbon"] = {
            "baseline": base_val,
            "latest": latest_carbon,
            "delta": round(latest_carbon - base_val, 2),
            "pct_change": round(((latest_carbon - base_val) / base_val * 100) if base_val > 0 else 0, 1),
        }
    if "species_count" in baseline_map:
        base_val = baseline_map["species_count"]["value"]
        comparisons["species_count"] = {
            "baseline": base_val,
            "latest": latest_species,
            "delta": latest_species - int(base_val),
        }
    if "ndvi_avg" in baseline_map:
        base_val = baseline_map["ndvi_avg"]["value"]
        comparisons["ndvi_avg"] = {
            "baseline": base_val,
            "latest": round(latest_ndvi, 4),
            "delta": round(latest_ndvi - base_val, 4),
        }

    return {
        "location_id": location_id,
        "baselines": baseline_map,
        "comparisons": comparisons,
        "baseline_count": len(baselines),
        "summary": f"{len(baselines)} baselines tracked, {len(comparisons)} with latest comparison",
    }
