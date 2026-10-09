"""Tests for OODA Cycle Tracker."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    """Create a mock connection that returns mock_cursor directly."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# OODACycleTracker Integration-Style Tests
# ---------------------------------------------------------------------------

class TestOODACycleTrackerIntegration:
    """Tests that exercise multiple tracker operations together."""

    def _make_tracker(self):
        from services.orientation.cycle_tracker import OODACycleTracker
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return OODACycleTracker(conn=mock_conn), mock_conn, mock_cursor

    def test_full_cycle_happy_path(self):
        """Complete a full OODA cycle: start -> observe -> orient -> decide -> act -> complete."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr_id = tracker.start_cycle(
            location_id="test-loc",
            cycle_type="automated",
            decision_type="intervention",
        )
        assert corr_id is not None

        tracker.complete_phase(corr_id, "observe", duration_ms=100)
        tracker.complete_phase(corr_id, "orient", duration_ms=200, framework_used="crisp")
        tracker.complete_phase(corr_id, "decide", duration_ms=50, policy_id="p1", decision_id="d1")
        tracker.complete_phase(corr_id, "act", duration_ms=150, action_type="alert")
        tracker.complete_cycle(corr_id, status="completed", outcome_type="effective")

        assert mock_cursor.execute.call_count >= 5

    def test_cycle_timeout(self):
        """A cycle can be marked as timed out."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr_id = tracker.start_cycle(
            location_id="test-loc",
            cycle_type="automated",
            decision_type="slow_operation",
        )

        tracker.complete_cycle(
            corr_id,
            status="timeout",
            failure_phase="orient",
            error_message="Orient phase exceeded 30s timeout",
        )

        mock_cursor.execute.assert_called()

    def test_cycle_failure_at_decide_phase(self):
        """A cycle can fail at the decide phase."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr_id = tracker.start_cycle(
            location_id="test-loc",
            cycle_type="automated",
            decision_type="decision",
        )

        tracker.complete_phase(corr_id, "observe", duration_ms=100)
        tracker.complete_phase(corr_id, "orient", duration_ms=200)
        tracker.complete_cycle(
            corr_id,
            status="failed",
            failure_phase="decide",
            error_message="No policy matched",
        )

        mock_cursor.execute.assert_called()

    def test_cycle_with_manual_type(self):
        """A cycle can be of type 'manual'."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr_id = tracker.start_cycle(
            location_id="test-loc",
            cycle_type="manual",
            decision_type="operator_decision",
        )

        call_args = str(mock_cursor.execute.call_args)
        assert "manual" in call_args

    def test_multiple_cycles_independent(self):
        """Multiple cycles can run independently."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr1 = tracker.start_cycle(location_id="loc-1", decision_type="type-a")
        corr2 = tracker.start_cycle(location_id="loc-2", decision_type="type-b")

        assert corr1 != corr2

        tracker.complete_phase(corr1, "observe", duration_ms=50)
        tracker.complete_phase(corr2, "observe", duration_ms=75)

        tracker.complete_cycle(corr1, status="completed")
        tracker.complete_cycle(corr2, status="completed")

        assert mock_cursor.execute.call_count >= 4

    def test_orient_phase_records_framework(self):
        """The orient phase can record which framework was used."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr_id = tracker.start_cycle(location_id="test-loc", decision_type="test")

        tracker.complete_phase(
            corr_id,
            "orient",
            duration_ms=300,
            framework_used="ecological_modeling",
        )

        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("orient_frameworks_used" in c for c in calls)

    def test_act_phase_records_outcome_id(self):
        """The act phase can record the action outcome ID."""
        tracker, mock_conn, mock_cursor = self._make_tracker()

        corr_id = tracker.start_cycle(location_id="test-loc", decision_type="test")
        outcome_id = str(uuid.uuid4())

        tracker.complete_phase(
            corr_id,
            "act",
            duration_ms=100,
            action_type="send_alert",
            action_outcome_id=outcome_id,
        )

        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("act_outcome_id" in c for c in calls)

    def test_list_recent_with_limit(self):
        """list_recent() respects the limit parameter."""
        tracker, mock_conn, mock_cursor = self._make_tracker()
        mock_cursor.fetchall.return_value = [
            {"id": str(uuid.uuid4())} for _ in range(5)
        ]

        result = tracker.list_recent(limit=5)
        assert len(result) == 5
