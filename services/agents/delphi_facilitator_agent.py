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


def summarize_study(study_id: str, location_id: str) -> Dict[str, Any]:
    """Build a live summary from consented aggregates at one signed location."""
    from services.agents.worker_cli import run_worker_delphi_facilitation

    errors = validate_task_inputs(
        "delphi_facilitation", {"study_id": study_id, "location_id": location_id}
    )
    if errors:
        raise ValueError("; ".join(errors))
    summary = run_worker_delphi_facilitation(study_id, location_id)

    lines: List[str] = []
    lines.append(f"Delphi study '{summary['title']}' — status: {summary['status']}, "
                 f"panel size: {summary['panel_size'] if summary['panel_size_available'] else 'suppressed'}.")
    for item in summary["items"]:
        label = item.get("label", "?")
        if not item.get("results_available"):
            lines.append(f"- {label}: results suppressed until the consented panel meets its privacy threshold.")
            continue
        median = item.get("median")
        iqr = item.get("iqr")
        count = item.get("participant_count", 0)
        reached = item.get("consensus_reached", False)
        lines.append(
            f"- {label} [{item.get('scale')}]: median={median}, iqr={iqr}, "
            f"n={count}, consensus={'yes' if reached else 'no'}"
        )

    return {
        "study_id": study_id,
        "location_id": location_id,
        "source_scope": summary["source_scope"],
        "title": summary["title"],
        "status": summary["status"],
        "panel_size": summary["panel_size"],
        "panel_size_available": summary["panel_size_available"],
        "items": summary["items"],
        "privacy_note": (
            "Only consented aggregate responses are shown. Results below the "
            "study privacy threshold are suppressed; participant tokens and "
            "free-text reasoning are never included."
        ),
        "synthesis": "\n".join(lines),
    }


def draft_recommendation(
    study_id: str,
    location_id: str,
    recommendation_text: str,
    summary: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare an in-memory suggestion; caller-supplied actor identity is ignored."""
    validate_task_capabilities("delphi_facilitation")
    errors = validate_task_inputs(
        "delphi_facilitation", {"study_id": study_id, "location_id": location_id}
    )
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "study_id": study_id,
        "location_id": location_id,
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
    location_id: str,
    draft: bool = False,
    recommendation_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the facilitator: summarize (and optionally draft a recommendation)."""
    validate_task_capabilities("delphi_facilitation")
    errors = validate_task_inputs(
        "delphi_facilitation", {"study_id": study_id, "location_id": location_id}
    )
    if errors:
        raise ValueError("; ".join(errors))
    summary = summarize_study(study_id, location_id)
    output: Dict[str, Any] = {"summary": summary}

    if draft:
        if not recommendation_text:
            recommendation_text = (
                "Based on current panel consensus, the facilitator recommends "
                "closing the study and adopting the median positions per item for "
                "downstream decision-making."
            )
        rec = draft_recommendation(
            study_id,
            location_id,
            recommendation_text,
            summary.get("synthesis"),
        )
        output["recommendation_draft"] = rec

    errors = validate_output("delphi_facilitation", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut Delphi facilitator agent")
    parser.add_argument("--study-id", required=True, help="Delphi study UUID")
    parser.add_argument("--location-id", required=True, help="Location UUID owning the Delphi study")
    parser.add_argument("--draft", action="store_true", help="Also draft a recommendation")
    parser.add_argument("--recommendation-text", help="Custom recommendation text (with --draft)")
    args = parser.parse_args()

    print_json(
        run_delphi_facilitation(
            args.study_id,
            args.location_id,
            draft=args.draft,
            recommendation_text=args.recommendation_text,
        ),
    )


if __name__ == "__main__":
    main()
