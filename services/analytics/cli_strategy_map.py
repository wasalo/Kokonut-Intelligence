"""CLI for Strategy Map (Balanced Scorecard)."""

from __future__ import annotations

import argparse
import sys

from services.analytics.strategy_map import (
    create_initiative,
    create_strategy_entry,
    get_execution_dashboard,
    get_initiative,
    get_perspective_summary,
    get_strategy_capabilities,
    get_strategy_entry,
    list_initiatives,
    list_strategy_entries,
    map_capability,
    update_initiative,
    update_strategy_entry,
)
from services.common.cli import print_json


def _out(data):
    print_json(data)


def cmd_create(args):
    data = create_strategy_entry(
        args.statement,
        perspective=args.perspective,
        entity_type=args.entity_type or "platform",
        entity_id=args.entity_id,
        strategic_theme=args.theme,
        target_value=args.target,
        current_value=args.current,
        unit=args.unit,
        weight=args.weight or 1.0,
    )
    _out(data)


def cmd_get(args):
    data = get_strategy_entry(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_list(args):
    data = list_strategy_entries(
        perspective=args.perspective,
        strategic_theme=args.theme,
        status=args.status,
    )
    _out(data)


def cmd_update(args):
    fields = {}
    if args.statement:
        fields["statement"] = args.statement
    if args.status:
        fields["status"] = args.status
    if args.target is not None:
        fields["target_value"] = args.target
    if args.current is not None:
        fields["current_value"] = args.current
    if args.theme:
        fields["strategic_theme"] = args.theme
    data = update_strategy_entry(args.id, **fields)
    if not data:
        print("Not found or no changes", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_create_initiative(args):
    data = create_initiative(
        args.strategy_id,
        args.name,
        description=args.description or "",
        owner=args.owner,
        start_date=args.start_date,
        target_date=args.target_date,
    )
    _out(data)


def cmd_map_capability(args):
    data = map_capability(
        args.strategy_id,
        args.capability_id,
        contribution_type=args.contribution_type,
        expected_impact=args.expected_impact,
    )
    _out(data)


def cmd_capabilities(args):
    _out(get_strategy_capabilities(args.strategy_id))


def cmd_get_initiative(args):
    data = get_initiative(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_list_initiatives(args):
    data = list_initiatives(
        strategy_map_id=args.strategy_id,
        owner=args.owner,
        status=args.status,
    )
    _out(data)


def cmd_update_initiative(args):
    fields = {}
    if args.name:
        fields["name"] = args.name
    if args.status:
        fields["status"] = args.status
    if args.completion_pct is not None:
        fields["completion_pct"] = args.completion_pct
    if args.owner:
        fields["owner"] = args.owner
    data = update_initiative(args.id, **fields)
    if not data:
        print("Not found or no changes", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_dashboard(args):
    data = get_execution_dashboard()
    _out(data)


def cmd_perspective_summary(args):
    data = get_perspective_summary()
    _out(data)


def build_parser(p):
    sub = p.add_subparsers(dest="sm_cmd")

    # create
    c = sub.add_parser("create", help="Create strategy entry")
    c.add_argument("statement")
    c.add_argument("--perspective", required=True,
                   choices=["financial", "customer", "internal_process", "learning_growth"])
    c.add_argument("--entity-type", default="platform")
    c.add_argument("--entity-id", default=None)
    c.add_argument("--theme", default=None)
    c.add_argument("--target", type=float, default=None)
    c.add_argument("--current", type=float, default=None)
    c.add_argument("--unit", default=None)
    c.add_argument("--weight", type=float, default=1.0)
    c.set_defaults(func=cmd_create)

    # get
    g = sub.add_parser("get", help="Get strategy entry")
    g.add_argument("id")
    g.set_defaults(func=cmd_get)

    # list
    l = sub.add_parser("list", help="List strategy entries")
    l.add_argument("--perspective", default=None)
    l.add_argument("--theme", default=None)
    l.add_argument("--status", default=None)
    l.set_defaults(func=cmd_list)

    # update
    u = sub.add_parser("update", help="Update strategy entry")
    u.add_argument("id")
    u.add_argument("--statement", default=None)
    u.add_argument("--status", default=None)
    u.add_argument("--target", type=float, default=None)
    u.add_argument("--current", type=float, default=None)
    u.add_argument("--theme", default=None)
    u.set_defaults(func=cmd_update)

    mc = sub.add_parser("map-capability", help="Link strategy to capability")
    mc.add_argument("strategy_id")
    mc.add_argument("capability_id")
    mc.add_argument("--contribution-type", default="primary", choices=["primary", "enabling"])
    mc.add_argument("--expected-impact", default=None)
    mc.set_defaults(func=cmd_map_capability)

    cs = sub.add_parser("capabilities", help="List capabilities for a strategy")
    cs.add_argument("strategy_id")
    cs.set_defaults(func=cmd_capabilities)

    # initiative create
    ic = sub.add_parser("initiative-create", help="Create initiative")
    ic.add_argument("strategy_id")
    ic.add_argument("name")
    ic.add_argument("--description", default="")
    ic.add_argument("--owner", default=None)
    ic.add_argument("--start-date", default=None)
    ic.add_argument("--target-date", default=None)
    ic.set_defaults(func=cmd_create_initiative)

    # initiative get
    ig = sub.add_parser("initiative-get", help="Get initiative")
    ig.add_argument("id")
    ig.set_defaults(func=cmd_get_initiative)

    # initiative list
    il = sub.add_parser("initiative-list", help="List initiatives")
    il.add_argument("--strategy-id", default=None)
    il.add_argument("--owner", default=None)
    il.add_argument("--status", default=None)
    il.set_defaults(func=cmd_list_initiatives)

    # initiative update
    iu = sub.add_parser("initiative-update", help="Update initiative")
    iu.add_argument("id")
    iu.add_argument("--name", default=None)
    iu.add_argument("--status", default=None)
    iu.add_argument("--completion-pct", type=float, default=None)
    iu.add_argument("--owner", default=None)
    iu.set_defaults(func=cmd_update_initiative)

    # dashboard
    d = sub.add_parser("dashboard", help="Execution dashboard")
    d.set_defaults(func=cmd_dashboard)

    # perspective-summary
    ps = sub.add_parser("perspective-summary", help="Summary by BSC perspective")
    ps.set_defaults(func=cmd_perspective_summary)


def main():
    parser = argparse.ArgumentParser(description="Strategy Map CLI")
    build_parser(parser)
    args = parser.parse_args()
    if not hasattr(args, "sm_cmd"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
