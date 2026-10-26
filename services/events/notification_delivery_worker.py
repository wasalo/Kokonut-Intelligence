"""Isolated worker for durable notifications and their attempt receipts."""

from __future__ import annotations

import re
from typing import Any

import psycopg2.extras

from services.common.worker_database import get_worker_db
from services.core.features import require_feature
from services.events.notification_outbox import _configured_channels, deliver_claimed_batch


def _validate(worker_id: str, limit: int, lease_seconds: int) -> None:
    if not isinstance(worker_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,149}", worker_id
    ):
        raise ValueError("notification worker ID has an invalid format")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("notification worker batch limit must be between 1 and 100")
    if (isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int)
            or not 30 <= lease_seconds <= 3600):
        raise ValueError("notification worker lease must be between 30 and 3600 seconds")


def _claim(connection, worker_id: str, limit: int, lease_seconds: int,
           channels: list[str]) -> list[dict[str, Any]]:
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.claim_notification_outbox_batch(
                       %s, %s, %s, %s::text[]
                   )""",
                (worker_id, limit, lease_seconds, channels),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        connection.commit()
        return rows
    except Exception:
        connection.rollback()
        raise


def _finish(connection, worker_id: str, row: dict[str, Any], *, success: bool,
            error_class: str | None) -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.finish_notification_outbox_attempt(
                       %s, %s, %s, %s, %s, %s, %s
                   )""",
                (
                    row["id"], worker_id, row["lease_token"], row["attempt_count"],
                    success, error_class,
                    _retry_delay_seconds(int(row["attempt_count"])),
                ),
            )
            result = cursor.fetchone()
        if result is None or result[0] not in {"succeeded", "failed", "lease_lost"}:
            raise RuntimeError("notification completion function returned an invalid result")
        connection.commit()
        return result[0]
    except Exception:
        connection.rollback()
        raise


def _retry_delay_seconds(attempt_count: int) -> int:
    exponent = min(max(attempt_count - 1, 0), 8)
    return min(3600, 15 * (2 ** exponent))


def run_once(
    worker_id: str = "notification-kernel-worker",
    limit: int = 100,
    lease_seconds: int = 300,
) -> dict[str, int]:
    """Claim and deliver one bounded batch with a dedicated database identity."""
    _validate(worker_id, limit, lease_seconds)
    require_feature("notification_delivery")
    require_feature("isolated_notification_delivery")
    channels = _configured_channels()
    connection = get_worker_db("notification_delivery")
    try:
        rows = _claim(connection, worker_id, limit, lease_seconds, channels)
        return deliver_claimed_batch(
            rows,
            lambda row, **kwargs: _finish(
                connection, worker_id, row, **kwargs
            ),
        )
    finally:
        connection.close()
