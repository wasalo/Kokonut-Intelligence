#!/usr/bin/env python3
"""
Crop Phenology — Growing Degree Day (GDD) Tracking and Growth Stage Detection

Computes accumulated GDD from weather data, detects current crop growth stages,
projects future stage dates, and identifies schedule anomalies.

Usage:
    python -m services.analytics.crop_phenology --accumulate --crop-cycle-id <uuid>
    python -m services.analytics.crop_phenology --detect-stage --crop-cycle-id <uuid>
    python -m services.analytics.crop_phenology --project --crop-cycle-id <uuid>
    python -m services.analytics.crop_phenology --anomalies --location-id <uuid>
    python -m services.analytics.crop_phenology --list-stages --crop maize
    python -m services.analytics.crop_phenology --current --location-id <uuid>
"""

import argparse
import json
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.crop_phenology")


# ============================================================
# GDD Computation
# ============================================================

def compute_gdd(temp_max: float, temp_min: float,
                base_temp: float = 10.0, upper_temp: float = 30.0) -> float:
    """Compute Growing Degree Days for a single day.
    
    GDD = max(0, min(temp_max, upper) - max(temp_min, base))
    
    Args:
        temp_max: Daily maximum temperature (°C)
        temp_min: Daily minimum temperature (°C)
        base_temp: Base temperature below which no growth (°C)
        upper_temp: Upper temperature above which no additional growth (°C)
    
    Returns:
        GDD value (°C·days), always >= 0
    """
    effective_max = min(temp_max, upper_temp)
    effective_min = max(temp_min, base_temp)
    gdd = max(0.0, effective_max - effective_min)
    return round(gdd, 2)


def compute_gdd_from_weather(temp_max: float, temp_min: float,
                              crop_name: str = "default") -> float:
    """Compute GDD using crop-specific base/upper temperatures."""
    from .evapotranspiration import CROP_KC
    # Use crop_gdd_config from DB if available, else defaults
    base_temps = {
        "maize": 10.0, "beans": 10.0, "cassava": 15.0,
        "sweet_potato": 10.0, "coffee": 10.0, "avocado": 10.0,
        "tomato": 10.0, "banana": 12.0,
    }
    upper_temps = {
        "maize": 30.0, "beans": 30.0, "cassava": 35.0,
        "sweet_potato": 35.0, "coffee": 30.0, "avocado": 30.0,
        "tomato": 30.0, "banana": 35.0,
    }
    base = base_temps.get(crop_name.lower(), 10.0)
    upper = upper_temps.get(crop_name.lower(), 30.0)
    return compute_gdd(temp_max, temp_min, base, upper)


# ============================================================
# GDD Accumulation
# ============================================================

