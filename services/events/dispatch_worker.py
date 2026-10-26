"""Isolated global EventBus dispatcher backed by bounded PostgreSQL functions."""

from __future__ import annotations

import json
import re
from typing import Any

from services.common.worker_database import get_worker_db
from services.common.worker_environment import isolated_worker_key
from services.core.features import require_feature
from services.events.bus import EventBus


def _validate(worker_id: str, batch_size: int, lease_seconds: int) -> None:
    if not isinstance(worker_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", worker_id
    ):
        raise ValueError("event worker ID has an invalid format")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 100:
        raise ValueError("event worker batch size must be between 1 and 100")
    if (isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int)
            or not 30 <= lease_seconds <= 3600):
        raise ValueError("event worker lease must be between 30 and 3600 seconds")


class IsolatedEventBus(EventBus):
    """EventBus process implementation that uses only migration 648 functions."""

    def _function(self, query: str, parameters: tuple[Any, ...], *, commit: bool = True):
        connection = self._get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                result = cursor.fetchall() if cursor.description and len(cursor.description) > 1 else cursor.fetchone()
            if commit:
                connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise

    def _claim(self, batch_size: int, worker_id: str):
        return self._function(
            "SELECT * FROM kokonut_security.claim_platform_event_batch(%s, %s, %s)",
            (worker_id, batch_size, self.lease_seconds),
        )

    def process_pending(self, batch_size: int = 100, worker_id: str = "default") -> dict[str, int]:
        stats = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}
        connection = self._get_conn()
        try:
            events = self._claim(batch_size, worker_id)
            for event_id, event_type, payload, retry_count, max_retries, lease_token in events:
                payload = json.loads(payload) if isinstance(payload, str) else payload
                outcome = self._process_event(
                    event_id, event_type, payload, worker_id, lease_token
                )
                if outcome == "success":
                    stats["processed"] += 1
                elif outcome == "skipped":
                    stats["skipped"] += 1
                elif outcome == "lease_lost":
                    stats["lease_lost"] += 1
                else:
                    retry_status = self._retry_or_dead_letter(
                        event_id, retry_count + 1, max_retries, worker_id, lease_token
                    )
                    if retry_status == "lease_lost":
                        stats["lease_lost"] += 1
                    else:
                        stats["failed"] += 1
            return stats
        except Exception:
            connection.rollback()
            raise

    def _process_event(self, event_id, event_type, payload, worker_id, lease_token):
        handlers = self._function(
            "SELECT * FROM kokonut_security.list_platform_event_handlers(%s, %s, %s, %s)",
            (event_id, event_type, worker_id, lease_token),
        )
        if not handlers:
            return "skipped" if self._complete(event_id, worker_id, lease_token) else "lease_lost"

        failed = False
        for handler_id, module_path, function_name, timeout_seconds, status in handlers:
            if status == "success":
                continue
            extension = min(max(self.lease_seconds, int(timeout_seconds) + 30), 3600)
            renewed = self._function(
                "SELECT kokonut_security.renew_platform_event_lease(%s, %s, %s, %s)",
                (event_id, worker_id, lease_token, extension),
            )
            if not renewed or not renewed[0]:
                return "lease_lost"

            started = self._function(
                "SELECT kokonut_security.begin_platform_event_handler(%s, %s, %s, %s)",
                (event_id, handler_id, worker_id, lease_token),
            )
            if not started or not started[0]:
                return "lease_lost"

            from datetime import datetime, timezone

            started_at = datetime.now(timezone.utc)
            delivery_status, error = self._invoke_handler(
                module_path,
                function_name,
                event_type,
                payload,
                int(timeout_seconds),
                event_id=str(event_id),
            )
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            finished = self._function(
                "SELECT kokonut_security.finish_platform_event_handler(%s, %s, %s, %s, %s, %s, %s)",
                (
                    event_id, handler_id, worker_id, lease_token,
                    delivery_status, duration_ms, error,
                ),
            )
            if not finished or not finished[0]:
                return "lease_lost"
            if delivery_status != "success":
                failed = True

        if failed:
            return "failed"
        return "success" if self._complete(event_id, worker_id, lease_token) else "lease_lost"

    def _complete(self, event_id, worker_id, lease_token):
        completed = self._function(
            "SELECT kokonut_security.complete_platform_event(%s, %s, %s)",
            (event_id, worker_id, lease_token),
        )
        return bool(completed and completed[0])

    def _retry_or_dead_letter(self, event_id, retry_count, max_retries, worker_id, lease_token):
        result = self._function(
            "SELECT kokonut_security.retry_platform_event(%s, %s, %s, %s, %s)",
            (event_id, worker_id, lease_token, retry_count, max_retries),
        )
        return result[0] if result else "lease_lost"


def run_once(
    worker_id: str = "event-kernel-worker",
    batch_size: int = 100,
    lease_seconds: int = 300,
) -> dict[str, int]:
    """Process one bounded batch using the isolated event-dispatch identity."""
    _validate(worker_id, batch_size, lease_seconds)
    require_feature("event_bus")
    require_feature("isolated_event_dispatch")
    if isolated_worker_key() != "event_dispatch":
        raise RuntimeError("isolated event-dispatch worker identity was not established")

    connection = get_worker_db("event_dispatch")
    try:
        bus = IsolatedEventBus(conn=connection, lease_seconds=lease_seconds, connect_timeout=5)
        return bus.process_pending(batch_size, worker_id)
    finally:
        connection.close()
