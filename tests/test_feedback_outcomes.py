"""Focused tests for durable metric-backed outcome measurement."""

from unittest.mock import MagicMock


def test_metric_fetch_joins_canonical_metric_id_and_parameterizes_window():
    from services.feedback.outcomes import ActionOutcomeTracker

    cursor = MagicMock()
    cursor.fetchall.return_value = []
    tracker = ActionOutcomeTracker(conn=MagicMock())

    tracker._fetch_recent_metrics(cursor, "location-1", 24)

    query, params = cursor.execute.call_args.args
    assert "mv.metric_id" in query
    assert "mv.metric_definition_id" not in query
    assert "INTERVAL '1 hour'" in query
    assert params == ("location-1", 24)


def test_automation_signal_is_proposal_not_application():
    from services.feedback.automation import FeedbackAutomation

    cursor = MagicMock()
    cursor.rowcount = 1
    automation = FeedbackAutomation(conn=MagicMock(), dry_run=False)

    result = automation._apply_signal(cursor, {
        "outcome_id": "outcome-1",
        "action_type": "alert",
        "location_id": "location-1",
        "recommendation": "increase_threshold",
        "reason": "ineffective outcome",
    })

    assert result == {"proposed": True, "applied": False, "adjusted": False}
