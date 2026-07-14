"""Management CLI for work items and RACI responsibility assignments.

User-facing output uses print(); service modules use structured logging.
"""

from __future__ import annotations

import argparse
import json
import sys

from services.ingestion.base import get_db
from services.management import responsibility, workbench


def _dump(rows):
    if rows is None:
        print("null")
        return
    if isinstance(rows, dict):
        rows = [rows]
    print(json.dumps([dict(r) for r in rows], default=str, indent=2))


def _cmd_create(args):
    conn = get_db()
    try:
        row = workbench.create_work_item(
            conn,
            organization_id=args.org_id,
            title=args.title,
            created_by_type=args.created_by_type,
            created_by_id=args.created_by_id,
            description=args.description,
            priority=args.priority,
            assignee_type=args.assignee_type,
            assignee_id=args.assignee_id,
            location_id=args.location_id,
            parent_work_item_id=args.parent_id,
            due_at=args.due_at,
            sla_at=args.sla_at,
        )
        _dump(row)
    finally:
        conn.close()


def _cmd_list(args):
    conn = get_db()
    try:
        _dump(workbench.list_work_items(
            conn, args.org_id, status=args.status,
            assignee_type=args.assignee_type, assignee_id=args.assignee_id,
        ))
    finally:
        conn.close()


def _cmd_show(args):
    conn = get_db()
    try:
        _dump(workbench.get_work_item(conn, args.id))
    finally:
        conn.close()


def _cmd_assign(args):
    conn = get_db()
    try:
        _dump(workbench.assign(
            conn, args.id, args.assignee_type, args.assignee_id,
            args.actor_type, args.actor_id, note=args.note,
        ))
    finally:
        conn.close()


def _cmd_transition(args):
    conn = get_db()
    try:
        _dump(workbench.transition(
            conn, args.id, args.to_status, args.actor_type,
            args.actor_id, action=args.action, note=args.note,
        ))
    finally:
        conn.close()


def _cmd_sla(args):
    conn = get_db()
    try:
        result = workbench.check_sla(conn, organization_id=args.org_id)
        print(json.dumps({
            "overdue": [dict(r) for r in result["overdue"]],
            "breached": [dict(r) for r in result["breached"]],
        }, default=str, indent=2))
    finally:
        conn.close()


def _cmd_resp_assign(args):
    conn = get_db()
    try:
        _dump(responsibility.assign_responsibility(
            conn, args.entity_type, args.entity_id,
            args.party_type, args.party_id, args.role,
        ))
    finally:
        conn.close()


def _cmd_resp_list(args):
    conn = get_db()
    try:
        _dump(responsibility.list_responsibilities_for_entity(
            conn, args.entity_type, args.entity_id,
        ))
    finally:
        conn.close()


def _cmd_resp_party(args):
    conn = get_db()
    try:
        _dump(responsibility.list_entities_for_party(
            conn, args.party_type, args.party_id,
        ))
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="management", description="Kokonut management workbench")
    sub = parser.add_subparsers(dest="group", required=True)

    wi = sub.add_parser("work-item", help="work item operations")
    wi_sub = wi.add_subparsers(dest="action", required=True)

    p = wi_sub.add_parser("create")
    p.add_argument("--org-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--created-by-type", default="system")
    p.add_argument("--created-by-id")
    p.add_argument("--description")
    p.add_argument("--priority", default="medium")
    p.add_argument("--assignee-type")
    p.add_argument("--assignee-id")
    p.add_argument("--location-id")
    p.add_argument("--parent-id")
    p.add_argument("--due-at")
    p.add_argument("--sla-at")
    p.set_defaults(func=_cmd_create)

    p = wi_sub.add_parser("list")
    p.add_argument("--org-id", required=True)
    p.add_argument("--status")
    p.add_argument("--assignee-type")
    p.add_argument("--assignee-id")
    p.set_defaults(func=_cmd_list)

    p = wi_sub.add_parser("show")
    p.add_argument("--id", required=True)
    p.set_defaults(func=_cmd_show)

    p = wi_sub.add_parser("assign")
    p.add_argument("--id", required=True)
    p.add_argument("--assignee-type", required=True)
    p.add_argument("--assignee-id", required=True)
    p.add_argument("--actor-type", default="manager")
    p.add_argument("--actor-id")
    p.add_argument("--note")
    p.set_defaults(func=_cmd_assign)

    p = wi_sub.add_parser("transition")
    p.add_argument("--id", required=True)
    p.add_argument("--to-status", required=True)
    p.add_argument("--actor-type", default="worker")
    p.add_argument("--actor-id")
    p.add_argument("--action")
    p.add_argument("--note")
    p.set_defaults(func=_cmd_transition)

    p = wi_sub.add_parser("sla")
    p.add_argument("--org-id")
    p.set_defaults(func=_cmd_sla)

    rp = sub.add_parser("responsibility", help="RACI responsibility operations")
    rp_sub = rp.add_subparsers(dest="action", required=True)

    p = rp_sub.add_parser("assign")
    p.add_argument("--entity-type", required=True)
    p.add_argument("--entity-id", required=True)
    p.add_argument("--party-type", required=True)
    p.add_argument("--party-id", required=True)
    p.add_argument("--role", required=True)
    p.set_defaults(func=_cmd_resp_assign)

    p = rp_sub.add_parser("list")
    p.add_argument("--entity-type", required=True)
    p.add_argument("--entity-id", required=True)
    p.set_defaults(func=_cmd_resp_list)

    p = rp_sub.add_parser("list-party")
    p.add_argument("--party-type", required=True)
    p.add_argument("--party-id", required=True)
    p.set_defaults(func=_cmd_resp_party)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
