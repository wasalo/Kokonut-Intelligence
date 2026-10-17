"""Run one allowlisted EventBus handler in a filtered child environment."""

from __future__ import annotations

import contextlib
import inspect
import json
import logging
import sys
from typing import Any

from services.events.bus import resolve_handler


def _safe_exception_class(exc: BaseException) -> str:
    name = type(exc).__name__
    if name.isascii() and name.isidentifier() and len(name) <= 64:
        return name
    return "Exception"


def _redirect_kokonut_logs_from_protocol_stdout(protocol_stdout):
    """Keep configured service log handlers from writing into the JSON protocol."""
    root = logging.getLogger("kokonut")
    reassigned = []
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is protocol_stdout:
            handler.setStream(sys.stderr)
            reassigned.append(handler)
    return reassigned


def execute_request(request: Any) -> dict[str, Any]:
    """Invoke a validated event handler and return a small JSON result."""
    if not isinstance(request, dict):
        return {"succeeded": False, "error": "handler request must be an object"}
    required = ("module_path", "function_name", "event_type", "payload")
    if any(name not in request for name in required):
        return {
            "succeeded": False,
            "error": "handler request is missing required fields",
        }

    try:
        module_path = request["module_path"]
        function_name = request["function_name"]
        event_type = request["event_type"]
        payload = request["payload"]
        event_id = request.get("event_id")
        protocol_stdout = sys.stdout
        reassigned = []
        try:
            with contextlib.redirect_stdout(sys.stderr):
                reassigned = _redirect_kokonut_logs_from_protocol_stdout(protocol_stdout)
                handler = resolve_handler(module_path, function_name)
                if "event_id" in inspect.signature(handler).parameters:
                    handler(event_type, payload, event_id=event_id)
                else:
                    handler(event_type, payload)
        finally:
            for log_handler in reassigned:
                if log_handler.stream is sys.stderr:
                    log_handler.setStream(protocol_stdout)
        return {"succeeded": True}
    except BaseException as exc:  # The parent needs all handler failures as data.
        return {
            "succeeded": False,
            "error": "handler execution failed",
            "error_class": _safe_exception_class(exc),
        }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        result = execute_request(request)
    except BaseException as exc:  # Keep the process protocol intact on bad input.
        result = {
            "succeeded": False,
            "error": "invalid handler request",
            "error_class": _safe_exception_class(exc),
        }
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
