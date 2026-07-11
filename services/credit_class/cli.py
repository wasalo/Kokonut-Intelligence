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


def _print_json(fn):
    with get_connection() as conn:
        result = fn(conn)
        print(json.dumps(result, indent=2, default=str))


def _print_list(label, fn):
    with get_connection() as conn:
        items = fn(conn)
        for item in items:
            name = item.get("name") or item.get("denom") or item.get("address") or item.get("abbreviation", "")
            print(f"  {name}")
        print(f"\n{len(items)} {label}s")


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

    # --- credit-type ---
    p_ct = sub.add_parser("credit-type", help="Credit type operations")
    ct_sub = p_ct.add_subparsers(dest="subcommand")

    p_ct_list = ct_sub.add_parser("list", help="List credit types")
    p_ct_list.set_defaults(func=lambda args: _print_list("credit_type", lambda conn: __import__("services.credit_class.entities", fromlist=["list_credit_types"]).list_credit_types(conn)))

    # --- issuer ---
    p_iss = sub.add_parser("issuer", help="Credit class issuer operations")
    iss_sub = p_iss.add_subparsers(dest="subcommand")

    p_iss_add = iss_sub.add_parser("add", help="Add an issuer")
    p_iss_add.add_argument("--class-id", required=True)
    p_iss_add.add_argument("--address", required=True)
    p_iss_add.add_argument("--name", default=None)
    p_iss_add.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.entities", fromlist=["add_issuer"]).add_issuer(conn, args.class_id, args.address, args.name)))

    p_iss_list = iss_sub.add_parser("list", help="List issuers")
    p_iss_list.add_argument("--class-id", required=True)
    p_iss_list.set_defaults(func=lambda args: _print_list("issuer", lambda conn: __import__("services.credit_class.entities", fromlist=["list_issuers"]).list_issuers(conn, args.class_id)))

    # --- allowlist ---
    p_al = sub.add_parser("allowlist", help="Creator allowlist operations")
    al_sub = p_al.add_subparsers(dest="subcommand")

    p_al_add = al_sub.add_parser("add", help="Add to allowlist")
    p_al_add.add_argument("--address", required=True)
    p_al_add.add_argument("--name", default=None)
    p_al_add.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.entities", fromlist=["add_to_allowlist"]).add_to_allowlist(conn, args.address, args.name)))

    p_al_list = al_sub.add_parser("list", help="List allowlist")
    p_al_list.set_defaults(func=lambda args: _print_list("allowlist", lambda conn: __import__("services.credit_class.entities", fromlist=["list_allowlist"]).list_allowlist(conn)))

    # --- basket ---
    p_bsk = sub.add_parser("basket", help="Basket operations")
    bsk_sub = p_bsk.add_subparsers(dest="subcommand")

    p_bsk_create = bsk_sub.add_parser("create", help="Create a basket")
    p_bsk_create.add_argument("--name", required=True)
    p_bsk_create.add_argument("--denom", required=True)
    p_bsk_create.add_argument("--description", default=None)
    p_bsk_create.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.basket", fromlist=["create_basket"]).create_basket(conn, args.name, args.denom, args.description)))

    p_bsk_list = bsk_sub.add_parser("list", help="List baskets")
    p_bsk_list.set_defaults(func=lambda args: _print_list("basket", lambda conn: __import__("services.credit_class.basket", fromlist=["list_baskets"]).list_baskets(conn)))

    p_bsk_deposit = bsk_sub.add_parser("deposit", help="Deposit credits into basket")
    p_bsk_deposit.add_argument("--basket-id", required=True)
    p_bsk_deposit.add_argument("--batch-id", required=True)
    p_bsk_deposit.add_argument("--address", required=True)
    p_bsk_deposit.add_argument("--quantity", type=float, required=True)
    p_bsk_deposit.add_argument("--token-amount", type=float, required=True)
    p_bsk_deposit.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.basket", fromlist=["deposit_credits"]).deposit_credits(conn, args.basket_id, args.batch_id, args.address, args.quantity, args.token_amount)))

    p_bsk_balance = bsk_sub.add_parser("balance", help="Check basket token balance")
    p_bsk_balance.add_argument("--basket-id", required=True)
    p_bsk_balance.add_argument("--address", required=True)
    p_bsk_balance.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.basket", fromlist=["get_token_balance"]).get_token_balance(conn, args.basket_id, args.address)))

    # --- marketplace ---
    p_mkt = sub.add_parser("marketplace", help="Marketplace operations")
    mkt_sub = p_mkt.add_subparsers(dest="subcommand")

    p_mkt_sell = mkt_sub.add_parser("sell", help="Create sell order")
    p_mkt_sell.add_argument("--batch-id", required=True)
    p_mkt_sell.add_argument("--seller", required=True)
    p_mkt_sell.add_argument("--quantity", type=float, required=True)
    p_mkt_sell.add_argument("--price", type=float, required=True)
    p_mkt_sell.add_argument("--denom", required=True)
    p_mkt_sell.add_argument("--auto-retire", action="store_true")
    p_mkt_sell.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.marketplace", fromlist=["create_sell_order"]).create_sell_order(conn, args.batch_id, args.seller, args.quantity, args.price, args.denom, args.auto_retire)))

    p_mkt_buy = mkt_sub.add_parser("buy", help="Create buy order")
    p_mkt_buy.add_argument("--sell-order-id", required=True)
    p_mkt_buy.add_argument("--buyer", required=True)
    p_mkt_buy.add_argument("--quantity", type=float, required=True)
    p_mkt_buy.add_argument("--auto-retire", action="store_true")
    p_mkt_buy.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.marketplace", fromlist=["create_buy_order"]).create_buy_order(conn, args.sell_order_id, args.buyer, args.quantity, args.auto_retire)))

    p_mkt_execute = mkt_sub.add_parser("execute", help="Execute buy order")
    p_mkt_execute.add_argument("--buy-order-id", required=True)
    p_mkt_execute.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.marketplace", fromlist=["execute_buy_order"]).execute_buy_order(conn, args.buy_order_id)))

    p_mkt_denoms = mkt_sub.add_parser("denoms", help="List allowed denominations")
    p_mkt_denoms.set_defaults(func=lambda args: _print_list("denom", lambda conn: __import__("services.credit_class.marketplace", fromlist=["list_allowed_denoms"]).list_allowed_denoms(conn)))

    # --- balance ---
    p_bal = sub.add_parser("balance", help="Credit balance operations")
    bal_sub = p_bal.add_subparsers(dest="subcommand")

    p_bal_get = bal_sub.add_parser("get", help="Get balance for batch+account")
    p_bal_get.add_argument("--batch-id", required=True)
    p_bal_get.add_argument("--account", required=True)
    p_bal_get.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.balance", fromlist=["get_balance"]).get_balance(conn, args.batch_id, args.account)))

    p_bal_account = bal_sub.add_parser("account", help="Get all balances for account")
    p_bal_account.add_argument("--account", required=True)
    p_bal_account.set_defaults(func=lambda args: _print_list("balance", lambda conn: __import__("services.credit_class.balance", fromlist=["get_balances_for_account"]).get_balances_for_account(conn, args.account)))

    p_bal_batch = bal_sub.add_parser("batch", help="Get all balances for batch")
    p_bal_batch.add_argument("--batch-id", required=True)
    p_bal_batch.set_defaults(func=lambda args: _print_list("balance", lambda conn: __import__("services.credit_class.balance", fromlist=["get_balances_for_batch"]).get_balances_for_batch(conn, args.batch_id)))

    p_bal_all = bal_sub.add_parser("all", help="Get all balances")
    p_bal_all.set_defaults(func=lambda args: _print_list("balance", lambda conn: __import__("services.credit_class.balance", fromlist=["get_all_balances"]).get_all_balances(conn)))

    p_bal_supply = bal_sub.add_parser("supply", help="Get supply for batch")
    p_bal_supply.add_argument("--batch-id", required=True)
    p_bal_supply.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.balance", fromlist=["get_supply"]).get_supply(conn, args.batch_id)))

    # --- params ---
    p_params = sub.add_parser("params", help="Module parameters")
    params_sub = p_params.add_subparsers(dest="subcommand")

    p_params_list = params_sub.add_parser("list", help="List all parameters")
    p_params_list.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.params", fromlist=["get_params"]).get_params(conn)))

    p_params_get = params_sub.add_parser("get", help="Get a parameter")
    p_params_get.add_argument("--key", required=True)
    p_params_get.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.params", fromlist=["get_param"]).get_param(conn, args.key)))

    # --- enrollment ---
    p_enr = sub.add_parser("enrollment", help="Project enrollment operations")
    enr_sub = p_enr.add_subparsers(dest="subcommand")

    p_enr_apply = enr_sub.add_parser("apply", help="Apply to credit class")
    p_enr_apply.add_argument("--location-id", required=True)
    p_enr_apply.add_argument("--class-id", required=True)
    p_enr_apply.add_argument("--metadata", default=None)
    p_enr_apply.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.enrollment", fromlist=["apply_to_class"]).apply_to_class(conn, args.location_id, args.class_id, args.metadata)))

    p_enr_evaluate = enr_sub.add_parser("evaluate", help="Evaluate application")
    p_enr_evaluate.add_argument("--enrollment-id", required=True)
    p_enr_evaluate.add_argument("--issuer", required=True)
    p_enr_evaluate.add_argument("--status", required=True, choices=["accepted", "rejected", "changes_requested", "terminated"])
    p_enr_evaluate.add_argument("--metadata", default=None)
    p_enr_evaluate.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.enrollment", fromlist=["evaluate_application"]).evaluate_application(conn, args.enrollment_id, args.issuer, args.status, args.metadata)))

    p_enr_list_class = enr_sub.add_parser("list-by-class", help="List enrollments by class")
    p_enr_list_class.add_argument("--class-id", required=True)
    p_enr_list_class.set_defaults(func=lambda args: _print_list("enrollment", lambda conn: __import__("services.credit_class.enrollment", fromlist=["list_enrollments_by_class"]).list_enrollments_by_class(conn, args.class_id)))

    p_enr_list_project = enr_sub.add_parser("list-by-project", help="List enrollments by project")
    p_enr_list_project.add_argument("--location-id", required=True)
    p_enr_list_project.set_defaults(func=lambda args: _print_list("enrollment", lambda conn: __import__("services.credit_class.enrollment", fromlist=["list_enrollments_by_project"]).list_enrollments_by_project(conn, args.location_id)))

    # --- bridge ---
    p_br = sub.add_parser("bridge", help="Bridge operations")
    br_sub = p_br.add_subparsers(dest="subcommand")

    p_br_out = br_sub.add_parser("out", help="Bridge credits to another chain")
    p_br_out.add_argument("--batch-id", required=True)
    p_br_out.add_argument("--sender", required=True)
    p_br_out.add_argument("--target", required=True)
    p_br_out.add_argument("--recipient", required=True)
    p_br_out.add_argument("--quantity", type=float, required=True)
    p_br_out.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.bridge", fromlist=["create_bridge_outbound"]).create_bridge_outbound(conn, args.batch_id, args.sender, args.target, args.recipient, args.quantity)))

    p_br_in = br_sub.add_parser("in", help="Bridge credits from another chain")
    p_br_in.add_argument("--class-id", required=True)
    p_br_in.add_argument("--source", required=True)
    p_br_in.add_argument("--issuer", required=True)
    p_br_in.add_argument("--recipient", required=True)
    p_br_in.add_argument("--quantity", type=float, required=True)
    p_br_in.add_argument("--origin-tx-id", default=None)
    p_br_in.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.bridge", fromlist=["create_bridge_inbound"]).create_bridge_inbound(conn, args.class_id, args.source, args.issuer, args.recipient, args.quantity, args.origin_tx_id)))

    p_br_complete = br_sub.add_parser("complete", help="Complete bridge transaction")
    p_br_complete.add_argument("--bridge-tx-id", required=True)
    p_br_complete.add_argument("--bridge-tx-hash", default=None)
    p_br_complete.set_defaults(func=lambda args: _print_json(lambda conn: __import__("services.credit_class.bridge", fromlist=["complete_bridge"]).complete_bridge(conn, args.bridge_tx_id, args.bridge_tx_hash)))

    p_br_list = br_sub.add_parser("list", help="List bridge transactions")
    p_br_list.add_argument("--direction", default=None)
    p_br_list.add_argument("--status", default=None)
    p_br_list.set_defaults(func=lambda args: _print_list("bridge", lambda conn: __import__("services.credit_class.bridge", fromlist=["list_bridge_transactions"]).list_bridge_transactions(conn, args.direction, args.status)))

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
