"""Worker status CLIs must not print historic raw persisted errors."""

import sys
import types
from types import SimpleNamespace

import pytest

from services.events import cli as events_cli
from services.ingestion import clickhouse_outbox, mqtt_delivery_cli
from services.scheduler import cli as scheduler_cli

DIAGNOSTIC = "synthetic provider diagnostic marker"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, *_args):
        pass

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.cursor_instance = _Cursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class _MappingResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _ContextConnection:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, *_args):
        return _MappingResult(self.rows)


class _OutboxCursor:
    description = [(name,) for name in (
        "id", "event_key", "source_table", "source_id", "target_table",
        "attempt_count", "last_error", "created_at", "updated_at",
    )]

    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def execute(self, *_args):
        pass

    def fetchall(self):
        return [(
            "outbox-1", "sensor:1", "sensor_reading", "reading-1", "sensor_readings",
            3, DIAGNOSTIC, "created", "updated",
        )]


class _OutboxConnection:
    def __init__(self):
        self.cursor_instance = _OutboxCursor()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def cursor(self):
        return self.cursor_instance


@pytest.mark.parametrize(
    ("command", "rows", "args"),
    [
        (
            events_cli.cmd_list_dead_letter,
            [("event-1", "farm.updated", 3, DIAGNOSTIC, "2026-10-17", "open")],
            SimpleNamespace(limit=5),
        ),
        (
            scheduler_cli.cmd_list_runs,
            [("run-1", "weather", "failed", "start", None, 100, DIAGNOSTIC)],
            SimpleNamespace(limit=5),
        ),
    ],
)
def test_worker_status_output_redacts_persisted_errors(
    monkeypatch, capsys, command, rows, args
):
    connection = _Connection(rows)
    database = types.ModuleType("services.common.database")
    database.get_db = lambda: connection
    monkeypatch.setitem(sys.modules, "services.common.database", database)

    result = command(args)

    output = capsys.readouterr().out
    assert result == 0
    assert DIAGNOSTIC not in output
    assert "Error: [details redacted]" in output
    assert connection.cursor_instance.closed
    assert connection.closed


def test_mqtt_delivery_list_redacts_persisted_error(monkeypatch, capsys):
    delivery = {
        "id": "delivery-1",
        "status": "dead_letter",
        "attempt_count": 3,
        "last_error": DIAGNOSTIC,
        "created_at": "created",
        "updated_at": "updated",
    }
    connection = _ContextConnection([delivery])
    monkeypatch.setattr(mqtt_delivery_cli, "get_connection", lambda: connection)

    mqtt_delivery_cli.command(
        SimpleNamespace(
            list=True,
            limit=5,
            actor=None,
            reason=None,
            replay=None,
            dispose=None,
        )
    )

    output = capsys.readouterr().out
    assert DIAGNOSTIC not in output
    assert '"id": "delivery-1"' in output
    assert '"status": "dead_letter"' in output
    assert '"attempt_count": 3' in output
    assert '"last_error": "[details redacted]"' in output
    assert connection.closed


def test_clickhouse_outbox_list_redacts_persisted_error(monkeypatch, capsys):
    connection = _OutboxConnection()
    monkeypatch.setattr(clickhouse_outbox, "get_connection", lambda: connection)
    monkeypatch.setattr(sys, "argv", ["clickhouse_outbox", "--list-dead-letter"])

    clickhouse_outbox.main()

    output = capsys.readouterr().out
    assert DIAGNOSTIC not in output
    assert '"id": "outbox-1"' in output
    assert '"event_key": "sensor:1"' in output
    assert '"attempt_count": 3' in output
    assert '"last_error": "[details redacted]"' in output
    assert connection.cursor_instance.closed
    assert connection.closed
