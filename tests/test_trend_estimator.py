"""Tests for Trend Estimator and Significance modules."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# TrendEstimator Tests
# ---------------------------------------------------------------------------

class TestTrendEstimator:
    def _make_estimator(self):
        from services.trends.estimator import TrendEstimator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return TrendEstimator(conn=mock_conn), mock_conn, mock_cursor

    def test_compute_trend_returns_required_fields(self):
        estimator, _, _ = self._make_estimator()
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = estimator.compute_trend(series)
        assert "slope" in result
        assert "intercept" in result
        assert "r_squared" in result
        assert "direction" in result

    def test_compute_trend_detects_increasing(self):
        estimator, _, _ = self._make_estimator()
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = estimator.compute_trend(series)
        assert result["slope"] > 0
        assert result["direction"] == "improving"

    def test_compute_trend_detects_decreasing(self):
        estimator, _, _ = self._make_estimator()
        series = [5.0, 4.0, 3.0, 2.0, 1.0]
        result = estimator.compute_trend(series)
        assert result["slope"] < 0
        assert result["direction"] == "declining"

    def test_compute_trend_detects_stable(self):
        estimator, _, _ = self._make_estimator()
        series = [5.0, 5.0, 5.0, 5.0, 5.0]
        result = estimator.compute_trend(series)
        assert result["slope"] == 0.0

    def test_compute_trend_insufficient_data(self):
        estimator, _, _ = self._make_estimator()
        result = estimator.compute_trend([1.0, 2.0])
        assert result["direction"] == "insufficient_data"

    def test_compute_trend_r_squared_for_perfect_line(self):
        estimator, _, _ = self._make_estimator()
        series = [0.0, 1.0, 2.0, 3.0, 4.0]
        result = estimator.compute_trend(series)
        assert result["r_squared"] > 0.99

    def test_compute_correlation_perfect(self):
        estimator, _, _ = self._make_estimator()
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = estimator.compute_correlation(x, y)
        assert result["correlation"] > 0.99

    def test_compute_correlation_zero(self):
        estimator, _, _ = self._make_estimator()
        x = [1.0, 2.0, 3.0]
        y = [3.0, 2.0, 1.0]
        result = estimator.compute_correlation(x, y)
        assert result["correlation"] < -0.9

    def test_detect_trend_direction_with_p_value(self):
        estimator, _, _ = self._make_estimator()
        result = estimator.detect_trend_direction(0.5, 0.005)
        assert result["direction"] == "improving"
        assert result["confidence"] == "high"

    def test_detect_trend_direction_stable_when_high_p(self):
        estimator, _, _ = self._make_estimator()
        result = estimator.detect_trend_direction(0.5, 0.20)
        assert result["direction"] == "stable"

    def test_metric_query_uses_canonical_metric_value_contract(self):
        estimator, _, cursor = self._make_estimator()
        cursor.fetchall.return_value = []

        estimator.compute_trend_per_metric("soil_carbon", "loc-1")

        query = cursor.execute.call_args.args[0]
        assert "mv.value" in query
        assert "mv.computed_at" in query
        assert "md.id = mv.metric_id" in query
        assert "metric_definition_id" not in query


# ---------------------------------------------------------------------------
# TrendSignificance Tests
# ---------------------------------------------------------------------------

class TestTrendSignificance:
    def _make_significance(self):
        from services.trends.significance import TrendSignificance
        return TrendSignificance()

    def test_mann_kendall_detects_increasing_trend(self):
        sig = self._make_significance()
        series = list(range(20))
        result = sig.mann_kendall_test(series)
        assert result["trend"] in ("significant_increasing", "likely_increasing")

    def test_mann_kendall_detects_no_trend(self):
        sig = self._make_significance()
        import random
        random.seed(42)
        series = [random.gauss(50, 10) for _ in range(20)]
        result = sig.mann_kendall_test(series)
        assert result["trend"] in ("no_trend", "possible_trend")

    def test_mann_kendall_insufficient_data(self):
        sig = self._make_significance()
        result = sig.mann_kendall_test([1.0, 2.0])
        assert result["trend"] == "insufficient_data"

    def test_compute_confidence_interval_returns_bounds(self):
        sig = self._make_significance()
        result = sig.compute_confidence_interval(0.5, 0.1, 10, 0.95)
        assert "lower" in result
        assert "upper" in result
        assert result["lower"] < result["upper"]

    def test_compute_prediction_interval_returns_bounds(self):
        sig = self._make_significance()
        result = sig.compute_prediction_interval(
            0.5, 1.0, 5.0, 3.0, 10.0, 0.5, 10, 0.95
        )
        assert "predicted" in result
        assert "lower" in result
        assert "upper" in result
        assert result["lower"] < result["upper"]

    def test_test_stationarity_returns_flag(self):
        sig = self._make_significance()
        # Stationary series
        series = [50.0 + (i % 5) for i in range(30)]
        result = sig.test_stationarity(series)
        assert "is_stationary" in result

    def test_test_stationarity_insufficient_data(self):
        sig = self._make_significance()
        result = sig.test_stationarity([1.0, 2.0, 3.0])
        assert result["is_stationary"] is None

    def test_normal_cdf_returns_probability(self):
        sig = self._make_significance()
        assert 0.0 < sig._normal_cdf(0.0) < 1.0
        assert sig._normal_cdf(0.0) == 0.5
        assert sig._normal_cdf(-3.0) < 0.01
        assert sig._normal_cdf(3.0) > 0.99
