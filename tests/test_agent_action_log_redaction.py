"""Agent action audit errors retain presence without raw diagnostic text."""

from unittest.mock import MagicMock

from services.agents import logging as agent_logging

DIAGNOSTIC = "synthetic provider credential diagnostic"


def test_log_agent_action_redacts_error_before_persisting(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(agent_logging, "get_db", lambda: connection)

    result = agent_logging.log_agent_action(
        agent_id="agent-1",
        task_id=None,
        action="read",
        collection="location",
        action_result="failed",
        error_message=DIAGNOSTIC,
    )

    parameters = cursor.execute.call_args.args[1]
    assert result
    assert parameters[8] == "[details redacted]"
    assert DIAGNOSTIC not in str(parameters)
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_get_agent_actions_redacts_historical_error_before_returning(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{"id": "action-1", "action_result": "failed", "error_message": DIAGNOSTIC}]
    monkeypatch.setattr(agent_logging, "get_db", lambda: connection)

    result = agent_logging.get_agent_actions(agent_id="agent-1")

    assert result == [{"id": "action-1", "action_result": "failed", "error_message": "[details redacted]"}]
    assert DIAGNOSTIC not in str(result)
    connection.close.assert_called_once_with()


def test_agent_action_log_failure_logs_class_not_exception_text(monkeypatch):
    connection = MagicMock()
    connection.cursor.side_effect = RuntimeError(DIAGNOSTIC)
    monkeypatch.setattr(agent_logging, "get_db", lambda: connection)
    logger_error = MagicMock()
    monkeypatch.setattr(agent_logging.logger, "error", logger_error)

    agent_logging.log_agent_action(
        agent_id="agent-1",
        task_id=None,
        action="read",
        collection="location",
    )

    logger_error.assert_called_once_with("Failed to log agent action (%s)", "RuntimeError")
    assert DIAGNOSTIC not in str(logger_error.call_args)
    connection.close.assert_called_once_with()
