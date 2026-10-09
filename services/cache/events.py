"""Event-driven cache invalidation handlers.

Registered as event handlers in the event bus — when platform events
fire (sensor_reading, metric_computed, etc.), these handlers invalidate
the relevant cache entries.
"""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("cache.events")


def handle_metric_computed(event_type: str, payload: dict) -> None:
    """Invalidate analytics caches when metrics are recomputed."""
    from services.cache.cache import ComputationCache

    location_id = payload.get("location_id")
    cache = ComputationCache()

    count = cache.invalidate(
        computation_type="analytics",
        location_id=location_id,
        reason=f"metric_computed:{event_type}",
    )
    logger.info("Invalidated %d analytics cache entries for location %s", count, location_id)


def handle_crisp_scored(event_type: str, payload: dict) -> None:
    """Invalidate CRISP caches when scores are recomputed."""
    from services.cache.cache import ComputationCache

    location_id = payload.get("location_id")
    cache = ComputationCache()

    count = cache.invalidate(
        computation_type="crisp",
        location_id=location_id,
        reason=f"crisp_scored:{event_type}",
    )
    logger.info("Invalidated %d CRISP cache entries for location %s", count, location_id)


def handle_sensor_reading(event_type: str, payload: dict) -> None:
    """Invalidate metric caches when new sensor data arrives."""
    from services.cache.cache import ComputationCache

    location_id = payload.get("location_id")
    cache = ComputationCache()

    count = cache.invalidate(
        computation_type="metric",
        location_id=location_id,
        reason=f"sensor_reading:{event_type}",
    )
    logger.info("Invalidated %d metric cache entries for location %s", count, location_id)


def handle_harvest_recorded(event_type: str, payload: dict) -> None:
    """Invalidate metric caches when a harvest is recorded."""
    from services.cache.cache import ComputationCache

    location_id = payload.get("location_id")
    cache = ComputationCache()

    count = cache.invalidate(
        computation_type="metric",
        location_id=location_id,
        reason=f"harvest_recorded:{event_type}",
    )
    logger.info("Invalidated %d metric cache entries for location %s", count, location_id)
