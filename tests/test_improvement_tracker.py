"""Tests for Improvement Rate Tracker."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestImprovementRateTracker:
    def _make_tracker(self):
        from services.systems.improvement_tracker import ImprovementRateTracker
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return ImprovementRateTracker(conn=mock_conn), mock_conn, mock_cursor

    def test_record_improvement_returns_structured_result(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = None

        now = datetime.now(timezone.utc)
        result = tracker.record_improvement(
            "test-loc", "yield", 2500.0, now, now, metric_domain="farm"
        )

        assert "id" in result
        assert result["metric_name"] == "yield"
        assert result["current_value"] == 2500.0
        assert result["prior_value"] is None
        assert result["absolute_change"] is None

    def test_record_improvement_with_prior(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = {
            "current_value": 2000.0,
            "baseline_value": 1500.0,
        }

        now = datetime.now(timezone.utc)
        result = tracker.record_improvement(
            "test-loc", "yield", 2500.0, now, now
        )

        assert result["prior_value"] == 2000.0
        assert result["absolute_change"] == 500.0
        assert result["pct_change"] == 25.0

    def test_record_improvement_persists(self):
        tracker, mock_conn, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = None

        now = datetime.now(timezone.utc)
        tracker.record_improvement("test-loc", "yield", 2500.0, now, now)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_get_improvement_report_empty(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.get_improvement_report("test-loc")

        assert result["total_metrics"] == 0
        assert result["improving"] == 0
        assert result["degrading"] == 0

    def test_get_improvement_report_with_metrics(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = [
            {
                "metric_name": "yield",
                "metric_domain": "farm",
                "current_value": 2500.0,
                "pct_change": 5.0,
                "trend_direction": "improving",
                "trend_strength": 0.8,
                "learning_rate": 2.0,
                "estimated_plateau": 3000.0,
                "projected_plateau_periods": 10,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "metric_name": "soil_moisture",
                "metric_domain": "ecological",
                "current_value": 45.0,
                "pct_change": -3.0,
                "trend_direction": "degrading",
                "trend_strength": 0.6,
                "learning_rate": -1.0,
                "estimated_plateau": None,
                "projected_plateau_periods": None,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        result = tracker.get_improvement_report("test-loc")

        assert result["total_metrics"] == 2
        assert result["improving"] == 1
        assert result["degrading"] == 1

    def test_detect_plateau_insufficient_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.detect_plateau("test-loc", "yield")

        assert result["plateau_detected"] is False
        assert result["reason"] == "insufficient_data"

    def test_detect_plateau_with_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        # Simulate stable values (plateau)
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {"current_value": 100.0, "created_at": now},
            {"current_value": 100.5, "created_at": now},
            {"current_value": 99.8, "created_at": now},
            {"current_value": 100.2, "created_at": now},
            {"current_value": 100.1, "created_at": now},
            {"current_value": 99.9, "created_at": now},
        ]

        result = tracker.detect_plateau("test-loc", "yield")

        assert result["metric"] == "yield"
        assert "plateau_detected" in result

    def test_detect_degradation_returns_list(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.detect_degradation("test-loc")

        assert isinstance(result, list)

    def test_get_learning_curve_empty(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.get_learning_curve("test-loc", "yield")

        assert result["metric"] == "yield"
        assert result["data_points"] == 0

    def test_get_learning_curve_with_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {"current_value": 100.0, "pct_change": None, "learning_rate": None,
             "estimated_plateau": None, "projected_plateau_periods": None,
             "period_start": now, "created_at": now},
            {"current_value": 120.0, "pct_change": 20.0, "learning_rate": 10.0,
             "estimated_plateau": 200.0, "projected_plateau_periods": 8,
             "period_start": now, "created_at": now},
            {"current_value": 140.0, "pct_change": 16.7, "learning_rate": 10.0,
             "estimated_plateau": 200.0, "projected_plateau_periods": 6,
             "period_start": now, "created_at": now},
        ]

        result = tracker.get_learning_curve("test-loc", "yield")

        assert result["data_points"] == 3
        assert len(result["values"]) == 3
        assert result["first_value"] == 100.0
        assert result["latest_value"] == 140.0

    def test_get_improvement_history_returns_list(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.get_improvement_history("test-loc", "yield", limit=10)

        assert isinstance(result, list)
