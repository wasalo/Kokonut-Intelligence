"""Sandbox persistence failures must not log database diagnostics."""

from __future__ import annotations

import logging

import pytest

from services.sandbox.environment import AnalysisEnvironment
from services.sandbox.isolation import IsolationGuard
from services.sandbox.monitor import ResourceMonitor

SECRET_ERROR = "postgresql://sandbox:secret@db.internal/kokonut"
_RAISE = object()


class _DatabaseFailure(Exception):
    pass


class _FailingCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        raise _DatabaseFailure(SECRET_ERROR)


class _FailingConnection:
    def __init__(self):
        self.rollbacks = 0

    def cursor(self):
        return _FailingCursor()

    def rollback(self):
        self.rollbacks += 1


@pytest.mark.parametrize(
    ("factory", "method", "args", "kwargs", "expected", "rolls_back"),
    [
        (AnalysisEnvironment, "create", ("location",), {}, _RAISE, True),
        (AnalysisEnvironment, "destroy", ("environment",), {}, False, True),
        (AnalysisEnvironment, "_complete_run", ("run", "failed", None, "error", 1), {}, None, True),
        (AnalysisEnvironment, "list_environments", (), {}, [], False),
        (AnalysisEnvironment, "list_runs", (), {}, [], False),
        (ResourceMonitor, "record_usage", ("run", {"cpu": 1}), {}, None, True),
        (ResourceMonitor, "get_usage_summary", (), {}, {}, False),
        (IsolationGuard, "get_sandbox_rules", ("environment",), {}, None, False),
    ],
)
def test_sandbox_database_errors_are_redacted(factory, method, args, kwargs, expected, rolls_back, caplog):
    conn = _FailingConnection()
    service = factory(conn=conn)

    with caplog.at_level(logging.WARNING, logger="kokonut.sandbox"):
        if expected is _RAISE:
            with pytest.raises(_DatabaseFailure, match="sandbox:secret"):
                getattr(service, method)(*args, **kwargs)
        else:
            assert getattr(service, method)(*args, **kwargs) == expected

    assert SECRET_ERROR not in caplog.text
    assert "_DatabaseFailure" in caplog.text
    assert "Traceback" not in caplog.text
    assert conn.rollbacks == int(rolls_back)
