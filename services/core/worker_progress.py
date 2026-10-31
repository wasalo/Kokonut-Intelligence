"""Read-only health probe for durable work owned by the Standard workers."""

from __future__ import annotations

import argparse
import json
import os
import stat
import time
from pathlib import Path
from typing import Any, Callable

from services.common.errors import safe_exception_class

DEFAULT_STALE_SECONDS = 300
DEFAULT_BACKLOG_SECONDS = 900
DEFAULT_HEARTBEAT_SECONDS = 60
HEARTBEAT_FILE_ENV = "KOKONUT_WORKER_PROGRESS_HEARTBEAT_FILE"
DEFAULT_HEARTBEAT_FILE = "/var/lib/kokonut/worker-progress/supervisor.json"
MAX_STALE_SECONDS = 2_678_400  # 31 days; protects interval conversion from bad configuration.
WORKER_NAMES = ("scheduler", "events", "notifications")

_PROGRESS_SELECTS = {
    "scheduler": """
        SELECT 'scheduler'::text AS worker,
               active.active::bigint,
               active.stale::bigint,
               backlog.queued::bigint,
               backlog.oldest_due_seconds::bigint
        FROM probe
        CROSS JOIN LATERAL (
            SELECT COUNT(*) AS active,
                   COUNT(*) FILTER (
                       WHERE task.lease_expires_at IS NULL
                          OR task.lease_expires_at <= probe.checked_at - probe.stale_after
                   ) AS stale
            FROM task_run AS run
            JOIN scheduled_task AS task ON task.id = run.task_id
            WHERE run.status = 'running'
        ) AS active
        CROSS JOIN LATERAL (
            SELECT COUNT(*) AS queued,
                   MAX(FLOOR(EXTRACT(EPOCH FROM probe.checked_at - due.due_at)))
                       AS oldest_due_seconds
            FROM (
                SELECT task.id,
                       CASE WHEN task.retry_at IS NOT NULL THEN task.retry_at
                            ELSE COALESCE(task.next_run_at, probe.checked_at) END AS due_at
                FROM scheduled_task AS task
                WHERE task.is_enabled = TRUE
                  AND (task.lease_expires_at IS NULL
                       OR task.lease_expires_at <= probe.checked_at)
                  AND (task.retry_at <= probe.checked_at OR
                       (task.retry_at IS NULL AND
                        (task.next_run_at IS NULL OR task.next_run_at <= probe.checked_at)))
                  AND (task.dependency_mode <> 'same_window' OR
                       CASE WHEN task.retry_at IS NOT NULL THEN task.run_window_at
                            ELSE task.next_run_at END IS NOT NULL)
                  AND NOT EXISTS (
                      SELECT 1
                      FROM unnest(task.depends_on) AS dep(dependency_id)
                      LEFT JOIN scheduled_task AS dependency
                        ON dependency.id = dep.dependency_id
                      WHERE (task.dependency_mode = 'last_completed'
                             AND dependency.last_status IS DISTINCT FROM 'completed')
                         OR (task.dependency_mode = 'same_window' AND NOT EXISTS (
                             SELECT 1 FROM task_run AS prerequisite
                             WHERE prerequisite.task_id = dep.dependency_id
                               AND prerequisite.status = 'completed'
                               AND prerequisite.scheduled_for =
                                   CASE WHEN task.retry_at IS NOT NULL
                                        THEN task.run_window_at ELSE task.next_run_at END
                         ))
                  )
                  AND (task.allow_overlap OR NOT EXISTS (
                      SELECT 1 FROM task_run AS running
                      WHERE running.task_id = task.id AND running.status = 'running'
                  ))
            ) AS due
            WHERE due.due_at <= probe.checked_at
        ) AS backlog
    """,
    "events": """
        SELECT 'events'::text AS worker,
               COUNT(*) FILTER (WHERE event.status = 'processing')::bigint AS active,
               COUNT(*) FILTER (
                   WHERE event.status = 'processing'
                     AND (event.lease_expires_at IS NULL
                          OR event.lease_expires_at <= probe.checked_at - probe.stale_after)
               )::bigint AS stale,
               COUNT(*) FILTER (WHERE event.status = 'pending')::bigint AS queued,
               CASE WHEN COUNT(*) FILTER (WHERE event.status = 'pending') = 0
                    THEN NULL::bigint
                    ELSE GREATEST(0, FLOOR(EXTRACT(EPOCH FROM
                        MIN(probe.checked_at) - MIN(event.created_at)
                            FILTER (WHERE event.status = 'pending')
                    )))::bigint
               END AS oldest_due_seconds
        FROM platform_event AS event
        CROSS JOIN probe
    """,
    "notifications": """
        SELECT 'notifications'::text AS worker,
               COUNT(*) FILTER (WHERE item.status = 'processing')::bigint AS active,
               COUNT(*) FILTER (
                   WHERE item.status = 'processing'
                     AND (item.lease_expires_at IS NULL
                          OR item.lease_expires_at <= probe.checked_at - probe.stale_after)
               )::bigint AS stale,
               COUNT(*) FILTER (
                   WHERE item.status IN ('pending', 'retryable')
                     AND item.available_at <= probe.checked_at
               )::bigint AS queued,
               FLOOR(EXTRACT(EPOCH FROM
                   MIN(probe.checked_at) - MIN(item.available_at)
                       FILTER (WHERE item.status IN ('pending', 'retryable')
                               AND item.available_at <= probe.checked_at)
               ))::bigint AS oldest_due_seconds
        FROM notification_outbox AS item
        CROSS JOIN probe
    """,
}


