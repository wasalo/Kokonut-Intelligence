"""Network value and trust graph services.

Computes Metcalfe's law network value and provides
multi-hop trust graph expansion.

Usage:
    python3 -m services.scoring --network-value
    python3 -m services.scoring --trust-graph --evaluator-id UUID --depth 2
    python3 -m services.scoring --transitive-trust --source UUID --target UUID
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

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

    cur.execute("SELECT COUNT(*) AS count FROM attestation_reference")
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
    possible_evaluator_pairs = evaluators * max(evaluators - 1, 0) // 2
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

    Uses BFS to find connected evaluators through attestation references.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get seed evaluator
    cur.execute("SELECT id, display_name, evaluator_type, trust_score FROM evaluator WHERE id = %s", (evaluator_id,))
    seed = cur.fetchone()
    if not seed:
        cur.close()
        return {"status": "error", "message": "Evaluator not found"}

    visited: Set[str] = {evaluator_id}
    nodes = [dict(seed)]
    edges = []
    frontier = [evaluator_id]

    for hop in range(depth):
        next_frontier = []
        for current_id in frontier:
            # Find attestations made by this evaluator
            cur.execute("""
                SELECT ar.id AS attestation_id, ar.target_attestation_id
                FROM attestation_record ar
                WHERE ar.created_by = %s
                AND ar.status = 'published'
            """, (current_id,))
            attestations = cur.fetchall()

            for att in attestations:
                target_id = str(att["target_attestation_id"]) if att["target_attestation_id"] else None
                if not target_id:
                    continue

                # Find evaluators who reviewed/attested the same target
                cur.execute("""
                    SELECT DISTINCT ar2.created_by AS evaluator_id
                    FROM attestation_record ar2
                    WHERE ar2.target_attestation_id = %s
                    AND ar2.created_by != %s
                    AND ar2.status = 'published'
                    AND ar2.created_by IS NOT NULL
                """, (target_id, current_id))
                connected = cur.fetchall()

                for conn_row in connected:
                    conn_eval_id = str(conn_row["evaluator_id"])
                    if conn_eval_id not in visited:
                        visited.add(conn_eval_id)
                        cur.execute("SELECT id, display_name, evaluator_type, trust_score FROM evaluator WHERE id = %s", (conn_eval_id,))
                        conn_eval = cur.fetchone()
                        if conn_eval:
                            nodes.append(dict(conn_eval))
                            next_frontier.append(conn_eval_id)
                            edges.append({
                                "from": current_id,
                                "to": conn_eval_id,
                                "via": str(att["attestation_id"]),
                                "hop": hop + 1,
                            })

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

    Uses BFS to find shortest trust path and computes
    trust propagation as product of trust scores along the path.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get source trust score
    cur.execute("SELECT trust_score FROM evaluator WHERE id = %s", (source_evaluator_id,))
    source = cur.fetchone()
    if not source:
        cur.close()
        return {"status": "error", "message": "Source evaluator not found"}

    # BFS for shortest path
    visited: Dict[str, Tuple[str, float]] = {source_evaluator_id: (None, float(source["trust_score"]))}
    frontier = [(source_evaluator_id, float(source["trust_score"]))]

    for depth in range(max_depth):
        next_frontier = []
        for current_id, current_trust in frontier:
            # Find connected evaluators through shared attestation targets
            cur.execute("""
                SELECT DISTINCT ar2.created_by AS connected_id
                FROM attestation_record ar1
                JOIN attestation_record ar2 ON ar1.target_attestation_id = ar2.target_attestation_id
                WHERE ar1.created_by = %s
                AND ar2.created_by != %s
                AND ar2.created_by IS NOT NULL
                AND ar1.status = 'published'
                AND ar2.status = 'published'
            """, (current_id, current_id))
            connected = cur.fetchall()

            for row in connected:
                conn_id = str(row["connected_id"])
                if conn_id not in visited:
                    cur.execute("SELECT trust_score FROM evaluator WHERE id = %s", (conn_id,))
                    conn_eval = cur.fetchone()
                    if conn_eval:
                        conn_trust = float(conn_eval["trust_score"])
                        visited[conn_id] = (current_id, conn_trust)
                        next_frontier.append((conn_id, conn_trust))

                        if conn_id == target_evaluator_id:
                            # Found path — compute transitive trust
                            path = []
                            node = conn_id
                            trust_product = 1.0
                            while node and node in visited:
                                prev, trust = visited[node]
                                path.append({"evaluator_id": node, "trust_score": trust})
                                trust_product *= trust
                                node = prev
                            path.reverse()

                            cur.close()
                            return {
                                "found": True,
                                "source": source_evaluator_id,
                                "target": target_evaluator_id,
                                "path_length": len(path),
                                "transitive_trust": round(trust_product, 6),
                                "path": path,
                            }

        frontier = next_frontier

    cur.close()
    return {
        "found": False,
        "source": source_evaluator_id,
        "target": target_evaluator_id,
        "transitive_trust": 0.0,
        "path": [],
        "message": "No trust path found within max_depth",
    }
