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
def test_handle_metric_computed_invalidates_analytics(MockCache):
    """Metric computed event invalidates analytics cache for the location."""
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
def test_handle_crisp_scored_invalidates_crisp(MockCache):
    """CRISP scored event invalidates crisp cache for the location."""
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
