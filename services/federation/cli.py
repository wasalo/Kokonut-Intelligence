"""CLI for federation protocol.

Usage:
    python3 -m services.federation --register --name NAME --url URL [--trust-level LEVEL]
    python3 -m services.federation --list-nodes
    python3 -m services.federation --share --node NAME --data-type TYPE --data '{}'
    python3 -m services.federation --query --type TYPE [--params '{}']
    python3 -m services.federation --shares [--data-type TYPE]
    python3 -m services.federation --queries [--status STATUS]
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_register(args):
    from services.federation.node import FederationNode

    node = FederationNode()
    node_id = node.register(
        node_name=args.name,
        node_url=args.url,
        trust_level=args.trust_level,
    )
    print(f"Registered node: {args.name} (id={node_id})")
    return 0


def cmd_list_nodes(args):
    from services.federation.node import FederationNode

    node = FederationNode()
    nodes = node.list_nodes()
    if not nodes:
        print("No federation nodes registered.")
        return 0

    print(f"{'Node':<25} {'URL':<35} {'Trust':<12} {'Status':<10} {'Last Sync'}")
    print("-" * 100)
    for n in nodes:
        print(
            f"{n['node_name']:<25} {n['node_url']:<35} {n['trust_level']:<12} "
            f"{n['status']:<10} {n['last_sync_at'] or 'never':<20}"
        )
    print(f"\nTotal: {len(nodes)} nodes")
    return 0


def cmd_share(args):
    from services.federation.protocol import FederationProtocol

    protocol = FederationProtocol()
    data = json.loads(args.data) if args.data else {}
    share_id = protocol.share(
        source_node_name=args.node,
        data_type=args.data_type,
        aggregate_data=data,
        period_start=args.period_start,
        period_end=args.period_end,
    )
    print(f"Shared data: {share_id}")
    return 0


def cmd_query(args):
    from services.federation.protocol import FederationProtocol

    protocol = FederationProtocol()
    params = json.loads(args.params) if args.params else {}
    query_id = protocol.query(
        query_type=args.query_type,
        parameters=params,
    )
    print(f"Query submitted: {query_id}")
    return 0


def cmd_shares(args):
    from services.federation.protocol import FederationProtocol

    protocol = FederationProtocol()
    shares = protocol.get_shares(data_type=args.data_type)
    if not shares:
        print("No federation shares found.")
        return 0

    for s in shares:
        print(f"  [{s['data_type']}] from {s['source_node']} ({s['consent_level']})")
        print(f"    ID: {s['share_id']}")
        print(f"    Shared: {s['shared_at']}")
        print()
    return 0


def cmd_queries(args):
    from services.federation.protocol import FederationProtocol

    protocol = FederationProtocol()
    queries = protocol.get_queries(status=args.status)
    if not queries:
        print("No federation queries found.")
        return 0

    for q in queries:
        print(f"  [{q['status']}] {q['query_type']}")
        print(f"    ID: {q['query_id']}")
        print(f"    Created: {q['created_at']}")
        print()
    return 0


def main():
    parser = argparse.ArgumentParser(description="Federation CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true", help="Register a federation node")
    group.add_argument("--list-nodes", action="store_true", help="List federation nodes")
    group.add_argument("--share", action="store_true", help="Share data with federation")
    group.add_argument("--query", action="store_true", help="Submit a federation query")
    group.add_argument("--shares", action="store_true", help="List federation shares")
    group.add_argument("--queries", action="store_true", help="List federation queries")

    parser.add_argument("--name", help="Node name")
    parser.add_argument("--url", help="Node URL")
    parser.add_argument("--trust-level", default="untrusted", help="Trust level")
    parser.add_argument("--node", help="Source node name (for --share)")
    parser.add_argument("--data-type", help="Data type")
    parser.add_argument("--data", help="JSON data (for --share)")
    parser.add_argument("--params", help="JSON params (for --query)")
    parser.add_argument("--query-type", dest="query_type", help="Query type")
    parser.add_argument("--period-start", dest="period_start", help="Period start date")
    parser.add_argument("--period-end", dest="period_end", help="Period end date")
    parser.add_argument("--status", help="Filter by status")
    parser.add_argument("--limit", type=int, default=50, help="Max results")

    args = parser.parse_args()

    if args.register:
        if not args.name or not args.url:
            parser.error("--register requires --name and --url")
        rc = cmd_register(args)
    elif args.list_nodes:
        rc = cmd_list_nodes(args)
    elif args.share:
        if not args.node or not args.data_type:
            parser.error("--share requires --node and --data-type")
        rc = cmd_share(args)
    elif args.query:
        if not args.query_type:
            parser.error("--query requires --query-type")
        rc = cmd_query(args)
    elif args.shares:
        rc = cmd_shares(args)
    elif args.queries:
        rc = cmd_queries(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
