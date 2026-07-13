#!/usr/bin/env python3
"""
Digital Twin — Crop Growth Simulation

Creates virtual farm replicas, runs crop growth simulations, and
supports what-if scenario analysis for management decisions.

Usage:
    python -m services.analytics.digital_twin create --location-id UUID --name "Adelphi Twin"
    python -m services.analytics.digital_twin configure --twin-id UUID --key crop --value maize
    python -m services.analytics.digital_twin simulate --twin-id UUID
    python -m services.analytics.digital_twin scenario --twin-id UUID --name "High Irrigation" --params '{"irrigation_mm": 30}'
    python -m services.analytics.digital_twin compare --twin-id UUID
    python -m services.analytics.digital_twin list --location-id UUID
"""

import argparse
import json
import math
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.digital_twin")


# ============================================================
# Default Simulation Parameters
# ============================================================

DEFAULT_PARAMS = {
    "crop": "maize",
    "planting_density": 7.0,      # seeds/m²
    "bed_area_sqm": 50.0,
    "bed_count": 20,
    "irrigation_mm": 10,          # mm per irrigation event
    "irrigation_frequency_days": 7,
    "fertilizer_kg_ha": 120,      # kg N/ha
    "soil_type": "loam",
    "initial_soil_nitrogen_ppm": 30,
    "initial_soil_moisture_pct": 40,
    "initial_soil_carbon_pct": 1.5,
    "rainfall_multiplier": 1.0,   # × baseline
    "temperature_offset_c": 0,    # +°C offset from baseline
}

CROP_PARAMS = {
    "maize": {
        "gdd_emergence": 120, "gdd_maturity": 1500,
        "max_biomass_kg_ha": 12000,
        "harvest_index": 0.45,
        "kc_initial": 0.3, "kc_mid": 1.2, "kc_late": 0.6,
        "n_uptake_factor": 0.7,
        "temp_optimal_min": 18, "temp_optimal_max": 32,
        "temp_stress_low": 10, "temp_stress_high": 38,
    },
    "beans": {
        "gdd_emergence": 100, "gdd_maturity": 1200,
        "max_biomass_kg_ha": 4000,
        "harvest_index": 0.40,
        "kc_initial": 0.35, "kc_mid": 1.1, "kc_late": 0.5,
        "n_uptake_factor": 0.3,
        "temp_optimal_min": 15, "temp_optimal_max": 28,
        "temp_stress_low": 5, "temp_stress_high": 35,
    },
    "cassava": {
        "gdd_emergence": 200, "gdd_maturity": 2500,
        "max_biomass_kg_ha": 15000,
        "harvest_index": 0.55,
        "kc_initial": 0.4, "kc_mid": 1.0, "kc_late": 0.5,
        "n_uptake_factor": 0.4,
        "temp_optimal_min": 20, "temp_optimal_max": 35,
        "temp_stress_low": 10, "temp_stress_high": 40,
    },
    "default": {
        "gdd_emergence": 150, "gdd_maturity": 1500,
        "max_biomass_kg_ha": 8000,
        "harvest_index": 0.40,
        "kc_initial": 0.35, "kc_mid": 1.1, "kc_late": 0.55,
        "n_uptake_factor": 0.5,
        "temp_optimal_min": 15, "temp_optimal_max": 32,
        "temp_stress_low": 5, "temp_stress_high": 38,
    },
}

BASELINE_RAINFALL_MM_DAY = 3.0  # average daily rainfall


# ============================================================
# Digital Twin Management
# ============================================================

def create_digital_twin(
    conn,
    location_id: str,
    name: str,
    description: str = None,
    twin_type: str = "crop_simulation",
    time_horizon_days: int = 365,
    start_date: date = None,
) -> dict:
    """Create a new digital twin."""
    cur = conn.cursor()
    twin_id = str(uuid.uuid4())
    start_date = start_date or date.today()

    cur.execute(
        """
        INSERT INTO digital_twin
            (id, location_id, name, description, twin_type, status,
             time_horizon_days, start_date, end_date)
        VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s)
        RETURNING id
        """,
        (
            twin_id, location_id, name, description, twin_type,
            time_horizon_days, start_date,
            start_date + timedelta(days=time_horizon_days),
        ),
    )
    conn.commit()
    cur.close()

    return {"twin_id": twin_id, "name": name, "location_id": location_id}


