"""Focused unit checks for the isolated EventBus handler runner."""

import io
import json

from services.events import handler_runner


def test_runner_invokes_handler_with_event_id_when_supported(monkeypatch):
    calls = []

    def handler(event_type, payload, *, event_id=None):
        calls.append((event_type, payload, event_id))

    monkeypatch.setattr(handler_runner, "resolve_handler", lambda *_: handler)

    result = handler_runner.execute_request(
        {
            "module_path": "example.handlers",
            "function_name": "handle",
            "event_type": "sensor_reading",
            "payload": {"reading": 3},
            "event_id": "event-123",
        }
    )

    assert result == {"succeeded": True}
    assert calls == [("sensor_reading", {"reading": 3}, "event-123")]


def test_runner_invokes_legacy_two_argument_handler(monkeypatch):
    calls = []

    def handler(event_type, payload):
        calls.append((event_type, payload))

    monkeypatch.setattr(handler_runner, "resolve_handler", lambda *_: handler)

    result = handler_runner.execute_request(
        {
            "module_path": "example.handlers",
            "function_name": "handle",
            "event_type": "kind",
            "payload": {},
        }
    )

    assert result == {"succeeded": True}
    assert calls == [("kind", {})]


def test_runner_serializes_handler_failure_without_traceback(monkeypatch):
    def handler(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(handler_runner, "resolve_handler", lambda *_: handler)

    result = handler_runner.execute_request(
        {
            "module_path": "example.handlers",
            "function_name": "handle",
            "event_type": "kind",
            "payload": {},
        }
    )

    assert result == {"succeeded": False, "error": "RuntimeError: synthetic failure"}


def test_runner_main_emits_only_json_result(monkeypatch):
    monkeypatch.setattr(handler_runner.sys, "stdin", io.StringIO('{"module_path":"missing"}'))
    output = io.StringIO()
    monkeypatch.setattr(handler_runner.sys, "stdout", output)

    assert handler_runner.main() == 0
    assert json.loads(output.getvalue()) == {
        "succeeded": False,
        "error": "ValueError: handler request is missing required fields",
    }