def _progress_sql(enabled_workers: tuple[str, ...]) -> str:
    """Build a query only for feature-selected queues, from fixed SQL fragments."""
    query = """
        WITH probe AS (
            SELECT statement_timestamp() AS checked_at,
                   make_interval(secs => %s::double precision) AS stale_after
        )
    """
    query += " UNION ALL ".join(_PROGRESS_SELECTS[worker] for worker in enabled_workers)
    return query + " ORDER BY worker"


def _enabled_worker_names() -> tuple[str, ...]:
    from services.core.features import is_enabled

    feature_by_worker = {
        "scheduler": "scheduler",
        "events": "event_bus",
        "notifications": "notification_delivery",
    }
    return tuple(worker for worker in WORKER_NAMES if is_enabled(feature_by_worker[worker]))


def stale_threshold_seconds(value: str | int | None = None) -> int:
    """Return a bounded stale-work grace period from config or the default."""
    return _threshold_seconds(
        value,
        environment_name="KOKONUT_WORKER_PROGRESS_STALE_SECONDS",
        default=DEFAULT_STALE_SECONDS,
    )


def backlog_threshold_seconds(value: str | int | None = None) -> int:
    """Return the bounded maximum age of due, unclaimed work."""
    return _threshold_seconds(
        value,
        environment_name="KOKONUT_WORKER_PROGRESS_BACKLOG_SECONDS",
        default=DEFAULT_BACKLOG_SECONDS,
    )


def heartbeat_threshold_seconds(value: str | int | None = None) -> int:
    """Return the bounded age after which a supervisor heartbeat is stale."""
    return _threshold_seconds(
        value,
        environment_name="KOKONUT_WORKER_PROGRESS_HEARTBEAT_SECONDS",
        default=DEFAULT_HEARTBEAT_SECONDS,
    )


def _threshold_seconds(
    value: str | int | None,
    *,
    environment_name: str,
    default: int,
) -> int:
    raw: str | int = os.environ.get(environment_name, str(default)) if value is None else value
    if isinstance(raw, bool):
        raise ValueError("worker progress threshold must be an integer")
    try:
        seconds = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("worker progress threshold must be an integer") from exc
    if str(seconds) != str(raw).strip() or not 1 <= seconds <= MAX_STALE_SECONDS:
        raise ValueError(f"worker progress threshold must be between 1 and {MAX_STALE_SECONDS} seconds")
    return seconds


def _heartbeat_file_path() -> Path:
    return Path(os.environ.get(HEARTBEAT_FILE_ENV, DEFAULT_HEARTBEAT_FILE))


