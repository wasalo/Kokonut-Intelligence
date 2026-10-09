#!/usr/bin/env python3
"""
Prescription Maps — Variable Rate Technology (VRT)

Generates prescription maps from soil, sensor, and remote sensing data.
Classifies fields into rate zones and computes material estimates.

Usage:
    python -m services.analytics.prescription --generate --location-id UUID --plot-id UUID --input fertilizer
    python -m services.analytics.prescription --list --location-id UUID
    python -m services.analytics.prescription --approve --prescription-id UUID --approved-by admin
    python -m services.analytics.prescription --estimate --prescription-id UUID
"""

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.prescription")


# ============================================================
# Rate Classification
# ============================================================

def classify_rates_natural_breaks(values: list[float], n_classes: int = 5) -> list[dict]:
    """Classify values into rate classes using natural breaks (simplified Jenks).
    
    Uses a greedy approach: sort values, find gaps, split into n_classes.
    """
    if not values or n_classes <= 0:
        return []

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    if n <= n_classes:
        # Each value is its own class
        return [
            {"class_index": i, "min": v, "max": v, "rate": v}
            for i, v in enumerate(sorted_vals)
        ]

    # Find n_classes-1 break points by maximizing within-class variance reduction
    # Simplified: use quantile-based breaks
    breaks = []
    for i in range(1, n_classes):
        idx = int(n * i / n_classes)
        breaks.append(sorted_vals[min(idx, n - 1)])

    classes = []
    prev = sorted_vals[0]
    for i, brk in enumerate(breaks):
        class_vals = [v for v in sorted_vals if prev <= v <= brk]
        if class_vals:
            classes.append({
                "class_index": i,
                "min": min(class_vals),
                "max": max(class_vals),
                "rate": sum(class_vals) / len(class_vals),
            })
        prev = brk + 0.001

    # Last class
    class_vals = [v for v in sorted_vals if v >= breaks[-1]]
    if class_vals:
        classes.append({
            "class_index": len(breaks),
            "min": min(class_vals),
            "max": max(class_vals),
            "rate": sum(class_vals) / len(class_vals),
        })

    return classes


def classify_rates_equal_interval(values: list[float], n_classes: int = 5) -> list[dict]:
    """Classify values into equal-interval classes."""
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)
    if min_val == max_val:
        return [{"class_index": 0, "min": min_val, "max": max_val, "rate": min_val}]

    interval = (max_val - min_val) / n_classes
    classes = []
    for i in range(n_classes):
        low = min_val + i * interval
        high = min_val + (i + 1) * interval
        class_vals = [v for v in values if low <= v < high or (i == n_classes - 1 and v == high)]
        if class_vals:
            classes.append({
                "class_index": i,
                "min": round(low, 4),
                "max": round(high, 4),
                "rate": round(sum(class_vals) / len(class_vals), 4),
            })
    return classes


# ============================================================
# Application Rate Computation
# ============================================================

# Default rate recommendations (crop × input × soil level)
FERTILIZER_RATES = {
    "maize": {
        "nitrogen": {
            "low": {"initial": 30, "development": 60, "mid": 90, "late": 30},
            "medium": {"initial": 50, "development": 80, "mid": 110, "late": 40},
            "high": {"initial": 70, "development": 100, "mid": 130, "late": 50},
        },
        "phosphorus": {"low": 40, "medium": 60, "high": 80},
        "potassium": {"low": 20, "medium": 35, "high": 50},
    },
    "beans": {
        "nitrogen": {
            "low": 15, "medium": 30, "high": 45,
        },
        "phosphorus": {"low": 30, "medium": 50, "high": 70},
        "potassium": {"low": 15, "medium": 25, "high": 40},
    },
    "cassava": {
        "nitrogen": {"low": 20, "medium": 40, "high": 60},
        "phosphorus": {"low": 25, "medium": 40, "high": 60},
        "potassium": {"low": 30, "medium": 50, "high": 70},
    },
    "default": {
        "nitrogen": {"low": 25, "medium": 50, "high": 75},
        "phosphorus": {"low": 30, "medium": 50, "high": 70},
        "potassium": {"low": 20, "medium": 35, "high": 50},
    },
}

