"""Action Outcome Tracker — records and evaluates action results.

Provides utilities for measuring the effectiveness of actions taken
by the decision engine, agents, or manual interventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras


class ActionOutcomeTracker:
    """Tracks and evaluates action outcomes for feedback."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def measure_outcome(
        self,
        action_type: str,
        location_id: str,
        before_metrics: Optional[Dict[str, float]] = None,
        after_metrics: Optional[Dict[str, float]] = None,
        measurement_window_hours: int = 24,
    ) -> Dict[str, Any]:
        """Measure the outcome of an action by comparing metrics before/after.

        Args:
            action_type: Type of action to measure.
            location_id: Location where action was taken.
            before_metrics: Metric values before the action.
            after_metrics: Metric values after the action.
            measurement_window_hours: Hours to look back for after metrics.

        Returns:
            Outcome assessment with type, evidence, and deltas.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Auto-fetch after_metrics if not provided
        if after_metrics is None:
            after_metrics = self._fetch_recent_metrics(
                cur, location_id, measurement_window_hours
            )

        # Auto-fetch before_metrics if not provided
        if before_metrics is None:
            before_metrics = self._fetch_baseline_metrics(
                cur, location_id, measurement_window_hours
            )

        cur.close()

        # Compute deltas
        deltas = {}
        all_keys = set(list(before_metrics.keys()) + list(after_metrics.keys()))
        for key in all_keys:
            before_val = before_metrics.get(key)
            after_val = after_metrics.get(key)
            if before_val is not None and after_val is not None:
                deltas[key] = after_val - before_val

        # Evaluate effectiveness
        outcome = self._evaluate_effectiveness(action_type, deltas)

        return {
            "action_type": action_type,
            "location_id": location_id,
            "outcome_type": outcome,
            "deltas": deltas,
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "measurement_window_hours": measurement_window_hours,
        }

    def _fetch_recent_metrics(
        self,
        cur,
        location_id: str,
        window_hours: int,
    ) -> Dict[str, float]:
        """Fetch recent metric values for a location."""
        cur.execute("""
            SELECT md.metric_key, mv.value
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_definition_id
            WHERE mv.location_id = %s
            AND mv.verified = TRUE
            AND mv.computed_at > NOW() - INTERVAL '%s hours'
            ORDER BY mv.computed_at DESC
            LIMIT 50
        """, (location_id, window_hours))

        metrics = {}
        for row in cur.fetchall():
            row = dict(row)
            key = row["metric_key"]
            if key not in metrics:
                metrics[key] = float(row["value"])

        return metrics

    def _fetch_baseline_metrics(
        self,
        cur,
        location_id: str,
        lookback_hours: int,
    ) -> Dict[str, float]:
        """Fetch baseline metric values (before the action window)."""
        cur.execute("""
            SELECT md.metric_key, mv.value
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_definition_id
            WHERE mv.location_id = %s
            AND mv.verified = TRUE
            AND mv.computed_at <= NOW() - INTERVAL '%s hours'
            ORDER BY mv.computed_at DESC
            LIMIT 50
        """, (location_id, lookback_hours))

        metrics = {}
        for row in cur.fetchall():
            row = dict(row)
            key = row["metric_key"]
            if key not in metrics:
                metrics[key] = float(row["value"])

        return metrics

    def _evaluate_effectiveness(
        self,
        action_type: str,
        deltas: Dict[str, float],
    ) -> str:
        """Evaluate the effectiveness of an action based on metric deltas.

        Returns one of: 'effective', 'partially_effective', 'ineffective',
        'no_effect', 'counterproductive'.
        """
        if not deltas:
            return "unknown"

        # Count positive, negative, and neutral changes
        positive = sum(1 for v in deltas.values() if v > 0)
        negative = sum(1 for v in deltas.values() if v < 0)
        total = len(deltas)

        if total == 0:
            return "no_effect"

        positive_ratio = positive / total
        negative_ratio = negative / total

        if positive_ratio >= 0.7:
            return "effective"
        elif positive_ratio >= 0.4:
            return "partially_effective"
        elif negative_ratio >= 0.7:
            return "counterproductive"
        elif negative_ratio >= 0.4:
            return "ineffective"
        else:
            return "no_effect"
