"""Core farm, crop, and climate report generators."""

from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
import psycopg2.extras

from .common import (
    _serialize_rows,
    _serialize_value,
)


def generate_farm_summary(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a farm summary report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
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

        # Harvest summary. Quantities from different units cannot be added or
        # averaged; retain unit totals and expose scalar measures only for one unit.
        cur.execute(
            """
            WITH filtered_harvest AS (
                SELECT quantity, unit, crop_cycle_id
                FROM harvest_event
                WHERE location_id = %s
                  AND status IN ('verified', 'published')
                  AND (%s::date IS NULL OR harvest_date >= %s::date)
                  AND (%s::date IS NULL OR harvest_date <= %s::date)
            ), unit_totals AS (
                SELECT unit, SUM(quantity) AS total_quantity
                FROM filtered_harvest
                GROUP BY unit
            )
            SELECT COUNT(*) AS total_harvests,
                   CASE WHEN COUNT(DISTINCT unit) <= 1
                        THEN COALESCE(SUM(quantity), 0) END AS total_quantity,
                   CASE WHEN COUNT(DISTINCT unit) <= 1
                        THEN COALESCE(AVG(quantity), 0) END AS avg_harvest_size,
                   COUNT(DISTINCT crop_cycle_id) AS cycles_with_harvest,
                   CASE WHEN COUNT(DISTINCT unit) = 1 THEN MIN(unit) END AS quantity_unit,
                   COALESCE(
                       (SELECT jsonb_object_agg(unit, total_quantity) FROM unit_totals),
                       '{}'::JSONB
                   ) AS total_quantity_by_unit
            FROM filtered_harvest
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
              AND (%s::date IS NULL OR ee.expense_date >= %s::date)
              AND (%s::date IS NULL OR ee.expense_date <= %s::date)
            GROUP BY ee.category ORDER BY total DESC
        """,
            (location_id, period_start, period_start, period_end, period_end),
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

        # Only published farm activity is eligible for this report. The projection
        # contains aggregate counts and reported hours; private free text, media,
        # participant identity, source lineage, and record IDs stay out of reports.
        cur.execute(
            """
            SELECT activity_type,
                   COUNT(*) AS activity_count,
                   COALESCE(SUM(labor_hours), 0) AS reported_labor_hours
            FROM farm_activity
            WHERE location_id = %s
              AND status = 'published'
              AND farm_activity_source_eligible_for_use(
                  source_system, source_id, source_raw, location_id
              )
              AND (%s::date IS NULL OR activity_date >= %s::date)
              AND (%s::date IS NULL OR activity_date <= %s::date)
            GROUP BY activity_type
            ORDER BY activity_type
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        activity_rows = [dict(r) for r in cur.fetchall()]
        activity_count = sum(int(row["activity_count"] or 0) for row in activity_rows)
        labor_hours = sum(
            (Decimal(str(row["reported_labor_hours"] or 0)) for row in activity_rows),
            Decimal("0"),
        )
        activity_type_breakdown = [
            {
                "activity_type": row["activity_type"],
                "activity_count": int(row["activity_count"] or 0),
                "reported_labor_hours": float(row["reported_labor_hours"] or 0),
                "reported_labor_hours_unit": "hours",
            }
            for row in activity_rows
        ]

    finally:
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
        "farm_activity_summary": {
            "published_activity_count": activity_count,
            "reported_labor_hours": float(labor_hours),
            "reported_labor_hours_unit": "hours",
            "by_activity_type": activity_type_breakdown,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return report


def generate_crop_noi(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a crop NOI report from the canonical crop-cycle NOI view."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT
                v.crop_cycle_id as cycle_id,
                cc.cycle_name,
                c.name as crop_name,
                p.name as plot_name,
                cc.status,
                cc.planting_date,
                cc.actual_harvest_date,
                cc.expected_yield,
                cc.actual_yield,
                cc.expected_revenue,
                v.gross_revenue,
                v.returns_discounts as returns_and_discounts,
                v.net_revenue,
                v.direct_crop_costs,
                v.allocated_shared_costs,
                v.total_costs,
                v.noi,
                v.operating_margin_pct,
                v.loss_rate_pct
            FROM v_crop_cycle_noi v
            JOIN crop_cycle cc ON cc.id = v.crop_cycle_id
            JOIN crop c ON cc.crop_id = c.id
            JOIN plot p ON cc.plot_id = p.id
            WHERE v.location_id = %s
              AND (%s::date IS NULL OR cc.planting_date >= %s::date)
              AND (%s::date IS NULL OR COALESCE(cc.actual_harvest_date, cc.expected_harvest_date) <= %s::date)
            ORDER BY cc.planting_date DESC
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        cycles = [dict(r) for r in cur.fetchall()]
        noi_data = []
        for cycle in cycles:
            gross_revenue = float(cycle["gross_revenue"] or 0)
            returns_and_discounts = float(cycle["returns_and_discounts"] or 0)
            net_revenue = float(cycle["net_revenue"] or 0)
            direct_crop_costs = float(cycle["direct_crop_costs"] or 0)
            allocated_shared_costs = float(cycle["allocated_shared_costs"] or 0)
            total_costs = float(cycle["total_costs"] or 0)
            noi = float(cycle["noi"] or 0)

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
                    # Retain the legacy keys while making their accounting basis
                    # explicit: actual revenue is net verified revenue, and the
                    # crop cost includes direct plus allocated shared costs.
                    "actual_revenue": net_revenue,
                    "allocated_cost": total_costs,
                    "gross_revenue": gross_revenue,
                    "returns_and_discounts": returns_and_discounts,
                    "net_revenue": net_revenue,
                    "direct_crop_costs": direct_crop_costs,
                    "allocated_shared_costs": allocated_shared_costs,
                    "total_costs": total_costs,
                    "crop_noi": noi,
                    "operating_margin_pct": float(cycle["operating_margin_pct"] or 0),
                    "loss_rate_pct": float(cycle["loss_rate_pct"] or 0),
                }
            )

    finally:
        cur.close()

    total_gross_revenue = sum(d["gross_revenue"] for d in noi_data)
    total_returns_and_discounts = sum(d["returns_and_discounts"] for d in noi_data)
    total_revenue = sum(d["net_revenue"] for d in noi_data)
    total_direct_costs = sum(d["direct_crop_costs"] for d in noi_data)
    total_shared_costs = sum(d["allocated_shared_costs"] for d in noi_data)
    total_cost = sum(d["total_costs"] for d in noi_data)
    total_noi = sum(d["crop_noi"] for d in noi_data)

    return {
        "report_type": "crop_noi",
        "location_id": location_id,
        "crop_cycles": noi_data,
        "summary": {
            "total_revenue": total_revenue,
            "total_gross_revenue": total_gross_revenue,
            "total_returns_and_discounts": total_returns_and_discounts,
            "total_direct_crop_costs": total_direct_costs,
            "total_allocated_shared_costs": total_shared_costs,
            "total_cost": total_cost,
            "total_noi": total_noi,
            "overall_margin_pct": (total_noi / total_revenue * 100) if total_revenue > 0 else 0,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_environmental(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate an environmental impact report."""
    if not location_id:
        raise ValueError("environmental requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
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

    finally:
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
    if not location_id:
        raise ValueError("revenue_multiplier requires an explicit location_id")

    from dataclasses import asdict

    from ...revenue_multiplier.analyzer import analyze_location

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
    try:
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

    finally:
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
    if not location_id:
        raise ValueError("climate_impact requires an explicit location_id")
    # Determine reporting year from period_start or current year
    from datetime import datetime as _dt

    from ...analytics.carbon_balance import (
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
    try:
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
        """
        )
        protocols = [dict(r) for r in cur.fetchall()]

    finally:
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
        "limitations": [
            "Active operations protocols are shared platform reference metadata, not location-specific evidence.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
