from unittest.mock import MagicMock

from services.feedback.automation import FeedbackAutomation


def _persisted_failure(cursor):
    failure_call = next(
        call
        for call in cursor.execute.call_args_list
        if "SET status = 'failed'" in call.args[0]
    )
    return failure_call.args[1][0].adapted[0]


def test_feedback_evaluation_redacts_and_persists_safe_failure():
    secret = "database password and private outcome text"
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor

    def execute(query, *_args):
        if "SELECT ao.*" in query:
            raise RuntimeError(secret)

    cursor.execute.side_effect = execute
    result = FeedbackAutomation(conn=conn).run_evaluation("location-1")

    assert result["status"] == "failed"
    assert result["error"] == "feedback evaluation failed (RuntimeError)"
    assert secret not in repr(result)
    assert _persisted_failure(cursor) == result["error"]
    conn.rollback.assert_called_once_with()
    assert conn.commit.call_count == 2
    cursor.close.assert_called_once_with()


def test_feedback_cycle_redacts_and_persists_safe_failure(monkeypatch):
    secret = "private decision payload"
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    automation = FeedbackAutomation(conn=conn, dry_run=False)
    monkeypatch.setattr(
        automation,
        "run_evaluation",
        lambda *_args, **_kwargs: {
            "signals": [{"signal_type": "synthetic"}],
            "outcomes_evaluated": 1,
            "signals_generated": 1,
        },
    )
    monkeypatch.setattr(
        automation,
        "_apply_signal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError(secret)),
    )

    result = automation.run_full_cycle("location-1")

    assert result["status"] == "failed"
    assert result["error"] == "feedback cycle failed (ValueError)"
    assert secret not in repr(result)
    assert _persisted_failure(cursor) == result["error"]
    conn.rollback.assert_called_once_with()
    assert conn.commit.call_count == 2
    cursor.close.assert_called_once_with()
