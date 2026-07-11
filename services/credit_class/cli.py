"""CLI for credit class, batch, and entity operations."""

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
            description=args.description, url=args.url,
        )
        print(json.dumps(result, indent=2, default=str))


def cmd_class_get(args):
    with get_connection() as conn:
        from services.credit_class.class_manager import get_class_full
        result = get_class_full(conn, args.class_id)
        if result:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Credit class not found: {args.class_id}")
            sys.exit(1)


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


def _entity_add(entity_name, add_fn):
    def handler(args):
        with get_connection() as conn:
            kwargs = {k: v for k, v in vars(args).items() if v is not None and k not in ("command", "subcommand", "entity_subcommand", "func")}
            result = add_fn(conn, **kwargs)
            print(json.dumps(result, indent=2, default=str))
    return handler


def _entity_list(entity_name, list_fn):
    def handler(args):
        with get_connection() as conn:
            items = list_fn(conn, args.class_id)
            for item in items:
                name = item.get("impact_name") or item.get("registry_name") or item.get("name")
                print(f"  {name}")
            print(f"\n{len(items)} {entity_name}s")
    return handler


def _entity_delete(entity_name, delete_fn):
    def handler(args):
        with get_connection() as conn:
            deleted = delete_fn(conn, args.entity_id)
            print(f"Deleted: {deleted}")
    return handler


def main():
    parser = argparse.ArgumentParser(description="Credit Class / Batch CLI")
    sub = parser.add_subparsers(dest="command")

    # --- class ---
    p_cc = sub.add_parser("class", help="Credit class operations")
    cc_sub = p_cc.add_subparsers(dest="subcommand")

    p_cc_create = cc_sub.add_parser("create", help="Create a credit class")
    p_cc_create.add_argument("--name", required=True)
    p_cc_create.add_argument("--methodology", required=True)
    p_cc_create.add_argument("--type", required=True, choices=["carbon", "biodiversity", "water", "soil", "mixed"])
    p_cc_create.add_argument("--description", default=None)
    p_cc_create.add_argument("--url", default=None)
    p_cc_create.set_defaults(func=cmd_class_create)

    p_cc_get = cc_sub.add_parser("get", help="Get credit class with all entities")
    p_cc_get.add_argument("--class-id", required=True)
    p_cc_get.set_defaults(func=cmd_class_get)

    p_cc_list = cc_sub.add_parser("list", help="List credit classes")
    p_cc_list.add_argument("--type", default=None)
    p_cc_list.add_argument("--status", default=None)
    p_cc_list.set_defaults(func=cmd_class_list)

    # --- batch ---
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

    # --- entity commands ---
    entities = [
        ("cobenefit", "add_cobenefit", ["credit_class_id", "impact_name"], {"impact_type": None, "sdg_numbers": None, "description": None}),
        ("registry", "add_registry", ["credit_class_id", "registry_name"], {"registry_url": None, "is_source": True}),
        ("program", "add_program", ["credit_class_id", "name"], {"url": None, "version": None, "identifier": None, "description": None}),
        ("protocol", "add_protocol", ["credit_class_id", "name"], {"url": None, "version": None, "identifier": None, "description": None, "is_primary": False}),
        ("methodology", "add_methodology", ["credit_class_id", "name"], {"url": None, "version": None, "identifier": None, "description": None, "is_approved": True}),
        ("buffer-pool", "add_buffer_pool", ["credit_class_id", "name"], {"wallet_address": None, "pool_allocation": None, "description": None}),
    ]

    for entity_name, add_fn_name, required_args, optional_args in entities:
        p_ent = sub.add_parser(entity_name, help=f"{entity_name.title()} operations")
        ent_sub = p_ent.add_subparsers(dest="subcommand")

        p_add = ent_sub.add_parser("add", help=f"Add a {entity_name}")
        for arg in required_args:
            p_add.add_argument(f"--{arg.replace('_', '-')}", required=True)
        for arg, default in optional_args.items():
            if arg == "sdg_numbers":
                p_add.add_argument(f"--{arg.replace('_', '-')}", nargs="*", type=int, default=None)
            elif isinstance(default, bool):
                p_add.add_argument(f"--{arg.replace('_', '-')}", action="store_true", default=default)
            else:
                p_add.add_argument(f"--{arg.replace('_', '-')}", default=default)
        p_add.set_defaults(func=_entity_add(entity_name, lambda conn, **kw: getattr(__import__("services.credit_class.entities", fromlist=[add_fn_name]), add_fn_name)(conn, **kw)))

        p_list = ent_sub.add_parser("list", help=f"List {entity_name}s")
        p_list.add_argument("--class-id", required=True)
        list_fn_name = f"list_{entity_name.replace('-', '_')}s" if entity_name != "buffer-pool" else "list_buffer_pools"
        p_list.set_defaults(func=_entity_list(entity_name, lambda conn, cid: getattr(__import__("services.credit_class.entities", fromlist=[list_fn_name]), list_fn_name)(conn, cid)))

        p_del = ent_sub.add_parser("delete", help=f"Delete a {entity_name}")
        p_del.add_argument("--entity-id", required=True)
        del_fn_name = f"delete_{entity_name.replace('-', '_')}"
        p_del.set_defaults(func=_entity_delete(entity_name, lambda conn, eid: getattr(__import__("services.credit_class.entities", fromlist=[del_fn_name]), del_fn_name)(conn, eid)))

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
