"""Focused unit checks for the isolated EventBus handler runner."""

import io
import json
import logging

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


def test_runner_keeps_configured_service_logs_off_json_protocol(monkeypatch):
    protocol_output = io.StringIO()
    log_handler = logging.StreamHandler(protocol_output)
    log_handler.setLevel(logging.INFO)
    logger = logging.getLogger("kokonut")
    logger.addHandler(log_handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)

    def handler(*_args, **_kwargs):
        logger.info("synthetic committed handler effect")

    monkeypatch.setattr(handler_runner.sys, "stdout", protocol_output)
    monkeypatch.setattr(handler_runner, "resolve_handler", lambda *_: handler)
    try:
        result = handler_runner.execute_request(
            {
                "module_path": "example.handlers",
                "function_name": "handle",
                "event_type": "data_stale",
                "payload": {},
                "event_id": "event-123",
            }
        )
    finally:
        logger.removeHandler(log_handler)
        logger.setLevel(previous_level)

    assert result == {"succeeded": True}
    assert protocol_output.getvalue() == ""
    assert log_handler.stream is protocol_output


def test_runner_main_emits_only_json_result(monkeypatch):
    monkeypatch.setattr(handler_runner.sys, "stdin", io.StringIO('{"module_path":"missing"}'))
    output = io.StringIO()
    monkeypatch.setattr(handler_runner.sys, "stdout", output)

    assert handler_runner.main() == 0
    assert json.loads(output.getvalue()) == {
        "succeeded": False,
        "error": "ValueError: handler request is missing required fields",
    }
