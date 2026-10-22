"""PostgreSQL-backed, at-least-once delivery for event notifications.

Event handlers persist notification intent here and return. A separate worker
claims the durable rows, sends through the configured provider, and records each
attempt. External receivers may observe duplicates if a worker exits after a
successful send but before its database acknowledgement; the stable idempotency
header lets receivers that support it suppress those duplicates.
"""

from __future__ import annotations

import json
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any

from services.common.logging import get_logger

logger = get_logger("events.notification_outbox")

MAX_ATTEMPTS = 8
LEASE_SECONDS = 300
MAX_BATCH_SIZE = 500
RETRY_BASE_SECONDS = 15
RETRY_MAX_SECONDS = 3600
DESTINATION_KEY = "primary"
DEFAULT_STORAGE_WARN_BYTES = 256 * 1024 * 1024
DEFAULT_STORAGE_CRITICAL_BYTES = 512 * 1024 * 1024


class NotificationOutboxError(RuntimeError):
    """Base error for notification queue operations."""


class NotificationIdempotencyConflict(NotificationOutboxError):
    """One event/channel identity was reused with a different payload."""


class NotificationConfigurationError(NotificationOutboxError):
    """A persisted notification has no currently configured destination."""


def _notification_payloads(
    event_type: str,
    payload: dict[str, Any],
    *,
    environment: dict[str, str] | None = None,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Build allowlisted notification messages without persisting credentials."""
    environment = os.environ if environment is None else environment
    severity = str(payload.get("severity") or "warning")
    metric = str(payload.get("metric") or "unknown")
    value = payload.get("value")
    threshold = payload.get("threshold")
    device_id = str(payload.get("sensor_device_id") or "unknown")
    message = str(payload.get("message") or f"{metric} = {value} (threshold: {threshold})")
    destinations: list[tuple[str, str, dict[str, Any]]] = []

    if environment.get("ALERT_WEBHOOK_URL", "").strip():
        if event_type == "sensor_alert":
            webhook_payload = {
                "text": f"[{severity.upper()}] {message}",
                "alert_id": payload.get("alert_id"),
                "severity": severity,
                "message": message,
                "sensor_device_id": payload.get("sensor_device_id"),
                "sensor_name": payload.get("sensor_name"),
                "sensor_type": payload.get("sensor_type"),
                "location_id": payload.get("location_id"),
                "location_name": payload.get("location_name"),
                "reading_value": payload.get("reading_value"),
                "threshold_value": payload.get("threshold_value"),
                "triggered_at": payload.get("triggered_at"),
                "claim_id": payload.get("claim_id"),
            }
        elif event_type == "data_stale":
            webhook_payload = {
                "text": message,
                "alert_id": payload.get("alert_id"),
                "source": payload.get("source_system"),
                "status": payload.get("status"),
                "severity": severity,
                "location_id": payload.get("location_id"),
                "gap_minutes": payload.get("gap_minutes"),
                "last_data_at": payload.get("last_data_at"),
            }
        else:
            webhook_payload = {
                "text": f"[{severity.upper()}] {message}",
                "severity": severity,
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "device_id": device_id,
            }
        destinations.append((
            "webhook",
            DESTINATION_KEY,
            webhook_payload,
        ))

    from services.core.providers import ProviderSettings

    if (ProviderSettings.from_environment(environment).directus
            and environment.get("DIRECTUS_ADMIN_TOKEN", "").strip()):
        if event_type == "sensor_alert":
            destinations.append((
                "directus",
                DESTINATION_KEY,
                {
                    "subject": f"Sensor Alert: {payload.get('sensor_name') or 'Unknown'}",
                    "message": message,
                    "type": severity,
                    "recipient": "role:00000000-0000-0000-0000-000000000006",
                    "status": "unread",
                },
            ))
        else:
            destinations.append((
                "directus",
                DESTINATION_KEY,
                {"message": message, "severity": severity},
            ))

    if (event_type in {"sensor_alert", "data_stale"}
            and environment.get("ALERT_SMTP_HOST", "").strip()
            and environment.get("ALERT_EMAIL_TO", "").strip()):
        if event_type == "sensor_alert":
            sensor_name = str(payload.get("sensor_name") or "Unknown")
            sensor_type = str(payload.get("sensor_type") or "unknown")
            location = str(payload.get("location_name") or "Unknown")
            subject = f"[{severity.upper()}] Sensor Alert: {sensor_name}"
            claim_line = f"Claim ID: {payload['claim_id']}\n" if payload.get("claim_id") else ""
            body = (
                "Sensor Alert Triggered\n\n"
                f"Severity: {severity.upper()}\n"
                f"Sensor: {sensor_name} ({sensor_type})\n"
                f"Location: {location}\n"
                f"Message: {message}\n\n"
                f"Reading Value: {payload.get('reading_value')}\n"
                f"Threshold: {payload.get('threshold_value')}\n"
                f"Time: {payload.get('triggered_at')}\n\n"
                f"Alert ID: {payload.get('alert_id')}\n"
                f"{claim_line}\nKokonut Intelligence Alert System\n"
            )
        else:
            source_system = str(payload.get("source_system") or "unknown")
            status = str(payload.get("status") or "unknown")
            subject = f"[Kokonut] Data freshness {status}: {source_system}"
            body = f"{message}\nAlert ID: {payload.get('alert_id')}\n"
        destinations.append(("email", DESTINATION_KEY, {"subject": subject, "body": body}))

    return destinations


def _configured_channels(environment: dict[str, str] | None = None) -> list[str]:
    """Return enabled destinations so disabled providers keep their retry budget."""
    environment = os.environ if environment is None else environment
    channels = []
    if environment.get("ALERT_WEBHOOK_URL", "").strip():
        channels.append("webhook")
    from services.core.providers import ProviderSettings

    if (ProviderSettings.from_environment(environment).directus
            and environment.get("DIRECTUS_ADMIN_TOKEN", "").strip()):
        channels.append("directus")
    if (environment.get("ALERT_SMTP_HOST", "").strip()
            and environment.get("ALERT_EMAIL_TO", "").strip()):
        channels.append("email")
    return channels


def enqueue_event_notification(
    conn,
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    location_id: str | None = None,
    environment: dict[str, str] | None = None,
) -> int:
    """Persist configured notification intents idempotently in the caller's transaction."""
    stable_event_id, event_type, location_id, messages = _prepare_event_notification(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        location_id=location_id,
        environment=environment,
    )
    inserted = 0
    with conn.cursor() as cur:
        for channel, destination_key, message in messages:
            encoded = json.dumps(message, sort_keys=True, separators=(",", ":"), default=str)
            cur.execute(
                """
                INSERT INTO notification_outbox
                    (source_event_id, event_type, channel, destination_key, payload, location_id)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::uuid)
                ON CONFLICT (source_event_id, channel, destination_key) DO NOTHING
                RETURNING id
                """,
                (stable_event_id, event_type, channel, destination_key, encoded, location_id),
            )
            row = cur.fetchone()
            if row is not None:
                inserted += 1
                continue

            cur.execute(
                """
                SELECT event_type, payload, location_id
                FROM notification_outbox
                WHERE source_event_id = %s AND channel = %s AND destination_key = %s
                FOR UPDATE
                """,
                (stable_event_id, channel, destination_key),
            )
            existing = cur.fetchone()
            if existing is None:
                raise NotificationOutboxError("notification identity disappeared during enqueue")
            stored_payload = existing[1]
            if isinstance(stored_payload, str):
                stored_payload = json.loads(stored_payload)
            if existing[0] != event_type or stored_payload != message:
                raise NotificationIdempotencyConflict(
                    "source event notification identity conflicts with existing content"
                )
            if existing[2] is None and location_id is not None:
                cur.execute(
                    """
                    UPDATE notification_outbox SET location_id = %s::uuid
                    WHERE source_event_id = %s AND channel = %s
                      AND destination_key = %s AND location_id IS NULL
                    """,
                    (location_id, stable_event_id, channel, destination_key),
                )
            elif (
                location_id is not None
                and existing[2] is not None
                and str(existing[2]) != location_id
            ):
                raise NotificationIdempotencyConflict(
                    "source event notification location conflicts with existing content"
                )
    return inserted


def enqueue_event_notification_isolated(
    conn,
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    location_id: str | None = None,
    environment: dict[str, str] | None = None,
) -> int:
    """Enqueue through the isolated notification identity's bounded SQL function."""
    stable_event_id, stable_event_type, stable_location_id, messages = (
        _prepare_event_notification(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            location_id=location_id,
            environment=environment,
        )
    )
    if not messages:
        return 0
    request = [
        {"channel": channel, "destination_key": destination_key, "payload": message}
        for channel, destination_key, message in messages
    ]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT kokonut_security.enqueue_notification_intents(
                %s::uuid, %s, %s::uuid, %s::jsonb
            )
            """,
            (
                stable_event_id,
                stable_event_type,
                stable_location_id,
                json.dumps(request, sort_keys=True, separators=(",", ":"), default=str),
            ),
        )
        row = cur.fetchone()
    if row is None or isinstance(row[0], bool) or not isinstance(row[0], int):
        raise NotificationOutboxError("notification enqueue function returned an invalid result")
    return row[0]


def _prepare_event_notification(
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    location_id: str | None,
    environment: dict[str, str] | None,
) -> tuple[str, str, str | None, list[tuple[str, str, dict[str, Any]]]]:
    """Validate shared handler inputs and build bounded, secret-free intents."""
    try:
        stable_event_id = str(uuid.UUID(str(event_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("a valid source event UUID is required for notification delivery") from exc
    if not event_type or not isinstance(event_type, str):
        raise ValueError("event_type is required for notification delivery")
    if not isinstance(payload, dict):
        raise ValueError("notification payload must be a JSON object")
    if location_id is not None:
        try:
            location_id = str(uuid.UUID(str(location_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("location_id must be a valid UUID") from exc

    messages = _notification_payloads(event_type, payload, environment=environment)
    for channel, destination_key, message in messages:
        if channel not in {"webhook", "directus", "email"}:
            raise ValueError("notification channel is not allowlisted")
        if destination_key != DESTINATION_KEY or not isinstance(message, dict):
            raise ValueError("notification destination is invalid")
        encoded = json.dumps(message, sort_keys=True, separators=(",", ":"), default=str)
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("notification payload exceeds the 16 KiB limit")
    return stable_event_id, event_type, location_id, messages


def _recover_expired_leases(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE notification_outbox_attempt a
            SET status = 'lease_lost', finished_at = NOW(),
                error_class = COALESCE(a.error_class, 'LeaseExpired')
            FROM notification_outbox o
            WHERE a.outbox_id = o.id AND a.lease_token = o.lease_token
              AND a.status = 'processing' AND o.status = 'processing'
              AND o.lease_expires_at < NOW()
            """
        )
        cur.execute(
            """
            UPDATE notification_outbox
            SET status = CASE WHEN retry_cycle_attempts >= %s THEN 'dead_letter' ELSE 'retryable' END,
                lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
                available_at = NOW(), updated_at = NOW(),
                last_error_class = COALESCE(last_error_class, 'LeaseExpired')
            WHERE status = 'processing' AND lease_expires_at < NOW()
            """,
            (MAX_ATTEMPTS,),
        )


