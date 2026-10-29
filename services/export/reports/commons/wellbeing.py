"""Report generators: wellbeing."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..common import _looks_like_uuid, _serialize_rows


def generate_gnh_alignment(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe GNH alignment report."""
    if not _looks_like_uuid(location_id):
        raise ValueError("gnh_alignment requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
        location = cur.fetchone()
        cur.execute(
            """
            SELECT id,
                   location_id,
                   farm_id,
                   assessment_date,
                   gnh_domain,
                   principle_refs,
                   alignment_score,
                   strengths,
                   gaps,
                   safeguards,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_gnh_alignment_summary
            WHERE location_id = %s
              AND (%s::date IS NULL OR assessment_date >= %s::date)
              AND (%s::date IS NULL OR assessment_date <= %s::date)
            ORDER BY assessment_date DESC, gnh_domain
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        assessments = [dict(r) for r in cur.fetchall()]
    finally:
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
    if not _looks_like_uuid(location_id):
        raise ValueError("cultural_preservation requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
        location = cur.fetchone()
        cur.execute(
            """
            SELECT id,
                   location_id,
                   farm_id,
                   cultural_context_record_id,
                   plan_date,
                   cultural_element,
                   preservation_type,
                   local_language,
                   digital_integration_strategy,
                   consent_protocol,
                   local_reviewer_role,
                   implementation_status,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_cultural_preservation_summary
            WHERE location_id = %s
              AND (%s::date IS NULL OR plan_date >= %s::date)
              AND (%s::date IS NULL OR plan_date <= %s::date)
            ORDER BY plan_date DESC, cultural_element
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        plans = [dict(r) for r in cur.fetchall()]
    finally:
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
    if not _looks_like_uuid(location_id):
        raise ValueError("renewable_energy requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
        location = cur.fetchone()
        cur.execute(
            """
            SELECT id,
                   location_id,
                   farm_id,
                   plan_date,
                   energy_use_case,
                   renewable_source,
                   implementation_status,
                   current_energy_source,
                   planned_capacity_kw,
                   estimated_annual_kwh,
                   renewable_share_pct,
                   fossil_displacement_estimate_co2e_tonnes,
                   infrastructure_dependencies,
                   maintenance_owner_role,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_renewable_energy_summary
            WHERE location_id = %s
              AND (%s::date IS NULL OR plan_date >= %s::date)
              AND (%s::date IS NULL OR plan_date <= %s::date)
            ORDER BY plan_date DESC, energy_use_case
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        plans = [dict(r) for r in cur.fetchall()]
    finally:
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
    if not _looks_like_uuid(location_id):
        raise ValueError("vulnerable_access requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
        location = cur.fetchone()
        cur.execute(
            """
            SELECT id,
                   location_id,
                   farm_id,
                   plan_date,
                   access_scope,
                   vulnerable_groups,
                   access_barriers,
                   accommodations,
                   participation_pathways,
                   accountable_role,
                   implementation_status,
                   access_coverage_pct,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_vulnerable_access_summary
            WHERE location_id = %s
              AND (%s::date IS NULL OR plan_date >= %s::date)
              AND (%s::date IS NULL OR plan_date <= %s::date)
            ORDER BY plan_date DESC, access_scope
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        plans = [dict(r) for r in cur.fetchall()]
    finally:
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
    if not _looks_like_uuid(location_id):
        raise ValueError("foundational_wellbeing requires an explicit location_id")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
        location = cur.fetchone()
        cur.execute(
            """
            SELECT id,
                   location_id,
                   farm_id,
                   observation_date,
                   wellbeing_domain,
                   stakeholder_group,
                   score_value,
                   count_value,
                   public_summary,
                   evidence_maturity,
                   evidence_maturity_label,
                   metadata
            FROM v_public_foundational_wellbeing_summary
            WHERE location_id = %s
              AND (%s::date IS NULL OR observation_date >= %s::date)
              AND (%s::date IS NULL OR observation_date <= %s::date)
            ORDER BY observation_date DESC, wellbeing_domain
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        observations = [dict(r) for r in cur.fetchall()]
    finally:
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


