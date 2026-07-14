"""Bounded reads against the active graph generation."""

from __future__ import annotations

import psycopg2.extras

EDGE_TYPES = frozenset({"registers", "measures", "about_location", "claims_metric", "supported_by", "uses_schema", "attests"})
MAX_DEPTH = 5
MAX_NODES = 500


def query_graph(conn, entity_key: str, depth: int = 1, node_cap: int = 100, edge_types=None, location_id=None, audience="internal") -> dict:
    if not entity_key: raise ValueError("entity_key is required")
    if not 0 <= depth <= MAX_DEPTH: raise ValueError("depth must be between 0 and 5")
    if not 1 <= node_cap <= MAX_NODES: raise ValueError("node_cap must be between 1 and 500")
    if audience not in {"internal", "public"}: raise ValueError("audience must be internal or public")
    edge_types = list(edge_types or sorted(EDGE_TYPES))
    if not edge_types or any(value not in EDGE_TYPES for value in edge_types): raise ValueError("unsupported edge type")
    allowed_audiences = ["public"] if audience == "public" else ["internal", "public"]
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("""WITH RECURSIVE active AS (SELECT active_generation_id AS id FROM graph_projection WHERE projection_key = %s AND projection_version = %s), walk(id, depth, path) AS (SELECT n.id, 0, ARRAY[n.id] FROM graph_node n JOIN active a ON a.id = n.generation_id WHERE n.entity_key = %s AND n.audience = ANY(%s) AND (%s::uuid IS NULL OR n.location_id = %s::uuid) UNION ALL SELECT CASE WHEN e.source_node_id = w.id THEN e.target_node_id ELSE e.source_node_id END, w.depth + 1, w.path || CASE WHEN e.source_node_id = w.id THEN e.target_node_id ELSE e.source_node_id END FROM walk w JOIN graph_edge e ON (e.source_node_id = w.id OR e.target_node_id = w.id) JOIN active a ON a.id = e.generation_id WHERE w.depth < %s AND e.edge_type = ANY(%s) AND e.audience = ANY(%s) AND (%s::uuid IS NULL OR e.location_id = %s::uuid) AND NOT (CASE WHEN e.source_node_id = w.id THEN e.target_node_id ELSE e.source_node_id END = ANY(w.path))), ids AS (SELECT id, MIN(depth) depth FROM walk GROUP BY id ORDER BY MIN(depth), id LIMIT %s) SELECT n.* FROM graph_node n JOIN ids ON ids.id = n.id JOIN active a ON a.id = n.generation_id WHERE n.audience = ANY(%s) ORDER BY ids.depth, n.id""", ("evidence_lineage", 1, entity_key, allowed_audiences, location_id, location_id, depth, edge_types, allowed_audiences, location_id, location_id, node_cap, allowed_audiences))
        nodes = [dict(row) for row in cur.fetchall()]; ids = [row["id"] for row in nodes]
        if not ids: return {"nodes": [], "edges": []}
        cur.execute("""SELECT e.* FROM graph_edge e JOIN graph_projection p ON p.active_generation_id = e.generation_id WHERE p.projection_key = %s AND p.projection_version = %s AND e.source_node_id = ANY(%s::uuid[]) AND e.target_node_id = ANY(%s::uuid[]) AND e.edge_type = ANY(%s) AND e.audience = ANY(%s) AND (%s::uuid IS NULL OR e.location_id = %s::uuid) ORDER BY e.edge_type, e.id""", ("evidence_lineage", 1, ids, ids, edge_types, allowed_audiences, location_id, location_id))
        return {"nodes": nodes, "edges": [dict(row) for row in cur.fetchall()]}
    finally: cur.close()
