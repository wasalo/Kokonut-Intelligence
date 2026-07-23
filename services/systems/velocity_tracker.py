"""Adaptation Velocity Tracker — measures whether the system is getting faster at learning.

Tracks OODA cycle times, feedback rates, effectiveness trends, and
time-to-action to determine if the system is accelerating, stable,
or decelerating in its adaptation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class AdaptationVelocityTracker:
    """Tracks and classifies adaptation velocity over time."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def compute_velocity(
        self, location_id: str, period_days: int = 30
    ) -> Dict[str, Any]:
        """Compute OODA cycle velocity, feedback velocity, effectiveness
        velocity, and time-to-action for a location.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)
        period_start = now
        period_end = now

        # --- OODA velocity ---
        cur.execute("""
            SELECT
                AVG(total_cycle_time_ms) as avg_cycle_time_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_cycle_time_ms)
                    as median_cycle_time_ms,
                COUNT(*) as cycles_completed
            FROM ooda_cycle_log
            WHERE location_id = %s
              AND status = 'completed'
              AND created_at > NOW() - INTERVAL '%s days'
        """, (location_id, period_days))
        ooda_row = cur.fetchone()

        avg_cycle_ms = None
        median_cycle_ms = None
        cycles_completed = 0
        if ooda_row and ooda_row["cycles_completed"] and ooda_row["cycles_completed"] > 0:
            avg_cycle_ms = float(ooda_row["avg_cycle_time_ms"]) if ooda_row["avg_cycle_time_ms"] else None
            median_cycle_ms = float(ooda_row["median_cycle_time_ms"]) if ooda_row["median_cycle_time_ms"] else None
            cycles_completed = ooda_row["cycles_completed"]

        # --- Feedback velocity ---
        cur.execute("""
            SELECT
                COUNT(*) as total_feedback,
                SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) as applied_feedback
            FROM feedback_loop
            WHERE created_at > NOW() - INTERVAL '%s days'
              AND (%s IS NULL OR target_entity_id IN (
                  SELECT id FROM adaptive_threshold WHERE location_id = %s
              ))
        """, (period_days, location_id, location_id))
        fb_row = cur.fetchone()

        total_fb = fb_row.get("total_feedback", 0) if fb_row else 0
        applied_fb = fb_row.get("applied_feedback", 0) if fb_row else 0
        feedback_rate = round(total_fb / max(period_days, 1), 2)
        feedback_success_rate = round(
            (applied_fb / total_fb * 100) if total_fb > 0 else 0.0, 2
        )

        # --- Effectiveness velocity ---
        cur.execute("""
            SELECT
                AVG(CASE
                    WHEN outcome_type = 'effective' THEN 100.0
                    WHEN outcome_type = 'partially_effective' THEN 60.0
                    WHEN outcome_type = 'no_effect' THEN 30.0
                    WHEN outcome_type = 'ineffective' THEN 10.0
                    WHEN outcome_type = 'counterproductive' THEN 0.0
                    ELSE 50.0
                END) as avg_effectiveness_pct
            FROM action_outcome
            WHERE location_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
        """, (location_id, period_days))
        eff_row = cur.fetchone()

        avg_effectiveness = None
        if eff_row and eff_row["avg_effectiveness_pct"] is not None:
            avg_effectiveness = round(float(eff_row["avg_effectiveness_pct"]), 2)

        # --- Trend computation (compare current period vs prior period) ---
        cycle_time_trend = self._compute_cycle_time_trend(cur, location_id, period_days)
        feedback_velocity_trend = self._compute_feedback_trend(cur, location_id, period_days)
        effectiveness_trend = self._compute_effectiveness_trend(cur, location_id, period_days)
        time_to_action_trend = self._compute_time_to_action_trend(cur, location_id, period_days)

        # --- Time-to-action (observe→act duration) ---
        cur.execute("""
            SELECT AVG(
                EXTRACT(EPOCH FROM (act_completed_at - observe_started_at)) / 3600
            ) as avg_hours
            FROM ooda_cycle_log
            WHERE location_id = %s
              AND status = 'completed'
              AND observe_started_at IS NOT NULL
              AND act_completed_at IS NOT NULL
              AND created_at > NOW() - INTERVAL '%s days'
        """, (location_id, period_days))
        tta_row = cur.fetchone()
        avg_time_to_action = None
        if tta_row and tta_row["avg_hours"] is not None:
            avg_time_to_action = round(float(tta_row["avg_hours"]), 2)

        # --- Moving averages for effectiveness ---
        ma7 = self._compute_effectiveness_ma(cur, location_id, 7)
        ma30 = self._compute_effectiveness_ma(cur, location_id, 30)

        # --- Acceleration score ---
        acceleration_score = self._compute_acceleration_score(
            cycle_time_trend, feedback_velocity_trend, effectiveness_trend
        )

        velocity_status = self._classify_status(acceleration_score, cycles_completed)

        cur.close()

        result = {
            "location_id": location_id,
            "period_days": period_days,
            "avg_cycle_time_ms": avg_cycle_ms,
            "median_cycle_time_ms": median_cycle_ms,
            "cycles_completed": cycles_completed,
            "cycle_time_trend": cycle_time_trend,
            "feedback_rate": feedback_rate,
            "feedback_success_rate": feedback_success_rate,
            "feedback_velocity_trend": feedback_velocity_trend,
            "avg_effectiveness_pct": avg_effectiveness,
            "effectiveness_trend": effectiveness_trend,
            "effectiveness_ma7": ma7,
            "effectiveness_ma30": ma30,
            "avg_time_to_insight_hours": avg_time_to_action,
            "avg_time_to_action_hours": avg_time_to_action,
            "time_to_action_trend": time_to_action_trend,
            "velocity_status": velocity_status,
            "acceleration_score": acceleration_score,
        }

        return result

    def compute_trend(
        self, location_id: str, metric: str, window_periods: int = 4
    ) -> Dict[str, Any]:
        """Compute trend direction and magnitude for a given metric."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                metric_name,
                metric_domain,
                trend_direction,
                trend_strength,
                periods_in_trend,
                pct_change,
                learning_rate,
                estimated_plateau,
                projected_plateau_periods,
                created_at
            FROM improvement_rate
            WHERE location_id = %s AND metric_name = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (location_id, metric, window_periods))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

        if not rows:
            return {
                "metric": metric,
                "trend_direction": "insufficient_data",
                "trend_strength": 0.0,
                "periods_in_trend": 0,
                "data_points": 0,
            }

        latest = rows[0]
        return {
            "metric": metric,
            "trend_direction": latest.get("trend_direction", "stable"),
            "trend_strength": float(latest.get("trend_strength") or 0.0),
            "periods_in_trend": latest.get("periods_in_trend") or 0,
            "learning_rate": float(latest.get("learning_rate") or 0.0),
            "estimated_plateau": float(latest.get("estimated_plateau") or 0.0),
            "data_points": len(rows),
        }

    def classify_acceleration(self, location_id: str) -> Dict[str, Any]:
        """Classify the system as accelerating/stable/decelerating/stalled."""
        velocity = self.compute_velocity(location_id, period_days=30)
        return {
            "location_id": location_id,
            "velocity_status": velocity["velocity_status"],
            "acceleration_score": velocity["acceleration_score"],
            "avg_effectiveness_pct": velocity["avg_effectiveness_pct"],
            "feedback_rate": velocity["feedback_rate"],
            "avg_cycle_time_ms": velocity["avg_cycle_time_ms"],
            "cycles_completed": velocity["cycles_completed"],
        }

    def get_velocity_history(
        self, location_id: str, limit: int = 12
    ) -> List[Dict[str, Any]]:
        """Get historical velocity logs."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM adaptation_velocity_log
            WHERE location_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (location_id, limit))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def record_velocity(
        self, location_id: str, period_days: int = 30
    ) -> Dict[str, Any]:
        """Compute and persist a velocity snapshot."""
        velocity = self.compute_velocity(location_id, period_days)

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)
        log_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO adaptation_velocity_log (
                id, location_id, period_start, period_end,
                avg_cycle_time_ms, median_cycle_time_ms, cycles_completed,
                cycle_time_trend,
                feedback_rate, feedback_success_rate, feedback_velocity_trend,
                avg_effectiveness_pct, effectiveness_trend,
                effectiveness_ma7, effectiveness_ma30,
                avg_time_to_insight_hours, avg_time_to_action_hours,
                time_to_action_trend,
                velocity_status, acceleration_score,
                created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s
            )
        """, (
            log_id, location_id, now, now,
            velocity["avg_cycle_time_ms"], velocity["median_cycle_time_ms"],
            velocity["cycles_completed"], velocity["cycle_time_trend"],
            velocity["feedback_rate"], velocity["feedback_success_rate"],
            velocity["feedback_velocity_trend"],
            velocity["avg_effectiveness_pct"], velocity["effectiveness_trend"],
            velocity["effectiveness_ma7"], velocity["effectiveness_ma30"],
            velocity["avg_time_to_insight_hours"],
            velocity["avg_time_to_action_hours"],
            velocity["time_to_action_trend"],
            velocity["velocity_status"], velocity["acceleration_score"],
            now,
        ))

        conn.commit()
        cur.close()

        velocity["id"] = log_id
        return velocity

    def get_global_velocity(self) -> Dict[str, Any]:
        """Compute aggregate velocity across all locations."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                AVG(avg_cycle_time_ms) as global_avg_cycle_ms,
                AVG(feedback_rate) as global_feedback_rate,
                AVG(feedback_success_rate) as global_feedback_success,
                AVG(avg_effectiveness_pct) as global_effectiveness,
                AVG(acceleration_score) as global_acceleration,
                COUNT(DISTINCT location_id) as locations_tracked,
                SUM(cycles_completed) as total_cycles
            FROM adaptation_velocity_log
            WHERE created_at > NOW() - INTERVAL '30 days'
        """)
        row = cur.fetchone()
        cur.close()

        if not row or row["locations_tracked"] is None:
            return {
                "status": "insufficient_data",
                "locations_tracked": 0,
                "global_acceleration_score": 0.0,
            }

        global_accel = float(row["global_acceleration"] or 0.0)
        return {
            "status": self._classify_status(global_accel, row["total_cycles"] or 0),
            "locations_tracked": row["locations_tracked"],
            "global_avg_cycle_ms": float(row["global_avg_cycle_ms"]) if row["global_avg_cycle_ms"] else None,
            "global_feedback_rate": float(row["global_feedback_rate"]) if row["global_feedback_rate"] else None,
            "global_feedback_success_rate": float(row["global_feedback_success"]) if row["global_feedback_success"] else None,
            "global_effectiveness_pct": float(row["global_effectiveness"]) if row["global_effectiveness"] else None,
            "global_acceleration_score": global_accel,
            "total_cycles": row["total_cycles"] or 0,
        }

    # --- Private helpers ---

    def _compute_cycle_time_trend(
        self, cur, location_id: str, period_days: int
    ) -> Optional[float]:
        """Compare current period avg cycle time vs prior period. Negative = faster."""
        cur.execute("""
            WITH periods AS (
                SELECT total_cycle_time_ms,
                    CASE WHEN created_at > NOW() - INTERVAL '%s days'
                        THEN 'current' ELSE 'prior' END as period
                FROM ooda_cycle_log
                WHERE location_id = %s
                  AND status = 'completed'
                  AND created_at > NOW() - INTERVAL '%s days'
            )
            SELECT period, AVG(total_cycle_time_ms) as avg_ms
            FROM periods
            GROUP BY period
        """, (period_days, location_id, period_days * 2))
        rows = {r["period"]: float(r["avg_ms"]) for r in cur.fetchall() if r["avg_ms"]}

        if "current" in rows and "prior" in rows and rows["prior"] > 0:
            return round((rows["current"] - rows["prior"]) / rows["prior"] * 100, 2)
        return None

    def _compute_feedback_trend(
        self, cur, location_id: str, period_days: int
    ) -> Optional[float]:
        """Compare current period feedback rate vs prior period."""
        cur.execute("""
            WITH periods AS (
                SELECT
                    CASE WHEN created_at > NOW() - INTERVAL '%s days'
                        THEN 'current' ELSE 'prior' END as period,
                    COUNT(*) as cnt
                FROM feedback_loop
                WHERE created_at > NOW() - INTERVAL '%s days'
                GROUP BY period
            )
            SELECT period, cnt FROM periods
        """, (period_days, period_days * 2))
        rows = {r["period"]: r["cnt"] for r in cur.fetchall()}

        if "current" in rows and "prior" in rows and rows["prior"] > 0:
            return round((rows["current"] - rows["prior"]) / rows["prior"] * 100, 2)
        return None

    def _compute_effectiveness_trend(
        self, cur, location_id: str, period_days: int
    ) -> Optional[float]:
        """Compare current period effectiveness vs prior period."""
        def _avg_eff(where_clause, params):
            cur.execute(f"""
                SELECT AVG(CASE
                    WHEN outcome_type = 'effective' THEN 100.0
                    WHEN outcome_type = 'partially_effective' THEN 60.0
                    WHEN outcome_type = 'no_effect' THEN 30.0
                    WHEN outcome_type = 'ineffective' THEN 10.0
                    WHEN outcome_type = 'counterproductive' THEN 0.0
                    ELSE 50.0
                END) as avg_eff
                FROM action_outcome
                WHERE {where_clause}
            """, params)
            row = cur.fetchone()
            return float(row["avg_eff"]) if row and row["avg_eff"] else None

        current = _avg_eff(
            "location_id = %s AND created_at > NOW() - INTERVAL '%s days'",
            (location_id, period_days),
        )
        prior = _avg_eff(
            "location_id = %s AND created_at > NOW() - INTERVAL '%s days' AND created_at <= NOW() - INTERVAL '%s days'",
            (location_id, period_days * 2, period_days),
        )

        if current is not None and prior is not None and prior > 0:
            return round((current - prior) / prior * 100, 2)
        return None

    def _compute_time_to_action_trend(
        self, cur, location_id: str, period_days: int
    ) -> Optional[float]:
        """Compare time-to-action between current and prior periods."""
        cur.execute("""
            WITH periods AS (
                SELECT
                    EXTRACT(EPOCH FROM (act_completed_at - observe_started_at)) / 3600 as hours,
                    CASE WHEN created_at > NOW() - INTERVAL '%s days'
                        THEN 'current' ELSE 'prior' END as period
                FROM ooda_cycle_log
                WHERE location_id = %s
                  AND status = 'completed'
                  AND observe_started_at IS NOT NULL
                  AND act_completed_at IS NOT NULL
                  AND created_at > NOW() - INTERVAL '%s days'
            )
            SELECT period, AVG(hours) as avg_hours
            FROM periods
            GROUP BY period
        """, (period_days, location_id, period_days * 2))
        rows = {r["period"]: float(r["avg_hours"]) for r in cur.fetchall() if r["avg_hours"]}

        if "current" in rows and "prior" in rows and rows["prior"] > 0:
            return round((rows["current"] - rows["prior"]) / rows["prior"] * 100, 2)
        return None

    def _compute_effectiveness_ma(
        self, cur, location_id: str, window_days: int
    ) -> Optional[float]:
        """Compute moving average effectiveness over window_days."""
        cur.execute("""
            SELECT AVG(CASE
                WHEN outcome_type = 'effective' THEN 100.0
                WHEN outcome_type = 'partially_effective' THEN 60.0
                WHEN outcome_type = 'no_effect' THEN 30.0
                WHEN outcome_type = 'ineffective' THEN 10.0
                WHEN outcome_type = 'counterproductive' THEN 0.0
                ELSE 50.0
            END) as avg_eff
            FROM action_outcome
            WHERE location_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
        """, (location_id, window_days))
        row = cur.fetchone()
        if row and row["avg_eff"] is not None:
            return round(float(row["avg_eff"]), 2)
        return None

    def _compute_acceleration_score(
        self,
        cycle_time_trend: Optional[float],
        feedback_trend: Optional[float],
        effectiveness_trend: Optional[float],
    ) -> float:
        """Compute composite acceleration score (-100 to +100)."""
        scores = []
        if cycle_time_trend is not None:
            # Negative cycle time trend = faster = positive acceleration
            scores.append(-cycle_time_trend)
        if feedback_trend is not None:
            scores.append(feedback_trend)
        if effectiveness_trend is not None:
            scores.append(effectiveness_trend)

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 2)

    def _classify_status(
        self, acceleration_score: float, cycles_completed: int
    ) -> str:
        """Classify velocity status from acceleration score."""
        if cycles_completed < 3:
            return "insufficient_data"
        if acceleration_score > 10.0:
            return "accelerating"
        if acceleration_score > -5.0:
            return "stable"
        if acceleration_score > -20.0:
            return "decelerating"
        return "stalled"
