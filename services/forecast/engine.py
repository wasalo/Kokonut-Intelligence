"""
Forecast Engine

Main orchestrator that reads scenario assumptions, pulls historical
data, calculates forecasts, and writes results to the database.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import psycopg2
import psycopg2.extras

from ..ingestion.base import get_db
from .config import CALCULATION_VERSION, CONFIDENCE_LEVEL
from .models import (
    PriceAssumptions, YieldAssumptions, CostAssumptions,
    GrowthAssumptions, ScenarioAssumptions,
)
from .pricing import get_historical_avg_prices, project_prices
from .yield_forecast import (
    get_crop_areas_for_location, project_yields, calculate_total_yield,
    get_historical_loss_rate, apply_loss_adjustment,
    get_bed_areas_for_location, project_yields_per_sqm,
)
from .cost_forecast import get_historical_costs, project_costs, allocate_shared_costs
from .ecology import (
    get_ecological_baseline, project_ecological_score,
    estimate_carbon_sequestration, estimate_biodiversity_value,
)
from .risk import (
    calculate_risk_factor, risk_adjust_noi, risk_adjust_revenue,
    calculate_confidence_interval,
)


def load_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Load a scenario from the database."""
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM forecast_scenario WHERE id = %s", (scenario_id,))
        row = cur.fetchone()
    db.close()
    return dict(row) if row else None


