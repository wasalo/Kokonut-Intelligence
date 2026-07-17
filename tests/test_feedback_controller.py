"""Tests for Feedback Controller."""

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
# FeedbackController Tests
# ---------------------------------------------------------------------------

class TestFeedbackController:
    """Unit tests for services.feedback.controller.FeedbackController."""

    def _make_controller(self):
        from services.feedback.controller import FeedbackController
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return FeedbackController(conn=mock_conn), mock_conn, mock_cursor

    def test_record_outcome_returns_id(self):
        """record_outcome() returns a valid outcome ID."""
        controller, mock_conn, mock_cursor = self._make_controller()

        outcome_id = controller.record_outcome(
            action_type="intervention",
            action_source="policy_engine",
            location_id="test-loc",
            outcome_type="effective",
        )

        assert outcome_id is not None
        assert isinstance(outcome_id, str)
        mock_cursor.execute.assert_called_once()

    def test_record_outcome_persists_to_db(self):
        """record_outcome() inserts into action_outcome table."""
        controller, mock_conn, mock_cursor = self._make_controller()

        controller.record_outcome(
            action_type="alert",
            action_source="agent",
            location_id="test-loc",
            outcome_type="ineffective",
        )

        call_args = str(mock_cursor.execute.call_args)
        assert "action_outcome" in call_args

    def test_evaluate_outcomes_returns_empty_when_no_outcomes(self):
        """evaluate_outcomes() returns empty list when no outcomes exist."""
        controller, mock_conn, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []

        result = controller.evaluate_outcomes()
        assert result == []

    def test_apply_feedback_persists_loop(self):
        """apply_feedback() inserts into feedback_loop table."""
        controller, mock_conn, mock_cursor = self._make_controller()
        mock_cursor.fetchone.return_value = {"current_value": '{"sensitivity": 1.0}'}
        mock_cursor.rowcount = 1

        feedback_id = controller.apply_feedback(
            outcome_id=str(uuid.uuid4()),
            feedback_type="threshold_adjustment",
            target_entity="adaptive_threshold",
            target_entity_id=str(uuid.uuid4()),
            target_field="current_value",
            new_value={"sensitivity": 1.2},
            adjustment_reason="ineffective action detected",
            adjustment_magnitude=0.2,
            applied_by="reviewer-1",
        )

        assert feedback_id is not None
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("feedback_loop" in c for c in calls)

    def test_apply_feedback_requires_human_approver(self):
        controller, _, _ = self._make_controller()

        with pytest.raises(ValueError, match="human approver"):
            controller.apply_feedback(
                outcome_id=str(uuid.uuid4()),
                feedback_type="threshold_adjustment",
                target_entity="adaptive_threshold",
                target_entity_id=str(uuid.uuid4()),
                target_field="current_value",
                new_value={"sensitivity": 1.2},
                adjustment_reason="reviewed",
            )

    def test_record_outcome_rolls_back_on_insert_failure(self):
        controller, mock_conn, mock_cursor = self._make_controller()
        mock_cursor.execute.side_effect = RuntimeError("database unavailable")

        with pytest.raises(RuntimeError):
            controller.record_outcome(
                action_type="alert",
                action_source="agent",
                location_id="test-loc",
            )

        mock_conn.rollback.assert_called_once()

    def test_list_adaptive_thresholds_returns_empty_when_none(self):
        """list_adaptive_thresholds() returns empty list when none exist."""
        controller, mock_conn, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []

        result = controller.list_adaptive_thresholds()
        assert result == []

    def test_get_feedback_stats_returns_zeros_when_no_data(self):
        """get_feedback_stats() returns zero stats when no outcomes exist."""
        controller, mock_conn, mock_cursor = self._make_controller()

        mock_cursor.fetchone.return_value = {
            "total_outcomes": 0,
            "effective": 0,
            "partially_effective": 0,
            "ineffective": 0,
            "no_effect": 0,
            "counterproductive": 0,
            "unknown": 0,
            "feedback_applied_count": 0,
        }
        mock_cursor.fetchall.return_value = []

        stats = controller.get_feedback_stats()
        assert stats["total_outcomes"] == 0
        assert stats["effective_rate"] == 0.0

    def test_analyze_outcome_returns_none_for_unknown(self):
        """_analyze_outcome() returns None for unknown outcome type."""
        controller, mock_conn, mock_cursor = self._make_controller()

        result = controller._analyze_outcome({
            "outcome_type": "unknown",
            "id": str(uuid.uuid4()),
            "action_type": "test",
            "location_id": "test-loc",
        })
        assert result is None

    def test_analyze_outcome_returns_negative_for_ineffective(self):
        """_analyze_outcome() returns negative signal for ineffective actions."""
        controller, mock_conn, mock_cursor = self._make_controller()

        result = controller._analyze_outcome({
            "outcome_type": "ineffective",
            "id": str(uuid.uuid4()),
            "action_type": "intervention",
            "location_id": "test-loc",
        })
        assert result is not None
        assert result["signal"] == "negative"


# ---------------------------------------------------------------------------
# FeedbackController Auto-Tuning Tests
# ---------------------------------------------------------------------------

class TestFeedbackControllerAutoTuning:
    def _make_controller(self):
        from services.feedback.controller import FeedbackController
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return FeedbackController(conn=mock_conn), mock_conn, mock_cursor

    def test_auto_tune_thresholds_empty(self):
        controller, _, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []

        result = controller.auto_tune_thresholds(dry_run=True)

        assert result["thresholds_analyzed"] == 0
        assert result["adjustments_recommended"] == 0
        assert result["dry_run"] is True

    def test_auto_tune_thresholds_with_threshold(self):
        controller, _, mock_cursor = self._make_controller()
        threshold_id = str(uuid.uuid4())
        # First fetchall returns thresholds, subsequent calls return outcomes
        mock_cursor.fetchall.side_effect = [
            [{
                "id": threshold_id,
                "threshold_key": "test_threshold",
                "threshold_name": "Test Threshold",
                "entity_type": "anomaly_sensitivity",
                "location_id": "test-loc",
                "current_value": {"sensitivity": 1.0},
                "baseline_value": {"sensitivity": 1.0},
                "adaptation_rate": 0.1,
                "is_enabled": True,
            }],
            [],  # outcomes for analyze_threshold_performance
        ]

        result = controller.auto_tune_thresholds(dry_run=True)

        assert result["thresholds_analyzed"] == 1
        assert result["dry_run"] is True

    def test_get_tuning_history_returns_list(self):
        controller, _, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []

        result = controller.get_tuning_history()

        assert isinstance(result, list)

    def test_compute_optimal_threshold_no_match(self):
        controller, _, mock_cursor = self._make_controller()
        mock_cursor.fetchall.return_value = []

        result = controller.compute_optimal_threshold("test-loc", "nonexistent_metric")

        assert result["optimal_value"] is None
        assert result["reason"] == "no_matching_thresholds"