def _supervisor_liveness(
    *,
    path: str | Path | None = None,
    stale_seconds: int | None = None,
    expected_workers: tuple[str, ...] = WORKER_NAMES,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    process_probe: Callable[[int], None] | None = None,
) -> dict[str, int | bool | None]:
    """Read private heartbeat state without returning process IDs."""
    threshold = heartbeat_threshold_seconds(stale_seconds)
    heartbeat_path = _heartbeat_file_path() if path is None else Path(path)
    try:
        parent_stat = heartbeat_path.parent.lstat()
        file_stat = heartbeat_path.lstat()
        if (
            not stat.S_ISDIR(parent_stat.st_mode)
            or parent_stat.st_uid != os.getuid()
            or parent_stat.st_mode & 0o077
            or not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != os.getuid()
            or file_stat.st_mode & 0o077
            or file_stat.st_size > 1024
        ):
            return {"alive": False, "age_seconds": None, "children_alive": False}
        payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {"alive": False, "age_seconds": None, "children_alive": False}

    if not isinstance(payload, dict) or set(payload) != {
        "children", "generation", "monotonic_ns", "pid"
    }:
        return {"alive": False, "age_seconds": None, "children_alive": False}
    generation = payload["generation"]
    pid = payload["pid"]
    heartbeat_ns = payload["monotonic_ns"]
    children = payload["children"]
    if (
        not isinstance(generation, str)
        or len(generation) != 32
        or any(character not in "0123456789abcdef" for character in generation)
        or isinstance(pid, bool)
        or not isinstance(pid, int)
        or not 1 <= pid <= 2_147_483_647
        or isinstance(heartbeat_ns, bool)
        or not isinstance(heartbeat_ns, int)
        or heartbeat_ns <= 0
        or not isinstance(children, dict)
        or any(worker not in WORKER_NAMES for worker in children)
        or set(children) != set(expected_workers)
        or any(
            isinstance(child_pid, bool)
            or not isinstance(child_pid, int)
            or not 1 <= child_pid <= 2_147_483_647
            or child_pid == pid
            for child_pid in children.values()
        )
        or len(set(children.values())) != len(children)
    ):
        return {"alive": False, "age_seconds": None, "children_alive": False}

    age_ns = monotonic_ns() - heartbeat_ns
    if age_ns < 0:
        return {"alive": False, "age_seconds": None, "children_alive": False}
    age_seconds = age_ns // 1_000_000_000
    probe = os.kill if process_probe is None else process_probe
    try:
        probe(pid, 0) if process_probe is None else probe(pid)
    except (ProcessLookupError, PermissionError, OSError):
        return {"alive": False, "age_seconds": age_seconds, "children_alive": False}
    children_alive = True
    try:
        for child_pid in children.values():
            probe(child_pid, 0) if process_probe is None else probe(child_pid)
    except (ProcessLookupError, PermissionError, OSError):
        children_alive = False
    return {
        "alive": age_seconds <= threshold,
        "age_seconds": age_seconds,
        "children_alive": children_alive,
    }


def inspect_progress(
    connection: Any,
    stale_seconds: int,
    enabled_workers: tuple[str, ...] = WORKER_NAMES,
    backlog_seconds: int | None = None,
) -> dict[str, Any]:
    """Return aggregate worker state without exposing queued payloads or IDs."""
    threshold = stale_threshold_seconds(stale_seconds)
    backlog_threshold = backlog_threshold_seconds(backlog_seconds)
    if not enabled_workers or any(worker not in WORKER_NAMES for worker in enabled_workers):
        raise ValueError("at least one known worker must be enabled")
    cursor = connection.cursor()
    try:
        cursor.execute(_progress_sql(enabled_workers), (threshold,))
        rows = cursor.fetchall()
    finally:
        cursor.close()

    counts: dict[str, dict[str, int]] = {}
    for worker, active, stale, queued, oldest_due_seconds in rows:
        if worker not in WORKER_NAMES or worker in counts:
            raise ValueError("database returned an invalid worker progress result")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (active, stale, queued)
        ):
            raise ValueError("database returned invalid worker progress counts")
        if stale > active:
            raise ValueError("database returned inconsistent worker progress counts")
        if oldest_due_seconds is not None and (
            isinstance(oldest_due_seconds, bool)
            or not isinstance(oldest_due_seconds, int)
            or oldest_due_seconds < 0
        ):
            raise ValueError("database returned invalid worker backlog age")
        if (queued == 0) != (oldest_due_seconds is None):
            raise ValueError("database returned inconsistent worker backlog state")
        counts[worker] = {
            "active": active,
            "stale": stale,
            "queued": queued,
            "oldest_due_seconds": oldest_due_seconds,
        }
    if set(counts) != set(enabled_workers):
        raise ValueError("database returned an incomplete worker progress result")

    active_total = sum(item["active"] for item in counts.values())
    stale_total = sum(item["stale"] for item in counts.values())
    backlog_workers = tuple(
        worker
        for worker, item in counts.items()
        if item["oldest_due_seconds"] is not None
        and item["oldest_due_seconds"] >= backlog_threshold
    )
    unhealthy = bool(stale_total or backlog_workers)
    return {
        "status": "unhealthy" if unhealthy else "healthy",
        "state": "stale" if stale_total else "backlog" if backlog_workers else "active" if active_total else "idle",
        "stale_after_seconds": threshold,
        "backlog_after_seconds": backlog_threshold,
        "backlog_workers": list(backlog_workers),
        "workers": counts,
    }


