"""Read-only health probe for durable work owned by the Standard workers."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable

from services.common.errors import safe_exception_class

DEFAULT_STALE_SECONDS = 300
MAX_STALE_SECONDS = 2_678_400  # 31 days; protects interval conversion from bad configuration.
WORKER_NAMES = ("scheduler", "events", "notifications")

_PROGRESS_SELECTS = {
    "scheduler": """
        SELECT 'scheduler'::text AS worker, COUNT(*)::bigint AS active,
               COUNT(*) FILTER (
                   WHERE task.lease_expires_at IS NULL
                      OR task.lease_expires_at <= probe.checked_at - probe.stale_after
               )::bigint AS stale
        FROM task_run AS run
        JOIN scheduled_task AS task ON task.id = run.task_id
        CROSS JOIN probe
        WHERE run.status = 'running'
    """,
    "events": """
        SELECT 'events'::text AS worker, COUNT(*)::bigint AS active,
               COUNT(*) FILTER (
                   WHERE event.lease_expires_at IS NULL
                      OR event.lease_expires_at <= probe.checked_at - probe.stale_after
               )::bigint AS stale
        FROM platform_event AS event
        CROSS JOIN probe
        WHERE event.status = 'processing'
    """,
    "notifications": """
        SELECT 'notifications'::text AS worker, COUNT(*)::bigint AS active,
               COUNT(*) FILTER (
                   WHERE item.lease_expires_at IS NULL
                      OR item.lease_expires_at <= probe.checked_at - probe.stale_after
               )::bigint AS stale
        FROM notification_outbox AS item
        CROSS JOIN probe
        WHERE item.status = 'processing'
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
    raw: str | int = (
        os.environ.get("KOKONUT_WORKER_PROGRESS_STALE_SECONDS", str(DEFAULT_STALE_SECONDS))
        if value is None
        else value
    )
    if isinstance(raw, bool):
        raise ValueError("stale threshold must be an integer")
    try:
        seconds = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("stale threshold must be an integer") from exc
    if str(seconds) != str(raw).strip() or not 1 <= seconds <= MAX_STALE_SECONDS:
        raise ValueError(f"stale threshold must be between 1 and {MAX_STALE_SECONDS} seconds")
    return seconds


def inspect_progress(
    connection: Any,
    stale_seconds: int,
    enabled_workers: tuple[str, ...] = WORKER_NAMES,
) -> dict[str, Any]:
    """Return aggregate worker state without exposing queued payloads or IDs."""
    threshold = stale_threshold_seconds(stale_seconds)
    if not enabled_workers or any(worker not in WORKER_NAMES for worker in enabled_workers):
        raise ValueError("at least one known worker must be enabled")
    cursor = connection.cursor()
    try:
        cursor.execute(_progress_sql(enabled_workers), (threshold,))
        rows = cursor.fetchall()
    finally:
        cursor.close()

    counts: dict[str, dict[str, int]] = {}
    for worker, active, stale in rows:
        if worker not in WORKER_NAMES or worker in counts:
            raise ValueError("database returned an invalid worker progress result")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (active, stale)
        ):
            raise ValueError("database returned invalid worker progress counts")
        if stale > active:
            raise ValueError("database returned inconsistent worker progress counts")
        counts[worker] = {"active": active, "stale": stale}
    if set(counts) != set(enabled_workers):
        raise ValueError("database returned an incomplete worker progress result")

    active_total = sum(item["active"] for item in counts.values())
    stale_total = sum(item["stale"] for item in counts.values())
    return {
        "status": "unhealthy" if stale_total else "healthy",
        "state": "stale" if stale_total else "active" if active_total else "idle",
        "stale_after_seconds": threshold,
        "workers": counts,
    }


def check_progress(
    *,
    stale_seconds: str | int | None = None,
    connection_factory: Callable[..., Any] | None = None,
    enabled_workers: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run the probe against PostgreSQL and fail closed on database errors."""
    try:
        threshold = stale_threshold_seconds(stale_seconds)
    except ValueError:
        return {
            "status": "unhealthy",
            "state": "invalid_configuration",
            "stale_after_seconds": None,
            "workers": {},
        }

    try:
        selected_workers = _enabled_worker_names() if enabled_workers is None else enabled_workers
        if not selected_workers or any(worker not in WORKER_NAMES for worker in selected_workers):
            return {
                "status": "unhealthy",
                "state": "no_workers_enabled",
                "stale_after_seconds": threshold,
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
            return inspect_progress(connection, threshold, selected_workers)
        finally:
            connection.close()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "state": "database_unavailable",
            "stale_after_seconds": threshold,
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
