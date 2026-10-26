"""Stakeholder feedback synthesis agent."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import (
    SynthesisAgent,
    agent_cli,
    require_synthesis_location_id,
)


def synthesize_feedback(conn, location_id: str) -> dict[str, Any]:
    """Summarize stakeholder voice only from the approved consent-safe view."""
    location_id = require_synthesis_location_id(location_id)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT stakeholder_group, feedback_type, sentiment, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM kokonut_agent_source.v_public_stakeholder_feedback_summary
        WHERE location_id = %s
        ORDER BY feedback_date DESC, id
        """,
        (location_id,),
    )
    public_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Only records already approved for public summaries may contribute to
    # worker aggregates. Private feedback, consent state, and harm narratives
    # stay outside this source-reader identity.
    aggregate_counts: dict[tuple[Any, ...], int] = {}
    for row in public_rows:
        key = (
            row.get("stakeholder_group"),
            row.get("feedback_type"),
            row.get("sentiment"),
            row.get("evidence_maturity"),
        )
        aggregate_counts[key] = aggregate_counts.get(key, 0) + 1
    aggregate_rows = [
        {
            "stakeholder_group": key[0],
            "feedback_type": key[1],
            "sentiment": key[2],
            "evidence_maturity": key[3],
            "feedback_count": count,
        }
        for key, count in sorted(
            aggregate_counts.items(),
            key=lambda item: (-item[1], str(item[0][0] or ""), str(item[0][1] or "")),
        )
    ]

    public_summaries = [row["public_summary"] for row in public_rows if row.get("public_summary")]
    stakeholder_groups = sorted({row["stakeholder_group"] for row in aggregate_rows if row.get("stakeholder_group")})
    synthesis_lines = []
    if public_summaries:
        synthesis_lines.append("Public stakeholder summaries indicate: " + " ".join(public_summaries))
    else:
        synthesis_lines.append("No public stakeholder summaries are available for this location.")
    return {
        "location_id": location_id,
        "stakeholder_groups": stakeholder_groups,
        "public_feedback_count": len(public_rows),
        "private_or_no_consent_count": None,
        "harm_or_unintended_consequence_count": None,
        "public_summaries": public_rows,
        "aggregate_feedback": aggregate_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": (
            "Only published feedback with effective public-summary consent is read. "
            "Private/no-consent counts and harm indicators are unavailable to this worker."
        ),
    }


class FeedbackSynthesisAgent(SynthesisAgent):
    task_key = "feedback_synthesis"
    summary_type = "stakeholder_feedback"
    read_collection = "stakeholder_feedback"
    model_version = "feedback-agent-v1"
    source_tables = ["stakeholder_feedback"]
    source_reference_views = {
        "stakeholder_feedback": "v_public_stakeholder_feedback_summary",
    }

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
