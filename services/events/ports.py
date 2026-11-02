"""Public event publication and administration contracts.

Event dispatch is a separate isolated worker capability; the shared event store
does not expose claim/ack/retry operations under the application identity.
"""

from __future__ import annotations

from typing import Any, Protocol


class EventStore(Protocol):
    def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        source_table=None,
        source_id=None,
        priority="normal",
        max_retries=3,
        metadata=None,
    ) -> str: ...

    def replay_dead_letter(self, event_id: str, actor: str) -> bool: ...

    def dispose_dead_letter(self, event_id: str, disposition: str, actor: str, reason: str) -> bool: ...

    def get_stats(self) -> dict: ...

    def cleanup_old_events(self, actor: str = "cli") -> int: ...

    def close(self) -> None: ...


class EventDispatcher(Protocol):
    """Bounded event processing interface implemented by isolated workers."""

    def process_pending(self, batch_size: int = 100, worker_id: str = "default") -> dict[str, int]: ...
