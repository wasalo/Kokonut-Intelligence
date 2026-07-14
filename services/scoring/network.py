"""Network value and trust graph services.

Computes Metcalfe's law network value and provides
multi-hop trust graph expansion.

Usage:
    python3 -m services.scoring --network-value
    python3 -m services.scoring --trust-graph --evaluator-id UUID --depth 2
    python3 -m services.scoring --transitive-trust --source UUID --target UUID
"""

from __future__ import annotations

import heapq
from typing import Any, Dict, List, Set, Tuple

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("scoring.network")


def compute_network_value(conn) -> Dict[str, Any]:
    """Compute Metcalfe's law network value.

    V = n * (n - 1) / 2
    where n = number of nodes in the network.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT COUNT(*) AS count FROM location WHERE status = 'active'")
    farms = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM evaluator WHERE status = 'active'")
    evaluators = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM attestation_record WHERE status = 'published'")
    attestations = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM stakeholder_feedback WHERE consent_given = TRUE")
    feedbacks = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM carbon_credit WHERE status = 'published'")
    credits = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM (
            SELECT DISTINCT g.source_evaluator_id, g.target_evaluator_id
            FROM v_evaluator_trust_edges g
            JOIN evaluator source ON source.id = g.source_evaluator_id
            JOIN evaluator target ON target.id = g.target_evaluator_id
            WHERE source.status = 'active'
              AND target.status = 'active'
              AND g.source_evaluator_id <> g.target_evaluator_id
              AND g.reference_type IN ('supports', 'validates')
              AND g.strength > 0
        ) eligible_pairs
    """)
    cross_refs = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) AS count FROM preference_signal ps
        JOIN evaluator e ON e.id = ps.evaluator_id WHERE e.status = 'active'
    """)
    preferences = cur.fetchone()["count"]

    cur.close()

    # Metcalfe's law: V = n * (n - 1) / 2
    evaluator_value = evaluators * max(evaluators - 1, 0) // 2
    attestation_value = attestations * max(attestations - 1, 0) // 2

    # Network density: actual connections / possible connections
    possible_evaluator_pairs = evaluators * max(evaluators - 1, 0)
    density = cross_refs / possible_evaluator_pairs if possible_evaluator_pairs > 0 else 0.0

    return {
        "active_farms": farms,
        "active_evaluators": evaluators,
        "published_attestations": attestations,
        "consented_feedbacks": feedbacks,
        "published_credits": credits,
        "evaluator_network_value": evaluator_value,
        "attestation_network_value": attestation_value,
        "total_cross_references": cross_refs,
        "total_preferences": preferences,
        "network_density": round(density, 6),
    }


def get_network_growth(conn, periods: int = 12) -> List[Dict[str, Any]]:
    """Track network growth over time (monthly snapshots)."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            DATE_TRUNC('month', created_at) AS month,
            COUNT(*) AS new_evaluators
        FROM evaluator
        WHERE created_at >= NOW() - INTERVAL '%s months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month
    """, (periods,))
    evaluator_growth = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT
            DATE_TRUNC('month', created_at) AS month,
            COUNT(*) AS new_attestations
        FROM attestation_record
        WHERE status = 'published'
        AND created_at >= NOW() - INTERVAL '%s months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month
    """, (periods,))
    attestation_growth = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT
            DATE_TRUNC('month', created_at) AS month,
            COUNT(*) AS new_references
        FROM attestation_reference
        WHERE created_at >= NOW() - INTERVAL '%s months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month
    """, (periods,))
    reference_growth = [dict(r) for r in cur.fetchall()]

    cur.close()

    return {
        "evaluator_growth": evaluator_growth,
        "attestation_growth": attestation_growth,
        "reference_growth": reference_growth,
    }


def get_trust_graph(conn, evaluator_id: str, depth: int = 1) -> Dict[str, Any]:
    """Expand trust graph from an evaluator up to N hops.

    Expands positive, directed trust relationships breadth-first.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get seed evaluator
    cur.execute("""
        SELECT id, display_name, evaluator_type, trust_score
        FROM evaluator WHERE id = %s AND status = 'active'
    """, (evaluator_id,))
    seed = cur.fetchone()
    if not seed:
        cur.close()
        return {"status": "error", "message": "Evaluator not found"}

    visited: Set[str] = {evaluator_id}
    nodes = [dict(seed)]
    edges = []
    frontier = [evaluator_id]

    for hop in range(max(depth, 0)):
        next_frontier = []
        for current_id in frontier:
            cur.execute("""
                SELECT g.target_evaluator_id, g.reference_type, g.strength,
                       target.id, target.display_name, target.evaluator_type,
                       target.trust_score
                FROM v_evaluator_trust_edges g
                JOIN evaluator source ON source.id = g.source_evaluator_id
                JOIN evaluator target ON target.id = g.target_evaluator_id
                WHERE g.source_evaluator_id = %s
                  AND source.status = 'active'
                  AND target.status = 'active'
                  AND g.reference_type IN ('supports', 'validates')
                  AND g.strength > 0
                ORDER BY g.target_evaluator_id, g.reference_type, g.strength DESC
            """, (current_id,))
            for row in cur.fetchall():
                conn_eval_id = str(row["target_evaluator_id"])
                edges.append({
                    "from": current_id,
                    "to": conn_eval_id,
                    "via": row["reference_type"],
                    "reference_type": row["reference_type"],
                    "strength": float(row["strength"]),
                    "hop": hop + 1,
                })
                if conn_eval_id not in visited:
                    visited.add(conn_eval_id)
                    nodes.append({
                        "id": row["id"],
                        "display_name": row["display_name"],
                        "evaluator_type": row["evaluator_type"],
                        "trust_score": row["trust_score"],
                    })
                    next_frontier.append(conn_eval_id)

        frontier = next_frontier

    cur.close()

    return {
        "evaluator_id": evaluator_id,
        "seed_name": seed["display_name"],
        "depth": depth,
        "nodes_found": len(nodes),
        "edges_found": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def compute_transitive_trust(
    conn,
    source_evaluator_id: str,
    target_evaluator_id: str,
    max_depth: int = 5,
) -> Dict[str, Any]:
    """Compute transitive trust between two evaluators.

    Finds the deterministic strongest-product simple path within max_depth.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT trust_score FROM evaluator WHERE id = %s AND status = 'active'", (source_evaluator_id,))
    source = cur.fetchone()
    if not source:
        cur.close()
        return {"status": "error", "message": "Source evaluator not found"}

    source_trust = float(source["trust_score"])
    if source_evaluator_id == target_evaluator_id:
        cur.close()
        return {
            "found": True, "source": source_evaluator_id, "target": target_evaluator_id,
            "path_length": 0, "transitive_trust": 1.0,
            "path": [{"evaluator_id": source_evaluator_id, "trust_score": source_trust}],
        }

    cur.execute("""
        SELECT g.source_evaluator_id, g.target_evaluator_id, g.reference_type,
               g.strength, target.trust_score AS target_trust
        FROM v_evaluator_trust_edges g
        JOIN evaluator source ON source.id = g.source_evaluator_id
        JOIN evaluator target ON target.id = g.target_evaluator_id
        WHERE source.status = 'active' AND target.status = 'active'
          AND g.reference_type IN ('supports', 'validates') AND g.strength > 0
        ORDER BY g.source_evaluator_id, g.target_evaluator_id,
                 g.reference_type, g.strength DESC
    """)
    adjacency: Dict[str, List[Tuple[str, float, float]]] = {}
    for row in cur.fetchall():
        adjacency.setdefault(str(row["source_evaluator_id"]), []).append((
            str(row["target_evaluator_id"]),
            float(row["strength"]),
            float(row["target_trust"]),
        ))

    # Heap ordering makes equal-product paths deterministic by evaluator ID sequence.
    queue = [(-source_trust, (source_evaluator_id,), ((source_evaluator_id, source_trust),))]
    best = None
    while queue:
        negative_product, ids, path_data = heapq.heappop(queue)
        product = -negative_product
        if ids[-1] == target_evaluator_id:
            if best is None or product > best[0] or (product == best[0] and ids < best[1]):
                best = (product, ids, path_data)
            continue
        if len(ids) - 1 >= max(max_depth, 0):
            continue
        for connected_id, strength, trust_score in adjacency.get(ids[-1], []):
            if connected_id in ids:
                continue
            next_product = product * strength * trust_score
            heapq.heappush(
                queue,
                (-next_product, ids + (connected_id,), path_data + ((connected_id, trust_score),)),
            )

    if best:
        trust_product, _, path_data = best
        path = [{"evaluator_id": evaluator_id, "trust_score": trust} for evaluator_id, trust in path_data]
        cur.close()
        return {
            "found": True,
            "source": source_evaluator_id,
            "target": target_evaluator_id,
            "path_length": len(path) - 1,
            "transitive_trust": round(trust_product, 6),
            "path": path,
        }

    cur.close()
    return {
        "found": False,
        "source": source_evaluator_id,
        "target": target_evaluator_id,
        "transitive_trust": 0.0,
        "path": [],
        "message": "No trust path found within max_depth",
    }
