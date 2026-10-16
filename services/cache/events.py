"""Event-driven cache invalidation handlers.

Registered as event handlers in the event bus — when platform events
fire (sensor_reading, metric_computed, etc.), these handlers invalidate
the relevant cache entries.
"""

from __future__ import annotations

from uuid import UUID

from services.cache.ports import ComputationCacheBackend
from services.common.logging import get_logger

logger = get_logger("cache.events")

_CACHE_EVENT_COMPUTATION_TYPES = {
    "metric_computed": "analytics",
    "crisp_scored": "crisp",
}


def _require_location_id(payload: dict) -> str:
    """Reject unscoped invalidation so malformed events cannot flush all tenants."""
    try:
        return str(UUID(str(payload.get("location_id", ""))))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("cache invalidation requires a valid location_id") from exc


def _invalidate_event_cache(
    *,
    expected_event_type: str,
    event_type: str,
    payload: dict,
    event_id: str | None,
    cache_backend: ComputationCacheBackend | None,
) -> tuple[int, str]:
    location_id = _require_location_id(payload)
    if event_type != expected_event_type:
        raise ValueError("cache invalidation event type does not match its handler")

    reason = f"{expected_event_type}:{event_type}"
    if cache_backend is not None:
        count = cache_backend.invalidate(
            computation_type=_CACHE_EVENT_COMPUTATION_TYPES[expected_event_type],
            location_id=location_id,
            reason=reason,
        )
        return count, location_id

    from services.core.features import is_enabled

    if not is_enabled("signed_cache_invalidation"):
        from services.cache.backend import get_computation_cache

        cache = get_computation_cache()
        count = cache.invalidate(
            computation_type=_CACHE_EVENT_COMPUTATION_TYPES[expected_event_type],
            location_id=location_id,
            reason=reason,
        )
        return count, location_id

    try:
        normalized_event_id = str(UUID(str(event_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("cache invalidation requires a valid event_id") from exc

    from services.common.tenant_context import set_worker_tenant_context
    from services.common.worker_database import get_worker_credential, get_worker_db

    credential = get_worker_credential("cache_invalidation")
    connection = get_worker_db("cache_invalidation")
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource="computation_cache",
            action="invalidate",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT kokonut_security.invalidate_worker_computation_cache(
                    %s::uuid, %s
                )
                """,
                (normalized_event_id, expected_event_type),
            )
            row = cursor.fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("database did not return a cache invalidation count")
        count = int(row[0])
        connection.commit()
        return count, location_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_metric_computed(
    event_type: str,
    payload: dict,
    *,
    event_id: str | None = None,
    cache_backend: ComputationCacheBackend | None = None,
) -> None:
    """Invalidate analytics caches when metrics are recomputed."""
    count, location_id = _invalidate_event_cache(
        expected_event_type="metric_computed",
        event_type=event_type,
        payload=payload,
        event_id=event_id,
        cache_backend=cache_backend,
    )
    logger.info("Invalidated %d analytics cache entries for location %s", count, location_id)


def handle_crisp_scored(
    event_type: str,
    payload: dict,
    *,
    event_id: str | None = None,
    cache_backend: ComputationCacheBackend | None = None,
) -> None:
    """Invalidate CRISP caches when scores are recomputed."""
    count, location_id = _invalidate_event_cache(
        expected_event_type="crisp_scored",
        event_type=event_type,
        payload=payload,
        event_id=event_id,
        cache_backend=cache_backend,
    )
    logger.info("Invalidated %d CRISP cache entries for location %s", count, location_id)


def handle_sensor_reading(
    event_type: str,
    payload: dict,
    *,
    cache_backend: ComputationCacheBackend | None = None,
) -> None:
    """Invalidate metric caches when new sensor data arrives."""
    from services.cache.backend import get_computation_cache

    location_id = _require_location_id(payload)
    cache = cache_backend if cache_backend is not None else get_computation_cache()
    count = cache.invalidate(
        computation_type="metric",
        location_id=location_id,
        reason=f"sensor_reading:{event_type}",
    )
    logger.info("Invalidated %d metric cache entries for location %s", count, location_id)


def handle_harvest_recorded(
    event_type: str,
    payload: dict,
    *,
    cache_backend: ComputationCacheBackend | None = None,
) -> None:
    """Invalidate metric caches when a harvest is recorded."""
    from services.cache.backend import get_computation_cache

    location_id = _require_location_id(payload)
    cache = cache_backend if cache_backend is not None else get_computation_cache()
    count = cache.invalidate(
        computation_type="metric",
        location_id=location_id,
        reason=f"harvest_recorded:{event_type}",
    )
    logger.info("Invalidated %d metric cache entries for location %s", count, location_id)
