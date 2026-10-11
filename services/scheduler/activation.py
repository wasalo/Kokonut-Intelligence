"""Transactional activation of reviewed scheduler definitions."""

from services.scheduler.graph import audit_graph


def enable_schedule(conn, name: str, *, include_dependencies: bool = False) -> list[str]:
    """Enable a task or its prerequisite closure within the caller's transaction.

    The table lock protects the definition snapshot against inserts, updates,
    deletes, and scheduler claims until validation and activation finish.
    """
    conn.execute("SET LOCAL lock_timeout = '5s'")
    conn.execute("LOCK TABLE scheduled_task IN EXCLUSIVE MODE")
    tasks = conn.execute(
        """SELECT id, name, module_path, command_args, cron_expression,
                  depends_on, dependency_mode, is_enabled, next_run_at,
                  retry_at, last_status FROM scheduled_task ORDER BY name"""
    ).all()
    by_id = {str(task["id"]): task for task in tasks}
    target = next((task for task in tasks if task["name"] == name), None)
    if target is None:
        raise ValueError(f"Task not found: {name}")
    if target["is_enabled"] and not include_dependencies:
        return []

    closure = set()
    pending = [str(target["id"])]
    while pending:
        task_id = pending.pop()
        if task_id in closure or task_id not in by_id:
            continue
        closure.add(task_id)
        pending.extend(str(dep) for dep in by_id[task_id].get("depends_on") or [])
    selected = [task for task in tasks if str(task["id"]) in closure]
    if include_dependencies and any(task.get("dependency_mode") == "same_window" for task in selected) and any(
        task.get("dependency_mode") != "same_window" for task in selected
    ):
        raise ValueError("Same-window graph activation requires one dependency mode throughout")
    if target.get("dependency_mode") == "same_window" and len(selected) > 1 and not include_dependencies:
        raise ValueError("Use --enable-graph for atomic same-window prerequisite activation")
    report = audit_graph(selected)
    if report["errors"]:
        details = "; ".join(f"{item['task_id']}: {item['code']}" for item in report["errors"])
        raise ValueError(f"Schedule activation rejected: {details}")
    if any(task.get("dependency_mode") == "same_window" and task["is_enabled"] for task in selected):
        raise ValueError("Disable and reconcile same-window prerequisites before graph activation")

    to_enable = selected if include_dependencies else [target]
    if any(task.get("retry_at") is not None or task.get("last_status") == "running" for task in to_enable):
        raise ValueError("Reconcile running or retrying work before activation")
    enabled = []
    for task in to_enable:
        if task["is_enabled"]:
            continue
        conn.execute(
            "UPDATE scheduled_task SET is_enabled = TRUE, updated_at = NOW() WHERE id = :task_id",
            {"task_id": task["id"]},
        )
        enabled.append(task["name"])
    return enabled
