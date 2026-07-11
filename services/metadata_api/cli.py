"""CLI for Metadata Graph API."""

from __future__ import annotations

import argparse
import json
import sys

from services.common.database import get_connection


def cmd_resolve(args):
    with get_connection() as conn:
        from services.metadata_api.resolver import resolve_metadata_graph
        result = resolve_metadata_graph(conn, args.iri)
        if result:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"IRI not found: {args.iri}")
            sys.exit(1)


def cmd_generate(args):
    with get_connection() as conn:
        from services.metadata_api.resolver import generate_iri_from_metadata
        metadata = json.loads(args.metadata)
        iri = generate_iri_from_metadata(conn, metadata)
        print(json.dumps({"iri": iri}, indent=2))


def cmd_serve(args):
    import uvicorn
    from services.metadata_api.app import app
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def main():
    parser = argparse.ArgumentParser(description="Metadata Graph API CLI")
    sub = parser.add_subparsers(dest="command")

    p_resolve = sub.add_parser("resolve", help="Resolve an IRI")
    p_resolve.add_argument("--iri", required=True)
    p_resolve.set_defaults(func=cmd_resolve)

    p_gen = sub.add_parser("generate", help="Generate IRI from metadata")
    p_gen.add_argument("--metadata", required=True, help="JSON metadata")
    p_gen.set_defaults(func=cmd_generate)

    p_serve = sub.add_parser("serve", help="Start API server")
    p_serve.add_argument("--port", type=int, default=8099)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
