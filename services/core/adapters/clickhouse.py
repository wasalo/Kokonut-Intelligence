"""Lazy ClickHouse connection construction for legacy callers."""

from __future__ import annotations

from typing import Any


def create_client(*, host: str, port: int, username: str, password: str, database: str | None = None) -> Any:
    """Preserve the client's default database when no database is specified.

    Missing optional driver returns None, matching the legacy factories.
    Connection errors propagate to the caller's existing error handling.
    """
    from services.core.providers import ProviderSettings

    if not ProviderSettings.from_environment().clickhouse:
        return None
    try:
        import clickhouse_connect
    except ImportError:
        return None
    options = dict(host=host, port=port, username=username, password=password)
    if database is not None:
        options["database"] = database
    return clickhouse_connect.get_client(**options)
