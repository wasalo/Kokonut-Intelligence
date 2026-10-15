"""Feature gate for destructive event-retention operations."""

from __future__ import annotations

import os

EVENT_RETENTION_CLEANUP_ENV = "KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP"


def event_retention_cleanup_enabled() -> bool:
    """Read only the explicit cleanup switch without loading database secrets."""
    return os.getenv(EVENT_RETENTION_CLEANUP_ENV, "false").lower() == "true"


def require_event_retention_cleanup() -> None:
    """Fail closed until an operator explicitly enables approved cleanup."""
    if not event_retention_cleanup_enabled():
        raise RuntimeError(
            "Event retention cleanup is disabled. Set "
            f"{EVENT_RETENTION_CLEANUP_ENV}=true only after retention and "
            "legal-hold policy is approved and event-level hold enforcement "
            "has been implemented."
        )
