"""Application construction boundary for catalog analytics."""

from __future__ import annotations

from typing import Callable

from services.analytics.queries import AnalyticsBackend


def get_analytics_backend(*, connection_factory: Callable | None = None) -> AnalyticsBackend:
    """Build the current PostgreSQL adapter for typed public analytics queries."""
    from services.core.adapters.postgres_analytics import PostgresAnalytics

    return PostgresAnalytics(connection_factory=connection_factory)
