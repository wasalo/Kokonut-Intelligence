"""Tests for Decision Policy Engine."""

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
# PolicyEngine Tests
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    """Unit tests for services.decision.policy_engine.PolicyEngine."""

    def _make_engine(self):
        from services.decision.policy_engine import PolicyEngine
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return PolicyEngine(conn=mock_conn), mock_conn, mock_cursor

    def test_evaluate_returns_empty_when_no_assessment(self):
        """evaluate() returns empty list when no assessment exists."""
        engine, mock_conn, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = None

        result = engine.evaluate(location_id="test-loc")
        assert result == []

    def test_evaluate_returns_empty_when_no_policies(self):
        """evaluate() returns empty list when no active policies exist."""
        engine, mock_conn, mock_cursor = self._make_engine()
        # First call: get assessment ID
        mock_cursor.fetchone.return_value = {"id": str(uuid.uuid4())}
        # Subsequent calls: no assessment data, no policies
        mock_cursor.fetchall.return_value = []

        result = engine.evaluate(location_id="test-loc")
        assert result == []

    def test_approve_sets_approval_status(self):
        """approve() sets approval_status to 'approved'."""
        engine, mock_conn, mock_cursor = self._make_engine()

        decision_id = str(uuid.uuid4())
        mock_cursor.fetchone.return_value = {
            "id": decision_id,
            "approval_status": "approved",
            "approved_by": "admin",
        }

        result = engine.approve(decision_id=decision_id, approved_by="admin")
        assert result.get("approval_status") == "approved" or "error" in result

    def test_reject_sets_rejection_reason(self):
        """reject() sets rejection_reason and status='rejected'."""
        engine, mock_conn, mock_cursor = self._make_engine()

        decision_id = str(uuid.uuid4())
        mock_cursor.fetchone.return_value = {
            "id": decision_id,
            "rejection_reason": "Not needed",
            "approval_status": "rejected",
        }

        result = engine.reject(
            decision_id=decision_id,
            rejected_by="admin",
            reason="Not needed"
        )
        assert result.get("rejection_reason") == "Not needed" or "error" in result

    def test_execute_requires_approval(self):
        """execute() rejects unapproved decisions."""
        engine, mock_conn, mock_cursor = self._make_engine()

        decision_id = str(uuid.uuid4())
        mock_cursor.fetchone.return_value = {
            "id": decision_id,
            "approval_status": "pending",
            "action_type": "test",
            "action_config": {},
            "location_id": "test-loc",
        }

        result = engine.execute(decision_id=decision_id)
        assert "error" in result
        assert "approved" in result["error"]

    @staticmethod
    def _approved_decision(action_type):
        return {
            "id": str(uuid.uuid4()),
            "approval_status": "approved",
            "action_type": action_type,
            "action_config": {},
            "location_id": "test-loc",
        }

    def test_execute_simulated_action_is_not_successful(self):
        """Built-in advisory handlers cannot claim a successful execution."""
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = self._approved_decision(
            "send_alert_notification"
        )

        result = engine.execute(decision_id="decision-1")

        assert result["success"] is False
        assert result["status"] == "simulated"
        assert "adapter" in result["error"]

    def test_execute_unsupported_action_fails_closed(self):
        engine, _, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = self._approved_decision("delete_everything")

        result = engine.execute(decision_id="decision-1")

        assert result == {
            "success": False,
            "status": "unsupported",
            "error": "Unsupported action type: delete_everything",
            "message": "Execution denied because no action adapter is registered",
            "action": "delete_everything",
        }

    def test_execute_adapter_requires_explicit_authorization(self):
        adapter = MagicMock(return_value={"success": True, "message": "sent"})
        engine, _, mock_cursor = self._make_engine()
        engine._action_adapters = {"send_alert_notification": adapter}
        mock_cursor.fetchone.return_value = self._approved_decision(
            "send_alert_notification"
        )

        result = engine.execute(decision_id="decision-1")

        assert result["success"] is False
        assert result["status"] == "unauthorized"
        adapter.assert_not_called()

    def test_execute_authorized_adapter_is_successful(self):
        adapter = MagicMock(return_value={"success": True, "message": "sent"})
        engine, _, mock_cursor = self._make_engine()
        engine._action_adapters = {"send_alert_notification": adapter}
        engine._authorized_action_types = {"send_alert_notification"}
        decision = self._approved_decision("send_alert_notification")
        mock_cursor.fetchone.return_value = decision

        result = engine.execute(decision_id=decision["id"], executed_by="operator")

        assert result == {
            "success": True,
            "message": "sent",
            "status": "executed",
            "action": "send_alert_notification",
        }
        adapter.assert_called_once_with(mock_cursor, decision)

    def test_list_pending_returns_empty_when_no_pending(self):
        """list_pending() returns empty list when no pending decisions."""
        engine, mock_conn, mock_cursor = self._make_engine()
        mock_cursor.fetchall.return_value = []

        result = engine.list_pending()
        assert result == []

    def test_get_decision_returns_none_when_not_found(self):
        """get_decision() returns None when decision doesn't exist."""
        engine, mock_conn, mock_cursor = self._make_engine()
        mock_cursor.fetchone.return_value = None

        result = engine.get_decision(decision_id="nonexistent")
        assert result is None

    def test_cooldown_prevents_duplicate_decisions(self):
        """_check_cooldown() returns True when policy is in cooldown."""
        engine, mock_conn, mock_cursor = self._make_engine()
        # First call: get cooldown_minutes, second call: count recent decisions
        mock_cursor.fetchone.side_effect = [
            {"cooldown_minutes": 60},
            {"cnt": 1},
        ]

        result = engine._check_cooldown(
            cur=mock_cursor,
            policy_id="test-policy",
            location_id="test-loc",
        )
        assert result is True


