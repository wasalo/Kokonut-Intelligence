"""Construction boundary for the canonical PostgreSQL scheduler engine."""

from __future__ import annotations

from services.scheduler.ports import SchedulerBackend


def get_scheduler(conn, worker_id: str | None = None) -> SchedulerBackend:
    """Use the caller's connection; the caller retains transaction/close ownership."""
    from services.scheduler.engine import SchedulerEngine

    return SchedulerEngine(conn, worker_id=worker_id)
