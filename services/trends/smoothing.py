"""Time Series Smoothing — moving average, exponential smoothing, Holt's linear.

Smooths noisy time series data to reveal underlying patterns.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import DEFAULT_SMOOTHING_WINDOW, DEFAULT_SMOOTHING_ALPHA


class TimeSeriesSmoothing:
    """Smooths time series data using various methods."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def moving_average(
        self, series: List[float], window: int = DEFAULT_SMOOTHING_WINDOW
    ) -> List[Optional[float]]:
        """Compute simple moving average.

        Args:
            series: List of numeric values.
            window: Number of periods for the average.

        Returns:
            List of smoothed values (None for first window-1 points).
        """
        n = len(series)
        result = [None] * min(window - 1, n)

        for i in range(window - 1, n):
            avg = sum(series[i - window + 1 : i + 1]) / window
            result.append(round(avg, 6))

        return result

    def weighted_moving_average(
        self, series: List[float], window: int = DEFAULT_SMOOTHING_WINDOW
    ) -> List[Optional[float]]:
        """Compute weighted moving average (more weight on recent values).

        Args:
            series: List of numeric values.
            window: Number of periods for the average.

        Returns:
            List of smoothed values.
        """
        n = len(series)
        result = [None] * min(window - 1, n)

        weights = list(range(1, window + 1))
        weight_sum = sum(weights)

        for i in range(window - 1, n):
            window_vals = series[i - window + 1 : i + 1]
            weighted = sum(v * w for v, w in zip(window_vals, weights))
            result.append(round(weighted / weight_sum, 6))

        return result

    def exponential_smoothing(
        self,
        series: List[float],
        alpha: float = DEFAULT_SMOOTHING_ALPHA,
    ) -> List[float]:
        """Compute single exponential smoothing.

        Args:
            series: List of numeric values.
            alpha: Smoothing factor (0-1). Higher = more responsive to recent values.

        Returns:
            List of smoothed values.
        """
        if not series:
            return []

        smoothed = [series[0]]
        for i in range(1, len(series)):
            s = alpha * series[i] + (1 - alpha) * smoothed[-1]
            smoothed.append(round(s, 6))

        return smoothed

    def holt_linear(
        self,
        series: List[float],
        alpha: float = DEFAULT_SMOOTHING_ALPHA,
        beta: float = 0.1,
    ) -> List[float]:
        """Compute Holt's linear trend method.

        Captures both level and trend in the data.

        Args:
            series: List of numeric values.
            alpha: Level smoothing factor.
            beta: Trend smoothing factor.

        Returns:
            List of smoothed values.
        """
        if len(series) < 2:
            return list(series)

        level = series[0]
        trend = series[1] - series[0]
        smoothed = [level]

        for i in range(1, len(series)):
            new_level = alpha * series[i] + (1 - alpha) * (level + trend)
            new_trend = beta * (new_level - level) + (1 - beta) * trend
            level = new_level
            trend = new_trend
            smoothed.append(round(level, 6))

        return smoothed

    def smooth_sensor_readings(
        self,
        sensor_device_id: str,
        metric: str,
        smoothing_type: str = "exponential",
        window: int = DEFAULT_SMOOTHING_WINDOW,
        alpha: float = DEFAULT_SMOOTHING_ALPHA,
    ) -> List[Dict[str, Any]]:
        """Auto-fetch and smooth sensor readings.

        Args:
            sensor_device_id: UUID of the sensor device.
            metric: Metric name to smooth.
            smoothing_type: Type of smoothing to apply.
            window: Window size for moving average.
            alpha: Alpha for exponential smoothing.

        Returns:
            List of smoothing results with timestamps.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT value, timestamp
            FROM stream_buffer
            WHERE sensor_device_id = %s AND metric = %s
            AND ingested = FALSE
            ORDER BY timestamp ASC
        """, (sensor_device_id, metric))

        rows = cur.fetchall()
        cur.close()

        if not rows:
            return []

        values = [float(r["value"]) for r in rows]
        timestamps = [r["timestamp"] for r in rows]

        # Apply smoothing
        if smoothing_type == "moving_average":
            smoothed = self.moving_average(values, window)
        elif smoothing_type == "weighted_moving_average":
            smoothed = self.weighted_moving_average(values, window)
        elif smoothing_type == "exponential":
            smoothed = self.exponential_smoothing(values, alpha)
        elif smoothing_type == "holt_linear":
            smoothed = self.holt_linear(values, alpha)
        else:
            smoothed = self.exponential_smoothing(values, alpha)

        # Build results
        results = []
        for i, (ts, orig, smooth) in enumerate(zip(timestamps, values, smoothed)):
            results.append({
                "original": orig,
                "smoothed": smooth,
                "timestamp": ts.isoformat() if ts else None,
            })

        # Persist results
        conn2 = self._get_conn()
        cur2 = conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        for r in results:
            if r["smoothed"] is not None:
                cur2.execute("""
                    INSERT INTO trend_smoothing (
                        id, metric_key, location_id, smoothing_type,
                        window_size, alpha, original_value, smoothed_value,
                        timestamp, computed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()), metric, None, smoothing_type,
                    window, alpha, r["original"], r["smoothed"],
                    r["timestamp"], datetime.now(timezone.utc),
                ))

        conn2.commit()
        cur2.close()

        return results
