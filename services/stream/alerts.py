"""Real-time alert evaluation for stream processing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from services.common.logging import get_logger

logger = get_logger("stream.alerts")


class StreamAlertEvaluator:
    """Evaluates stream data against alert rules and creates stream_alert records."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def evaluate_threshold(
        self,
        sensor_device_id: str,
        metric: str,
        value: float,
        threshold: float,
        operator: str = "gt",
        severity: str = "warning",
    ) -> str | None:
        """Evaluate a value against a threshold. Returns alert ID if triggered."""
        triggered = False
        if operator == "gt" and value > threshold:
            triggered = True
        elif operator == "lt" and value < threshold:
            triggered = True
        elif operator == "gte" and value >= threshold:
            triggered = True
        elif operator == "lte" and value <= threshold:
            triggered = True
        elif operator == "eq" and abs(value - threshold) < 0.001:
            triggered = True

        if not triggered:
            return None

        return self._create_alert(
            sensor_device_id=sensor_device_id,
            alert_type="threshold",
            severity=severity,
            metric=metric,
            value=value,
            threshold=threshold,
            message=f"{metric} {operator} {threshold}: value={value}",
        )

    def evaluate_spike(
        self,
        sensor_device_id: str,
        metric: str,
        current_value: float,
        baseline_value: float,
        deviation: float,
        threshold: float = 0.3,
    ) -> str | None:
        """Evaluate spike detection result."""
        if deviation <= threshold:
            return None

        severity = "critical" if deviation > threshold * 2 else "warning"
        return self._create_alert(
            sensor_device_id=sensor_device_id,
            alert_type="spike",
            severity=severity,
            metric=metric,
            value=current_value,
            threshold=baseline_value,
            message=f"Spike detected: {metric}={current_value} (baseline={baseline_value}, deviation={deviation:.1%})",
        )

    def evaluate_gap(
        self,
        sensor_device_id: str,
        metric: str,
        gap_minutes: int,
        threshold_minutes: int = 30,
    ) -> str | None:
        """Evaluate data gap detection."""
        if gap_minutes < threshold_minutes:
            return None

        severity = "critical" if gap_minutes > threshold_minutes * 4 else "warning"
        return self._create_alert(
            sensor_device_id=sensor_device_id,
            alert_type="gap",
            severity=severity,
            metric=metric,
            value=float(gap_minutes),
            threshold=float(threshold_minutes),
            message=f"Data gap: {metric} no data for {gap_minutes}min (threshold={threshold_minutes}min)",
        )

    def evaluate_rate_of_change(
        self,
        sensor_device_id: str,
        metric: str,
        rate: float,
        threshold: float,
        operator: str = "gt",
        severity: str = "warning",
    ) -> str | None:
        """Evaluate rate of change."""
        triggered = False
        if operator == "gt" and rate > threshold:
            triggered = True
        elif operator == "lt" and rate < threshold:
            triggered = True

        if not triggered:
            return None

        return self._create_alert(
            sensor_device_id=sensor_device_id,
            alert_type="rate_of_change",
            severity=severity,
            metric=metric,
            value=rate,
            threshold=threshold,
            message=f"Rate of change: {metric} rate={rate:.2f}/hr (threshold={threshold})",
        )

    def _create_alert(
        self,
        sensor_device_id: str,
        alert_type: str,
        severity: str,
        metric: str,
        value: float,
        threshold: float,
        message: str,
    ) -> str:
        """Create a stream alert record. Returns alert ID."""
        alert_id = str(uuid.uuid4())
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stream_alert
                        (id, sensor_device_id, alert_type, severity, metric,
                         value, threshold, message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (alert_id, sensor_device_id, alert_type, severity, metric, value, threshold, message),
                )

                # Also publish to event bus
                try:
                    from services.events.bus import EventBus
                    bus = EventBus(conn=conn)
                    bus.publish(
                        "stream_alert",
                        {
                            "alert_id": alert_id,
                            "sensor_device_id": sensor_device_id,
                            "alert_type": alert_type,
                            "severity": severity,
                            "metric": metric,
                            "value": value,
                            "threshold": threshold,
                            "message": message,
                        },
                        source_table="stream_alert",
                        source_id=alert_id,
                        priority="high" if severity == "critical" else "normal",
                    )
                except Exception:
                    pass  # Don't fail alert creation due to event bus errors

            conn.commit()
            logger.info("Stream alert created: %s [%s] %s", alert_type, severity, message[:100])
            return alert_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to create stream alert")
            raise

    def acknowledge(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge a stream alert."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE stream_alert
                    SET acknowledged = TRUE, acknowledged_by = %s, acknowledged_at = NOW()
                    WHERE id = %s AND NOT acknowledged
                    RETURNING id
                    """,
                    (acknowledged_by, alert_id),
                )
                result = cur.fetchone()
            conn.commit()
            return result is not None
        except Exception:
            conn.rollback()
            logger.exception("Failed to acknowledge alert")
            return False

    def list_unacknowledged(self, severity: str | None = None, limit: int = 50) -> list[dict]:
        """List unacknowledged stream alerts."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                conditions = ["NOT acknowledged"]
                params = []
                if severity:
                    conditions.append("severity = %s")
                    params.append(severity)
                params.append(limit)

                where = " AND ".join(conditions)
                cur.execute(
                    f"""
                    SELECT id, sensor_device_id, alert_type, severity, metric,
                           value, threshold, message, created_at
                    FROM stream_alert
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [
                    {
                        "alert_id": str(r[0]),
                        "sensor_device_id": str(r[1]),
                        "alert_type": r[2],
                        "severity": r[3],
                        "metric": r[4],
                        "value": r[5],
                        "threshold": r[6],
                        "message": r[7],
                        "created_at": r[8].isoformat(),
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to list unacknowledged alerts")
            return []
