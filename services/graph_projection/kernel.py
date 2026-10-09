"""Atomic full-rebuild projection kernel."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import psycopg2.extras

from services.common.logging import get_logger

from .evidence_lineage import build, load_sources

logger = get_logger("graph_projection.kernel")
PROJECTION_KEY = "evidence_lineage"
PROJECTION_VERSION = 1
LOCK_NAMESPACE = 173001


def validate_rows(nodes, edges) -> None:
    node_ids = {row["id"] for row in nodes}
    if len(node_ids) != len(nodes):
        raise ValueError("duplicate graph node id")
    if any(edge["source_node_id"] not in node_ids or edge["target_node_id"] not in node_ids for edge in edges):
        raise ValueError("graph edge references a missing node")
    if any(row["audience"] not in {"internal", "public"} for row in nodes + edges):
        raise ValueError("invalid graph audience")
    if any(row["valid_from"] is None for row in nodes + edges):
        raise ValueError("graph validity start is required")


def _insert_many(cur, table, columns, rows):
    if not rows:
        return

    def adapt(column, value):
        if isinstance(value, uuid.UUID):
            return str(value)
        if column == "attributes":
            return psycopg2.extras.Json(value, dumps=lambda item: json.dumps(item, default=str))
        return value

    values = [[adapt(column, row.get(column)) for column in columns] for row in rows]
    psycopg2.extras.execute_values(
        cur,
        f"INSERT INTO {table} ({','.join(columns)}) VALUES %s",
        values,
    )


def _rebuild(
    conn, actor: str, projection_key: str = PROJECTION_KEY, projection_version: int = PROJECTION_VERSION,
    rebuild_id=None, cutoff=None, commit: bool = True
) -> dict:
    if not actor or not actor.strip():
        raise ValueError("actor is required")
    cutoff = cutoff or datetime.now(timezone.utc)
    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute("SET LOCAL statement_timeout = '120s'")
        cur.execute("SET LOCAL lock_timeout = '10s'")
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, %s))", (projection_key, LOCK_NAMESPACE))
        cur.execute(
            "INSERT INTO graph_projection_generation (projection_key, projection_version, status, source_cutoff, built_by, rebuild_id) VALUES (%s, %s, 'building', %s, %s, %s) RETURNING id",
            (projection_key, projection_version, cutoff, actor, rebuild_id),
        )
        generation_id = cur.fetchone()[0]
        sources = load_sources(cur, cutoff)
        nodes, edges = build(generation_id, sources)
        for row in nodes + edges:
            row["valid_from"] = cutoff
        validate_rows(nodes, edges)
        node_columns = (
            "id",
            "generation_id",
            "node_type",
            "entity_type",
            "entity_id",
            "entity_key",
            "iri",
            "location_id",
            "lifecycle_status",
            "audience",
            "valid_from",
            "valid_to",
            "source_table",
            "source_updated_at",
            "source_hash",
            "attributes",
        )
        edge_columns = (
            "id",
            "generation_id",
            "edge_type",
            "source_node_id",
            "target_node_id",
            "source_table",
            "source_entity_id",
            "source_key",
            "location_id",
            "audience",
            "valid_from",
            "valid_to",
            "source_hash",
            "attributes",
        )
        _insert_many(cur, "graph_node", node_columns, nodes)
        _insert_many(cur, "graph_edge", edge_columns, edges)
        cur.execute(
            "SELECT (SELECT COUNT(*) FROM graph_node WHERE generation_id = %s), (SELECT COUNT(*) FROM graph_edge WHERE generation_id = %s)",
            (generation_id, generation_id),
        )
        persisted_counts = cur.fetchone()
        if persisted_counts != (len(nodes), len(edges)):
            raise ValueError("persisted graph counts do not match generated rows")
        content_hash = hashlib.sha256(
            "".join(sorted([row["source_hash"] for row in nodes + edges])).encode()
        ).hexdigest()
        cur.execute(
            "UPDATE graph_projection_generation SET status = 'superseded' WHERE projection_key = %s AND projection_version = %s AND status = 'active' AND id <> %s",
            (projection_key, projection_version, generation_id),
        )
        cur.execute(
            "UPDATE graph_projection_generation SET status = 'active', node_count = %s, edge_count = %s, content_hash = %s, completed_at = NOW() WHERE id = %s AND status = 'building'",
            (len(nodes), len(edges), content_hash, generation_id),
        )
        cur.execute(
            "UPDATE graph_projection SET active_generation_id = %s, updated_at = NOW() WHERE projection_key = %s AND projection_version = %s",
            (generation_id, projection_key, projection_version),
        )
        if cur.rowcount != 1:
            raise ValueError("graph projection definition not found")
        if commit:
            conn.commit()
        logger.info("Activated graph projection generation %s by %s", generation_id, actor)
        return {
            "projection_key": projection_key,
            "projection_version": projection_version,
            "generation_id": generation_id,
            "status": "active",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "content_hash": content_hash,
            "source_cutoff": cutoff,
        }
    except Exception:
        conn.rollback()
        logger.exception("Graph projection rebuild failed")
        raise
    finally:
        cur.close()


def rebuild(
    conn, actor: str, projection_key: str = PROJECTION_KEY, projection_version: int = PROJECTION_VERSION
) -> dict:
    return _rebuild(conn, actor, projection_key, projection_version)


def validate_generation(conn, generation_id=None) -> dict:
    cur = conn.cursor()
    try:
        if generation_id is None:
            cur.execute(
                "SELECT active_generation_id FROM graph_projection WHERE projection_key = %s AND projection_version = %s",
                (PROJECTION_KEY, PROJECTION_VERSION),
            )
            row = cur.fetchone()
            generation_id = row[0] if row else None
        if generation_id is None:
            return {"valid": False, "errors": ["no active generation"]}
        cur.execute(
            "SELECT node_count, edge_count, content_hash FROM graph_projection_generation WHERE id = %s",
            (generation_id,),
        )
        expected = cur.fetchone()
        cur.execute(
            "SELECT (SELECT COUNT(*) FROM graph_node WHERE generation_id = %s), (SELECT COUNT(*) FROM graph_edge WHERE generation_id = %s), (SELECT string_agg(source_hash, '' ORDER BY source_hash) FROM (SELECT source_hash FROM graph_node WHERE generation_id = %s UNION ALL SELECT source_hash FROM graph_edge WHERE generation_id = %s) hashes)",
            (generation_id, generation_id, generation_id, generation_id),
        )
        actual = cur.fetchone()
        errors = []
        if not expected:
            errors.append("generation not found")
        elif (expected[0], expected[1]) != actual[:2]:
            errors.append("stored counts do not match")
        elif expected[2] and expected[2] != hashlib.sha256((actual[2] or "").encode()).hexdigest():
            errors.append("stored content hash does not match")
        return {
            "generation_id": generation_id,
            "valid": not errors,
            "errors": errors,
            "node_count": actual[0],
            "edge_count": actual[1],
        }
    finally:
        cur.close()
