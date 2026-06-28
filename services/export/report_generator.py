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

        for report_type in report_types:
            print(f"Generating {report_type}...")
            try:
                generator = REPORT_GENERATORS[report_type]
                report_data = generator(conn, args.location_id, args.period_start, args.period_end)
                snapshot_id = store_snapshot(conn, report_data, args.location_id, args.period_start, args.period_end)
                snapshot_hash = compute_hash(report_data)
                print(f"  ✓ {report_type}: {snapshot_id} ({snapshot_hash[:16]})")
            except Exception as e:
                print(f"  ✗ {report_type}: {e}")

        print(f"\nDone: {len(report_types)} reports generated")
        conn.close()
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
