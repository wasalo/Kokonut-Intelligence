"""Stored sandbox execution diagnostics are not returned verbatim."""

from datetime import datetime, timezone

from services.sandbox.environment import AnalysisEnvironment


class _Cursor:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, *_args):
        pass

    def fetchall(self):
        now = datetime.now(timezone.utc)
        return [("run-1", "sandbox", "services.analytics.example", "failed", now, None, 12,
                 "synthetic database diagnostic")]


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()

    def cursor(self):
        return self.cursor_instance


def test_list_runs_redacts_persisted_error_message():
    connection = _Connection()
    environment = AnalysisEnvironment(conn=connection)

    result = environment.list_runs()

    assert result[0]["status"] == "failed"
    assert result[0]["duration_ms"] == 12
    assert result[0]["error_message"] == "[details redacted]"
    assert "synthetic database diagnostic" not in str(result)
    assert connection.cursor_instance.closed
