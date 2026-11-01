"""Durable PostgreSQL-backed event bus."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import uuid
from typing import Any

from services.common.worker_environment import (
    event_handler_worker_policy,
    worker_subprocess_environment,
)
from services.security.execution_allowlist import validate_event_handler


def _validate_lease_seconds(lease_seconds: int) -> None:
    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or not 30 <= lease_seconds <= 3600
    ):
        raise ValueError("event worker lease must be between 30 and 3600 seconds")

def _handler_child_environment(module_path, function_name, environ=None):
    """Copy the environment with only an exact handler's worker identity.

    Handler registrations are database-backed, so worker access must be
    selected from this source-controlled mapping rather than event metadata or
    registration fields.
    """
    allowed_worker_keys, isolated = event_handler_worker_policy(
        module_path,
        function_name,
        environ=environ,
    )
    return worker_subprocess_environment(
        allowed_worker_keys=allowed_worker_keys,
        isolated_database_credentials=bool(allowed_worker_keys),
        strip_shared_database_credentials=isolated,
        environ=environ,
    )


def resolve_handler(module_path: str, function_name: str):
    """Resolve a configured handler and reject non-callable attributes."""
    validate_event_handler(module_path, function_name)
    handler = getattr(importlib.import_module(module_path), function_name, None)
    if not callable(handler):
        raise TypeError(f"Event handler is not callable: {module_path}.{function_name}")
    return handler


class EventBus:
    """Publish and deliver events with leases and per-handler idempotency."""

    def __init__(self, conn=None, lease_seconds: int = 300, connect_timeout: int | None = None):
        _validate_lease_seconds(lease_seconds)
        self._conn = conn
        self._owns_conn = conn is None
        self.lease_seconds = lease_seconds
        self.connect_timeout = connect_timeout

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = (
                get_db() if self.connect_timeout is None else get_db(connect_timeout=self.connect_timeout)
            )
        return self._conn

    def close(self):
        if self._owns_conn and self._conn is not None:
            self._conn.close()
            self._conn = None

    def publish(self, event_type: str, payload: dict[str, Any], *, event_id=None,
                source_table=None, source_id=None, priority="normal", max_retries=3,
                metadata=None, commit: bool = True) -> str:
        """Persist an event, optionally leaving transaction control to the caller."""
        if event_id is None:
            event_id = str(uuid.uuid4())
        else:
            try:
                event_id = str(uuid.UUID(str(event_id)))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("event_id must be a valid UUID") from exc
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
            if commit:
                conn.commit()
            return event_id
        except Exception:
            if commit:
                conn.rollback()
            raise

    def _invoke_handler(
        self, module_path, function_name, event_type, payload, timeout_seconds, *, event_id=None
    ):
        request = {
            "module_path": module_path,
            "function_name": function_name,
            "event_type": event_type,
            "payload": payload,
            "event_id": event_id,
        }
        try:
            request_body = json.dumps(request)
        except (TypeError, ValueError):
            return "error", "Handler request could not be encoded"
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "services.events.handler_runner"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                env=_handler_child_environment(module_path, function_name),
            )
        except OSError as exc:
            return "error", f"Handler process could not start: {type(exc).__name__}"
        try:
            output, _ = process.communicate(request_body, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return "timeout", f"Handler exceeded {timeout_seconds}s timeout"
        if process.returncode != 0:
            return "error", f"Handler process exited with code {process.returncode}"
        try:
            result = json.loads(output)
        except (TypeError, json.JSONDecodeError):
            return "error", "Handler process returned an invalid result"
        if not isinstance(result, dict):
            return "error", "Handler process returned an invalid result"
        if result.get("succeeded") is True:
            return "success", None
        error_class = result.get("error_class")
        if (
            isinstance(error_class, str)
            and error_class.isascii()
            and error_class.isidentifier()
            and len(error_class) <= 64
        ):
            return "error", f"Handler failed ({error_class})"
        return "error", "Handler failed"

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

    def cleanup_old_events(self, actor: str = "cli"):
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor is required for retention audit")
        from services.events.retention import require_event_retention_cleanup

        require_event_retention_cleanup()
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext('kokonut.retention.legal_hold'))"
                )
                cur.execute(
                    """
                    SELECT id, retention_days
                    FROM data_retention_policy
                    WHERE data_category = 'event_bus'
                      AND entity_type = 'platform_event'
                      AND location_id IS NULL
                      AND jurisdiction_code IS NULL
                      AND purpose_code IS NULL
                      AND retention_days > 0
                      AND deletion_method = 'hard_delete'
                      AND legal_hold = FALSE
                      AND auto_enforce = TRUE
                      AND enforcement_status = 'active'
                      AND NULLIF(BTRIM(approved_by), '') IS NOT NULL
                      AND NULLIF(BTRIM(policy_owner), '') IS NOT NULL
                      AND approval_date IS NOT NULL
                      AND status = 'active'
                      AND NOT EXISTS (
                          SELECT 1 FROM data_retention_policy overlap
                          WHERE overlap.id <> data_retention_policy.id
                            AND overlap.data_category = 'event_bus'
                            AND overlap.entity_type = 'platform_event'
                            AND overlap.status = 'active'
                      )
                    FOR SHARE
                    """
                )
                policies = cur.fetchall()
                if len(policies) != 1:
                    raise RuntimeError(
                        "Event cleanup requires exactly one approved, active "
                        "event_bus/platform_event hard-delete policy; no pruning was performed."
                    )
                policy_id, days = policies[0]
                if isinstance(days, bool) or not isinstance(days, int) or days < 1:
                    raise RuntimeError(
                        "The approved event retention policy has no valid window; "
                        "no pruning was performed."
                    )

                cur.execute(
                    """
                    WITH removed AS (
                        DELETE FROM platform_event
                        WHERE created_at < NOW() - make_interval(days => %s)
                          AND status IN ('completed', 'dead_letter')
                          AND NOT EXISTS (
                              SELECT 1 FROM event_dead_letter dead
                              WHERE dead.original_event_id = platform_event.id
                                AND dead.disposition = 'pending'
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM event_handler_delivery delivery
                              WHERE delivery.event_id = platform_event.id
                                AND delivery.status <> 'success'
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM data_retention_legal_hold hold
                              WHERE hold.entity_type = 'platform_event'
                                AND hold.entity_id = platform_event.id
                                AND hold.released_at IS NULL
                          )
                        RETURNING id
                    )
                    SELECT COUNT(*) FROM removed
                    """,
                    (days,),
                )
                count = int(cur.fetchone()[0])
                cur.execute(
                    """
                    INSERT INTO data_retention_enforcement_log
                        (policy_id, actor, dry_run, status, candidates, affected)
                    VALUES (%s, %s, FALSE, 'completed', %s, %s)
                    """,
                    (policy_id, actor.strip(), count, count),
                )
                cur.execute(
                    """
                    UPDATE data_retention_policy
                    SET last_enforced_at = NOW(), updated_at = NOW()
                    WHERE id = %s
                    """,
                    (policy_id,),
                )
            conn.commit()
            return count
        except Exception:
            conn.rollback()
            raise
