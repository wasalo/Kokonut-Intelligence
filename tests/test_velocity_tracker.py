"""Tests for Adaptation Velocity Tracker."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestAdaptationVelocityTracker:
    def _make_tracker(self):
        from services.systems.velocity_tracker import AdaptationVelocityTracker
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return AdaptationVelocityTracker(conn=mock_conn), mock_conn, mock_cursor

    def test_compute_velocity_returns_structured_result(self):
        tracker, _, mock_cursor = self._make_tracker()
        # Return None for all fetchone calls — code handles missing data gracefully
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        result = tracker.compute_velocity("test-loc", period_days=30)

        assert result["location_id"] == "test-loc"
        assert result["period_days"] == 30
        assert "velocity_status" in result
        assert "acceleration_score" in result

    def test_compute_velocity_insufficient_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        result = tracker.compute_velocity("test-loc")

        assert result["velocity_status"] == "insufficient_data"
        assert result["cycles_completed"] == 0

    def test_classify_acceleration_returns_status(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        result = tracker.classify_acceleration("test-loc")

        assert "velocity_status" in result
        assert "acceleration_score" in result
        assert result["location_id"] == "test-loc"

    def test_get_velocity_history_returns_list(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.get_velocity_history("test-loc", limit=5)

        assert isinstance(result, list)

    def test_record_velocity_persists(self):
        tracker, mock_conn, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        result = tracker.record_velocity("test-loc", period_days=30)

        assert "id" in result
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_get_global_velocity_insufficient_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = {
            "global_avg_cycle_ms": None,
            "global_feedback_rate": None,
            "global_feedback_success": None,
            "global_effectiveness": None,
            "global_acceleration": None,
            "locations_tracked": None,
            "total_cycles": None,
        }

        result = tracker.get_global_velocity()

        assert result["status"] == "insufficient_data"
        assert result["locations_tracked"] == 0

    def test_get_global_velocity_with_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = {
            "global_avg_cycle_ms": 3000.0,
            "global_feedback_rate": 2.5,
            "global_feedback_success": 75.0,
            "global_effectiveness": 65.0,
            "global_acceleration": 15.0,
            "locations_tracked": 3,
            "total_cycles": 50,
        }

        result = tracker.get_global_velocity()

        assert result["locations_tracked"] == 3
        assert result["global_acceleration_score"] == 15.0

    def test_compute_trend_insufficient_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.compute_trend("test-loc", "yield")

        assert result["trend_direction"] == "insufficient_data"
        assert result["data_points"] == 0

    def test_compute_trend_with_data(self):
        tracker, _, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = [
            {
                "metric_name": "yield",
                "metric_domain": "farm",
                "trend_direction": "improving",
                "trend_strength": 0.8,
                "periods_in_trend": 3,
                "pct_change": 5.0,
                "learning_rate": 2.0,
                "estimated_plateau": 100.0,
                "projected_plateau_periods": 10,
                "created_at": datetime.now(timezone.utc),
            }
        ]

        result = tracker.compute_trend("test-loc", "yield")

        assert result["trend_direction"] == "improving"
        assert result["trend_strength"] == 0.8
        assert result["data_points"] == 1
