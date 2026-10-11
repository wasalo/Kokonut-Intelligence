"""Contract for persisted computation results and event-driven invalidation.

This cache retains computation metadata; it is distinct from an ephemeral
key/value cache used to accelerate HTTP responses.
"""

from __future__ import annotations

from typing import Protocol


class ComputationCacheBackend(Protocol):
    def get(
        self, computation_type: str, location_id: str | None = None, parameters: dict | None = None
    ) -> dict | None: ...

    def set(
        self,
        computation_type: str,
        result: dict,
        location_id: str | None = None,
        parameters: dict | None = None,
        ttl_seconds: int | None = None,
        computed_by: str | None = None,
        metadata: dict | None = None,
    ) -> str: ...

    def invalidate(
        self, computation_type: str | None = None, location_id: str | None = None, reason: str = "manual"
    ) -> int: ...

    def cleanup_expired(self) -> int: ...

    def stats(self) -> dict: ...
