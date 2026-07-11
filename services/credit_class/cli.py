"""CLI for credit class and batch operations."""

from __future__ import annotations

import argparse
import json
import sys

from services.common.database import get_connection


def cmd_class_create(args):
    with get_connection() as conn:
        from services.credit_class.class_manager import create_class
        result = create_class(
            conn, name=args.name, methodology=args.methodology, credit_type=args.type,
            description=args.description,
        )
        print(json.dumps(result, indent=2, default=str))


def cmd_class_list(args):
    with get_connection() as conn:
        from services.credit_class.class_manager import list_classes
        classes = list_classes(conn, credit_type=args.type, status=args.status)
        for c in classes:
            print(f"  [{c['status']}] {c['name']} ({c['credit_type']}) — {c['methodology']}")
        print(f"\n{len(classes)} classes")


def cmd_batch_create(args):
    with get_connection() as conn:
        from services.credit_class.batch_manager import create_batch
        result = create_batch(
            conn, credit_class_id=args.class_id, location_id=args.location_id,
            vintage_year=args.vintage, total_quantity=args.quantity,
        )
        print(json.dumps(result, indent=2, default=str))


def cmd_batch_issue(args):
    with get_connection() as conn:
        from services.credit_class.batch_manager import issue_batch
        result = issue_batch(conn, args.batch_id)
        print(json.dumps(result, indent=2, default=str))


def cmd_batch_balance(args):
    with get_connection() as conn:
        from services.credit_class.batch_manager import get_batch_balance
        result = get_batch_balance(conn, args.batch_id)
        print(json.dumps(result, indent=2, default=str))


def cmd_batch_list(args):
    with get_connection() as conn:
        from services.credit_class.batch_manager import list_batches
        batches = list_batches(conn, credit_class_id=args.class_id, location_id=args.location_id)
        for b in batches:
            print(f"  [{b['status']}] {b['batch_code']} — {b['total_quantity']} {b['unit']}")
        print(f"\n{len(batches)} batches")


def main():
    parser = argparse.ArgumentParser(description="Credit Class / Batch CLI")
    sub = parser.add_subparsers(dest="command")

    p_cc = sub.add_parser("class", help="Credit class operations")
    cc_sub = p_cc.add_subparsers(dest="subcommand")

    p_cc_create = cc_sub.add_parser("create", help="Create a credit class")
    p_cc_create.add_argument("--name", required=True)
    p_cc_create.add_argument("--methodology", required=True)
    p_cc_create.add_argument("--type", required=True, choices=["carbon", "biodiversity", "water", "soil", "mixed"])
    p_cc_create.add_argument("--description", default=None)
    p_cc_create.set_defaults(func=cmd_class_create)

    p_cc_list = cc_sub.add_parser("list", help="List credit classes")
    p_cc_list.add_argument("--type", default=None)
    p_cc_list.add_argument("--status", default=None)
    p_cc_list.set_defaults(func=cmd_class_list)

    p_cb = sub.add_parser("batch", help="Credit batch operations")
    cb_sub = p_cb.add_subparsers(dest="subcommand")

    p_cb_create = cb_sub.add_parser("create", help="Create a credit batch")
    p_cb_create.add_argument("--class-id", required=True)
    p_cb_create.add_argument("--location-id", required=True)
    p_cb_create.add_argument("--vintage", type=int, required=True)
    p_cb_create.add_argument("--quantity", type=float, required=True)
    p_cb_create.set_defaults(func=cmd_batch_create)

    p_cb_issue = cb_sub.add_parser("issue", help="Issue a credit batch")
    p_cb_issue.add_argument("--batch-id", required=True)
    p_cb_issue.set_defaults(func=cmd_batch_issue)

    p_cb_balance = cb_sub.add_parser("balance", help="Check batch balance")
    p_cb_balance.add_argument("--batch-id", required=True)
    p_cb_balance.set_defaults(func=cmd_batch_balance)

    p_cb_list = cb_sub.add_parser("list", help="List credit batches")
    p_cb_list.add_argument("--class-id", default=None)
    p_cb_list.add_argument("--location-id", default=None)
    p_cb_list.set_defaults(func=cmd_batch_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
