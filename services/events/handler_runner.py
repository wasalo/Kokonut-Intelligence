"""Run one allowlisted EventBus handler in a filtered child environment."""

from __future__ import annotations

import contextlib
import inspect
import json
import sys
from typing import Any

from services.events.bus import resolve_handler


def execute_request(request: Any) -> dict[str, Any]:
    """Invoke a validated event handler and return a small JSON result."""
    try:
        if not isinstance(request, dict):
            raise ValueError("handler request must be an object")
        required = ("module_path", "function_name", "event_type", "payload")
        if any(name not in request for name in required):
            raise ValueError("handler request is missing required fields")
        module_path = request["module_path"]
        function_name = request["function_name"]
        event_type = request["event_type"]
        payload = request["payload"]
        event_id = request.get("event_id")
        with contextlib.redirect_stdout(sys.stderr):
            handler = resolve_handler(module_path, function_name)
            if "event_id" in inspect.signature(handler).parameters:
                handler(event_type, payload, event_id=event_id)
            else:
                handler(event_type, payload)
        return {"succeeded": True}
    except BaseException as exc:  # The parent needs all handler failures as data.
        return {"succeeded": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        result = execute_request(request)
    except BaseException as exc:  # Keep the process protocol intact on bad input.
        result = {"succeeded": False, "error": f"{type(exc).__name__}: {exc}"}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