def load_scenario_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Load a scenario by name."""
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM forecast_scenario WHERE name = %s", (name,))
        row = cur.fetchone()
    db.close()
    return dict(row) if row else None


def run_forecast(scenario_id: str) -> Dict[str, Any]:
    """Run full forecast calculation for a scenario."""
    scenario = load_scenario(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")

    location_id = scenario["location_id"]
    scenario_type = scenario.get("scenario_type", "baseline")

    # Parse assumptions
    sa = ScenarioAssumptions.from_dict(scenario.get("assumptions", {}))
    pa = PriceAssumptions.from_dict(scenario.get("price_assumptions", {}))
    ya = YieldAssumptions.from_dict(scenario.get("yield_assumptions", {}))
    ca = CostAssumptions.from_dict(scenario.get("cost_assumptions", {}))
    ga = GrowthAssumptions.from_dict(scenario.get("growth_assumptions", {}))

    # Get historical data
    hist_prices = get_historical_avg_prices(12, location_id=location_id)
    crop_areas = get_crop_areas_for_location(location_id)
    hist_costs = get_historical_costs(location_id)
    eco_baseline = get_ecological_baseline(location_id)

    # Calculate projections
    projected_prices = project_prices(hist_prices, pa, ga.price_appreciation_pct)
    projected_yields = project_yields(crop_areas, ya, ga)
    total_area = sum(v["area_ha"] for v in projected_yields.values())

    # Apply loss adjustment using historical loss rate
    historical_loss_rate = get_historical_loss_rate(location_id)
    projected_yields = apply_loss_adjustment(projected_yields, historical_loss_rate)

    # Per-square-meter path: if bed data exists, compute per-m² metrics
    bed_data = get_bed_areas_for_location(location_id)
    per_sqm_data = None
    total_bed_area_sqm = 0.0
    production_per_sqm = 0.0
    revenue_per_sqm_usd = 0.0

    if bed_data["has_bed_data"] and crop_areas:
        # Get planting density from first crop_cycle (per-m² path)
        db_density = get_db()
        with db_density.cursor() as cur:
            cur.execute("""
                SELECT cc.planting_density, cc.planting_density_unit, c.name
                FROM crop_cycle cc
                JOIN crop c ON cc.crop_id = c.id
                WHERE cc.location_id = %s AND cc.status = 'completed'
                  AND cc.planting_density IS NOT NULL AND cc.planting_density > 0
                LIMIT 1
            """, (location_id,))
            density_row = cur.fetchone()
        db_density.close()

        if density_row:
            planting_density = float(density_row[0])
            density_unit = density_row[1] or "plants_per_sqm"

            # Convert if needed (plants_per_ha → plants_per_sqm)
            if "ha" in str(density_unit).lower():
                planting_density = planting_density / 10000

            # Use average bed dimensions across plots
            avg_bed_area = sum(
                p["bed_area_sqm"] for p in bed_data["plots"].values()
            ) / max(bed_data["plot_count"], 1)
            avg_bed_count = sum(
                p["bed_count"] for p in bed_data["plots"].values()
            ) / max(bed_data["plot_count"], 1)

            # Get yield per ha for the first crop
            first_crop = list(projected_yields.values())[0] if projected_yields else {}
            yield_per_ha = first_crop.get("yield_per_ha", 0)

            per_sqm_data = project_yields_per_sqm(
                planting_density_per_sqm=planting_density,
                bed_area_sqm=avg_bed_area,
                bed_count=int(avg_bed_count),
                plot_count=bed_data["plot_count"],
                loss_rate=historical_loss_rate,
                yield_per_ha=yield_per_ha,
            )
            total_bed_area_sqm = per_sqm_data["total_bed_area_sqm"]
            production_per_sqm = per_sqm_data["yield_per_sqm"]

            # Revenue per m² (will be computed after total_revenue is known)
            # Store for later; placeholder now
            per_sqm_data["_total_revenue"] = 0  # computed below

    projected_costs = project_costs(hist_costs, ca, ga, total_area)
    shared_alloc = allocate_shared_costs(projected_costs["total_shared"], projected_yields)
    eco_proj = project_ecological_score(eco_baseline)

    # Carbon sequestration estimate
    som_change_pct = eco_proj.get("som_projected", 3.0) - eco_baseline.get("soil_organic_matter_pct", 3.0)
    carbon_tonnes = estimate_carbon_sequestration(total_area, abs(som_change_pct))
    from ..revenue_multiplier.config import get_config
    carbon_price_per_tonne = float(get_config(key="carbon_credit_price_usd"))
    carbon_credit_value = carbon_tonnes * carbon_price_per_tonne

    # Biodiversity credit value estimate
    _db = get_db()
    bio_value = estimate_biodiversity_value(_db, location_id)
    biodiversity_credit_value = bio_value["total_value_usd"]
    _db.close()

    # Retained value projection
    retention_rate = _get_retention_rate(sa, location_id)
    retained_value = total_noi * (retention_rate / 100)

    # Revenue per crop
    revenue_by_crop = {}
    total_revenue = 0.0
    for crop_name, yld in projected_yields.items():
        price = projected_prices.get(crop_name, 0)
        rev = yld["total_yield_tonnes"] * price
        revenue_by_crop[crop_name] = round(rev, 2)
        total_revenue += rev

    # NOI per crop
    noi_by_crop = {}
    total_noi = 0.0
    for crop_name in projected_yields:
        rev = revenue_by_crop.get(crop_name, 0)
        alloc = shared_alloc.get(crop_name, 0)
        # Direct costs proportional to area
        total_ha = max(total_area, 1)
        crop_ha = projected_yields[crop_name]["area_ha"]
        direct_share = projected_costs["total_direct"] * (crop_ha / total_ha)
        crop_total_costs = direct_share + alloc
        crop_noi = rev - crop_total_costs
        margin = (crop_noi / rev * 100) if rev > 0 else 0
        noi_by_crop[crop_name] = {
            "revenue": round(rev, 2),
            "costs": round(crop_total_costs, 2),
            "noi": round(crop_noi, 2),
            "margin_pct": round(margin, 2),
        }
        total_noi += crop_noi

    total_costs = projected_costs["total_costs"]
    overall_margin = (total_noi / total_revenue * 100) if total_revenue > 0 else 0

    # Per-m² revenue (computed after total_revenue is known)
    if per_sqm_data and total_bed_area_sqm > 0:
        revenue_per_sqm_usd = total_revenue / total_bed_area_sqm

    # Risk adjustment
    drought_prob = sa.drought_probability
    risk_factor = calculate_risk_factor(scenario_type, drought_prob)
    risk_noi = risk_adjust_noi(total_noi, risk_factor)
    risk_rev = risk_adjust_revenue(total_revenue, risk_factor)

    # Cash flow — structured capex from capex_breakdown table
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT category, SUM(amount_usd) as total,
                   SUM(CASE WHEN is_recurring THEN COALESCE(annual_depreciation_usd, amount_usd) ELSE amount_usd END) as annual_cost
            FROM capex_breakdown
            WHERE location_id = %s AND status IN ('verified', 'published')
            GROUP BY category
        """, (location_id,))
        capex_rows = cur.fetchall()
    db.close()

    if capex_rows:
        capex_by_category = {r["category"]: float(r["annual_cost"]) for r in capex_rows}
        capex_estimate = sum(capex_by_category.values())
    else:
        capex_by_category = {"equipment": total_area * 200}
        capex_estimate = total_area * 200  # fallback: $200/ha

    cash_flow = total_noi - capex_estimate
    cf_low, cf_high = calculate_confidence_interval(cash_flow, risk_factor)

    # Public goods allocation (10% of revenue)
    public_goods = total_revenue * 0.10

    # Build outputs
    now = datetime.now(timezone.utc)
    period_start = scenario.get("assumptions", {}).get("period", "").split(" to ")[0] if scenario.get("assumptions", {}).get("period") else "2026-04-01"
    period_end = scenario.get("assumptions", {}).get("period", "").split(" to ")[1] if scenario.get("assumptions", {}).get("period") and " to " in scenario.get("assumptions", {}).get("period", "") else "2027-03-31"

    loss_adjusted_total = round(sum(
        v.get("loss_adjusted_yield_tonnes", v["total_yield_tonnes"])
        for v in projected_yields.values()
    ), 2)

    outputs = [
        _make_output(scenario_id, location_id, "projected_revenue_usd",
                      total_revenue, "usd", risk_rev["confidence_low"],
                      risk_rev["confidence_high"], period_start, period_end,
                      {"revenue_by_crop": revenue_by_crop}),
        _make_output(scenario_id, location_id, "projected_noi_usd",
                      total_noi, "usd", risk_noi["confidence_low"],
                      risk_noi["confidence_high"], period_start, period_end,
                      {"total_revenue": total_revenue, "total_costs": total_costs,
                       "noi_by_crop": {k: v["noi"] for k, v in noi_by_crop.items()}}),
        _make_output(scenario_id, location_id, "operating_margin_pct",
                      round(overall_margin, 2), "pct",
                      round(overall_margin * 0.8, 2), round(overall_margin * 1.2, 2),
                      period_start, period_end,
                      {"noi": total_noi, "revenue": total_revenue}),
        _make_output(scenario_id, location_id, "total_yield_tonnes",
                      round(calculate_total_yield(projected_yields), 2), "tonnes",
                      round(calculate_total_yield(projected_yields) * 0.85, 2),
                      round(calculate_total_yield(projected_yields) * 1.15, 2),
                      period_start, period_end,
                      {"yields": {k: v["total_yield_tonnes"] for k, v in projected_yields.items()},
                       "loss_rate": historical_loss_rate}),
        _make_output(scenario_id, location_id, "loss_adjusted_yield_tonnes",
                      loss_adjusted_total, "tonnes",
                      round(loss_adjusted_total * 0.85, 2),
                      round(loss_adjusted_total * 1.15, 2),
                      period_start, period_end,
                      {"gross_yield": round(calculate_total_yield(projected_yields), 2),
                       "loss_rate": historical_loss_rate,
                       "loss_adjusted_yields": {k: v.get("loss_adjusted_yield_tonnes", v["total_yield_tonnes"]) for k, v in projected_yields.items()}}),
        _make_output(scenario_id, location_id, "projected_cash_flow_usd",
                      round(cash_flow, 2), "usd", round(cf_low, 2), round(cf_high, 2),
                      period_start, period_end,
                      {"noi": total_noi, "capex": capex_estimate,
                       "capex_by_category": {k: round(v, 2) for k, v in capex_by_category.items()},
                       "capex_source": "capex_breakdown" if capex_rows else "fallback_200_per_ha"}),
        _make_output(scenario_id, location_id, "public_goods_allocation_usd",
                      round(public_goods, 2), "usd",
                      round(public_goods * 0.85, 2), round(public_goods * 1.15, 2),
                      period_start, period_end,
                      {"revenue": total_revenue, "allocation_pct": 0.10}),
        _make_output(scenario_id, location_id, "ecological_score_forecast",
                      eco_proj["ecological_score"], "score",
                      round(eco_proj["ecological_score"] * 0.9, 1),
                      round(eco_proj["ecological_score"] * 1.1, 1),
                      period_start, period_end,
                      {"baseline": eco_baseline, "projected": eco_proj}),
        _make_output(scenario_id, location_id, "risk_adjusted_noi_usd",
                      risk_noi["risk_adjusted_noi"], "usd",
                      risk_noi["confidence_low"], risk_noi["confidence_high"],
                      period_start, period_end,
                      {"base_noi": total_noi, "risk_factor": risk_factor}),
        _make_output(scenario_id, location_id, "carbon_sequestration_tonnes",
                      round(carbon_tonnes, 2), "tonnes",
                      round(carbon_tonnes * 0.8, 2), round(carbon_tonnes * 1.2, 2),
                      period_start, period_end,
                      {"som_change_pct": round(som_change_pct, 4), "area_ha": total_area}),
        _make_output(scenario_id, location_id, "carbon_credit_value_usd",
                      round(carbon_credit_value, 2), "usd",
                      round(carbon_credit_value * 0.8, 2), round(carbon_credit_value * 1.2, 2),
                      period_start, period_end,
                      {"carbon_tonnes": carbon_tonnes, "price_per_tonne": carbon_price_per_tonne}),
        _make_output(scenario_id, location_id, "biodiversity_credit_value_usd",
                      round(biodiversity_credit_value, 2), "usd",
                      round(biodiversity_credit_value * 0.8, 2), round(biodiversity_credit_value * 1.2, 2),
                      period_start, period_end,
                      {"species_count": bio_value["species_count"],
                       "shannon_index": bio_value["shannon_index"],
                       "price_per_species": bio_value["credit_price_per_species"]}),
        _make_output(scenario_id, location_id, "retained_value_usd",
                      round(retained_value, 2), "usd",
                      round(retained_value * 0.8, 2), round(retained_value * 1.2, 2),
                      period_start, period_end,
                      {"noi": total_noi, "retention_rate_pct": retention_rate,
                       "source": "scenario_assumption" if sa.retention_rate_pct is not None else "historical_rate"}),
        _make_output(scenario_id, location_id, "retention_rate_pct",
                      round(retention_rate, 2), "pct",
                      round(retention_rate * 0.9, 2), round(retention_rate * 1.1, 2),
                      period_start, period_end,
                      {"retention_rate_pct": retention_rate,
                       "source": "scenario_assumption" if sa.retention_rate_pct is not None else "historical_rate"}),
        _make_output(scenario_id, location_id, "production_per_sqm",
                      round(production_per_sqm, 6), "tonnes_per_sqm",
                      round(production_per_sqm * 0.85, 6), round(production_per_sqm * 1.15, 6),
                      period_start, period_end,
                      {"total_bed_area_sqm": total_bed_area_sqm,
                       "total_yield_tonnes": per_sqm_data["total_yield_tonnes"] if per_sqm_data else 0,
                       "loss_rate": historical_loss_rate,
                       "calculation_path": "per_sqm" if per_sqm_data else "ha_fallback"}),
        _make_output(scenario_id, location_id, "revenue_per_sqm_usd",
                      round(revenue_per_sqm_usd, 4), "usd_per_sqm",
                      round(revenue_per_sqm_usd * 0.85, 4), round(revenue_per_sqm_usd * 1.15, 4),
                      period_start, period_end,
                      {"total_revenue": total_revenue,
                       "total_bed_area_sqm": total_bed_area_sqm,
                       "planting_density_per_sqm": per_sqm_data["planting_density_per_sqm"] if per_sqm_data else 0,
                       "calculation_path": "per_sqm" if per_sqm_data else "ha_fallback"}),
    ]

    # Per-cycle outputs
    cycle_id_map = {}
    for ca in crop_areas:
        name = ca["crop_name"]
        cycle_id = ca.get("cycle_id")
        if cycle_id and name not in cycle_id_map:
            cycle_id_map[name] = cycle_id

    for crop_name, cycle_id in cycle_id_map.items():
        crop_data = noi_by_crop.get(crop_name, {})
        if not crop_data:
            continue
        outputs.append(_make_output(
            scenario_id, location_id, "crop_noi_usd",
            crop_data["noi"], "usd",
            round(crop_data["noi"] * 0.8, 2), round(crop_data["noi"] * 1.2, 2),
            period_start, period_end,
            {"crop": crop_name, "revenue": crop_data["revenue"], "costs": crop_data["costs"]},
            crop_cycle_id=cycle_id,
        ))
        outputs.append(_make_output(
            scenario_id, location_id, "crop_margin_pct",
            crop_data["margin_pct"], "pct",
            round(crop_data["margin_pct"] * 0.8, 2), round(crop_data["margin_pct"] * 1.2, 2),
            period_start, period_end,
            {"crop": crop_name},
            crop_cycle_id=cycle_id,
        ))

    # Write outputs to database
    _write_outputs(outputs)

    # Write dashboard dataset for BI integration
    _write_dashboard_dataset(scenario_id, location_id, outputs, scenario_type)

    # Update scenario status
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            UPDATE forecast_scenario
            SET status = 'published', updated_at = NOW()
            WHERE id = %s
        """, (scenario_id,))
    db.commit()
    db.close()

    return {
        "scenario_id": scenario_id,
        "location_id": location_id,
        "scenario_type": scenario_type,
        "total_revenue": round(total_revenue, 2),
        "total_costs": round(total_costs, 2),
        "total_noi": round(total_noi, 2),
        "operating_margin_pct": round(overall_margin, 2),
        "total_yield_tonnes": round(calculate_total_yield(projected_yields), 2),
        "risk_adjusted_noi": risk_noi["risk_adjusted_noi"],
        "risk_factor": risk_factor,
        "ecological_score": eco_proj["ecological_score"],
        "biodiversity_credit_value": round(biodiversity_credit_value, 2),
        "retained_value": round(retained_value, 2),
        "retention_rate_pct": round(retention_rate, 2),
        "production_per_sqm": round(production_per_sqm, 6),
        "revenue_per_sqm_usd": round(revenue_per_sqm_usd, 4),
        "total_bed_area_sqm": round(total_bed_area_sqm, 2),
        "calculation_path": "per_sqm" if per_sqm_data else "ha_fallback",
        "outputs_written": len(outputs),
    }


def _get_retention_rate(sa: ScenarioAssumptions, location_id: str) -> float:
    """Get retention rate: scenario assumption if provided, else historical rate."""
    if sa.retention_rate_pct is not None:
        return sa.retention_rate_pct

    # Historical rate from value_flow_event
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT
                SUM(CASE WHEN flow_type = 'reinvestment' THEN amount ELSE 0 END) as reinvested,
                SUM(CASE WHEN flow_type = 'revenue' THEN amount ELSE 0 END) as revenue
            FROM value_flow_event
            WHERE location_id = %s AND verified = TRUE
        """, (location_id,))
        row = cur.fetchone()
    db.close()

    if row and row[1] and float(row[1]) > 0:
        return round(float(row[0] or 0) / float(row[1]) * 100, 2)

    # Default: 20% reinvestment rate
    return 20.0


