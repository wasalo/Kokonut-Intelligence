"""Trust graph export helpers for EBF scorecards."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_connection():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)


def export_trust_graph(conn, reference_id: str, public_safe: bool = False) -> dict[str, Any]:
    """Export trust graph nodes and edges connected to a reference UUID."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    public_filter = "AND n.public_safe = TRUE" if public_safe else ""
    edge_public_filter = "AND e.public_safe = TRUE" if public_safe else ""
    cur.execute(
        f"""
        WITH seed_nodes AS (
            SELECT id FROM ebf_trust_graph_node n
            WHERE reference_id = %s {public_filter}
        ), connected_nodes AS (
            SELECT id FROM seed_nodes
            UNION
            SELECT e.source_node_id FROM ebf_trust_graph_edge e JOIN seed_nodes s ON s.id = e.target_node_id {edge_public_filter}
            UNION
            SELECT e.target_node_id FROM ebf_trust_graph_edge e JOIN seed_nodes s ON s.id = e.source_node_id {edge_public_filter}
        )
        SELECT n.*
        FROM ebf_trust_graph_node n
        JOIN connected_nodes cn ON cn.id = n.id
        ORDER BY n.node_type, n.label, n.id
        """,
        (reference_id,),
    )
    nodes = [dict(row) for row in cur.fetchall()]
    node_ids = [row["id"] for row in nodes]

    edges: list[dict[str, Any]] = []
    if node_ids:
        cur.execute(
            f"""
            SELECT e.*
            FROM ebf_trust_graph_edge e
            WHERE e.source_node_id = ANY(%s::uuid[])
              AND e.target_node_id = ANY(%s::uuid[])
              {edge_public_filter}
            ORDER BY e.edge_type, e.id
            """,
            (node_ids, node_ids),
        )
        edges = [dict(row) for row in cur.fetchall()]
    cur.close()

    return {
        "export_type": "ebf_trust_graph",
        "reference_id": reference_id,
        "public_safe": public_safe,
        "nodes": nodes,
        "edges": edges,
    }
