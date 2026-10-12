"""Construction boundary for the existing durable PostgreSQL event bus."""

from __future__ import annotations

from services.events.ports import EventStore


def get_event_store(conn=None, lease_seconds: int = 300) -> EventStore:
    from services.events.bus import EventBus

    return EventBus(conn=conn, lease_seconds=lease_seconds)
