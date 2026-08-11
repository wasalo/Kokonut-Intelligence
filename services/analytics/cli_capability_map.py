"""CLI for Business Architecture Capability Map."""

from __future__ import annotations

import argparse
import sys

from services.analytics.capability_map import (
    create_capability, get_capability, list_capabilities, update_capability,
    map_process, unmap_process, get_capability_processes,
    map_service, unmap_service, get_capability_services,
    record_maturity, get_maturity_history,
    get_capability_dashboard, get_coverage_analysis, get_hierarchy,
)
from services.common.cli import print_json


def _out(data):
    print_json(data)


def cmd_create(args):
    data = create_capability(
        args.name,
        description=args.description or "",
        capability_type=args.type,
        parent_id=args.parent,
        guild_key=args.guild,
        maturity_level=args.maturity,
        owner_role=args.owner,
    )
    _out(data)


def cmd_get(args):
    data = get_capability(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_list(args):
    data = list_capabilities(
        guild_key=args.guild,
        capability_type=args.type,
        status=args.status,
    )
    _out(data)


def cmd_update(args):
    fields = {}
    if args.name:
        fields["name"] = args.name
    if args.description:
        fields["description"] = args.description
    if args.maturity is not None:
        fields["maturity_level"] = args.maturity
    if args.status:
        fields["status"] = args.status
    data = update_capability(args.id, **fields)
    if not data:
        print("Not found or no changes", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_map_process(args):
    data = map_process(args.id, args.process_key, is_primary=not args.secondary)
    _out(data)


def cmd_unmap_process(args):
    ok = unmap_process(args.id, args.process_key)
    print("removed" if ok else "not found")


def cmd_processes(args):
    data = get_capability_processes(args.id)
    _out(data)


def cmd_map_service(args):
    data = map_service(args.id, args.service_name, is_primary=not args.secondary)
    _out(data)


def cmd_unmap_service(args):
    ok = unmap_service(args.id, args.service_name)
    print("removed" if ok else "not found")


def cmd_services(args):
    data = get_capability_services(args.id)
    _out(data)


def cmd_maturity(args):
    data = record_maturity(
        args.id, args.level,
        assessed_by=args.assessed_by,
        notes=args.notes,
    )
    _out(data)


def cmd_maturity_history(args):
    data = get_maturity_history(args.id)
    _out(data)


def cmd_dashboard(args):
    data = get_capability_dashboard(guild_key=args.guild)
    _out(data)


def cmd_coverage(args):
    data = get_coverage_analysis()
    _out(data)


def cmd_hierarchy(args):
    data = get_hierarchy()
    _out(data)


def build_parser(p):
    sub = p.add_subparsers(dest="ba_cmd")

    # create
    c = sub.add_parser("create", help="Create a capability")
    c.add_argument("name")
    c.add_argument("--description", default="")
    c.add_argument("--type", default="core", choices=["strategic", "core", "support"])
    c.add_argument("--parent", default=None)
    c.add_argument("--guild", default=None)
    c.add_argument("--maturity", type=int, default=None)
    c.add_argument("--owner", default=None)
    c.set_defaults(func=cmd_create)

    # get
    g = sub.add_parser("get", help="Get a capability")
    g.add_argument("id")
    g.set_defaults(func=cmd_get)

    # list
    l = sub.add_parser("list", help="List capabilities")
    l.add_argument("--guild", default=None)
    l.add_argument("--type", default=None, choices=["strategic", "core", "support"])
    l.add_argument("--status", default="active")
    l.set_defaults(func=cmd_list)

    # update
    u = sub.add_parser("update", help="Update a capability")
    u.add_argument("id")
    u.add_argument("--name", default=None)
    u.add_argument("--description", default=None)
    u.add_argument("--maturity", type=int, default=None)
    u.add_argument("--status", default=None)
    u.set_defaults(func=cmd_update)

    # map-process
    mp = sub.add_parser("map-process", help="Link capability to process")
    mp.add_argument("id")
    mp.add_argument("process_key")
    mp.add_argument("--secondary", action="store_true")
    mp.set_defaults(func=cmd_map_process)

    # unmap-process
    up = sub.add_parser("unmap-process", help="Remove capability-process link")
    up.add_argument("id")
    up.add_argument("process_key")
    up.set_defaults(func=cmd_unmap_process)

    # processes
    pr = sub.add_parser("processes", help="List processes for a capability")
    pr.add_argument("id")
    pr.set_defaults(func=cmd_processes)

    # map-service
    ms = sub.add_parser("map-service", help="Link capability to service")
    ms.add_argument("id")
    ms.add_argument("service_name")
    ms.add_argument("--secondary", action="store_true")
    ms.set_defaults(func=cmd_map_service)

    # unmap-service
    us = sub.add_parser("unmap-service", help="Remove capability-service link")
    us.add_argument("id")
    us.add_argument("service_name")
    us.set_defaults(func=cmd_unmap_service)

    # services
    sv = sub.add_parser("services", help="List services for a capability")
    sv.add_argument("id")
    sv.set_defaults(func=cmd_services)

    # maturity
    m = sub.add_parser("maturity", help="Record maturity assessment")
    m.add_argument("id")
    m.add_argument("level", type=int, choices=range(1, 6))
    m.add_argument("--assessed-by", default=None)
    m.add_argument("--notes", default=None)
    m.set_defaults(func=cmd_maturity)

    # maturity-history
    mh = sub.add_parser("maturity-history", help="Maturity assessment history")
    mh.add_argument("id")
    mh.set_defaults(func=cmd_maturity_history)

    # dashboard
    d = sub.add_parser("dashboard", help="Capability dashboard")
    d.add_argument("--guild", default=None)
    d.set_defaults(func=cmd_dashboard)

    # coverage
    cv = sub.add_parser("coverage", help="Coverage analysis")
    cv.set_defaults(func=cmd_coverage)

    # hierarchy
    h = sub.add_parser("hierarchy", help="Full capability hierarchy")
    h.set_defaults(func=cmd_hierarchy)


def main():
    parser = argparse.ArgumentParser(description="Business Architecture Capability Map CLI")
    build_parser(parser)
    args = parser.parse_args()
    if not hasattr(args, "ba_cmd"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
