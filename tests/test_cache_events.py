"""Tests for services.cache.events — event-driven cache invalidation handlers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.cache.events import (
    handle_metric_computed,
    handle_crisp_scored,
    handle_sensor_reading,
    handle_harvest_recorded,
)


@patch("services.cache.cache.ComputationCache")
def test_handle_metric_computed_invalidates_analytics(MockCache):
    """Metric computed event invalidates analytics cache for the location."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 2
    MockCache.return_value = cache_instance

    handle_metric_computed("metric_computed", {"location_id": "loc-1"})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="analytics",
        location_id="loc-1",
        reason="metric_computed:metric_computed",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_crisp_scored_invalidates_crisp(MockCache):
    """CRISP scored event invalidates crisp cache for the location."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 1
    MockCache.return_value = cache_instance

    handle_crisp_scored("crisp_scored", {"location_id": "loc-42"})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="crisp",
        location_id="loc-42",
        reason="crisp_scored:crisp_scored",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_sensor_reading_invalidates_metric(MockCache):
    """Sensor reading event invalidates metric cache for the location."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 5
    MockCache.return_value = cache_instance

    handle_sensor_reading("sensor_reading", {"location_id": "loc-7"})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="metric",
        location_id="loc-7",
        reason="sensor_reading:sensor_reading",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_harvest_recorded_invalidates_metric(MockCache):
    """Harvest recorded event invalidates metric cache for the location."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 3
    MockCache.return_value = cache_instance

    handle_harvest_recorded("harvest_recorded", {"location_id": "loc-99"})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="metric",
        location_id="loc-99",
        reason="harvest_recorded:harvest_recorded",
    )


@patch("services.cache.cache.ComputationCache")
def test_handle_event_missing_location_id(MockCache):
    """Events without location_id still invalidate (location_id=None)."""
    cache_instance = MagicMock()
    cache_instance.invalidate.return_value = 0
    MockCache.return_value = cache_instance

    handle_metric_computed("metric_computed", {})

    cache_instance.invalidate.assert_called_once_with(
        computation_type="analytics",
        location_id=None,
        reason="metric_computed:metric_computed",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
