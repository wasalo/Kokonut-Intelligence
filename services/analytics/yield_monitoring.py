#!/usr/bin/env python3
"""
Yield Monitoring

Records harvest yields, computes trends, predicts future yields,
and compares against historical benchmarks.

Usage:
    python -m services.analytics.yield_monitoring record --location-id UUID --yield 2500 --area 1.5 --crop maize
    python -m services.analytics.yield_monitoring summary --location-id UUID
    python -m services.analytics.yield_monitoring trend --location-id UUID --crop maize
    python -m services.analytics.yield_monitoring predict --location-id UUID --crop maize --days 60
    python -m services.analytics.yield_monitoring benchmark --location-id UUID --crop maize
"""

import argparse
import json
import math
import uuid
from datetime import datetime, date, timezone
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.yield_monitoring")


# ============================================================
# Yield Recording
# ============================================================

def record_yield_observation(
    conn,
    location_id: str,
    yield_amount: float,
    area_ha: float = 1.0,
    crop_name: str = "maize",
    variety: str = None,
    harvest_date: date = None,
    moisture_pct: float = None,
    grade: str = None,
    source_type: str = "manual",
    source_system: str = None,
    source_id: str = None,
    metadata: dict = None,
) -> dict:
    """Record a harvest yield observation."""
    cur = conn.cursor()
    obs_id = str(uuid.uuid4())

    harvest_date = harvest_date or date.today()
    total_yield = yield_amount * area_ha

    cur.execute(
        """
        INSERT INTO harvest_yield_observation
            (id, location_id, harvest_date, crop_name, variety,
             yield_amount, yield_unit, area_ha, total_yield,
             moisture_content_pct, grade, source_type, source_system, source_id,
             metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'kg/ha', %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
        RETURNING id
        """,
        (
            obs_id, location_id, harvest_date, crop_name, variety,
            yield_amount, area_ha, total_yield,
            moisture_pct, grade, source_type, source_system, source_id,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    return {
        "observation_id": obs_id,
        "location_id": location_id,
        "crop_name": crop_name,
        "yield_kg_ha": yield_amount,
        "area_ha": area_ha,
        "total_yield_kg": round(total_yield, 2),
        "harvest_date": harvest_date.isoformat(),
    }


# ============================================================
# Yield Summary
# ============================================================

def get_yield_summary(conn, location_id: str) -> dict:
    """Get yield summary statistics for a location."""
    cur = conn.cursor()

    # By crop
    cur.execute(
        """
        SELECT crop_name,
               COUNT(*) AS observations,
               AVG(yield_amount) AS avg_yield,
               MIN(yield_amount) AS min_yield,
               MAX(yield_amount) AS max_yield,
               STDDEV(yield_amount) AS stddev_yield,
               SUM(total_yield) AS total_production
        FROM harvest_yield_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY crop_name
        ORDER BY total_production DESC NULLS LAST
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    crops = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Recent harvests
    cur.execute(
        """
        SELECT harvest_date, crop_name, yield_amount, area_ha, total_yield, grade
        FROM harvest_yield_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        ORDER BY harvest_date DESC LIMIT 10
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    recent = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Overall
    cur.execute(
        """
        SELECT COUNT(*), SUM(total_yield), AVG(yield_amount),
               MIN(harvest_date), MAX(harvest_date)
        FROM harvest_yield_observation
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "total_observations": int(row[0]) if row[0] else 0,
        "total_production_kg": float(row[1]) if row[1] else 0,
        "overall_avg_yield": round(float(row[2]), 2) if row[2] else 0,
        "first_harvest": row[3].isoformat() if row[3] else None,
        "last_harvest": row[4].isoformat() if row[4] else None,
        "crops": crops,
        "recent_harvests": recent,
    }


# ============================================================
# Yield Trend
# ============================================================

def compute_yield_trend(conn, location_id: str, crop_name: str = None) -> dict:
    """Compute yield trend over time (linear regression)."""
    cur = conn.cursor()

    where = "location_id = %s AND status IN ('verified', 'published')"
    params = [location_id]
    if crop_name:
        where += " AND crop_name = %s"
        params.append(crop_name)

    cur.execute(
        f"""
        SELECT EXTRACT(EPOCH FROM harvest_date) / 86400.0 AS day_num,
               yield_amount, harvest_date, crop_name
        FROM harvest_yield_observation
        WHERE {where}
        ORDER BY harvest_date
        """,
        tuple(params),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    if len(rows) < 2:
        return {
            "location_id": location_id,
            "crop_name": crop_name,
            "data_points": len(rows),
            "trend": "insufficient_data",
        }

    # Linear regression
    n = len(rows)
    x = [float(r["day_num"]) for r in rows]
    y = [float(r["yield_amount"]) for r in rows]
    x_mean = sum(x) / n
    y_mean = sum(y) / n

    ss_xx = sum((xi - x_mean) ** 2 for xi in x)
    ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))

    if ss_xx == 0:
        slope = 0
    else:
        slope = ss_xy / ss_xx

    intercept = y_mean - slope * x_mean

    # R² calculation
    y_pred = [slope * xi + intercept for xi in x]
    ss_res = sum((yi - yp) ** 2 for yi, yp in zip(y, y_pred))
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    # Convert slope to per-month
    slope_per_month = slope * 30

    # Determine trend direction
    if abs(slope_per_month) < 0.5:
        direction = "stable"
    elif slope_per_month > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return {
        "location_id": location_id,
        "crop_name": crop_name or "all",
        "data_points": n,
        "trend": direction,
        "slope_per_month": round(slope_per_month, 4),
        "r_squared": round(r_squared, 4),
        "avg_yield": round(y_mean, 2),
        "first_yield": round(y[0], 2),
        "last_yield": round(y[-1], 2),
        "change_pct": round((y[-1] - y[0]) / max(y[0], 0.01) * 100, 1),
    }


# ============================================================
# Yield Prediction
# ============================================================

def predict_yield(
    conn,
    location_id: str,
    crop_name: str = "maize",
    days_to_harvest: int = 60,
) -> dict:
    """Predict yield based on historical data and current conditions."""
    cur = conn.cursor()

    # Get historical average
    cur.execute(
        """
        SELECT AVG(yield_amount), STDDEV(yield_amount), COUNT(*)
        FROM harvest_yield_observation
        WHERE location_id = %s AND crop_name = %s
          AND status IN ('verified', 'published')
        """,
        (location_id, crop_name),
    )
    row = cur.fetchone()
    hist_avg = float(row[0]) if row and row[0] else 1500.0
    hist_std = float(row[1]) if row and row[1] else hist_avg * 0.2
    hist_count = int(row[2]) if row and row[2] else 0

    # Get current GDD
    cur.execute(
        """
        SELECT SUM(gdd_accumulated)
        FROM crop_growth_stage
        WHERE location_id = %s AND crop_name = %s
          AND status = 'completed'
        """,
        (location_id, crop_name),
    )
    gdd_row = cur.fetchone()
    current_gdd = float(gdd_row[0]) if gdd_row and gdd_row[0] else 0

    # Get recent weather conditions
    cur.execute(
        """
        SELECT AVG(temperature_c), SUM(precipitation_mm)
        FROM weather_observation
        WHERE location_id = %s
          AND observation_date >= CURRENT_DATE - 30
        """,
        (location_id,),
    )
    weather_row = cur.fetchone()
    avg_temp = float(weather_row[0]) if weather_row and weather_row[0] else 25.0
    rainfall_30d = float(weather_row[1]) if weather_row and weather_row[1] else 50.0

    cur.close()

    # Simple regression model
    # Yield = base_avg × gdd_factor × weather_factor × trend_factor
    gdd_factor = min(max(current_gdd / 1500.0, 0.5), 1.5) if current_gdd > 0 else 0.7
    weather_factor = min(max(rainfall_30d / 60.0, 0.5), 1.3)
    predicted = hist_avg * gdd_factor * weather_factor

    # Confidence interval (based on historical variability)
    ci_low = max(predicted - 1.96 * hist_std, 0)
    ci_high = predicted + 1.96 * hist_std

    confidence = 0.7 if hist_count >= 5 else 0.5 if hist_count >= 2 else 0.3

    return {
        "location_id": location_id,
        "crop_name": crop_name,
        "predicted_yield_kg_ha": round(predicted, 2),
        "confidence_low": round(ci_low, 2),
        "confidence_high": round(ci_high, 2),
        "confidence_level": 0.95,
        "confidence": confidence,
        "days_to_harvest": days_to_harvest,
        "inputs": {
            "historical_avg": round(hist_avg, 2),
            "current_gdd": round(current_gdd, 2),
            "rainfall_30d_mm": round(rainfall_30d, 2),
            "avg_temp_c": round(avg_temp, 2),
        },
        "model": "ensemble_simple",
    }


# ============================================================
# Benchmark Comparison
# ============================================================

def compare_benchmark(conn, location_id: str, crop_name: str = None) -> dict:
    """Compare yield against historical benchmarks."""
    cur = conn.cursor()

    where_bench = "location_id = %s AND crop_name = %s"
    params = [location_id, crop_name]
    if not crop_name:
        where_bench = "location_id = %s"
        params = [location_id]

    cur.execute(
        f"""
        SELECT benchmark_type, AVG(yield_value) AS benchmark_yield
        FROM yield_benchmark
        WHERE {where_bench}
        GROUP BY benchmark_type
        """,
        tuple(params),
    )
    cols = [d[0] for d in cur.description]
    benchmarks = {row[0]: float(row[1]) for row in cur.fetchall()}

    # Current yield
    where_yield = "location_id = %s AND status IN ('verified', 'published')"
    y_params = [location_id]
    if crop_name:
        where_yield += " AND crop_name = %s"
        y_params.append(crop_name)

    cur.execute(
        f"SELECT AVG(yield_amount) FROM harvest_yield_observation WHERE {where_yield}",
        tuple(y_params),
    )
    row = cur.fetchone()
    current_avg = float(row[0]) if row and row[0] else None
    cur.close()

    comparisons = {}
    if current_avg is not None:
        for btype, bval in benchmarks.items():
            if bval > 0:
                pct_diff = (current_avg - bval) / bval * 100
                comparisons[btype] = {
                    "benchmark": round(bval, 2),
                    "current": round(current_avg, 2),
                    "difference_pct": round(pct_diff, 1),
                    "status": "above" if pct_diff > 0 else "below" if pct_diff < 0 else "at",
                }

    return {
        "location_id": location_id,
        "crop_name": crop_name,
        "current_avg_yield": round(current_avg, 2) if current_avg else None,
        "benchmarks": comparisons,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Yield monitoring")
    sub = parser.add_subparsers(dest="command")

    # Record
    rec = sub.add_parser("record", help="Record yield observation")
    rec.add_argument("--location-id", required=True)
    rec.add_argument("--yield-amount", type=float, required=True, help="Yield in kg/ha")
    rec.add_argument("--area", type=float, default=1.0, help="Area in hectares")
    rec.add_argument("--crop", default="maize")
    rec.add_argument("--variety")
    rec.add_argument("--date", help="Harvest date YYYY-MM-DD")
    rec.add_argument("--moisture", type=float, help="Moisture content %")
    rec.add_argument("--grade")
    rec.add_argument("--json", action="store_true")

    # Summary
    sm = sub.add_parser("summary", help="Yield summary")
    sm.add_argument("--location-id", required=True)
    sm.add_argument("--json", action="store_true")

    # Trend
    tr = sub.add_parser("trend", help="Yield trend")
    tr.add_argument("--location-id", required=True)
    tr.add_argument("--crop")
    tr.add_argument("--json", action="store_true")

    # Predict
    pr = sub.add_parser("predict", help="Predict yield")
    pr.add_argument("--location-id", required=True)
    pr.add_argument("--crop", default="maize")
    pr.add_argument("--days", type=int, default=60)
    pr.add_argument("--json", action="store_true")

    # Benchmark
    bm = sub.add_parser("benchmark", help="Compare benchmarks")
    bm.add_argument("--location-id", required=True)
    bm.add_argument("--crop")
    bm.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from services.common.database import get_db

    if args.command in ("record", "summary", "trend", "predict", "benchmark"):
        db = get_db()
    else:
        parser.print_help()
        return

    try:
        if args.command == "record":
            hd = date.fromisoformat(args.date) if args.date else None
            result = record_yield_observation(
                db, args.location_id, args.yield_amount, args.area, args.crop,
                harvest_date=hd, moisture_pct=args.moisture, grade=args.grade,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_record(result)
            print(output)

        elif args.command == "summary":
            result = get_yield_summary(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_summary(result)
            print(output)

        elif args.command == "trend":
            result = compute_yield_trend(db, args.location_id, args.crop)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_trend(result)
            print(output)

        elif args.command == "predict":
            result = predict_yield(db, args.location_id, args.crop, args.days)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_predict(result)
            print(output)

        elif args.command == "benchmark":
            result = compare_benchmark(db, args.location_id, args.crop)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_benchmark(result)
            print(output)

    finally:
        db.close()


def _format_record(r: dict) -> str:
    return f"Recorded: {r['crop_name']} {r['yield_kg_ha']} kg/ha × {r['area_ha']} ha = {r['total_yield_kg']} kg ({r['harvest_date']})"


def _format_summary(r: dict) -> str:
    lines = [f"Yield Summary — {r['location_id'][:8]}... ({r['total_observations']} observations)"]
    for c in r["crops"]:
        lines.append(f"  {c['crop_name']:20s} avg={c['avg_yield']:.0f} kg/ha  total={c['total_production']:.0f} kg  n={c['observations']}")
    return "\n".join(lines) if len(lines) > 1 else "No yield data."


def _format_trend(r: dict) -> str:
    if r["trend"] == "insufficient_data":
        return f"Trend: Insufficient data ({r['data_points']} points)"
    arrow = "↑" if r["trend"] == "increasing" else "↓" if r["trend"] == "decreasing" else "→"
    return (
        f"Yield Trend — {r['crop_name']} ({r['data_points']} points)\n"
        f"  Direction: {arrow} {r['trend']}\n"
        f"  Slope: {r['slope_per_month']:.2f} kg/ha/month\n"
        f"  R²: {r['r_squared']:.3f}\n"
        f"  Change: {r['change_pct']}%"
    )


def _format_predict(r: dict) -> str:
    return (
        f"Yield Prediction — {r['crop_name']}\n"
        f"  Predicted: {r['predicted_yield_kg_ha']} kg/ha\n"
        f"  Range: {r['confidence_low']} – {r['confidence_high']} kg/ha\n"
        f"  Days to harvest: {r['days_to_harvest']}\n"
        f"  Confidence: {r['confidence']:.0%}"
    )


def _format_benchmark(r: dict) -> str:
    lines = [f"Benchmark — {r['crop_name']} at {r['location_id'][:8]}..."]
    if not r["benchmarks"]:
        lines.append("  No benchmarks available.")
    for btype, comp in r["benchmarks"].items():
        icon = "▲" if comp["status"] == "above" else "▼" if comp["status"] == "below" else "="
        lines.append(f"  {icon} {btype}: {comp['current']:.0f} vs {comp['benchmark']:.0f} ({comp['difference_pct']:+.1f}%)")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
