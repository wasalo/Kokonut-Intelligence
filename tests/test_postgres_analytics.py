"""The PostgreSQL adapter implements only typed, bounded public queries."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from services.analytics.queries import (
    AnalyticsContext,
    MetricSummary,
    MetricSummaryRequest,
    PublicLocationDirectoryRequest,
    PublicLocationSummary,
    QueryId,
)
from services.core.adapters.postgres_analytics import PostgresAnalytics

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


def _adapter(rows=()):
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    cursor.fetchall.return_value = rows
    connection = Mock()
    connection.cursor.return_value = cursor
    adapter = PostgresAnalytics(connection_factory=Mock(return_value=connection))
    return adapter, cursor, connection


def test_public_location_directory_is_a_bounded_typed_query():
    adapter, cursor, connection = _adapter(
        [(LOCATION_ID, "Reference Farm", "DO", "North", "active")]
    )

    result = adapter.execute(
        QueryId.PUBLIC_LOCATION_DIRECTORY,
        PublicLocationDirectoryRequest(),
        AnalyticsContext(),
    )

    assert result == (
        PublicLocationSummary(LOCATION_ID, "Reference Farm", "DO", "North", "active"),
    )
    assert cursor.execute.call_args_list[-1].args == (
        "SELECT location_id, location_name, country, region, status "
        "FROM v_public_farm_summary ORDER BY location_name, location_id LIMIT 100",
        (),
    )
    assert connection.rollback.called
    assert connection.close.called


def test_public_location_detail_binds_exact_location():
    adapter, cursor, _connection = _adapter(
        [(LOCATION_ID, "Reference Farm", "DO", "North", "active")]
    )

    adapter.execute(
        QueryId.PUBLIC_LOCATION_DIRECTORY,
        PublicLocationDirectoryRequest(LOCATION_ID),
        AnalyticsContext(location_id=LOCATION_ID),
    )

    assert cursor.execute.call_args_list[-1].args == (
        "SELECT location_id, location_name, country, region, status "
        "FROM v_public_farm_summary WHERE location_id = %s "
        "ORDER BY location_name, location_id LIMIT 100",
        (LOCATION_ID,),
    )


@pytest.mark.parametrize(
    ("query_id", "query_request", "context"),
    [
        (
            QueryId.PUBLIC_METRIC_SUMMARY,
            MetricSummaryRequest(LOCATION_ID),
            AnalyticsContext(location_id="22222222-2222-4222-8222-222222222222"),
        ),
        (
            QueryId.PUBLIC_METRIC_SUMMARY,
            MetricSummaryRequest(LOCATION_ID),
            AnalyticsContext(location_id=LOCATION_ID, public=False),
        ),
        (
            QueryId.PUBLIC_LOCATION_DIRECTORY,
            PublicLocationDirectoryRequest(LOCATION_ID),
            AnalyticsContext(),
        ),
    ],
)
def test_invalid_public_scope_is_rejected_before_connection(query_id, query_request, context):
    connection_factory = Mock()
    adapter = PostgresAnalytics(connection_factory=connection_factory)

    with pytest.raises(PermissionError):
        adapter.execute(query_id, query_request, context)

    connection_factory.assert_not_called()


def test_metric_summary_query_contract_remains_unchanged():
    computed_at = datetime(2026, 10, 26, tzinfo=timezone.utc)
    adapter, cursor, _connection = _adapter([("yield", "Yield", "kg", Decimal("12.5"), computed_at)])

    result = adapter.execute(
        QueryId.PUBLIC_METRIC_SUMMARY,
        MetricSummaryRequest(LOCATION_ID),
        AnalyticsContext(location_id=LOCATION_ID),
    )

    assert result == (MetricSummary("yield", "Yield", "kg", Decimal("12.5"), computed_at),)
    assert cursor.execute.call_args_list[-1].args[1] == (LOCATION_ID,)
