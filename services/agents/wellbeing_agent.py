"""Holistic well-being synthesis agent."""

from __future__ import annotations

from collections import Counter
from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.base import SynthesisAgent, agent_cli


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

    cur.close()

    # Language coverage is derived from the same public-safe cultural and
    # wellbeing views as the rest of this summary. Do not read private feedback
    # just to produce language totals.
    language_counts = Counter(
        row["language"]
        for row in (*cultural_rows, *wellbeing_rows)
        if row.get("language")
    )
    language_rows = [
        {"language": language, "public_safe_evidence_count": count}
        for language, count in sorted(
            language_counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]
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
        "safety_note": (
            "Public-safe summaries and language counts from published, public-safe "
            "evidence only; private feedback and cultural evidence are not queried."
        ),
    }


class WellbeingSynthesisAgent(SynthesisAgent):
    task_key = "holistic_wellbeing_synthesis"
    summary_type = "holistic_wellbeing"
    read_collection = "wellbeing_metric_observation"
    model_version = "wellbeing-agent-v1"
    source_tables = [
        "cultural_context_record",
        "wellbeing_metric_observation",
        "participatory_action_record",
        "stakeholder_feedback",
    ]
    source_reference_views = {
        "cultural_context_record": "v_public_cultural_context_summary",
        "wellbeing_metric_observation": "v_public_wellbeing_metric_summary",
        "participatory_action_record": "v_public_participatory_governance_summary",
        "stakeholder_feedback": "v_public_stakeholder_feedback_summary",
    }

    def synthesize(self, conn, location_id=None):
        return synthesize_wellbeing(conn, location_id)


agent = WellbeingSynthesisAgent()


def run_wellbeing_synthesis(location_id: str, store: bool = False) -> dict[str, Any]:
    """Run the agent; delegates to the shared :class:`WellbeingSynthesisAgent` flow."""
    return agent.run(location_id, store=store)


def main() -> None:
    agent_cli(agent, description="Run the Kokonut holistic well-being synthesis agent", location_required=True)


if __name__ == "__main__":
    main()