def check_progress(
    *,
    stale_seconds: str | int | None = None,
    backlog_seconds: str | int | None = None,
    connection_factory: Callable[..., Any] | None = None,
    enabled_workers: tuple[str, ...] | None = None,
    heartbeat_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the probe against PostgreSQL and fail closed on database errors."""
    try:
        threshold = stale_threshold_seconds(stale_seconds)
        backlog_threshold = backlog_threshold_seconds(backlog_seconds)
        heartbeat_threshold = heartbeat_threshold_seconds()
    except ValueError:
        return {
            "status": "unhealthy",
            "state": "invalid_configuration",
            "stale_after_seconds": None,
            "backlog_after_seconds": None,
            "backlog_workers": [],
            "supervisor": {
                "alive": False,
                "age_seconds": None,
                "children_alive": False,
            },
            "workers": {},
        }

    supervisor: dict[str, int | bool | None] = {
        "alive": False,
        "age_seconds": None,
        "children_alive": False,
    }
    try:
        selected_workers = _enabled_worker_names() if enabled_workers is None else enabled_workers
        if not selected_workers or any(worker not in WORKER_NAMES for worker in selected_workers):
            return {
                "status": "unhealthy",
                "state": "no_workers_enabled",
                "stale_after_seconds": threshold,
                "backlog_after_seconds": backlog_threshold,
                "backlog_workers": [],
                "supervisor": {
                    "alive": False,
                    "age_seconds": None,
                    "children_alive": False,
                },
                "workers": {},
            }
        supervisor = _supervisor_liveness(
            path=heartbeat_path,
            stale_seconds=heartbeat_threshold,
            expected_workers=selected_workers,
        )
        if not supervisor["alive"]:
            return {
                "status": "unhealthy",
                "state": "supervisor_unresponsive",
                "stale_after_seconds": threshold,
                "backlog_after_seconds": backlog_threshold,
                "backlog_workers": [],
                "supervisor": supervisor,
                "workers": {},
            }
        if not supervisor["children_alive"]:
            return {
                "status": "unhealthy",
                "state": "worker_child_unresponsive",
                "stale_after_seconds": threshold,
                "backlog_after_seconds": backlog_threshold,
                "backlog_workers": [],
                "supervisor": supervisor,
                "workers": {},
            }
        if connection_factory is None:
            from services.common.database import get_db

            connection_factory = get_db
        connection = connection_factory(connect_timeout=3)
        try:
            # The worker's health probe has no write path, even if its runtime
            # login otherwise has broader legacy privileges.
            connection.set_session(readonly=True)
            result = inspect_progress(
                connection,
                threshold,
                selected_workers,
                backlog_seconds=backlog_threshold,
            )
            result["supervisor"] = supervisor
            return result
        finally:
            connection.close()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "state": "database_unavailable",
            "stale_after_seconds": threshold,
            "backlog_after_seconds": backlog_threshold,
            "backlog_workers": [],
            "supervisor": supervisor,
            "workers": {},
            "error": safe_exception_class(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check durable Standard worker progress")
    parser.add_argument("--check", action="store_true", help="run the read-only progress probe")
    args = parser.parse_args()
    if not args.check:
        parser.error("--check is required")
    result = check_progress()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
