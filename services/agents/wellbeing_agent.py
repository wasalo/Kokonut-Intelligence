"""Holistic well-being synthesis agent."""

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


def synthesize_wellbeing(conn, location_id: str) -> dict[str, Any]:
    """Summarize public-safe well-being, cultural, and participation evidence."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    cultural_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT metric_key, metric_name, observation_date, stakeholder_group,
               language, score_value, count_value, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_wellbeing_metric_summary
        WHERE location_id = %s
        ORDER BY observation_date DESC, metric_key
        """,
        (location_id,),
    )
    wellbeing_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT action_type, action_date, stakeholder_group, feedback_type,
               sentiment, metric_name, metric_proposal_status, decision_status,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_participatory_governance_summary
        WHERE location_id = %s
        ORDER BY action_date DESC, action_type
        """,
        (location_id,),
    )
    participation_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT language, COUNT(*) AS feedback_count,
               COUNT(*) FILTER (WHERE consent_given = TRUE AND is_public = TRUE) AS public_safe_count
        FROM stakeholder_feedback
        WHERE location_id = %s AND status != 'rejected'
        GROUP BY language
        ORDER BY feedback_count DESC, language
        """,
        (location_id,),
    )
    language_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    languages = sorted({row["language"] for row in language_rows if row.get("language")})
    cultural_count = len(cultural_rows)
    wellbeing_count = len(wellbeing_rows)
    participation_count = len(participation_rows)

    synthesis_lines = []
    if wellbeing_rows:
        synthesis_lines.append(f"{wellbeing_count} public-safe well-being metric observation(s) are available.")
    else:
        synthesis_lines.append("No public-safe well-being metric observations are available for this location.")
    if cultural_rows:
        synthesis_lines.append(f"{cultural_count} public-safe cultural context record(s) are available.")
    if languages:
        synthesis_lines.append("Stakeholder evidence languages recorded: " + ", ".join(languages) + ".")
    if participation_rows:
        synthesis_lines.append(f"{participation_count} public-safe participatory action(s) link community voice to follow-up.")

    return {
        "location_id": location_id,
        "cultural_context_count": cultural_count,
        "wellbeing_metric_count": wellbeing_count,
        "participatory_action_count": participation_count,
        "languages": languages,
        "cultural_context": cultural_rows,
        "wellbeing_metrics": wellbeing_rows,
        "participatory_actions": participation_rows,
        "language_coverage": language_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": "Public-safe summaries and aggregate language counts only; raw private stakeholder or cultural evidence is not included.",
    }


def store_wellbeing_summary(conn, summary: dict[str, Any], model_version: str = "wellbeing-agent-v1") -> str:
    """Store a draft AI summary for human review."""
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    summary_id = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, 'holistic_wellbeing', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            summary["location_id"],
            summary["synthesis"],
            ["cultural_context_record", "wellbeing_metric_observation", "participatory_action_record"],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_wellbeing_synthesis(location_id: str, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "wellbeing_metric_observation", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_wellbeing(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_wellbeing_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("holistic_wellbeing_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut holistic well-being synthesis agent")
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_wellbeing_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
