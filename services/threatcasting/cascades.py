"""Cascade Modeler — models cascading failure scenarios, detects active cascades,
and computes risk scores."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger
from services.threatcasting.config import CASCADE_CONFIG

logger = get_logger(__name__)


class CascadeModeler:
    """Models and evaluates cascading failure scenarios."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def create_cascade(
        self,
        trigger_threat_id: str,
        cascade_name: str,
        description: Optional[str] = None,
        failure_chain: Optional[List[str]] = None,
        mitigation_strategies: Optional[List[str]] = None,
        early_warning_signals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new cascade scenario."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cascade_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO threat_cascade
                (id, trigger_threat_id, cascade_name, description,
                 failure_chain, mitigation_strategies, early_warning_signals)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                cascade_id, trigger_threat_id, cascade_name, description,
                failure_chain or [], mitigation_strategies or [], early_warning_signals or [],
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created cascade %s: %s", cascade_id, cascade_name)
        return result

    def get_cascade(self, cascade_id: str) -> Optional[Dict[str, Any]]:
        """Get a single cascade."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT c.*, t.threat_name AS trigger_threat_name
            FROM threat_cascade c
            JOIN threat t ON t.id = c.trigger_threat_id
            WHERE c.id = %s
            """,
            (cascade_id,),
        )
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None

    def get_cascades(
        self,
        location_id: Optional[str] = None,
        trigger_threat_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get cascades with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions: list = []
        params: list = []

        if trigger_threat_id:
            conditions.append("c.trigger_threat_id = %s")
            params.append(trigger_threat_id)
        if location_id:
            conditions.append("t.location_id = %s")
            params.append(location_id)
        if active_only:
            conditions.append("c.is_enabled = TRUE")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        cur.execute(
            f"""
            SELECT c.*, t.threat_name AS trigger_threat_name
            FROM threat_cascade c
            JOIN threat t ON t.id = c.trigger_threat_id
            WHERE {where_clause}
            ORDER BY c.cascade_probability DESC NULLS LAST
            """,
            params,
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def model_cascade(
        self,
        trigger_threat_id: str,
        chain: List[str],
    ) -> Dict[str, Any]:
        """Simulate a cascade from trigger through the chain."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get trigger threat
        cur.execute(
            "SELECT id, threat_name, threat_type, severity_potential, probability, velocity FROM threat WHERE id = %s",
            (trigger_threat_id,),
        )
        trigger_row = cur.fetchone()
        trigger = dict(trigger_row) if trigger_row else None

        # Get all threats in chain
        chain_threats = []
        for tid in chain:
            cur.execute(
                "SELECT id, threat_name, threat_type, severity_potential, probability FROM threat WHERE id = %s",
                (tid,),
            )
            row = cur.fetchone()
            if row:
                chain_threats.append(dict(row))

        # Get cross-impacts along the chain
        cumulative_prob = 1.0
        chain_effects = []
        prev_tid = trigger_threat_id

        for tid in chain:
            cur.execute(
                """
                SELECT impact_type, impact_magnitude, impact_direction, lag_days
                FROM threat_cross_impact
                WHERE source_threat_id = %s AND target_threat_id = %s AND is_enabled = TRUE
                """,
                (prev_tid, tid),
            )
            impact = cur.fetchone()
            if impact:
                impact = dict(impact)
                modifier = impact["impact_magnitude"] if impact["impact_type"] in ("amplifies", "triggers") else -impact["impact_magnitude"]
                cumulative_prob *= (1 + modifier)
                cumulative_prob = max(0, min(1, cumulative_prob))
                chain_effects.append({
                    "from": prev_tid,
                    "to": tid,
                    "impact": impact["impact_type"],
                    "magnitude": impact["impact_magnitude"],
                })
            prev_tid = tid

        cur.close()

        # Determine severity progression
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        severity_labels = {1: "low", 2: "medium", 3: "high", 4: "critical"}

        max_sev = 1
        for t in chain_threats:
            sev = severity_map.get(t.get("severity_potential", "low"), 1)
            if sev > max_sev:
                max_sev = sev

        return {
            "trigger_threat": trigger,
            "chain": chain_threats,
            "chain_length": len(chain_threats),
            "cumulative_probability": round(cumulative_prob, 4),
            "chain_effects": chain_effects,
            "total_impact_severity": severity_labels.get(max_sev, "low"),
            "estimated_time_hours": sum(
                self._estimate_propagation_time(t.get("velocity", "moderate"))
                for t in chain_threats
            ),
        }

    def _estimate_propagation_time(self, velocity: str) -> int:
        """Estimate propagation time based on threat velocity."""
        times = {"slow": 720, "moderate": 168, "fast": 48, "rapid": 12}
        return times.get(velocity, 168)

    def detect_active_cascades(self, location_id: str) -> List[Dict[str, Any]]:
        """Detect potentially active cascades based on flag statuses."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get all cascades for location
        cur.execute(
            """
            SELECT c.*
            FROM threat_cascade c
            JOIN threat t ON t.id = c.trigger_threat_id
            WHERE t.location_id = %s AND c.is_enabled = TRUE
            """,
            (location_id,),
        )
        cascades = [dict(r) for r in cur.fetchall()]

        active = []
        for cascade in cascades:
            # Check if trigger threat has warning/critical flags
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM threat_flag f
                WHERE f.threat_id = %s AND f.status IN ('warning', 'critical')
                """,
                (cascade["trigger_threat_id"],),
            )
            warning_count = cur.fetchone()["cnt"]

            if warning_count > 0:
                cascade["trigger_warning_count"] = warning_count
                cascade["activation_risk"] = "high" if warning_count >= 2 else "medium"
                active.append(cascade)

        cur.close()
        return active

    def get_cascade_risk_score(self, location_id: str) -> Dict[str, Any]:
        """Compute overall cascade risk score for a location."""
        cascades = self.get_cascades(location_id=location_id)
        active = self.detect_active_cascades(location_id)

        if not cascades:
            return {
                "location_id": location_id,
                "total_cascades": 0,
                "active_cascades": 0,
                "risk_score": 0.0,
                "risk_level": "low",
            }

        # Compute risk score
        total_prob = sum(float(c.get("cascade_probability") or 0) for c in cascades)
        active_prob = sum(float(c.get("cascade_probability") or 0) for c in active)

        severity_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        max_severity = max(
            severity_map.get(c.get("total_impact_severity", "low"), 0.25)
            for c in cascades
        )

        risk_score = (active_prob / total_prob * max_severity) if total_prob > 0 else 0

        risk_level = "low"
        if risk_score >= 0.7:
            risk_level = "critical"
        elif risk_score >= 0.5:
            risk_level = "high"
        elif risk_score >= 0.3:
            risk_level = "medium"

        return {
            "location_id": location_id,
            "total_cascades": len(cascades),
            "active_cascades": len(active),
            "total_probability": round(total_prob, 4),
            "active_probability": round(active_prob, 4),
            "max_severity": max_severity,
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
        }

    def mitigate_cascade(
        self,
        cascade_id: str,
        strategy: str,
    ) -> Dict[str, Any]:
        """Record a mitigation strategy for a cascade."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            UPDATE threat_cascade
            SET mitigation_strategies = array_append(mitigation_strategies, %s),
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (strategy, cascade_id),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Added mitigation to cascade %s: %s", cascade_id, strategy)
        return result

    def delete_cascade(self, cascade_id: str) -> bool:
        """Delete a cascade."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM threat_cascade WHERE id = %s", (cascade_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
