"""Event bus for reactive workflows.

Publishes and processes platform events, enabling decoupled
pub-sub communication between services.

Usage:
    from services.events.bus import EventBus

    bus = EventBus()
    bus.publish("sensor_reading", payload={"device_id": "abc", "value": 25.3})
    bus.process_pending(batch_size=100)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("events.bus")


class EventBus:
    """Publish-subscribe event bus backed by PostgreSQL."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        source_table: str | None = None,
        source_id: str | None = None,
        priority: str = "normal",
        max_retries: int = 3,
        metadata: dict | None = None,
    ) -> str:
        """Publish an event to the bus. Returns the event ID."""
        event_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform_event
                        (id, event_type, source_table, source_id, payload,
                         priority, status, max_retries, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                    """,
                    (
                        event_id,
                        event_type,
                        source_table,
                        source_id,
                        json.dumps(payload),
                        priority,
                        max_retries,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
            conn.commit()
            logger.info("Published event %s type=%s priority=%s", event_id[:8], event_type, priority)
            return event_id
        except Exception:
            conn.rollback()
            logger.exception("Failed to publish event type=%s", event_type)
            raise

    def process_pending(
        self,
        batch_size: int = 100,
        worker_id: str = "default",
    ) -> dict[str, int]:
        """Process pending events. Returns counts by status."""
        conn = self._get_conn()
        stats = {"processed": 0, "failed": 0, "skipped": 0}

        try:
            with conn.cursor() as cur:
                # Fetch pending events ordered by priority
                cur.execute(
                    """
                    SELECT id, event_type, payload, retry_count, max_retries
                    FROM platform_event
                    WHERE status = 'pending'
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 0
                            WHEN 'high' THEN 1
                            WHEN 'normal' THEN 2
                            WHEN 'low' THEN 3
                        END,
                        created_at
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (batch_size,),
                )
                events = cur.fetchall()

                if not events:
                    return stats

                for event_id, event_type, payload, retry_count, max_retries in events:
                    # Mark as processing
                    cur.execute(
                        """
                        UPDATE platform_event
                        SET status = 'processing', worker_id = %s
                        WHERE id = %s
                        """,
                        (worker_id, event_id),
                    )

                    # Find and execute handlers
                    cur.execute(
                        """
                        SELECT id, module_path, function_name, timeout_seconds
                        FROM event_handler
                        WHERE event_type = %s AND is_enabled = TRUE
                        ORDER BY priority_order
                        """,
                        (event_type,),
                    )
                    handlers = cur.fetchall()

                    if not handlers:
                        # No handlers — mark completed
                        cur.execute(
                            """
                            UPDATE platform_event
                            SET status = 'completed', processed_at = NOW()
                            WHERE id = %s
                            """,
                            (event_id,),
                        )
                        stats["skipped"] += 1
                        continue

                    all_succeeded = True
                    for handler_id, module_path, function_name, timeout_sec in handlers:
                        handler_start = datetime.now(timezone.utc)
                        try:
                            self._invoke_handler(
                                module_path, function_name, event_type, payload
                            )
                            duration_ms = int(
                                (datetime.now(timezone.utc) - handler_start).total_seconds() * 1000
                            )
                            cur.execute(
                                """
                                INSERT INTO event_handler_log
                                    (event_id, handler_id, status, duration_ms)
                                VALUES (%s, %s, 'success', %s)
                                """,
                                (event_id, handler_id, duration_ms),
                            )
                        except Exception as exc:
                            duration_ms = int(
                                (datetime.now(timezone.utc) - handler_start).total_seconds() * 1000
                            )
                            cur.execute(
                                """
                                INSERT INTO event_handler_log
                                    (event_id, handler_id, status, duration_ms, error_message)
                                VALUES (%s, %s, 'error', %s, %s)
                                """,
                                (event_id, handler_id, duration_ms, str(exc)[:500]),
                            )
                            all_succeeded = False
                            logger.warning(
                                "Handler %s failed for event %s: %s",
                                module_path, event_id[:8], exc,
                            )

                    if all_succeeded:
                        cur.execute(
                            """
                            UPDATE platform_event
                            SET status = 'completed', processed_at = NOW()
                            WHERE id = %s
                            """,
                            (event_id,),
                        )
                        stats["processed"] += 1
                    else:
                        new_retry = retry_count + 1
                        if new_retry >= max_retries:
                            # Move to dead letter
                            cur.execute(
                                """
                                UPDATE platform_event
                                SET status = 'dead_letter', retry_count = %s,
                                    error_message = 'Max retries exceeded'
                                WHERE id = %s
                                """,
                                (new_retry, event_id),
                            )
                            cur.execute(
                                """
                                INSERT INTO event_dead_letter
                                    (original_event_id, event_type, payload,
                                     failure_count, last_error)
                                SELECT id, event_type, payload, retry_count, error_message
                                FROM platform_event WHERE id = %s
                                """,
                                (event_id,),
                            )
                        else:
                            cur.execute(
                                """
                                UPDATE platform_event
                                SET status = 'pending', retry_count = %s
                                WHERE id = %s
                                """,
                                (new_retry, event_id),
                            )
                        stats["failed"] += 1

            conn.commit()
            logger.info(
                "Processed batch: %d processed, %d failed, %d skipped",
                stats["processed"], stats["failed"], stats["skipped"],
            )
            return stats

        except Exception:
            conn.rollback()
            logger.exception("Failed to process event batch")
            raise

    def _invoke_handler(
        self, module_path: str, function_name: str, event_type: str, payload: dict
    ) -> Any:
        """Dynamically import and call a handler function."""
        import importlib

        module = importlib.import_module(module_path)
        handler_fn = getattr(module, function_name)
        return handler_fn(event_type, payload)

    def get_stats(self) -> dict[str, int]:
        """Get event bus statistics."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM platform_event
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY status
                    """
                )
                return dict(cur.fetchall())
        finally:
            conn.close()

    def cleanup_old_events(self, days: int = 30) -> int:
        """Delete events older than N days. Returns count deleted."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM platform_event
                    WHERE created_at < NOW() - INTERVAL '%s days'
                    AND status IN ('completed', 'dead_letter')
                    """,
                    (days,),
                )
                count = cur.rowcount
            conn.commit()
            return count
        finally:
            conn.close()
