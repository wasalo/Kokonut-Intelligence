"""Cross-Impact Analyzer — maps how threats influence each other,
detects amplification/attenuation chains, and simulates threat interactions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger
from services.threatcasting.config import VELOCITY_MULTIPLIERS

logger = get_logger(__name__)


class CrossImpactAnalyzer:
    """Analyzes cross-impact relationships between threats."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def create_impact(
        self,
        source_threat_id: str,
        target_threat_id: str,
        impact_type: str,
        impact_magnitude: float,
        impact_direction: str,
        description: Optional[str] = None,
        confidence_level: str = "medium",
        evidence_source: Optional[str] = None,
        lag_days: int = 0,
    ) -> Dict[str, Any]:
        """Create a new cross-impact relationship."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        impact_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO threat_cross_impact
                (id, source_threat_id, target_threat_id, impact_type,
                 impact_magnitude, impact_direction, description,
                 confidence_level, evidence_source, lag_days)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                impact_id, source_threat_id, target_threat_id, impact_type,
                impact_magnitude, impact_direction, description,
                confidence_level, evidence_source, lag_days,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created cross-impact %s: %s → %s (%s)", impact_id, source_threat_id, target_threat_id, impact_type)
        return result

    def get_impacts(
        self,
        location_id: Optional[str] = None,
        source_threat_id: Optional[str] = None,
        target_threat_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get cross-impact relationships with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["ci.is_enabled = TRUE"]
        params: list = []

        if source_threat_id:
            conditions.append("ci.source_threat_id = %s")
            params.append(source_threat_id)
        if target_threat_id:
            conditions.append("ci.target_threat_id = %s")
            params.append(target_threat_id)
        if location_id:
            conditions.append("t.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(
            f"""
            SELECT ci.*, ts.threat_name AS source_name, tt.threat_name AS target_name
            FROM threat_cross_impact ci
            JOIN threat ts ON ts.id = ci.source_threat_id
            JOIN threat tt ON tt.id = ci.target_threat_id
            WHERE {where_clause}
            ORDER BY ci.impact_magnitude DESC
            """,
            params,
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def analyze_cross_impact_matrix(self, location_id: str) -> Dict[str, Any]:
        """Build full cross-impact matrix for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get all active threats
        cur.execute(
            """
            SELECT id, threat_name, threat_type, severity_potential, probability, velocity
            FROM threat
            WHERE location_id = %s AND is_active = TRUE
            ORDER BY threat_name
            """,
            (location_id,),
        )
        threats = [dict(r) for r in cur.fetchall()]

        # Get all cross-impacts
        cur.execute(
            """
            SELECT ci.*, ts.threat_name AS source_name, tt.threat_name AS target_name
            FROM threat_cross_impact ci
            JOIN threat ts ON ts.id = ci.source_threat_id
            JOIN threat tt ON tt.id = ci.target_threat_id
            WHERE ci.is_enabled = TRUE
            ORDER BY ci.impact_magnitude DESC
            """,
        )
        impacts = [dict(r) for r in cur.fetchall()]
        cur.close()

        # Build adjacency matrix
        threat_ids = {t["id"]: t["threat_name"] for t in threats}
        matrix: Dict[str, Dict[str, float]] = {}
        for tid in threat_ids:
            matrix[tid] = {}
            for tid2 in threat_ids:
                matrix[tid][tid2] = 0.0

        for imp in impacts:
            if imp["source_threat_id"] in matrix and imp["target_threat_id"] in matrix[imp["source_threat_id"]]:
                direction = 1.0 if imp["impact_direction"] == "positive" else -1.0
                matrix[imp["source_threat_id"]][imp["target_threat_id"]] = imp["impact_magnitude"] * direction

        # Detect amplification chains
        chains = self._detect_amplification_chains(threat_ids, impacts)

        # Compute summary statistics
        total_impacts = len(impacts)
        amplifications = sum(1 for i in impacts if i["impact_type"] == "amplifies")
        attenuations = sum(1 for i in impacts if i["impact_type"] == "attenuates")
        triggers = sum(1 for i in impacts if i["impact_type"] == "triggers")
        avg_magnitude = sum(i["impact_magnitude"] for i in impacts) / total_impacts if total_impacts > 0 else 0

        return {
            "location_id": location_id,
            "threats": threats,
            "impacts": impacts,
            "matrix": matrix,
            "amplification_chains": chains,
            "summary": {
                "total_threats": len(threats),
                "total_impacts": total_impacts,
                "amplifications": amplifications,
                "attenuations": attenuations,
                "triggers": triggers,
                "avg_magnitude": round(avg_magnitude, 4),
                "chain_count": len(chains),
            },
        }

    def _detect_amplification_chains(
        self,
        threat_ids: Dict[str, str],
        impacts: List[Dict[str, Any]],
    ) -> List[List[str]]:
        """Detect self-reinforcing amplification chains using DFS."""
        # Build adjacency list for amplification edges
        adj: Dict[str, List[str]] = {tid: [] for tid in threat_ids}
        for imp in impacts:
            if imp["impact_type"] == "amplifies":
                adj[imp["source_threat_id"]].append(imp["target_threat_id"])

        # Detect cycles (amplification loops)
        chains: List[List[str]] = []
        visited: set = set()
        path: list = []

        def dfs(node: str, start: str):
            if node in visited and node == start and len(path) > 1:
                chains.append(list(path))
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in adj.get(node, []):
                dfs(neighbor, start)
            path.pop()
            visited.remove(node)

        for tid in threat_ids:
            visited.clear()
            path.clear()
            dfs(tid, tid)

        return chains

    def simulate_threat_interaction(
        self,
        threat_ids: List[str],
        scenario: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Simulate combined effect of multiple threats interacting."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get threat details
        placeholders = ",".join(["%s"] * len(threat_ids))
        cur.execute(
            f"""
            SELECT id, threat_name, threat_type, severity_potential, probability, velocity
            FROM threat
            WHERE id IN ({placeholders}) AND is_active = TRUE
            """,
            threat_ids,
        )
        threats = {str(r["id"]): dict(r) for r in cur.fetchall()}

        # Get cross-impacts between these threats
        cur.execute(
            f"""
            SELECT * FROM threat_cross_impact
            WHERE source_threat_id IN ({placeholders})
              AND target_threat_id IN ({placeholders})
              AND is_enabled = TRUE
            """,
            threat_ids + threat_ids,
        )
        impacts = [dict(r) for r in cur.fetchall()]
        cur.close()

        # Compute combined probability using Bayesian-like fusion
        combined_prob = 1.0
        for tid in threat_ids:
            if tid in threats and threats[tid].get("probability"):
                combined_prob *= (1 - float(threats[tid]["probability"]))
        combined_prob = 1 - combined_prob

        # Apply cross-impact modifiers
        for imp in impacts:
            if imp["impact_type"] == "amplifies":
                combined_prob = min(1.0, combined_prob * (1 + imp["impact_magnitude"] * 0.2))
            elif imp["impact_type"] == "attenuates":
                combined_prob = max(0.0, combined_prob * (1 - imp["impact_magnitude"] * 0.2))

        # Determine combined severity
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_severity = max(
            severity_map.get(threats[tid].get("severity_potential", "low"), 1)
            for tid in threat_ids if tid in threats
        )
        severity_labels = {1: "low", 2: "medium", 3: "high", 4: "critical"}
        combined_severity = severity_labels.get(max_severity, "low")

        return {
            "threat_ids": threat_ids,
            "threats": threats,
            "impacts": impacts,
            "combined_probability": round(combined_prob, 4),
            "combined_severity": combined_severity,
            "interaction_count": len(impacts),
            "amplification_count": sum(1 for i in impacts if i["impact_type"] == "amplifies"),
            "attenuation_count": sum(1 for i in impacts if i["impact_type"] == "attenuates"),
        }

    def get_cross_impact_summary(self, location_id: str) -> Dict[str, Any]:
        """Get simplified cross-impact summary for dashboard."""
        matrix = self.analyze_cross_impact_matrix(location_id)

        # Identify most connected threats (hub threats)
        threat_connectivity: Dict[str, int] = {}
        for imp in matrix["impacts"]:
            src = imp["source_threat_id"]
            tgt = imp["target_threat_id"]
            threat_connectivity[src] = threat_connectivity.get(src, 0) + 1
            threat_connectivity[tgt] = threat_connectivity.get(tgt, 0) + 1

        hub_threats = sorted(threat_connectivity.items(), key=lambda x: x[1], reverse=True)[:5]

        # Identify critical paths (high-magnitude amplifications)
        critical_paths = [
            imp for imp in matrix["impacts"]
            if imp["impact_type"] == "amplifies" and imp["impact_magnitude"] >= 0.7
        ]

        return {
            "location_id": location_id,
            "total_threats": matrix["summary"]["total_threats"],
            "total_impacts": matrix["summary"]["total_impacts"],
            "amplifications": matrix["summary"]["amplifications"],
            "attenuations": matrix["summary"]["attenuations"],
            "triggers": matrix["summary"]["triggers"],
            "avg_magnitude": matrix["summary"]["avg_magnitude"],
            "chain_count": matrix["summary"]["chain_count"],
            "hub_threats": [
                {"threat_id": tid, "connections": cnt, "name": matrix["threats"][0]["threat_name"] if matrix["threats"] else "unknown"}
                for tid, cnt in hub_threats
            ],
            "critical_paths_count": len(critical_paths),
            "amplification_chains": matrix["amplification_chains"],
        }
