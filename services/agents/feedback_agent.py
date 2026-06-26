"""Stakeholder feedback synthesis agent."""

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


def synthesize_feedback(conn, location_id: str) -> dict[str, Any]:
    """Summarize public stakeholder voice and aggregate private-feedback signals."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_stakeholder_feedback_summary
        WHERE location_id = %s
        ORDER BY feedback_date DESC, id
        """,
        (location_id,),
    )
    public_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, status,
               consent_given, is_public, evidence_maturity,
               COUNT(*) AS feedback_count,
               COUNT(*) FILTER (WHERE consent_given = FALSE) AS private_or_no_consent_count,
               COUNT(*) FILTER (WHERE harms_or_unintended_consequences IS NOT NULL) AS harm_count
        FROM stakeholder_feedback
        WHERE location_id = %s AND status != 'rejected'
        GROUP BY stakeholder_group, feedback_type, sentiment, status,
                 consent_given, is_public, evidence_maturity
        ORDER BY feedback_count DESC, stakeholder_group
        """,
        (location_id,),
    )
    aggregate_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    public_summaries = [row["public_summary"] for row in public_rows if row.get("public_summary")]
    stakeholder_groups = sorted({row["stakeholder_group"] for row in aggregate_rows if row.get("stakeholder_group")})
    private_count = sum(int(row.get("private_or_no_consent_count") or 0) for row in aggregate_rows)
    harm_count = sum(int(row.get("harm_count") or 0) for row in aggregate_rows)

    synthesis_lines = []
    if public_summaries:
        synthesis_lines.append("Public stakeholder summaries indicate: " + " ".join(public_summaries))
    else:
        synthesis_lines.append("No public stakeholder summaries are available for this location.")
    if private_count:
        synthesis_lines.append(f"{private_count} feedback record(s) remain private or lack public consent.")
    if harm_count:
        synthesis_lines.append(f"{harm_count} record(s) mention harms or unintended consequences and require reviewer attention.")

    return {
        "location_id": location_id,
        "stakeholder_groups": stakeholder_groups,
        "public_feedback_count": len(public_rows),
        "private_or_no_consent_count": private_count,
        "harm_or_unintended_consequence_count": harm_count,
        "public_summaries": public_rows,
        "aggregate_feedback": aggregate_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Raw private feedback is not included; private/no-consent records are aggregated only.",
    }


def store_feedback_summary(conn, summary: dict[str, Any], model_version: str = "feedback-agent-v1") -> str:
    """Store a draft AI summary for human review."""
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    summary_id = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, 'stakeholder_feedback', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            summary["location_id"],
            summary["synthesis"],
            ["stakeholder_feedback", "stakeholder_feedback_review"],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_feedback_synthesis(location_id: str, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "stakeholder_feedback", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_feedback(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_feedback_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("feedback_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut stakeholder feedback synthesis agent")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_feedback_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
