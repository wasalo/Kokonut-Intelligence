"""Improvement Rate Tracker — tracks whether metrics are getting better over time.

Computes trend analysis, improvement velocity, learning curves, and
plateau detection for tracked metrics across all domains.
"""

from __future__ import annotations

import uuid
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class ImprovementRateTracker:
    """Tracks improvement rates and learning curves for metrics."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def record_improvement(
        self,
        location_id: Optional[str],
        metric_name: str,
        current_value: float,
        period_start: datetime,
        period_end: datetime,
        metric_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a metric value and compute trend/improvement rate."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        record_id = str(uuid.uuid4())

        # Get prior value
        cur.execute("""
            SELECT current_value, baseline_value
            FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (location_id, location_id, metric_name))
        prior = cur.fetchone()

        prior_value = float(prior["current_value"]) if prior and prior["current_value"] is not None else None
        baseline_value = float(prior["baseline_value"]) if prior and prior["baseline_value"] is not None else current_value

        absolute_change = round(current_value - prior_value, 4) if prior_value is not None else None
        pct_change = round((absolute_change / prior_value * 100), 4) if prior_value and prior_value != 0 else None
        change_from_baseline = round((current_value - baseline_value) / baseline_value * 100, 4) if baseline_value and baseline_value != 0 else None

        # Trend computation from recent history
        trend_direction, trend_strength, periods_in_trend = self._compute_trend(
            cur, location_id, metric_name
        )

        # Learning rate and plateau estimation
        learning_rate, estimated_plateau, projected_periods = self._estimate_learning_curve(
            cur, location_id, metric_name
        )

        cur.execute("""
            INSERT INTO improvement_rate (
                id, location_id, metric_name, metric_domain,
                period_start, period_end,
                current_value, prior_value, baseline_value,
                absolute_change, pct_change, change_from_baseline,
                trend_direction, trend_strength, periods_in_trend,
                learning_rate, estimated_plateau, projected_plateau_periods,
                created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                NOW()
            )
        """, (
            record_id, location_id, metric_name, metric_domain,
            period_start, period_end,
            current_value, prior_value, baseline_value,
            absolute_change, pct_change, change_from_baseline,
            trend_direction, trend_strength, periods_in_trend,
            learning_rate, estimated_plateau, projected_periods,
        ))

        conn.commit()
        cur.close()

        return {
            "id": record_id,
            "metric_name": metric_name,
            "current_value": current_value,
            "prior_value": prior_value,
            "absolute_change": absolute_change,
            "pct_change": pct_change,
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "learning_rate": learning_rate,
        }

    def get_improvement_report(
        self,
        location_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get improvement report for tracked metrics."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["1=1"]
        params: list = []

        if location_id:
            conditions.append("ir.location_id = %s")
            params.append(location_id)
        if domain:
            conditions.append("ir.metric_domain = %s")
            params.append(domain)

        where_clause = " AND ".join(conditions)

        # Get latest record per metric
        cur.execute(f"""
            SELECT DISTINCT ON (ir.metric_name)
                ir.metric_name,
                ir.metric_domain,
                ir.current_value,
                ir.pct_change,
                ir.trend_direction,
                ir.trend_strength,
                ir.learning_rate,
                ir.estimated_plateau,
                ir.projected_plateau_periods,
                ir.created_at
            FROM improvement_rate ir
            WHERE {where_clause}
            ORDER BY ir.metric_name, ir.created_at DESC
        """, params)

        metrics = [dict(r) for r in cur.fetchall()]
        cur.close()

        improving = sum(1 for m in metrics if m.get("trend_direction") == "improving")
        degrading = sum(1 for m in metrics if m.get("trend_direction") == "degrading")
        stable = sum(1 for m in metrics if m.get("trend_direction") == "stable")

        return {
            "total_metrics": len(metrics),
            "improving": improving,
            "degrading": degrading,
            "stable": stable,
            "metrics": metrics,
        }

    def detect_plateau(
        self, location_id: Optional[str], metric_name: str
    ) -> Dict[str, Any]:
        """Detect if a metric has plateaued."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT current_value, created_at
            FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (location_id, location_id, metric_name))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

        if len(rows) < 4:
            return {
                "metric": metric_name,
                "plateau_detected": False,
                "reason": "insufficient_data",
                "data_points": len(rows),
            }

        values = [float(r["current_value"]) for r in rows if r["current_value"] is not None]

        if len(values) < 4:
            return {
                "metric": metric_name,
                "plateau_detected": False,
                "reason": "insufficient_values",
            }

        # Check if recent values have low variance (plateau indicator)
        recent = values[:5]
        older = values[5:] if len(values) > 5 else values

        recent_mean = statistics.mean(recent)
        recent_stdev = statistics.stdev(recent) if len(recent) > 1 else 0.0

        # Coefficient of variation
        cv = (recent_stdev / abs(recent_mean) * 100) if recent_mean != 0 else 0.0

        plateau_detected = cv < 5.0  # Less than 5% variation = plateau

        return {
            "metric": metric_name,
            "plateau_detected": plateau_detected,
            "recent_mean": round(recent_mean, 4),
            "recent_stdev": round(recent_stdev, 4),
            "coefficient_of_variation_pct": round(cv, 2),
            "data_points": len(rows),
        }

    def detect_degradation(
        self, location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect metrics that are degrading."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["trend_direction = 'degrading'"]
        params: list = []

        if location_id:
            conditions.append("location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT DISTINCT ON (metric_name)
                metric_name, metric_domain, current_value, pct_change,
                trend_strength, periods_in_trend, created_at
            FROM improvement_rate
            WHERE {where_clause}
            ORDER BY metric_name, created_at DESC
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def get_learning_curve(
        self, location_id: Optional[str], metric_name: str
    ) -> Dict[str, Any]:
        """Get learning curve data: historical values, trend line, projected plateau."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT current_value, pct_change, learning_rate,
                   estimated_plateau, projected_plateau_periods,
                   period_start, created_at
            FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
            ORDER BY created_at ASC
        """, (location_id, location_id, metric_name))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

        if not rows:
            return {"metric": metric_name, "data_points": 0, "values": []}

        values = [
            {
                "value": float(r["current_value"]) if r["current_value"] is not None else None,
                "pct_change": float(r["pct_change"]) if r["pct_change"] is not None else None,
                "date": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

        latest = rows[-1]
        return {
            "metric": metric_name,
            "data_points": len(rows),
            "values": values,
            "learning_rate": float(latest["learning_rate"]) if latest.get("learning_rate") else None,
            "estimated_plateau": float(latest["estimated_plateau"]) if latest.get("estimated_plateau") else None,
            "projected_plateau_periods": latest.get("projected_plateau_periods"),
            "first_value": values[0]["value"] if values else None,
            "latest_value": values[-1]["value"] if values else None,
        }

    def get_improvement_history(
        self, location_id: Optional[str], metric_name: str, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Get time-series of a specific improvement metric."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (location_id, location_id, metric_name, limit))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # --- Private helpers ---

    def _compute_trend(
        self, cur, location_id: Optional[str], metric_name: str
    ) -> tuple:
        """Compute trend direction, strength, and consecutive periods."""
        cur.execute("""
            SELECT pct_change, created_at
            FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
              AND pct_change IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 10
        """, (location_id, location_id, metric_name))

        rows = cur.fetchall()

        if len(rows) < 2:
            return ("stable", 0.0, 0)

        changes = [float(r["pct_change"]) for r in rows]

        # Count consecutive same-direction changes
        direction = "improving" if changes[0] > 0 else "degrading" if changes[0] < 0 else "stable"
        consecutive = 0
        for c in changes:
            if (direction == "improving" and c > 0) or \
               (direction == "degrading" and c < 0) or \
               (direction == "stable" and c == 0):
                consecutive += 1
            else:
                break

        # Strength: consistency of direction
        if direction == "improving":
            consistency = sum(1 for c in changes if c > 0) / len(changes)
        elif direction == "degrading":
            consistency = sum(1 for c in changes if c < 0) / len(changes)
        else:
            consistency = sum(1 for c in changes if c == 0) / len(changes)

        return (direction, round(consistency, 2), consecutive)

    def _estimate_learning_curve(
        self, cur, location_id: Optional[str], metric_name: str
    ) -> tuple:
        """Estimate learning rate, plateau, and time to plateau."""
        cur.execute("""
            SELECT current_value, created_at
            FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
              AND current_value IS NOT NULL
            ORDER BY created_at ASC
        """, (location_id, location_id, metric_name))

        rows = cur.fetchall()

        if len(rows) < 3:
            return (None, None, None)

        values = [float(r["current_value"]) for r in rows]

        # Simple linear regression for learning rate
        n = len(values)
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        if denominator == 0:
            return (None, None, None)

        learning_rate = round(numerator / denominator, 4)

        # Plateau estimation: if learning rate is near zero, we're plateaued
        if abs(learning_rate) < 0.001:
            estimated_plateau = round(values[-1], 4)
            projected_periods = 0
        else:
            # Estimate plateau as where the trend line flattens (simplified)
            estimated_plateau = round(values[-1] + learning_rate * 10, 4)
            projected_periods = None  # Would need more complex fitting

        return (learning_rate, estimated_plateau, projected_periods)
