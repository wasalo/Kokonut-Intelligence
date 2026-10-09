"""Stakeholder feedback synthesis agent."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import SynthesisAgent, agent_cli


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


class FeedbackSynthesisAgent(SynthesisAgent):
    task_key = "feedback_synthesis"
    summary_type = "stakeholder_feedback"
    read_collection = "stakeholder_feedback"
    model_version = "feedback-agent-v1"
    source_tables = ["stakeholder_feedback", "stakeholder_feedback_review"]

    def synthesize(self, conn, location_id=None):
        return synthesize_feedback(conn, location_id)


agent = FeedbackSynthesisAgent()


def run_feedback_synthesis(location_id: str, store: bool = False) -> dict[str, Any]:
    """Run the agent; delegates to the shared :class:`FeedbackSynthesisAgent` flow."""
    return agent.run(location_id, store=store)


def main() -> None:
    agent_cli(agent, description="Run the Kokonut stakeholder feedback synthesis agent", location_required=True)


if __name__ == "__main__":
    main()
