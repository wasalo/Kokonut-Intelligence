"""Isolated worker for durable notifications and their attempt receipts."""

from __future__ import annotations

import re
from typing import Any

import psycopg2.extras

from services.common.cli import print_json
from services.common.worker_database import get_worker_db
from services.core.features import require_feature
from services.core.worker_progress import pulse_worker_progress
from services.events.notification_outbox import _configured_channels, deliver_claimed_batch

MAX_FUNCTION_BATCH_SIZE = 100
MAX_CLI_BATCH_SIZE = 500


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
            progress_callback=pulse_worker_progress,
        )
    finally:
        connection.close()


def run_batches(
    worker_id: str = "notification-kernel-worker",
    limit: int = 100,
    lease_seconds: int = 300,
) -> dict[str, int]:
    """Deliver up to the CLI's 500-row bound in 100-row function batches."""
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_CLI_BATCH_SIZE
    ):
        raise ValueError(
            f"notification worker batch limit must be between 1 and {MAX_CLI_BATCH_SIZE}"
        )

    totals = {"claimed": 0, "delivered": 0, "failed": 0, "lease_lost": 0}
    remaining = limit
    while remaining:
        requested = min(remaining, MAX_FUNCTION_BATCH_SIZE)
        result = run_once(worker_id, requested, lease_seconds)
        claimed = result.get("claimed")
        if (
            isinstance(claimed, bool)
            or not isinstance(claimed, int)
            or not 0 <= claimed <= requested
        ):
            raise RuntimeError("notification worker returned an invalid claimed count")
        for key in ("delivered", "failed", "lease_lost"):
            value = result.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError("notification worker returned invalid batch statistics")
            totals[key] += value
        if claimed != sum(result[key] for key in ("delivered", "failed", "lease_lost")):
            raise RuntimeError("notification worker returned inconsistent batch statistics")
        totals["claimed"] += claimed
        remaining -= claimed
        if claimed < requested:
            break
    return totals


def main(argv: list[str] | None = None) -> None:
    """Run one batch through the dedicated notification-delivery identity."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Deliver one bounded batch of durable notification intents"
    )
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--worker-id", default="notification-kernel-worker")
    parser.add_argument("--limit", type=int, default=MAX_FUNCTION_BATCH_SIZE)
    parser.add_argument("--lease-seconds", type=int, default=300)
    args = parser.parse_args(argv)

    result = run_once(args.worker_id, args.limit, args.lease_seconds)
    print_json(result)
    if result["failed"] or result["lease_lost"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
