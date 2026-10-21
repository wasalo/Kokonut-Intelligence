"""Delphi facilitator agent.

Acts as the AI facilitator for Real-time Delphi studies: builds anonymized
live summaries of the panel distribution and in-memory recommendation
suggestions. Persisted drafts and review decisions use the authenticated
location-scoped Gateway; a human must review before any outcome is approved.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from services.agents.tasks import (
    validate_output,
    validate_task_capabilities,
    validate_task_inputs,
)
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
    """Prepare an in-memory suggestion; compatibility actor/facilitator args are ignored."""
    validate_task_capabilities("delphi_facilitation")
    errors = validate_task_inputs("delphi_facilitation", {"study_id": study_id})
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "study_id": study_id,
        "summary": summary,
        "recommendation_text": recommendation_text,
        "status": "draft",
        "safety_note": (
            "In-memory agent suggestion only. Persist through the authenticated "
            "operator Gateway draft route and review it independently."
        ),
    }


def run_delphi_facilitation(
    study_id: str,
    draft: bool = False,
    recommendation_text: Optional[str] = None,
    facilitator: Optional[Facilitator] = None,
) -> Dict[str, Any]:
    """Run the facilitator: summarize (and optionally draft a recommendation)."""
    validate_task_capabilities("delphi_facilitation")
    errors = validate_task_inputs("delphi_facilitation", {"study_id": study_id})
    if errors:
        raise ValueError("; ".join(errors))
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
