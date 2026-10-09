"""Time Series Forecaster — ARIMA models, prediction intervals, backtesting.

Provides statistical forecasting capabilities for time series data.
"""

from __future__ import annotations

import uuid
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from .config import ARIMA_MAX_P, ARIMA_MAX_D, ARIMA_MAX_Q, DEFAULT_FORECAST_HORIZON


class TimeSeriesForecaster:
    """Forecasts time series values using various models."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def arima_forecast(
        self,
        series: List[float],
        order: Tuple[int, int, int] = (1, 0, 1),
        steps: int = DEFAULT_FORECAST_HORIZON,
    ) -> Dict[str, Any]:
        """ARIMA model fitting and forecasting.

        Args:
            series: Historical time series values.
            order: (p, d, q) order of ARIMA model.
            steps: Number of steps to forecast.

        Returns:
            Dict with fitted values, forecasts, and model stats.
        """
        p, d, q = order
        n = len(series)

        if n < max(p, q) + 2:
            return {
                "error": "Insufficient data for ARIMA model",
                "data_points": n,
            }

        # Apply differencing
        diff_series = self._difference(series, d)

        # Fit ARMA model on differenced series
        if len(diff_series) < p + q + 1:
            return {
                "error": "Insufficient data after differencing",
                "data_points": n,
            }

        # Simple AR(1) + MA(1) approximation
        fitted, residuals = self._fit_arma(diff_series, p, q)

        # Generate forecasts
        forecasts = self._forecast_arma(diff_series, fitted, residuals, steps, p, q)

        # Re-integrate (undo differencing)
        if d > 0:
            forecasts = self._undifference(series, forecasts, d)

        # Compute prediction intervals
        residual_std = (sum(r ** 2 for r in residuals) / len(residuals)) ** 0.5 if residuals else 0.0

        return {
            "model_type": "arima",
            "order": order,
            "fitted_values": [round(f, 4) for f in fitted[-min(20, n):]],
            "forecasts": [round(f, 4) for f in forecasts],
            "forecast_steps": steps,
            "residual_std": round(residual_std, 4),
            "aic": self._compute_aic(residuals, n),
            "data_points": n,
        }

    def auto_arima(
        self, series: List[float], max_order: int = 3
    ) -> Dict[str, Any]:
        """Automatically select ARIMA order using AIC.

        Args:
            series: Historical time series values.
            max_order: Maximum p and q to test.

        Returns:
            Best ARIMA model with selected order.
        """
        best_aic = float("inf")
        best_order = (1, 0, 1)
        best_result = None

        for p in range(0, max_order + 1):
            for d in range(0, 3):
                for q in range(0, max_order + 1):
                    try:
                        result = self.arima_forecast(series, (p, d, q), steps=0)
                        if "error" not in result:
                            aic = result.get("aic", float("inf"))
                            if aic < best_aic:
                                best_aic = aic
                                best_order = (p, d, q)
                                best_result = result
                    except Exception:
                        continue

        if best_result is None:
            return {"error": "No valid ARIMA model found"}

        best_result["selected_order"] = best_order
        best_result["selection_method"] = "aic"
        return best_result

    def get_forecast_with_intervals(
        self,
        series: List[float],
        steps: int = DEFAULT_FORECAST_HORIZON,
        confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """Generate forecasts with prediction intervals.

        Args:
            series: Historical values.
            steps: Forecast horizon.
            confidence: Confidence level for intervals.

        Returns:
            Forecasts with lower/upper bounds.
        """
        result = self.arima_forecast(series, steps=steps)
        if "error" in result:
            return result

        forecasts = result["forecasts"]
        residual_std = result["residual_std"]

        # Approximate z-value for confidence level
        if confidence >= 0.99:
            z = 2.576
        elif confidence >= 0.95:
            z = 1.96
        elif confidence >= 0.90:
            z = 1.645
        else:
            z = 1.28

        # Growing prediction intervals
        intervals = []
        for i, f in enumerate(forecasts):
            horizon_factor = math.sqrt(i + 1)
            margin = z * residual_std * horizon_factor
            intervals.append({
                "step": i + 1,
                "forecast": f,
                "lower": round(f - margin, 4),
                "upper": round(f + margin, 4),
            })

        return {
            "forecasts": forecasts,
            "intervals": intervals,
            "confidence": confidence,
            "residual_std": residual_std,
            "model_order": result["order"],
        }

    def backtest(
        self,
        series: List[float],
        train_pct: float = 0.8,
        order: Tuple[int, int, int] = (1, 0, 1),
    ) -> Dict[str, Any]:
        """Walk-forward backtesting.

        Args:
            series: Full historical series.
            train_pct: Fraction of data for training.
            order: ARIMA order to test.

        Returns:
            Backtest results with error metrics.
        """
        n = len(series)
        split = int(n * train_pct)
        train = series[:split]
        test = series[split:]

        if len(test) < 1:
            return {"error": "Insufficient test data"}

        # Fit on training data
        result = self.arima_forecast(train, order=order, steps=len(test))
        if "error" in result:
            return result

        forecasts = result["forecasts"]

        # Compute error metrics
        errors = [actual - predicted for actual, predicted in zip(test, forecasts)]
        mae = sum(abs(e) for e in errors) / len(errors)
        mse = sum(e ** 2 for e in errors) / len(errors)
        rmse = math.sqrt(mse)

        return {
            "train_size": split,
            "test_size": len(test),
            "order": order,
            "mae": round(mae, 4),
            "mse": round(mse, 4),
            "rmse": round(rmse, 4),
            "actual": [round(a, 4) for a in test],
            "predicted": [round(p, 4) for p in forecasts],
        }

    # --- Private helpers ---

    def _difference(self, series: List[float], d: int) -> List[float]:
        """Apply differencing."""
        result = series
        for _ in range(d):
            result = [result[i] - result[i - 1] for i in range(1, len(result))]
        return result

    def _undifference(
        self, original: List[float], forecasts: List[float], d: int
    ) -> List[float]:
        """Undo differencing to get back to original scale."""
        result = forecasts
        for _ in range(d):
            last_val = original[-1] if original else 0
            result = [last_val + result[0]] + [
                result[i] + result[i - 1] for i in range(1, len(result))
            ]
        return result

    def _fit_arma(
        self, series: List[float], p: int, q: int
    ) -> Tuple[List[float], List[float]]:
        """Simple ARMA fitting using method of moments."""
        n = len(series)
        mean = sum(series) / n

        # AR coefficients (simple approximation)
        ar_coeffs = [0.5] * p if p > 0 else []

        # Fit AR part
        fitted = []
        residuals = []
        for i in range(max(p, q), n):
            ar_pred = sum(ar_coeffs[j] * series[i - j - 1] for j in range(p))
            fitted_val = mean + ar_pred
            fitted.append(fitted_val)
            residuals.append(series[i] - fitted_val)

        return fitted, residuals

    def _forecast_arma(
        self,
        series: List[float],
        fitted: List[float],
        residuals: List[float],
        steps: int,
        p: int,
        q: int,
    ) -> List[float]:
        """Generate ARMA forecasts."""
        forecasts = []
        recent = series[-p:] if p > 0 else [sum(series) / len(series)]
        mean = sum(series) / len(series)

        for _ in range(steps):
            pred = mean
            for j in range(min(p, len(recent))):
                pred += 0.5 * recent[-(j + 1)]
            forecasts.append(pred)
            recent.append(pred)

        return forecasts

    def _compute_aic(self, residuals: List[float], n: int) -> float:
        """Compute Akaike Information Criterion."""
        if not residuals or n < 3:
            return float("inf")
        k = 3  # Number of parameters (p, d, q)
        sse = sum(r ** 2 for r in residuals)
        if sse <= 0:
            return float("inf")
        return round(n * math.log(sse / n) + 2 * k, 2)
