"""Seasonal Decomposer — separates trend, seasonal, and residual components.

Decomposes time series data to understand underlying patterns.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import DEFAULT_SMOOTHING_WINDOW


class SeasonalDecomposer:
    """Decomposes time series into trend, seasonal, and residual components."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def decompose(
        self,
        series: List[float],
        period: int = 12,
        method: str = "classical",
    ) -> Dict[str, Any]:
        """Decompose a time series into trend, seasonal, and residual.

        Args:
            series: List of numeric values.
            period: Number of observations per seasonal cycle.
            method: Decomposition method ('classical' or 'stl').

        Returns:
            Dict with trend, seasonal, residual, and strength metrics.
        """
        n = len(series)
        if n < 2 * period:
            return {
                "trend": [],
                "seasonal": [],
                "residual": [],
                "seasonal_strength": 0.0,
                "trend_strength": 0.0,
                "error": "Insufficient data for decomposition",
            }

        if method == "classical":
            return self._classical_decompose(series, period)
        else:
            return self._classical_decompose(series, period)

    def _classical_decompose(
        self, series: List[float], period: int
    ) -> Dict[str, Any]:
        """Classical additive decomposition."""
        n = len(series)

        # Step 1: Compute trend using centered moving average
        trend = self._centered_moving_average(series, period)

        # Step 2: Compute detrended series
        detrended = []
        for i in range(n):
            if trend[i] is not None:
                detrended.append(series[i] - trend[i])
            else:
                detrended.append(None)

        # Step 3: Compute seasonal component (average for each period position)
        seasonal = [None] * n
        seasonal_means = {}
        for pos in range(period):
            values_at_pos = [
                detrended[i] for i in range(pos, n, period)
                if detrended[i] is not None
            ]
            if values_at_pos:
                seasonal_means[pos] = sum(values_at_pos) / len(values_at_pos)

        # Center seasonal component
        mean_seasonal = sum(seasonal_means.values()) / len(seasonal_means) if seasonal_means else 0
        for pos in range(period):
            seasonal_means[pos] = seasonal_means.get(pos, 0) - mean_seasonal

        for i in range(n):
            seasonal[i] = seasonal_means.get(i % period, 0.0)

        # Step 4: Compute residual
        residual = []
        for i in range(n):
            if trend[i] is not None:
                residual.append(series[i] - trend[i] - seasonal[i])
            else:
                residual.append(None)

        # Compute strength metrics
        seasonal_strength = self._compute_seasonal_strength(series, trend, seasonal, residual)
        trend_strength = self._compute_trend_strength(series, trend, residual)

        return {
            "trend": [round(t, 4) if t is not None else None for t in trend],
            "seasonal": [round(s, 4) for s in seasonal],
            "residual": [round(r, 4) if r is not None else None for r in residual],
            "seasonal_strength": round(seasonal_strength, 4),
            "trend_strength": round(trend_strength, 4),
            "residual_variance": round(self._variance([r for r in residual if r is not None]), 4),
            "period": period,
            "data_points": n,
        }

    def get_seasonal_strength(self, decomposition: Dict) -> float:
        """Get the seasonal strength from a decomposition result."""
        return decomposition.get("seasonal_strength", 0.0)

    def get_trend_strength(self, decomposition: Dict) -> float:
        """Get the trend strength from a decomposition result."""
        return decomposition.get("trend_strength", 0.0)

    def residual_analysis(self, decomposition: Dict) -> Dict[str, Any]:
        """Analyze residuals for anomalies and patterns."""
        residuals = [r for r in decomposition.get("residual", []) if r is not None]
        if not residuals:
            return {"anomalies": [], "stats": {}}

        mean_r = sum(residuals) / len(residuals)
        std_r = self._variance(residuals) ** 0.5

        # Detect anomalies (residuals > 2 standard deviations)
        anomalies = []
        for i, r in enumerate(decomposition.get("residual", [])):
            if r is not None and abs(r - mean_r) > 2 * std_r:
                anomalies.append({
                    "index": i,
                    "value": round(r, 4),
                    "severity": "high" if abs(r - mean_r) > 3 * std_r else "medium",
                })

        return {
            "anomalies": anomalies,
            "stats": {
                "mean": round(mean_r, 4),
                "std": round(std_r, 4),
                "min": round(min(residuals), 4),
                "max": round(max(residuals), 4),
                "count": len(residuals),
            },
        }

    def persist_decomposition(
        self,
        metric_key: str,
        location_id: str,
        decomposition: Dict,
    ) -> str:
        """Persist decomposition results to the database."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        decomp_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO seasonal_decomposition (
                id, metric_key, location_id, decomposition_method, period,
                trend_component, seasonal_component, residual_component,
                seasonal_strength, trend_strength, residual_variance,
                data_points, computed_at
            ) VALUES (%s, %s, %s, 'classical', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            decomp_id, metric_key, location_id,
            decomposition["period"],
            psycopg2.extras.Json(decomposition["trend"]),
            psycopg2.extras.Json(decomposition["seasonal"]),
            psycopg2.extras.Json(decomposition["residual"]),
            decomposition["seasonal_strength"],
            decomposition["trend_strength"],
            decomposition["residual_variance"],
            decomposition["data_points"],
            datetime.now(timezone.utc),
        ))

        conn.commit()
        cur.close()
        return decomp_id

    # --- Private helpers ---

    def _centered_moving_average(
        self, series: List[float], period: int
    ) -> List[Optional[float]]:
        """Compute centered moving average for trend extraction."""
        n = len(series)
        result = [None] * n
        half = period // 2

        for i in range(half, n - half):
            window = series[i - half : i + half + 1]
            result[i] = sum(window) / len(window)

        return result

    def _variance(self, values: List[float]) -> float:
        """Compute variance of a list of values."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / (len(values) - 1)

    def _compute_seasonal_strength(
        self, series, trend, seasonal, residual
    ) -> float:
        """Compute how much of the variation is seasonal."""
        valid_residuals = [r for r in residual if r is not None]
        valid_detrended = [
            series[i] - trend[i]
            for i in range(len(series))
            if trend[i] is not None
        ]

        if not valid_residuals or not valid_detrended:
            return 0.0

        var_residual = self._variance(valid_residuals)
        var_detrended = self._variance(valid_detrended)

        if var_detrended == 0:
            return 0.0

        return max(0.0, 1.0 - var_residual / var_detrended)

    def _compute_trend_strength(self, series, trend, residual) -> float:
        """Compute how much of the variation is trend."""
        valid_residuals = [r for r in residual if r is not None]

        if not valid_residuals:
            return 0.0

        var_residual = self._variance(valid_residuals)
        var_series = self._variance(series)

        if var_series == 0:
            return 0.0

        return max(0.0, 1.0 - var_residual / var_series)
