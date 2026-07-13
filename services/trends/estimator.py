"""Trend Estimator — least-squares fitting, slope, r-squared, correlation.

Core trend analysis engine that fits linear trends to time series data
and computes goodness-of-fit statistics.
"""

from __future__ import annotations

import uuid
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from .config import (
    DEFAULT_MIN_DATA_POINTS,
    DIRECTION_THRESHOLDS,
    TIME_UNIT_DAYS,
)


class TrendEstimator:
    """Estimates linear trends in time series data."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def compute_trend(
        self,
        values: List[float],
        timestamps: Optional[List[float]] = None,
        time_unit: str = "day",
    ) -> Dict[str, Any]:
        """Compute linear trend for a series of values.

        Args:
            values: List of numeric values.
            timestamps: List of timestamps as numeric offsets (if None, uses index).
            time_unit: Time unit for slope interpretation.

        Returns:
            Dict with slope, intercept, r_squared, standard_error, direction, etc.
        """
        n = len(values)
        if n < 3:
            return {
                "slope": 0.0,
                "intercept": 0.0,
                "r_squared": 0.0,
                "standard_error": 0.0,
                "direction": "insufficient_data",
                "confidence_level": "insufficient_data",
                "data_points": n,
            }

        # Create x values (time indices)
        if timestamps is not None:
            x = timestamps
        else:
            x = list(range(n))

        # Least-squares fit
        slope, intercept, r_squared, std_err = self._least_squares(x, values)

        # Determine direction
        direction = self._classify_direction(slope, r_squared, std_err)

        # Confidence level
        confidence = self._classify_confidence(r_squared)

        return {
            "slope": round(slope, 6),
            "intercept": round(intercept, 4),
            "r_squared": round(r_squared, 4),
            "standard_error": round(std_err, 6),
            "direction": direction,
            "confidence_level": confidence,
            "data_points": n,
            "time_unit": time_unit,
            "slope_per_unit": round(slope, 6),
            "slope_per_day": round(slope * TIME_UNIT_DAYS.get(time_unit, 1), 6),
        }

    def compute_trend_per_metric(
        self,
        metric_key: str,
        location_id: str,
        lookback_days: int = 90,
    ) -> Dict[str, Any]:
        """Auto-fetch metric data and compute trend.

        Args:
            metric_key: The metric to analyze.
            location_id: Location UUID.
            lookback_days: How many days of data to use.

        Returns:
            Trend result dict with persistence info.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT mv.value, mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s AND md.metric_key = %s
            AND mv.verified = TRUE
            AND mv.computed_at > NOW() - INTERVAL '%s days'
            ORDER BY mv.computed_at ASC
        """, (location_id, metric_key, lookback_days))

        rows = cur.fetchall()
        cur.close()

        if len(rows) < 3:
            return {
                "metric_key": metric_key,
                "location_id": location_id,
                "direction": "insufficient_data",
                "data_points": len(rows),
            }

        values = [float(r["value"]) for r in rows]
        timestamps = [
            (r["computed_at"] - rows[0]["computed_at"]).total_seconds() / 86400
            for r in rows
        ]

        result = self.compute_trend(values, timestamps, time_unit="day")
        result["metric_key"] = metric_key
        result["location_id"] = location_id
        result["period_start"] = rows[0]["computed_at"].isoformat()
        result["period_end"] = rows[-1]["computed_at"].isoformat()

        return result

    def detect_trend_direction(
        self, slope: float, p_value: float = 1.0
    ) -> Dict[str, Any]:
        """Classify trend direction with significance.

        Args:
            slope: The fitted slope.
            p_value: Statistical significance of the slope.

        Returns:
            Dict with direction and confidence.
        """
        epsilon = DIRECTION_THRESHOLDS["slope_epsilon"]

        if p_value > 0.10:
            direction = "stable"
        elif slope > epsilon:
            direction = "improving"
        elif slope < -epsilon:
            direction = "declining"
        else:
            direction = "stable"

        if p_value < 0.01:
            confidence = "high"
        elif p_value < 0.05:
            confidence = "moderate"
        elif p_value < 0.10:
            confidence = "low"
        else:
            confidence = "low"

        return {"direction": direction, "confidence": confidence, "p_value": p_value}

    def compute_correlation(
        self, series_x: List[float], series_y: List[float]
    ) -> Dict[str, Any]:
        """Compute Pearson correlation between two series.

        Args:
            series_x: First series of values.
            series_y: Second series of values.

        Returns:
            Dict with correlation coefficient and p-value estimate.
        """
        n = len(series_x)
        if n < 3 or len(series_x) != len(series_y):
            return {"correlation": 0.0, "p_value": 1.0, "data_points": n}

        # Pearson correlation
        mean_x = sum(series_x) / n
        mean_y = sum(series_y) / n

        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(series_x, series_y))
        ss_xx = sum((x - mean_x) ** 2 for x in series_x)
        ss_yy = sum((y - mean_y) ** 2 for y in series_y)

        if ss_xx == 0 or ss_yy == 0:
            return {"correlation": 0.0, "p_value": 1.0, "data_points": n}

        r = ss_xy / math.sqrt(ss_xx * ss_yy)

        # Approximate p-value using t-distribution approximation
        if abs(r) >= 1.0:
            p_value = 0.0
        else:
            t_stat = r * math.sqrt((n - 2) / (1 - r * r))
            # Approximate two-tailed p-value
            p_value = self._t_dist_p_value(t_stat, n - 2)

        return {
            "correlation": round(r, 4),
            "p_value": round(p_value, 4),
            "r_squared": round(r * r, 4),
            "data_points": n,
        }

    def persist_trend(
        self,
        metric_key: str,
        location_id: str,
        trend_result: Dict[str, Any],
        computed_by: str = "system",
    ) -> str:
        """Persist a trend estimate to the database.

        Returns:
            The trend_estimate record ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        trend_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO trend_estimate (
                id, metric_key, location_id, period_start, period_end,
                data_points, slope, intercept, r_squared, standard_error,
                slope_p_value, direction, confidence_level,
                slope_ci_lower, slope_ci_upper, time_unit,
                computed_at, computed_by, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            trend_id, metric_key, location_id,
            trend_result.get("period_start", datetime.now(timezone.utc)),
            trend_result.get("period_end", datetime.now(timezone.utc)),
            trend_result.get("data_points", 0),
            trend_result["slope"],
            trend_result["intercept"],
            trend_result["r_squared"],
            trend_result["standard_error"],
            trend_result.get("slope_p_value"),
            trend_result["direction"],
            trend_result["confidence_level"],
            trend_result.get("slope_ci_lower"),
            trend_result.get("slope_ci_upper"),
            trend_result.get("time_unit", "day"),
            datetime.now(timezone.utc), computed_by,
            psycopg2.extras.Json(trend_result.get("metadata", {})),
        ))

        conn.commit()
        cur.close()
        return trend_id

    # --- Private helpers ---

    def _least_squares(
        self, x: List[float], y: List[float]
    ) -> Tuple[float, float, float, float]:
        """Compute least-squares linear fit.

        Returns:
            (slope, intercept, r_squared, standard_error)
        """
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        ss_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        ss_xx = sum((xi - mean_x) ** 2 for xi in x)
        ss_yy = sum((yi - mean_y) ** 2 for yi in y)

        if ss_xx == 0:
            return 0.0, mean_y, 0.0, 0.0

        slope = ss_xy / ss_xx
        intercept = mean_y - slope * mean_x

        # R-squared
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        r_squared = 1.0 - (ss_res / ss_yy) if ss_yy > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        # Standard error of the slope
        if n > 2:
            variance = ss_res / (n - 2)
            std_err_slope = math.sqrt(variance / ss_xx) if ss_xx > 0 else 0.0
        else:
            std_err_slope = 0.0

        return slope, intercept, r_squared, std_err_slope

    def _classify_direction(
        self, slope: float, r_squared: float, std_err: float
    ) -> str:
        """Classify trend direction from slope and fit quality."""
        epsilon = DIRECTION_THRESHOLDS["slope_epsilon"]

        if abs(slope) < epsilon or r_squared < 0.1:
            return "stable"

        # Check if slope is statistically meaningful
        if std_err > 0 and abs(slope) < 2 * std_err:
            return "stable"

        return "improving" if slope > 0 else "declining"

    def _classify_confidence(self, r_squared: float) -> str:
        """Classify confidence level from r-squared."""
        if r_squared >= DIRECTION_THRESHOLDS["r_squared_high"]:
            return "high"
        elif r_squared >= DIRECTION_THRESHOLDS["r_squared_min"]:
            return "moderate"
        else:
            return "low"

    def _t_dist_p_value(self, t_stat: float, df: int) -> float:
        """Approximate two-tailed p-value from t-distribution.

        Uses a simple approximation for small df.
        """
        x = df / (df + t_stat * t_stat)
        # Simple approximation using incomplete beta function
        # For our purposes, a rough estimate is sufficient
        if abs(t_stat) > 3.5:
            return 0.001
        elif abs(t_stat) > 2.5:
            return 0.02
        elif abs(t_stat) > 1.96:
            return 0.05
        elif abs(t_stat) > 1.645:
            return 0.10
        elif abs(t_stat) > 1.0:
            return 0.30
        else:
            return 0.50
