#!/usr/bin/env python3
"""
Energy Monitoring

Tracks energy sources, consumption/production readings, efficiency metrics,
renewable energy share, carbon intensity, and cost analysis.

Usage:
    python -m services.analytics.energy_monitoring add-source --location-id UUID --name "Solar PV" --type solar --capacity 15.0
    python -m services.analytics.energy_monitoring record --source-id UUID --date 2026-07-10 --type consumption --kwh 120.5 --cost 0.15
    python -m services.analytics.energy_monitoring consumption --location-id UUID --days 30
    python -m services.analytics.energy_monitoring efficiency --location-id UUID --period monthly
    python -m services.analytics.energy_monitoring add-renewable --location-id UUID --source-id UUID --renewable-type solar_pv --capacity 15.0
    python -m services.analytics.energy_monitoring renewable-summary --location-id UUID
    python -m services.analytics.energy_monitoring dashboard --location-id UUID
    python -m services.analytics.energy_monitoring carbon-intensity --location-id UUID
    python -m services.analytics.energy_monitoring cost-analysis --location-id UUID --days 30
"""

import argparse
import json
import uuid
from datetime import date, timedelta
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.energy_monitoring")


# ============================================================
# Energy Source Management
# ============================================================

def add_source(
    conn,
    location_id: str,
    source_name: str,
    source_type: str,
    capacity_kw: float = None,
    installation_date: date = None,
    metadata: dict = None,
) -> dict:
    """Add an energy source to a location."""
    cur = conn.cursor()
    source_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO energy_source
            (id, location_id, source_name, source_type, capacity_kw,
             installation_date, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
        RETURNING id
        """,
        (
            source_id, location_id, source_name, source_type, capacity_kw,
            installation_date or date.today(),
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Added energy source %s (%s) at %s", source_name, source_type, location_id)

    return {
        "source_id": source_id,
        "location_id": location_id,
        "source_name": source_name,
        "source_type": source_type,
        "capacity_kw": capacity_kw,
        "installation_date": (installation_date or date.today()).isoformat(),
    }


# ============================================================
# Energy Reading Recording
# ============================================================

def record_reading(
    conn,
    source_id: str,
    reading_date: date,
    reading_type: str,
    kwh: float,
    cost_per_kwh: float = None,
    activity_type: str = None,
    equipment_id: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record an energy reading for a source."""
    cur = conn.cursor()

    cur.execute("SELECT location_id FROM energy_source WHERE id = %s", (source_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        raise ValueError(f"Energy source {source_id} not found")
    location_id = row[0]

    total_cost = round(kwh * cost_per_kwh, 2) if cost_per_kwh else None

    reading_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO energy_reading
            (id, location_id, source_id, reading_date, reading_type, kwh,
             cost_per_kwh, total_cost, activity_type, equipment_id,
             notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
        RETURNING id
        """,
        (
            reading_id, location_id, source_id, reading_date, reading_type, kwh,
            cost_per_kwh, total_cost, activity_type, equipment_id,
            notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded %s reading: %.1f kWh for source %s", reading_type, kwh, source_id)

    return {
        "reading_id": reading_id,
        "source_id": source_id,
        "location_id": location_id,
        "reading_date": reading_date.isoformat(),
        "reading_type": reading_type,
        "kwh": kwh,
        "cost_per_kwh": cost_per_kwh,
        "total_cost": total_cost,
        "activity_type": activity_type,
    }


# ============================================================
# Consumption Summary
# ============================================================

def get_consumption(conn, location_id: str, days: int = 30) -> dict:
    """Get consumption breakdown by activity and source."""
    cur = conn.cursor()
    cutoff = date.today() - timedelta(days=days)

    cur.execute(
        """
        SELECT es.source_name, es.source_type,
               er.activity_type,
               SUM(er.kwh) AS total_kwh,
               SUM(er.total_cost) AS total_cost,
               COUNT(*) AS readings
        FROM energy_reading er
        JOIN energy_source es ON es.id = er.source_id
        WHERE er.location_id = %s
          AND er.reading_type = 'consumption'
          AND er.reading_date >= %s
          AND er.status IN ('recorded', 'verified', 'approved')
        GROUP BY es.source_name, es.source_type, er.activity_type
        ORDER BY total_kwh DESC
        """,
        (location_id, cutoff),
    )
    cols = [d[0] for d in cur.description]
    by_activity = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT SUM(er.kwh) AS total_kwh,
               SUM(COALESCE(er.total_cost, 0)) AS total_cost,
               COUNT(DISTINCT er.source_id) AS sources_used,
               COUNT(*) AS readings
        FROM energy_reading er
        WHERE er.location_id = %s
          AND er.reading_type = 'consumption'
          AND er.reading_date >= %s
          AND er.status IN ('recorded', 'verified', 'approved')
        """,
        (location_id, cutoff),
    )
    agg = cur.fetchone()

    # By source type
    cur.execute(
        """
        SELECT es.source_type,
               SUM(er.kwh) AS total_kwh,
               SUM(COALESCE(er.total_cost, 0)) AS total_cost
        FROM energy_reading er
        JOIN energy_source es ON es.id = er.source_id
        WHERE er.location_id = %s
          AND er.reading_type = 'consumption'
          AND er.reading_date >= %s
          AND er.status IN ('recorded', 'verified', 'approved')
        GROUP BY es.source_type
        ORDER BY total_kwh DESC
        """,
        (location_id, cutoff),
    )
    cols = [d[0] for d in cur.description]
    by_source = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "total_kwh": float(agg[0]) if agg[0] else 0,
        "total_cost": float(agg[1]) if agg[1] else 0,
        "avg_cost_per_kwh": round(float(agg[1]) / float(agg[0]), 4) if agg[0] and agg[1] else None,
        "sources_used": int(agg[2]) if agg[2] else 0,
        "readings": int(agg[3]) if agg[3] else 0,
        "by_activity": by_activity,
        "by_source_type": by_source,
    }


# ============================================================
# Efficiency Metrics
# ============================================================

def get_efficiency(conn, location_id: str, period: str = "monthly") -> dict:
    """Get efficiency metrics for a location."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT log_date, period, total_consumption_kwh, total_production_kwh,
               net_energy_kwh, renewable_pct, carbon_intensity_kg_kwh,
               cost_per_unit_output
        FROM energy_efficiency_log
        WHERE location_id = %s AND period = %s
        ORDER BY log_date DESC
        LIMIT 12
        """,
        (location_id, period),
    )
    cols = [d[0] for d in cur.description]
    logs = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Compute current efficiency from readings if no logs exist
    renewable_pct = 0.0
    total_consumption = 0.0
    total_production = 0.0

    if not logs:
        cur.execute(
            """
            SELECT
                SUM(CASE WHEN reading_type = 'consumption' THEN kwh ELSE 0 END) AS total_consumption,
                SUM(CASE WHEN reading_type = 'production' THEN kwh ELSE 0 END) AS total_production
            FROM energy_reading
            WHERE location_id = %s
              AND reading_date >= CURRENT_DATE - INTERVAL '30 days'
              AND status IN ('recorded', 'verified', 'approved')
            """,
            (location_id,),
        )
        agg = cur.fetchone()
        total_consumption = float(agg[0]) if agg[0] else 0
        total_production = float(agg[1]) if agg[1] else 0

        if total_consumption > 0:
            cur.execute(
                """
                SELECT SUM(er.kwh) AS renewable_kwh
                FROM energy_reading er
                JOIN energy_source es ON es.id = er.source_id
                WHERE er.location_id = %s
                  AND er.reading_type = 'consumption'
                  AND es.source_type IN ('solar', 'wind', 'biogas', 'biomass')
                  AND er.reading_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND er.status IN ('recorded', 'verified', 'approved')
                """,
                (location_id,),
            )
            ren_row = cur.fetchone()
            renewable_kwh = float(ren_row[0]) if ren_row and ren_row[0] else 0
            renewable_pct = round(renewable_kwh / total_consumption * 100, 2) if total_consumption > 0 else 0

    cur.close()

    latest = logs[0] if logs else None

    return {
        "location_id": location_id,
        "period": period,
        "latest_efficiency": latest,
        "history": logs,
        "current_metrics": {
            "total_consumption_kwh": round(total_consumption, 2),
            "total_production_kwh": round(total_production, 2),
            "net_energy_kwh": round(total_production - total_consumption, 2),
            "renewable_pct": renewable_pct,
        },
    }


# ============================================================
# Renewable Energy Registration
# ============================================================

def add_renewable(
    conn,
    location_id: str,
    source_id: str,
    renewable_type: str,
    rated_capacity_kw: float,
    annual_generation_kwh: float = None,
    carbon_offset_kg: float = None,
    metadata: dict = None,
) -> dict:
    """Register a renewable energy source."""
    cur = conn.cursor()
    renewable_id = str(uuid.uuid4())

    if annual_generation_kwh is None:
        annual_generation_kwh = round(rated_capacity_kw * 1500, 2)
    if carbon_offset_kg is None:
        carbon_offset_kg = round(annual_generation_kwh * 0.4, 2)

    cur.execute(
        """
        INSERT INTO renewable_energy_source
            (id, location_id, source_id, renewable_type, rated_capacity_kw,
             annual_generation_kwh, carbon_offset_kg, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
        RETURNING id
        """,
        (
            renewable_id, location_id, source_id, renewable_type, rated_capacity_kw,
            annual_generation_kwh, carbon_offset_kg, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Registered renewable source %s (%s) at %s", renewable_type, source_id, location_id)

    return {
        "renewable_id": renewable_id,
        "source_id": source_id,
        "location_id": location_id,
        "renewable_type": renewable_type,
        "rated_capacity_kw": rated_capacity_kw,
        "annual_generation_kwh": annual_generation_kwh,
        "carbon_offset_kg": carbon_offset_kg,
    }


# ============================================================
# Renewable Energy Summary
# ============================================================

def get_renewable_summary(conn, location_id: str) -> dict:
    """Get renewable energy share and carbon offset."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT res.renewable_type, es.source_name, es.source_type,
               res.rated_capacity_kw, res.annual_generation_kwh,
               res.carbon_offset_kg, res.status
        FROM renewable_energy_source res
        JOIN energy_source es ON es.id = res.source_id
        WHERE res.location_id = %s
          AND res.status = 'active'
        ORDER BY res.annual_generation_kwh DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    sources = [dict(zip(cols, row)) for row in cur.fetchall()]

    total_capacity = sum(float(s["rated_capacity_kw"] or 0) for s in sources)
    total_generation = sum(float(s["annual_generation_kwh"] or 0) for s in sources)
    total_offset = sum(float(s["carbon_offset_kg"] or 0) for s in sources)

    # Get total consumption for share calculation
    cur.execute(
        """
        SELECT SUM(kwh) AS total_kwh
        FROM energy_reading
        WHERE location_id = %s
          AND reading_type = 'consumption'
          AND reading_date >= CURRENT_DATE - INTERVAL '365 days'
          AND status IN ('recorded', 'verified', 'approved')
        """,
        (location_id,),
    )
    cons_row = cur.fetchone()
    annual_consumption = float(cons_row[0]) if cons_row and cons_row[0] else 0

    renewable_share_pct = 0.0
    if annual_consumption > 0:
        renewable_share_pct = round(total_generation / annual_consumption * 100, 2)

    cur.close()

    return {
        "location_id": location_id,
        "active_sources": len(sources),
        "total_capacity_kw": round(total_capacity, 2),
        "annual_generation_kwh": round(total_generation, 2),
        "total_carbon_offset_kg": round(total_offset, 2),
        "annual_consumption_kwh": round(annual_consumption, 2),
        "renewable_share_pct": min(renewable_share_pct, 100.0),
        "sources": sources,
    }


# ============================================================
# Energy Dashboard
# ============================================================

def get_energy_dashboard(conn, location_id: str) -> dict:
    """Dashboard with consumption, efficiency, and renewable metrics."""
    consumption = get_consumption(conn, location_id, days=30)
    efficiency = get_efficiency(conn, location_id, period="daily")
    renewable = get_renewable_summary(conn, location_id)

    # Active sources
    cur = conn.cursor()
    cur.execute(
        """
        SELECT source_type, COUNT(*) AS count,
               SUM(capacity_kw) AS total_capacity
        FROM energy_source
        WHERE location_id = %s AND status = 'active'
        GROUP BY source_type
        ORDER BY total_capacity DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    source_breakdown = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Last 7 days trend
    cutoff_7d = date.today() - timedelta(days=7)
    cur.execute(
        """
        SELECT reading_date,
               SUM(CASE WHEN reading_type = 'consumption' THEN kwh ELSE 0 END) AS consumption_kwh,
               SUM(CASE WHEN reading_type = 'production' THEN kwh ELSE 0 END) AS production_kwh
        FROM energy_reading
        WHERE location_id = %s
          AND reading_date >= %s
          AND status IN ('recorded', 'verified', 'approved')
        GROUP BY reading_date
        ORDER BY reading_date
        """,
        (location_id, cutoff_7d),
    )
    cols = [d[0] for d in cur.description]
    trend = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    return {
        "location_id": location_id,
        "consumption": consumption,
        "efficiency": efficiency,
        "renewable": renewable,
        "source_breakdown": source_breakdown,
        "trend_7d": trend,
    }


# ============================================================
# Carbon Intensity
# ============================================================

def compute_carbon_intensity(conn, location_id: str) -> dict:
    """Compute kg CO2e per kWh based on energy mix."""
    cur = conn.cursor()

    # Emission factors (kg CO2e per kWh) by source type
    emission_factors = {
        "grid": 0.45,
        "diesel_generator": 0.70,
        "solar": 0.0,
        "wind": 0.0,
        "biogas": 0.05,
        "biomass": 0.10,
        "battery": 0.0,
    }

    cur.execute(
        """
        SELECT es.source_type,
               SUM(er.kwh) AS total_kwh,
               SUM(CASE WHEN er.reading_type = 'consumption' THEN er.kwh ELSE 0 END) AS consumption_kwh,
               SUM(CASE WHEN er.reading_type = 'production' THEN er.kwh ELSE 0 END) AS production_kwh
        FROM energy_reading er
        JOIN energy_source es ON es.id = er.source_id
        WHERE er.location_id = %s
          AND er.reading_date >= CURRENT_DATE - INTERVAL '30 days'
          AND er.status IN ('recorded', 'verified', 'approved')
        GROUP BY es.source_type
        ORDER BY consumption_kwh DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    total_consumption = 0.0
    total_emissions = 0.0
    breakdown = []

    for r in rows:
        stype = r["source_type"]
        cons_kwh = float(r["consumption_kwh"] or 0)
        factor = emission_factors.get(stype, 0.0)
        emissions = cons_kwh * factor
        total_consumption += cons_kwh
        total_emissions += emissions

        breakdown.append({
            "source_type": stype,
            "consumption_kwh": round(cons_kwh, 2),
            "emission_factor_kg_kwh": factor,
            "emissions_kg": round(emissions, 2),
        })

    carbon_intensity = round(total_emissions / total_consumption, 4) if total_consumption > 0 else 0

    # Renewable share
    renewable_kwh = sum(
        float(r["consumption_kwh"] or 0)
        for r in rows
        if r["source_type"] in ("solar", "wind", "biogas", "biomass")
    )
    renewable_pct = round(renewable_kwh / total_consumption * 100, 2) if total_consumption > 0 else 0

    # Carbon offset from renewables
    cur.execute(
        """
        SELECT SUM(carbon_offset_kg)
        FROM renewable_energy_source
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    off_row = cur.fetchone()
    annual_offset = float(off_row[0]) if off_row and off_row[0] else 0
    monthly_offset = round(annual_offset / 12, 2)

    cur.close()

    return {
        "location_id": location_id,
        "period_days": 30,
        "total_consumption_kwh": round(total_consumption, 2),
        "total_emissions_kg_co2e": round(total_emissions, 2),
        "carbon_intensity_kg_co2e_kwh": carbon_intensity,
        "renewable_share_pct": renewable_pct,
        "monthly_carbon_offset_kg": monthly_offset,
        "net_monthly_emissions_kg": round(total_emissions - monthly_offset, 2),
        "breakdown": breakdown,
    }


# ============================================================
# Cost Analysis
# ============================================================

def get_cost_analysis(conn, location_id: str, days: int = 30) -> dict:
    """Energy cost breakdown by activity."""
    cur = conn.cursor()
    cutoff = date.today() - timedelta(days=days)

    cur.execute(
        """
        SELECT er.activity_type,
               SUM(er.kwh) AS total_kwh,
               SUM(COALESCE(er.total_cost, 0)) AS total_cost,
               AVG(er.cost_per_kwh) AS avg_cost_per_kwh,
               COUNT(*) AS readings
        FROM energy_reading er
        WHERE er.location_id = %s
          AND er.reading_type = 'consumption'
          AND er.reading_date >= %s
          AND er.status IN ('recorded', 'verified', 'approved')
        GROUP BY er.activity_type
        ORDER BY total_cost DESC
        """,
        (location_id, cutoff),
    )
    cols = [d[0] for d in cur.description]
    by_activity = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT es.source_type,
               SUM(er.kwh) AS total_kwh,
               SUM(COALESCE(er.total_cost, 0)) AS total_cost,
               AVG(er.cost_per_kwh) AS avg_cost_per_kwh
        FROM energy_reading er
        JOIN energy_source es ON es.id = er.source_id
        WHERE er.location_id = %s
          AND er.reading_type = 'consumption'
          AND er.reading_date >= %s
          AND er.status IN ('recorded', 'verified', 'approved')
        GROUP BY es.source_type
        ORDER BY total_cost DESC
        """,
        (location_id, cutoff),
    )
    cols = [d[0] for d in cur.description]
    by_source = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Total
    cur.execute(
        """
        SELECT SUM(COALESCE(total_cost, 0)),
               SUM(kwh),
               AVG(cost_per_kwh)
        FROM energy_reading
        WHERE location_id = %s
          AND reading_type = 'consumption'
          AND reading_date >= %s
          AND status IN ('recorded', 'verified', 'approved')
        """,
        (location_id, cutoff),
    )
    tot = cur.fetchone()
    total_cost = float(tot[0]) if tot[0] else 0
    total_kwh = float(tot[1]) if tot[1] else 0
    avg_cost = float(tot[2]) if tot[2] else None

    # Monthly projection
    monthly_projected = round(total_cost / days * 30, 2) if days > 0 else 0

    cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "total_cost": round(total_cost, 2),
        "total_kwh": round(total_kwh, 2),
        "avg_cost_per_kwh": round(avg_cost, 4) if avg_cost else None,
        "monthly_projected_cost": monthly_projected,
        "by_activity": by_activity,
        "by_source_type": by_source,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Energy monitoring")
    sub = parser.add_subparsers(dest="command")

    # add-source
    as_ = sub.add_parser("add-source", help="Add energy source")
    as_.add_argument("--location-id", required=True)
    as_.add_argument("--name", required=True)
    as_.add_argument("--type", required=True, dest="source_type",
                     choices=["grid", "diesel_generator", "solar", "wind", "biogas", "biomass", "battery"])
    as_.add_argument("--capacity", type=float, help="Capacity in kW")
    as_.add_argument("--installation-date", help="YYYY-MM-DD")
    as_.add_argument("--json", action="store_true")

    # record
    rd = sub.add_parser("record", help="Record energy reading")
    rd.add_argument("--source-id", required=True)
    rd.add_argument("--date", default=None, help="Reading date YYYY-MM-DD")
    rd.add_argument("--type", required=True, dest="reading_type",
                    choices=["consumption", "production"])
    rd.add_argument("--kwh", type=float, required=True)
    rd.add_argument("--cost", type=float, dest="cost_per_kwh", help="Cost per kWh")
    rd.add_argument("--activity", dest="activity_type",
                    choices=["irrigation", "processing", "storage", "lighting", "pump", "other"])
    rd.add_argument("--equipment-id")
    rd.add_argument("--notes")
    rd.add_argument("--json", action="store_true")

    # consumption
    co = sub.add_parser("consumption", help="Consumption summary")
    co.add_argument("--location-id", required=True)
    co.add_argument("--days", type=int, default=30)
    co.add_argument("--json", action="store_true")

    # efficiency
    ef = sub.add_parser("efficiency", help="Efficiency metrics")
    ef.add_argument("--location-id", required=True)
    ef.add_argument("--period", default="daily", choices=["daily", "weekly", "monthly"])
    ef.add_argument("--json", action="store_true")

    # add-renewable
    ar = sub.add_parser("add-renewable", help="Register renewable source")
    ar.add_argument("--location-id", required=True)
    ar.add_argument("--source-id", required=True)
    ar.add_argument("--renewable-type", required=True,
                    choices=["solar_pv", "solar_thermal", "wind", "biogas", "micro_hydro"])
    ar.add_argument("--capacity", type=float, required=True, dest="rated_capacity_kw")
    ar.add_argument("--annual-generation", type=float, help="Annual generation kWh")
    ar.add_argument("--carbon-offset", type=float, help="Carbon offset kg/year")
    ar.add_argument("--json", action="store_true")

    # renewable-summary
    rs = sub.add_parser("renewable-summary", help="Renewable energy summary")
    rs.add_argument("--location-id", required=True)
    rs.add_argument("--json", action="store_true")

    # dashboard
    db = sub.add_parser("dashboard", help="Energy dashboard")
    db.add_argument("--location-id", required=True)
    db.add_argument("--json", action="store_true")

    # carbon-intensity
    ci = sub.add_parser("carbon-intensity", help="Compute carbon intensity")
    ci.add_argument("--location-id", required=True)
    ci.add_argument("--json", action="store_true")

    # cost-analysis
    ca = sub.add_parser("cost-analysis", help="Energy cost analysis")
    ca.add_argument("--location-id", required=True)
    ca.add_argument("--days", type=int, default=30)
    ca.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command is None:
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "add-source":
            inst = date.fromisoformat(args.installation_date) if args.installation_date else None
            result = add_source(
                db, args.location_id, args.name, args.source_type,
                capacity_kw=args.capacity, installation_date=inst,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_source(result)
            print(output)

        elif args.command == "record":
            rd = date.fromisoformat(args.date) if args.date else date.today()
            result = record_reading(
                db, args.source_id, rd, args.reading_type, args.kwh,
                cost_per_kwh=args.cost_per_kwh, activity_type=args.activity_type,
                equipment_id=args.equipment_id, notes=args.notes,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_reading(result)
            print(output)

        elif args.command == "consumption":
            result = get_consumption(db, args.location_id, args.days)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_consumption(result)
            print(output)

        elif args.command == "efficiency":
            result = get_efficiency(db, args.location_id, args.period)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_efficiency(result)
            print(output)

        elif args.command == "add-renewable":
            result = add_renewable(
                db, args.location_id, args.source_id, args.renewable_type,
                args.rated_capacity_kw, annual_generation_kwh=args.annual_generation,
                carbon_offset_kg=args.carbon_offset,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_renewable(result)
            print(output)

        elif args.command == "renewable-summary":
            result = get_renewable_summary(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_renewable_summary(result)
            print(output)

        elif args.command == "dashboard":
            result = get_energy_dashboard(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_dashboard(result)
            print(output)

        elif args.command == "carbon-intensity":
            result = compute_carbon_intensity(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_carbon(result)
            print(output)

        elif args.command == "cost-analysis":
            result = get_cost_analysis(db, args.location_id, args.days)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_cost(result)
            print(output)

    finally:
        db.close()


# ============================================================
# Formatters
# ============================================================

def _format_source(r: dict) -> str:
    return f"Added source: {r['source_name']} ({r['source_type']}) {r['capacity_kw']} kW at {r['location_id'][:8]}..."


def _format_reading(r: dict) -> str:
    cost = f" @ ${r['cost_per_kwh']}/kWh = ${r['total_cost']}" if r['total_cost'] else ""
    return f"Recorded {r['reading_type']}: {r['kwh']} kWh{cost} ({r['reading_date']})"


def _format_consumption(r: dict) -> str:
    lines = [f"Consumption — {r['location_id'][:8]}... ({r['period_days']}d)"]
    lines.append(f"  Total: {r['total_kwh']:.1f} kWh  Cost: ${r['total_cost']:.2f}  Avg: ${r['avg_cost_per_kwh'] or 0:.4f}/kWh")
    for a in r["by_activity"]:
        act = a["activity_type"] or "unclassified"
        lines.append(f"  {act:15s}  {a['total_kwh']:8.1f} kWh  ${a['total_cost'] or 0:.2f}  ({a['readings']} readings)")
    return "\n".join(lines) if len(lines) > 1 else "No consumption data."


def _format_efficiency(r: dict) -> str:
    cm = r["current_metrics"]
    lines = [
        f"Efficiency — {r['location_id'][:8]}... ({r['period']})",
        f"  Consumption: {cm['total_consumption_kwh']:.1f} kWh",
        f"  Production:  {cm['total_production_kwh']:.1f} kWh",
        f"  Net:         {cm['net_energy_kwh']:.1f} kWh",
        f"  Renewable:   {cm['renewable_pct']:.1f}%",
    ]
    return "\n".join(lines)


def _format_renewable(r: dict) -> str:
    return (
        f"Renewable registered: {r['renewable_type']} ({r['rated_capacity_kw']} kW)\n"
        f"  Est. generation: {r['annual_generation_kwh']:.0f} kWh/year  Offset: {r['carbon_offset_kg']:.0f} kg CO2e/year"
    )


def _format_renewable_summary(r: dict) -> str:
    lines = [
        f"Renewable Summary — {r['location_id'][:8]}... ({r['active_sources']} sources)",
        f"  Capacity: {r['total_capacity_kw']:.1f} kW  Generation: {r['annual_generation_kwh']:.0f} kWh/year",
        f"  Carbon Offset: {r['total_carbon_offset_kg']:.0f} kg CO2e/year",
        f"  Renewable Share: {r['renewable_share_pct']:.1f}%",
    ]
    for s in r["sources"]:
        lines.append(f"    {s['renewable_type']:15s}  {s['rated_capacity_kw']:6.1f} kW  {s['annual_generation_kwh'] or 0:.0f} kWh/yr")
    return "\n".join(lines)


def _format_dashboard(r: dict) -> str:
    cons = r["consumption"]
    eff = r["efficiency"]
    ren = r["renewable"]
    lines = [
        f"Energy Dashboard — {r['location_id'][:8]}...",
        f"  Sources: {cons['sources_used']}  Readings: {cons['readings']}",
        f"  Total Consumption: {cons['total_kwh']:.1f} kWh  Cost: ${cons['total_cost']:.2f}",
        f"  Renewable Share: {ren['renewable_share_pct']:.1f}%",
        f"  Carbon Offset: {ren['total_carbon_offset_kg']:.0f} kg CO2e/year",
    ]
    for sb in r["source_breakdown"]:
        lines.append(f"    {sb['source_type']:20s}  {int(sb['count'])} sources  {sb['total_capacity']:.1f} kW")
    return "\n".join(lines)


def _format_carbon(r: dict) -> str:
    lines = [
        f"Carbon Intensity — {r['location_id'][:8]}... (30d)",
        f"  Intensity: {r['carbon_intensity_kg_co2e_kwh']:.4f} kg CO2e/kWh",
        f"  Total Emissions: {r['total_emissions_kg_co2e']:.1f} kg CO2e",
        f"  Renewable: {r['renewable_share_pct']:.1f}%",
        f"  Monthly Offset: {r['monthly_carbon_offset_kg']:.1f} kg",
        f"  Net Emissions: {r['net_monthly_emissions_kg']:.1f} kg CO2e/month",
    ]
    for b in r["breakdown"]:
        lines.append(f"    {b['source_type']:20s}  {b['consumption_kwh']:8.1f} kWh  {b['emissions_kg']:8.1f} kg CO2e")
    return "\n".join(lines)


def _format_cost(r: dict) -> str:
    lines = [
        f"Cost Analysis — {r['location_id'][:8]}... ({r['period_days']}d)",
        f"  Total: ${r['total_cost']:.2f}  ({r['total_kwh']:.1f} kWh @ ${r['avg_cost_per_kwh'] or 0:.4f}/kWh)",
        f"  Projected monthly: ${r['monthly_projected_cost']:.2f}",
    ]
    for a in r["by_activity"]:
        act = a["activity_type"] or "unclassified"
        lines.append(f"    {act:15s}  ${a['total_cost'] or 0:>8.2f}  {a['total_kwh']:8.1f} kWh")
    lines.append("  By source:")
    for s in r["by_source_type"]:
        lines.append(f"    {s['source_type']:20s}  ${s['total_cost'] or 0:>8.2f}  {s['total_kwh']:8.1f} kWh")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
