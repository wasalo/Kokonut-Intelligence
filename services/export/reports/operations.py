"""Operational reports: pest, resource, training, organic, and work statements."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from .common import (
    _serialize_rows,
)


def generate_pest_management(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe pest management report.

    Analysis lives in the pest_management domain module
    (get_pest_management_report); this generator just routes to it.
    """
    from ...analytics.pest_management import get_pest_management_report

    return get_pest_management_report(conn, location_id, period_start, period_end)


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
        WHERE location_id = %s
          AND (%s::date IS NULL OR period_start >= %s::date)
          AND (%s::date IS NULL OR period_start <= %s::date)
        ORDER BY resource_type, period_start DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    resources = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT SUM(he.quantity) AS total_harvest_kg
        FROM harvest_event he
        WHERE he.location_id = %s AND he.status IN ('verified', 'published')
          AND (%s::date IS NULL OR he.event_date >= %s::date)
          AND (%s::date IS NULL OR he.event_date <= %s::date)
        """,
        (location_id, period_start, period_start, period_end, period_end),
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
    avg_improvement = sum(s.get("improvement_pct", 0) or 0 for s in sessions) / max(len(sessions), 1)
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
    avg_mape = sum(p.get("mape", 0) or 0 for p in predictions) / max(len(predictions), 1)
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
    from services.analytics.reward_calibration import detect_overjustification_risk

    overjustification = None
    try:
        overjustification = detect_overjustification_risk(conn, location_id)
    except Exception as exc:  # advisory: never fatal
        overjustification = {"error": str(exc)}
    return {
        "report_type": "reward_calibration",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "calibration_models": _serialize_rows(models),
        "metric_links": _serialize_rows(metric_links),
        "latest_calibration_score": latest.get("calibration_score") if latest else None,
        "latest_model_name": latest.get("model_name") if latest else None,
        "overjustification_risk": overjustification,
        "limitations": [
            "Calibration scores are computed from limited pilot data.",
            "Weight assignments are governance-decided and may change.",
            "Metric-reward correlations require sufficient sample size.",
            "Token per unit output ratios depend on total epoch budget.",
            "overjustification_risk is advisory-only (overjustification effect "
            "guardrail); it never auto-disables rewards.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Organic Certification Readiness Report
# ---------------------------------------------------------------------------


def generate_organic_certification_readiness(
    conn, location_id: str, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a public-safe organic certification readiness report with composite score and sub-dimensions."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_organic_readiness
        WHERE location_id = %s ORDER BY assessment_date DESC LIMIT 1
        """,
        (location_id,),
    )
    readiness = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_organic_transition
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    transitions = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_organic_certifications
        WHERE location_id = %s ORDER BY created_at DESC
        """,
        (location_id,),
    )
    certifications = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_organic_compliance_dashboard
        WHERE location_id = %s
        """,
        (location_id,),
    )
    dashboard = cur.fetchone()
    cur.close()
    return {
        "report_type": "organic_certification_readiness",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "readiness_assessment": dict(readiness) if readiness else None,
        "active_transitions": _serialize_rows(transitions),
        "certifications": _serialize_rows(certifications),
        "compliance_dashboard": dict(dashboard) if dashboard else None,
        "overall_score": float(readiness.get("overall_score", 0)) if readiness else 0,
        "top_barriers": (readiness.get("barriers", []) if readiness else []),
        "limitations": [
            "Organic readiness scores are advisory assessments, not certification guarantees.",
            "Actual certification requires inspection by an accredited certification body.",
            "Transition progress depends on consistent adherence to organic practices.",
            "Readiness scores are computed from self-reported farm data.",
            "Agent synthesis is a draft; not verified or published without human review.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Organic Transition Progress Report
# ---------------------------------------------------------------------------


def generate_organic_transition_progress(
    conn, location_id: str, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a public-safe organic transition progress report with timeline, milestones, and barriers."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_organic_transition
        WHERE location_id = %s
        """,
        (location_id,),
    )
    transitions = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_prohibited_substance_audit
        WHERE location_id = %s
        """,
        (location_id,),
    )
    substances = [dict(r) for r in cur.fetchall()]
    cur.close()
    active = [t for t in transitions if t.get("status") == "active"]
    return {
        "report_type": "organic_transition_progress",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "transitions": _serialize_rows(transitions),
        "active_transition": active[0] if active else None,
        "prohibited_substances": _serialize_rows(substances),
        "total_transitions": len(transitions),
        "active_count": len(active),
        "limitations": [
            "Transition progress is based on self-reported milestone dates.",
            "Prohibited substance records depend on complete farm reporting.",
            "Withdrawal period clearance requires laboratory verification.",
            "Transition timelines may change based on inspection outcomes.",
            "Agent synthesis is a draft; not verified or published without human review.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Organic Input Audit Report
# ---------------------------------------------------------------------------


def generate_organic_input_audit(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe organic input audit report with full input trail, organic/prohibited flags, and compliance."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_organic_input_audit
        WHERE location_id = %s
        ORDER BY application_date DESC
        """,
        (location_id,),
    )
    inputs = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_harvest_segregation
        WHERE location_id = %s
        """,
        (location_id,),
    )
    harvests = [dict(r) for r in cur.fetchall()]
    cur.close()
    total = len(inputs)
    organic = sum(1 for i in inputs if i.get("organic_certified"))
    prohibited = sum(1 for i in inputs if i.get("is_prohibited"))
    compliance_pct = ((total - prohibited) / total * 100) if total > 0 else 100
    return {
        "report_type": "organic_input_audit",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "inputs": _serialize_rows(inputs),
        "harvest_handling": _serialize_rows(harvests),
        "total_inputs": total,
        "organic_certified_inputs": organic,
        "prohibited_inputs": prohibited,
        "compliance_pct": round(compliance_pct, 1),
        "limitations": [
            "Input audit reflects logged data; unreported inputs are not captured.",
            "Organic certification status depends on supplier documentation.",
            "Prohibited substance status is based on self-assessment against standard lists.",
            "Harvest segregation compliance depends on operational discipline.",
            "Agent synthesis is a draft; not verified or published without human review.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Statement of Work Report
# ---------------------------------------------------------------------------


def generate_statement_of_work(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a Statement of Work by assembling data from existing tables.

    Pulls objectives, tasks, phases, steps, financials, staff, partners, and
    SOW-specific tables to produce a comprehensive project document.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Location info
    cur.execute("SELECT name, country, region, latitude, longitude FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()

    # SOW records
    cur.execute(
        """
        SELECT * FROM statement_of_work
        WHERE location_id = %s ORDER BY created_at DESC LIMIT 1
        """,
        (location_id,),
    )
    sow = cur.fetchone()

    # Objectives (Purpose & Objectives)
    cur.execute(
        """
        SELECT objective_name, description, objective_type, target_value, current_value,
               unit, target_date, priority, success_criteria, status
        FROM objective
        WHERE location_id = %s AND status IN ('approved', 'in_progress', 'achieved')
        ORDER BY priority DESC, target_date
        """,
        (location_id,),
    )
    objectives = [dict(r) for r in cur.fetchall()]

    # Tasks (Scope of Work)
    cur.execute(
        """
        SELECT task_name, description, category, start_date, end_date,
               priority, status, estimated_cost_usd, actual_cost_usd
        FROM farm_task
        WHERE location_id = %s AND status != 'cancelled'
        ORDER BY start_date
        """,
        (location_id,),
    )
    tasks = [dict(r) for r in cur.fetchall()]

    # Development Phases (Timeline)
    cur.execute(
        """
        SELECT phase_name, description, phase_order, start_date, end_date, status
        FROM development_phase
        WHERE location_id = %s
        ORDER BY phase_order
        """,
        (location_id,),
    )
    phases = [dict(r) for r in cur.fetchall()]

    # Framework Steps (Methodology)
    cur.execute(
        """
        SELECT step_name, description, step_order, step_type, duration_days, prerequisites, status
        FROM framework_step
        WHERE location_id = %s
        ORDER BY step_order
        """,
        (location_id,),
    )
    steps = [dict(r) for r in cur.fetchall()]

    # Staff (Team)
    cur.execute(
        """
        SELECT s.name, s.role, s.email, d.name AS department_name, jr.name AS job_role_name
        FROM staff s
        LEFT JOIN department d ON s.department_id = d.id
        LEFT JOIN job_role jr ON s.job_role_id = jr.id
        WHERE s.location_id = %s AND s.is_active = TRUE
        """,
        (location_id,),
    )
    staff = [dict(r) for r in cur.fetchall()]

    # Partners (Stakeholders)
    cur.execute(
        """
        SELECT name, partner_type, description, contact_email
        FROM partner
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    partners = [dict(r) for r in cur.fetchall()]

    # Financial Projections
    cur.execute(
        """
        SELECT metric_name, value, unit, confidence_low, confidence_high, period_start, period_end
        FROM forecast_output
        WHERE location_id = %s
        ORDER BY period_start DESC
        LIMIT 10
        """,
        (location_id,),
    )
    forecasts = [dict(r) for r in cur.fetchall()]

    # Financial Sustainability
    cur.execute(
        """
        SELECT projected_annual_revenue_usd, projected_annual_operating_cost_usd,
               projected_annual_noi_usd, runway_months, grant_dependency_pct
        FROM financial_sustainability_plan
        WHERE location_id = %s AND status = 'published'
        LIMIT 1
        """,
        (location_id,),
    )
    sustainability = cur.fetchone()

    # SOW Deliverables
    deliverables = []
    payment_schedule = []
    change_requests = []
    if sow:
        cur.execute("SELECT * FROM sow_deliverable WHERE sow_id = %s ORDER BY due_date", (sow["id"],))
        deliverables = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM sow_payment_schedule WHERE sow_id = %s ORDER BY due_date", (sow["id"],))
        payment_schedule = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM sow_change_request WHERE sow_id = %s ORDER BY created_at", (sow["id"],))
        change_requests = [dict(r) for r in cur.fetchall()]

    cur.close()

    return {
        "report_type": "statement_of_work",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "sow": dict(sow) if sow else None,
        "objectives": _serialize_rows(objectives),
        "scope_of_work": {
            "tasks": _serialize_rows(tasks),
            "development_phases": _serialize_rows(phases),
            "framework_steps": _serialize_rows(steps),
        },
        "deliverables": _serialize_rows(deliverables),
        "timeline": {
            "phases": _serialize_rows(phases),
            "tasks": _serialize_rows(tasks),
        },
        "location_info": dict(location) if location else None,
        "payment_schedule": _serialize_rows(payment_schedule),
        "team": _serialize_rows(staff),
        "stakeholders": _serialize_rows(partners),
        "financial_projections": _serialize_rows(forecasts),
        "financial_sustainability": dict(sustainability) if sustainability else None,
        "change_requests": _serialize_rows(change_requests),
        "limitations": [
            "SOW is assembled from governed data and should be reviewed by authorized personnel.",
            "Financial projections are estimates based on forecast scenarios.",
            "Deliverable acceptance requires human verification and sign-off.",
            "Change requests require mutual agreement per the change management process.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Data Stream Summary
# ---------------------------------------------------------------------------
