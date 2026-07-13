"""ML Retraining Pipeline — scheduled retraining based on model performance degradation.

When accuracy drops below threshold, triggers retrain. Models get
better over time instead of degrading silently.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class MLRetrainingPipeline:
    """Monitors ML model health and triggers retraining when needed."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def check_models(
        self, location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Check all scheduled models for retraining triggers."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["ms.enabled = TRUE"]
        params: list = []

        if location_id:
            conditions.append("ms.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT ms.*
            FROM ml_retrain_schedule ms
            WHERE {where_clause}
            ORDER BY ms.model_name
        """, params)

        schedules = [dict(r) for r in cur.fetchall()]

        results = []
        for schedule in schedules:
            needs_retrain = False
            reason = None

            # Check if retrain is due by time
            if schedule.get("next_retrain_at"):
                if schedule["next_retrain_at"] <= datetime.now(timezone.utc):
                    needs_retrain = True
                    reason = "scheduled_interval"

            # Check last retrain time
            if not needs_retrain and schedule.get("last_retrain_at"):
                interval = schedule.get("retrain_interval_days", 30)
                next_due = schedule["last_retrain_at"] + timedelta(days=interval)
                if next_due <= datetime.now(timezone.utc):
                    needs_retrain = True
                    reason = "interval_elapsed"

            results.append({
                "model_name": schedule["model_name"],
                "location_id": schedule.get("location_id"),
                "needs_retrain": needs_retrain,
                "reason": reason,
                "accuracy_threshold": float(schedule.get("accuracy_threshold") or 20.0),
                "last_retrain_at": schedule.get("last_retrain_at"),
                "next_retrain_at": schedule.get("next_retrain_at"),
                "retrain_interval_days": schedule.get("retrain_interval_days"),
                "auto_retrain": schedule.get("auto_retrain", False),
            })

        cur.close()
        return results

    def trigger_retrain(
        self,
        model_name: str,
        location_id: Optional[str] = None,
        reason: str = "scheduled",
        trigger_metric: Optional[str] = None,
        trigger_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Trigger a retrain for a specific model."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Get current accuracy from schedule
        cur.execute("""
            SELECT accuracy_threshold FROM ml_retrain_schedule
            WHERE model_name = %s
              AND (%s IS NULL OR location_id = %s)
        """, (model_name, location_id, location_id))
        schedule = cur.fetchone()

        accuracy_threshold = float(schedule["accuracy_threshold"]) if schedule else 20.0

        cur.execute("""
            INSERT INTO ml_retrain_log (
                id, model_name, location_id, trigger_reason,
                trigger_metric, trigger_value,
                accuracy_before, status, started_at, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'running', %s, '{}')
        """, (
            log_id, model_name, location_id, reason,
            trigger_metric, trigger_value,
            accuracy_threshold, now,
        ))

        conn.commit()
        cur.close()

        return {
            "log_id": log_id,
            "model_name": model_name,
            "status": "running",
            "trigger_reason": reason,
        }

    def get_retrain_history(
        self,
        model_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get retraining history with accuracy before/after."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = []
        params: list = []

        if model_name:
            conditions.append("model_name = %s")
            params.append(model_name)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT * FROM ml_retrain_log
            {where_clause}
            ORDER BY started_at DESC
            LIMIT %s
        """, params + [limit])

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def configure_schedule(
        self,
        model_name: str,
        interval_days: int = 30,
        threshold: float = 20.0,
        auto_retrain: bool = False,
        location_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure retrain schedule for a model."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)
        schedule_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO ml_retrain_schedule (
                id, model_name, location_id, retrain_interval_days,
                accuracy_threshold, auto_retrain, enabled,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
            ON CONFLICT (model_name, COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid))
            DO UPDATE SET
                retrain_interval_days = EXCLUDED.retrain_interval_days,
                accuracy_threshold = EXCLUDED.accuracy_threshold,
                auto_retrain = EXCLUDED.auto_retrain,
                updated_at = NOW()
            RETURNING *
        """, (
            schedule_id, model_name, location_id,
            interval_days, threshold, auto_retrain,
            now, now,
        ))

        row = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return row

    def get_model_health(self) -> List[Dict[str, Any]]:
        """Get health status of all tracked ML models."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                ms.model_name,
                ms.location_id,
                ms.accuracy_threshold,
                ms.last_retrain_at,
                ms.retrain_interval_days,
                ms.auto_retrain,
                COUNT(mrl.id) as total_retrains,
                MAX(mrl.started_at) as last_retrain_started,
                MAX(mrl.accuracy_after) as last_accuracy_after,
                MAX(mrl.improvement_pct) as last_improvement_pct
            FROM ml_retrain_schedule ms
            LEFT JOIN ml_retrain_log mrl ON
                mrl.model_name = ms.model_name
                AND (mrl.location_id = ms.location_id
                     OR (mrl.location_id IS NULL AND ms.location_id IS NULL))
            WHERE ms.enabled = TRUE
            GROUP BY ms.model_name, ms.location_id, ms.accuracy_threshold,
                     ms.last_retrain_at, ms.retrain_interval_days, ms.auto_retrain
            ORDER BY ms.model_name
        """)

        models = []
        for r in cur.fetchall():
            r = dict(r)

            # Determine health status
            if r["last_retrain_at"] and r["retrain_interval_days"]:
                next_due = r["last_retrain_at"] + timedelta(days=r["retrain_interval_days"])
                overdue = next_due <= datetime.now(timezone.utc)
            else:
                overdue = False

            if r.get("last_accuracy_after") and r["last_accuracy_after"] > r["accuracy_threshold"]:
                health = "degraded"
            elif overdue:
                health = "overdue"
            else:
                health = "healthy"

            r["health_status"] = health
            r["next_retrain_due"] = (
                r["last_retrain_at"] + timedelta(days=r["retrain_interval_days"])
                if r.get("last_retrain_at") and r.get("retrain_interval_days")
                else None
            )
            models.append(r)

        cur.close()
        return models
