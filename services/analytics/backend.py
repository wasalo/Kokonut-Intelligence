"""Application construction boundary for catalog analytics."""

from __future__ import annotations

from services.analytics.queries import AnalyticsBackend


def get_analytics_backend() -> AnalyticsBackend:
    """Keep the current PostgreSQL implementation for public metric summaries."""
    from services.core.adapters.postgres_analytics import PostgresAnalytics

    return PostgresAnalytics()
