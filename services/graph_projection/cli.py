"""Graph projection command line interface."""

import argparse
from uuid import UUID

from services.common.cli import print_json
from services.common.database import get_db

from .kernel import PROJECTION_KEY, PROJECTION_VERSION, rebuild, validate_generation
from .query import EDGE_TYPES, MAX_DEPTH, MAX_NODES, query_graph


def main(argv=None):
    parser = argparse.ArgumentParser(description="Governed graph projection")
    sub = parser.add_subparsers(dest="command", required=True)
    rebuild_parser = sub.add_parser("rebuild")
    rebuild_parser.add_argument("--actor", required=True)
    sub.add_parser("status")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--generation-id")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("--entity-key", required=True)
    query_parser.add_argument("--depth", type=int, default=1)
    query_parser.add_argument("--node-cap", type=int, default=100)
    query_parser.add_argument("--edge-type", action="append", choices=sorted(EDGE_TYPES))
    query_parser.add_argument("--location-id")
    query_parser.add_argument("--audience", choices=("internal", "public"), default="internal")
    args = parser.parse_args(argv)
    if args.command == "rebuild" and not args.actor.strip():
        parser.error("--actor must not be blank")
    if args.command == "validate" and args.generation_id is not None:
        try:
            args.generation_id = str(UUID(args.generation_id))
        except (AttributeError, TypeError, ValueError):
            parser.error("--generation-id must be a valid UUID")
    if args.command == "query":
        if not args.entity_key:
            parser.error("--entity-key must not be empty")
        if not 0 <= args.depth <= MAX_DEPTH:
            parser.error(f"--depth must be between 0 and {MAX_DEPTH}")
        if not 1 <= args.node_cap <= MAX_NODES:
            parser.error(f"--node-cap must be between 1 and {MAX_NODES}")
        if args.location_id is not None:
            try:
                args.location_id = str(UUID(args.location_id))
            except (AttributeError, TypeError, ValueError):
                parser.error("--location-id must be a valid UUID")
    conn = get_db()
    try:
        if args.command == "rebuild":
            result = rebuild(conn, args.actor)
        elif args.command == "validate":
            result = validate_generation(conn, args.generation_id)
        elif args.command == "query":
            result = query_graph(
                conn, args.entity_key, args.depth, args.node_cap, args.edge_type, args.location_id, args.audience
            )
        else:
            cur = conn.cursor()
            cur.execute(
                """SELECT p.projection_key, p.projection_version, p.active_generation_id, g.status, g.source_cutoff, g.node_count, g.edge_count, g.content_hash FROM graph_projection p LEFT JOIN graph_projection_generation g ON g.id = p.active_generation_id WHERE p.projection_key = %s AND p.projection_version = %s""",
                (PROJECTION_KEY, PROJECTION_VERSION),
            )
            row = cur.fetchone()
            columns = [column[0] for column in cur.description]
            result = (
                dict(zip(columns, row))
                if row
                else {"projection_key": PROJECTION_KEY, "projection_version": PROJECTION_VERSION, "status": "missing"}
            )
            cur.close()
        print_json(result)
    finally:
        conn.close()
