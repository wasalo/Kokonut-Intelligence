"""CLI for Data Module v2 operations."""

from __future__ import annotations

import argparse
import sys

from services.common.database import get_connection
from services.common.cli import print_json

def cmd_hash(args):
    with get_connection() as conn:
        from services.data_module.content_hash import compute_content_hash
        result = compute_content_hash(args.data, algorithm=args.algorithm, content_type=args.type)
        print_json(result)


def cmd_create_hash(args):
    with get_connection() as conn:
        from services.data_module.content_hash import create_content_hash
        result = create_content_hash(
            conn, iri_id=args.iri_id, hash_value=args.hash,
            hash_algorithm=args.algorithm, content_type=args.type,
            media_type=args.media_type,
        )
        print_json(result)


def cmd_find_by_hash(args):
    with get_connection() as conn:
        from services.data_module.content_hash import find_iri_by_content_hash
        results = find_iri_by_content_hash(conn, args.hash)
        for r in results:
            print(f"  {r['iri']} ({r['entity_type']}) — {r['hash_algorithm']}")
        print(f"\n{len(results)} results")


def cmd_define_resolver(args):
    with get_connection() as conn:
        from services.data_module.resolver import define_resolver
        result = define_resolver(conn, args.url, args.manager, args.description)
        print_json(result)


def cmd_register_data(args):
    with get_connection() as conn:
        from services.data_module.resolver import register_data_to_resolver
        result = register_data_to_resolver(conn, args.resolver_id, args.iri_id)
        print_json(result)


def cmd_resolvers_for_iri(args):
    with get_connection() as conn:
        from services.data_module.resolver import get_resolvers_for_iri
        resolvers = get_resolvers_for_iri(conn, args.iri_id)
        for r in resolvers:
            print(f"  {r['resolver_url']} (manager: {r['manager_address']})")
        print(f"\n{len(resolvers)} resolvers")


def cmd_attest(args):
    with get_connection() as conn:
        from services.data_module.attestor import attest_to_iri
        result = attest_to_iri(conn, args.iri_id, args.attestor)
        print_json(result)


def cmd_attestors(args):
    with get_connection() as conn:
        from services.data_module.attestor import get_attestors_for_iri
        attestors = get_attestors_for_iri(conn, args.iri_id)
        for a in attestors:
            print(f"  {a['attestor_address']} @ {a['attested_at']}")
        print(f"\n{len(attestors)} attestors")


def main():
    parser = argparse.ArgumentParser(description="Data Module v2 CLI")
    sub = parser.add_subparsers(dest="command")

    # --- hash ---
    p_hash = sub.add_parser("hash", help="Compute content hash")
    p_hash.add_argument("--data", required=True, help="Data to hash")
    p_hash.add_argument("--algorithm", default="sha256", choices=["sha256", "blake2b256", "sha512"])
    p_hash.add_argument("--type", default="raw", choices=["raw", "graph"])
    p_hash.set_defaults(func=cmd_hash)

    p_ch = sub.add_parser("content-hash", help="Content hash operations")
    ch_sub = p_ch.add_subparsers(dest="subcommand")

    p_ch_create = ch_sub.add_parser("create", help="Create content hash entry")
    p_ch_create.add_argument("--iri-id", required=True)
    p_ch_create.add_argument("--hash", required=True)
    p_ch_create.add_argument("--algorithm", default="sha256")
    p_ch_create.add_argument("--type", default="raw")
    p_ch_create.add_argument("--media-type", default=None)
    p_ch_create.set_defaults(func=cmd_create_hash)

    p_ch_find = ch_sub.add_parser("find", help="Find IRI by content hash")
    p_ch_find.add_argument("--hash", required=True)
    p_ch_find.set_defaults(func=cmd_find_by_hash)

    # --- resolver ---
    p_res = sub.add_parser("resolver", help="Resolver operations")
    res_sub = p_res.add_subparsers(dest="subcommand")

    p_res_define = res_sub.add_parser("define", help="Define a resolver")
    p_res_define.add_argument("--url", required=True)
    p_res_define.add_argument("--manager", required=True)
    p_res_define.add_argument("--description", default=None)
    p_res_define.set_defaults(func=cmd_define_resolver)

    p_res_register = res_sub.add_parser("register", help="Register data to resolver")
    p_res_register.add_argument("--resolver-id", required=True)
    p_res_register.add_argument("--iri-id", required=True)
    p_res_register.set_defaults(func=cmd_register_data)

    p_res_for_iri = res_sub.add_parser("by-iri", help="Get resolvers for IRI")
    p_res_for_iri.add_argument("--iri-id", required=True)
    p_res_for_iri.set_defaults(func=cmd_resolvers_for_iri)

    # --- attest ---
    p_att = sub.add_parser("attest", help="IRI attestation operations")
    att_sub = p_att.add_subparsers(dest="subcommand")

    p_att_do = att_sub.add_parser("do", help="Attest to an IRI")
    p_att_do.add_argument("--iri-id", required=True)
    p_att_do.add_argument("--attestor", required=True)
    p_att_do.set_defaults(func=cmd_attest)

    p_att_list = att_sub.add_parser("list", help="List attestors for IRI")
    p_att_list.add_argument("--iri-id", required=True)
    p_att_list.set_defaults(func=cmd_attestors)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