IRRIGATION_RATES = {
    "low": 15,    # mm — deficit zone needs more
    "medium": 10,  # mm — moderate zone
    "high": 5,     # mm — surplus zone needs less
}

SEED_RATES = {
    "maize": {"low": 6.0, "medium": 7.5, "high": 9.0},   # seeds/m²
    "beans": {"low": 10.0, "medium": 15.0, "high": 20.0},
    "cassava": {"low": 0.8, "medium": 1.0, "high": 1.2},
    "default": {"low": 5.0, "medium": 8.0, "high": 10.0},
}


def compute_application_rate(
    basis_value: float,
    crop_name: str,
    input_type: str,
    growth_stage: str = "mid",
    soil_classes: list[dict] = None,
) -> dict:
    """Compute application rate from basis value and context.
    
    Args:
        basis_value: Measured/predicted value (e.g., soil_N ppm, soil_moisture %)
        crop_name: Crop name
        input_type: 'fertilizer', 'irrigation', 'seed', 'pesticide'
        growth_stage: Current growth stage
        soil_classes: Classification results from classify_rates()
    
    Returns:
        dict with rate, unit, level, confidence
    """
    crop_lc = crop_name.lower().strip()
    crop_rates = FERTILIZER_RATES.get(crop_lc, FERTILIZER_RATES["default"])

    # Determine level from soil_classes
    level = "medium"
    if soil_classes:
        for cls in soil_classes:
            if cls["min"] <= basis_value <= cls["max"]:
                # Low basis value → high application rate (inverse relationship for nutrients)
                if cls["class_index"] == 0:
                    level = "high"
                elif cls["class_index"] == len(soil_classes) - 1:
                    level = "low"
                else:
                    level = "medium"
                break

    if input_type == "fertilizer":
        rates = crop_rates.get("nitrogen", crop_rates.get("nitrogen", 50))
        if isinstance(rates, dict) and growth_stage in rates:
            rate = rates[growth_stage]
        elif isinstance(rates, dict):
            rate = list(rates.values())[len(rates) // 2]
        else:
            rate = rates
        unit = "kg N/ha"
    elif input_type == "irrigation":
        rate = IRRIGATION_RATES.get(level, 10)
        unit = "mm"
    elif input_type == "seed":
        seed_rates = SEED_RATES.get(crop_lc, SEED_RATES["default"])
        rate = seed_rates.get(level, 8.0)
        unit = "seeds/m2"
    else:
        rate = 0
        unit = "units/ha"

    return {
        "rate": rate,
        "unit": unit,
        "level": level,
        "basis_value": basis_value,
        "confidence": 0.8 if soil_classes else 0.5,
    }


# ============================================================
# Prescription Map Generation
# ============================================================

def generate_prescription_map(
    conn,
    location_id: str,
    plot_id: str = None,
    input_type: str = "fertilizer",
    basis_metric: str = "soil_nitrogen",
    crop_cycle_id: str = None,
) -> dict:
    """Generate a prescription map from available data.
    
    Args:
        conn: Database connection
        location_id: Location UUID
        plot_id: Optional plot UUID (if None, uses all plots)
        input_type: fertilizer, irrigation, seed
        basis_metric: soil_nitrogen, soil_moisture, ndvi, yield_potential
        crop_cycle_id: Optional crop cycle UUID
    
    Returns:
        dict with prescription_map record and zones
    """
    cur = conn.cursor()

    # Get crop info
    crop_name = "default"
    growth_stage = "mid"
    if crop_cycle_id:
        cur.execute(
            """
            SELECT c.name, cc.status FROM crop_cycle cc
            JOIN crop c ON c.id = cc.crop_id WHERE cc.id = %s
            """,
            (crop_cycle_id,),
        )
        row = cur.fetchone()
        if row:
            crop_name, growth_stage = row[0], row[1] or "mid"

    # Get basis values from the appropriate source
    basis_values = _get_basis_values(conn, location_id, plot_id, basis_metric)

    if not basis_values:
        cur.close()
        return {"error": f"No {basis_metric} data available for this location"}

    # Classify into rate zones
    values = [b["value"] for b in basis_values]
    soil_classes = classify_rates_natural_breaks(values, n_classes=min(5, len(values)))

    # Compute rates for each data point
    rate_data = []
    for bv in basis_values:
        rate_result = compute_application_rate(
            bv["value"], crop_name, input_type, growth_stage, soil_classes
        )
        rate_data.append({
            **bv,
            "rate": rate_result["rate"],
            "unit": rate_result["unit"],
            "level": rate_result["level"],
            "confidence": rate_result["confidence"],
        })

    # Compute statistics
    rates = [r["rate"] for r in rate_data]
    avg_rate = sum(rates) / len(rates) if rates else 0
    min_rate = min(rates) if rates else 0
    max_rate = max(rates) if rates else 0

    # Estimate total volume (assume 1 ha grid for now)
    total_area_ha = len(rates) * 0.01  # rough: each data point ~ 0.01 ha
    total_volume = sum(r["rate"] * 0.01 for r in rate_data)

    # Get material cost
    material_cost = _get_material_cost(conn, location_id, input_type)
    estimated_cost = total_volume * material_cost if material_cost else None

    # Create prescription map record
    prescription_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO prescription_map
            (id, location_id, plot_id, crop_cycle_id, input_type, basis_metric,
             basis_source, unit, total_area_ha, avg_rate, min_rate, max_rate,
             total_volume, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s::jsonb)
        RETURNING id
        """,
        (
            prescription_id, location_id, plot_id, crop_cycle_id,
            input_type, basis_metric, "sensor_analysis",
            rate_data[0]["unit"] if rate_data else "units/ha",
            total_area_ha, avg_rate, min_rate, max_rate, total_volume,
            json.dumps({"crop_name": crop_name, "growth_stage": growth_stage,
                        "n_data_points": len(rate_data),
                        "estimated_cost_usd": estimated_cost}),
        ),
    )

    # Create zone records
    for rd in rate_data:
        zone_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO prescription_zone
                (id, prescription_map_id, zone_name, zone_class, area_m2,
                 application_rate, application_unit, basis_value, confidence,
                 material_cost_usd, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                zone_id, prescription_id,
                f"Zone {rd.get('level', 'unknown').title()}",
                rd.get("level", "medium"),
                100.0,  # default zone area
                rd["rate"], rd["unit"],
                rd["value"], rd["confidence"],
                rd["rate"] * 0.01 * material_cost if material_cost else None,
                json.dumps({"source_id": str(rd.get("source_id", ""))}),
            ),
        )

    conn.commit()
    cur.close()

    return {
        "prescription_id": prescription_id,
        "location_id": location_id,
        "plot_id": plot_id,
        "input_type": input_type,
        "basis_metric": basis_metric,
        "crop_name": crop_name,
        "n_zones": len(rate_data),
        "avg_rate": round(avg_rate, 2),
        "min_rate": round(min_rate, 2),
        "max_rate": round(max_rate, 2),
        "total_volume": round(total_volume, 2),
        "estimated_cost_usd": round(estimated_cost, 2) if estimated_cost else None,
        "status": "draft",
    }


def _get_basis_values(conn, location_id: str, plot_id: str = None,
                       basis_metric: str = "soil_nitrogen") -> list[dict]:
    """Get basis values from the appropriate data source."""
    cur = conn.cursor()
    results = []

    if basis_metric == "soil_nitrogen":
        query = """
            SELECT id, location_id, plot_id, nitrogen_ppm AS value,
                   'soil_sample' AS source
            FROM soil_sample
            WHERE location_id = %s AND nitrogen_ppm IS NOT NULL
        """
        params = [location_id]
        if plot_id:
            query += " AND plot_id = %s"
            params.append(plot_id)
        query += " ORDER BY sample_date DESC LIMIT 100"
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]

    elif basis_metric == "soil_moisture":
        query = """
            SELECT id, location_id, plot_id, value AS value,
                   'sensor_reading' AS source
            FROM sensor_reading
            WHERE location_id = %s AND sensor_type = 'soil_moisture'
        """
        params = [location_id]
        if plot_id:
            query += " AND plot_id = %s"
            params.append(plot_id)
        query += " ORDER BY reading_date DESC LIMIT 100"
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]

    elif basis_metric == "ndvi":
        query = """
            SELECT id, location_id, plot_id, ndvi AS value,
                   'remote_sensing' AS source
            FROM remote_sensing_observation
            WHERE location_id = %s AND ndvi IS NOT NULL
        """
        params = [location_id]
        if plot_id:
            query += " AND plot_id = %s"
            params.append(plot_id)
        query += " ORDER BY observation_date DESC LIMIT 100"
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]

    elif basis_metric == "soil_ph":
        query = """
            SELECT id, location_id, plot_id, ph AS value,
                   'soil_sample' AS source
            FROM soil_sample
            WHERE location_id = %s AND ph IS NOT NULL
        """
        params = [location_id]
        if plot_id:
            query += " AND plot_id = %s"
            params.append(plot_id)
        query += " ORDER BY sample_date DESC LIMIT 100"
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.close()
    return results


def _get_material_cost(conn, location_id: str, input_type: str) -> Optional[float]:
    """Get material cost per unit for the location and input type."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cost_per_unit, unit FROM material_cost
        WHERE location_id = %s AND input_type = %s
        ORDER BY effective_date DESC LIMIT 1
        """,
        (location_id, input_type),
    )
    row = cur.fetchone()
    cur.close()
    return float(row[0]) if row else None


# ============================================================
# Prescription Management
# ============================================================

def list_prescriptions(conn, location_id: str, status: str = None) -> list[dict]:
    """List prescriptions for a location."""
    cur = conn.cursor()
    query = """
        SELECT pm.id, pm.input_type, pm.basis_metric, pm.unit,
               pm.total_area_ha, pm.avg_rate, pm.total_volume,
               pm.status, pm.generated_at, pm.approved_at,
               COUNT(pz.id) AS zone_count,
               SUM(COALESCE(pz.material_cost_usd, 0)) AS est_cost
        FROM prescription_map pm
        LEFT JOIN prescription_zone pz ON pz.prescription_map_id = pm.id
        WHERE pm.location_id = %s
    """
    params = [location_id]
    if status:
        query += " AND pm.status = %s"
        params.append(status)
    query += " GROUP BY pm.id ORDER BY pm.generated_at DESC"
    cur.execute(query, params)
    cols = [desc[0] for desc in cur.description]
    results = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return results


def approve_prescription(conn, prescription_id: str, approved_by: str) -> dict:
    """Approve a prescription map (draft → approved)."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE prescription_map
        SET status = 'approved', approved_by = %s, approved_at = NOW(), updated_at = NOW()
        WHERE id = %s AND status = 'draft'
        RETURNING id, input_type, total_volume
        """,
        (approved_by, prescription_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"error": "Prescription not found or not in draft status"}

    return {
        "prescription_id": str(row[0]),
        "input_type": row[1],
        "total_volume": float(row[2]) if row[2] else 0,
        "status": "approved",
    }


def get_material_estimate(conn, prescription_id: str) -> dict:
    """Get material and cost estimate for a prescription."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pm.input_type, pm.unit, pm.total_volume, pm.total_area_ha,
               pm.avg_rate, mc.cost_per_unit, mc.unit AS cost_unit
        FROM prescription_map pm
        LEFT JOIN material_cost mc ON mc.location_id = pm.location_id
            AND mc.input_type = pm.input_type
            AND mc.effective_date = (
                SELECT MAX(effective_date) FROM material_cost
                WHERE location_id = pm.location_id AND input_type = pm.input_type
            )
        WHERE pm.id = %s
        """,
        (prescription_id,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": "Prescription not found"}

    input_type, unit, total_volume, total_area_ha, avg_rate, cost_per_unit, cost_unit = row

    total_cost = float(total_volume) * float(cost_per_unit) if cost_per_unit and total_volume else None

    return {
        "prescription_id": prescription_id,
        "input_type": input_type,
        "unit": unit,
        "total_volume": float(total_volume) if total_volume else 0,
        "total_area_ha": float(total_area_ha) if total_area_ha else 0,
        "avg_rate": float(avg_rate) if avg_rate else 0,
        "cost_per_unit": float(cost_per_unit) if cost_per_unit else None,
        "total_cost_usd": round(total_cost, 2) if total_cost else None,
    }


# ============================================================
# CLI
# ============================================================

cli = CommandLine("prescription", "Prescription map management (VRT)")


def _render(result, args, human):
    print(json.dumps(result, indent=2, default=str) if args.json else human(result))


def _format_prescription(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    lines = [
        f"Prescription {r.get('prescription_id', '?')[:8]}...",
        f"  Input: {r.get('input_type', '?')}",
        f"  Zones: {r.get('n_zones', r.get('zone_count', '?'))}",
        f"  Avg rate: {r.get('avg_rate', '?')} {r.get('unit', '')}",
        f"  Total volume: {r.get('total_volume', '?')}",
        f"  Status: {r.get('status', '?')}",
    ]
    if r.get("estimated_cost_usd"):
        lines.append(f"  Est. cost: ${r['estimated_cost_usd']:.2f}")
    return "\n".join(lines)


def _format_list(results: list) -> str:
    if not results:
        return "No prescriptions found."
    lines = [f"  {r['input_type']:15s} {r['basis_metric']:15s} {r['status']:10s} "
             f"zones={r['zone_count']} avg={r['avg_rate']} {r['unit']}"
             for r in results]
    return f"Prescriptions ({len(results)}):\n" + "\n".join(lines)


def _format_estimate(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    lines = [
        f"Material Estimate for {r['input_type']}:",
        f"  Total volume: {r['total_volume']} {r['unit']}",
        f"  Area: {r['total_area_ha']} ha",
        f"  Avg rate: {r['avg_rate']} {r['unit']}",
    ]
    if r.get("cost_per_unit"):
        lines.append(f"  Cost/unit: ${r['cost_per_unit']:.2f}")
    if r.get("total_cost_usd"):
        lines.append(f"  Total cost: ${r['total_cost_usd']:.2f}")
    return "\n".join(lines)


def _cmd_generate(db, a):
    return generate_prescription_map(
        db, a.location_id, a.plot_id,
        a.input, a.basis, a.crop_cycle_id,
    )


cli.subcommand("generate", "Generate a prescription map") \
    .add("--location-id", required=True) \
    .add("--plot-id") \
    .add("--input", default="fertilizer", help="fertilizer, irrigation, seed") \
    .add("--basis", default="soil_nitrogen", help="soil_nitrogen, soil_moisture, ndvi, soil_ph") \
    .add("--crop-cycle-id") \
    .add("--json", action="store_true") \
    .run(_cmd_generate) \
    .render_with(lambda r, a: _render(r, a, _format_prescription))

cli.subcommand("list", "List prescriptions") \
    .add("--location-id", required=True) \
    .add("--status") \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_prescriptions(db, a.location_id, a.status)) \
    .render_with(lambda r, a: _render(r, a, _format_list))

cli.subcommand("approve", "Approve a prescription") \
    .add("--prescription-id", required=True) \
    .add("--approved-by", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: approve_prescription(db, a.prescription_id, a.approved_by)) \
    .render_with(lambda r, a: _render(r, a, _format_prescription))

cli.subcommand("estimate", "Material estimate") \
    .add("--prescription-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_material_estimate(db, a.prescription_id)) \
    .render_with(lambda r, a: _render(r, a, _format_estimate))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()
