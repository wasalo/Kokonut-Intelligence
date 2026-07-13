"""Tests for Growth Curve Analyzer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestGrowthCurveAnalyzer:
    def _make_analyzer(self):
        from services.systems.growth_curve import GrowthCurveAnalyzer
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return GrowthCurveAnalyzer(conn=mock_conn), mock_conn, mock_cursor

    def test_analyze_metric_insufficient_data(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []

        result = analyzer.analyze_metric("test-loc", "yield")

        assert result["curve_type"] == "insufficient_data"
        assert result["data_points_used"] == 0

    def test_analyze_metric_with_data_points(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []

        data_points = [
            {"value": 100, "date": datetime.now(timezone.utc)},
            {"value": 120, "date": datetime.now(timezone.utc)},
            {"value": 140, "date": datetime.now(timezone.utc)},
            {"value": 160, "date": datetime.now(timezone.utc)},
        ]

        result = analyzer.analyze_metric("test-loc", "yield", data_points=data_points)

        assert result["curve_type"] in ("linear", "exponential", "logarithmic", "s_curve", "declining")
        assert result["data_points_used"] == 4
        assert "fit_quality" in result

    def test_detect_tipping_points_returns_list(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []

        result = analyzer.detect_tipping_points("test-loc")

        assert isinstance(result, list)

    def test_detect_exponential_growth_returns_list(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []

        result = analyzer.detect_exponential_growth("test-loc")

        assert isinstance(result, list)

    def test_detect_saturation_returns_list(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []

        result = analyzer.detect_saturation("test-loc")

        assert isinstance(result, list)

    def test_get_curve_report_empty(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = []

        result = analyzer.get_curve_report("test-loc")

        assert result["total_metrics"] == 0
        assert result["exponential"] == 0

    def test_get_curve_report_with_data(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchall.return_value = [
            {
                "metric_name": "yield",
                "curve_type": "exponential",
                "fit_quality": 0.8,
                "current_velocity": 5.0,
                "acceleration": 2.0,
                "tipping_point_risk": 0.3,
                "current_position_pct": None,
                "analyzed_at": datetime.now(timezone.utc),
            },
            {
                "metric_name": "soil_moisture",
                "curve_type": "logarithmic",
                "fit_quality": 0.7,
                "current_velocity": 1.0,
                "acceleration": -0.5,
                "tipping_point_risk": 0.1,
                "current_position_pct": 80.0,
                "analyzed_at": datetime.now(timezone.utc),
            },
        ]

        result = analyzer.get_curve_report("test-loc")

        assert result["total_metrics"] == 2
        assert result["exponential"] == 1
        assert result["logarithmic"] == 1

    def test_predict_trajectory_no_data(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchone.return_value = None

        result = analyzer.predict_trajectory("test-loc", "yield", periods_ahead=5)

        assert result["projections"] == []
        assert result["curve_type"] == "unknown"

    def test_predict_trajectory_with_analysis(self):
        analyzer, _, mock_cursor = self._make_analyzer()
        mock_cursor.fetchone.return_value = {
            "metric_name": "yield",
            "curve_type": "linear",
            "current_velocity": 10.0,
            "acceleration": 0.0,
            "current_position_pct": 50.0,
        }

        result = analyzer.predict_trajectory("test-loc", "yield", periods_ahead=3)

        assert result["curve_type"] == "linear"
        assert len(result["projections"]) == 3
        assert result["projections"][0]["period"] == 1

    def test_fit_curve_linear(self):
        analyzer, _, _ = self._make_analyzer()
        values = [10, 20, 30, 40, 50]

        curve_type, quality, params = analyzer._fit_curve(values)

        assert curve_type == "linear"
        assert quality > 0.3

    def test_fit_curve_oscillating(self):
        analyzer, _, _ = self._make_analyzer()
        values = [10, 50, 10, 50, 10, 50]

        curve_type, quality, params = analyzer._fit_curve(values)

        assert curve_type == "oscillating"

    def test_compute_velocity(self):
        analyzer, _, _ = self._make_analyzer()

        # Uses last 3 points: (30 - 10) / 3 = 6.6667
        assert analyzer._compute_velocity([10, 20, 30]) == round(20 / 3, 4)
        assert analyzer._compute_velocity([10]) == 0.0
        assert analyzer._compute_velocity([]) == 0.0
