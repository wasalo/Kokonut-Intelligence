"""Tests for OODA Orientation — SituationAssessor and OODACycleTracker."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


def _make_mock_conn(mock_cursor):
    """Create a mock connection that returns mock_cursor directly."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# SituationAssessor Tests
# ---------------------------------------------------------------------------

class TestSituationAssessor:
    """Unit tests for services.orientation.assess.SituationAssessor."""

    def _make_assessor(self):
        from services.orientation.assess import SituationAssessor
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return SituationAssessor(conn=mock_conn), mock_conn, mock_cursor

    def test_assess_returns_required_fields(self):
        """assess() returns a dict with all required fields."""
        assessor, mock_conn, mock_cursor = self._make_assessor()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        result = assessor.assess(location_id="test-loc-001")

        assert "assessment_id" in result
        assert "situation_grade" in result
        assert "composite_score" in result
        assert "confidence_level" in result
        assert "evidence_maturity" in result
        assert "signal_count" in result
        assert "recommendation_count" in result

    def test_assess_assigns_valid_grade(self):
        """assess() assigns a valid grade."""
        assessor, mock_conn, mock_cursor = self._make_assessor()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        result = assessor.assess(location_id="test-loc-002")
        assert result["situation_grade"] in ("critical", "warning", "stable", "flourishing")

    def test_assess_persists_dimensions(self):
        """assess() persists 5 dimension summaries even with no data."""
        assessor, mock_conn, mock_cursor = self._make_assessor()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        assessor.assess(location_id="test-loc-003")

        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        dim_inserts = [c for c in calls if "assessment_dimension" in c]
        assert len(dim_inserts) == 5

    def test_assess_persists_assessment_record(self):
        """assess() persists the assessment to situation_assessment table."""
        assessor, mock_conn, mock_cursor = self._make_assessor()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        assessor.assess(location_id="test-loc-004")

        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assessment_inserts = [c for c in calls if "situation_assessment" in c]
        assert len(assessment_inserts) == 1

    def test_assess_generates_recommendations(self):
        """assess() generates recommendations based on signals."""
        assessor, mock_conn, mock_cursor = self._make_assessor()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        result = assessor.assess(location_id="test-loc-005")
        assert isinstance(result["recommendation_count"], int)

    def test_get_latest_returns_none_when_no_assessment(self):
        """get_latest() returns None when no assessment exists."""
        assessor, mock_conn, mock_cursor = self._make_assessor()
        mock_cursor.fetchone.return_value = None

        result = assessor.get_latest(location_id="test-loc-nonexistent")
        assert result is None

    def test_grade_thresholds_correct(self):
        """Grade thresholds cover the full 0-100 range."""
        from services.orientation.assess import GRADE_THRESHOLDS

        all_ranges = []
        for grade, (low, high) in GRADE_THRESHOLDS.items():
            all_ranges.append((low, high))
            assert low < high, f"Grade {grade} has invalid range: {low}-{high}"

        all_ranges.sort()
        assert all_ranges[0][0] == 0


# ---------------------------------------------------------------------------
# OODACycleTracker Tests
# ---------------------------------------------------------------------------

class TestOODACycleTracker:
    """Unit tests for services.orientation.cycle_tracker.OODACycleTracker."""

    def _make_tracker(self):
        from services.orientation.cycle_tracker import OODACycleTracker
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return OODACycleTracker(conn=mock_conn), mock_conn, mock_cursor

    def test_start_cycle_returns_correlation_id(self):
        """start_cycle() returns a valid correlation ID."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        correlation_id = tracker.start_cycle(
            location_id="test-loc-001",
            cycle_type="automated",
            decision_type="test_decision",
        )

        assert correlation_id is not None
        assert isinstance(correlation_id, str)
        mock_cursor.execute.assert_called_once()

    def test_start_cycle_generates_uuid_if_not_provided(self):
        """start_cycle() generates a UUID when no correlation_id is given."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        correlation_id = tracker.start_cycle(location_id="test-loc")

        uuid_obj = uuid.UUID(correlation_id)
        assert str(uuid_obj) == correlation_id

    def test_complete_phase_updates_cycle(self):
        """complete_phase() updates the cycle record."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        tracker.complete_phase(
            correlation_id="test-corr-001",
            phase="observe",
            duration_ms=150,
        )

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_complete_act_calculates_total_time(self):
        """complete_phase('act') sets total_cycle_time_ms."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        tracker.complete_phase(
            correlation_id="test-corr-002",
            phase="act",
            duration_ms=500,
            action_type="send_alert",
        )

        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("total_cycle_time_ms" in c for c in calls)

    def test_complete_cycle_sets_status(self):
        """complete_cycle() sets the final status."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        tracker.complete_cycle(
            correlation_id="test-corr-003",
            status="completed",
            outcome_type="effective",
        )

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_get_cycle_returns_none_when_not_found(self):
        """get_cycle() returns None when correlation ID doesn't exist."""
        tracker, mock_conn, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = None

        result = tracker.get_cycle(correlation_id="nonexistent")
        assert result is None

    def test_get_stats_returns_zero_when_no_cycles(self):
        """get_stats() returns zero stats when no completed cycles exist."""
        tracker, mock_conn, mock_cursor = self._make_tracker()
        mock_cursor.fetchone.return_value = {
            "total_cycles": 0,
            "avg_cycle_time_ms": None,
            "min_cycle_time_ms": None,
            "max_cycle_time_ms": None,
            "median_cycle_time_ms": None,
            "avg_observe_ms": None,
            "avg_orient_ms": None,
            "avg_decide_ms": None,
            "avg_act_ms": None,
            "effective_count": None,
            "ineffective_count": None,
            "unknown_outcome_count": None,
        }

        stats = tracker.get_stats()
        assert stats["total_cycles"] == 0

    def test_list_recent_returns_empty_when_no_cycles(self):
        """list_recent() returns empty list when no cycles exist."""
        tracker, mock_conn, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = []

        result = tracker.list_recent()
        assert result == []
