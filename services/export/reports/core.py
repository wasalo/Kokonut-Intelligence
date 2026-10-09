"""Core farm, crop, and climate report generators."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from .common import (
    _serialize_rows,
    _serialize_value,
)


def generate_farm_summary(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a farm summary report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Location info
    cur.execute("SELECT * FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    if not location:
        raise ValueError(f"Location {location_id} not found")

    # Farms
    cur.execute("SELECT * FROM farm WHERE location_id = %s", (location_id,))
    farms = [dict(r) for r in cur.fetchall()]

    # Plots
    cur.execute(
        """
        SELECT p.*, f.name as farm_name
        FROM plot p JOIN farm f ON p.farm_id = f.id
        WHERE f.location_id = %s
    """,
        (location_id,),
    )
    plots = [dict(r) for r in cur.fetchall()]

    # Active crop cycles
    cur.execute(
        """
        SELECT cc.*, c.name as crop_name, p.name as plot_name
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s
    """,
        (location_id,),
    )
    crop_cycles = [dict(r) for r in cur.fetchall()]

    # Harvest summary
    cur.execute(
        """
        SELECT
            COUNT(*) as total_harvests,
            COALESCE(SUM(quantity), 0) as total_quantity,
            COALESCE(AVG(quantity), 0) as avg_harvest_size,
            COUNT(DISTINCT crop_cycle_id) as cycles_with_harvest
        FROM harvest_event
        WHERE location_id = %s
        AND (%s::date IS NULL OR harvest_date >= %s::date)
        AND (%s::date IS NULL OR harvest_date <= %s::date)
    """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    harvest_summary = dict(cur.fetchone())

    # Financial summary
    cur.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'revenue' THEN amount_usd ELSE 0 END), 0) as total_revenue,
            COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount_usd ELSE 0 END), 0) as total_expenses,
            COALESCE(SUM(CASE WHEN transaction_type = 'revenue' THEN amount_usd ELSE 0 END)
                - SUM(CASE WHEN transaction_type = 'expense' THEN amount_usd ELSE 0 END), 0) as net_income
        FROM financial_transaction
        WHERE location_id = %s
        AND (%s::date IS NULL OR transaction_date >= %s::date)
        AND (%s::date IS NULL OR transaction_date <= %s::date)
    """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    financial = dict(cur.fetchone())

    # Expense breakdown
    cur.execute(
        """
        SELECT ee.category, COALESCE(SUM(ee.amount), 0) as total
        FROM expense_event ee
        WHERE ee.location_id = %s AND ee.status IN ('verified', 'published')
        GROUP BY ee.category ORDER BY total DESC
    """,
        (location_id,),
    )
    expense_breakdown = [dict(r) for r in cur.fetchall()]

    # Attestation coverage
    cur.execute(
        """
        SELECT
            COUNT(*) as total_records,
            COUNT(CASE WHEN status = 'published' THEN 1 END) as attested,
            COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft
        FROM attestation_record
        WHERE subject_type = 'location' AND subject_id = %s
    """,
        (location_id,),
    )
    attestation = dict(cur.fetchone())

    cur.close()

    report = {
        "report_type": "farm_summary",
        "location": {k: _serialize_value(v) for k, v in dict(location).items() if k != "boundary" and k != "center"},
        "farms": _serialize_rows(farms),
        "plots": _serialize_rows(plots),
        "crop_cycles": _serialize_rows(crop_cycles),
        "harvest_summary": harvest_summary,
        "financial_summary": financial,
        "expense_breakdown": expense_breakdown,
        "attestation_coverage": attestation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return report


def generate_crop_noi(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a crop net operating income report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT
            cc.id as cycle_id,
            cc.cycle_name,
            c.name as crop_name,
            p.name as plot_name,
            cc.status,
            cc.planting_date,
            cc.actual_harvest_date,
            cc.expected_yield,
            cc.actual_yield,
            cc.expected_revenue,
            cc.actual_revenue
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s
        ORDER BY cc.planting_date DESC
    """,
        (location_id,),
    )
    cycles = [dict(r) for r in cur.fetchall()]

    # Get expenses per crop cycle
    noi_data = []
    for cycle in cycles:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(ca.allocated_amount), 0) as total_allocated_cost
            FROM crop_cost_allocation ca
            WHERE ca.crop_cycle_id = %s
        """,
            (cycle["cycle_id"],),
        )
        cost = dict(cur.fetchone())

        actual_revenue = float(cycle["actual_revenue"] or 0)
        allocated_cost = float(cost["total_allocated_cost"])
        noi = actual_revenue - allocated_cost

        noi_data.append(
            {
                "cycle_id": str(cycle["cycle_id"]),
                "cycle_name": cycle["cycle_name"],
                "crop_name": cycle["crop_name"],
                "plot_name": cycle["plot_name"],
                "status": cycle["status"],
                "planting_date": cycle["planting_date"].isoformat() if cycle["planting_date"] else None,
                "actual_harvest_date": cycle["actual_harvest_date"].isoformat()
                if cycle["actual_harvest_date"]
                else None,
                "expected_yield": float(cycle["expected_yield"] or 0),
                "actual_yield": float(cycle["actual_yield"] or 0),
                "expected_revenue": float(cycle["expected_revenue"] or 0),
                "actual_revenue": actual_revenue,
                "allocated_cost": allocated_cost,
                "crop_noi": noi,
                "operating_margin_pct": (noi / actual_revenue * 100) if actual_revenue > 0 else 0,
            }
        )

    cur.close()

    total_revenue = sum(d["actual_revenue"] for d in noi_data)
    total_cost = sum(d["allocated_cost"] for d in noi_data)
    total_noi = total_revenue - total_cost

    return {
        "report_type": "crop_noi",
        "location_id": location_id,
        "crop_cycles": noi_data,
        "summary": {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_noi": total_noi,
            "overall_margin_pct": (total_noi / total_revenue * 100) if total_revenue > 0 else 0,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_environmental(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate an environmental impact report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Soil carbon measurements
    cur.execute(
        """
        SELECT measurement_date, carbon_tonnes_per_ha, measurement_method, depth_cm
        FROM soil_carbon_measurement
        WHERE location_id = %s
        ORDER BY measurement_date
    """,
        (location_id,),
    )
    soil_carbon = [dict(r) for r in cur.fetchall()]

    # Species observations
    cur.execute(
        """
        SELECT observation_date, count, habitat_type, notes
        FROM species_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """,
        (location_id,),
    )
    species = [dict(r) for r in cur.fetchall()]

    # Remote sensing
    cur.execute(
        """
        SELECT observation_date, ndvi, ndre, cloud_cover_pct
        FROM remote_sensing_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """,
        (location_id,),
    )
    remote_sensing = [dict(r) for r in cur.fetchall()]

    # Loss events (environmental)
    cur.execute(
        """
        SELECT loss_date, loss_type, quantity, unit, cause
        FROM loss_event
        WHERE location_id = %s
        ORDER BY loss_date
    """,
        (location_id,),
    )
    losses = [dict(r) for r in cur.fetchall()]

    cur.close()

    def _serialize(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return obj

    return {
        "report_type": "environmental",
        "location_id": location_id,
        "soil_carbon": [{k: _serialize(v) for k, v in r.items()} for r in soil_carbon],
        "species_observations": [{k: _serialize(v) for k, v in r.items()} for r in species],
        "remote_sensing": [{k: _serialize(v) for k, v in r.items()} for r in remote_sensing],
        "loss_events": [{k: _serialize(v) for k, v in r.items()} for r in losses],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_revenue_multiplier(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a revenue multiplier opportunity map report."""
    from dataclasses import asdict

    from ..revenue_multiplier.analyzer import analyze_location

    result = analyze_location(location_id)
    return {
        "report_type": "revenue_multiplier",
        "location_id": location_id,
        "location_name": result.location_name,
        "overall_score": result.overall_score,
        "total_opportunity_usd": result.total_opportunity_usd,
        "dimensions": [asdict(d) for d in result.dimensions],
        "generated_at": result.generated_at,
    }


def generate_forecast_summary(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a forecast summary report across all scenarios."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all scenarios for this location
    cur.execute(
        """
        SELECT id, name, scenario_type, status, assumptions, created_at
        FROM forecast_scenario
        WHERE location_id = %s
        ORDER BY created_at DESC
    """,
        (location_id,),
    )

    # Get all forecast outputs grouped by scenario
    cur.execute(
        """
        SELECT
            fo.scenario_id,
            fs.name as scenario_name,
            fs.scenario_type,
            fo.metric_name,
            fo.value,
            fo.unit,
            fo.confidence_low,
            fo.confidence_high,
            fo.inputs,
            fo.period_start,
            fo.period_end,
            fo.calculated_at
        FROM forecast_output fo
        JOIN forecast_scenario fs ON fo.scenario_id = fs.id
        WHERE fo.location_id = %s
        ORDER BY fs.scenario_type, fo.metric_name
    """,
        (location_id,),
    )
    outputs = [dict(r) for r in cur.fetchall()]

    # Group outputs by scenario
    scenarios_data = {}
    for out in outputs:
        sid = str(out["scenario_id"])
        if sid not in scenarios_data:
            scenarios_data[sid] = {
                "scenario_name": out["scenario_name"],
                "scenario_type": out["scenario_type"],
                "period_start": out["period_start"],
                "period_end": out["period_end"],
                "calculated_at": out["calculated_at"].isoformat() if out["calculated_at"] else None,
                "metrics": {},
            }
        scenarios_data[sid]["metrics"][out["metric_name"]] = {
            "value": float(out["value"]) if out["value"] else None,
            "unit": out["unit"],
            "confidence_low": float(out["confidence_low"]) if out["confidence_low"] else None,
            "confidence_high": float(out["confidence_high"]) if out["confidence_high"] else None,
            "inputs": dict(out["inputs"]) if out["inputs"] else {},
        }

    # Get location info
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    loc = cur.fetchone()
    location_name = loc["name"] if loc else "Unknown"

    cur.close()

    return {
        "report_type": "forecast",
        "location_id": location_id,
        "location_name": location_name,
        "scenario_count": len(scenarios_data),
        "scenarios": scenarios_data,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_climate_impact(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a climate-impact report for a location and year."""
    # Determine reporting year from period_start or current year
    from datetime import datetime as _dt

    from ..analytics.carbon_balance import (
        compute_carbon_balance,
        compute_ghg_emissions,
        compute_regenerative_score,
        compute_tree_carbon,
    )

    if period_start:
        reporting_year = int(period_start[:4])
    else:
        reporting_year = _dt.now(timezone.utc).year - 1  # default to last full year

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Location info
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    loc = cur.fetchone()
    location_name = loc["name"] if loc else "Unknown"

    # Climate impact summary (if stored)
    cur.execute(
        """
        SELECT * FROM climate_impact_summary
        WHERE location_id = %s AND reporting_year = %s
        LIMIT 1
    """,
        (location_id, reporting_year),
    )
    summary_row = cur.fetchone()

    # Framework phases
    cur.execute(
        """
        SELECT framework_key, phase, phase_status, phase_start_date, review_cadence
        FROM framework_phase
        WHERE location_id = %s AND phase_status = 'active'
        ORDER BY framework_key
    """,
        (location_id,),
    )
    phases = [dict(r) for r in cur.fetchall()]

    # Operations protocols
    cur.execute(
        """
        SELECT protocol_key, title, section, version, review_cadence
        FROM operations_protocol
        WHERE status = 'active'
        ORDER BY section
    """,
        (location_id,),
    )
    protocols = [dict(r) for r in cur.fetchall()]

    cur.close()

    # Analytics from live data
    carbon_balance = compute_carbon_balance(conn, location_id, reporting_year)
    ghg = compute_ghg_emissions(conn, location_id)
    tree = compute_tree_carbon(conn, location_id)
    regen = compute_regenerative_score(conn, location_id)

    return {
        "report_type": "climate_impact",
        "location_id": location_id,
        "location_name": location_name,
        "reporting_year": reporting_year,
        "carbon_balance": carbon_balance,
        "ghg_emissions": ghg,
        "tree_carbon": tree,
        "regenerative_score": regen,
        "framework_phases": phases,
        "operations_protocols": [
            {"title": p["title"], "section": p["section"], "version": p["version"]} for p in protocols
        ],
        "stored_summary": dict(summary_row) if summary_row else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