def accumulate_gdd(conn, crop_cycle_id: str) -> dict:
    """Accumulate GDD from planting date to today using weather data.
    
    Returns:
        dict with accumulated_gdd, days_elapsed, avg_gdd_per_day,
        gdd_rate, daily_gdd_data
    """
    cur = conn.cursor()

    # Get crop cycle and crop info
    cur.execute(
        """
        SELECT cc.id, cc.planting_date, cc.status, c.name,
               cg.base_temp_c, cg.upper_temp_c, cg.total_gdd_required
        FROM crop_cycle cc
        JOIN crop c ON c.id = cc.crop_id
        LEFT JOIN crop_gdd_config cg ON cg.crop_name = c.name
        WHERE cc.id = %s
        """,
        (crop_cycle_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": f"Crop cycle {crop_cycle_id} not found"}

    cycle_id, planting_date, status, crop_name, base_temp, upper_temp, total_gdd = row
    base_temp = float(base_temp or 10.0)
    upper_temp = float(upper_temp or 30.0)
    total_gdd = float(total_gdd or 2000)

    if not planting_date:
        cur.close()
        return {"error": "No planting date set for this crop cycle"}

    # Get weather data from planting date to now
    cur.execute(
        """
        SELECT observation_date,
               COALESCE(temp_max_c, temperature_c) AS temp_max,
               COALESCE(temp_min_c, temperature_c) AS temp_min
        FROM weather_observation
        WHERE location_id = (SELECT location_id FROM crop_cycle WHERE id = %s)
          AND observation_date >= %s
          AND observation_date <= CURRENT_DATE
          AND (temp_max_c IS NOT NULL OR temperature_c IS NOT NULL)
        ORDER BY observation_date
        """,
        (crop_cycle_id, planting_date),
    )
    weather_rows = cur.fetchall()

    cur.close()

    accumulated = 0.0
    daily_gdd = []

    for obs_date, temp_max, temp_min in weather_rows:
        if temp_max is None or temp_min is None:
            continue
        day_gdd = compute_gdd(float(temp_max), float(temp_min), base_temp, upper_temp)
        accumulated += day_gdd
        daily_gdd.append({
            "date": obs_date.isoformat(),
            "gdd": round(day_gdd, 2),
            "accumulated": round(accumulated, 2),
        })

    days_elapsed = (date.today() - planting_date).days
    avg_gdd_per_day = accumulated / max(days_elapsed, 1)
    pct_complete = min((accumulated / total_gdd) * 100, 100) if total_gdd > 0 else 0

    return {
        "crop_cycle_id": crop_cycle_id,
        "crop_name": crop_name,
        "planting_date": planting_date.isoformat(),
        "days_elapsed": days_elapsed,
        "accumulated_gdd": round(accumulated, 2),
        "total_gdd_required": total_gdd,
        "pct_gdd_complete": round(pct_complete, 1),
        "avg_gdd_per_day": round(avg_gdd_per_day, 2),
        "gdd_rate": round(avg_gdd_per_day, 2),
        "daily_gdd_data": daily_gdd,
    }


# ============================================================
# Growth Stage Detection
# ============================================================

def get_crop_stages_from_config(conn, crop_name: str) -> list[dict]:
    """Get growth stage definitions from crop_gdd_config."""
    cur = conn.cursor()
    cur.execute(
        "SELECT stages, total_gdd_required FROM crop_gdd_config WHERE crop_name = %s",
        (crop_name,),
    )
    row = cur.fetchone()
    cur.close()

    if row and row[0]:
        stages = row[0] if isinstance(row[0], list) else json.loads(row[0])
        total_gdd = float(row[1] or 2000)
        return stages

    # Default stages for common crops
    defaults = {
        "maize": [
            {"name": "emergence", "gdd": 100},
            {"name": "vegetative", "gdd": 500},
            {"name": "tasseling", "gdd": 1100},
            {"name": "silking", "gdd": 1200},
            {"name": "maturity", "gdd": 2500},
        ],
        "beans": [
            {"name": "emergence", "gdd": 80},
            {"name": "vegetative", "gdd": 300},
            {"name": "flowering", "gdd": 500},
            {"name": "pod_fill", "gdd": 800},
            {"name": "maturity", "gdd": 1400},
        ],
        "cassava": [
            {"name": "emergence", "gdd": 150},
            {"name": "vegetative", "gdd": 800},
            {"name": "tuber_init", "gdd": 1500},
            {"name": "bulking", "gdd": 3000},
            {"name": "maturity", "gdd": 4500},
        ],
        "sweet_potato": [
            {"name": "emergence", "gdd": 100},
            {"name": "vegetative", "gdd": 400},
            {"name": "tuber_init", "gdd": 800},
            {"name": "bulking", "gdd": 1500},
            {"name": "maturity", "gdd": 2200},
        ],
        "coffee": [
            {"name": "emergence", "gdd": 120},
            {"name": "vegetative", "gdd": 600},
            {"name": "flowering", "gdd": 1200},
            {"name": "cherry_development", "gdd": 2000},
            {"name": "maturity", "gdd": 3000},
        ],
    }
    return defaults.get(crop_name.lower(), defaults["maize"])


def get_current_stage(conn, crop_cycle_id: str) -> dict:
    """Get current growth stage based on accumulated GDD.
    
    Returns:
        dict with stage_name, accumulated_gdd, expected_gdd, 
        stage_index, total_stages, next_stage
    """
    cur = conn.cursor()

    # Get accumulated GDD
    gdd_data = accumulate_gdd(conn, crop_cycle_id)
    if "error" in gdd_data:
        cur.close()
        return gdd_data

    accumulated = gdd_data["accumulated_gdd"]
    crop_name = gdd_data["crop_name"]

    # Get stage definitions
    stages = get_crop_stages_from_config(conn, crop_name)
    cur.close()

    if not stages:
        return {
            "crop_cycle_id": crop_cycle_id,
            "stage_name": "unknown",
            "accumulated_gdd": accumulated,
        }

    current_stage = stages[0]
    current_index = 0

    for i, stage in enumerate(stages):
        if accumulated >= stage.get("gdd", 0):
            current_stage = stage
            current_index = i

    next_stage = stages[current_index + 1] if current_index + 1 < len(stages) else None

    return {
        "crop_cycle_id": crop_cycle_id,
        "crop_name": crop_name,
        "planting_date": gdd_data["planting_date"],
        "days_elapsed": gdd_data["days_elapsed"],
        "accumulated_gdd": accumulated,
        "stage_name": current_stage.get("name", "unknown"),
        "stage_gdd": current_stage.get("gdd", 0),
        "stage_index": current_index + 1,
        "total_stages": len(stages),
        "next_stage": next_stage.get("name") if next_stage else None,
        "next_stage_gdd": next_stage.get("gdd") if next_stage else None,
        "gdd_to_next_stage": (next_stage.get("gdd", 0) - accumulated) if next_stage else None,
        "pct_gdd_complete": gdd_data["pct_gdd_complete"],
    }


def detect_and_update_stages(conn, crop_cycle_id: str) -> dict:
    """Detect current stage and update crop_growth_stage table.
    
    Returns:
        dict with detected stage and update counts
    """
    cur = conn.cursor()

    stage_info = get_current_stage(conn, crop_cycle_id)
    if "error" in stage_info:
        cur.close()
        return stage_info

    crop_name = stage_info["crop_name"]
    stages = get_crop_stages_from_config(conn, crop_name)
    accumulated = stage_info["accumulated_gdd"]

    created = 0
    updated = 0

    for i, stage_def in enumerate(stages):
        stage_name = stage_def.get("name", f"stage_{i}")
        expected_gdd = stage_def.get("gdd", 0)

        # Determine status
        if accumulated >= expected_gdd:
            if i < len(stages) - 1 and accumulated >= stages[i + 1].get("gdd", float("inf")):
                stage_status = "completed"
            else:
                stage_status = "current"
        else:
            stage_status = "pending"

        # Upsert
        cur.execute(
            """
            INSERT INTO crop_growth_stage
                (crop_cycle_id, stage_name, stage_order, expected_gdd,
                 actual_gdd, status, detected_by)
            VALUES (%s, %s, %s, %s, %s, %s, 'gdd')
            ON CONFLICT (crop_cycle_id, stage_name) DO UPDATE SET
                actual_gdd = EXCLUDED.actual_gdd,
                status = EXCLUDED.status,
                updated_at = NOW()
            RETURNING (xmax = 0) AS inserted
            """,
            (crop_cycle_id, stage_name, i + 1, expected_gdd,
             accumulated if stage_status == "current" else (accumulated if stage_status == "completed" else None),
             stage_status),
        )
        result = cur.fetchone()
        if result and result[0]:
            created += 1
        else:
            updated += 1

    conn.commit()
    cur.close()

    return {
        "crop_cycle_id": crop_cycle_id,
        "current_stage": stage_info["stage_name"],
        "accumulated_gdd": accumulated,
        "stages_created": created,
        "stages_updated": updated,
    }


# ============================================================
# Stage Date Projection
# ============================================================

def estimate_stage_dates(conn, crop_cycle_id: str, weather_forecast: list[dict] = None) -> dict:
    """Project future growth stage dates using forecast or historical weather.
    
    Args:
        conn: Database connection
        crop_cycle_id: Crop cycle UUID
        weather_forecast: Optional list of daily forecast dicts with temp_max, temp_min
    
    Returns:
        dict with stage projections
    """
    cur = conn.cursor()

    # Get crop info
    cur.execute(
        """
        SELECT cc.planting_date, c.name, cg.total_gdd_required,
               cg.base_temp_c, cg.upper_temp_c
        FROM crop_cycle cc
        JOIN crop c ON c.id = cc.crop_id
        LEFT JOIN crop_gdd_config cg ON cg.crop_name = c.name
        WHERE cc.id = %s
        """,
        (crop_cycle_id,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": "Crop cycle not found"}

    planting_date, crop_name, total_gdd, base_temp, upper_temp = row
    total_gdd = float(total_gdd or 2000)
    base_temp = float(base_temp or 10.0)
    upper_temp = float(upper_temp or 30.0)

    if not planting_date:
        return {"error": "No planting date"}

    stages = get_crop_stages_from_config(conn, crop_name)

    # Get current accumulated GDD
    gdd_data = accumulate_gdd(conn, crop_cycle_id)
    accumulated = gdd_data.get("accumulated_gdd", 0)

    # Estimate GDD accumulation rate
    days_elapsed = (date.today() - planting_date).days
    avg_gdd_per_day = accumulated / max(days_elapsed, 1)

    # If forecast available, use it for more accurate future estimates
    future_gdd_per_day = avg_gdd_per_day
    if weather_forecast:
        forecast_gdds = []
        for day in weather_forecast:
            tmax = day.get("temp_max", day.get("temp_max_c", 25))
            tmin = day.get("temp_min", day.get("temp_min_c", 18))
            if tmax and tmin:
                gdd = compute_gdd(float(tmax), float(tmin), base_temp, upper_temp)
                forecast_gdds.append(gdd)
        if forecast_gdds:
            future_gdd_per_day = sum(forecast_gdds) / len(forecast_gdds)

    projections = []
    current_accumulated = accumulated

    for stage in stages:
        stage_gdd = stage.get("gdd", 0)
        stage_name = stage.get("name", "unknown")

        if current_accumulated >= stage_gdd:
            # Already reached
            projections.append({
                "stage": stage_name,
                "expected_gdd": stage_gdd,
                "status": "reached",
                "estimated_date": None,
                "days_remaining": 0,
            })
        else:
            gdd_needed = stage_gdd - current_accumulated
            days_to_go = int(gdd_needed / max(future_gdd_per_day, 0.1))
            est_date = date.today() + timedelta(days=days_to_go)
            projections.append({
                "stage": stage_name,
                "expected_gdd": stage_gdd,
                "status": "projected",
                "estimated_date": est_date.isoformat(),
                "days_remaining": days_to_go,
            })

    return {
        "crop_cycle_id": crop_cycle_id,
        "crop_name": crop_name,
        "planting_date": planting_date.isoformat(),
        "accumulated_gdd": accumulated,
        "gdd_per_day": round(future_gdd_per_day, 2),
        "projections": projections,
    }


# ============================================================
# Anomaly Detection
# ============================================================

def detect_schedule_anomalies(conn, location_id: str) -> list[dict]:
    """Detect crop cycles that are behind or ahead of schedule.
    
    Returns:
        list of anomaly dicts
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT cc.id, cc.planting_date, cc.status, c.name,
               cg.total_gdd_required
        FROM crop_cycle cc
        JOIN crop c ON c.id = cc.crop_id
        LEFT JOIN crop_gdd_config cg ON cg.crop_name = c.name
        WHERE cc.location_id = %s
          AND cc.status IN ('active', 'flowering')
        """,
        (location_id,),
    )
    cycles = cur.fetchall()
    cur.close()

    anomalies = []

    for cycle_id, planting_date, status, crop_name, total_gdd in cycles:
        total_gdd = float(total_gdd or 2000)
        days_elapsed = (date.today() - planting_date).days if planting_date else 0

        # Expected progress based on growing season
        expected_days = total_gdd / 15  # rough: ~15 GDD/day average
        expected_progress = min(days_elapsed / max(expected_days, 1), 1.0)

        gdd_data = accumulate_gdd(conn, cycle_id)
        actual_progress = gdd_data.get("pct_gdd_complete", 0) / 100

        deviation = actual_progress - expected_progress

        if abs(deviation) > 0.2:  # More than 20% deviation
            direction = "ahead" if deviation > 0 else "behind"
            severity = "critical" if abs(deviation) > 0.4 else "warning"
            anomalies.append({
                "crop_cycle_id": cycle_id,
                "crop_name": crop_name,
                "planting_date": planting_date.isoformat() if planting_date else None,
                "days_elapsed": days_elapsed,
                "expected_progress_pct": round(expected_progress * 100, 1),
                "actual_progress_pct": round(actual_progress * 100, 1),
                "deviation_pct": round(deviation * 100, 1),
                "direction": direction,
                "severity": severity,
                "accumulated_gdd": gdd_data.get("accumulated_gdd", 0),
                "total_gdd_required": total_gdd,
                "message": f"{crop_name} is {abs(round(deviation * 100))}% {direction} schedule",
            })

    return anomalies


# ============================================================
# List Stages
# ============================================================

def list_stages(conn, crop_name: str) -> list[dict]:
    """List all growth stages for a crop type."""
    stages = get_crop_stages_from_config(conn, crop_name)
    return [
        {
            "stage": s.get("name", f"stage_{i}"),
            "order": i + 1,
            "gdd_threshold": s.get("gdd", 0),
        }
        for i, s in enumerate(stages)
    ]


def get_current_stages_all(conn, location_id: str) -> list[dict]:
    """Get current growth stage for all active crop cycles at a location."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM crop_cycle WHERE location_id = %s AND status IN ('active', 'flowering')",
        (location_id,),
    )
    cycle_ids = [row[0] for row in cur.fetchall()]
    cur.close()

    results = []
    for cycle_id in cycle_ids:
        stage = get_current_stage(conn, cycle_id)
        if "error" not in stage:
            results.append(stage)

    return results


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Crop phenology — GDD tracking and growth stage detection"
    )
    sub = parser.add_subparsers(dest="command")

    # Accumulate GDD
    acc_parser = sub.add_parser("accumulate", help="Accumulate GDD for a crop cycle")
    acc_parser.add_argument("--crop-cycle-id", required=True, help="Crop cycle UUID")
    acc_parser.add_argument("--json", action="store_true", help="JSON output")

    # Detect stage
    detect_parser = sub.add_parser("detect-stage", help="Detect and update current growth stage")
    detect_parser.add_argument("--crop-cycle-id", required=True, help="Crop cycle UUID")
    detect_parser.add_argument("--json", action="store_true", help="JSON output")

    # Project stages
    proj_parser = sub.add_parser("project", help="Project future stage dates")
    proj_parser.add_argument("--crop-cycle-id", required=True, help="Crop cycle UUID")
    proj_parser.add_argument("--json", action="store_true", help="JSON output")

    # Anomalies
    anom_parser = sub.add_parser("anomalies", help="Detect schedule anomalies")
    anom_parser.add_argument("--location-id", required=True, help="Location UUID")
    anom_parser.add_argument("--json", action="store_true", help="JSON output")

    # List stages
    list_parser = sub.add_parser("list-stages", help="List growth stages for a crop")
    list_parser.add_argument("--crop", required=True, help="Crop name")
    list_parser.add_argument("--json", action="store_true", help="JSON output")

    # Current stages
    current_parser = sub.add_parser("current", help="Current stage for all active crops")
    current_parser.add_argument("--location-id", required=True, help="Location UUID")
    current_parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    from .base import get_db

    if args.command in ("accumulate", "detect-stage", "project", "anomalies", "current"):
        db = get_db()

    try:
        if args.command == "accumulate":
            result = accumulate_gdd(db, args.crop_cycle_id)
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Crop: {result.get('crop_name', '?')}")
                print(f"  Planting date: {result.get('planting_date', '?')}")
                print(f"  Days elapsed: {result.get('days_elapsed', 0)}")
                print(f"  Accumulated GDD: {result.get('accumulated_gdd', 0)}")
                print(f"  Total GDD required: {result.get('total_gdd_required', '?')}")
                print(f"  % Complete: {result.get('pct_gdd_complete', 0)}%")
                print(f"  GDD rate: {result.get('gdd_rate', 0)}/day")

        elif args.command == "detect-stage":
            result = detect_and_update_stages(db, args.crop_cycle_id)
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Current stage: {result.get('current_stage', '?')}")
                print(f"  Accumulated GDD: {result.get('accumulated_gdd', 0)}")
                print(f"  Stages created: {result.get('stages_created', 0)}")
                print(f"  Stages updated: {result.get('stages_updated', 0)}")

        elif args.command == "project":
            result = estimate_stage_dates(db, args.crop_cycle_id)
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Crop: {result.get('crop_name', '?')}")
                print(f"  Accumulated GDD: {result.get('accumulated_gdd', 0)}")
                print(f"  GDD/day: {result.get('gdd_per_day', 0)}")
                for proj in result.get("projections", []):
                    status = "✓" if proj["status"] == "reached" else "→"
                    date_str = proj.get("estimated_date", "done")
                    print(f"  {status} {proj['stage']}: {proj['expected_gdd']} GDD"
                          f" — {date_str} ({proj.get('days_remaining', 0)} days)")

        elif args.command == "anomalies":
            anomalies = detect_schedule_anomalies(db, args.location_id)
            if args.json:
                print(json.dumps(anomalies, indent=2, default=str))
            else:
                if not anomalies:
                    print("No schedule anomalies detected.")
                for a in anomalies:
                    icon = "⚠" if a["severity"] == "warning" else "🔴"
                    print(f"  {icon} {a['message']}")
                    print(f"    Expected: {a['expected_progress_pct']}%, "
                          f"Actual: {a['actual_progress_pct']}%")

        elif args.command == "list-stages":
            stages = list_stages(db, args.crop)
            if args.json:
                print(json.dumps(stages, indent=2))
            else:
                print(f"Growth stages for {args.crop}:")
                for s in stages:
                    print(f"  {s['order']}. {s['stage']}: {s['gdd_threshold']} GDD")

        elif args.command == "current":
            results = get_current_stages_all(db, args.location_id)
            if args.json:
                print(json.dumps(results, indent=2, default=str))
            else:
                if not results:
                    print("No active crop cycles found.")
                for r in results:
                    print(f"{r['crop_name']}: {r['stage_name']}"
                          f" ({r['accumulated_gdd']} GDD, {r['pct_gdd_complete']}%)")

        else:
            parser.print_help()

    finally:
        if args.command in ("accumulate", "detect-stage", "project", "anomalies", "current"):
            db.close()


if __name__ == "__main__":
    main()
