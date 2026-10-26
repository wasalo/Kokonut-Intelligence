"""Built-in event handlers for the event bus.

These handlers are registered in the event_handler table and
invoked by the event bus when matching events are published.
"""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("events.handlers")


def handle_alert_notification(event_type: str, payload: dict, *, event_id: str | None = None) -> None:
    """Persist configured alert notifications before acknowledging the event."""
    from services.common.database import get_connection
    from services.core.features import is_enabled
    from services.events.notification_outbox import (
        _notification_payloads,
        enqueue_event_notification,
        enqueue_event_notification_isolated,
    )

    if not event_id:
        if _notification_payloads(event_type, payload):
            raise ValueError("configured alert notifications require their source event ID")
        logger.debug("No configured notification destination for event type %s", event_type)
        return

    if is_enabled("isolated_notification_enqueue"):
        from services.common.worker_database import get_worker_db

        conn = get_worker_db("notification_enqueue")
        try:
            queued = enqueue_event_notification_isolated(
                conn,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                location_id=payload.get("location_id"),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        with get_connection() as conn:
            queued = enqueue_event_notification(
                conn,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                location_id=payload.get("location_id"),
            )
    logger.info("Queued %d alert notification deliveries for event %s", queued, event_id)


def handle_stale_data(
    event_type: str, payload: dict, *, event_id: str | None = None
) -> None:
    """Adapt stale-data events to the durable alert notification outbox."""
    handle_alert_notification(event_type, payload, event_id=event_id)