def _make_output(
    scenario_id: str, location_id: str,
    metric_name: str, value: float, unit: str,
    confidence_low: float, confidence_high: float,
    period_start: str, period_end: str,
    inputs: Dict[str, Any],
    crop_cycle_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a forecast output record."""
    return {
        "id": str(uuid.uuid4()),
        "scenario_id": scenario_id,
        "location_id": location_id,
        "metric_name": metric_name,
        "period_start": period_start,
        "period_end": period_end,
        "value": value,
        "unit": unit,
        "confidence_low": confidence_low,
        "confidence_high": confidence_high,
        "confidence_level": CONFIDENCE_LEVEL,
        "calculation_version": CALCULATION_VERSION,
        "calculated_at": datetime.now(timezone.utc),
        "inputs": json.dumps(inputs),
        "crop_cycle_id": crop_cycle_id,
    }


def _write_outputs(outputs: List[Dict[str, Any]]) -> None:
    """Write forecast outputs to the database."""
    db = get_db()
    with db.cursor() as cur:
        for out in outputs:
            cur.execute("""
                INSERT INTO forecast_output
                    (id, scenario_id, location_id, metric_name, period_start, period_end,
                     value, unit, confidence_low, confidence_high, confidence_level,
                     calculation_version, calculated_at, inputs, crop_cycle_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                out["id"], out["scenario_id"], out["location_id"],
                out["metric_name"], out["period_start"], out["period_end"],
                out["value"], out["unit"], out["confidence_low"], out["confidence_high"],
                out["confidence_level"], out["calculation_version"],
                out["calculated_at"], out["inputs"], out.get("crop_cycle_id"),
            ))
    db.commit()
    db.close()


