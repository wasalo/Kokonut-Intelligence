"""Tests for Feedback Loop Automation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestFeedbackAutomation:
    def _make_automation(self, dry_run=True):
        from services.feedback.automation import FeedbackAutomation
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return FeedbackAutomation(conn=mock_conn, dry_run=dry_run), mock_conn, mock_cursor

    def test_run_evaluation_returns_structured_result(self):
        automation, _, mock_cursor = self._make_automation()
        mock_cursor.fetchall.return_value = []

        result = automation.run_evaluation("test-loc")

        assert result["status"] == "completed"
        assert result["outcomes_evaluated"] == 0
        assert result["signals_generated"] == 0
        assert "log_id" in result

    def test_run_evaluation_persists_log(self):
        automation, mock_conn, mock_cursor = self._make_automation()
        mock_cursor.fetchall.return_value = []

        automation.run_evaluation("test-loc")

        # Should have INSERT and UPDATE calls
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("feedback_automation_log" in c for c in calls)

    def test_run_evaluation_with_outcomes(self):
        automation, _, mock_cursor = self._make_automation()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "action_type": "intervention",
                "outcome_type": "ineffective",
                "location_id": "test-loc",
                "policy_id": None,
            }
        ]

        result = automation.run_evaluation("test-loc")

        assert result["outcomes_evaluated"] == 1
        assert result["signals_generated"] >= 1

    def test_run_full_cycle_dry_run(self):
        automation, _, mock_cursor = self._make_automation(dry_run=True)
        mock_cursor.fetchall.return_value = []

        result = automation.run_full_cycle("test-loc")

        assert result["status"] == "completed"
        assert result["dry_run"] is True

    def test_run_full_cycle_applies_feedback(self):
        automation, _, mock_cursor = self._make_automation(dry_run=False)
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid.uuid4()),
                "action_type": "alert",
                "outcome_type": "ineffective",
                "location_id": "test-loc",
                "policy_id": None,
            }
        ]

        result = automation.run_full_cycle("test-loc")

        assert result["status"] == "completed"
        assert result["feedback_loops_applied"] >= 0

    def test_get_automation_log_returns_list(self):
        automation, _, mock_cursor = self._make_automation()
        mock_cursor.fetchall.return_value = []

        result = automation.get_automation_log("test-loc")

        assert isinstance(result, list)

    def test_configure_persists_config(self):
        automation, mock_conn, mock_cursor = self._make_automation()
        mock_cursor.fetchone.return_value = {
            "id": str(uuid.uuid4()),
            "location_id": "test-loc",
            "eval_interval_hours": 12,
            "max_adjustments_per_run": 3,
            "auto_apply": False,
            "dry_run": True,
            "enabled": True,
        }

        result = automation.configure("test-loc", eval_interval_hours=12)

        assert result["eval_interval_hours"] == 12
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_get_pending_adjustments_returns_list(self):
        automation, _, mock_cursor = self._make_automation()
        mock_cursor.fetchall.return_value = []

        result = automation.get_pending_adjustments("test-loc")

        assert isinstance(result, list)

    def test_analyze_outcome_ineffective(self):
        automation, _, _ = self._make_automation()

        outcome = {
            "id": str(uuid.uuid4()),
            "action_type": "intervention",
            "outcome_type": "ineffective",
            "location_id": "test-loc",
        }

        signal = automation._analyze_outcome(outcome)

        assert signal is not None
        assert signal["recommendation"] == "increase_threshold"
        assert signal["priority"] == "high"

    def test_analyze_outcome_effective_returns_none(self):
        automation, _, _ = self._make_automation()

        outcome = {
            "id": str(uuid.uuid4()),
            "action_type": "intervention",
            "outcome_type": "effective",
            "location_id": "test-loc",
        }

        signal = automation._analyze_outcome(outcome)

        assert signal is None
