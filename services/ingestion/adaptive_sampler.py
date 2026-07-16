"""Adaptive Sensor Sampler — dynamically adjusts polling intervals.

Reads feedback signals from the OODA loop to increase sampling when
uncertainty is high and decrease it when stable to conserve resources.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class AdaptiveSampler:
    """Dynamically adjusts sensor sampling intervals."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def register_sensor(
        self,
        sensor_device_id: str,
        sensor_type: str,
        location_id: str,
        base_interval_minutes: int = 15,
        min_interval_minutes: int = 1,
        max_interval_minutes: int = 60,
    ) -> str:
        """Register a sensor for adaptive sampling.

        Args:
            sensor_device_id: UUID of the sensor device.
            sensor_type: Type of sensor (e.g., 'soil_moisture').
            location_id: UUID of the location.
            base_interval_minutes: Default polling interval.
            min_interval_minutes: Minimum interval (fastest polling).
            max_interval_minutes: Maximum interval (slowest polling).

        Returns:
            The config record ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        config_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO sampling_config (
                id, sensor_device_id, sensor_type, location_id,
                base_interval_minutes, adaptive_interval_minutes,
                min_interval_minutes, max_interval_minutes,
                reason, last_adjusted_at, adjustment_count,
                stable_since, is_enabled, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'initial', %s, 0, %s, TRUE, %s, %s)
            ON CONFLICT (sensor_device_id, sensor_type)
            DO UPDATE SET
                base_interval_minutes = EXCLUDED.base_interval_minutes,
                min_interval_minutes = EXCLUDED.min_interval_minutes,
                max_interval_minutes = EXCLUDED.max_interval_minutes,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """, (
            config_id, sensor_device_id, sensor_type, location_id,
            base_interval_minutes, base_interval_minutes,
            min_interval_minutes, max_interval_minutes,
            now, now, now, now,
        ))

        row = cur.fetchone()
        conn.commit()
        cur.close()
        return str(row["id"]) if row else config_id

    def get_interval(
        self, sensor_device_id: str, sensor_type: str
    ) -> int:
        """Get the current adaptive interval for a sensor.

        Returns:
            Current interval in minutes.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT adaptive_interval_minutes
            FROM sampling_config
            WHERE sensor_device_id = %s AND sensor_type = %s
            AND is_enabled = TRUE
        """, (sensor_device_id, sensor_type))

        row = cur.fetchone()
        cur.close()

        if row is None:
            return 15  # Default fallback

        return row["adaptive_interval_minutes"]

    def increase_sampling(
        self,
        sensor_device_id: str,
        sensor_type: str,
        factor: float = 0.5,
        reason: str = "high_uncertainty",
    ) -> Dict[str, Any]:
        """Increase sampling rate (decrease interval).

        Args:
            sensor_device_id: UUID of the sensor.
            sensor_type: Type of sensor.
            factor: Multiplier for interval (0.5 = double the rate).
            reason: Reason for the adjustment.

        Returns:
            Updated config with old and new intervals.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        cur.execute("""
            SELECT id, adaptive_interval_minutes, min_interval_minutes
            FROM sampling_config
            WHERE sensor_device_id = %s AND sensor_type = %s
            AND is_enabled = TRUE
            FOR UPDATE
        """, (sensor_device_id, sensor_type))

        row = cur.fetchone()
        if row is None:
            cur.close()
            return {"error": "Sensor not registered for adaptive sampling"}

        row = dict(row)
        old_interval = row["adaptive_interval_minutes"]
        min_interval = row["min_interval_minutes"]
        config_id = row["id"]

        new_interval = max(min_interval, int(old_interval * factor))

        if new_interval == old_interval:
            cur.close()
            return {
                "adjusted": False,
                "reason": "already_at_minimum",
                "current_interval": old_interval,
            }

        cur.execute("""
            UPDATE sampling_config
            SET adaptive_interval_minutes = %s,
                reason = %s,
                last_adjusted_at = %s,
                adjustment_count = adjustment_count + 1,
                stable_since = NULL,
                updated_at = %s
            WHERE id = %s
        """, (new_interval, reason, now, now, config_id))

        # Log the adjustment
        cur.execute("""
            INSERT INTO sampling_adjustment_log (
                id, config_id, previous_interval, new_interval,
                reason, trigger_source, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'feedback_controller', %s)
        """, (
            str(uuid.uuid4()), config_id, old_interval, new_interval,
            reason, now,
        ))

        conn.commit()
        cur.close()

        return {
            "adjusted": True,
            "previous_interval": old_interval,
            "new_interval": new_interval,
            "reason": reason,
        }

    def decrease_sampling(
        self,
        sensor_device_id: str,
        sensor_type: str,
        factor: float = 1.5,
        reason: str = "stable_period",
    ) -> Dict[str, Any]:
        """Decrease sampling rate (increase interval).

        Args:
            sensor_device_id: UUID of the sensor.
            sensor_type: Type of sensor.
            factor: Multiplier for interval (1.5 = 33% slower rate).
            reason: Reason for the adjustment.

        Returns:
            Updated config with old and new intervals.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        cur.execute("""
            SELECT id, adaptive_interval_minutes, max_interval_minutes
            FROM sampling_config
            WHERE sensor_device_id = %s AND sensor_type = %s
            AND is_enabled = TRUE
            FOR UPDATE
        """, (sensor_device_id, sensor_type))

        row = cur.fetchone()
        if row is None:
            cur.close()
            return {"error": "Sensor not registered for adaptive sampling"}

        row = dict(row)
        old_interval = row["adaptive_interval_minutes"]
        max_interval = row["max_interval_minutes"]
        config_id = row["id"]

        new_interval = min(max_interval, int(old_interval * factor))

        if new_interval == old_interval:
            cur.close()
            return {
                "adjusted": False,
                "reason": "already_at_maximum",
                "current_interval": old_interval,
            }

        cur.execute("""
            UPDATE sampling_config
            SET adaptive_interval_minutes = %s,
                reason = %s,
                last_adjusted_at = %s,
                adjustment_count = adjustment_count + 1,
                updated_at = %s
            WHERE id = %s
        """, (new_interval, reason, now, now, config_id))

        # Log the adjustment
        cur.execute("""
            INSERT INTO sampling_adjustment_log (
                id, config_id, previous_interval, new_interval,
                reason, trigger_source, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'feedback_controller', %s)
        """, (
            str(uuid.uuid4()), config_id, old_interval, new_interval,
            reason, now,
        ))

        conn.commit()
        cur.close()

        return {
            "adjusted": True,
            "previous_interval": old_interval,
            "new_interval": new_interval,
            "reason": reason,
        }

    def check_stability(
        self,
        sensor_device_id: str,
        sensor_type: str,
        stable_threshold_days: int = 7,
    ) -> Dict[str, Any]:
        """Check if a sensor has been stable and should have reduced sampling.

        A sensor is considered stable if it has had no anomalies for
        stable_threshold_days days.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM sensor_alert sa
                 JOIN sensor_device sd ON sd.id = sa.sensor_device_id
                 WHERE sd.id = %s AND sd.sensor_type = %s
                   AND sa.created_at > NOW() - INTERVAL '%s days') AS anomaly_count,
                (SELECT COUNT(*) FROM sensor_reading sr
                 WHERE sr.sensor_id = %s
                   AND sr.created_at > NOW() - INTERVAL '%s days') AS observation_count
        """, (sensor_device_id, sensor_type, stable_threshold_days, sensor_device_id, stable_threshold_days))

        row = cur.fetchone()
        anomaly_count = row["anomaly_count"] if row else 0
        observation_count = row.get("observation_count", 0) if row else 0

        cur.close()

        return {
            "stable": anomaly_count == 0 and observation_count > 0,
            "anomaly_count": anomaly_count,
            "observation_count": observation_count,
            "threshold_days": stable_threshold_days,
        }

    def list_configs(
        self,
        location_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all adaptive sampling configs."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["sc.is_enabled = TRUE"]
        params = []

        if location_id:
            conditions.append("sc.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT
                sc.*,
                sd.device_id as device_name,
                (SELECT COUNT(*)
                 FROM sampling_adjustment_log sal
                 WHERE sal.config_id = sc.id
                 AND sal.created_at > NOW() - INTERVAL '7 days'
                ) as recent_adjustments
            FROM sampling_config sc
            LEFT JOIN sensor_device sd ON sd.id = sc.sensor_device_id
            WHERE {where_clause}
            ORDER BY sc.sensor_type, sc.sensor_device_id
        """, params)

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def get_adjustment_history(
        self,
        sensor_device_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent sampling adjustments."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = []
        params = []

        if sensor_device_id:
            conditions.append("sc.sensor_device_id = %s")
            params.append(sensor_device_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur.execute(f"""
            SELECT
                sal.*,
                sc.sensor_device_id,
                sc.sensor_type,
                sc.location_id
            FROM sampling_adjustment_log sal
            JOIN sampling_config sc ON sc.id = sal.config_id
            {where_clause}
            ORDER BY sal.created_at DESC
            LIMIT %s
        """, params + [limit])

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
