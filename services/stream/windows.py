"""Windowed aggregation for stream processing — tumbling and sliding windows."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from services.common.logging import get_logger

logger = get_logger("stream.windows")

# Window sizes in minutes
WINDOW_SIZES = {
    "1min": 1,
    "5min": 5,
    "15min": 15,
    "1hour": 60,
}


class WindowAggregator:
    """Maintains windowed aggregations for sensor metrics."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def _get_window_bounds(self, ts: datetime, window_size: str) -> tuple[datetime, datetime]:
        """Compute tumbling window start/end for a timestamp."""
        minutes = WINDOW_SIZES.get(window_size, 5)
        # Floor to window boundary
        floored_minute = (ts.minute // minutes) * minutes
        start = ts.replace(minute=floored_minute, second=0, microsecond=0)
        end = start + timedelta(minutes=minutes)
        return start, end

    def ingest(self, sensor_device_id: str, metric: str, value: float, ts: datetime) -> None:
        """Ingest a value into all window sizes."""
        for window_size in WINDOW_SIZES:
            self._update_window(sensor_device_id, metric, window_size, value, ts)

    def _update_window(
        self,
        sensor_device_id: str,
        metric: str,
        window_size: str,
        value: float,
        ts: datetime,
    ) -> None:
        """Update or create a window aggregation entry."""
        window_start, window_end = self._get_window_bounds(ts, window_size)
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                # Try to update existing window
                cur.execute(
                    """
                    UPDATE stream_window
                    SET min_value = LEAST(min_value, %s),
                        max_value = GREATEST(max_value, %s),
                        avg_value = (avg_value * sample_count + %s) / (sample_count + 1),
                        sample_count = sample_count + 1
                    WHERE sensor_device_id = %s
                      AND metric = %s
                      AND window_size = %s
                      AND window_start = %s
                    """,
                    (value, value, value, sensor_device_id, metric, window_size, window_start),
                )

                if cur.rowcount == 0:
                    # Create new window
                    cur.execute(
                        """
                        INSERT INTO stream_window
                            (sensor_device_id, metric, window_size, window_start,
                             window_end, min_value, max_value, avg_value, sample_count)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
                        """,
                        (sensor_device_id, metric, window_size, window_start,
                         window_end, value, value, value),
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Window update failed for %s %s", sensor_device_id[:8], metric)

    def get_windows(
        self,
        sensor_device_id: str,
        metric: str,
        window_size: str,
        limit: int = 24,
    ) -> list[dict]:
        """Get recent window aggregations."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT window_start, window_end, min_value, max_value,
                           avg_value, sample_count, anomaly_count
                    FROM stream_window
                    WHERE sensor_device_id = %s
                      AND metric = %s
                      AND window_size = %s
                    ORDER BY window_start DESC
                    LIMIT %s
                    """,
                    (sensor_device_id, metric, window_size, limit),
                )
                return [
                    {
                        "window_start": r[0].isoformat(),
                        "window_end": r[1].isoformat(),
                        "min_value": r[2],
                        "max_value": r[3],
                        "avg_value": float(r[4]) if r[4] else None,
                        "sample_count": r[5],
                        "anomaly_count": r[6],
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to get windows")
            return []

    def detect_spikes(
        self,
        sensor_device_id: str,
        metric: str,
        threshold_factor: float = 3.0,
    ) -> dict | None:
        """Detect spike using 5min vs 15min window comparison."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # Get latest 5min window
                cur.execute(
                    """
                    SELECT avg_value, sample_count
                    FROM stream_window
                    WHERE sensor_device_id = %s AND metric = %s AND window_size = '5min'
                    ORDER BY window_start DESC LIMIT 1
                    """,
                    (sensor_device_id, metric),
                )
                recent = cur.fetchone()
                if not recent:
                    return None

                # Get 15min baseline
                cur.execute(
                    """
                    SELECT AVG(avg_value)
                    FROM stream_window
                    WHERE sensor_device_id = %s AND metric = %s AND window_size = '15min'
                      AND window_start >= NOW() - INTERVAL '2 hours'
                    """,
                    (sensor_device_id, metric),
                )
                baseline = cur.fetchone()
                if not baseline or not baseline[0]:
                    return None

                recent_avg = float(recent[0])
                baseline_avg = float(baseline[0])

                if baseline_avg != 0 and abs(recent_avg - baseline_avg) / abs(baseline_avg) > threshold_factor:
                    return {
                        "type": "spike",
                        "metric": metric,
                        "recent_value": recent_avg,
                        "baseline_value": baseline_avg,
                        "deviation": abs(recent_avg - baseline_avg) / abs(baseline_avg),
                    }
            return None
        except Exception:
            logger.exception("Spike detection failed")
            return None
