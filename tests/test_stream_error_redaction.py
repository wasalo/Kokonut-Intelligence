"""Stream failures avoid logging sensor payloads or database diagnostics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from services.stream.alerts import StreamAlertEvaluator
from services.stream.buffer import StreamBuffer
from services.stream.processor import StreamProcessor
from services.stream.windows import WindowAggregator

SECRET_ERROR = "sensor payload rejected at postgresql://operator:secret@db.internal/kokonut"
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
        self.commits = 0

    def cursor(self):
        return _FailingCursor()

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


_READING = {"sensor_device_id": "device", "metric": "soil_moisture", "value": 21.5}
_TS = datetime.now(timezone.utc)


@pytest.mark.parametrize(
    ("factory", "method", "args", "expected", "rolls_back"),
    [
        (StreamProcessor, "ingest", ("device", "soil_moisture", 21.5), _RAISE, True),
        (StreamProcessor, "ingest_batch", ([_READING],), 0, False),
        (StreamProcessor, "process_buffer", (), {"processed": 0, "aggregated": 0, "errors": 0}, True),
        (StreamProcessor, "get_recent", ("device", "soil_moisture"), [], False),
        (StreamProcessor, "stats", (), {}, False),
        (StreamBuffer, "cleanup", (), 0, True),
        (StreamBuffer, "pending_count", (), 0, False),
        (StreamBuffer, "oldest_pending", (), None, False),
        (StreamBuffer, "pressure_ratio", (), 0.0, False),
        (WindowAggregator, "_update_window", ("device", "soil_moisture", "5min", 21.5, _TS), None, True),
        (WindowAggregator, "get_windows", ("device", "soil_moisture", "5min"), [], False),
        (WindowAggregator, "detect_spikes", ("device", "soil_moisture"), None, False),
        (StreamAlertEvaluator, "_create_alert", ("device", "threshold", "warning", "soil_moisture", 21.5, 20.0, "test"), _RAISE, True),
        (StreamAlertEvaluator, "acknowledge", ("alert-id", "operator"), False, True),
        (StreamAlertEvaluator, "list_unacknowledged", (), [], False),
    ],
)
def test_database_exception_text_is_not_logged(factory, method, args, expected, rolls_back, caplog):
    conn = _FailingConnection()
    service = factory(conn=conn)

    with caplog.at_level(logging.WARNING, logger="kokonut.stream"):
        if expected is _RAISE:
            with pytest.raises(_DatabaseFailure, match="operator:secret"):
                getattr(service, method)(*args)
        else:
            assert getattr(service, method)(*args) == expected

    assert SECRET_ERROR not in caplog.text
    assert "_DatabaseFailure" in caplog.text
    assert "Traceback" not in caplog.text
    assert conn.rollbacks == int(rolls_back)
