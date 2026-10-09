"""Forecast Accuracy — MAE, RMSE, MAPE, bias tracking.

Validates forecast quality by comparing predictions against actuals.
"""

from __future__ import annotations

import uuid
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class ForecastAccuracy:
    """Tracks and computes forecast accuracy metrics."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def compute_mae(self, predicted: List[float], actual: List[float]) -> float:
        """Compute Mean Absolute Error."""
        if not predicted or not actual or len(predicted) != len(actual):
            return 0.0
        errors = [abs(a - p) for a, p in zip(actual, predicted)]
        return round(sum(errors) / len(errors), 6)

    def compute_rmse(self, predicted: List[float], actual: List[float]) -> float:
        """Compute Root Mean Square Error."""
        if not predicted or not actual or len(predicted) != len(actual):
            return 0.0
        errors = [(a - p) ** 2 for a, p in zip(actual, predicted)]
        return round(math.sqrt(sum(errors) / len(errors)), 6)

    def compute_mape(self, predicted: List[float], actual: List[float]) -> float:
        """Compute Mean Absolute Percentage Error."""
        if not predicted or not actual or len(predicted) != len(actual):
            return 0.0
        pct_errors = []
        for a, p in zip(actual, predicted):
            if abs(a) > 1e-10:
                pct_errors.append(abs((a - p) / a))
        if not pct_errors:
            return 0.0
        return round(sum(pct_errors) / len(pct_errors) * 100, 2)

    def compute_bias(self, predicted: List[float], actual: List[float]) -> float:
        """Compute forecast bias (positive = over-prediction)."""
        if not predicted or not actual or len(predicted) != len(actual):
            return 0.0
        errors = [p - a for a, p in zip(actual, predicted)]
        return round(sum(errors) / len(errors), 6)

    def track_accuracy_over_time(
        self,
        forecast_id: str,
        actual_timestamps: List[str],
        actual_values: List[float],
    ) -> Dict[str, Any]:
        """Track accuracy by recording actual values against a forecast.

        Args:
            forecast_id: UUID of the forecast record.
            actual_timestamps: Timestamps of actual observations.
            actual_values: Actual observed values.

        Returns:
            Summary of tracked accuracy.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get forecast predictions
        cur.execute("""
            SELECT forecast_values FROM time_series_forecast WHERE id = %s
        """, (forecast_id,))
        row = cur.fetchone()
        if row is None:
            cur.close()
            return {"error": "Forecast not found"}

        forecast_values = row["forecast_values"]
        if not isinstance(forecast_values, list):
            forecast_values = []

        # Track accuracy for each actual observation
        records = []
        for i, (ts, actual) in enumerate(zip(actual_timestamps, actual_values)):
            if i < len(forecast_values):
                predicted = forecast_values[i]
                error_abs = abs(actual - predicted)
                error_sq = (actual - predicted) ** 2
                error_pct = (abs((actual - predicted) / actual) * 100) if abs(actual) > 1e-10 else None

                record_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO forecast_accuracy (
                        id, forecast_id, actual_timestamp, predicted_value,
                        actual_value, error_abs, error_squared, error_pct,
                        computed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record_id, forecast_id, ts, predicted,
                    actual, error_abs, error_sq, error_pct,
                    datetime.now(timezone.utc),
                ))
                records.append({
                    "timestamp": ts,
                    "predicted": predicted,
                    "actual": actual,
                    "error_abs": round(error_abs, 4),
                    "error_pct": round(error_pct, 2) if error_pct else None,
                })

        conn.commit()
        cur.close()

        # Compute aggregate accuracy
        if records:
            predicted_list = [r["predicted"] for r in records]
            actual_list = [r["actual"] for r in records]
            return {
                "forecast_id": forecast_id,
                "tracked_points": len(records),
                "mae": self.compute_mae(predicted_list, actual_list),
                "rmse": self.compute_rmse(predicted_list, actual_list),
                "mape": self.compute_mape(predicted_list, actual_list),
                "bias": self.compute_bias(predicted_list, actual_list),
                "details": records,
            }

        return {"forecast_id": forecast_id, "tracked_points": 0}

    def get_accuracy_summary(
        self, forecast_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregate accuracy metrics for a forecast or all forecasts."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if forecast_id:
            cur.execute("""
                SELECT
                    COUNT(*) as count,
                    AVG(error_abs) as mae,
                    SQRT(AVG(error_squared)) as rmse,
                    AVG(error_pct) as mape
                FROM forecast_accuracy WHERE forecast_id = %s
            """, (forecast_id,))
        else:
            cur.execute("""
                SELECT
                    COUNT(*) as count,
                    AVG(error_abs) as mae,
                    SQRT(AVG(error_squared)) as rmse,
                    AVG(error_pct) as mape
                FROM forecast_accuracy
            """)

        row = cur.fetchone()
        cur.close()

        if row is None:
            return {"count": 0}

        return {
            "count": row["count"] or 0,
            "mae": round(row["mae"], 4) if row["mae"] else None,
            "rmse": round(row["rmse"], 4) if row["rmse"] else None,
            "mape": round(row["mape"], 2) if row["mape"] else None,
        }
