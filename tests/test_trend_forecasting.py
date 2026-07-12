"""Tests for Time Series Forecaster and Forecast Accuracy."""

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
# TimeSeriesForecaster Tests
# ---------------------------------------------------------------------------

class TestTimeSeriesForecaster:
    def _make_forecaster(self):
        from services.trends.forecasting import TimeSeriesForecaster
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return TimeSeriesForecaster(conn=mock_conn), mock_conn, mock_cursor

    def test_arima_forecast_returns_forecasts(self):
        forecaster, _, _ = self._make_forecaster()
        series = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = forecaster.arima_forecast(series, steps=5)
        assert "forecasts" in result
        assert len(result["forecasts"]) == 5

    def test_arima_forecast_insufficient_data(self):
        forecaster, _, _ = self._make_forecaster()
        result = forecaster.arima_forecast([1.0, 2.0], steps=3)
        assert "error" in result

    def test_arima_forecast_has_order(self):
        forecaster, _, _ = self._make_forecaster()
        series = list(range(20))
        result = forecaster.arima_forecast(series, order=(1, 1, 1), steps=3)
        assert result["order"] == (1, 1, 1)

    def test_auto_arima_selects_order(self):
        forecaster, _, _ = self._make_forecaster()
        series = [1.0 + i * 0.5 + (i % 3) * 0.1 for i in range(30)]
        result = forecaster.auto_arima(series, max_order=2)
        assert "selected_order" in result

    def test_get_forecast_with_intervals(self):
        forecaster, _, _ = self._make_forecaster()
        series = list(range(20))
        result = forecaster.get_forecast_with_intervals(series, steps=5)
        assert "intervals" in result
        assert len(result["intervals"]) == 5
        assert result["intervals"][0]["lower"] < result["intervals"][0]["upper"]

    def test_backtest_returns_metrics(self):
        forecaster, _, _ = self._make_forecaster()
        series = [1.0 + i * 0.5 for i in range(20)]
        result = forecaster.backtest(series, train_pct=0.7)
        assert "mae" in result
        assert "rmse" in result
        assert result["mae"] >= 0

    def test_backtest_insufficient_test_data(self):
        forecaster, _, _ = self._make_forecaster()
        result = forecaster.backtest([1.0, 2.0], train_pct=0.5)
        assert "error" in result


# ---------------------------------------------------------------------------
# ForecastAccuracy Tests
# ---------------------------------------------------------------------------

class TestForecastAccuracy:
    def _make_accuracy(self):
        from services.trends.accuracy import ForecastAccuracy
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return ForecastAccuracy(conn=mock_conn), mock_conn, mock_cursor

    def test_compute_mae_perfect(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_mae([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert result == 0.0

    def test_compute_mae_with_errors(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_mae([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
        assert result == 1.0

    def test_compute_rmse_with_errors(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_rmse([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
        assert result == 1.0

    def test_compute_mape_with_errors(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_mape([100.0, 200.0], [110.0, 190.0])
        assert result > 0

    def test_compute_bias_overprediction(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_bias([2.0, 3.0, 4.0], [1.0, 2.0, 3.0])
        assert result > 0

    def test_compute_bias_underprediction(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_bias([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
        assert result < 0

    def test_compute_bias_perfect(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_bias([1.0, 2.0], [1.0, 2.0])
        assert result == 0.0

    def test_compute_mae_empty(self):
        accuracy, _, _ = self._make_accuracy()
        result = accuracy.compute_mae([], [])
        assert result == 0.0
