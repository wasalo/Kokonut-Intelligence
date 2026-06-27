"""CLI for EBF scorecard export helpers."""

from __future__ import annotations

import argparse
import json

from .export import dumps_export, export_internal_scorecard, export_public_scorecard, get_connection
from .trust_graph import export_trust_graph, trust_graph_to_mermaid


def main() -> None:
    parser = argparse.ArgumentParser(description="EBF scorecard helpers")
    parser.add_argument("--scorecard-id", help="EBF scorecard UUID")
    parser.add_argument("--export", choices=["public", "internal"], help="Export scorecard JSON")
    parser.add_argument("--trust-graph", help="Reference UUID for trust graph export")
    parser.add_argument("--public-safe", action="store_true", help="Restrict trust graph to public-safe nodes and edges")
    parser.add_argument("--mermaid", action="store_true", help="Render trust graph as Mermaid text")
    args = parser.parse_args()

    if args.export:
        if not args.scorecard_id:
            parser.error("--export requires --scorecard-id")
        conn = get_connection()
        try:
            document = export_public_scorecard(conn, args.scorecard_id) if args.export == "public" else export_internal_scorecard(conn, args.scorecard_id)
            print(dumps_export(document))
        finally:
            conn.close()
        return

    if args.trust_graph:
        conn = get_connection()
        try:
            graph = export_trust_graph(conn, args.trust_graph, public_safe=args.public_safe)
            print(trust_graph_to_mermaid(graph) if args.mermaid else json.dumps(graph, indent=2, default=str))
        finally:
            conn.close()
        return

    parser.print_help()
