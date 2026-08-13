"""Commons, bio-factory, stewardship, and ecological report generators."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from .common import (
    _serialize_rows,
)


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
        row
        for row in inputs
        if row.get("origin_region")
        and any(
            keyword in (row.get("origin_region") or "").lower()
            for keyword in [
                "caribbean",
                "central america",
                "south america",
                "monte plata",
                "dominican",
                "mexico",
                "latin america",
                "sabana grande",
                "greater antilles",
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


def generate_bio_recipe_library(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
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


def generate_bio_regional_input(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
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


def generate_governance_inclusion(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
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
        "pseudonymous_participation_enabled_count": sum(
            1 for row in observations if row.get("pseudonymous_participation_enabled")
        ),
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


def generate_community_governance(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
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


def generate_replication_readiness(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
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


def generate_perpetual_value_stress(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
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
    watchlist = [
        row
        for row in scenarios
        if row.get("solvency_status") in {"watchlist", "needs_mitigation", "insolvent_without_support"}
    ]
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


def generate_open_source_impact(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate public-safe open-source artifact reuse report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM v_public_open_source_impact_artifact ORDER BY reuse_count DESC, artifact_type, artifact_name"
    )
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
    # Validate identifiers to prevent SQL injection
    import re

    _IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    _ORDER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*$")
    if not _IDENT_RE.match(view_name):
        raise ValueError(f"Invalid view name: {view_name}")
    if not _ORDER_RE.match(order_by):
        raise ValueError(f"Invalid order_by: {order_by}")

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


def generate_anti_capture_governance(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    policies = _fetch_public_view(
        conn, "v_public_anti_capture_governance_policy", location_id, "policy_scope, policy_name"
    )
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


def generate_redistribution_policy(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    policies = _fetch_public_view(
        conn, "v_public_commons_redistribution_policy", location_id, "policy_status, policy_scope, policy_name"
    )
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


def generate_federation_mutual_aid(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    protocols = _fetch_public_view(
        conn, "v_public_federation_protocol", None, "protocol_status, federation_scope, protocol_name"
    )
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


def generate_algorithmic_redistribution(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    mechanisms = _fetch_public_view(
        conn,
        "v_public_algorithmic_redistribution_mechanism",
        location_id,
        "implementation_status, mechanism_type, mechanism_name",
    )
    return {
        "report_type": "algorithmic_redistribution",
        "location_id": location_id,
        "mechanisms": _serialize_rows(mechanisms),
        "active_or_pilot_count": sum(
            1 for row in mechanisms if row.get("implementation_status") in {"active", "pilot"}
        ),
        "limitations": [
            "Redistribution mechanisms are not onchain payment implementations unless enforcement mode documents smart-contract execution.",
            "Public reports exclude private eligibility, protected-class details, and household-level beneficiary data.",
            "Airdrops, progressive fees, or reparations claims require separate governed implementation records.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_participatory_signal(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    experiments = _fetch_public_view(
        conn, "v_public_participatory_signal_experiment", None, "experiment_status, signal_type, experiment_name"
    )
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
        WHERE location_id = %s
          AND (%s::date IS NULL OR run_date >= %s::date)
          AND (%s::date IS NULL OR run_date <= %s::date)
        ORDER BY run_date DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    models = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_population_dynamics_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR record_date >= %s::date)
          AND (%s::date IS NULL OR record_date <= %s::date)
        ORDER BY species_name, record_date
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    populations = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_energy_flow_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR measurement_date >= %s::date)
          AND (%s::date IS NULL OR measurement_date <= %s::date)
        ORDER BY measurement_date DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    energy_flows = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_soil_input_retention
        WHERE location_id = %s
          AND (%s::date IS NULL OR application_date >= %s::date)
          AND (%s::date IS NULL OR application_date <= %s::date)
        ORDER BY application_date DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    soil_inputs = [dict(r) for r in cur.fetchall()]
    cur.close()
    mutualism_count = sum(1 for i in interactions if i.get("interaction_type") == "mutualism")
    predation_count = sum(1 for i in interactions if i.get("interaction_type") == "predation")
    trophic_balance = mutualism_count / max(mutualism_count + predation_count, 1)
    avg_residual = sum(s.get("residual_pct", 0) or 0 for s in soil_inputs) / max(len(soil_inputs), 1)
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
          AND (%s::date IS NULL OR record_date >= %s::date)
          AND (%s::date IS NULL OR record_date <= %s::date)
        GROUP BY trophic_level
        """,
        (location_id, period_start, period_start, period_end, period_end),
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
