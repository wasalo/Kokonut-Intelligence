"""CLI for the Real-time Delphi service."""

from __future__ import annotations

import argparse
import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def _get_conn():
    from services.common.database import get_db
    return get_db()


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def cmd_create_study(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    criteria = json.loads(args.criteria) if args.criteria else None
    study = f.create_study(
        title=args.title,
        description=args.description,
        location_id=args.location_id,
        variation=args.variation,
        facilitator_type=args.facilitator_type,
        stopping_criteria=criteria,
        created_by=args.created_by,
    )
    print(_json(study))


def cmd_open_study(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    print(_json(f.open_study(args.study_id)))


def cmd_close_study(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    print(_json(f.close_study(args.study_id)))


def cmd_add_panel(args):
    from services.delphi.panel import PanelManager
    pm = PanelManager(conn=_get_conn())
    member = pm.add_member(
        study_id=args.study_id,
        participant_ref_type=args.ref_type,
        participant_ref_id=args.ref_id,
        role=args.role,
        display_token=args.token,
        is_anonymous=not args.public,
        expert_weight=args.weight,
    )
    print(_json(member))


def cmd_list_panel(args):
    from services.delphi.panel import PanelManager
    pm = PanelManager(conn=_get_conn())
    print(_json(pm.list_members(args.study_id)))


def cmd_add_item(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    item = f.add_item(
        study_id=args.study_id,
        label=args.label,
        item_type=args.type,
        scale=args.scale,
        description=args.description,
        min_value=args.min_value,
        max_value=args.max_value,
        target_entity_type=args.target_type,
        target_entity_id=args.target_id,
    )
    print(_json(item))


def cmd_submit(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    result = f.submit_contribution(
        study_id=args.study_id,
        item_id=args.item_id,
        panel_member_id=args.member_id,
        score=args.score,
        reasoning=args.reasoning,
    )
    print(_json(result))


def cmd_live_summary(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    print(_json(f.get_live_summary(args.study_id)))


def cmd_consensus(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    study = f.get_study(args.study_id)
    # Return current consensus snapshots via live summary items
    summary = f.get_live_summary(args.study_id)
    print(_json({"study_id": args.study_id, "items": summary["items"]}))


def cmd_check_stopping(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    print(_json(f.check_stopping(args.study_id)))


def cmd_draft_recommendation(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    rec = f.draft_recommendation(
        study_id=args.study_id,
        recommendation_text=args.text,
        summary=args.summary,
        created_by=args.created_by,
    )
    print(_json(rec))


def cmd_approve_recommendation(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    rec = f.approve_recommendation(args.recommendation_id, args.approved_by)
    print(_json(rec))


def cmd_list_recommendations(args):
    from services.delphi.facilitator import Facilitator
    f = Facilitator(conn=_get_conn())
    print(_json(f.list_recommendations(args.study_id)))


def cmd_list_studies(args):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM delphi_study ORDER BY created_at DESC LIMIT 50")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    for row in rows:
        print(_json(dict(zip(cols, row))))


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
    p.set_defaults(func=cmd_live_summary)

    p = sub.add_parser("consensus", help="Current consensus snapshots")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_consensus)

    p = sub.add_parser("check-stopping", help="Evaluate stopping criteria")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_check_stopping)

    # Recommendations
    p = sub.add_parser("draft-recommendation", help="Draft a recommendation (agent)")
    p.add_argument("--study-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--summary")
    p.add_argument("--created-by")
    p.set_defaults(func=cmd_draft_recommendation)

    p = sub.add_parser("approve-recommendation", help="Approve a recommendation (human)")
    p.add_argument("--recommendation-id", required=True)
    p.add_argument("--approved-by", required=True)
    p.set_defaults(func=cmd_approve_recommendation)

    p = sub.add_parser("list-recommendations", help="List recommendations")
    p.add_argument("--study-id", required=True)
    p.set_defaults(func=cmd_list_recommendations)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
