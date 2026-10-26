"""Public location reads through the typed analytics query catalog."""

from __future__ import annotations

from typing import Callable

from services.analytics.backend import get_analytics_backend
from services.analytics.queries import (
    AnalyticsContext,
    PublicLocationDirectoryRequest,
    PublicLocationSummary,
    QueryId,
)


def public_locations(location_id: str | None = None, *, connection_factory: Callable | None = None) -> list[dict]:
    backend = get_analytics_backend(connection_factory=connection_factory)
    request = PublicLocationDirectoryRequest(location_id)
    context = AnalyticsContext(location_id=location_id, public=True)
    rows = backend.execute(QueryId.PUBLIC_LOCATION_DIRECTORY, request, context)
    location_rows = tuple(row for row in rows if isinstance(row, PublicLocationSummary))
    if len(location_rows) != len(rows):
        raise TypeError("Public location query returned an unexpected analytics result")
    return [_public_location(row) for row in location_rows]


def _public_location(row: PublicLocationSummary) -> dict:
    return {
        "id": str(row.location_id),
        "name": row.location_name,
        "country": row.country,
        "region": row.region,
        "status": row.status,
    }
