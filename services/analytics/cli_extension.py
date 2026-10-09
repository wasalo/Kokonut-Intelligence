"""Digital extension services (modules, enrollment, delivery) CLI.

Extracted from services.analytics.extension so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_extension --help
"""

import argparse

from ..common.cli import print_json
from .extension import (
    add_peer_member,
    create_module,
    create_peer_group,
    deliver_content,
    enroll_farmer,
    get_delivery_stats,
    get_extension_effectiveness,
    get_farmer_progress,
    get_module_stats,
    get_peer_groups,
    list_modules,
    recommend_modules,
    record_assessment,
    update_progress,
)

# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Digital extension services")
    sub = parser.add_subparsers(dest="command")

    # create-module
    cm = sub.add_parser("create-module", help="Create training module")
    cm.add_argument("--title", required=True)
    cm.add_argument("--category", required=True)
    cm.add_argument("--content-type", required=True, dest="content_type")
    cm.add_argument("--content-url", dest="content_url")
    cm.add_argument("--duration", type=int, dest="duration_min")
    cm.add_argument("--difficulty", default="beginner")
    cm.add_argument("--description")
    cm.add_argument("--language", default="en")
    cm.add_argument("--tags", nargs="*")
    cm.add_argument("--prerequisites", nargs="*")
    cm.add_argument("--json", action="store_true")

    # list-modules
    lm = sub.add_parser("list-modules", help="List training modules")
    lm.add_argument("--category")
    lm.add_argument("--difficulty")
    lm.add_argument("--content-type", dest="content_type")
    lm.add_argument("--status", default="active")
    lm.add_argument("--json", action="store_true")

    # enroll
    en = sub.add_parser("enroll", help="Enroll farmer in module")
    en.add_argument("--farmer-id", required=True)
    en.add_argument("--module-id", required=True)
    en.add_argument("--location-id")
    en.add_argument("--json", action="store_true")

    # update-progress
    up = sub.add_parser("update-progress", help="Update learning progress")
    up.add_argument("--progress-id", required=True)
    up.add_argument("--status")
    up.add_argument("--score", type=float)
    up.add_argument("--progress-pct", type=float)
    up.add_argument("--time-spent", type=int, dest="time_spent_min")
    up.add_argument("--json", action="store_true")

    # farmer-progress
    fp = sub.add_parser("farmer-progress", help="Get farmer progress")
    fp.add_argument("--farmer-id", required=True)
    fp.add_argument("--json", action="store_true")

    # module-stats
    ms = sub.add_parser("module-stats", help="Module completion stats")
    ms.add_argument("--module-id", required=True)
    ms.add_argument("--json", action="store_true")

    # create-peer-group
    cpg = sub.add_parser("create-peer-group", help="Create peer learning group")
    cpg.add_argument("--name", required=True)
    cpg.add_argument("--topic", required=True)
    cpg.add_argument("--location-id")
    cpg.add_argument("--network-type", default="learning_group")
    cpg.add_argument("--description")
    cpg.add_argument("--max-members", type=int)
    cpg.add_argument("--meeting-cadence")
    cpg.add_argument("--json", action="store_true")

    # add-peer-member
    apm = sub.add_parser("add-peer-member", help="Add member to peer group")
    apm.add_argument("--group-id", required=True)
    apm.add_argument("--farmer-id", required=True)
    apm.add_argument("--role", default="member")
    apm.add_argument("--json", action="store_true")

    # peer-groups
    pg = sub.add_parser("peer-groups", help="List peer groups")
    pg.add_argument("--location-id")
    pg.add_argument("--json", action="store_true")

    # deliver
    dl = sub.add_parser("deliver", help="Track content delivery")
    dl.add_argument("--farmer-id", required=True)
    dl.add_argument("--module-id", required=True)
    dl.add_argument("--channel", required=True)
    dl.add_argument("--location-id")
    dl.add_argument("--device-type")
    dl.add_argument("--network-type")
    dl.add_argument("--bandwidth", type=int, dest="bandwidth_kbps")
    dl.add_argument("--json", action="store_true")

    # delivery-stats
    ds = sub.add_parser("delivery-stats", help="Content delivery stats")
    ds.add_argument("--farmer-id", required=True)
    ds.add_argument("--json", action="store_true")

    # record-assessment
    ra = sub.add_parser("record-assessment", help="Record skill assessment")
    ra.add_argument("--farmer-id", required=True)
    ra.add_argument("--module-id", required=True)
    ra.add_argument("--type", required=True, dest="assessment_type")
    ra.add_argument("--score", type=float, required=True)
    ra.add_argument("--max-score", type=float, default=100)
    ra.add_argument("--questions-total", type=int)
    ra.add_argument("--questions-correct", type=int)
    ra.add_argument("--time-spent", type=int, dest="time_spent_min")
    ra.add_argument("--assessor")
    ra.add_argument("--notes")
    ra.add_argument("--json", action="store_true")

    # effectiveness
    ef = sub.add_parser("effectiveness", help="Training effectiveness")
    ef.add_argument("--location-id", required=True)
    ef.add_argument("--json", action="store_true")

    # recommend
    rc = sub.add_parser("recommend", help="Recommend modules")
    rc.add_argument("--farmer-id", required=True)
    rc.add_argument("--location-id", required=True)
    rc.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from ..ingestion.base import get_db

    if args.command is None:
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "create-module":
            result = create_module(
                db, args.title, args.category, args.content_type,
                content_url=args.content_url, duration_min=args.duration_min,
                difficulty=args.difficulty, description=args.description,
                language=args.language, tags=args.tags,
                prerequisites=args.prerequisites,
            )
        elif args.command == "list-modules":
            result = list_modules(
                db, category=args.category, difficulty=args.difficulty,
                content_type=args.content_type, status=args.status,
            )
        elif args.command == "enroll":
            result = enroll_farmer(
                db, args.farmer_id, args.module_id, location_id=args.location_id,
            )
        elif args.command == "update-progress":
            result = update_progress(
                db, args.progress_id, status=args.status, score=args.score,
                progress_pct=args.progress_pct, time_spent_min=args.time_spent_min,
            )
        elif args.command == "farmer-progress":
            result = get_farmer_progress(db, args.farmer_id)
        elif args.command == "module-stats":
            result = get_module_stats(db, args.module_id)
        elif args.command == "create-peer-group":
            result = create_peer_group(
                db, args.name, args.topic, location_id=args.location_id,
                network_type=args.network_type, description=args.description,
                max_members=args.max_members, meeting_cadence=args.meeting_cadence,
            )
        elif args.command == "add-peer-member":
            result = add_peer_member(
                db, args.group_id, args.farmer_id, role=args.role,
            )
        elif args.command == "peer-groups":
            result = get_peer_groups(db, location_id=args.location_id)
        elif args.command == "deliver":
            result = deliver_content(
                db, args.farmer_id, args.module_id, args.channel,
                location_id=args.location_id, device_type=args.device_type,
                network_type=args.network_type, bandwidth_kbps=args.bandwidth_kbps,
            )
        elif args.command == "delivery-stats":
            result = get_delivery_stats(db, args.farmer_id)
        elif args.command == "record-assessment":
            result = record_assessment(
                db, args.farmer_id, args.module_id, args.assessment_type,
                args.score, max_score=args.max_score,
                questions_total=args.questions_total,
                questions_correct=args.questions_correct,
                time_spent_min=args.time_spent_min,
                assessor_name=args.assessor, notes=args.notes,
            )
        elif args.command == "effectiveness":
            result = get_extension_effectiveness(db, args.location_id)
        elif args.command == "recommend":
            result = recommend_modules(db, args.farmer_id, args.location_id)

        print_json(result)

    finally:
        db.close()


if __name__ == "__main__":
    main()