def configure_twin(conn, twin_id: str, config_key: str, config_value) -> dict:
    """Set a simulation configuration parameter."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO simulation_config (id, twin_id, config_key, config_value)
        VALUES (%s, %s, %s, %s::jsonb)
        ON CONFLICT (twin_id, config_key)
        DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = NOW()
        """,
        (str(uuid.uuid4()), twin_id, config_key, json.dumps(config_value)),
    )
    conn.commit()
    cur.close()
    return {"twin_id": twin_id, "key": config_key, "value": config_value}


def get_twin_config(conn, twin_id: str) -> dict:
    """Get all configuration for a twin, merged with defaults."""
    cur = conn.cursor()
    cur.execute(
        "SELECT config_key, config_value FROM simulation_config WHERE twin_id = %s",
        (twin_id,),
    )
    rows = cur.fetchall()
    cur.close()

    params = dict(DEFAULT_PARAMS)
    for key, val in rows:
        if isinstance(val, dict) and "value" in val:
            params[key] = val["value"]
        else:
            params[key] = val

    return params


def list_twins(conn, location_id: str = None) -> list:
    """List digital twins."""
    cur = conn.cursor()
    if location_id:
        cur.execute(
            "SELECT id, name, twin_type, status, start_date, last_run_at, run_count FROM digital_twin WHERE location_id = %s ORDER BY created_at DESC",
            (location_id,),
        )
    else:
        cur.execute(
            "SELECT id, name, twin_type, status, start_date, last_run_at, run_count FROM digital_twin ORDER BY created_at DESC"
        )
    cols = [d[0] for d in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


# ============================================================
# Simulation Engine
# ============================================================

def run_simulation(conn, twin_id: str, parameters: dict = None) -> dict:
    """Run a crop growth simulation.

    Simplified daily time-step model:
    - GDD accumulation from temperature
    - Biomass growth from GDD, light, water, nitrogen
    - Water balance: rainfall + irrigation - ET - drainage
    - Nitrogen uptake and leaching
    - Carbon sequestration from biomass
    """
    import time as _time
    start_time = _time.time()

    params = get_twin_config(conn, twin_id)
    if parameters:
        params.update(parameters)

    # Get twin info
    cur = conn.cursor()
    cur.execute(
        "SELECT location_id, start_date, time_horizon_days FROM digital_twin WHERE id = %s",
        (twin_id,),
    )
    twin_row = cur.fetchone()
    if not twin_row:
        cur.close()
        return {"error": "Twin not found"}

    location_id, start_date, time_horizon = twin_row
    crop = params.get("crop", "maize")
    crop_p = CROP_PARAMS.get(crop, CROP_PARAMS["default"])

    # Create run record
    run_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO simulation_run (id, twin_id, run_label, status, parameters, started_at)
        VALUES (%s, %s, 'base_simulation', 'running', %s::jsonb, NOW())
        RETURNING id
        """,
        (run_id, twin_id, json.dumps(parameters or {})),
    )

    # Update twin run count
    cur.execute(
        "UPDATE digital_twin SET last_run_at = NOW(), run_count = run_count + 1 WHERE id = %s",
        (twin_id,),
    )
    conn.commit()

    # Initialize state
    soil_nitrogen = float(params.get("initial_soil_nitrogen_ppm", 30))
    soil_moisture = float(params.get("initial_soil_moisture_pct", 40))
    soil_carbon = float(params.get("initial_soil_carbon_pct", 1.5))
    gdd_accum = 0.0
    biomass = 0.0
    lai = 0.1
    root_depth = 5.0
    total_water_in = 0.0
    total_nitrogen_used = 0.0
    total_carbon_seq = 0.0
    rain_mult = float(params.get("rainfall_multiplier", 1.0))
    temp_offset = float(params.get("temperature_offset_c", 0))
    fert_kg_ha = float(params.get("fertilizer_kg_ha", 120))
    irr_mm = float(params.get("irrigation_mm", 10))
    irr_freq = int(params.get("irrigation_frequency_days", 7))

    # Apply fertilizer at start
    soil_nitrogen += fert_kg_ha * 0.8  # 80% immediately available

    states = []

    for day in range(time_horizon):
        current_date = start_date + timedelta(days=day)

        # --- Weather (simple model with seasonality) ---
        day_of_year = current_date.timetuple().tm_yday
        # Seasonal temperature curve (peak at day 180)
        seasonal_temp = 25 + 10 * math.sin(2 * math.pi * (day_of_year - 80) / 365)
        temp_avg = seasonal_temp + temp_offset + (hash(str(day)) % 10 - 5) * 0.3
        temp_min = temp_avg - 5
        temp_max = temp_avg + 5

        # Seasonal rainfall
        seasonal_rain = BASELINE_RAINFALL_MM_DAY * (1 + 0.5 * math.sin(2 * math.pi * (day_of_year - 100) / 365))
        rainfall = max(0, seasonal_rain * rain_mult + (hash(str(day + 1000)) % 8 - 4) * 0.5)

        # Solar radiation (MJ/m²/day)
        solar = 15 + 8 * math.sin(2 * math.pi * (day_of_year - 80) / 365)
        humidity = 60 + 20 * math.sin(2 * math.pi * (day_of_year - 150) / 365)
        wind = 5 + 3 * math.sin(2 * math.pi * (day_of_year + 50) / 365)

        # --- GDD ---
        gdd_day = max(0, (temp_min + temp_max) / 2 - 10)  # base 10°C
        gdd_accum += gdd_day

        # --- Crop stage ---
        if gdd_accum < crop_p["gdd_emergence"]:
            stage = "emergence"
            growth_frac = 0
        elif gdd_accum < crop_p["gdd_maturity"] * 0.3:
            stage = "vegetative"
            growth_frac = min(1.0, (gdd_accum - crop_p["gdd_emergence"]) / (crop_p["gdd_maturity"] * 0.3 - crop_p["gdd_emergence"]))
        elif gdd_accum < crop_p["gdd_maturity"] * 0.7:
            stage = "flowering"
            growth_frac = 0.7
        elif gdd_accum < crop_p["gdd_maturity"]:
            stage = "grain_fill"
            growth_frac = 0.9
        else:
            stage = "maturity"
            growth_frac = 1.0

        # --- ET calculation ---
        kc = crop_p["kc_mid"] if stage in ("flowering", "grain_fill") else crop_p["kc_initial"] if stage == "emergence" else crop_p["kc_late"]
        et0 = max(0, 0.0023 * solar * (temp_avg + 17.8) * (1 - humidity / 100) * 0.408)
        et_actual = et0 * kc * (0.5 + 0.5 * min(soil_moisture / 50, 1.0))

        # --- Irrigation ---
        irrigation = 0
        if day % irr_freq == 0 and soil_moisture < 35:
            irrigation = irr_mm

        # --- Water balance ---
        water_in = rainfall + irrigation
        drainage = max(0, soil_moisture + water_in * 0.3 - 100) * 0.1
        soil_moisture = max(0, min(100, soil_moisture + water_in * 0.3 - et_actual - drainage))
        total_water_in += water_in

        # --- Nitrogen dynamics ---
        n_uptake = crop_p["n_uptake_factor"] * growth_frac * 0.5 if gdd_accum > crop_p["gdd_emergence"] else 0
        n_leach = soil_nitrogen * 0.02 * (drainage / 5) if drainage > 0 else 0
        soil_nitrogen = max(0, soil_nitrogen - n_uptake - n_leach)
        total_nitrogen_used += n_uptake

        # --- Biomass growth ---
        water_stress = min(1.0, soil_moisture / 30) if soil_moisture < 30 else 1.0
        n_stress = min(1.0, soil_nitrogen / 15) if soil_nitrogen < 15 else 1.0
        temp_stress = 1.0
        if temp_avg < crop_p["temp_stress_low"] or temp_avg > crop_p["temp_stress_high"]:
            temp_stress = 0.3
        elif temp_avg < crop_p["temp_optimal_min"] or temp_avg > crop_p["temp_optimal_max"]:
            temp_stress = 0.7

        growth_rate = crop_p["max_biomass_kg_ha"] * gdd_day / crop_p["gdd_maturity"]
        biomass += growth_rate * water_stress * n_stress * temp_stress * 0.8
        biomass = max(0, min(crop_p["max_biomass_kg_ha"], biomass))

        # LAI and root depth
        lai = min(6.0, biomass / crop_p["max_biomass_kg_ha"] * 5.5)
        root_depth = min(60, 5 + biomass / crop_p["max_biomass_kg_ha"] * 55)

        # --- Carbon ---
        c_biomass = biomass * 0.45 * 3.67  # C content × CO2 equivalent
        c_soil = (soil_carbon / 100) * 1500000 * 0.001  # rough: 1500t soil/ha
        carbon_seq_day = c_biomass * 0.001  # rough sequestration rate
        total_carbon_seq += carbon_seq_day

        states.append({
            "day_number": day + 1,
            "state_date": current_date.isoformat(),
            "soil_moisture_pct": round(soil_moisture, 2),
            "soil_nitrogen_ppm": round(soil_nitrogen, 2),
            "soil_carbon_pct": round(soil_carbon, 3),
            "gdd_accumulated": round(gdd_accum, 2),
            "crop_biomass_kg_ha": round(biomass, 2),
            "leaf_area_index": round(lai, 3),
            "crop_stage": stage,
            "root_depth_cm": round(root_depth, 2),
            "rainfall_mm": round(rainfall, 2),
            "irrigation_mm": round(irrigation, 2),
            "et_actual_mm": round(et_actual, 2),
            "temp_avg_c": round(temp_avg, 2),
            "temp_min_c": round(temp_min, 2),
            "temp_max_c": round(temp_max, 2),
            "solar_radiation_mj": round(solar, 2),
            "humidity_pct": round(humidity, 2),
            "wind_speed_kmh": round(wind, 2),
            "carbon_sequestered_kg_ha": round(carbon_seq_day, 4),
        })

    # Compute final yield
    final_biomass = states[-1]["crop_biomass_kg_ha"] if states else 0
    final_yield = final_biomass * crop_p["harvest_index"]

    duration_ms = int((_time.time() - start_time) * 1000)

    # Store states (batch insert)
    if states:
        _store_states(conn, run_id, states)

    # Update run record
    cur.execute(
        """
        UPDATE simulation_run
        SET status = 'completed', completed_at = NOW(), duration_ms = %s,
            final_yield = %s, total_water_mm = %s, total_nitrogen_kg = %s,
            avg_soil_carbon_pct = %s
        WHERE id = %s
        """,
        (
            duration_ms, round(final_yield, 2),
            round(total_water_in, 2), round(total_nitrogen_used, 2),
            round(soil_carbon, 3), run_id,
        ),
    )
    conn.commit()
    cur.close()

    return {
        "run_id": run_id,
        "twin_id": twin_id,
        "status": "completed",
        "final_yield_kg_ha": round(final_yield, 2),
        "total_biomass_kg_ha": round(final_biomass, 2),
        "total_water_mm": round(total_water_in, 2),
        "total_nitrogen_used": round(total_nitrogen_used, 2),
        "final_soil_carbon_pct": round(soil_carbon, 3),
        "final_soil_moisture_pct": round(soil_moisture, 2),
        "duration_ms": duration_ms,
        "days_simulated": time_horizon,
    }


def _store_states(conn, run_id: str, states: list):
    """Batch insert simulation states."""
    cur = conn.cursor()
    for s in states:
        cur.execute(
            """
            INSERT INTO simulation_state
                (id, run_id, day_number, state_date,
                 soil_moisture_pct, soil_nitrogen_ppm, soil_carbon_pct,
                 gdd_accumulated, crop_biomass_kg_ha, leaf_area_index,
                 crop_stage, root_depth_cm,
                 rainfall_mm, irrigation_mm, et_actual_mm,
                 temp_avg_c, temp_min_c, temp_max_c,
                 solar_radiation_mj, humidity_pct, wind_speed_kmh,
                 carbon_sequestered_kg_ha)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()), run_id, s["day_number"], s["state_date"],
                s["soil_moisture_pct"], s["soil_nitrogen_ppm"], s["soil_carbon_pct"],
                s["gdd_accumulated"], s["crop_biomass_kg_ha"], s["leaf_area_index"],
                s["crop_stage"], s["root_depth_cm"],
                s["rainfall_mm"], s["irrigation_mm"], s["et_actual_mm"],
                s["temp_avg_c"], s["temp_min_c"], s["temp_max_c"],
                s["solar_radiation_mj"], s["humidity_pct"], s["wind_speed_kmh"],
                s["carbon_sequestered_kg_ha"],
            ),
        )
    conn.commit()
    cur.close()


