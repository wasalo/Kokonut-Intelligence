"""Report generators: liberation."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..common import _serialize_rows


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


