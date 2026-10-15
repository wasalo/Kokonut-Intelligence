"""Public durable event delivery contract matching the existing PostgreSQL bus.

Claim/ack/retry remain encapsulated by process_pending so callers cannot bypass
the implementation's lease ownership and per-handler delivery invariants.
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

    def process_pending(self, batch_size: int = 100, worker_id: str = "default") -> dict[str, int]: ...

    def replay_dead_letter(self, event_id: str, actor: str) -> bool: ...

    def dispose_dead_letter(self, event_id: str, disposition: str, actor: str, reason: str) -> bool: ...

    def get_stats(self) -> dict: ...

    def cleanup_old_events(self, actor: str = "cli") -> int: ...

    def close(self) -> None: ...
