"""CLI for the Real-time Delphi service."""

from __future__ import annotations

import argparse
import json
from typing import Any


def _require_scoped_gateway(operation: str) -> None:
    """Block legacy database operations that have no authenticated tenant scope."""
    raise SystemExit(
        f"Direct Delphi {operation} is disabled because the CLI has no authenticated "
        "location grant; use an authenticated location-scoped Operator Gateway "
        "operation when available"
    )


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def cmd_create_study(args):
    _require_scoped_gateway("study creation")


def cmd_open_study(args):
    _require_scoped_gateway("study opening")


def cmd_close_study(args):
    _require_scoped_gateway("study closing")


def cmd_add_panel(args):
    _require_scoped_gateway("panel enrollment")


def cmd_list_panel(args):
    _require_scoped_gateway("panel listing")


def cmd_add_item(args):
    _require_scoped_gateway("item creation")


def cmd_submit(args):
    _require_scoped_gateway("contribution submission")


def cmd_live_summary(args):
    from services.agents.delphi_facilitator_agent import summarize_study

    print(_json(summarize_study(args.study_id, args.location_id)))


def cmd_consensus(args):
    from services.agents.delphi_facilitator_agent import summarize_study

    summary = summarize_study(args.study_id, args.location_id)
    print(_json({"study_id": args.study_id, "items": summary["items"]}))


def cmd_check_stopping(args):
    _require_scoped_gateway("stopping-criteria evaluation")


def cmd_draft_recommendation(args):
    from services.agents.delphi_facilitator_agent import draft_recommendation
    rec = draft_recommendation(
        study_id=args.study_id,
        location_id=args.location_id,
        recommendation_text=args.text,
        summary=args.summary,
        created_by=args.created_by,
    )
    print(_json(rec))


def cmd_approve_recommendation(args):
    _require_scoped_gateway("recommendation review")


def cmd_list_recommendations(args):
    _require_scoped_gateway("recommendation reads")


def cmd_reject_recommendation(args):
    _require_scoped_gateway("recommendation review")


def cmd_calibrate_panel(args):
    _require_scoped_gateway("panel calibration")


def cmd_list_studies(args):
    _require_scoped_gateway("study listing")


def main():
    parser = argparse.ArgumentParser(description="Real-time Delphi Service")
    sub = parser.add_subparsers(dest="command", help="Command")

    # Study
    p = sub.add_parser("create-study", help="Create a Delphi study")
    p.add_argument("--title", required=True)
    p.add_argument("--description")
    p.add_argument("--location-id")
    p.add_argument("--variation", default="real_time")
    p.add_argument("--facilitator-type", default="agent")
    p.add_argument("--criteria", help="JSON stopping criteria")
    p.add_argument("--created-by")
    p.set_defaults(func=cmd_create_study)

    p = sub.add_parser("open-study", help="Open a study")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_open_study)

    p = sub.add_parser("close-study", help="Close a study")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_close_study)

    p = sub.add_parser("list-studies", help="List studies")
    p.set_defaults(func=cmd_list_studies)

    # Panel
    p = sub.add_parser("add-panel", help="Add a panel member")
    p.add_argument("--study-id", required=True)
    p.add_argument("--ref-type", default="farmer_identity")
    p.add_argument("--ref-id")
    p.add_argument("--role", default="expert", choices=["expert", "policymaker", "citizen"])
    p.add_argument("--token")
    p.add_argument("--public", action="store_true", help="Disable anonymity")
    p.add_argument("--weight", type=float)
    p.set_defaults(func=cmd_add_panel)

    p = sub.add_parser("list-panel", help="List panel members")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_list_panel)

    # Items
    p = sub.add_parser("add-item", help="Add an item")
    p.add_argument("--study-id", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--type", default="option", choices=["issue", "goal", "option"])
    p.add_argument("--scale", default="desirability",
                   choices=["desirability", "feasibility_technical", "feasibility_political", "probability"])
    p.add_argument("--description")
    p.add_argument("--min-value", type=float, default=-1.0)
    p.add_argument("--max-value", type=float, default=1.0)
    p.add_argument("--target-type")
    p.add_argument("--target-id")
    p.set_defaults(func=cmd_add_item)

    # Contributions
    p = sub.add_parser("submit", help="Submit/update a contribution")
    p.add_argument("--study-id", required=True)
    p.add_argument("--item-id", required=True)
    p.add_argument("--member-id", required=True)
    p.add_argument("--score", type=float, required=True)
    p.add_argument("--reasoning")
    p.set_defaults(func=cmd_submit)

    # Consensus / summaries
    p = sub.add_parser("live-summary", help="Anonymized live summary")
    p.add_argument("--study-id", required=True)
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_live_summary)

    p = sub.add_parser("consensus", help="Current consensus snapshots")
    p.add_argument("--study-id", required=True)
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_consensus)

    p = sub.add_parser("check-stopping", help="Evaluate stopping criteria")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_check_stopping)

    # Recommendations
    p = sub.add_parser(
        "draft-recommendation",
        help="Generate an in-memory recommendation suggestion (not persisted)",
    )
    p.add_argument("--study-id", required=True)
    p.add_argument("--location-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--summary")
    p.add_argument("--created-by", help="Ignored for compatibility; identity is Gateway-derived")
    p.set_defaults(func=cmd_draft_recommendation)

    p = sub.add_parser("approve-recommendation", help="Approve a recommendation (human)")
    p.add_argument("--recommendation-id", required=True)
    p.add_argument("--approved-by", required=True)
    p.set_defaults(func=cmd_approve_recommendation)

    p = sub.add_parser("list-recommendations", help="List recommendations")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_list_recommendations)

    p = sub.add_parser("reject-recommendation", help="Reject a recommendation (human)")
    p.add_argument("--recommendation-id", required=True)
    p.add_argument("--rejected-by", required=True)
    p.add_argument("--reason")
    p.set_defaults(func=cmd_reject_recommendation)

    p = sub.add_parser("calibrate-panel", help="Recalibrate expert weights")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_calibrate_panel)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
