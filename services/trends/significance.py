"""Trend Significance — Mann-Kendall test, confidence intervals, stationarity.

Statistical testing for trend presence and significance in time series data.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .config import CONFIDENCE_LEVELS, DEFAULT_SIGNIFICANCE_THRESHOLD


class TrendSignificance:
    """Statistical significance testing for trends."""

    def mann_kendall_test(
        self, series: List[float]
    ) -> Dict[str, Any]:
        """Perform Mann-Kendall trend test.

        Non-parametric test for presence of monotonic trend.

        Args:
            series: List of numeric values.

        Returns:
            Dict with statistic, p_value, trend direction, and significance.
        """
        n = len(series)
        if n < 4:
            return {
                "statistic": 0.0,
                "p_value": 1.0,
                "trend": "insufficient_data",
                "data_points": n,
            }

        # Compute S statistic
        s = 0
        for k in range(n - 1):
            for j in range(k + 1, n):
                diff = series[j] - series[k]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        # Compute variance of S
        # Handle ties
        unique_vals = {}
        for v in series:
            unique_vals[v] = unique_vals.get(v, 0) + 1

        tp = sum(t * (t - 1) * (2 * t + 5) for t in unique_vals.values() if t > 1)
        var_s = (n * (n - 1) * (2 * n + 5) - tp) / 18.0

        # Compute Z statistic
        if s > 0:
            z = (s - 1) / math.sqrt(var_s) if var_s > 0 else 0.0
        elif s < 0:
            z = (s + 1) / math.sqrt(var_s) if var_s > 0 else 0.0
        else:
            z = 0.0

        # Approximate two-tailed p-value
        p_value = 2.0 * (1.0 - self._normal_cdf(abs(z)))

        # Determine trend
        if p_value < 0.01:
            trend = "significant_increasing" if s > 0 else "significant_decreasing"
        elif p_value < 0.05:
            trend = "likely_increasing" if s > 0 else "likely_decreasing"
        elif p_value < 0.10:
            trend = "possible_trend"
        else:
            trend = "no_trend"

        return {
            "statistic": round(s, 2),
            "z_score": round(z, 4),
            "p_value": round(p_value, 6),
            "trend": trend,
            "data_points": n,
        }

    def compute_confidence_interval(
        self,
        slope: float,
        std_err: float,
        df: int,
        confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """Compute confidence interval for the trend slope.

        Args:
            slope: Fitted slope.
            std_err: Standard error of the slope.
            df: Degrees of freedom (n - 2).
            confidence: Confidence level (0.90, 0.95, 0.99).

        Returns:
            Dict with lower, upper bounds and margin of error.
        """
        if df < 1 or std_err == 0:
            return {"lower": slope, "upper": slope, "margin": 0.0}

        # t-critical values (approximation)
        t_crit = self._t_critical(df, confidence)
        margin = t_crit * std_err

        return {
            "lower": round(slope - margin, 6),
            "upper": round(slope + margin, 6),
            "margin": round(margin, 6),
            "confidence": confidence,
            "degrees_of_freedom": df,
        }

    def compute_prediction_interval(
        self,
        slope: float,
        intercept: float,
        x_new: float,
        x_mean: float,
        ss_xx: float,
        residual_std: float,
        n: int,
        confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """Compute prediction interval for a new observation.

        Args:
            slope: Fitted slope.
            intercept: Fitted intercept.
            x_new: New x value to predict at.
            x_mean: Mean of x values in training data.
            ss_xx: Sum of squared deviations of x.
            residual_std: Standard deviation of residuals.
            n: Number of training points.
            confidence: Confidence level.

        Returns:
            Dict with predicted value, lower, upper bounds.
        """
        predicted = slope * x_new + intercept

        if n < 3 or ss_xx == 0:
            return {
                "predicted": round(predicted, 4),
                "lower": round(predicted, 4),
                "upper": round(predicted, 4),
            }

        t_crit = self._t_critical(n - 2, confidence)
        se_pred = residual_std * math.sqrt(1 + 1 / n + (x_new - x_mean) ** 2 / ss_xx)
        margin = t_crit * se_pred

        return {
            "predicted": round(predicted, 4),
            "lower": round(predicted - margin, 4),
            "upper": round(predicted + margin, 4),
            "margin": round(margin, 4),
        }

    def test_stationarity(
        self, series: List[float]
    ) -> Dict[str, Any]:
        """Simple stationarity test using rolling statistics.

        Checks if mean and variance are approximately constant over time.

        Args:
            series: List of numeric values.

        Returns:
            Dict with is_stationary flag, rolling_mean_trend, rolling_std_trend.
        """
        n = len(series)
        if n < 10:
            return {"is_stationary": None, "data_points": n}

        # Split into two halves and compare
        half = n // 2
        first_half = series[:half]
        second_half = series[half:]

        mean_first = sum(first_half) / len(first_half)
        mean_second = sum(second_half) / len(second_half)

        var_first = sum((x - mean_first) ** 2 for x in first_half) / len(first_half)
        var_second = sum((x - mean_second) ** 2 for x in second_half) / len(second_half)

        # Check if means and variances are similar
        mean_diff = abs(mean_second - mean_first) / (abs(mean_first) + 1e-10)
        var_diff = abs(var_second - var_first) / (var_first + 1e-10)

        is_stationary = mean_diff < 0.1 and var_diff < 0.3

        return {
            "is_stationary": is_stationary,
            "mean_change_pct": round(mean_diff * 100, 1),
            "variance_change_pct": round(var_diff * 100, 1),
            "data_points": n,
        }

    # --- Private helpers ---

    def _normal_cdf(self, x: float) -> float:
        """Approximate cumulative distribution function of standard normal."""
        # Using the error function approximation
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))

    def _t_critical(self, df: int, confidence: float) -> float:
        """Approximate t-critical value.

        Uses a simple approximation for common confidence levels.
        """
        alpha = 1 - confidence

        # Common t-critical values (two-tailed)
        if df >= 30:
            if alpha <= 0.01:
                return 2.750
            elif alpha <= 0.05:
                return 2.042
            elif alpha <= 0.10:
                return 1.697
        elif df >= 10:
            if alpha <= 0.01:
                return 3.169
            elif alpha <= 0.05:
                return 2.228
            elif alpha <= 0.10:
                return 1.812
        elif df >= 5:
            if alpha <= 0.01:
                return 4.032
            elif alpha <= 0.05:
                return 2.571
            elif alpha <= 0.10:
                return 2.015
        else:
            if alpha <= 0.01:
                return 5.841
            elif alpha <= 0.05:
                return 3.182
            elif alpha <= 0.10:
                return 2.353

        return 2.0  # Default fallback