def claim_batch(
    conn,
    worker_id: str,
    limit: int = 100,
    *,
    lease_seconds: int = LEASE_SECONDS,
) -> list[dict[str, Any]]:
    """Claim a bounded batch and commit durable leases before any network I/O."""
    if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 150:
        raise ValueError("worker_id must contain 1 to 150 characters")
    if not isinstance(limit, int) or not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_BATCH_SIZE}")
    if not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 3600:
        raise ValueError("lease_seconds must be between 30 and 3600")

    channels = _configured_channels()
    if not channels:
        _recover_expired_leases(conn)
        conn.commit()
        return []

    lease_token = str(uuid.uuid4())
    _recover_expired_leases(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH candidates AS (
                SELECT id
                FROM notification_outbox
                WHERE status IN ('pending', 'retryable') AND available_at <= NOW()
                  AND channel = ANY(%s)
                ORDER BY available_at, created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE notification_outbox o
            SET status = 'processing', attempt_count = o.attempt_count + 1,
                retry_cycle_attempts = o.retry_cycle_attempts + 1,
                lease_owner = %s, lease_token = %s,
                lease_expires_at = NOW() + (%s * INTERVAL '1 second'),
                updated_at = NOW()
            FROM candidates c
            WHERE o.id = c.id
            RETURNING o.id, o.source_event_id, o.event_type, o.channel,
                      o.destination_key, o.payload, o.attempt_count,
                      o.lease_owner, o.lease_token
            """,
            (channels, limit, worker_id, lease_token, lease_seconds),
        )
        names = [item[0] for item in cur.description]
        rows = [dict(zip(names, row)) for row in cur.fetchall()]
        for row in rows:
            cur.execute(
                """
                INSERT INTO notification_outbox_attempt
                    (outbox_id, attempt_number, lease_owner, lease_token)
                VALUES (%s, %s, %s, %s)
                """,
                (row["id"], row["attempt_count"], worker_id, row["lease_token"]),
            )
    conn.commit()
    return rows


def _deliver(row: dict[str, Any]) -> None:
    headers = {"Idempotency-Key": str(row["id"])}
    if row["channel"] == "webhook":
        from services.common.http import http

        url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
        if not url:
            raise NotificationConfigurationError("webhook destination is no longer configured")
        response = http.post(url, json=row["payload"], headers=headers, timeout=10)
    elif row["channel"] == "directus":
        from services.common.http import http
        from services.core.providers import ProviderSettings

        if not ProviderSettings.from_environment().directus:
            raise NotificationConfigurationError("Directus notification provider is disabled")
        base_url = os.environ.get("DIRECTUS_URL", "http://localhost:8055").rstrip("/")
        token = os.environ.get("DIRECTUS_ADMIN_TOKEN", "").strip()
        if not token:
            raise NotificationConfigurationError("Directus notification credentials are unavailable")
        response = http.post(
            f"{base_url}/notifications",
            json=row["payload"],
            headers={**headers, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
    elif row["channel"] == "email":
        host = os.environ.get("ALERT_SMTP_HOST", "").strip()
        recipient = os.environ.get("ALERT_EMAIL_TO", "").strip()
        if not host or not recipient:
            raise NotificationConfigurationError("email destination is no longer configured")
        try:
            port = int(os.environ.get("ALERT_SMTP_PORT", "587"))
        except ValueError as exc:
            raise NotificationConfigurationError("email SMTP port must be an integer") from exc

        msg = EmailMessage()
        msg["From"] = os.environ.get("ALERT_EMAIL_FROM", "alerts@kokonut.network").strip()
        msg["To"] = recipient
        msg["Subject"] = str(row["payload"].get("subject") or "Kokonut sensor alert")
        msg["Message-ID"] = f"<kokonut-outbox-{row['id']}@kokonut.local>"
        msg["X-Kokonut-Idempotency-Key"] = str(row["id"])
        msg.set_content(str(row["payload"].get("body") or "Kokonut sensor alert"))

        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            if port != 25:
                server.starttls()
                server.ehlo()
            username = os.environ.get("ALERT_SMTP_USER", "").strip()
            if username:
                server.login(username, os.environ.get("ALERT_SMTP_PASSWORD", ""))
            server.send_message(msg)
        return
    else:
        raise NotificationConfigurationError("unsupported notification channel")
    response.raise_for_status()


def _retry_delay_seconds(attempt_count: int) -> int:
    exponent = min(max(attempt_count - 1, 0), 8)
    return min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2 ** exponent))


def _finish_attempt(
    conn,
    row: dict[str, Any],
    *,
    success: bool,
    error_class: str | None = None,
) -> str:
    """Acknowledge only while this process still owns the unexpired lease."""
    delay = _retry_delay_seconds(int(row["attempt_count"]))
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE notification_outbox
            SET status = CASE WHEN %s THEN 'succeeded'
                              WHEN retry_cycle_attempts >= %s THEN 'dead_letter'
                              ELSE 'retryable' END,
                available_at = CASE WHEN %s THEN available_at
                                    ELSE NOW() + (%s * INTERVAL '1 second') END,
                delivered_at = CASE WHEN %s THEN NOW() ELSE delivered_at END,
                last_error_class = %s,
                lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
                updated_at = NOW()
            WHERE id = %s AND status = 'processing'
              AND lease_owner = %s AND lease_token = %s
              AND lease_expires_at > NOW()
            RETURNING id
            """,
            (
                success, MAX_ATTEMPTS, success, delay, success, error_class,
                row["id"], row["lease_owner"], row["lease_token"],
            ),
        )
        owned = cur.fetchone() is not None
        attempt_status = ("succeeded" if success else "failed") if owned else "lease_lost"
        cur.execute(
            """
            UPDATE notification_outbox_attempt
            SET status = %s, error_class = %s, finished_at = NOW()
            WHERE outbox_id = %s AND attempt_number = %s
              AND lease_token = %s AND status = 'processing'
            """,
            (attempt_status, error_class, row["id"], row["attempt_count"], row["lease_token"]),
        )
    conn.commit()
    return attempt_status


def deliver_batch(conn, worker_id: str, limit: int = 100) -> dict[str, int]:
    """Deliver one batch with bounded retries; external sends remain at-least-once."""
    rows = claim_batch(conn, worker_id, limit)
    stats = {"claimed": len(rows), "delivered": 0, "failed": 0, "lease_lost": 0}
    for row in rows:
        error_class = None
        try:
            _deliver(row)
            success = True
        except Exception as exc:  # Persist only the class; URLs/response text may contain secrets.
            success = False
            error_class = type(exc).__name__[:100]
            logger.warning(
                "Notification delivery failed (outbox_id=%s channel=%s class=%s)",
                row["id"], row["channel"], error_class,
            )
        status = _finish_attempt(conn, row, success=success, error_class=error_class)
        if status == "succeeded":
            stats["delivered"] += 1
        elif status == "lease_lost":
            stats["lease_lost"] += 1
        else:
            stats["failed"] += 1
    return stats


def _storage_thresholds() -> tuple[int, int]:
    """Return advisory table-size thresholds; they never block notification writes."""
    try:
        warning = int(os.environ.get(
            "KOKONUT_NOTIFICATION_OUTBOX_WARN_BYTES", DEFAULT_STORAGE_WARN_BYTES
        ))
        critical = int(os.environ.get(
            "KOKONUT_NOTIFICATION_OUTBOX_CRITICAL_BYTES", DEFAULT_STORAGE_CRITICAL_BYTES
        ))
    except (TypeError, ValueError) as exc:
        raise NotificationConfigurationError(
            "notification outbox storage thresholds must be integer byte counts"
        ) from exc
    if warning < 1 or critical < warning:
        raise NotificationConfigurationError(
            "notification outbox thresholds require 1 <= warning <= critical"
        )
    return warning, critical


def get_stats(conn) -> dict[str, int | str]:
    """Return row, age, and storage capacity signals without exposing payloads."""
    with conn.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM notification_outbox GROUP BY status")
        counts = dict(cur.fetchall())
        cur.execute(
            """
            SELECT COUNT(*)::bigint,
                   COUNT(*) FILTER (
                       WHERE status IN ('pending', 'processing', 'retryable', 'dead_letter')
                   )::bigint,
                   COALESCE(EXTRACT(EPOCH FROM NOW() - MIN(created_at) FILTER (
                       WHERE status IN ('pending', 'processing', 'retryable', 'dead_letter')
                   ))::bigint, 0),
                   pg_total_relation_size('notification_outbox'::regclass)
                     + pg_total_relation_size('notification_outbox_attempt'::regclass)
                     + pg_total_relation_size('notification_outbox_operator_audit'::regclass)
            FROM notification_outbox
            """
        )
        total_rows, open_rows, oldest_open_seconds, storage_bytes = cur.fetchone()
    warning_bytes, critical_bytes = _storage_thresholds()
    storage_state = (
        "critical" if storage_bytes >= critical_bytes
        else "warning" if storage_bytes >= warning_bytes
        else "ok"
    )
    result: dict[str, int | str] = {status: int(counts.get(status, 0)) for status in (
        "pending", "processing", "retryable", "succeeded", "dead_letter", "resolved", "discarded"
    )}
    result.update({
        "total_rows": int(total_rows),
        "open_rows": int(open_rows),
        "oldest_open_seconds": int(oldest_open_seconds),
        "storage_bytes": int(storage_bytes),
        "storage_warning_bytes": warning_bytes,
        "storage_critical_bytes": critical_bytes,
        "storage_state": storage_state,
    })
    return result


def list_dead_letters(conn, limit: int = 50) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source_event_id, event_type, channel, attempt_count,
                   replay_count, last_error_class, created_at, updated_at
            FROM notification_outbox
            WHERE status = 'dead_letter'
            ORDER BY updated_at DESC, id
            LIMIT %s
            """,
            (limit,),
        )
        names = [item[0] for item in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def _validate_operator(actor: str, reason: str) -> tuple[str, str]:
    if not isinstance(actor, str) or not 1 <= len(actor.strip()) <= 255:
        raise ValueError("operator actor must contain 1 to 255 characters")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise ValueError("operator reason must contain 1 to 2000 characters")
    return actor.strip(), reason.strip()


def replay_dead_letter(conn, outbox_id: str, *, actor: str, reason: str) -> bool:
    actor, reason = _validate_operator(actor, reason)
    try:
        stable_id = str(uuid.UUID(str(outbox_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("outbox_id must be a UUID") from exc
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, attempt_count, replay_count
            FROM notification_outbox WHERE id = %s FOR UPDATE
            """,
            (stable_id,),
        )
        prior = cur.fetchone()
        if prior is None or prior[0] != "dead_letter":
            conn.rollback()
            return False
        cur.execute(
            """
            UPDATE notification_outbox
            SET status = 'retryable', retry_cycle_attempts = 0,
                replay_count = replay_count + 1,
                available_at = NOW(), last_error_class = NULL, updated_at = NOW()
            WHERE id = %s AND status = 'dead_letter'
            RETURNING replay_count
            """,
            (stable_id,),
        )
        replay_count = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO notification_outbox_operator_audit
                (outbox_id, action, actor, reason, prior_status, prior_attempt_count, replay_count)
            VALUES (%s, 'replayed', %s, %s, %s, %s, %s)
            """,
            (stable_id, actor, reason, prior[0], prior[1], replay_count),
        )
    conn.commit()
    return True


def dispose_dead_letter(
    conn,
    outbox_id: str,
    *,
    disposition: str,
    actor: str,
    reason: str,
) -> bool:
    if disposition not in {"resolved", "discarded"}:
        raise ValueError("disposition must be resolved or discarded")
    actor, reason = _validate_operator(actor, reason)
    try:
        stable_id = str(uuid.UUID(str(outbox_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("outbox_id must be a UUID") from exc
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, attempt_count, replay_count
            FROM notification_outbox WHERE id = %s FOR UPDATE
            """,
            (stable_id,),
        )
        prior = cur.fetchone()
        if prior is None or prior[0] != "dead_letter":
            conn.rollback()
            return False
        cur.execute(
            """
            UPDATE notification_outbox
            SET status = %s, lease_owner = NULL, lease_token = NULL,
                lease_expires_at = NULL, updated_at = NOW()
            WHERE id = %s AND status = 'dead_letter'
            """,
            (disposition, stable_id),
        )
        cur.execute(
            """
            INSERT INTO notification_outbox_operator_audit
                (outbox_id, action, actor, reason, prior_status, prior_attempt_count, replay_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (stable_id, disposition, actor, reason, prior[0], prior[1], prior[2]),
        )
    conn.commit()
    return True
