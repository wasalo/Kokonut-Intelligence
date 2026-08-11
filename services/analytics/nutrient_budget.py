#!/usr/bin/env python3
"""
Nutrient Budget Tracking

Tracks field-level nutrient balances (N/P/K), records input and removal events,
stores soil-test results, and computes nutrient use efficiency.

Usage:
    python -m services.analytics.nutrient_budget create-budget --location-id UUID --season 2026S1 --crop maize --area 2.5
    python -m services.analytics.nutrient_budget record-input --budget-id UUID --type fertilizer --product "Urea 46-0-0" --n 50 --p 0 --k 0
    python -m services.analytics.nutrient_budget record-removal --budget-id UUID --crop maize --yield 3.5 --n 86.8 --p 30.1 --k 63.7
    python -m services.analytics.nutrient_budget balance --location-id UUID
    python -m services.analytics.nutrient_budget input-summary --budget-id UUID
    python -m services.analytics.nutrient_budget soil-test --location-id UUID --plot-id UUID --ph 6.5 --om 3.2 --n 45 --p 22 --k 180
    python -m services.analytics.nutrient_budget recommendation --plot-id UUID
    python -m services.analytics.nutrient_budget dashboard --location-id UUID
    python -m services.analytics.nutrient_budget removal --crop maize --yield 3.5
    python -m services.analytics.nutrient_budget efficiency --location-id UUID --season 2026S1
"""

import json
import uuid
from datetime import date
from typing import Optional

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.nutrient_budget")


# ============================================================
# Nutrient Removal Computation
# ============================================================

