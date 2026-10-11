"""Read-only implementation of the first governed analytics catalog query."""

from __future__ import annotations

from functools import partial
from typing import Callable

from services.analytics.queries import AnalyticsContext, MetricSummary, MetricSummaryRequest, QueryId


class PostgresAnalytics:
    def __init__(self, connection_factory: Callable | None = None):
        self._connection_factory = connection_factory

    def execute(
        self, query_id: QueryId, request: MetricSummaryRequest, context: AnalyticsContext
    ) -> tuple[MetricSummary, ...]:
        if query_id != QueryId.PUBLIC_METRIC_SUMMARY:
            raise ValueError("Unknown analytics query")
        if context.location_id != request.location_id or not context.public:
            raise PermissionError("Public metrics query requires a matching public location scope")
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
                cur.execute(
                    """
                    SELECT metric_key, display_name, unit, latest_value, computed_at
                    FROM v_public_metric_summary
                    WHERE location_id = %s
                    ORDER BY metric_key
                    """,
                    (request.location_id,),
                )
                return tuple(MetricSummary(*row) for row in cur.fetchall())
            finally:
                cur.close()
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()
