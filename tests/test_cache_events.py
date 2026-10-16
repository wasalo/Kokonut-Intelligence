"""Tests for services.cache.events — event-driven cache invalidation handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.cache.events import (
    handle_crisp_scored,
    handle_harvest_recorded,
    handle_metric_computed,
    handle_sensor_reading,
)

LOCATION_1 = "11111111-1111-4111-8111-111111111111"
LOCATION_2 = "22222222-2222-4222-8222-222222222222"


@patch("services.cache.cache.ComputationCache")
def test_handle_metric_computed_invalidates_analytics(MockCache, monkeypatch):
    """Metric computed event invalidates analytics cache for the location."""
    monkeypatch.setattr("services.core.features.is_enabled", lambda _feature: False)
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 2
    MockCache.return_value = cache_instance

    handle_metric_computed("metric_computed", {"location_id": LOCATION_1})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="analytics",
        location_id=LOCATION_1,
        reason="metric_computed:metric_computed",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_crisp_scored_invalidates_crisp(MockCache, monkeypatch):
    """CRISP scored event invalidates crisp cache for the location."""
    monkeypatch.setattr("services.core.features.is_enabled", lambda _feature: False)
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 1
    MockCache.return_value = cache_instance

    handle_crisp_scored("crisp_scored", {"location_id": LOCATION_2})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="crisp",
        location_id=LOCATION_2,
        reason="crisp_scored:crisp_scored",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_sensor_reading_invalidates_metric(MockCache):
    """Sensor reading event invalidates metric cache for the location."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 5
    MockCache.return_value = cache_instance

    handle_sensor_reading("sensor_reading", {"location_id": LOCATION_1})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="metric",
        location_id=LOCATION_1,
        reason="sensor_reading:sensor_reading",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_harvest_recorded_invalidates_metric(MockCache):
    """Harvest recorded event invalidates metric cache for the location."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 3
    MockCache.return_value = cache_instance

    handle_harvest_recorded("harvest_recorded", {"location_id": LOCATION_2})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="metric",
        location_id=LOCATION_2,
        reason="harvest_recorded:harvest_recorded",
    )


@pytest.mark.parametrize(
    ("handler", "event_type"),
    [
        (handle_metric_computed, "metric_computed"),
        (handle_crisp_scored, "crisp_scored"),
        (handle_sensor_reading, "sensor_reading"),
        (handle_harvest_recorded, "harvest_recorded"),
    ],
)
@pytest.mark.parametrize("payload", [{}, {"location_id": "not-a-uuid"}, {"location_id": None}])
@patch("services.cache.cache.ComputationCache")
def test_unscoped_or_invalid_location_never_invalidates_cache(
    MockCache, handler, event_type, payload
):
    with pytest.raises(ValueError, match="valid location_id"):
        handler(event_type, payload)
    MockCache.assert_not_called()


@pytest.mark.parametrize(
    ("handler", "event_type"),
    [
        (handle_metric_computed, "metric_computed"),
        (handle_crisp_scored, "crisp_scored"),
        (handle_sensor_reading, "sensor_reading"),
        (handle_harvest_recorded, "harvest_recorded"),
    ],
)
def test_signed_cache_invalidation_sets_scope_and_uses_bounded_function(
    handler, event_type, monkeypatch
):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (2,)
    connection.cursor.return_value.__enter__.return_value = cursor
    set_context = MagicMock()
    get_credential = MagicMock(return_value="synthetic-cache-worker-credential")
    get_connection = MagicMock(return_value=connection)

    monkeypatch.setattr("services.core.features.is_enabled", lambda _feature: True)
    monkeypatch.setattr("services.common.tenant_context.set_worker_tenant_context", set_context)
    monkeypatch.setattr("services.common.worker_database.get_worker_credential", get_credential)
    monkeypatch.setattr("services.common.worker_database.get_worker_db", get_connection)

    handler(event_type, {"location_id": LOCATION_1}, event_id="33333333-3333-4333-8333-333333333333")

    get_credential.assert_called_once_with("cache_invalidation")
    get_connection.assert_called_once_with("cache_invalidation")
    set_context.assert_called_once_with(
        connection,
        credential="synthetic-cache-worker-credential",
        location_id=LOCATION_1,
        resource="computation_cache",
        action="invalidate",
    )
    sql, params = cursor.execute.call_args.args
    assert "kokonut_security.invalidate_worker_computation_cache" in sql
    assert params == ("33333333-3333-4333-8333-333333333333", event_type)
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    ("handler", "event_type"),
    [
        (handle_metric_computed, "metric_computed"),
        (handle_crisp_scored, "crisp_scored"),
        (handle_sensor_reading, "sensor_reading"),
        (handle_harvest_recorded, "harvest_recorded"),
    ],
)
def test_signed_cache_invalidation_rolls_back_and_closes_on_database_error(
    handler, event_type, monkeypatch
):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("synthetic database error")
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr("services.core.features.is_enabled", lambda _feature: True)
    monkeypatch.setattr(
        "services.common.tenant_context.set_worker_tenant_context", MagicMock()
    )
    monkeypatch.setattr(
        "services.common.worker_database.get_worker_credential",
        lambda _worker: "synthetic-cache-worker-credential",
    )
    monkeypatch.setattr(
        "services.common.worker_database.get_worker_db", lambda _worker: connection
    )

    with pytest.raises(RuntimeError, match="synthetic database error"):
        handler(
            event_type,
            {"location_id": LOCATION_1},
            event_id="33333333-3333-4333-8333-333333333333",
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    ("handler", "expected_type"),
    [
        (handle_metric_computed, "metric_computed"),
        (handle_crisp_scored, "crisp_scored"),
        (handle_sensor_reading, "sensor_reading"),
        (handle_harvest_recorded, "harvest_recorded"),
    ],
)
def test_signed_cache_invalidation_rejects_wrong_handler_type_before_database_access(
    handler, expected_type, monkeypatch
):
    monkeypatch.setattr("services.core.features.is_enabled", lambda _feature: True)
    get_credential = MagicMock()
    get_connection = MagicMock()
    monkeypatch.setattr("services.common.worker_database.get_worker_credential", get_credential)
    monkeypatch.setattr("services.common.worker_database.get_worker_db", get_connection)

    with pytest.raises(ValueError, match="event type does not match"):
        handler(
            "wrong_event",
            {"location_id": LOCATION_1},
            event_id="33333333-3333-4333-8333-333333333333",
        )

    get_credential.assert_not_called()
    get_connection.assert_not_called()


@pytest.mark.parametrize(
    ("handler", "event_type"),
    [
        (handle_metric_computed, "metric_computed"),
        (handle_crisp_scored, "crisp_scored"),
        (handle_sensor_reading, "sensor_reading"),
        (handle_harvest_recorded, "harvest_recorded"),
    ],
)
@pytest.mark.parametrize("event_id", [None, "not-a-uuid"])
def test_signed_cache_invalidation_requires_valid_durable_event_id(
    handler, event_type, event_id, monkeypatch
):
    monkeypatch.setattr("services.core.features.is_enabled", lambda _feature: True)
    get_credential = MagicMock()
    get_connection = MagicMock()
    monkeypatch.setattr("services.common.worker_database.get_worker_credential", get_credential)
    monkeypatch.setattr("services.common.worker_database.get_worker_db", get_connection)

    with pytest.raises(ValueError, match="valid event_id"):
        handler(
            event_type,
            {"location_id": LOCATION_1},
            event_id=event_id,
        )

    get_credential.assert_not_called()
    get_connection.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
