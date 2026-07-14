"""Durable PostgreSQL-backed event bus."""

from __future__ import annotations

import importlib
import json
import multiprocessing
import uuid
from datetime import datetime, timezone
from queue import Empty
from typing import Any

from services.common.logging import get_logger

logger = get_logger("events.bus")


def _handler_process(result_queue, module_path, function_name, event_type, payload):
    """Invoke a handler in an isolated process so its deadline is enforceable."""
    try:
        handler = getattr(importlib.import_module(module_path), function_name)
        handler(event_type, payload)
        result_queue.put((True, None))
    except BaseException as exc:  # Child must report all handler failures.
        result_queue.put((False, f"{type(exc).__name__}: {exc}"))


class EventBus:
    """Publish and deliver events with leases and per-handler idempotency."""

    def __init__(self, conn=None, lease_seconds: int = 300):
        self._conn = conn
        self._owns_conn = conn is None
        self.lease_seconds = lease_seconds

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def close(self):
        if self._owns_conn and self._conn is not None:
            self._conn.close()
            self._conn = None

    def publish(self, event_type: str, payload: dict[str, Any], *, source_table=None,
                source_id=None, priority="normal", max_retries=3, metadata=None) -> str:
        event_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform_event
                        (id, event_type, source_table, source_id, payload, priority,
                         status, max_retries, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                """, (event_id, event_type, source_table, source_id, json.dumps(payload),
                      priority, max_retries, json.dumps(metadata) if metadata else None))
            conn.commit()
            return event_id
        except Exception:
            conn.rollback()
            raise

    def _claim(self, batch_size: int, worker_id: str):
        """Atomically claim eligible events; caller commits before any handler runs."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                WITH claimable AS (
                    SELECT id FROM platform_event
                    WHERE status = 'pending'
                       OR (status = 'processing' AND lease_expires_at < NOW())
                    ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                             WHEN 'normal' THEN 2 ELSE 3 END, created_at
                    LIMIT %s FOR UPDATE SKIP LOCKED
                )
                UPDATE platform_event e
                SET status = 'processing', claimed_at = NOW(), worker_id = %s,
                    lease_owner = %s,
                    lease_expires_at = NOW() + (%s * INTERVAL '1 second')
                FROM claimable c WHERE e.id = c.id
                RETURNING e.id, e.event_type, e.payload, e.retry_count, e.max_retries
            """, (batch_size, worker_id, worker_id, self.lease_seconds))
            events = cur.fetchall()
        conn.commit()
        return events

    def process_pending(self, batch_size: int = 100, worker_id: str = "default") -> dict[str, int]:
        stats = {"processed": 0, "failed": 0, "skipped": 0}
        conn = self._get_conn()
        try:
            events = self._claim(batch_size, worker_id)
            for event_id, event_type, payload, retry_count, max_retries in events:
                payload = json.loads(payload) if isinstance(payload, str) else payload
                outcome = self._process_event(event_id, event_type, payload, worker_id)
                if outcome == "success":
                    stats["processed"] += 1
                elif outcome == "skipped":
                    stats["skipped"] += 1
                else:
                    self._retry_or_dead_letter(
                        event_id, retry_count + 1, max_retries, worker_id
                    )
                    stats["failed"] += 1
            return stats
        except Exception:
            conn.rollback()
            logger.exception("Failed to process event batch")
            raise

    def _process_event(self, event_id, event_type, payload, worker_id):
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT h.id, h.module_path, h.function_name, h.timeout_seconds,
                       d.status
                FROM event_handler h
                LEFT JOIN event_handler_delivery d
                  ON d.event_id = %s AND d.handler_id = h.id
                WHERE h.event_type = %s AND h.is_enabled = TRUE
                ORDER BY h.priority_order
            """, (event_id, event_type))
            handlers = cur.fetchall()
        conn.commit()
        if not handlers:
            return "skipped" if self._complete(event_id, worker_id) else "lease_lost"

        failed = False
        for handler_id, module_path, function_name, timeout_seconds, status in handlers:
            if status == "success":
                continue
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform_event
                    SET lease_expires_at = NOW() + (%s * INTERVAL '1 second')
                    WHERE id = %s AND status = 'processing' AND lease_owner = %s
                    RETURNING id
                """, (max(self.lease_seconds, timeout_seconds + 30), event_id, worker_id))
                still_owned = cur.fetchone()
            conn.commit()
            if not still_owned:
                logger.warning("Lease lost before handler delivery for event %s", event_id)
                return "lease_lost"
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO event_handler_delivery
                        (event_id, handler_id, status, attempt_count, started_at, updated_at)
                    VALUES (%s, %s, 'processing', 1, NOW(), NOW())
                    ON CONFLICT (event_id, handler_id) DO UPDATE
                    SET status = 'processing', attempt_count = event_handler_delivery.attempt_count + 1,
                        started_at = NOW(), updated_at = NOW(), last_error = NULL
                """, (event_id, handler_id))
            conn.commit()
            started = datetime.now(timezone.utc)
            delivery_status, error = self._invoke_handler(
                module_path, function_name, event_type, payload, timeout_seconds
            )
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE event_handler_delivery
                    SET status = %s, completed_at = NOW(), last_error = %s, updated_at = NOW()
                    WHERE event_id = %s AND handler_id = %s
                """, (delivery_status, error, event_id, handler_id))
                cur.execute("""
                    INSERT INTO event_handler_log
                        (event_id, handler_id, status, duration_ms, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                """, (event_id, handler_id, delivery_status, duration_ms, error))
            conn.commit()
            if delivery_status != "success":
                failed = True
        if failed:
            return "failed"
        return "success" if self._complete(event_id, worker_id) else "lease_lost"

    def _invoke_handler(self, module_path, function_name, event_type, payload, timeout_seconds):
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue(maxsize=1)
        process = ctx.Process(target=_handler_process, args=(
            result_queue, module_path, function_name, event_type, payload
        ))
        process.start()
        process.join(timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join()
            return "timeout", f"Handler exceeded {timeout_seconds}s timeout"
        try:
            succeeded, error = result_queue.get(timeout=1)
        except Empty:
            return "error", f"Handler process exited with code {process.exitcode}"
        return ("success", None) if succeeded else ("error", error[:500])

    def _complete(self, event_id, worker_id):
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE platform_event SET status = 'completed', processed_at = NOW(),
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE id = %s AND status = 'processing' AND lease_owner = %s
                RETURNING id
            """, (event_id, worker_id))
            completed = cur.fetchone() is not None
        conn.commit()
        return completed

    def _retry_or_dead_letter(self, event_id, retry_count, max_retries, worker_id):
        conn = self._get_conn()
        dead = retry_count >= max_retries
        error = "Max retries exceeded" if dead else "One or more handlers failed"
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE platform_event SET status = %s, retry_count = %s,
                    error_message = %s, lease_owner = NULL, lease_expires_at = NULL
                WHERE id = %s AND lease_owner = %s
                RETURNING id
            """, ("dead_letter" if dead else "pending", retry_count, error,
                  event_id, worker_id))
            changed = cur.fetchone()
            if dead and changed:
                cur.execute("""
                    INSERT INTO event_dead_letter
                        (original_event_id, event_type, payload, failure_count, last_error)
                    SELECT id, event_type, payload, retry_count, error_message
                    FROM platform_event WHERE id = %s
                    ON CONFLICT (original_event_id) WHERE disposition = 'pending'
                    DO UPDATE SET failure_count = EXCLUDED.failure_count,
                                  last_error = EXCLUDED.last_error
                """, (event_id,))
        conn.commit()

    def replay_dead_letter(self, event_id: str, actor: str) -> bool:
        if not actor or not actor.strip():
            raise ValueError("actor is required")
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                WITH replayable AS (
                    SELECT dead.id AS dead_letter_id
                    FROM event_dead_letter dead
                    JOIN platform_event event ON event.id = dead.original_event_id
                    WHERE dead.original_event_id = %s
                      AND dead.disposition = 'pending'
                      AND event.status = 'dead_letter'
                    FOR UPDATE OF dead, event
                ), reset_event AS (
                    UPDATE platform_event event
                    SET status = 'pending', retry_count = 0, error_message = NULL,
                        claimed_at = NULL, lease_owner = NULL, lease_expires_at = NULL
                    FROM replayable
                    WHERE event.id = %s
                    RETURNING replayable.dead_letter_id
                )
                UPDATE event_dead_letter dead
                SET disposition = 'replayed', replayed_at = NOW(),
                    disposed_by = %s, disposed_at = NOW()
                FROM reset_event
                WHERE dead.id = reset_event.dead_letter_id
                RETURNING dead.original_event_id
            """, (event_id, event_id, actor))
            found = cur.fetchone()
        conn.commit()
        return found is not None

    def dispose_dead_letter(self, event_id: str, disposition: str, actor: str, reason: str) -> bool:
        if disposition not in {"resolved", "discarded"}:
            raise ValueError("disposition must be resolved or discarded")
        if not actor or not actor.strip():
            raise ValueError("actor is required")
        if not reason or not reason.strip():
            raise ValueError("reason is required")
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE event_dead_letter SET disposition = %s, disposition_reason = %s,
                    disposed_by = %s, disposed_at = NOW()
                WHERE original_event_id = %s AND disposition = 'pending'
            """, (disposition, reason, actor, event_id))
            changed = cur.rowcount > 0
        conn.commit()
        return changed

    def get_stats(self):
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""SELECT status, COUNT(*) FROM platform_event
                            WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY status""")
            return dict(cur.fetchall())

    def cleanup_old_events(self, days: int = 30):
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""DELETE FROM platform_event
                            WHERE created_at < NOW() - (%s * INTERVAL '1 day')
                              AND status IN ('completed', 'dead_letter')""", (days,))
            count = cur.rowcount
        conn.commit()
        return count
