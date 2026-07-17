"""Built-in event handlers for the event bus.

These handlers are registered in the event_handler table and
invoked by the event bus when matching events are published.
"""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("events.handlers")


def handle_alert_notification(event_type: str, payload: dict) -> None:
    """Send alert notifications when thresholds are breached."""
    import os
    import json

    severity = payload.get("severity", "warning")
    metric = payload.get("metric", "unknown")
    value = payload.get("value")
    threshold = payload.get("threshold")
    device_id = payload.get("sensor_device_id", "unknown")
    message = payload.get("message", f"{metric} = {value} (threshold: {threshold})")

    logger.info("Alert notification: %s severity=%s", message, severity)

    # Webhook notification
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
    if webhook_url:
        try:
            import urllib.request

            alert_payload = json.dumps({
                "text": f"[{severity.upper()}] {message}",
                "severity": severity,
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "device_id": device_id,
            }).encode()
            req = urllib.request.Request(
                webhook_url,
                data=alert_payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            logger.info("Alert webhook sent successfully")
        except Exception:
            logger.exception("Failed to send alert webhook")

    # Directus notification
    directus_url = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
    admin_token = os.environ.get("DIRECTUS_ADMIN_TOKEN", "")
    if admin_token:
        try:
            import urllib.request

            notif_payload = json.dumps({
                "message": message,
                "severity": severity,
            }).encode()
            req = urllib.request.Request(
                f"{directus_url}/notifications",
                data=notif_payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {admin_token}",
                },
            )
            urllib.request.urlopen(req, timeout=10)
            logger.info("Directus notification sent")
        except Exception:
            logger.exception("Failed to send Directus notification")


def handle_stale_data(event_type: str, payload: dict) -> None:
    """Adapt stale-data events to the standard alert notification handler."""
    handle_alert_notification(event_type, payload)
