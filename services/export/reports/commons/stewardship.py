"""Report generators: stewardship."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..common import _serialize_rows


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


