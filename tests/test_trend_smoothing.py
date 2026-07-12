"""Tests for Time Series Smoothing and Seasonal Decomposer."""

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
# TimeSeriesSmoothing Tests
# ---------------------------------------------------------------------------

class TestTimeSeriesSmoothing:
    def _make_smoothing(self):
        from services.trends.smoothing import TimeSeriesSmoothing
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return TimeSeriesSmoothing(conn=mock_conn), mock_conn, mock_cursor

    def test_moving_average_reduces_noise(self):
        smoothing, _, _ = self._make_smoothing()
        series = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = smoothing.moving_average(series, window=3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == 2.0  # (1+2+3)/3
        assert len(result) == len(series)

    def test_weighted_moving_average_weights_recent(self):
        smoothing, _, _ = self._make_smoothing()
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = smoothing.weighted_moving_average(series, window=3)
        assert result[2] is not None
        # Weighted: 1*1 + 2*2 + 3*3 = 14 / 6 = 2.333
        assert result[2] > 2.0

    def test_exponential_smoothing_tracks_trend(self):
        smoothing, _, _ = self._make_smoothing()
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = smoothing.exponential_smoothing(series, alpha=0.5)
        assert len(result) == len(series)
        assert result[0] == 1.0
        assert result[-1] > result[0]

    def test_exponential_smoothing_smoothing_factor(self):
        smoothing, _, _ = self._make_smoothing()
        series = [1.0, 10.0, 1.0, 10.0]
        low_alpha = smoothing.exponential_smoothing(series, alpha=0.1)
        high_alpha = smoothing.exponential_smoothing(series, alpha=0.9)
        # High alpha should follow the series more closely
        assert abs(high_alpha[-1] - 10.0) < abs(low_alpha[-1] - 10.0)

    def test_holt_linear_captures_trend(self):
        smoothing, _, _ = self._make_smoothing()
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = smoothing.holt_linear(series, alpha=0.5, beta=0.1)
        assert len(result) == len(series)
        assert result[-1] > result[0]

    def test_smooth_sensor_readings_returns_empty_when_no_data(self):
        smoothing, _, mock_cursor = self._make_smoothing()
        mock_cursor.fetchall.return_value = []
        result = smoothing.smooth_sensor_readings("sensor-001", "soil_moisture")
        assert result == []

    def test_smooth_sensor_readings_returns_results(self):
        smoothing, _, mock_cursor = self._make_smoothing()
        mock_cursor.fetchall.return_value = [
            {"value": 10.0, "timestamp": datetime.now(timezone.utc)},
            {"value": 12.0, "timestamp": datetime.now(timezone.utc)},
            {"value": 11.0, "timestamp": datetime.now(timezone.utc)},
        ]
        result = smoothing.smooth_sensor_readings("sensor-001", "soil_moisture")
        assert len(result) == 3
        assert "smoothed" in result[0]

    def test_empty_series_returns_empty(self):
        smoothing, _, _ = self._make_smoothing()
        result = smoothing.exponential_smoothing([])
        assert result == []


# ---------------------------------------------------------------------------
# SeasonalDecomposer Tests
# ---------------------------------------------------------------------------

class TestSeasonalDecomposer:
    def _make_decomposer(self):
        from services.trends.decomposer import SeasonalDecomposer
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return SeasonalDecomposer(conn=mock_conn), mock_conn, mock_cursor

    def test_decompose_returns_components(self):
        decomposer, _, _ = self._make_decomposer()
        # Create a seasonal pattern
        import math
        series = [10 + 5 * math.sin(2 * math.pi * i / 12) + i * 0.1 for i in range(48)]
        result = decomposer.decompose(series, period=12)
        assert "trend" in result
        assert "seasonal" in result
        assert "residual" in result
        assert len(result["trend"]) == len(series)
        assert len(result["seasonal"]) == len(series)
        assert len(result["residual"]) == len(series)

    def test_decompose_insufficient_data(self):
        decomposer, _, _ = self._make_decomposer()
        series = list(range(10))
        result = decomposer.decompose(series, period=12)
        assert "error" in result

    def test_seasonal_strength_for_seasonal_data(self):
        decomposer, _, _ = self._make_decomposer()
        import math
        series = [10 + 5 * math.sin(2 * math.pi * i / 12) for i in range(60)]
        result = decomposer.decompose(series, period=12)
        assert result["seasonal_strength"] > 0.3

    def test_trend_strength_for_trending_data(self):
        decomposer, _, _ = self._make_decomposer()
        series = [i * 2.0 + 0.5 * (i % 12) for i in range(60)]
        result = decomposer.decompose(series, period=12)
        assert result["trend_strength"] > 0.3

    def test_residual_analysis_detects_anomalies(self):
        decomposer, _, _ = self._make_decomposer()
        decomposition = {
            "residual": [0.1, 0.2, 0.1, 0.2, 5.0, 0.1, 0.2, 0.1, 0.2, 0.1,
                        0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1],
        }
        result = decomposer.residual_analysis(decomposition)
        assert len(result["anomalies"]) > 0

    def test_residual_analysis_clean_data(self):
        decomposer, _, _ = self._make_decomposer()
        decomposition = {
            "residual": [0.1, 0.15, 0.12, 0.11, 0.13, 0.12, 0.11, 0.14, 0.12, 0.13],
        }
        result = decomposer.residual_analysis(decomposition)
        assert len(result["anomalies"]) == 0

    def test_get_seasonal_strength_returns_value(self):
        decomposer, _, _ = self._make_decomposer()
        result = decomposer.get_seasonal_strength({"seasonal_strength": 0.75})
        assert result == 0.75

    def test_get_trend_strength_returns_value(self):
        decomposer, _, _ = self._make_decomposer()
        result = decomposer.get_trend_strength({"trend_strength": 0.65})
        assert result == 0.65