def _write_dashboard_dataset(
    scenario_id: str, location_id: str,
    outputs: List[Dict[str, Any]], scenario_type: str,
) -> None:
    """Write forecast summary to dashboard_dataset for BI integration."""
    try:
        summary = {}
        for out in outputs:
            summary[out["metric_name"]] = {
                "value": out["value"],
                "unit": out["unit"],
                "confidence_low": out["confidence_low"],
                "confidence_high": out["confidence_high"],
            }

        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO dashboard_dataset
                    (id, location_id, dataset_type, query_sql, status,
                     metadata, created_at)
                VALUES (%s, %s, 'forecast', %s, 'published', %s::jsonb, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    metadata = EXCLUDED.metadata,
                    status = 'published',
                    updated_at = NOW()
            """, (
                str(uuid.uuid4()),
                location_id,
                f"SELECT * FROM forecast_output WHERE scenario_id = '{scenario_id}'",
                json.dumps({
                    "scenario_id": scenario_id,
                    "scenario_type": scenario_type,
                    "outputs": summary,
                }),
            ))
        db.commit()
        db.close()
    except Exception as e:
        print(f"[Forecast] Warning: Failed to write dashboard_dataset: {e}")


def run_all_scenarios(location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Run forecast for all draft/published scenarios."""
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if location_id:
            cur.execute(
                "SELECT id, name FROM forecast_scenario WHERE location_id = %s AND status IN ('draft', 'published')",
                (location_id,),
            )
        else:
            cur.execute(
                "SELECT id, name FROM forecast_scenario WHERE status IN ('draft', 'published')"
            )
        scenarios = cur.fetchall()
    db.close()

    results = []
    for sc in scenarios:
        try:
            result = run_forecast(str(sc["id"]))
            results.append(result)
            print(f"  ✓ {sc['name']}: NOI=${result['total_noi']:,.2f}, Margin={result['operating_margin_pct']:.1f}%")
        except Exception as e:
            print(f"  ✗ {sc['name']}: {e}")
            results.append({"scenario_id": str(sc["id"]), "error": str(e)})

    return results
