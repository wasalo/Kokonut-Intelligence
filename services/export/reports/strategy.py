"""Strategic, stakeholder, and tactical report generators."""

from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras


def generate_data_stream_summary(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a summary of data stream activity for a location."""
    conditions = ["dsp.location_id = :location_id"]
    params: dict[str, Any] = {"location_id": location_id}

    if period_start:
        conditions.append("dsp.created_at >= :period_start")
        params["period_start"] = period_start
    if period_end:
        conditions.append("dsp.created_at <= :period_end")
        params["period_end"] = period_end

    where = " AND ".join(conditions)

    posts = (
        conn.execute(
            conn.text(
                f"SELECT dsp.post_type, dsp.status, dsp.visibility, dsp.is_anchored, dsp.created_at "
                f"FROM data_stream_post dsp WHERE {where} ORDER BY dsp.created_at DESC"
            ),
            params,
        )
        .mappings()
        .all()
    )

    total_posts = len(posts)
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_visibility: dict[str, int] = {}
    anchored_count = 0

    for p in posts:
        by_type[p["post_type"]] = by_type.get(p["post_type"], 0) + 1
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1
        by_visibility[p["visibility"]] = by_visibility.get(p["visibility"], 0) + 1
        if p["is_anchored"]:
            anchored_count += 1

    return {
        "report_type": "data_stream_summary",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "total_posts": total_posts,
        "anchored_posts": anchored_count,
        "unanchored_posts": total_posts - anchored_count,
        "by_type": by_type,
        "by_status": by_status,
        "by_visibility": by_visibility,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_business_model_canvas(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a Business Model Canvas report for a location."""
    from services.analytics.business_model_canvas import compute_health, get, list_canvas

    canvases = list_canvas(conn, location_id=location_id)
    canvas_data = []
    for c in canvases:
        full = get(conn, str(c["id"]))
        if full:
            canvas_data.append(full)

    # Get latest health score
    health = None
    if canvas_data:
        try:
            health = compute_health(conn, str(canvas_data[0]["id"]))
        except Exception:
            health = None

    return {
        "report_type": "business_model_canvas",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "canvas_count": len(canvas_data),
        "canvases": canvas_data,
        "health_summary": health,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Pitch Deck report
# ---------------------------------------------------------------------------


def generate_pitch_deck(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    from services.analytics.pitch import generate_pitch, render_markdown

    pitch_data = generate_pitch(conn, location_id, "elevator")
    return {
        "report_type": "pitch_deck",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "pitch": pitch_data,
        "markdown": render_markdown(pitch_data),
        "limitations": [
            "Pitch data is generated from live platform records at query time.",
            "Metrics reflect the latest available data and may change.",
            "Audience-specific pitches are available via the pitch CLI.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Business Architecture Report Generators
# ---------------------------------------------------------------------------


def generate_capability_dashboard(conn, location_id=None, period_start=None, period_end=None):
    """Generate a capability map dashboard report."""
    from ..analytics.capability_map import get_capability_dashboard, get_coverage_analysis

    dashboard = get_capability_dashboard()
    coverage = get_coverage_analysis()
    return {
        "report_type": "capability_dashboard",
        "location_id": location_id,
        "capability_count": coverage.get("total_capabilities", 0),
        "process_count": coverage.get("total_processes", 0),
        "service_count": coverage.get("total_services", 0),
        "unmapped_processes": len(coverage.get("unmapped_processes", [])),
        "unmapped_services": len(coverage.get("unmapped_services", [])),
        "capabilities": dashboard,
        "coverage": coverage,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_strategy_execution(conn, location_id=None, period_start=None, period_end=None):
    """Generate a strategy execution report (Balanced Scorecard and kernel)."""
    from ..analytics.competitive_report import health as competitive_health
    from ..analytics.strategy_execution import dashboard
    from ..analytics.strategy_map import get_perspective_summary

    execution = dashboard(conn, scope_type="location", scope_id=location_id) if location_id else dashboard(conn)
    perspectives = get_perspective_summary()
    external_health = []
    for row in execution:
        try:
            external_health.append(competitive_health(conn, str(row["strategy_plan_id"])))
        except Exception:
            continue
    return {
        "report_type": "strategy_execution",
        "location_id": location_id,
        "perspectives": perspectives,
        "entries": execution,
        "external_position_health": external_health,
        "total_entries": len(execution),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_capability_assessment(conn, location_id=None, period_start=None, period_end=None):
    """Generate a capability maturity and coverage assessment."""
    from ..analytics.capability_map import get_capability_dashboard, get_coverage_analysis

    dashboard = get_capability_dashboard()
    coverage = get_coverage_analysis()
    maturity_scores = [c.get("latest_maturity_score") for c in dashboard if c.get("latest_maturity_score")]
    avg_maturity = round(sum(maturity_scores) / len(maturity_scores), 1) if maturity_scores else None
    return {
        "report_type": "capability_assessment",
        "location_id": location_id,
        "average_maturity": avg_maturity,
        "capabilities_with_maturity": len(maturity_scores),
        "total_capabilities": len(dashboard),
        "unmapped_processes": len(coverage.get("unmapped_processes", [])),
        "unmapped_services": len(coverage.get("unmapped_services", [])),
        "capabilities": dashboard,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_value_stream_formal(conn, location_id=None, period_start=None, period_end=None):
    """Generate a formal value stream map report."""
    from ..analytics.value_stream_defs import get_stream_summary

    streams = get_stream_summary()
    return {
        "report_type": "value_stream_formal",
        "location_id": location_id,
        "stream_count": len(streams),
        "streams": streams,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_technology_roadmap(conn, location_id=None, period_start=None, period_end=None):
    """Generate an executive technology roadmap report."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_technology_roadmap_overview ORDER BY name")
        roadmaps = [dict(row) for row in cur.fetchall()]
        for roadmap in roadmaps:
            cur.execute(
                "SELECT id AS requirement_id, title, need_type, priority, target_value, unit, target_date, status "
                "FROM technology_roadmap_requirement WHERE roadmap_id = %s ORDER BY priority DESC, title",
                (roadmap["roadmap_id"],),
            )
            roadmap["requirements"] = [dict(row) for row in cur.fetchall()]
            cur.execute(
                "SELECT alt.id, alt.name, alt.recommendation, alt.maturity_status, alt.confidence, "
                "alt.expected_maturity_date, alt.estimated_cost, td.name AS driver_name, ta.name AS area_name "
                "FROM technology_alternative alt JOIN technology_driver td ON td.id = alt.driver_id "
                "JOIN technology_area ta ON ta.id = td.area_id WHERE ta.roadmap_id = %s "
                "ORDER BY alt.recommendation, alt.expected_maturity_date NULLS LAST, alt.name",
                (roadmap["roadmap_id"],),
            )
            roadmap["alternatives"] = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "technology_roadmap",
        "location_id": location_id,
        "roadmap_count": len(roadmaps),
        "roadmaps": roadmaps,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_landscape(conn, location_id=None, period_start=None, period_end=None):
    """Generate an internal stakeholder landscape report."""
    query = "SELECT * FROM v_stakeholder_landscape"
    params = []
    if location_id:
        query += " WHERE EXISTS (SELECT 1 FROM party_identifier pi WHERE pi.party_id = party_id AND pi.identifier_type = 'location_id' AND pi.identifier_value = %s)"
        params.append(location_id)
    query += " ORDER BY advisory_score DESC NULLS LAST, display_name"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        parties = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_landscape",
        "location_id": location_id,
        "party_count": len(parties),
        "parties": parties,
        "limitations": [
            "Salience is advisory and depends on evidence quality and representation coverage.",
            "Proxy parties represent interests through governed evidence; they do not provide human consent or votes.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_engagement(conn, location_id=None, period_start=None, period_end=None):
    """Generate stakeholder engagement plan and commitment health report."""
    query = "SELECT * FROM v_stakeholder_engagement_summary"
    params = []
    if location_id:
        query += " WHERE scope_type = 'location' AND scope_id = %s::uuid"
        params.append(location_id)
    query += " ORDER BY overdue_commitment_count DESC, name"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        plans = [dict(row) for row in cur.fetchall()]
        health = []
        for plan in plans:
            cur.execute(
                "SELECT * FROM v_stakeholder_commitment_health WHERE plan_id = %s AND is_overdue = TRUE ORDER BY due_at NULLS LAST",
                (plan["plan_id"],),
            )
            health.extend(dict(row) for row in cur.fetchall())
    return {
        "report_type": "stakeholder_engagement",
        "location_id": location_id,
        "plan_count": len(plans),
        "plans": plans,
        "overdue_commitments": health,
        "limitations": [
            "Commitment health indicates due-date and linkage status, not whether the stakeholder considers an outcome satisfactory.",
            "Engagement mode is a plan-level intention and does not prove meaningful participation.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_grievance(conn, location_id=None, period_start=None, period_end=None):
    """Generate an internal grievance, remedy, and appeal health report."""
    query = "SELECT * FROM v_stakeholder_grievance_health"
    params = []
    if location_id:
        query += " WHERE location_id = %s::uuid"
        params.append(location_id)
    query += " ORDER BY is_overdue DESC, severity DESC, received_at"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        cases = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_grievance",
        "location_id": location_id,
        "case_count": len(cases),
        "overdue_count": sum(1 for case in cases if case.get("is_overdue")),
        "cases": cases,
        "limitations": [
            "This is an internal operational report; protected details and private evidence are excluded.",
            "Case status does not establish that a remedy was satisfactory without affected-party confirmation.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_representation(conn, location_id=None, period_start=None, period_end=None):
    """Generate privacy-aware stakeholder representation and equity metrics."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_public_stakeholder_representation ORDER BY activity_type, activity_id")
        representation = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_stakeholder_equity_distribution ORDER BY distribution_type, metric_name")
        distributions = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_representation",
        "location_id": location_id,
        "representation_count": len(representation),
        "representation": representation,
        "distribution_count": len(distributions),
        "distributions": distributions,
        "limitations": [
            "Public representation rows are suppressed for activities with fewer than five invitees.",
            "Aggregated benefit and harm records require verified or published evidence.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_decision_lineage(conn, location_id=None, period_start=None, period_end=None):
    """Generate an internal stakeholder decision, trade-off, and evidence report."""
    query = "SELECT * FROM v_stakeholder_decision_lineage"
    params = []
    if location_id:
        query += " WHERE scope_type = 'location' AND scope_id = %s::uuid"
        params.append(location_id)
    query += " ORDER BY approved_at DESC NULLS LAST, decision_id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        decisions = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_decision_lineage",
        "location_id": location_id,
        "decision_count": len(decisions),
        "decisions": decisions,
        "limitations": [
            "This is an internal lineage report; private evidence and protected grievance details are not exposed.",
            "Approval records human authorization but does not establish that affected stakeholders consented.",
            "Outcome records require separate verification before public impact claims are made.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_ecosystem(conn, location_id=None, period_start=None, period_end=None):
    """Generate the internal stakeholder ecosystem cockpit report."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_stakeholder_cockpit_internal")
        cockpit = dict(cur.fetchone())
        cur.execute("SELECT * FROM v_stakeholder_landscape ORDER BY advisory_score DESC NULLS LAST, display_name")
        landscape = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM relationship_risk_indicator ORDER BY created_at DESC")
        risks = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_party_relationship_recommendations ORDER BY recommendation, display_name")
        recommendations = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_ecosystem",
        "location_id": location_id,
        "cockpit": cockpit,
        "landscape": landscape,
        "relationship_risks": risks,
        "relationship_recommendations": recommendations,
        "limitations": [
            "Salience is advisory and must not be used as an automatic exclusion rule.",
            "Trust and relationship risks require evidence review, correction, and appeal pathways.",
            "Proxy parties represent documented interests; they do not consent or vote.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_outcomes(conn, location_id=None, period_start=None, period_end=None):
    """Generate stakeholder outcomes from governed outcomes and architecture links."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        query = "SELECT * FROM stakeholder_outcome WHERE status IN ('verified', 'published')"
        params = []
        if location_id:
            query += " AND location_id = %s::uuid"
            params.append(location_id)
        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        outcomes = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_stakeholder_capability_value_stream ORDER BY entity_type, entity_name, party_name")
        architecture = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_outcomes",
        "location_id": location_id,
        "outcome_count": len(outcomes),
        "outcomes": outcomes,
        "capability_and_value_stream_links": architecture,
        "limitations": [
            "Only verified or published governed outcomes are included.",
            "Outcome presence does not establish causal attribution or satisfaction without supporting evidence.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_trust(conn, location_id=None, period_start=None, period_end=None):
    """Generate explainable trust profiles, evidence timelines, and disputes."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_party_trust_profile ORDER BY open_risk_count DESC, display_name")
        profiles = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_market_dispute_performance")
        disputes = dict(cur.fetchone())
        cur.execute(
            "SELECT * FROM relationship_risk_indicator WHERE status IN ('open', 'monitoring') ORDER BY created_at DESC"
        )
        risks = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_party_financing_eligibility_inputs ORDER BY open_risk_count DESC, display_name")
        eligibility_inputs = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_trust",
        "location_id": location_id,
        "profiles": profiles,
        "dispute_performance": disputes,
        "relationship_risks": risks,
        "financing_and_insurance_inputs": eligibility_inputs,
        "limitations": [
            "No universal reputation score is calculated or exposed.",
            "Every evidence record should be interpreted with its source, age, confidence, uncertainty, correction, and appeal state.",
            "Trust signals are inputs for human review, not automatic exclusion, financing, or insurance decisions.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_value_streams(conn, location_id=None, period_start=None, period_end=None):
    """Generate stakeholder-aware capability and value-stream outcomes."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_stakeholder_capability_value_stream ORDER BY entity_type, entity_name, party_name")
        links = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_value_stream_performance")
        performance = [dict(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT * FROM stakeholder_bottleneck_priority WHERE status IN ('reviewed', 'active') ORDER BY priority, reviewed_at DESC NULLS LAST"
        )
        bottlenecks = [dict(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT * FROM technology_alternative_stakeholder_outcome WHERE status IN ('reviewed', 'approved') ORDER BY reviewed_at DESC NULLS LAST"
        )
        alternatives = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "stakeholder_value_streams",
        "location_id": location_id,
        "stakeholder_links": links,
        "performance": performance,
        "stakeholder_bottleneck_priorities": bottlenecks,
        "technology_alternative_outcomes": alternatives,
        "limitations": [
            "Operational bottleneck metrics are prioritization signals, not proof of stakeholder harm.",
            "Stakeholder outcomes require evidence and human interpretation alongside process measures.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_stakeholder_cockpit(conn, location_id=None, period_start=None, period_end=None):
    """Generate a composite internal/public-safe stakeholder cockpit snapshot."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_stakeholder_cockpit_internal")
        internal = dict(cur.fetchone())
        cur.execute("SELECT * FROM v_public_stakeholder_cockpit")
        public = dict(cur.fetchone())
    return {
        "report_type": "stakeholder_cockpit",
        "location_id": location_id,
        "internal": internal,
        "public_safe": public,
        "limitations": [
            "Internal and public-safe sections are deliberately separated.",
            "Counts are governed-record indicators and do not prove absence of harm or satisfaction.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_coordination_cockpit(conn, location_id=None, period_start=None, period_end=None):
    """Generate internal coordination controls and public-safe alliance output."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_coordination_cockpit_internal ORDER BY name")
        internal = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_public_coordination_alliance ORDER BY name")
        public = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "coordination_cockpit",
        "location_id": location_id,
        "internal": internal,
        "public_safe": public,
        "limitations": [
            "Internal output includes unresolved conflicts, risks, remedies, and dependency signals for human review.",
            "Public output includes only published summaries and consent-safe aggregate evidence.",
            "Coordination observations do not create ownership or reputation scores.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_governance_coordination_health(conn, location_id=None, period_start=None, period_end=None):
    """Generate internal governance health and public-safe throughput output."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM v_governance_cockpit_internal")
        internal = dict(cur.fetchone())
        cur.execute("SELECT * FROM v_governance_cockpit_public")
        public = dict(cur.fetchone())
        cur.execute("SELECT * FROM v_governance_tension_health ORDER BY severity DESC, urgency DESC")
        tensions = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_governance_proposal_lineage ORDER BY approved_at DESC NULLS LAST, proposal_id")
        proposals = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM v_governance_circle_links ORDER BY term_end NULLS LAST")
        links = [dict(row) for row in cur.fetchall()]
    return {
        "report_type": "governance_coordination_health",
        "location_id": location_id,
        "internal": internal,
        "public_safe": public,
        "tensions": tensions,
        "proposals": proposals,
        "circle_links": links,
        "limitations": [
            "Internal records include unresolved governance risks and are not public evidence.",
            "Public output is aggregate throughput and does not establish stakeholder satisfaction or impact.",
            "Role and circle activity does not replace human approval or existing treasury and Guild governance.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# PESTEL Assessment report
# ---------------------------------------------------------------------------


def generate_pestel_assessment(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    from services.analytics.pestel import list_analyses, render_markdown

    analyses = list_analyses(conn, location_id)
    latest = analyses[0] if analyses else {}
    return {
        "report_type": "pestel_assessment",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "analysis_count": len(analyses),
        "latest_analysis": latest,
        "markdown": render_markdown(latest) if latest else "No PESTEL analyses found",
        "limitations": [
            "PESTEL data is generated from platform records at query time.",
            "Factor scores reflect subjective assessments and evidence availability.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Regional Readiness report
# ---------------------------------------------------------------------------


def generate_regional_readiness(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    from services.analytics.regional_readiness import list_assessments, render_markdown

    assessments = list_assessments(conn, location_id)
    latest = assessments[0] if assessments else {}
    return {
        "report_type": "regional_readiness",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "assessment_count": len(assessments),
        "latest_assessment": latest,
        "markdown": render_markdown(latest) if latest else "No regional readiness assessments found",
        "limitations": [
            "Readiness scores are computed from available platform data.",
            "Missing data sources result in lower scores (not absence of capability).",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Publics & Market Landscape report
# ---------------------------------------------------------------------------


def generate_publics_market_landscape(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    from services.analytics.publics import influence_interest_matrix, list_publics, list_segments

    publics = list_publics(conn, location_id)
    segments = list_segments(conn, location_id)
    matrix = influence_interest_matrix(conn, location_id)
    return {
        "report_type": "publics_market_landscape",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "public_count": len(publics),
        "segment_count": len(segments),
        "publics": publics,
        "segments": segments,
        "matrix": matrix,
        "limitations": [
            "Stakeholder classifications are manually curated or auto-suggested.",
            "Market segment sizes are estimates based on available demand signals.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Environmental Scan report
# ---------------------------------------------------------------------------


def generate_env_scan_report(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    from services.analytics.env_scanning import list_scans, render_markdown

    scans = list_scans(conn, location_id)
    latest = scans[0] if scans else {}
    return {
        "report_type": "env_scan_report",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "scan_count": len(scans),
        "latest_scan": latest,
        "markdown": render_markdown(latest) if latest else "No environmental scans found",
        "limitations": [
            "Scan findings are auto-populated from platform data.",
            "Manual review and human judgment are required for all scan conclusions.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tactical Layer report generators (chess-inspired governance tactics)
# ---------------------------------------------------------------------------


def _tactical_location_param(location_id: Optional[str]) -> Optional[str]:
    return location_id


def generate_fork_opportunities(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Fork tactic: a single event that reveals/creates multiple high-value opportunities."""
    from services.events.fork_detector import detect_fork_opportunities

    result = detect_fork_opportunities(conn, location_id=location_id)
    return {
        "report_type": "fork_opportunities",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "fork_count": result.get("fork_count", 0),
        "forks": result.get("forks", []),
        "note": "Read-only detection. Use events CLI to propose DRAFT tactical items.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_pin_dependency(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Pin tactic: governed records blocked (pinned) by an unverified upstream."""
    from services.analytics.pin_dependency import detect_pin_blocks

    result = detect_pin_blocks(conn, location_id=location_id)
    return {
        "report_type": "pin_dependency",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "pin_count": result.get("pin_count", 0),
        "severity": result.get("severity", "low"),
        "pins": result.get("pins", []),
        "note": "Read-only detection. Use pin_dependency detection to propose DRAFT items.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_promotion_ladder(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Promotion tactic: the regenerative value chain funnel per location."""
    from services.analytics.promotion_ladder import compute_promotion_ladder

    result = compute_promotion_ladder(conn, location_id=location_id)
    return {
        "report_type": "promotion_ladder",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "ladder_depth": result.get("ladder_depth", 4),
        "locations": result.get("locations", []),
        "note": "Read-only funnel; no writes performed.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_tactical_layer(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Composite Tactical Layer view: fork, discovered double-check, pin, zwischenzug, promotion."""
    from services.analytics.pin_dependency import detect_pin_blocks
    from services.analytics.promotion_ladder import compute_promotion_ladder
    from services.events.fork_detector import detect_fork_opportunities
    from services.feedback.automation import detect_zwischenzug
    from services.threatcasting.preempt import plan_preemptive_actions

    forks = detect_fork_opportunities(conn, location_id=location_id)
    preempt = plan_preemptive_actions(conn, location_id=location_id)
    pins = detect_pin_blocks(conn, location_id=location_id)
    zwischenzug = detect_zwischenzug(conn, location_id=location_id)
    ladder = compute_promotion_ladder(conn, location_id=location_id)

    return {
        "report_type": "tactical_layer",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "fork": {"fork_count": forks.get("fork_count", 0), "forks": forks.get("forks", [])},
        "double_check": {
            "double_check_count": preempt.get("double_check_count", 0),
            "double_checks": preempt.get("double_checks", []),
        },
        "pin": {"pin_count": pins.get("pin_count", 0), "severity": pins.get("severity", "low")},
        "zwischenzug": {"zwischenzug_count": zwischenzug.get("zwischenzug_count", 0)},
        "promotion_ladder": {
            "ladder_depth": ladder.get("ladder_depth", 4),
            "locations": ladder.get("locations", []),
        },
        "note": (
            "Composite read-only tactical surface. Individual tactics propose DRAFT "
            "tactical_opportunity rows via their CLIs; human review required to act."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_simulation_wargame(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate an advisory tactical-wargame simulation report.

    ADVISORY-ONLY. Runs two probabilistic stress-tests:
    1. A Monte Carlo yield ensemble over the location's digital twin (yield
       distribution under perturbed weather/inputs).
    2. A two-sided clash of active high/critical threat pressure against the
       location's strategic-reserve adequacy.

    No governed state is written; the "opposing force" is shocks/threats vs.
    reserves, never stakeholders or communities (see AGENTS.md).
    """
    from services.analytics.digital_twin import list_twins, monte_carlo_yield
    from services.simulation.clash_examples import stress_reserve

    result = {
        "report_type": "simulation_wargame",
        "location_id": location_id,
        "monte_carlo_yield": None,
        "reserve_clash": None,
        "note": (
            "Advisory probabilistic stress-test. Outcomes are distributions, not "
            "determinations. No automatic action is taken."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if location_id:
        twins = list_twins(conn, location_id)
        if twins:
            result["monte_carlo_yield"] = monte_carlo_yield(conn, twins[0]["twin_id"], n=200)
        try:
            result["reserve_clash"] = stress_reserve(conn, location_id)
        except Exception as exc:  # advisory: never fatal
            result["reserve_clash"] = {"error": str(exc)}

    return result


def generate_capital_accounting(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate the capital-accounting report (Keynes-inspired, advisory-only).

    Aggregates four lenses over the 8 Forms of Capital:
      - capacity: stock vs regenerative output capacity (under-mobilization)
      - diversion: consumption-vs-reinvestment diversion index
      - capture_risk: value-leakage / concentration signal
      - credit_ledger: DRAFT-only deferred regenerative credits + capacity

    No governed state is written; the credit ledger is a read-only view here.
    """
    from services.capital import accounting_report

    if not location_id:
        raise ValueError("capital_accounting report requires a location_id")

    return accounting_report.build_capital_accounting(conn, location_id, period_start, period_end)


# ---------------------------------------------------------------------------
# REPORT_GENERATORS dictionary
# ---------------------------------------------------------------------------
