"""Ensure report-generation subprocess output cannot expose report data."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from services.analytics import reporting_cadence


def _connection():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = {
        "auto_generate_report": True,
        "report_generator_command": "python3 -m services.export.report_generator",
    }
    return conn


def test_failed_report_command_redacts_stdout_and_stderr(monkeypatch):
    stdout_secret = "participant report content must stay private"
    stderr_secret = "database password=private at https://user:secret@example.invalid"
    conn = _connection()
    subprocess = MagicMock(return_value=SimpleNamespace(
        returncode=17,
        stdout=stdout_secret,
        stderr=stderr_secret,
    ))
    mark_completed = MagicMock()
    monkeypatch.setattr(reporting_cadence.subprocess, "run", subprocess)
    monkeypatch.setattr(reporting_cadence, "worker_subprocess_environment", lambda: {"PATH": "/usr/bin"})
    monkeypatch.setattr(reporting_cadence, "mark_completed", mark_completed)

    result = reporting_cadence.trigger_auto_generation(conn, "cadence-1")

    assert result == {
        "status": "failed",
        "output": "",
        "output_available": True,
        "exit_code": 17,
        "error": "report generator failed (exit code 17)",
    }
    assert stdout_secret not in repr(result)
    assert stderr_secret not in repr(result)
    mark_completed.assert_not_called()


def test_successful_report_command_does_not_return_report_output(monkeypatch):
    stdout_secret = "sensitive report output"
    conn = _connection()
    monkeypatch.setattr(
        reporting_cadence.subprocess,
        "run",
        MagicMock(return_value=SimpleNamespace(returncode=0, stdout=stdout_secret, stderr="")),
    )
    monkeypatch.setattr(reporting_cadence, "worker_subprocess_environment", lambda: {"PATH": "/usr/bin"})
    mark_completed = MagicMock(return_value={"status": "completed"})
    monkeypatch.setattr(reporting_cadence, "mark_completed", mark_completed)

    result = reporting_cadence.trigger_auto_generation(conn, "cadence-1")

    assert result == {
        "status": "success",
        "output": "",
        "output_available": True,
        "exit_code": 0,
        "error": None,
    }
    assert stdout_secret not in repr(result)
    mark_completed.assert_called_once_with(conn, "cadence-1")


def test_report_command_exception_returns_bounded_summary_and_closes_cursor(monkeypatch):
    secret = "command crashed with env token=private"
    conn = _connection()
    cursor = conn.cursor.return_value
    logger = MagicMock()
    monkeypatch.setattr(reporting_cadence.subprocess, "run", MagicMock(side_effect=RuntimeError(secret)))
    monkeypatch.setattr(reporting_cadence, "worker_subprocess_environment", lambda: {"PATH": "/usr/bin"})
    monkeypatch.setattr(reporting_cadence, "logger", logger)

    result = reporting_cadence.trigger_auto_generation(conn, "cadence-1")

    assert result == {
        "status": "error",
        "message": "report generation failed (RuntimeError)",
    }
    assert secret not in repr(result)
    assert secret not in repr(logger.mock_calls)
    assert "RuntimeError" in repr(logger.mock_calls)
    cursor.close.assert_called_once()
