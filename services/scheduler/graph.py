"""Read-only preactivation audit of scheduler definitions."""

from collections import deque
from datetime import datetime, timezone

from services.scheduler.parser import parse_cron
from services.security.execution_allowlist import validate_scheduled_module
from services.security.scheduled_command_contracts import validate_scheduled_command


def audit_graph(tasks: list[dict]) -> dict:
    """Report configuration issues without executing or modifying tasks.

    Window alignment checks apply to disabled same-window graphs only. Live
    progress must be reconciled with task_run history before changing schedules.
    """
    errors = []
    warnings = []
    by_id = {}

    def error(task_id, code, message):
        errors.append({"task_id": task_id, "code": code, "message": message})

    for task in tasks:
        task_id = str(task["id"])
        if task_id in by_id:
            error(task_id, "duplicate_id", "Task identifier occurs more than once")
        by_id[task_id] = task

    dependencies = {}
    for task_id, task in by_id.items():
        deps = {str(dep) for dep in task.get("depends_on") or []}
        dependencies[task_id] = deps
        for dep in sorted(deps - by_id.keys()):
            error(task_id, "missing_dependency", f"Missing prerequisite {dep}")
        if task_id in deps:
            error(task_id, "self_dependency", "Task depends on itself")
        module_allowed = True
        try:
            validate_scheduled_module(task["module_path"])
        except ValueError:
            module_allowed = False
            error(task_id, "module_policy", "Module is outside the scheduler allowlist")
        arguments = task.get("command_args", [])
        if not isinstance(arguments, list) or any(not isinstance(arg, str) for arg in arguments):
            error(task_id, "invalid_arguments", "Command arguments must be an array of strings")
        elif module_allowed:
            try:
                validate_scheduled_command(task.get("module_path"), arguments)
            except ValueError:
                error(task_id, "command_contract", "Command arguments are not valid for the scheduled operation")
        parsed = None
        try:
            parsed = parse_cron(task["cron_expression"])
            if not all(parsed.values()):
                raise ValueError("Empty cron component")
        except (ValueError, TypeError, AttributeError):
            error(task_id, "invalid_cron", "Cron expression cannot be parsed into nonempty fields")

        mode = task.get("dependency_mode", "last_completed")
        if mode not in {"last_completed", "same_window"}:
            error(task_id, "invalid_dependency_mode", "Unknown dependency mode")
        if mode == "last_completed" and deps:
            warnings.append(
                {
                    "task_id": task_id,
                    "code": "legacy_dependencies",
                    "message": "An earlier completion can satisfy dependencies",
                }
            )
        if mode != "same_window":
            continue
        if task.get("is_enabled"):
            warnings.append(
                {
                    "task_id": task_id,
                    "code": "live_graph",
                    "message": "Disable and reconcile run history before preactivation alignment review",
                }
            )
            continue
        window = task.get("next_run_at")
        if not isinstance(window, datetime) or window.tzinfo is None or window.utcoffset() is None:
            error(task_id, "missing_window", "An explicit timezone-aware initial next_run_at is required")
        elif parsed and all(parsed.values()):
            utc_window = window.astimezone(timezone.utc)
            components = {
                "minute": utc_window.minute,
                "hour": utc_window.hour,
                "day": utc_window.day,
                "month": utc_window.month,
                "weekday": (utc_window.weekday() + 1) % 7,
            }
            if (
                utc_window.second
                or utc_window.microsecond
                or any(value not in parsed[field] for field, value in components.items())
            ):
                error(task_id, "off_cadence_window", "Initial UTC window must match the cron cadence exactly")
        if task.get("retry_at") is not None or task.get("last_status") == "running":
            error(task_id, "in_flight", "Reconcile running or retrying work before preactivation review")
        for dep in sorted(deps & by_id.keys()):
            prerequisite = by_id[dep]
            if prerequisite.get("is_enabled"):
                error(task_id, "live_prerequisite", f"Prerequisite {dep} is still enabled")
            if prerequisite.get("dependency_mode", "last_completed") != "same_window":
                error(task_id, "mixed_dependency_mode", f"Prerequisite {dep} must use same_window")
            if prerequisite.get("cron_expression") != task.get("cron_expression"):
                error(task_id, "cadence_mismatch", f"Prerequisite {dep} has a different cadence")
            if window is not None and prerequisite.get("next_run_at") != window:
                error(task_id, "window_mismatch", f"Prerequisite {dep} has a different initial window")

    # Kahn's algorithm avoids recursion limits on large or cyclic definitions.
    pending = {task_id: len(deps & by_id.keys()) for task_id, deps in dependencies.items()}
    children = {task_id: [] for task_id in by_id}
    for task_id, deps in dependencies.items():
        for dep in deps & by_id.keys():
            children[dep].append(task_id)
    ready = deque(sorted(task_id for task_id, count in pending.items() if count == 0))
    order = []
    while ready:
        task_id = ready.popleft()
        order.append(task_id)
        for child in sorted(children[task_id]):
            pending[child] -= 1
            if pending[child] == 0:
                ready.append(child)
    for task_id in sorted(by_id.keys() - set(order)):
        error(task_id, "cyclic_or_blocked", "Task is in a dependency cycle or depends on one")
    return {"valid": not errors, "tasks": len(tasks), "errors": errors, "warnings": warnings, "dependency_order": order}