# ============================================================
# What-If Scenarios
# ============================================================

def create_scenario(
    conn,
    twin_id: str,
    name: str,
    parameters: dict,
    description: str = None,
    category: str = "management",
) -> dict:
    """Create a what-if scenario."""
    cur = conn.cursor()
    scenario_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO what_if_scenario (id, twin_id, name, description, parameters, category, status)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, 'draft')
        RETURNING id
        """,
        (scenario_id, twin_id, name, description, json.dumps(parameters), category),
    )
    conn.commit()
    cur.close()
    return {"scenario_id": scenario_id, "twin_id": twin_id, "name": name}


def run_scenario(conn, scenario_id: str) -> dict:
    """Run a what-if scenario."""
    cur = conn.cursor()
    cur.execute(
        "SELECT twin_id, parameters, name FROM what_if_scenario WHERE id = %s",
        (scenario_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Scenario not found"}

    twin_id = row[0]
    params = row[1] if isinstance(row[1], dict) else json.loads(row[1]) if row[1] else {}
    scenario_name = row[2]
    cur.close()

    result = run_simulation(conn, twin_id, parameters=params)
    if "error" in result:
        return result

    # Update scenario with run result
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE what_if_scenario
        SET run_id = %s, status = 'completed', updated_at = NOW()
        WHERE id = %s
        """,
        (result["run_id"], scenario_id),
    )
    conn.commit()
    cur.close()

    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "run_id": result["run_id"],
        "final_yield_kg_ha": result["final_yield_kg_ha"],
        "status": "completed",
    }


