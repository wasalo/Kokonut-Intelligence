"""Read-only implementation of the first governed analytics catalog query."""

from __future__ import annotations

from functools import partial
from typing import Callable

from services.analytics.queries import (
    AnalyticsContext,
    MetricSummary,
    MetricSummaryRequest,
    PublicLocationDirectoryRequest,
    PublicLocationSummary,
    QueryId,
)


class PostgresAnalytics:
    def __init__(self, connection_factory: Callable | None = None):
        self._connection_factory = connection_factory

    def execute(
        self,
        query_id: QueryId,
        request: MetricSummaryRequest | PublicLocationDirectoryRequest,
        context: AnalyticsContext,
    ) -> tuple[MetricSummary | PublicLocationSummary, ...]:
        if not context.public:
            raise PermissionError("Public analytics query requires an explicit public scope")

        if query_id == QueryId.PUBLIC_METRIC_SUMMARY:
            if not isinstance(request, MetricSummaryRequest):
                raise TypeError("Public metric summary requires a metric-summary request")
            if context.location_id is None or context.location_id != request.location_id:
                raise PermissionError("Public metrics query requires a matching public location scope")
        elif query_id == QueryId.PUBLIC_LOCATION_DIRECTORY:
            if not isinstance(request, PublicLocationDirectoryRequest):
                raise TypeError("Public location directory requires a location-directory request")
            if context.location_id != request.location_id:
                raise PermissionError("Public location query requires a matching public scope")
        else:
            raise ValueError("Unknown analytics query")

        factory = self._connection_factory
        if factory is None:
            from services.common.database import get_db

            factory = partial(get_db, connect_timeout=3)
        conn = factory()
        try:
            cur = conn.cursor()
            try:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute("SET LOCAL lock_timeout = '2s'")
                if query_id == QueryId.PUBLIC_METRIC_SUMMARY:
                    metric_request = request
                    assert isinstance(metric_request, MetricSummaryRequest)
                    cur.execute(
                        """
                        SELECT metric_key, display_name, unit, latest_value, computed_at
                        FROM v_public_metric_summary
                        WHERE location_id = %s
                        ORDER BY metric_key
                        """,
                        (metric_request.location_id,),
                    )
                    return tuple(MetricSummary(*row) for row in cur.fetchall())

                location_request = request
                assert isinstance(location_request, PublicLocationDirectoryRequest)
                query = (
                    "SELECT location_id, location_name, country, region, status "
                    "FROM v_public_farm_summary"
                )
                parameters: tuple[str, ...] = ()
                if location_request.location_id is not None:
                    query += " WHERE location_id = %s"
                    parameters = (location_request.location_id,)
                query += " ORDER BY location_name, location_id LIMIT 100"
                cur.execute(query, parameters)
                return tuple(PublicLocationSummary(*row) for row in cur.fetchall())
            finally:
                cur.close()
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()
