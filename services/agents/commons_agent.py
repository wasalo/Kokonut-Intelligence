"""Commons liberation and stewardship synthesis agent."""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def _location_filter(column: str, location_id: str | None) -> tuple[str, tuple[Any, ...]]:
    if location_id:
        return f"WHERE {column} = %s", (location_id,)
    return "", ()


def synthesize_commons(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe time liberation, capital alignment, governance inclusion, and land stewardship."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT workflow_area, location_id, observation_date, baseline_hours, observed_hours,
               hours_reclaimed, burden_reduction_pct, automation_or_agent_used,
               automation_type, beneficiary_group, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_time_liberation_summary
        {where}
        ORDER BY observation_date DESC, workflow_area
        """,
        params,
    )
    time_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT provider_name, location_id, assessment_date, provider_type,
               alignment_status, extractive_risk_level, community_control_terms,
               profit_extraction_limits, commons_reinvestment_commitment_pct,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_capital_alignment_summary
        {where}
        ORDER BY assessment_date DESC, provider_type
        """,
        params,
    )
    capital_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT governance_body, location_id, observation_date, inclusion_scope,
               represented_groups, missing_groups, pseudonymous_participation_enabled,
               marginalized_voice_count, total_participant_count,
               representation_coverage_pct, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_governance_inclusion_summary
        {where}
        ORDER BY observation_date DESC, governance_body
        """,
        params,
    )
    inclusion_rows = [dict(r) for r in cur.fetchall()]

    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT stewardship_model, location_id, commitment_date, landlord_dependency_risk,
               anti_speculation_terms, community_benefit_rights, commons_transition_path,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_land_stewardship_summary
        {where}
        ORDER BY commitment_date DESC, stewardship_model
        """,
        params,
    )
    land_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    hours_reclaimed = sum(float(row.get("hours_reclaimed") or 0) for row in time_rows)
    high_capital_risk = [row for row in capital_rows if row.get("extractive_risk_level") in {"high", "critical"}]
    pseudonymous_count = sum(1 for row in inclusion_rows if row.get("pseudonymous_participation_enabled"))

    synthesis_lines = []
    if time_rows:
        synthesis_lines.append(f"{len(time_rows)} public time-liberation observation(s) document {hours_reclaimed:,.1f} reclaimed hours.")
    else:
        synthesis_lines.append("No public time-liberation observations are available.")
    if capital_rows:
        synthesis_lines.append(f"{len(capital_rows)} capital alignment assessment(s) are available; {len(high_capital_risk)} are high or critical extractive risk.")
    if inclusion_rows:
        synthesis_lines.append(f"{len(inclusion_rows)} governance inclusion observation(s) are available; {pseudonymous_count} enable privacy-preserving participation.")
    if land_rows:
        synthesis_lines.append(f"{len(land_rows)} land stewardship commitment(s) are available with explicit claim boundaries.")

    return {
        "location_id": location_id,
        "time_liberation_count": len(time_rows),
        "capital_alignment_count": len(capital_rows),
        "governance_inclusion_count": len(inclusion_rows),
        "land_stewardship_count": len(land_rows),
        "total_hours_reclaimed": round(hours_reclaimed, 2),
        "high_or_critical_extractive_risk_count": len(high_capital_risk),
        "pseudonymous_participation_enabled_count": pseudonymous_count,
        "time_liberation": time_rows,
        "capital_alignment": capital_rows,
        "governance_inclusion": inclusion_rows,
        "land_stewardship": land_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe summaries only; private labor records, private capital terms, raw identity details, and unsupported land-transfer claims are excluded.",
    }


def store_commons_summary(conn, summary: dict[str, Any], model_version: str = "commons-agent-v1") -> str:
    """Store a draft AI summary for human review."""
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    summary_id = str(uuid.uuid4())
    subject_id = summary.get("location_id") or "00000000-0000-0000-0000-000000000000"
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, 'commons_liberation', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            [
                "time_liberation_observation",
                "capital_alignment_assessment",
                "governance_inclusion_observation",
                "land_stewardship_commitment",
            ],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_commons_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "time_liberation_observation", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_commons(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_commons_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("commons_liberation_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut commons liberation synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_commons_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
