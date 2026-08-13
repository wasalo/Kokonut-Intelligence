"""CLI for IRI system operations."""

from __future__ import annotations

import argparse
import json
import sys

from services.common.database import get_connection
from services.common.cli import print_json

def cmd_generate(args):
    with get_connection() as conn:
        from services.iri.resolver import generate_iri
        content = json.loads(args.content) if args.content else None
        iri = generate_iri(conn, args.entity_type, args.entity_id, content=content)
        print_json({"iri": iri})


def cmd_resolve(args):
    with get_connection() as conn:
        from services.iri.resolver import resolve_metadata
        result = resolve_metadata(conn, args.iri)
        if result:
            print_json(result)
        else:
            print(f"IRI not found: {args.iri}")
            sys.exit(1)


def cmd_history(args):
    with get_connection() as conn:
        from services.iri.resolver import get_version_history
        versions = get_version_history(conn, args.entity_type, args.entity_id)
        for v in versions:
            current = " [CURRENT]" if v["is_current"] else ""
            print(f"  v{v['version']}: {v['iri']}{current}")
        print(f"\n{len(versions)} versions")


def cmd_anchor(args):
    with get_connection() as conn:
        from services.iri.resolver import anchor_iri
        result = anchor_iri(conn, args.iri, chain=args.chain)
        print_json(result)


def main():
    parser = argparse.ArgumentParser(description="IRI System CLI")
    sub = parser.add_subparsers(dest="command")

    p_gen = sub.add_parser("generate", help="Generate a new IRI")
    p_gen.add_argument("--entity-type", required=True)
    p_gen.add_argument("--entity-id", required=True)
    p_gen.add_argument("--content", default=None, help="JSON metadata")
    p_gen.set_defaults(func=cmd_generate)

    p_resolve = sub.add_parser("resolve", help="Resolve an IRI")
    p_resolve.add_argument("--iri", required=True)
    p_resolve.set_defaults(func=cmd_resolve)

    p_hist = sub.add_parser("history", help="Show version history")
    p_hist.add_argument("--entity-type", required=True)
    p_hist.add_argument("--entity-id", required=True)
    p_hist.set_defaults(func=cmd_history)

    p_anch = sub.add_parser("anchor", help="Anchor IRI on-chain")
    p_anch.add_argument("--iri", required=True)
    p_anch.add_argument("--chain", default="celo")
    p_anch.set_defaults(func=cmd_anchor)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
