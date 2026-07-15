"""CLI for Vision, Mission & Values."""

from __future__ import annotations

import argparse
import json
import sys

from services.analytics.vision_mission import (
    create_statement, get_statement, list_statements,
    approve_statement, archive_statement, get_current_statements,
)


def _out(data):
    print(json.dumps(data, indent=2, default=str))


def cmd_create(args):
    data = create_statement(
        args.text,
        statement_type=args.type,
        entity_type=args.entity_type or "platform",
        entity_id=args.entity_id,
        effective_date=args.effective_date,
        review_date=args.review_date,
    )
    _out(data)


def cmd_get(args):
    data = get_statement(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_list(args):
    data = list_statements(
        entity_type=args.entity_type,
        statement_type=args.type,
        status=args.status,
    )
    _out(data)


def cmd_approve(args):
    data = approve_statement(args.id, approved_by=args.approved_by)
    if not data:
        print("Not found or not in draft status", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_archive(args):
    data = archive_statement(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_current(args):
    data = get_current_statements(entity_type=args.entity_type or "platform")
    _out(data)


def build_parser(p):
    sub = p.add_subparsers(dest="vm_cmd")

    c = sub.add_parser("create", help="Create statement")
    c.add_argument("text")
    c.add_argument("--type", required=True, choices=["vision", "mission", "values"])
    c.add_argument("--entity-type", default="platform")
    c.add_argument("--entity-id", default=None)
    c.add_argument("--effective-date", default=None)
    c.add_argument("--review-date", default=None)
    c.set_defaults(func=cmd_create)

    g = sub.add_parser("get", help="Get statement")
    g.add_argument("id")
    g.set_defaults(func=cmd_get)

    l = sub.add_parser("list", help="List statements")
    l.add_argument("--entity-type", default=None)
    l.add_argument("--type", default=None, choices=["vision", "mission", "values"])
    l.add_argument("--status", default=None)
    l.set_defaults(func=cmd_list)

    a = sub.add_parser("approve", help="Approve statement")
    a.add_argument("id")
    a.add_argument("--approved-by", required=True)
    a.set_defaults(func=cmd_approve)

    ar = sub.add_parser("archive", help="Archive statement")
    ar.add_argument("id")
    ar.set_defaults(func=cmd_archive)

    cu = sub.add_parser("current", help="Get current approved statements")
    cu.add_argument("--entity-type", default="platform")
    cu.set_defaults(func=cmd_current)


def main():
    parser = argparse.ArgumentParser(description="Vision, Mission & Values CLI")
    build_parser(parser)
    args = parser.parse_args()
    if not hasattr(args, "vm_cmd"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
