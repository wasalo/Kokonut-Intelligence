"""Built-in event handlers for the event bus.

These handlers are registered in the event_handler table and
invoked by the event bus when matching events are published.
"""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("events.handlers")


def handle_alert_notification(event_type: str, payload: dict, *, event_id: str | None = None) -> None:
    """Persist configured alert notifications before acknowledging the event."""
    from services.core.features import require_feature
    from services.events.notification_outbox import (
        _notification_payloads,
        enqueue_event_notification_isolated,
    )

    if not isinstance(payload, dict):
        raise ValueError("notification payload must be a JSON object")
    messages = _notification_payloads(event_type, payload)
    if not event_id:
        if messages:
            raise ValueError("configured alert notifications require their source event ID")
        logger.debug("No configured notification destination for event type %s", event_type)
        return

    if not messages:
        logger.debug("No configured notification destination for event type %s", event_type)
        return

    from uuid import UUID

    try:
        event_id = str(UUID(str(event_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("a valid source event UUID is required for notification delivery") from exc
    location_id = payload.get("location_id")
    if location_id is not None:
        try:
            location_id = str(UUID(str(location_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("location_id must be a valid UUID") from exc

    # Never enqueue notification intents through the shared runtime login.
    # Check the opt-in before obtaining any database connection so a disabled
    # isolated worker fails closed without triggering a legacy fallback.
    require_feature("isolated_notification_enqueue")
    from services.common.worker_database import get_worker_db

    conn = get_worker_db("notification_enqueue")
    try:
        queued = enqueue_event_notification_isolated(
            conn,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            location_id=location_id,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    logger.info("Queued %d alert notification deliveries for event %s", queued, event_id)


def handle_stale_data(
    event_type: str, payload: dict, *, event_id: str | None = None
) -> None:
    """Adapt stale-data events to the durable alert notification outbox."""
    handle_alert_notification(event_type, payload, event_id=event_id)