def compare_scenarios(conn, twin_id: str) -> dict:
    """Compare all scenario results for a twin."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ws.id, ws.name, ws.category, ws.parameters, ws.status,
               sr.final_yield, sr.total_water_mm, sr.total_nitrogen_kg,
               sr.total_cost_usd, sr.total_revenue_usd, sr.net_margin_usd
        FROM what_if_scenario ws
        LEFT JOIN simulation_run sr ON sr.id = ws.run_id
        WHERE ws.twin_id = %s
        ORDER BY ws.created_at
        """,
        (twin_id,),
    )
    cols = [d[0] for d in cur.description]
    scenarios = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    # Also get base run
    cur.execute(
        """
        SELECT sr.id, sr.final_yield, sr.total_water_mm, sr.total_nitrogen_kg,
               sr.net_margin_usd
        FROM simulation_run sr
        WHERE sr.twin_id = %s AND sr.run_label = 'base_simulation'
        ORDER BY sr.created_at DESC LIMIT 1
        """,
        (twin_id,),
    )
    base_row = cur.fetchone()
    base_yield = float(base_row[1]) if base_row and base_row[1] else None
    cur.close()

    comparisons = []
    for s in scenarios:
        comp = {
            "scenario_id": s["id"],
            "name": s["name"],
            "category": s["category"],
            "status": s["status"],
            "yield_kg_ha": float(s["final_yield"]) if s["final_yield"] else None,
            "water_mm": float(s["total_water_mm"]) if s["total_water_mm"] else None,
            "nitrogen_kg": float(s["total_nitrogen_kg"]) if s["total_nitrogen_kg"] else None,
        }
        if base_yield and comp["yield_kg_ha"]:
            comp["yield_change_pct"] = round((comp["yield_kg_ha"] - base_yield) / max(base_yield, 1) * 100, 1)
        comparisons.append(comp)

    return {
        "twin_id": twin_id,
        "base_yield": round(base_yield, 2) if base_yield else None,
        "scenarios": comparisons,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Digital twin simulation")
    sub = parser.add_subparsers(dest="command")

    # Create
    cr = sub.add_parser("create", help="Create digital twin")
    cr.add_argument("--location-id", required=True)
    cr.add_argument("--name", required=True)
    cr.add_argument("--description")
    cr.add_argument("--horizon", type=int, default=365, help="Days to simulate")
    cr.add_argument("--json", action="store_true")

    # Configure
    cfg = sub.add_parser("configure", help="Configure twin parameters")
    cfg.add_argument("--twin-id", required=True)
    cfg.add_argument("--key", required=True)
    cfg.add_argument("--value", required=True, help="JSON value")
    cfg.add_argument("--json", action="store_true")

    # Simulate
    sim = sub.add_parser("simulate", help="Run simulation")
    sim.add_argument("--twin-id", required=True)
    sim.add_argument("--json", action="store_true")

    # Scenario
    sc = sub.add_parser("scenario", help="Create and run what-if scenario")
    sc.add_argument("--twin-id", required=True)
    sc.add_argument("--name", required=True)
    sc.add_argument("--params", required=True, help="JSON parameters")
    sc.add_argument("--json", action="store_true")

    # Compare
    cmp = sub.add_parser("compare", help="Compare scenarios")
    cmp.add_argument("--twin-id", required=True)
    cmp.add_argument("--json", action="store_true")

    # List
    ls = sub.add_parser("list", help="List twins")
    ls.add_argument("--location-id")
    ls.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command in ("create", "configure", "simulate", "scenario", "compare", "list"):
        db = get_db()
    else:
        parser.print_help()
        return

    try:
        if args.command == "create":
            result = create_digital_twin(
                db, args.location_id, args.name, args.description,
                time_horizon_days=args.horizon,
            )
            output = json.dumps(result, indent=2) if args.json else f"Created: {result['name']} ({result['twin_id'][:8]}...)"
            print(output)

        elif args.command == "configure":
            val = json.loads(args.value)
            result = configure_twin(db, args.twin_id, args.key, val)
            output = json.dumps(result, indent=2) if args.json else f"Set {result['key']} = {result['value']}"
            print(output)

        elif args.command == "simulate":
            result = run_simulation(db, args.twin_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_sim(result)
            print(output)

        elif args.command == "scenario":
            params = json.loads(args.params)
            result = create_scenario(db, args.twin_id, args.name, params)
            if "scenario_id" in result:
                run_result = run_scenario(db, result["scenario_id"])
                output = json.dumps(run_result, indent=2, default=str) if args.json else _format_scenario(run_result)
            else:
                output = json.dumps(result, indent=2)
            print(output)

        elif args.command == "compare":
            result = compare_scenarios(db, args.twin_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_compare(result)
            print(output)

        elif args.command == "list":
            results = list_twins(db, args.location_id)
            output = json.dumps(results, indent=2, default=str) if args.json else _format_list(results)
            print(output)

    finally:
        db.close()


def _format_sim(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return (
        f"Simulation Complete — {r['days_simulated']} days ({r['duration_ms']}ms)\n"
        f"  Final Yield: {r['final_yield_kg_ha']} kg/ha\n"
        f"  Total Biomass: {r['total_biomass_kg_ha']} kg/ha\n"
        f"  Water Used: {r['total_water_mm']} mm\n"
        f"  N Used: {r['total_nitrogen_used']} kg/ha\n"
        f"  Soil Carbon: {r['final_soil_carbon_pct']}%\n"
        f"  Soil Moisture: {r['final_soil_moisture_pct']}%"
    )


def _format_scenario(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    return f"Scenario '{r['scenario_name']}': {r['final_yield_kg_ha']} kg/ha"


def _format_compare(r: dict) -> str:
    lines = [f"Scenario Comparison — {r['twin_id'][:8]}...", f"  Base Yield: {r['base_yield'] or 'N/A'} kg/ha"]
    for s in r["scenarios"]:
        arrow = f" ({s['yield_change_pct']:+.1f}%)" if s.get("yield_change_pct") else ""
        lines.append(f"  {s['name']:30s} {s['yield_kg_ha'] or 'N/A':>8} kg/ha{arrow}")
    return "\n".join(lines)


def _format_list(results: list) -> str:
    if not results:
        return "No digital twins."
    lines = [f"Digital Twins ({len(results)}):"]
    for r in results:
        lines.append(f"  {r['name']:30s} {r['twin_type']:20s} runs={r['run_count']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
