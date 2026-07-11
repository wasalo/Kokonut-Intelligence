"""RDF CLI: build, query, serialize."""

from __future__ import annotations

import argparse
import json
import sys

from services.common.database import get_connection


def cmd_build(args):
    with get_connection() as conn:
        from services.rdf.graph_builder import persist_graph
        count = persist_graph(conn, args.location_id)
        print(f"Built {count} triples for location {args.location_id}")


def cmd_query(args):
    with get_connection() as conn:
        from services.rdf.triple_store import query_triples
        results = query_triples(conn, subject=args.subject, predicate=args.predicate, graph_name=args.graph)
        for r in results:
            obj = r.get("object_iri") or r.get("object_value", "")
            print(f"  <{r['subject']}> <{r['predicate']}> {obj}")
        print(f"\n{len(results)} triples")


def cmd_serialize(args):
    with get_connection() as conn:
        from services.rdf.triple_store import query_triples
        triples = query_triples(conn, graph_name=args.graph)
        if args.format == "turtle":
            from services.rdf.serializers import to_turtle
            print(to_turtle(triples))
        elif args.format == "ntriples":
            from services.rdf.serializers import to_ntriples
            print(to_ntriples(triples))
        elif args.format == "jsonld":
            from services.rdf.serializers import to_jsonld
            print(json.dumps(to_jsonld(triples), indent=2))
        else:
            print(f"Unknown format: {args.format}")
            sys.exit(1)


def cmd_count(args):
    with get_connection() as conn:
        from services.rdf.triple_store import count_triples
        count = count_triples(conn, graph_name=args.graph)
        print(f"{count} triples" + (f" in graph '{args.graph}'" if args.graph else ""))


def cmd_list_graphs(args):
    with get_connection() as conn:
        from services.rdf.sparql_engine import list_named_graphs
        graphs = list_named_graphs(conn)
        for g in graphs:
            print(f"  {g['name']}: {g['triple_count']} triples (built: {g.get('last_built_at', 'never')})")
        print(f"\n{len(graphs)} named graphs")


def main():
    parser = argparse.ArgumentParser(description="RDF CLI")
    sub = parser.add_subparsers(dest="command")

    p_build = sub.add_parser("build", help="Build RDF graph for a location")
    p_build.add_argument("--location-id", required=True)
    p_build.set_defaults(func=cmd_build)

    p_query = sub.add_parser("query", help="Query triples")
    p_query.add_argument("--subject", default=None)
    p_query.add_argument("--predicate", default=None)
    p_query.add_argument("--graph", default=None)
    p_query.set_defaults(func=cmd_query)

    p_ser = sub.add_parser("serialize", help="Serialize graph")
    p_ser.add_argument("--format", choices=["turtle", "ntriples", "jsonld"], default="turtle")
    p_ser.add_argument("--graph", required=True)
    p_ser.set_defaults(func=cmd_serialize)

    p_count = sub.add_parser("count", help="Count triples")
    p_count.add_argument("--graph", default=None)
    p_count.set_defaults(func=cmd_count)

    p_graphs = sub.add_parser("list-graphs", help="List named graphs")
    p_graphs.set_defaults(func=cmd_list_graphs)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
