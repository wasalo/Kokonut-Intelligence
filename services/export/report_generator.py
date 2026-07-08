#!/usr/bin/env python3
"""
Report Generator — Farm Summary, Crop NOI, Environmental Impact

Generates structured report snapshots with hash verification.
Stores results in the report_snapshot table.

Usage:
    python3 -m services.export.report_generator --type farm_summary --location-id UUID
    python3 -m services.export.report_generator --type crop_noi --location-id UUID
    python3 -m services.export.report_generator --type environmental --location-id UUID
    python3 -m services.export.report_generator --list
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras


from ..common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_pg():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


# ---------------------------------------------------------------------------
# Report Generators
# ---------------------------------------------------------------------------

def _serialize_value(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (bytes, memoryview)):
        return hashlib.sha256(bytes(obj)).hexdigest()[:16]
    return obj


def _serialize_rows(rows: list[dict]) -> list[dict]:
    return [{k: _serialize_value(v) for k, v in row.items()} for row in rows]


def fetch_public_interest_context(conn, location_id: str) -> dict:
    """Fetch public-interest context attached to every Green Paper report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_stakeholder_feedback_summary
        WHERE location_id = %s
        ORDER BY feedback_date DESC, id
        LIMIT 10
        """,
        (location_id,),
    )
    public_feedback = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT claim_category, claim_type, claim_text, claim_value, claim_unit,
               evidence_maturity, evidence_maturity_label, confidence_level,
               methodology_ref, external_verifier, attestation_uid
        FROM v_public_impact_claim_summary
        WHERE location_id = %s
        ORDER BY claim_date DESC, id
        LIMIT 10
        """,
        (location_id,),
    )
    public_claims = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT claim_category, claim_type, status, public_claim,
               evidence_maturity, COUNT(*) AS claim_count,
               COUNT(*) FILTER (
                   WHERE public_claim = TRUE AND evidence_maturity < 4
               ) AS public_claims_below_threshold,
               COUNT(*) FILTER (
                   WHERE public_claim = TRUE
                     AND claim_category = 'carbon'
                     AND (
                       evidence_maturity < 6
                       OR external_verifier IS NULL
                       OR methodology_ref IS NULL
                     )
               ) AS carbon_publication_gaps,
               COUNT(*) FILTER (
                   WHERE evidence_cid IS NULL
                     AND evidence_hash IS NULL
                     AND attestation_uid IS NULL
               ) AS missing_evidence_links
        FROM impact_claim
        WHERE location_id = %s AND status != 'rejected'
        GROUP BY claim_category, claim_type, status, public_claim, evidence_maturity
        ORDER BY carbon_publication_gaps DESC, public_claims_below_threshold DESC,
                 missing_evidence_links DESC, claim_count DESC
        """,
        (location_id,),
    )
    evidence_gaps = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, status,
               consent_given, consent_scope, is_public, evidence_maturity,
               COUNT(*) AS feedback_count,
               COUNT(*) FILTER (WHERE consent_given = FALSE) AS private_or_no_consent_count,
               COUNT(*) FILTER (WHERE harms_or_unintended_consequences IS NOT NULL) AS harm_or_unintended_consequence_count
        FROM stakeholder_feedback
        WHERE location_id = %s AND status != 'rejected'
        GROUP BY stakeholder_group, feedback_type, sentiment, status,
                 consent_given, consent_scope, is_public, evidence_maturity
        ORDER BY feedback_count DESC, stakeholder_group
        """,
        (location_id,),
    )
    feedback_summary = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT practice_name, practice_type, stakeholder_group, language,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_cultural_context_summary
        WHERE location_id = %s
        ORDER BY practice_type, practice_name
        LIMIT 10
        """,
        (location_id,),
    )
    cultural_context = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT metric_key, metric_name, stakeholder_group, language,
               score_value, count_value, public_summary, evidence_maturity,
               evidence_maturity_label
        FROM v_public_wellbeing_metric_summary
        WHERE location_id = %s
        ORDER BY observation_date DESC, metric_key
        LIMIT 10
        """,
        (location_id,),
    )
    wellbeing_metrics = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT action_type, action_date, stakeholder_group, metric_name,
               decision_status, public_summary, evidence_maturity,
               evidence_maturity_label
        FROM v_public_participatory_governance_summary
        WHERE location_id = %s
        ORDER BY action_date DESC, action_type
        LIMIT 10
        """,
        (location_id,),
    )
    participatory_actions = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT plan_name, farm_model, sustainability_status, grant_dependency_pct,
               reinvestment_pct, public_goods_allocation_pct, runway_months,
               projected_annual_revenue_usd, projected_annual_noi_usd,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_financial_sustainability_summary
        WHERE location_id = %s
        ORDER BY plan_period_start DESC, plan_name
        LIMIT 5
        """,
        (location_id,),
    )
    financial_sustainability = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT risk_category, likelihood, impact_level, residual_risk_level,
               owner_role, review_cadence, next_review_date, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_risk_mitigation_summary
        WHERE location_id = %s
        ORDER BY next_review_date NULLS LAST, risk_category
        LIMIT 10
        """,
        (location_id,),
    )
    risk_mitigation = [dict(r) for r in cur.fetchall()]
    cur.close()

    has_private_feedback = any(row.get("private_or_no_consent_count", 0) for row in feedback_summary)
    has_carbon_gaps = any(row.get("carbon_publication_gaps", 0) for row in evidence_gaps)
    has_missing_evidence = any(row.get("missing_evidence_links", 0) for row in evidence_gaps)

    limitations = []
    if has_private_feedback:
        limitations.append("Some stakeholder feedback is private or lacks public consent and is summarized only in aggregate.")
    if has_carbon_gaps:
        limitations.append("Some public carbon claims are not publication-ready until Level 6 verifier and methodology requirements are satisfied.")
    if has_missing_evidence:
        limitations.append("Some claims are missing CIDs, hashes, or attestation UIDs and should be treated as lower-confidence evidence.")
    if not limitations:
        limitations.append("No public-interest evidence gaps were detected for the current governed dataset.")

    return {
        "principles": [
            "Publish only governed records that are verified, published, consented, or explicitly public-safe.",
            "Keep private stakeholder evidence off public reports unless consent scope allows publication.",
            "Separate public carbon-balance claims from credit issuance claims unless external verification supports issuance.",
            "Show limitations and evidence gaps beside positive impact claims.",
        ],
        "public_feedback": _serialize_rows(public_feedback),
        "public_claims": _serialize_rows(public_claims),
        "evidence_gaps": _serialize_rows(evidence_gaps),
        "stakeholder_feedback_summary": _serialize_rows(feedback_summary),
        "cultural_context": _serialize_rows(cultural_context),
        "wellbeing_metrics": _serialize_rows(wellbeing_metrics),
        "participatory_actions": _serialize_rows(participatory_actions),
        "financial_sustainability": _serialize_rows(financial_sustainability),
        "risk_mitigation": _serialize_rows(risk_mitigation),
        "limitations": limitations,
    }


def attach_public_interest_context(conn, report_data: dict, location_id: Optional[str]) -> dict:
    """Attach public-interest context without changing report-specific payloads."""
    if location_id:
        report_data["public_interest"] = fetch_public_interest_context(conn, location_id)
    return report_data

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
    cur.execute("""
        SELECT p.*, f.name as farm_name
        FROM plot p JOIN farm f ON p.farm_id = f.id
        WHERE f.location_id = %s
    """, (location_id,))
    plots = [dict(r) for r in cur.fetchall()]

    # Active crop cycles
    cur.execute("""
        SELECT cc.*, c.name as crop_name, p.name as plot_name
        FROM crop_cycle cc
        JOIN crop c ON cc.crop_id = c.id
        JOIN plot p ON cc.plot_id = p.id
        WHERE cc.location_id = %s
    """, (location_id,))
    crop_cycles = [dict(r) for r in cur.fetchall()]

    # Harvest summary
    cur.execute("""
        SELECT
            COUNT(*) as total_harvests,
            COALESCE(SUM(quantity), 0) as total_quantity,
            COALESCE(AVG(quantity), 0) as avg_harvest_size,
            COUNT(DISTINCT crop_cycle_id) as cycles_with_harvest
        FROM harvest_event
        WHERE location_id = %s
        AND (%s::date IS NULL OR harvest_date >= %s::date)
        AND (%s::date IS NULL OR harvest_date <= %s::date)
    """, (location_id, period_start, period_start, period_end, period_end))
    harvest_summary = dict(cur.fetchone())

    # Financial summary
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'revenue' THEN amount_usd ELSE 0 END), 0) as total_revenue,
            COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount_usd ELSE 0 END), 0) as total_expenses,
            COALESCE(SUM(CASE WHEN transaction_type = 'revenue' THEN amount_usd ELSE 0 END)
                - SUM(CASE WHEN transaction_type = 'expense' THEN amount_usd ELSE 0 END), 0) as net_income
        FROM financial_transaction
        WHERE location_id = %s
        AND (%s::date IS NULL OR transaction_date >= %s::date)
        AND (%s::date IS NULL OR transaction_date <= %s::date)
    """, (location_id, period_start, period_start, period_end, period_end))
    financial = dict(cur.fetchone())

    # Expense breakdown
    cur.execute("""
        SELECT ee.category, COALESCE(SUM(ee.amount), 0) as total
        FROM expense_event ee
        WHERE ee.location_id = %s AND ee.status IN ('verified', 'published')
        GROUP BY ee.category ORDER BY total DESC
    """, (location_id,))
    expense_breakdown = [dict(r) for r in cur.fetchall()]

    # Attestation coverage
    cur.execute("""
        SELECT
            COUNT(*) as total_records,
            COUNT(CASE WHEN status = 'published' THEN 1 END) as attested,
            COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft
        FROM attestation_record
        WHERE subject_type = 'location' AND subject_id = %s
    """, (location_id,))
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

    cur.execute("""
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
    """, (location_id,))
    cycles = [dict(r) for r in cur.fetchall()]

    # Get expenses per crop cycle
    noi_data = []
    for cycle in cycles:
        cur.execute("""
            SELECT
                COALESCE(SUM(ca.allocated_amount), 0) as total_allocated_cost
            FROM crop_cost_allocation ca
            WHERE ca.crop_cycle_id = %s
        """, (cycle["cycle_id"],))
        cost = dict(cur.fetchone())

        actual_revenue = float(cycle["actual_revenue"] or 0)
        allocated_cost = float(cost["total_allocated_cost"])
        noi = actual_revenue - allocated_cost

        noi_data.append({
            "cycle_id": str(cycle["cycle_id"]),
            "cycle_name": cycle["cycle_name"],
            "crop_name": cycle["crop_name"],
            "plot_name": cycle["plot_name"],
            "status": cycle["status"],
            "planting_date": cycle["planting_date"].isoformat() if cycle["planting_date"] else None,
            "actual_harvest_date": cycle["actual_harvest_date"].isoformat() if cycle["actual_harvest_date"] else None,
            "expected_yield": float(cycle["expected_yield"] or 0),
            "actual_yield": float(cycle["actual_yield"] or 0),
            "expected_revenue": float(cycle["expected_revenue"] or 0),
            "actual_revenue": actual_revenue,
            "allocated_cost": allocated_cost,
            "crop_noi": noi,
            "operating_margin_pct": (noi / actual_revenue * 100) if actual_revenue > 0 else 0,
        })

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
    cur.execute("""
        SELECT measurement_date, carbon_tonnes_per_ha, measurement_method, depth_cm
        FROM soil_carbon_measurement
        WHERE location_id = %s
        ORDER BY measurement_date
    """, (location_id,))
    soil_carbon = [dict(r) for r in cur.fetchall()]

    # Species observations
    cur.execute("""
        SELECT observation_date, count, habitat_type, notes
        FROM species_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """, (location_id,))
    species = [dict(r) for r in cur.fetchall()]

    # Remote sensing
    cur.execute("""
        SELECT observation_date, ndvi, ndre, cloud_cover_pct
        FROM remote_sensing_observation
        WHERE location_id = %s
        ORDER BY observation_date
    """, (location_id,))
    remote_sensing = [dict(r) for r in cur.fetchall()]

    # Loss events (environmental)
    cur.execute("""
        SELECT loss_date, loss_type, quantity, unit, cause
        FROM loss_event
        WHERE location_id = %s
        ORDER BY loss_date
    """, (location_id,))
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
    cur.execute("""
        SELECT id, name, scenario_type, status, assumptions, created_at
        FROM forecast_scenario
        WHERE location_id = %s
        ORDER BY created_at DESC
    """, (location_id,))
    scenarios = [dict(r) for r in cur.fetchall()]

    # Get all forecast outputs grouped by scenario
    cur.execute("""
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
    """, (location_id,))
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
    from ..analytics.carbon_balance import (
        compute_ghg_emissions, compute_tree_carbon,
        compute_carbon_balance, compute_regenerative_score,
    )

    # Determine reporting year from period_start or current year
    from datetime import datetime as _dt
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
    cur.execute("""
        SELECT * FROM climate_impact_summary
        WHERE location_id = %s AND reporting_year = %s
        LIMIT 1
    """, (location_id, reporting_year))
    summary_row = cur.fetchone()

    # Framework phases
    cur.execute("""
        SELECT framework_key, phase, phase_status, phase_start_date, review_cadence
        FROM framework_phase
        WHERE location_id = %s AND phase_status = 'active'
        ORDER BY framework_key
    """, (location_id,))
    phases = [dict(r) for r in cur.fetchall()]

    # Operations protocols
    cur.execute("""
        SELECT protocol_key, title, section, version, review_cadence
        FROM operations_protocol
        WHERE status = 'active'
        ORDER BY section
    """, (location_id,))
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
            {"title": p["title"], "section": p["section"], "version": p["version"]}
            for p in protocols
        ],
        "stored_summary": dict(summary_row) if summary_row else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_ebf_scorecard(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe EBF scorecard report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM v_public_ebf_scorecard_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR period_start >= %s::date)
          AND (%s::date IS NULL OR period_end <= %s::date)
        ORDER BY period_end DESC, scorecard_id
        LIMIT 1
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    summary = cur.fetchone()

    pillars = []
    if summary:
        cur.execute(
            """
            SELECT pillar_key, pillar_name, normalized_score, confidence_level,
                   trend_direction, score_evidence_maturity_label,
                   evidence_summary, uncertainty_notes
            FROM v_public_ebf_scorecard
            WHERE scorecard_id = %s
            ORDER BY pillar_key
            """,
            (summary["scorecard_id"],),
        )
        pillars = [dict(r) for r in cur.fetchall()]
    cur.close()

    return {
        "report_type": "ebf_scorecard",
        "location_id": location_id,
        "summary": _serialize_rows([dict(summary)])[0] if summary else None,
        "pillars": _serialize_rows(pillars),
        "limitations": [
            "This report includes only published EBF scorecards that meet public evidence maturity gates.",
            "The carbon pillar is public only when evidence maturity is Level 6.",
            "Use EBF scorecards for evidence-backed learning, not farm ranking.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_holistic_wellbeing(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe holistic well-being report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    location_name = location["name"] if location else None

    cur.execute(
        """
        SELECT practice_name, practice_type, stakeholder_group, language,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_cultural_context_summary
        WHERE location_id = %s
        ORDER BY practice_type, practice_name
        """,
        (location_id,),
    )
    cultural_context = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT metric_key, metric_name, observation_date, stakeholder_group,
               language, score_value, count_value, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_wellbeing_metric_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR observation_date >= %s::date)
          AND (%s::date IS NULL OR observation_date <= %s::date)
        ORDER BY observation_date DESC, metric_key
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    wellbeing_metrics = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT action_type, action_date, stakeholder_group, feedback_type,
               sentiment, metric_name, metric_proposal_status, decision_status,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_participatory_governance_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR action_date >= %s::date)
          AND (%s::date IS NULL OR action_date <= %s::date)
        ORDER BY action_date DESC, action_type
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    participatory_actions = [dict(r) for r in cur.fetchall()]
    cur.close()

    languages = sorted({row["language"] for row in wellbeing_metrics + cultural_context if row.get("language")})

    return {
        "report_type": "holistic_wellbeing",
        "location_id": location_id,
        "location_name": location_name,
        "languages": languages,
        "cultural_context": _serialize_rows(cultural_context),
        "wellbeing_metrics": _serialize_rows(wellbeing_metrics),
        "participatory_actions": _serialize_rows(participatory_actions),
        "limitations": [
            "This report includes public-safe summaries and aggregate signals only.",
            "Private stakeholder feedback, household-level observations, and non-consented cultural knowledge remain excluded.",
            "Well-being metrics are learning signals unless externally verified by a named reviewer or methodology.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_financial_sustainability(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe financial sustainability report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_financial_sustainability_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR plan_period_start >= %s::date)
          AND (%s::date IS NULL OR plan_period_end IS NULL OR plan_period_end <= %s::date)
        ORDER BY plan_period_start DESC, plan_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    plans = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "financial_sustainability",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "plans": _serialize_rows(plans),
        "limitations": [
            "This report summarizes published financial sustainability plans only.",
            "Projected revenue, NOI, runway, and grant dependency are planning signals, not guarantees.",
            "Private financial terms and draft capital discussions are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_risk_mitigation(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe risk mitigation report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_risk_mitigation_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR review_date IS NULL OR review_date >= %s::date)
          AND (%s::date IS NULL OR review_date IS NULL OR review_date <= %s::date)
        ORDER BY next_review_date NULLS LAST, risk_category
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    risks = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "risk_mitigation",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "risks": _serialize_rows(risks),
        "limitations": [
            "This report summarizes published risk register entries only.",
            "Insurance scope may be summarized when full policy documents are private or unavailable for publication.",
            "Residual risk remains a reviewer-assessed signal and should be revisited on the listed cadence.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_scaling_roadmap(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe scaling roadmap report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_scaling_roadmap_summary
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR target_date >= %s::date)
              AND (%s::date IS NULL OR target_date <= %s::date)
            ORDER BY target_date, roadmap_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_scaling_roadmap_summary
            WHERE (%s::date IS NULL OR target_date >= %s::date)
              AND (%s::date IS NULL OR target_date <= %s::date)
            ORDER BY target_date, roadmap_name
            """,
            (period_start, period_start, period_end, period_end),
        )
    milestones = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "scaling_roadmap",
        "location_id": location_id,
        "milestones": _serialize_rows(milestones),
        "total_capital_required_usd": round(sum(float(row.get("capital_required_usd") or 0) for row in milestones), 2),
        "limitations": [
            "Scaling roadmap entries are milestone plans, not guaranteed expansion commitments.",
            "Capital requirements, partner dependencies, and risk gates should be reviewed before each expansion decision.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_green_paper_publication_status(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe Green Paper publication status report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM v_public_green_paper_publication_status
        ORDER BY target_publication_date DESC, version DESC
        """
    )
    reviews = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "green_paper_publication_status",
        "location_id": location_id,
        "reviews": _serialize_rows(reviews),
        "limitations": [
            "Draft or private reviewer notes are not exposed in public publication status reports.",
            "Final publication requires stakeholder approval plus publication hash or CID metadata.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_capital_efficiency(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe capital efficiency and regenerative ROI scenario report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_capital_efficiency_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR period_start >= %s::date)
          AND (%s::date IS NULL OR period_end IS NULL OR period_end <= %s::date)
        ORDER BY period_start DESC, scenario_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    scenarios = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT *
        FROM v_public_regenerative_efficiency_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR observation_date >= %s::date)
          AND (%s::date IS NULL OR observation_date <= %s::date)
        ORDER BY observation_date DESC, practice_type
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    regenerative_observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "capital_efficiency",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "scenarios": _serialize_rows(scenarios),
        "regenerative_efficiency": _serialize_rows(regenerative_observations),
        "limitations": [
            "Capital efficiency and payback values are scenario evidence, not guaranteed returns.",
            "Private capital terms and draft financial assumptions are excluded.",
            "Regenerative savings should be recalculated as additional verified expense, output, and practice records mature.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_governance_throughput(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe governance throughput report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_governance_throughput_summary
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR proposal_created_at::date >= %s::date)
              AND (%s::date IS NULL OR proposal_created_at::date <= %s::date)
            ORDER BY proposal_created_at DESC, proposal_code
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_governance_throughput_summary
            WHERE (%s::date IS NULL OR proposal_created_at::date >= %s::date)
              AND (%s::date IS NULL OR proposal_created_at::date <= %s::date)
            ORDER BY proposal_created_at DESC, proposal_code
            """,
            (period_start, period_start, period_end, period_end),
        )
    observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    latencies = [float(row["decision_latency_days"]) for row in observations if row.get("decision_latency_days") is not None]
    return {
        "report_type": "governance_throughput",
        "location_id": location_id,
        "observations": _serialize_rows(observations),
        "average_decision_latency_days": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "limitations": [
            "Governance throughput reflects published proposal timestamps only.",
            "Off-platform discussion, informal consensus, and private negotiation time may be excluded.",
            "Fast decisions are not automatically better decisions; risk gates and stakeholder review still apply.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_capital_provider_utility(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe capital-provider utility scenario report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_capital_provider_utility_summary
        WHERE location_id = %s
        ORDER BY utility_score DESC NULLS LAST, scenario_name
        """,
        (location_id,),
    )
    scenarios = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "capital_provider_utility",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "scenarios": _serialize_rows(scenarios),
        "limitations": [
            "Capital-provider utility scenarios are planning evidence, not an offer of securities or guaranteed returns.",
            "Private funder terms, side letters, and unpublished negotiations are excluded.",
            "Public-goods, verification, and learning outputs should be evaluated alongside financial risk.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_bio_factory_batch(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-organic fertilizer batch report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_factory_batch_summary
        WHERE (location_id = %s OR location_id IS NULL)
          AND (%s::date IS NULL OR production_start_date >= %s::date)
          AND (%s::date IS NULL OR production_end_date IS NULL OR production_end_date <= %s::date)
        ORDER BY production_start_date DESC, batch_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    batches = [dict(r) for r in cur.fetchall()]
    cur.close()
    total_kg = sum(float(row.get("output_kg_total") or 0) for row in batches)
    total_liters = sum(float(row.get("output_liters_total") or 0) for row in batches)
    return {
        "report_type": "bio_factory_batch",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "batches": _serialize_rows(batches),
        "total_kg_produced": round(total_kg, 2),
        "total_liters_produced": round(total_liters, 2),
        "limitations": [
            "Bio-factory batch yields are smallholder pilot evidence, not commercial production guarantees.",
            "Yield varies with feedstock moisture, microbial activity, and process conditions.",
            "Public recipes and batch records are not commercial endorsements.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_bio_input_provenance(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-input provenance report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_input_provenance_summary
        WHERE (location_id = %s OR location_id IS NULL)
        ORDER BY input_category, input_name
        """,
        (location_id,),
    )
    inputs = [dict(r) for r in cur.fetchall()]
    cur.close()
    lac_inputs = [
        row for row in inputs
        if row.get("origin_region")
        and any(
            keyword in (row.get("origin_region") or "").lower()
            for keyword in [
                "caribbean", "central america", "south america",
                "monte plata", "dominican", "mexico", "latin america",
                "sabana grande", "greater antilles",
            ]
        )
    ]
    return {
        "report_type": "bio_input_provenance",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "inputs": _serialize_rows(inputs),
        "lac_input_count": len(lac_inputs),
        "lac_input_share_pct": round(len(lac_inputs) / len(inputs) * 100, 1) if inputs else None,
        "limitations": [
            "Input provenance reflects documented supplier relationships, not full supply chain audits.",
            "Private supplier terms and pricing are excluded.",
            "LAC regional sourcing is documented per-batch; aggregate percentages are advisory.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_bio_recipe_library(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-organic fertilizer recipe library report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_bio_recipe_library_summary
            WHERE (location_id = %s OR location_id IS NULL)
            ORDER BY recipe_type, recipe_name
            """,
            (location_id,),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_bio_recipe_library_summary
            ORDER BY recipe_type, recipe_name
            """
        )
    recipes = [dict(r) for r in cur.fetchall()]
    cur.close()
    recipe_types: dict[str, int] = {}
    for row in recipes:
        rt = row.get("recipe_type")
        if rt:
            recipe_types[rt] = recipe_types.get(rt, 0) + 1
    return {
        "report_type": "bio_recipe_library",
        "location_id": location_id,
        "recipes": _serialize_rows(recipes),
        "recipe_type_breakdown": recipe_types,
        "limitations": [
            "Recipes are public knowledge for adaptation, not commercial endorsements.",
            "Recipe reusability is a planning signal, not a guarantee of results at scale.",
            "Quality warnings (e.g. sargassum arsenic, manure pathogens) must be followed.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_bio_quality_test(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-factory quality test report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_factory_quality_test_summary
        WHERE (location_id = %s OR location_id IS NULL)
          AND (%s::date IS NULL OR test_date >= %s::date)
          AND (%s::date IS NULL OR test_date <= %s::date)
        ORDER BY test_date DESC, parameter_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    tests = [dict(r) for r in cur.fetchall()]
    cur.close()
    test_count = len(tests)
    pass_count = sum(1 for row in tests if row.get("pass_fail") == "pass")
    return {
        "report_type": "bio_quality_test",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "tests": _serialize_rows(tests),
        "test_count": test_count,
        "pass_count": pass_count,
        "pass_rate_pct": round(pass_count / test_count * 100, 1) if test_count else None,
        "limitations": [
            "Quality test results are advisory, not certification or regulatory compliance.",
            "On-site lab results are not externally accredited unless lab_accredited = TRUE.",
            "Pass/fail thresholds are advisory and should be calibrated to specific use cases.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_bio_regional_input(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe LAC regional input availability report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_regional_input_summary
        ORDER BY region_scope, input_name
        """
    )
    regional = [dict(r) for r in cur.fetchall()]
    cur.close()
    region_counts: dict[str, int] = {}
    for row in regional:
        rs = row.get("region_scope")
        if rs:
            region_counts[rs] = region_counts.get(rs, 0) + 1
    return {
        "report_type": "bio_regional_input",
        "location_id": location_id,
        "regional_inputs": _serialize_rows(regional),
        "region_breakdown": region_counts,
        "limitations": [
            "LAC regional input availability reflects documented sourcing notes, not exhaustive surveys.",
            "Cautions (e.g. sargassum arsenic, pesticide residues) must be followed before use.",
            "Sourcing notes are advisory; suppliers should be verified per-batch.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_time_liberation(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe time liberation report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_time_liberation_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR observation_date >= %s::date)
          AND (%s::date IS NULL OR observation_date <= %s::date)
        ORDER BY observation_date DESC, workflow_area
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "time_liberation",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "observations": _serialize_rows(observations),
        "total_hours_reclaimed": round(sum(float(row.get("hours_reclaimed") or 0) for row in observations), 2),
        "limitations": [
            "Time liberation observations are reviewed planning and workflow signals, not surveillance of individual workers.",
            "Private labor records and household-level details are excluded from public reporting.",
            "Automation and AI support must remain human-reviewed and should reduce burdens rather than intensify work.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_capital_alignment(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe capital alignment report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_capital_alignment_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR assessment_date >= %s::date)
          AND (%s::date IS NULL OR assessment_date <= %s::date)
        ORDER BY assessment_date DESC, provider_type
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    assessments = [dict(r) for r in cur.fetchall()]
    cur.close()
    high_risk = [row for row in assessments if row.get("extractive_risk_level") in {"high", "critical"}]
    return {
        "report_type": "capital_alignment",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "assessments": _serialize_rows(assessments),
        "high_or_critical_extractive_risk_count": len(high_risk),
        "limitations": [
            "Capital alignment assessments summarize public-safe terms and do not disclose private negotiations.",
            "Aligned capital signals do not guarantee future funding availability or performance.",
            "Debt, equity, and investor-like structures require explicit community-control and extraction-risk review before public endorsement.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_governance_inclusion(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe governance inclusion report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_governance_inclusion_summary
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR observation_date >= %s::date)
              AND (%s::date IS NULL OR observation_date <= %s::date)
            ORDER BY observation_date DESC, governance_body
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_governance_inclusion_summary
            WHERE (%s::date IS NULL OR observation_date >= %s::date)
              AND (%s::date IS NULL OR observation_date <= %s::date)
            ORDER BY observation_date DESC, governance_body
            """,
            (period_start, period_start, period_end, period_end),
        )
    observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "governance_inclusion",
        "location_id": location_id,
        "observations": _serialize_rows(observations),
        "pseudonymous_participation_enabled_count": sum(1 for row in observations if row.get("pseudonymous_participation_enabled")),
        "limitations": [
            "Governance inclusion reports use privacy-safe group summaries, not raw identity records.",
            "Pseudonymous participation is supported only where accountability and safety gates are preserved.",
            "Representation observations identify gaps for improvement and are not external certification of inclusivity.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_land_stewardship(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe land stewardship report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_land_stewardship_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR commitment_date >= %s::date)
          AND (%s::date IS NULL OR commitment_date <= %s::date)
        ORDER BY commitment_date DESC, stewardship_model
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    commitments = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "land_stewardship",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "commitments": _serialize_rows(commitments),
        "limitations": [
            "Land stewardship reports are not legal opinions and do not claim land transfer unless separately documented.",
            "Anti-speculation and commons-transition paths must be backed by governed evidence before public claims expand.",
            "Private household, title, or lease details are excluded from public reporting.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_gnh_alignment(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe GNH alignment report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_gnh_alignment_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR assessment_date >= %s::date)
          AND (%s::date IS NULL OR assessment_date <= %s::date)
        ORDER BY assessment_date DESC, gnh_domain
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    assessments = [dict(r) for r in cur.fetchall()]
    cur.close()
    scores = [float(row["alignment_score"]) for row in assessments if row.get("alignment_score") is not None]
    return {
        "report_type": "gnh_alignment",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "assessments": _serialize_rows(assessments),
        "average_alignment_score": round(sum(scores) / len(scores), 2) if scores else None,
        "limitations": [
            "GNH alignment is a reviewer-assessed evidence signal, not Bhutan readiness certification.",
            "Local cultural review is required before adapting claims to a Bhutanese context.",
            "Domain scores summarize published evidence and should be interpreted with listed gaps and safeguards.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_cultural_preservation(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe cultural preservation report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_cultural_preservation_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR plan_date >= %s::date)
          AND (%s::date IS NULL OR plan_date <= %s::date)
        ORDER BY plan_date DESC, cultural_element
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    plans = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "cultural_preservation",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "plans": _serialize_rows(plans),
        "limitations": [
            "Cultural preservation reports expose public summaries only; private cultural knowledge remains excluded.",
            "Traditional-practice claims require local consent and reviewer context before publication.",
            "Cross-cultural expansion requires new local review rather than reusing Adelphi assumptions.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_renewable_energy(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe renewable energy report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_renewable_energy_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR plan_date >= %s::date)
          AND (%s::date IS NULL OR plan_date <= %s::date)
        ORDER BY plan_date DESC, energy_use_case
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    plans = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "renewable_energy",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "plans": _serialize_rows(plans),
        "planned_count": sum(1 for row in plans if row.get("implementation_status") == "planned"),
        "implemented_count": sum(1 for row in plans if row.get("implementation_status") == "implemented"),
        "limitations": [
            "Renewable energy plans distinguish planned infrastructure from implemented operational evidence.",
            "Fossil displacement estimates are conservative planning signals, not carbon-credit claims.",
            "Implemented renewable-share claims require follow-up operational energy records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_vulnerable_access(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe vulnerable group access report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_vulnerable_access_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR plan_date >= %s::date)
          AND (%s::date IS NULL OR plan_date <= %s::date)
        ORDER BY plan_date DESC, access_scope
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    plans = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "vulnerable_access",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "plans": _serialize_rows(plans),
        "limitations": [
            "Vulnerable access reports use group-level summaries, not private identity or protected-class data.",
            "Planned accommodations are not represented as completed inclusion outcomes.",
            "Meaningful access should be reviewed with affected groups before stronger public claims are made.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_foundational_wellbeing(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe foundational well-being report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_foundational_wellbeing_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR observation_date >= %s::date)
          AND (%s::date IS NULL OR observation_date <= %s::date)
        ORDER BY observation_date DESC, wellbeing_domain
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "foundational_wellbeing",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "observations": _serialize_rows(observations),
        "limitations": [
            "Foundational well-being signals are public-safe summaries, not clinical or external certification.",
            "Private feedback, household-level observations, and unresolved allegations remain excluded from public output.",
            "Scores should be read alongside qualitative limitations and evidence maturity labels.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_regenerative_outcomes(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe regenerative outcome summary report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_regenerative_outcome_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR period_start >= %s::date)
          AND (%s::date IS NULL OR period_end <= %s::date)
        ORDER BY period_end DESC, summary_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "regenerative_outcomes",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "outcomes": _serialize_rows(rows),
        "total_hectares_restored": round(sum(float(row.get("hectares_restored") or 0) for row in rows), 4),
        "limitations": [
            "Regenerative outcome summaries consolidate source evidence for reviewers; source tables remain canonical.",
            "Moderate or low confidence outcomes should not be treated as external certification.",
            "Carbon-credit or biodiversity-credit claims require separate maturity and verification gates.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_community_governance(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe community governance mechanism report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_community_governance_mechanism
            WHERE location_id = %s OR location_id IS NULL
            ORDER BY governance_level, mechanism_name
            """,
            (location_id,),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_community_governance_mechanism
            ORDER BY governance_level, mechanism_name
            """
        )
    mechanisms = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "community_governance",
        "location_id": location_id,
        "mechanisms": _serialize_rows(mechanisms),
        "limitations": [
            "Governance reports summarize public mechanisms and do not expose private participant identities.",
            "Power-sharing claims should be read alongside participation, veto, and escalation details.",
            "Agent-generated outputs remain draft-only and cannot verify or publish governance decisions.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_replication_readiness(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe replication readiness report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_replication_readiness_summary
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, target_region
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_replication_readiness_summary
            WHERE (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, target_region
            """,
            (period_start, period_start, period_end, period_end),
        )
    assessments = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "replication_readiness",
        "location_id": location_id,
        "assessments": _serialize_rows(assessments),
        "limitations": [
            "Replication readiness is conditional evidence, not an unlimited-scaling claim.",
            "Each new region requires local ecological, cultural, governance, infrastructure, and evidence review.",
            "Barriers and support structures must be resolved before public replication commitments expand.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_adaptive_stewardship(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe adaptive stewardship report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_adaptive_stewardship_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR review_date >= %s::date)
          AND (%s::date IS NULL OR review_date <= %s::date)
        ORDER BY review_date DESC, stewardship_scope
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    reviews = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "adaptive_stewardship",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "reviews": _serialize_rows(reviews),
        "limitations": [
            "Adaptive stewardship reviews are management evidence, not guarantees that risks are eliminated.",
            "Corrective actions should be re-reviewed on the listed cadence before stronger claims are made.",
            "Funding continuity plans are planning evidence and may exclude private terms.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_scaling_economics(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe scaling economics and unit-cost report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_farm_launch_unit_economics
            WHERE location_id = %s OR location_id IS NULL
            ORDER BY target_region, economics_name
            """,
            (location_id,),
        )
    else:
        cur.execute("SELECT * FROM v_public_farm_launch_unit_economics ORDER BY target_region, economics_name")
    economics = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT *
        FROM v_public_network_scaling_target
        WHERE (%s::date IS NULL OR target_date >= %s::date)
          AND (%s::date IS NULL OR target_date <= %s::date)
        ORDER BY target_date, target_name
        """,
        (period_start, period_start, period_end, period_end),
    )
    targets = [dict(r) for r in cur.fetchall()]
    cur.close()

    total_launch_cost = sum(float(row.get("total_launch_cost_usd") or 0) for row in economics)
    total_target_capital = sum(float(row.get("capital_required_usd") or 0) for row in targets)
    planned_farms = sum(int(row.get("planned_farm_count") or 0) for row in economics)
    target_farms = sum(int(row.get("target_farm_count") or 0) for row in targets)
    return {
        "report_type": "scaling_economics",
        "location_id": location_id,
        "unit_economics": _serialize_rows(economics),
        "network_targets": _serialize_rows(targets),
        "total_launch_cost_usd": round(total_launch_cost, 2),
        "total_target_capital_usd": round(total_target_capital, 2),
        "planned_farm_count": planned_farms,
        "target_farm_count": target_farms,
        "limitations": [
            "Scaling economics are planning evidence, not guaranteed ROI or securities-style return claims.",
            "Planned farm counts are roadmap targets unless backed by separate registry records.",
            "Private capital terms, side letters, and unsupported external integrations are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_adoption_barriers(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe adoption and market barrier report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_adoption_barrier_assessment
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, barrier_category, barrier_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_adoption_barrier_assessment
            WHERE (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, barrier_category, barrier_name
            """,
            (period_start, period_start, period_end, period_end),
        )
    barriers = [dict(r) for r in cur.fetchall()]
    cur.close()
    active = [row for row in barriers if row.get("resolution_status") in {"open", "mitigating", "blocked"}]
    return {
        "report_type": "adoption_barriers",
        "location_id": location_id,
        "barriers": _serialize_rows(barriers),
        "active_barrier_count": len(active),
        "limitations": [
            "Barrier reports summarize public-safe categories and do not expose private stakeholder feedback.",
            "Regulatory and cultural readiness must be reviewed per location before expansion claims are made.",
            "Mitigation costs are planning estimates unless backed by verified expense records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_perpetual_value_stress(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe downside stress-test report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_perpetual_value_stress_test
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR scenario_date >= %s::date)
              AND (%s::date IS NULL OR scenario_date <= %s::date)
            ORDER BY scenario_date DESC, stress_type, scenario_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_perpetual_value_stress_test
            WHERE (%s::date IS NULL OR scenario_date >= %s::date)
              AND (%s::date IS NULL OR scenario_date <= %s::date)
            ORDER BY scenario_date DESC, stress_type, scenario_name
            """,
            (period_start, period_start, period_end, period_end),
        )
    scenarios = [dict(r) for r in cur.fetchall()]
    cur.close()
    watchlist = [row for row in scenarios if row.get("solvency_status") in {"watchlist", "needs_mitigation", "insolvent_without_support"}]
    return {
        "report_type": "perpetual_value_stress",
        "location_id": location_id,
        "stress_tests": _serialize_rows(scenarios),
        "watchlist_or_mitigation_count": len(watchlist),
        "limitations": [
            "Stress tests are planning evidence and do not guarantee solvency or capital availability.",
            "Down-cycle assumptions should be refreshed as market, climate, cost, and governance records mature.",
            "Private reserves or unpublished funder commitments are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_open_source_impact(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate public-safe open-source artifact reuse report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM v_public_open_source_impact_artifact ORDER BY reuse_count DESC, artifact_type, artifact_name")
    artifacts = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "open_source_impact",
        "location_id": location_id,
        "artifacts": _serialize_rows(artifacts),
        "artifact_count": len(artifacts),
        "total_reuse_count": sum(int(row.get("reuse_count") or 0) for row in artifacts),
        "limitations": [
            "Open-source artifact reuse counts are governed evidence signals, not claims of external adoption unless separately sourced.",
            "Hypercert, Ecocertain, or other external integrations should not be claimed until canonical records exist.",
            "Repository paths and public URLs may identify reusable artifacts but do not imply third-party certification.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_public_view(conn, view_name: str, location_id: str = None, order_by: str = "id") -> list[dict]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            f"SELECT * FROM {view_name} WHERE location_id = %s OR location_id IS NULL ORDER BY {order_by}",
            (location_id,),
        )
    else:
        cur.execute(f"SELECT * FROM {view_name} ORDER BY {order_by}")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def generate_anti_capture_governance(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    policies = _fetch_public_view(conn, "v_public_anti_capture_governance_policy", location_id, "policy_scope, policy_name")
    return {
        "report_type": "anti_capture_governance",
        "location_id": location_id,
        "policies": _serialize_rows(policies),
        "community_veto_count": sum(1 for row in policies if row.get("community_veto_enabled")),
        "operator_veto_count": sum(1 for row in policies if row.get("worker_or_operator_veto_enabled")),
        "limitations": [
            "Anti-capture policies are public governance evidence and may be offchain unless enforcement mode says otherwise.",
            "Do not claim one-person-one-vote, quadratic voting, or smart-contract enforcement unless explicitly documented.",
            "Representation requirements must remain lawful, consented, and privacy-safe.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_redistribution_policy(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    policies = _fetch_public_view(conn, "v_public_commons_redistribution_policy", location_id, "policy_status, policy_scope, policy_name")
    return {
        "report_type": "redistribution_policy",
        "location_id": location_id,
        "policies": _serialize_rows(policies),
        "active_policy_count": sum(1 for row in policies if row.get("policy_status") == "active"),
        "scenario_policy_count": sum(1 for row in policies if row.get("policy_scope") == "scenario"),
        "limitations": [
            "Redistribution policies are scenario-specific and should not be generalized across farms without matching records.",
            "Current policy percentages and proposed scenarios are separate; proposed policies are not commitments.",
            "Private recipient identities and private capital terms are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_federation_mutual_aid(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    protocols = _fetch_public_view(conn, "v_public_federation_protocol", None, "protocol_status, federation_scope, protocol_name")
    return {
        "report_type": "federation_mutual_aid",
        "location_id": location_id,
        "protocols": _serialize_rows(protocols),
        "permissionless_forking_count": sum(1 for row in protocols if row.get("permissionless_forking_enabled")),
        "limitations": [
            "Federation protocols support reuse and local adaptation; they are not unlimited-scaling guarantees.",
            "New communities require local registry, governance, cultural, financial, and evidence records.",
            "Anti-extractive safeguards should be reviewed before public replication claims expand.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_algorithmic_redistribution(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    mechanisms = _fetch_public_view(conn, "v_public_algorithmic_redistribution_mechanism", location_id, "implementation_status, mechanism_type, mechanism_name")
    return {
        "report_type": "algorithmic_redistribution",
        "location_id": location_id,
        "mechanisms": _serialize_rows(mechanisms),
        "active_or_pilot_count": sum(1 for row in mechanisms if row.get("implementation_status") in {"active", "pilot"}),
        "limitations": [
            "Redistribution mechanisms are not onchain payment implementations unless enforcement mode documents smart-contract execution.",
            "Public reports exclude private eligibility, protected-class details, and household-level beneficiary data.",
            "Airdrops, progressive fees, or reparations claims require separate governed implementation records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_participatory_signal(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    experiments = _fetch_public_view(conn, "v_public_participatory_signal_experiment", None, "experiment_status, signal_type, experiment_name")
    return {
        "report_type": "participatory_signal",
        "location_id": location_id,
        "experiments": _serialize_rows(experiments),
        "advisory_count": sum(1 for row in experiments if row.get("decision_binding") == "advisory"),
        "limitations": [
            "Participatory signal experiments are advisory unless decision binding states otherwise and human review approves use.",
            "Meme, vibes, and story signals cannot override evidence maturity, privacy, or treasury controls.",
            "Moderation and safety boundaries must be enforced before publication.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Ecological Modeling Reports
# ---------------------------------------------------------------------------

def generate_ecological_modeling(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe ecological modeling report with interactions, model runs, and population dynamics."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_ecological_interaction_summary
        WHERE location_id = %s ORDER BY interaction_strength DESC
        """,
        (location_id,),
    )
    interactions = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_ecological_model_summary
        WHERE location_id = %s ORDER BY run_date DESC
        """,
        (location_id,),
    )
    models = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_population_dynamics_summary
        WHERE location_id = %s ORDER BY species_name, record_date
        """,
        (location_id,),
    )
    populations = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_energy_flow_summary
        WHERE location_id = %s ORDER BY measurement_date DESC
        """,
        (location_id,),
    )
    energy_flows = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_soil_input_retention
        WHERE location_id = %s ORDER BY application_date DESC
        """,
        (location_id,),
    )
    soil_inputs = [dict(r) for r in cur.fetchall()]
    cur.close()
    mutualism_count = sum(1 for i in interactions if i.get("interaction_type") == "mutualism")
    predation_count = sum(1 for i in interactions if i.get("interaction_type") == "predation")
    trophic_balance = mutualism_count / max(mutualism_count + predation_count, 1)
    avg_residual = (
        sum(s.get("residual_pct", 0) or 0 for s in soil_inputs) / max(len(soil_inputs), 1)
    )
    return {
        "report_type": "ecological_modeling",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "interactions": _serialize_rows(interactions),
        "model_runs": _serialize_rows(models),
        "population_records": _serialize_rows(populations),
        "energy_flows": _serialize_rows(energy_flows),
        "soil_inputs": _serialize_rows(soil_inputs),
        "interaction_count": len(interactions),
        "mutualism_count": mutualism_count,
        "predation_count": predation_count,
        "trophic_balance_index": round(trophic_balance, 3),
        "soil_input_count": len(soil_inputs),
        "avg_residual_pct": round(avg_residual, 2),
        "limitations": [
            "Ecological model outputs are simulation estimates, not guaranteed outcomes.",
            "Interaction strength values are observational estimates requiring ground-truth verification.",
            "Population dynamics records depend on survey method accuracy and observer skill.",
            "Energy flow measurements use estimation methods; direct measurement preferred.",
            "Soil input retention rates vary with soil type, climate, and microbial activity.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_trophic_pyramid(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe trophic pyramid report showing energy flow across trophic levels."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_energy_flow_efficiency
        WHERE location_id = %s ORDER BY from_trophic_level, to_trophic_level
        """,
        (location_id,),
    )
    energy_flows = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT species_a_trophic AS trophic_level, COUNT(*) AS interaction_count,
               AVG(interaction_strength) AS avg_strength
        FROM ecological_interaction
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY species_a_trophic
        """,
        (location_id,),
    )
    trophic_counts = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT trophic_level, COUNT(DISTINCT species_name) AS species_count
        FROM population_dynamics_record
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY trophic_level
        """,
        (location_id,),
    )
    species_by_trophic = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "trophic_pyramid",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "energy_flows": _serialize_rows(energy_flows),
        "trophic_interaction_counts": _serialize_rows(trophic_counts),
        "species_by_trophic_level": _serialize_rows(species_by_trophic),
        "total_energy_transfers": len(energy_flows),
        "limitations": [
            "Trophic pyramid metrics are aggregated from observational data with inherent measurement uncertainty.",
            "Energy flow efficiency percentages use estimation methods; direct biomass measurement preferred.",
            "Species classifications by trophic level may vary with life stage and diet.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Pest Management Report
# ---------------------------------------------------------------------------

def generate_pest_management(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe pest management report with incidence trends and biocontrol effectiveness."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_pest_trends
        WHERE location_id = %s ORDER BY observation_date DESC
        """,
        (location_id,),
    )
    pest_trends = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_biocontrol_effectiveness
        WHERE location_id = %s ORDER BY release_date DESC
        """,
        (location_id,),
    )
    biocontrol = [dict(r) for r in cur.fetchall()]
    cur.close()
    severe_count = sum(1 for p in pest_trends if p.get("severity") in ("high", "critical"))
    avg_outbreak_prob = (
        sum(p.get("outbreak_probability_pct", 0) or 0 for p in pest_trends) / max(len(pest_trends), 1)
    )
    return {
        "report_type": "pest_management",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "pest_trends": _serialize_rows(pest_trends),
        "biocontrol_releases": _serialize_rows(biocontrol),
        "total_observations": len(pest_trends),
        "severe_observations": severe_count,
        "avg_outbreak_probability_pct": round(avg_outbreak_prob, 2),
        "biocontrol_release_count": len(biocontrol),
        "limitations": [
            "Pest outbreak probability is a model estimate based on historical incidence and weather.",
            "Biocontrol effectiveness depends on environmental conditions and timing.",
            "Pest identification may require expert verification.",
            "Natural enemy counts are observational estimates.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Resource Efficiency Report
# ---------------------------------------------------------------------------

def generate_resource_efficiency(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe resource efficiency report with labor, energy, and water intensity."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_resource_efficiency
        WHERE location_id = %s ORDER BY resource_type, period_start DESC
        """,
        (location_id,),
    )
    resources = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT SUM(he.quantity) AS total_harvest_kg
        FROM harvest_event he
        WHERE he.location_id = %s AND he.status IN ('verified', 'published')
        """,
        (location_id,),
    )
    harvest = cur.fetchone()
    cur.close()
    total_harvest = float(harvest["total_harvest_kg"] or 0) if harvest else 0
    by_type = {}
    for r in resources:
        rt = r.get("resource_type", "unknown")
        if rt not in by_type:
            by_type[rt] = {"total": 0, "unit": r.get("unit"), "count": 0}
        by_type[rt]["total"] += float(r.get("quantity", 0) or 0)
        by_type[rt]["count"] += 1
    efficiency = {}
    for rt, data in by_type.items():
        efficiency[rt] = {
            "total_quantity": round(data["total"], 2),
            "unit": data["unit"],
            "record_count": data["count"],
            "per_kg_yield": round(data["total"] / total_harvest, 4) if total_harvest > 0 else None,
        }
    return {
        "report_type": "resource_efficiency",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "resources": _serialize_rows(resources),
        "total_harvest_kg": round(total_harvest, 2),
        "efficiency_by_type": efficiency,
        "limitations": [
            "Resource consumption may include estimated values where metering is unavailable.",
            "Labor hours depend on activity tracking completeness.",
            "Water and energy estimates are based on planned targets, not metered consumption.",
            "Yield-linked efficiency metrics require matched harvest and resource periods.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Training Impact Report
# ---------------------------------------------------------------------------

def generate_training_impact(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe training impact report with participation and improvement metrics."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_training_impact
        WHERE location_id = %s ORDER BY session_date DESC
        """,
        (location_id,),
    )
    sessions = [dict(r) for r in cur.fetchall()]
    cur.close()
    unique_participants = len(set(s.get("participant_name") for s in sessions if s.get("participant_name")))
    avg_improvement = (
        sum(s.get("improvement_pct", 0) or 0 for s in sessions) / max(len(sessions), 1)
    )
    total_hours = sum(float(s.get("duration_hours", 0) or 0) for s in sessions)
    return {
        "report_type": "training_impact",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "sessions": _serialize_rows(sessions),
        "total_sessions": len(sessions),
        "unique_participants": unique_participants,
        "total_training_hours": round(total_hours, 2),
        "avg_improvement_pct": round(avg_improvement, 2),
        "limitations": [
            "Training scores are self-assessed or trainer-assessed, not independently verified.",
            "Improvement percentages depend on baseline assessment quality.",
            "Participant counts may undercount repeat attendees.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Revenue Streams Report
# ---------------------------------------------------------------------------

def generate_revenue_streams(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe revenue streams report showing contribution to profitability."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_revenue_streams
        WHERE location_id = %s ORDER BY period_start DESC, net_contribution DESC
        """,
        (location_id,),
    )
    streams = [dict(r) for r in cur.fetchall()]
    cur.close()
    total_gross = sum(float(s.get("gross_revenue", 0) or 0) for s in streams)
    total_net = sum(float(s.get("net_contribution", 0) or 0) for s in streams)
    return {
        "report_type": "revenue_streams",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "streams": _serialize_rows(streams),
        "total_gross_revenue": round(total_gross, 2),
        "total_net_contribution": round(total_net, 2),
        "stream_count": len(streams),
        "limitations": [
            "Revenue stream classification depends on accurate categorization at data entry.",
            "Cost allocation methods may affect net contribution calculations.",
            "Period boundaries may not align perfectly across revenue streams.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Model Validation Report
# ---------------------------------------------------------------------------

def generate_model_validation(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe model validation report with prediction accuracy and feature importance."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_prediction_accuracy
        WHERE location_id = %s ORDER BY prediction_date DESC
        """,
        (location_id,),
    )
    predictions = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_feature_importance
        WHERE location_id = %s ORDER BY importance_score DESC
        """,
        (location_id,),
    )
    features = [dict(r) for r in cur.fetchall()]
    cur.close()
    avg_mape = (
        sum(p.get("mape", 0) or 0 for p in predictions) / max(len(predictions), 1)
    )
    overall_accuracy = 100 - avg_mape
    return {
        "report_type": "model_validation",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "predictions": _serialize_rows(predictions),
        "feature_importance": _serialize_rows(features),
        "total_predictions": len(predictions),
        "avg_mape_pct": round(avg_mape, 2),
        "overall_accuracy_pct": round(overall_accuracy, 2),
        "top_predictors": [f.get("feature_name") for f in features[:5]],
        "limitations": [
            "Model validation metrics are computed from limited pilot data.",
            "Feature importance scores may change with additional observations.",
            "Prediction accuracy depends on input data quality and completeness.",
            "Backtesting results do not guarantee future model performance.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Livestock Feed Report
# ---------------------------------------------------------------------------

def generate_livestock_feed(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe livestock feed report with intake, conversion ratio, and per-animal metrics."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_livestock_feed_intake
        WHERE location_id = %s ORDER BY record_date DESC
        """,
        (location_id,),
    )
    feed_records = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT group_name, species, breed, animal_count, feed_type, status
        FROM livestock_group
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    groups = [dict(r) for r in cur.fetchall()]
    cur.close()
    total_feed = sum(float(r.get("quantity_kg", 0) or 0) for r in feed_records)
    total_animals = sum(g.get("animal_count", 0) or 0 for g in groups)
    return {
        "report_type": "livestock_feed",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "livestock_groups": _serialize_rows(groups),
        "feed_records": _serialize_rows(feed_records),
        "total_groups": len(groups),
        "total_animals": total_animals,
        "total_feed_kg": round(total_feed, 3),
        "limitations": [
            "Feed intake measurements depend on accurate weighing practices.",
            "Feed conversion ratio is estimated from available weight data.",
            "Per-animal consumption assumes uniform distribution within groups.",
            "Supplemental foraging intake is not captured in feed records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Token Rewards Report
# ---------------------------------------------------------------------------

def generate_token_rewards(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe token rewards report with distribution, epoch totals, and metric correlation."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_token_reward_distribution
        WHERE location_id = %s ORDER BY distribution_date DESC
        """,
        (location_id,),
    )
    distributions = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_reward_calibration
        WHERE location_id = %s ORDER BY run_date DESC LIMIT 1
        """,
        (location_id,),
    )
    calibration = cur.fetchone()
    cur.close()
    total_tokens = sum(float(d.get("token_amount", 0) or 0) for d in distributions)
    total_usd = sum(float(d.get("usd_value", 0) or 0) for d in distributions)
    onchain_count = sum(1 for d in distributions if d.get("is_onchain"))
    return {
        "report_type": "token_rewards",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "distributions": _serialize_rows(distributions),
        "latest_calibration": dict(calibration) if calibration else None,
        "total_distributions": len(distributions),
        "total_tokens": round(total_tokens, 8),
        "total_usd": round(total_usd, 2),
        "onchain_count": onchain_count,
        "offchain_count": len(distributions) - onchain_count,
        "limitations": [
            "Token reward amounts depend on DAO governance decisions.",
            "USD values are approximate and may not reflect current market price.",
            "Metric-linked rewards use the value at time of distribution.",
            "On-chain rewards require transaction confirmation; off-chain rewards are pending.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Reward Calibration Report
# ---------------------------------------------------------------------------

def generate_reward_calibration(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe reward calibration report with calibration model outputs and sensitivity."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_reward_calibration
        WHERE location_id = %s ORDER BY run_date DESC
        """,
        (location_id,),
    )
    models = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT reward_type, linked_metric_key, AVG(linked_metric_value) AS avg_metric,
               AVG(token_amount) AS avg_tokens, COUNT(*) AS count
        FROM token_reward_distribution
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND linked_metric_value IS NOT NULL
        GROUP BY reward_type, linked_metric_key
        """,
        (location_id,),
    )
    metric_links = [dict(r) for r in cur.fetchall()]
    cur.close()
    latest = models[0] if models else None
    return {
        "report_type": "reward_calibration",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "calibration_models": _serialize_rows(models),
        "metric_links": _serialize_rows(metric_links),
        "latest_calibration_score": latest.get("calibration_score") if latest else None,
        "latest_model_name": latest.get("model_name") if latest else None,
        "limitations": [
            "Calibration scores are computed from limited pilot data.",
            "Weight assignments are governance-decided and may change.",
            "Metric-reward correlations require sufficient sample size.",
            "Token per unit output ratios depend on total epoch budget.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Snapshot storage
# ---------------------------------------------------------------------------

REPORT_GENERATORS = {
    "farm_summary": generate_farm_summary,
    "crop_noi": generate_crop_noi,
    "environmental": generate_environmental,
    "revenue_multiplier": generate_revenue_multiplier,
    "forecast": generate_forecast_summary,
    "climate_impact": generate_climate_impact,
    "ebf_scorecard": generate_ebf_scorecard,
    "holistic_wellbeing": generate_holistic_wellbeing,
    "financial_sustainability": generate_financial_sustainability,
    "risk_mitigation": generate_risk_mitigation,
    "scaling_roadmap": generate_scaling_roadmap,
    "green_paper_publication_status": generate_green_paper_publication_status,
    "capital_efficiency": generate_capital_efficiency,
    "governance_throughput": generate_governance_throughput,
    "capital_provider_utility": generate_capital_provider_utility,
    "time_liberation": generate_time_liberation,
    "capital_alignment": generate_capital_alignment,
    "governance_inclusion": generate_governance_inclusion,
    "land_stewardship": generate_land_stewardship,
    "gnh_alignment": generate_gnh_alignment,
    "cultural_preservation": generate_cultural_preservation,
    "renewable_energy": generate_renewable_energy,
    "vulnerable_access": generate_vulnerable_access,
    "foundational_wellbeing": generate_foundational_wellbeing,
    "regenerative_outcomes": generate_regenerative_outcomes,
    "community_governance": generate_community_governance,
    "replication_readiness": generate_replication_readiness,
    "adaptive_stewardship": generate_adaptive_stewardship,
    "scaling_economics": generate_scaling_economics,
    "adoption_barriers": generate_adoption_barriers,
    "perpetual_value_stress": generate_perpetual_value_stress,
    "open_source_impact": generate_open_source_impact,
    "anti_capture_governance": generate_anti_capture_governance,
    "redistribution_policy": generate_redistribution_policy,
    "federation_mutual_aid": generate_federation_mutual_aid,
    "algorithmic_redistribution": generate_algorithmic_redistribution,
    "participatory_signal": generate_participatory_signal,
    "bio_factory_batch": generate_bio_factory_batch,
    "bio_input_provenance": generate_bio_input_provenance,
    "bio_recipe_library": generate_bio_recipe_library,
    "bio_quality_test": generate_bio_quality_test,
    "bio_regional_input": generate_bio_regional_input,
    "ecological_modeling": generate_ecological_modeling,
    "trophic_pyramid": generate_trophic_pyramid,
    "pest_management": generate_pest_management,
    "resource_efficiency": generate_resource_efficiency,
    "training_impact": generate_training_impact,
    "revenue_streams": generate_revenue_streams,
    "model_validation": generate_model_validation,
    "livestock_feed": generate_livestock_feed,
    "token_rewards": generate_token_rewards,
    "reward_calibration": generate_reward_calibration,
}


def compute_hash(data: dict) -> str:
    """Compute SHA-256 hash of report data for reproducibility."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def store_snapshot(conn, report_data: dict, location_id: str = None, period_start: str = None, period_end: str = None) -> str:
    """Store report snapshot in the database."""
    report_data = attach_public_interest_context(conn, report_data, location_id)
    snapshot_hash = compute_hash(report_data)
    report_type = report_data.get("report_type", "unknown")
    public_interest = report_data.get("public_interest", {})
    public_summary = "; ".join(public_interest.get("limitations", [])) if public_interest else None
    negative_findings = [
        gap for gap in public_interest.get("evidence_gaps", [])
        if gap.get("public_claims_below_threshold", 0)
        or gap.get("carbon_publication_gaps", 0)
        or gap.get("missing_evidence_links", 0)
    ] if public_interest else []
    affected_voice = json.dumps(public_interest.get("public_feedback", []), default=str) if public_interest else None

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO report_snapshot (
            report_name, report_type, location_id, period_start, period_end,
            report_data, snapshot_hash, status, frozen, frozen_at,
            public_interest_summary, uncertainty_notes, negative_findings, affected_community_voice
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'published', TRUE, NOW(), %s, %s, %s, %s)
        RETURNING id
        """,
        (
            f"{report_type}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            report_type,
            location_id,
            period_start,
            period_end,
            json.dumps(report_data, default=str),
            snapshot_hash,
            public_summary,
            public_summary,
            json.dumps(negative_findings, default=str),
            affected_voice,
        ),
    )
    snapshot_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return snapshot_id


def list_snapshots(conn, location_id: str = None):
    """List existing report snapshots."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            "SELECT id, report_name, report_type, snapshot_hash, status, created_at FROM report_snapshot WHERE location_id = %s ORDER BY created_at DESC LIMIT 20",
            (location_id,),
        )
    else:
        cur.execute("SELECT id, report_name, report_type, snapshot_hash, status, created_at FROM report_snapshot ORDER BY created_at DESC LIMIT 20")
    snapshots = [dict(r) for r in cur.fetchall()]
    cur.close()
    return snapshots


def _verify_snapshot(conn, snapshot_id_or_hash: str) -> None:
    """Verify a snapshot's hash integrity."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT id, report_name, report_type, report_data, snapshot_hash, status FROM report_snapshot WHERE id = %s OR snapshot_hash = %s",
        (snapshot_id_or_hash, snapshot_id_or_hash),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        print(f"Snapshot not found: {snapshot_id_or_hash}")
        return

    stored_hash = row["snapshot_hash"]
    report_data = row["report_data"]

    recomputed = compute_hash(report_data)

    print(f"Snapshot:   {row['id']}")
    print(f"Report:     {row['report_name']} ({row['report_type']})")
    print(f"Status:     {row['status']}")
    print(f"Stored:     {stored_hash}")
    print(f"Recomputed: {recomputed}")

    if stored_hash == recomputed:
        print("Result:     PASS -- hash matches, report is intact")
    else:
        print("Result:     FAIL -- hash mismatch, report may have been tampered with")


def _check_report_empty(report_data: dict, report_type: str) -> None:
    """Warn if a report has no primary content rows."""
    content_keys = [k for k in report_data if k in {
        "plans", "risks", "milestones", "scenarios", "observations", "reviews",
        "policies", "protocols", "mechanisms", "experiments", "barriers",
        "stress_tests", "artifacts", "economics", "targets", "assessments",
        "outcomes", "mechanisms", "rows", "items", "farms", "crops",
        "pillars", "scores", "evidence_gaps", "recommendations",
        "cultural_context", "wellbeing_metrics", "participatory_actions",
        "financial_sustainability", "risk_mitigation",
    }]
    for key in content_keys:
        value = report_data.get(key)
        if isinstance(value, list) and len(value) == 0:
            print(f"  ⚠ {report_type}: no rows in '{key}' — report may be empty")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Kokonut report snapshots")
    parser.add_argument("--type", choices=list(REPORT_GENERATORS.keys()), help="Report type to generate")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--period-start", help="Report period start (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Report period end (YYYY-MM-DD)")
    parser.add_argument("--list", action="store_true", help="List existing snapshots")
    parser.add_argument("--verify", help="Verify a snapshot by hash")
    parser.add_argument("--auto", action="store_true", help="Generate all report types for the location")
    args = parser.parse_args()

    if not args.list:
        if not args.type and not args.auto:
            parser.error("--type or --auto is required (or use --list)")

        if not args.location_id:
            parser.error("--location-id is required")

    conn = get_pg()

    if args.list:
        snapshots = list_snapshots(conn, args.location_id)
        if not snapshots:
            print("No snapshots found.")
        else:
            print(f"{'ID':<38} {'Type':<20} {'Status':<12} {'Created':<20} Hash")
            print("-" * 120)
            for s in snapshots:
                print(f"{str(s['id']):<38} {s['report_type']:<20} {s['status']:<12} {str(s['created_at']):<20} {s['snapshot_hash'][:16]}")
        conn.close()
        return

    if args.verify:
        _verify_snapshot(conn, args.verify)
        conn.close()
        return

    if args.auto:
        report_types = list(REPORT_GENERATORS.keys())
        print(f"Generating all {len(report_types)} report types for location {args.location_id}...")
        print()

        success = 0
        failed = 0
        empty = 0

        for report_type in report_types:
            print(f"Generating {report_type}...")
            try:
                generator = REPORT_GENERATORS[report_type]
                report_data = generator(conn, args.location_id, args.period_start, args.period_end)
                _check_report_empty(report_data, report_type)
                snapshot_id = store_snapshot(conn, report_data, args.location_id, args.period_start, args.period_end)
                snapshot_hash = compute_hash(report_data)
                print(f"  ✓ {report_type}: {snapshot_id} ({snapshot_hash[:16]})")
                success += 1
            except Exception as e:
                print(f"  ✗ {report_type}: {e}")
                failed += 1

        print(f"\nDone: {success} succeeded, {failed} failed, {empty} empty")
        conn.close()
        if failed > 0:
            exit(1)
        return

    print(f"Generating {args.type} report for location {args.location_id}...")

    generator = REPORT_GENERATORS[args.type]
    report_data = generator(conn, args.location_id, args.period_start, args.period_end)

    snapshot_id = store_snapshot(conn, report_data, args.location_id, args.period_start, args.period_end)
    snapshot_hash = compute_hash(report_data)

    print(f"Snapshot stored: {snapshot_id}")
    print(f"Hash: {snapshot_hash}")
    print(f"Report type: {args.type}")

    conn.close()


if __name__ == "__main__":
    main()