def compute_removal(conn, crop_name: str, yield_amount: float) -> dict:
    """Compute N/P/K removal using crop_nutrient_removal_factor.

    Args:
        crop_name: Crop name (e.g. 'maize').
        yield_amount: Harvest yield in tonnes.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT nutrient, removal_kg_per_tonne, yield_part, source
            FROM crop_nutrient_removal_factor
            WHERE crop_name = %s
            """,
            (crop_name,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    factors = {}
    for nutrient, rate, yield_part, source in rows:
        factors[nutrient] = {
            "removal_kg_per_tonne": float(rate),
            "yield_part": yield_part,
            "source": source,
        }

    n_kg = yield_amount * factors.get("nitrogen", {}).get("removal_kg_per_tonne", 0)
    p_kg = yield_amount * factors.get("phosphorus", {}).get("removal_kg_per_tonne", 0)
    k_kg = yield_amount * factors.get("potassium", {}).get("removal_kg_per_tonne", 0)

    return {
        "crop_name": crop_name,
        "yield_tonnes": yield_amount,
        "nitrogen_kg": round(n_kg, 2),
        "phosphorus_kg": round(p_kg, 2),
        "potassium_kg": round(k_kg, 2),
        "factors": factors,
    }


# ============================================================
# Create Budget
# ============================================================

def create_budget(
    conn,
    location_id: str,
    season: str,
    crop_name: str = None,
    area_ha: float = None,
    plot_id: str = None,
    metadata: dict = None,
) -> dict:
    """Create a nutrient budget for a field/plot/season."""
    cur = conn.cursor()
    budget_id = str(uuid.uuid4())

    try:
        cur.execute(
            """
            INSERT INTO nutrient_budget
                (id, location_id, plot_id, season, crop_name, area_ha, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
            RETURNING id
            """,
            (
                budget_id, location_id, plot_id, season,
                crop_name, area_ha, json.dumps(metadata or {}),
            ),
        )
        conn.commit()
    finally:
        cur.close()

    return {
        "budget_id": budget_id,
        "location_id": location_id,
        "plot_id": plot_id,
        "season": season,
        "crop_name": crop_name,
        "area_ha": area_ha,
    }


# ============================================================
# Record Nutrient Input
# ============================================================

def record_input(
    conn,
    budget_id: str,
    input_date: date,
    input_type: str,
    product_name: str = None,
    n_kg: float = 0,
    p_kg: float = 0,
    k_kg: float = 0,
    application_rate: float = None,
    rate_unit: str = None,
    cost: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a nutrient input event against a budget."""
    cur = conn.cursor()
    input_id = str(uuid.uuid4())
    input_date = input_date or date.today()

    try:
        cur.execute(
            """
            INSERT INTO nutrient_input
                (id, budget_id, input_date, input_type, product_name,
                 nitrogen_kg, phosphorus_kg, potassium_kg,
                 application_rate, rate_unit, cost, notes, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
            RETURNING id
            """,
            (
                input_id, budget_id, input_date, input_type, product_name,
                n_kg, p_kg, k_kg,
                application_rate, rate_unit, cost, notes, json.dumps(metadata or {}),
            ),
        )

        # Update budget cumulative inputs
        cur.execute(
            """
            UPDATE nutrient_budget
            SET nitrogen_input_kg   = nitrogen_input_kg   + %s,
                phosphorus_input_kg = phosphorus_input_kg + %s,
                potassium_input_kg  = potassium_input_kg  + %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (n_kg, p_kg, k_kg, budget_id),
        )
        conn.commit()
    finally:
        cur.close()

    return {
        "input_id": input_id,
        "budget_id": budget_id,
        "input_date": input_date.isoformat(),
        "input_type": input_type,
        "product_name": product_name,
        "nitrogen_kg": n_kg,
        "phosphorus_kg": p_kg,
        "potassium_kg": k_kg,
    }


# ============================================================
# Record Nutrient Removal
# ============================================================

def record_removal(
    conn,
    budget_id: str,
    harvest_date: date,
    crop_name: str,
    yield_amount: float,
    n_kg: float,
    p_kg: float,
    k_kg: float,
    yield_unit: str = "tonnes",
    removal_factor_source: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record nutrient removal at harvest."""
    cur = conn.cursor()
    removal_id = str(uuid.uuid4())
    harvest_date = harvest_date or date.today()

    try:
        cur.execute(
            """
            INSERT INTO nutrient_removal
                (id, budget_id, harvest_date, crop_name,
                 yield_amount, yield_unit,
                 nitrogen_kg, phosphorus_kg, potassium_kg,
                 removal_factor_source, notes, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
            RETURNING id
            """,
            (
                removal_id, budget_id, harvest_date, crop_name,
                yield_amount, yield_unit,
                n_kg, p_kg, k_kg,
                removal_factor_source, notes, json.dumps(metadata or {}),
            ),
        )

        # Update budget cumulative removals
        cur.execute(
            """
            UPDATE nutrient_budget
            SET nitrogen_removal_kg   = nitrogen_removal_kg   + %s,
                phosphorus_removal_kg = phosphorus_removal_kg + %s,
                potassium_removal_kg  = potassium_removal_kg  + %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (n_kg, p_kg, k_kg, budget_id),
        )
        conn.commit()
    finally:
        cur.close()

    return {
        "removal_id": removal_id,
        "budget_id": budget_id,
        "harvest_date": harvest_date.isoformat(),
        "crop_name": crop_name,
        "yield_amount": yield_amount,
        "yield_unit": yield_unit,
        "nitrogen_kg": n_kg,
        "phosphorus_kg": p_kg,
        "potassium_kg": k_kg,
    }


# ============================================================
# Get Nutrient Balance
# ============================================================

def get_nutrient_balance(conn, location_id: str) -> dict:
    """Get current nutrient surplus/deficit per plot from the balance view."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT budget_id, plot_id, season, crop_name, area_ha,
                   nitrogen_input_kg, nitrogen_removal_kg, nitrogen_surplus_kg,
                   phosphorus_input_kg, phosphorus_removal_kg, phosphorus_surplus_kg,
                   potassium_input_kg, potassium_removal_kg, potassium_surplus_kg,
                   nitrogen_balance_status, phosphorus_balance_status, potassium_balance_status
            FROM v_nutrient_balance
            WHERE location_id = %s
            ORDER BY season DESC, plot_id NULLS LAST
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        cur.close()

    return {
        "location_id": location_id,
        "budgets": [
            {
                "budget_id": str(r["budget_id"]),
                "plot_id": str(r["plot_id"]) if r["plot_id"] else None,
                "season": r["season"],
                "crop_name": r["crop_name"],
                "area_ha": float(r["area_ha"]) if r["area_ha"] else None,
                "nitrogen": {
                    "input_kg": float(r["nitrogen_input_kg"]),
                    "removal_kg": float(r["nitrogen_removal_kg"]),
                    "surplus_kg": float(r["nitrogen_surplus_kg"]),
                    "status": r["nitrogen_balance_status"],
                },
                "phosphorus": {
                    "input_kg": float(r["phosphorus_input_kg"]),
                    "removal_kg": float(r["phosphorus_removal_kg"]),
                    "surplus_kg": float(r["phosphorus_surplus_kg"]),
                    "status": r["phosphorus_balance_status"],
                },
                "potassium": {
                    "input_kg": float(r["potassium_input_kg"]),
                    "removal_kg": float(r["potassium_removal_kg"]),
                    "surplus_kg": float(r["potassium_surplus_kg"]),
                    "status": r["potassium_balance_status"],
                },
            }
            for r in rows
        ],
    }


# ============================================================
# Get Input Summary
# ============================================================

def get_input_summary(conn, budget_id: str) -> dict:
    """Get input totals by type for a budget."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT input_type, event_count, total_nitrogen_kg,
                   total_phosphorus_kg, total_potassium_kg,
                   total_cost, avg_application_rate, rate_unit
            FROM v_nutrient_input_summary
            WHERE budget_id = %s
            ORDER BY input_type
            """,
            (budget_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        cur.close()

    return {
        "budget_id": budget_id,
        "summary": [
            {
                "input_type": r["input_type"],
                "event_count": int(r["event_count"]),
                "nitrogen_kg": float(r["total_nitrogen_kg"]),
                "phosphorus_kg": float(r["total_phosphorus_kg"]),
                "potassium_kg": float(r["total_potassium_kg"]),
                "total_cost": float(r["total_cost"]) if r["total_cost"] else None,
                "avg_application_rate": round(float(r["avg_application_rate"]), 2) if r["avg_application_rate"] else None,
                "rate_unit": r["rate_unit"],
            }
            for r in rows
        ],
    }


# ============================================================
# Record Soil Test
# ============================================================

def record_soil_test(
    conn,
    location_id: str,
    plot_id: str = None,
    test_date: date = None,
    soil_ph: float = None,
    organic_matter_pct: float = None,
    n_ppm: float = None,
    p_ppm: float = None,
    k_ppm: float = None,
    cec: float = None,
    recommended_n_kg_ha: float = None,
    recommended_p_kg_ha: float = None,
    recommended_k_kg_ha: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a soil test result with optional nutrient recommendations."""
    cur = conn.cursor()
    test_id = str(uuid.uuid4())
    test_date = test_date or date.today()

    try:
        cur.execute(
            """
            INSERT INTO soil_test_recommendation
                (id, location_id, plot_id, test_date,
                 soil_ph, organic_matter_pct,
                 nitrogen_ppm, phosphorus_ppm, potassium_ppm, cec,
                 recommended_n_kg_ha, recommended_p_kg_ha, recommended_k_kg_ha,
                 notes, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
            RETURNING id
            """,
            (
                test_id, location_id, plot_id, test_date,
                soil_ph, organic_matter_pct,
                n_ppm, p_ppm, k_ppm, cec,
                recommended_n_kg_ha, recommended_p_kg_ha, recommended_k_kg_ha,
                notes, json.dumps(metadata or {}),
            ),
        )
        conn.commit()
    finally:
        cur.close()

    return {
        "test_id": test_id,
        "location_id": location_id,
        "plot_id": plot_id,
        "test_date": test_date.isoformat(),
        "soil_ph": soil_ph,
        "organic_matter_pct": organic_matter_pct,
        "nitrogen_ppm": n_ppm,
        "phosphorus_ppm": p_ppm,
        "potassium_ppm": k_ppm,
        "cec": cec,
        "recommended_n_kg_ha": recommended_n_kg_ha,
        "recommended_p_kg_ha": recommended_p_kg_ha,
        "recommended_k_kg_ha": recommended_k_kg_ha,
    }


# ============================================================
# Get Recommendation
# ============================================================

def get_recommendation(conn, plot_id: str) -> dict:
    """Get the latest soil-test-based nutrient recommendations for a plot."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, location_id, test_date, soil_ph, organic_matter_pct,
                   nitrogen_ppm, phosphorus_ppm, potassium_ppm, cec,
                   recommended_n_kg_ha, recommended_p_kg_ha, recommended_k_kg_ha,
                   notes
            FROM soil_test_recommendation
            WHERE plot_id = %s AND status IN ('recorded', 'verified')
            ORDER BY test_date DESC
            LIMIT 1
            """,
            (plot_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()

    if not row:
        return {"plot_id": plot_id, "recommendation": None, "message": "No soil test records found."}

    return {
        "plot_id": plot_id,
        "test_id": str(row[0]),
        "location_id": str(row[1]),
        "test_date": row[2].isoformat() if row[2] else None,
        "soil_ph": float(row[4]) if row[4] else None,
        "organic_matter_pct": float(row[5]) if row[5] else None,
        "nitrogen_ppm": float(row[6]) if row[6] else None,
        "phosphorus_ppm": float(row[7]) if row[7] else None,
        "potassium_ppm": float(row[8]) if row[8] else None,
        "cec": float(row[9]) if row[9] else None,
        "recommended": {
            "nitrogen_kg_ha": float(row[10]) if row[10] else None,
            "phosphorus_kg_ha": float(row[11]) if row[11] else None,
            "potassium_kg_ha": float(row[12]) if row[12] else None,
        },
        "notes": row[13],
    }


# ============================================================
# Get Nutrient Dashboard
# ============================================================

def get_nutrient_dashboard(conn, location_id: str) -> dict:
    """Dashboard combining balances, inputs, and soil tests."""
    cur = conn.cursor()
    try:
        # Balances
        cur.execute(
            """
            SELECT budget_id, plot_id, season, crop_name, area_ha,
                   nitrogen_input_kg, nitrogen_removal_kg, nitrogen_surplus_kg,
                   phosphorus_input_kg, phosphorus_removal_kg, phosphorus_surplus_kg,
                   potassium_input_kg, potassium_removal_kg, potassium_surplus_kg
            FROM v_nutrient_balance
            WHERE location_id = %s
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        balances = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Aggregate inputs across all budgets at this location
        cur.execute(
            """
            SELECT ni.input_type,
                   COUNT(*) AS event_count,
                   SUM(ni.nitrogen_kg) AS total_n,
                   SUM(ni.phosphorus_kg) AS total_p,
                   SUM(ni.potassium_kg) AS total_k,
                   SUM(ni.cost) AS total_cost
            FROM nutrient_input ni
            JOIN nutrient_budget nb ON nb.id = ni.budget_id
            WHERE nb.location_id = %s AND ni.status IN ('recorded', 'verified')
            GROUP BY ni.input_type
            ORDER BY ni.input_type
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        inputs = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Soil tests
        cur.execute(
            """
            SELECT plot_id, test_date, soil_ph, organic_matter_pct,
                   nitrogen_ppm, phosphorus_ppm, potassium_ppm
            FROM soil_test_recommendation
            WHERE location_id = %s AND status IN ('recorded', 'verified')
            ORDER BY test_date DESC
            LIMIT 10
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        soil_tests = [dict(zip(cols, r)) for r in cur.fetchall()]

    finally:
        cur.close()

    return {
        "location_id": location_id,
        "balances": [
            {
                "budget_id": str(b["budget_id"]),
                "plot_id": str(b["plot_id"]) if b["plot_id"] else None,
                "season": b["season"],
                "crop_name": b["crop_name"],
                "area_ha": float(b["area_ha"]) if b["area_ha"] else None,
                "nitrogen_surplus_kg": float(b["nitrogen_surplus_kg"]),
                "phosphorus_surplus_kg": float(b["phosphorus_surplus_kg"]),
                "potassium_surplus_kg": float(b["potassium_surplus_kg"]),
            }
            for b in balances
        ],
        "inputs_by_type": [
            {
                "input_type": i["input_type"],
                "event_count": int(i["event_count"]),
                "nitrogen_kg": float(i["total_n"]),
                "phosphorus_kg": float(i["total_p"]),
                "potassium_kg": float(i["total_k"]),
                "total_cost": float(i["total_cost"]) if i["total_cost"] else None,
            }
            for i in inputs
        ],
        "recent_soil_tests": [
            {
                "plot_id": str(st["plot_id"]) if st["plot_id"] else None,
                "test_date": st["test_date"].isoformat() if st["test_date"] else None,
                "soil_ph": float(st["soil_ph"]) if st["soil_ph"] else None,
                "organic_matter_pct": float(st["organic_matter_pct"]) if st["organic_matter_pct"] else None,
                "nitrogen_ppm": float(st["nitrogen_ppm"]) if st["nitrogen_ppm"] else None,
                "phosphorus_ppm": float(st["phosphorus_ppm"]) if st["phosphorus_ppm"] else None,
                "potassium_ppm": float(st["potassium_ppm"]) if st["potassium_ppm"] else None,
            }
            for st in soil_tests
        ],
    }


# ============================================================
# Nutrient Use Efficiency
# ============================================================

def get_efficiency_ratio(conn, location_id: str, season: str) -> dict:
    """Compute nutrient use efficiency (output / input) per nutrient."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT nitrogen_input_kg, nitrogen_removal_kg,
                   phosphorus_input_kg, phosphorus_removal_kg,
                   potassium_input_kg, potassium_removal_kg
            FROM nutrient_budget
            WHERE location_id = %s AND season = %s
              AND status IN ('verified', 'published')
            """,
            (location_id, season),
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    if not rows:
        return {
            "location_id": location_id,
            "season": season,
            "efficiency": None,
            "message": "No verified budget data for this location/season.",
        }

    total_n_input = sum(float(r[0]) for r in rows)
    total_n_removal = sum(float(r[1]) for r in rows)
    total_p_input = sum(float(r[2]) for r in rows)
    total_p_removal = sum(float(r[3]) for r in rows)
    total_k_input = sum(float(r[4]) for r in rows)
    total_k_removal = sum(float(r[5]) for r in rows)

    def _ratio(output, input_val):
        if input_val and input_val > 0:
            return round(output / input_val, 4)
        return None

    return {
        "location_id": location_id,
        "season": season,
        "efficiency": {
            "nitrogen": {
                "input_kg": round(total_n_input, 2),
                "removal_kg": round(total_n_removal, 2),
                "ratio": _ratio(total_n_removal, total_n_input),
            },
            "phosphorus": {
                "input_kg": round(total_p_input, 2),
                "removal_kg": round(total_p_removal, 2),
                "ratio": _ratio(total_p_removal, total_p_input),
            },
            "potassium": {
                "input_kg": round(total_k_input, 2),
                "removal_kg": round(total_k_removal, 2),
                "ratio": _ratio(total_k_removal, total_k_input),
            },
        },
    }


# ============================================================
# CLI
# ============================================================

cli = CommandLine("nutrient_budget", "Nutrient budget tracking")


def _cmd_record_input(db, a):
    d = date.fromisoformat(a.date) if a.date else None
    return record_input(
        db, a.budget_id, d, a.input_type,
        product_name=a.product,
        n_kg=a.n, p_kg=a.p, k_kg=a.k,
        application_rate=a.rate, rate_unit=a.rate_unit,
        cost=a.cost, notes=a.notes,
    )


def _cmd_record_removal(db, a):
    d = date.fromisoformat(a.date) if a.date else None
    return record_removal(
        db, a.budget_id, d, a.crop, a.yield_amount,
        n_kg=a.n, p_kg=a.p, k_kg=a.k,
        yield_unit=a.yield_unit, removal_factor_source=a.source,
        notes=a.notes,
    )


def _cmd_soil_test(db, a):
    d = date.fromisoformat(a.date) if a.date else None
    return record_soil_test(
        db, a.location_id, plot_id=a.plot_id,
        test_date=d,
        soil_ph=a.soil_ph,
        organic_matter_pct=a.organic_matter_pct,
        n_ppm=a.n_ppm, p_ppm=a.p_ppm, k_ppm=a.k_ppm,
        cec=a.cec,
        recommended_n_kg_ha=a.recommended_n_kg_ha,
        recommended_p_kg_ha=a.recommended_p_kg_ha,
        recommended_k_kg_ha=a.recommended_k_kg_ha,
        notes=a.notes,
    )


cli.subcommand("create-budget", "Create nutrient budget") \
    .add("--location-id", required=True) \
    .add("--season", required=True) \
    .add("--crop") \
    .add("--area", type=float, help="Area in hectares") \
    .add("--plot-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: create_budget(db, a.location_id, a.season, crop_name=a.crop, area_ha=a.area, plot_id=a.plot_id))

cli.subcommand("record-input", "Record nutrient input") \
    .add("--budget-id", required=True) \
    .add("--date", help="Input date YYYY-MM-DD") \
    .add("--type", required=True, dest="input_type",
         choices=["fertilizer", "manure", "compost", "biochar",
                  "green_manure", "rainfall", "irrigation", "seed", "other"]) \
    .add("--product", help="Product name") \
    .add("--n", type=float, default=0, help="Nitrogen kg") \
    .add("--p", type=float, default=0, help="Phosphorus kg") \
    .add("--k", type=float, default=0, help="Potassium kg") \
    .add("--rate", type=float, help="Application rate") \
    .add("--rate-unit", help="Rate unit (kg/ha, L/ha, etc)") \
    .add("--cost", type=float, help="Cost") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_input)

cli.subcommand("record-removal", "Record nutrient removal at harvest") \
    .add("--budget-id", required=True) \
    .add("--date", help="Harvest date YYYY-MM-DD") \
    .add("--crop", required=True) \
    .add("--yield", type=float, required=True, dest="yield_amount", help="Yield in tonnes") \
    .add("--n", type=float, default=0, help="Nitrogen removed kg") \
    .add("--p", type=float, default=0, help="Phosphorus removed kg") \
    .add("--k", type=float, default=0, help="Potassium removed kg") \
    .add("--yield-unit", default="tonnes") \
    .add("--source", help="Removal factor source") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_removal)

cli.subcommand("balance", "Get nutrient balance") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_nutrient_balance(db, a.location_id))

cli.subcommand("input-summary", "Get input summary by type") \
    .add("--budget-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_input_summary(db, a.budget_id))

cli.subcommand("soil-test", "Record soil test") \
    .add("--location-id", required=True) \
    .add("--plot-id") \
    .add("--date", help="Test date YYYY-MM-DD") \
    .add("--ph", type=float, dest="soil_ph") \
    .add("--om", type=float, dest="organic_matter_pct", help="Organic matter %") \
    .add("--n", type=float, dest="n_ppm", help="Nitrogen ppm") \
    .add("--p", type=float, dest="p_ppm", help="Phosphorus ppm") \
    .add("--k", type=float, dest="k_ppm", help="Potassium ppm") \
    .add("--cec", type=float) \
    .add("--rec-n", type=float, dest="recommended_n_kg_ha", help="Recommended N kg/ha") \
    .add("--rec-p", type=float, dest="recommended_p_kg_ha", help="Recommended P kg/ha") \
    .add("--rec-k", type=float, dest="recommended_k_kg_ha", help="Recommended K kg/ha") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_soil_test)

cli.subcommand("recommendation", "Get soil-test recommendation") \
    .add("--plot-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_recommendation(db, a.plot_id))

cli.subcommand("dashboard", "Nutrient dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_nutrient_dashboard(db, a.location_id))

cli.subcommand("removal", "Compute removal from yield") \
    .add("--crop", required=True) \
    .add("--yield", type=float, required=True, dest="yield_amount", help="Yield in tonnes") \
    .add("--json", action="store_true") \
    .run(lambda db, a: compute_removal(db, a.crop, a.yield_amount))

cli.subcommand("efficiency", "Nutrient use efficiency") \
    .add("--location-id", required=True) \
    .add("--season", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_efficiency_ratio(db, a.location_id, a.season))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()
