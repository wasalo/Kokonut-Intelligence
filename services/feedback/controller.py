"""Feedback Controller — closes the OODA loop.

Tracks action outcomes, evaluates effectiveness, and generates
adaptive feedback that modifies thresholds, weights, and sampling
rates based on observed results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class FeedbackController:
    """Tracks outcomes and generates adaptive feedback."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def record_outcome(
        self,
        action_type: str,
        action_source: str,
        location_id: str,
        outcome_type: str = "unknown",
        action_source_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        outcome_evidence: Optional[Dict] = None,
        measured_delta: Optional[Dict] = None,
        measurement_period_hours: int = 24,
        confidence: str = "low",
    ) -> str:
        """Record the outcome of an action.

        Args:
            action_type: Type of action taken (e.g., 'intervention', 'alert').
            action_source: Source of the action (e.g., 'policy_engine', 'agent').
            location_id: UUID of the location affected.
            outcome_type: 'effective', 'partially_effective', 'ineffective',
                         'no_effect', 'counterproductive', or 'unknown'.
            action_source_id: ID of the source action record.
            correlation_id: OODA cycle correlation ID.
            decision_id: Decision log ID if action came from policy engine.
            outcome_evidence: Evidence supporting the outcome assessment.
            measured_delta: Measured changes in relevant metrics.
            measurement_period_hours: How long after action was outcome measured.
            confidence: Confidence in the outcome assessment.

        Returns:
            The outcome record ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        outcome_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO action_outcome (
                id, action_type, action_source, action_source_id,
                location_id, correlation_id, decision_id,
                outcome_type, outcome_evidence, measured_delta,
                measurement_period_hours, measured_at, measured_by,
                confidence, feedback_applied, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'system', %s, FALSE, '{}')
        """, (
            outcome_id, action_type, action_source, action_source_id,
            location_id, correlation_id, decision_id,
            outcome_type,
            psycopg2.extras.Json(outcome_evidence or {}),
            psycopg2.extras.Json(measured_delta or {}),
            measurement_period_hours, now, confidence,
        ))

        conn.commit()
        cur.close()
        return outcome_id

    def evaluate_outcomes(
        self,
        location_id: Optional[str] = None,
        since_hours: int = 168,
    ) -> List[Dict[str, Any]]:
        """Evaluate recent outcomes and generate feedback signals.

        Args:
            location_id: Optional location filter.
            since_hours: Look back window in hours (default: 7 days).

        Returns:
            List of feedback signals with adaptation recommendations.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["ao.feedback_applied = FALSE"]
        params = []

        if location_id:
            conditions.append("ao.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT
                ao.*,
                dl.policy_id,
                dp.policy_name,
                dp.action_type as policy_action_type
            FROM action_outcome ao
            LEFT JOIN decision_log dl ON dl.id = ao.decision_id
            LEFT JOIN decision_policy dp ON dp.id = dl.policy_id
            WHERE {where_clause}
            AND ao.measured_at > NOW() - INTERVAL '{since_hours} hours'
            ORDER BY ao.measured_at DESC
        """, params)

        outcomes = [dict(r) for r in cur.fetchall()]
        cur.close()

        # Generate feedback signals
        signals = []
        for outcome in outcomes:
            signal = self._analyze_outcome(outcome)
            if signal:
                signals.append(signal)

        return signals

    def apply_feedback(
        self,
        outcome_id: str,
        feedback_type: str,
        target_entity: str,
        target_entity_id: Optional[str],
        target_field: str,
        new_value: Any,
        adjustment_reason: str,
        adjustment_magnitude: float = 0.0,
        applied_by: str = "system",
    ) -> str:
        """Apply adaptive feedback based on an outcome.

        Args:
            outcome_id: The outcome that generated this feedback.
            feedback_type: Type of adaptation ('threshold_adjustment',
                          'weight_shift', 'sampling_rate', etc.).
            target_entity: Entity being modified ('alert_rule', 'crisp_weight', etc.).
            target_entity_id: UUID of the specific entity.
            target_field: Field being modified.
            new_value: New value for the field.
            adjustment_reason: Human-readable reason.
            adjustment_magnitude: How much the value changed.
            applied_by: Who applied the feedback.

        Returns:
            The feedback loop record ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Get current value
        previous_value = self._get_current_value(
            cur, target_entity, target_entity_id, target_field
        )

        cur.execute("""
            INSERT INTO feedback_loop (
                id, loop_type, source_outcome_id, target_entity,
                target_entity_id, target_field, previous_value,
                new_value, adjustment_reason, adjustment_magnitude,
                status, applied_at, applied_by, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'applied', %s, %s, %s, %s)
        """, (
            feedback_id, feedback_type, outcome_id, target_entity,
            target_entity_id, target_field,
            psycopg2.extras.Json(previous_value) if previous_value else None,
            psycopg2.extras.Json(new_value),
            adjustment_reason, adjustment_magnitude,
            now, applied_by, now, now,
        ))

        # Mark outcome as feedback applied
        cur.execute("""
            UPDATE action_outcome
            SET feedback_applied = TRUE, feedback_applied_at = %s
            WHERE id = %s
        """, (now, outcome_id))

        conn.commit()
        cur.close()
        return feedback_id

    def list_adaptive_thresholds(
        self,
        entity_type: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List adaptive thresholds."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["at.is_enabled = TRUE"]
        params = []

        if entity_type:
            conditions.append("at.entity_type = %s")
            params.append(entity_type)
        if location_id:
            conditions.append("at.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT * FROM adaptive_threshold at
            WHERE {where_clause}
            ORDER BY at.threshold_name
        """, params)

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def get_feedback_stats(
        self, location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get feedback loop statistics."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = []
        params = []

        if location_id:
            conditions.append("ao.location_id = %s")
            params.append(location_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT
                COUNT(*) as total_outcomes,
                COUNT(*) FILTER (WHERE outcome_type = 'effective') as effective,
                COUNT(*) FILTER (WHERE outcome_type = 'partially_effective') as partially_effective,
                COUNT(*) FILTER (WHERE outcome_type = 'ineffective') as ineffective,
                COUNT(*) FILTER (WHERE outcome_type = 'no_effect') as no_effect,
                COUNT(*) FILTER (WHERE outcome_type = 'counterproductive') as counterproductive,
                COUNT(*) FILTER (WHERE outcome_type = 'unknown') as unknown,
                COUNT(*) FILTER (WHERE feedback_applied = TRUE) as feedback_applied_count
            FROM action_outcome ao
            {where_clause}
        """, params)

        row = dict(cur.fetchone())

        cur.execute(f"""
            SELECT COUNT(*) as total, loop_type, status
            FROM feedback_loop fl
            {'WHERE fl.target_entity_id IS NOT NULL' if not location_id else ''}
            GROUP BY loop_type, status
        """)

        loop_stats = {}
        for r in cur.fetchall():
            r = dict(r)
            lt = r["loop_type"]
            if lt not in loop_stats:
                loop_stats[lt] = {"applied": 0, "proposed": 0, "rejected": 0}
            loop_stats[lt][r["status"]] = r["total"]

        cur.close()

        total = row["total_outcomes"] or 0
        effective = row["effective"] or 0

        return {
            "total_outcomes": total,
            "effective": effective,
            "partially_effective": row["partially_effective"] or 0,
            "ineffective": row["ineffective"] or 0,
            "no_effect": row["no_effect"] or 0,
            "counterproductive": row["counterproductive"] or 0,
            "unknown": row["unknown"] or 0,
            "effective_rate": effective / total if total > 0 else 0.0,
            "feedback_applied": row["feedback_applied_count"] or 0,
            "feedback_loops": loop_stats,
        }

    # --- Private helpers ---

    def _analyze_outcome(
        self, outcome: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze an outcome and generate a feedback signal."""
        outcome_type = outcome.get("outcome_type", "unknown")

        # Only generate feedback for assessed outcomes
        if outcome_type == "unknown":
            return None

        # Generate signal based on outcome type
        if outcome_type in ("ineffective", "counterproductive"):
            return {
                "outcome_id": str(outcome["id"]),
                "action_type": outcome["action_type"],
                "location_id": str(outcome["location_id"]),
                "signal": "negative",
                "recommendation": "Review and potentially revert this action pattern",
                "magnitude": 1.0 if outcome_type == "counterproductive" else 0.5,
            }

        if outcome_type == "effective":
            return {
                "outcome_id": str(outcome["id"]),
                "action_type": outcome["action_type"],
                "location_id": str(outcome["location_id"]),
                "signal": "positive",
                "recommendation": "Action pattern is effective — consider reinforcing",
                "magnitude": 0.5,
            }

        return None

    def _get_current_value(
        self,
        cur,
        target_entity: str,
        target_entity_id: Optional[str],
        target_field: str,
    ) -> Optional[Any]:
        """Get the current value of a target field."""
        if target_entity == "adaptive_threshold" and target_entity_id:
            cur.execute(
                f"SELECT {target_field} FROM adaptive_threshold WHERE id = %s",
                (target_entity_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

        return None