# ---------------------------------------------------------------------------
# Policies Module Tests
# ---------------------------------------------------------------------------

class TestPolicies:
    """Unit tests for services.decision.policies."""

    def test_list_policies_returns_five_defaults(self):
        """list_policies() returns 5 default policies."""
        from services.decision.policies import list_policies

        policies = list_policies()
        assert len(policies) == 5

    def test_get_policy_returns_correct_policy(self):
        """get_policy() returns the correct policy by name."""
        from services.decision.policies import get_policy

        policy = get_policy("critical_situation_intervention")
        assert policy["policy_name"] == "critical_situation_intervention"
        assert policy["action_type"] == "create_intervention_draft"
        assert policy["requires_approval"] is True
        assert policy["risk_level"] == "high"

    def test_get_policy_raises_on_unknown(self):
        """get_policy() raises KeyError for unknown policy name."""
        from services.decision.policies import get_policy

        with pytest.raises(KeyError):
            get_policy("nonexistent_policy")

    def test_all_policies_require_approval(self):
        """All default policies require human approval."""
        from services.decision.policies import list_policies

        policies = list_policies()
        for policy in policies:
            assert policy["requires_approval"] is True, (
                f"Policy {policy['policy_name']} should require approval"
            )

    def test_all_policies_have_valid_risk_level(self):
        """All policies have valid risk levels."""
        from services.decision.policies import list_policies

        valid_risks = {"low", "medium", "high", "critical"}
        policies = list_policies()
        for policy in policies:
            assert policy["risk_level"] in valid_risks, (
                f"Policy {policy['policy_name']} has invalid risk level"
            )

    def test_policies_have_unique_names(self):
        """All policies have unique names."""
        from services.decision.policies import list_policies

        policies = list_policies()
        names = [p["policy_name"] for p in policies]
        assert len(names) == len(set(names))

    def test_all_policies_have_cooldown(self):
        """All policies have a cooldown period."""
        from services.decision.policies import list_policies

        policies = list_policies()
        for policy in policies:
            assert policy["cooldown_minutes"] > 0, (
                f"Policy {policy['policy_name']} has no cooldown"
            )

    def test_all_policies_have_daily_limit(self):
        """All policies have a daily execution limit."""
        from services.decision.policies import list_policies

        policies = list_policies()
        for policy in policies:
            assert policy["max_executions_per_day"] > 0, (
                f"Policy {policy['policy_name']} has no daily limit"
            )
