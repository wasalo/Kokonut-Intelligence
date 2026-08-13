"""Delphi facilitator agent.

Acts as the AI facilitator for Real-time Delphi studies: builds anonymized
live summaries of the panel distribution and drafts recommendations. Per
Kokonut agent safety rules, the agent may only create DRAFT recommendations; a
human must approve before any outcome is published.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.common.cli import print_json
from services.delphi.facilitator import Facilitator


def summarize_study(study_id: str, facilitator: Optional[Facilitator] = None) -> Dict[str, Any]:
    """Build an anonymized, human-readable summary of the current panel state."""
    fac = facilitator or Facilitator()
    summary = fac.get_live_summary(study_id)

    lines: List[str] = []
    lines.append(f"Delphi study '{summary['title']}' — status: {summary['status']}, "
                 f"panel size: {summary['panel_size']}.")
    for item in summary["items"]:
        label = item.get("label", "?")
        median = item.get("median")
        iqr = item.get("iqr")
        count = item.get("participant_count", 0)
        reached = item.get("consensus_reached", False)
        lines.append(
            f"- {label} [{item.get('scale')}]: median={median}, iqr={iqr}, "
            f"n={count}, consensus={'yes' if reached else 'no'}"
        )

    conflicting = summary.get("conflicting_viewpoints", {})
    if conflicting:
        lines.append("Conflicting viewpoints (anonymized):")
        for item_id, c in conflicting.items():
            low = c.get("lowest", {})
            high = c.get("highest", {})
            lines.append(
                f"  * {low.get('display_token')} (score {low.get('score')}) vs "
                f"{high.get('display_token')} (score {high.get('score')})"
            )

    return {
        "study_id": study_id,
        "title": summary["title"],
        "status": summary["status"],
        "panel_size": summary["panel_size"],
        "items": summary["items"],
        "conflicting_viewpoints": conflicting,
        "synthesis": "\n".join(lines),
    }


def draft_recommendation(
    study_id: str,
    recommendation_text: str,
    summary: Optional[str] = None,
    created_by: Optional[str] = None,
    facilitator: Optional[Facilitator] = None,
) -> Dict[str, Any]:
    """Draft a recommendation. Agents cannot publish — status stays 'draft'."""
    assert_agent_action_allowed("create", "delphi_recommendation", {"status": "draft"})
    fac = facilitator or Facilitator()
    rec = fac.draft_recommendation(
        study_id=study_id,
        recommendation_text=recommendation_text,
        summary=summary,
        created_by=created_by,
    )
    return rec


def run_delphi_facilitation(
    study_id: str,
    draft: bool = False,
    recommendation_text: Optional[str] = None,
    facilitator: Optional[Facilitator] = None,
) -> Dict[str, Any]:
    """Run the facilitator: summarize (and optionally draft a recommendation)."""
    fac = facilitator or Facilitator()
    summary = summarize_study(study_id, fac)
    output: Dict[str, Any] = {"summary": summary}

    if draft:
        if not recommendation_text:
            recommendation_text = (
                "Based on current panel consensus, the facilitator recommends "
                "closing the study and adopting the median positions per item for "
                "downstream decision-making."
            )
        rec = draft_recommendation(study_id, recommendation_text, summary.get("synthesis"), facilitator=fac)
        output["recommendation_draft"] = rec

    errors = validate_output("delphi_facilitation", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut Delphi facilitator agent")
    parser.add_argument("--study-id", required=True, help="Delphi study UUID")
    parser.add_argument("--draft", action="store_true", help="Also draft a recommendation")
    parser.add_argument("--recommendation-text", help="Custom recommendation text (with --draft)")
    args = parser.parse_args()

    print_json(
        run_delphi_facilitation(args.study_id, draft=args.draft, recommendation_text=args.recommendation_text),
    )


if __name__ == "__main__":
    main()
