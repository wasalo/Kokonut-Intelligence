"""Durable PostgreSQL-to-ClickHouse delivery.

PostgreSQL producers enqueue rows in their transaction. This module claims,
delivers, retries, and dead-letters those rows without losing the source event.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from services.common.logging import get_logger
from services.ingestion.base import get_clickhouse

logger = get_logger("ingestion.clickhouse_outbox")

MAX_ATTEMPTS = 8
LEASE_SECONDS = 300


def enqueue(
    conn,
    *,
    event_key: str,
    source_table: str,
    source_id: str,
    target_table: str,
    columns: list[str],
    rows: list[list[Any]],
    payload_hash: str,
) -> str:
    """Insert one idempotent delivery record into the caller's transaction."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clickhouse_outbox
                (event_key, source_table, source_id, target_table, columns, rows, payload_hash)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (event_key) DO UPDATE SET updated_at = NOW()
            RETURNING id
            """,
            (
                event_key,
                source_table,
                source_id,
                target_table,
                json.dumps(columns),
                json.dumps(rows, default=str),
                payload_hash,
            ),
        )
        return str(cur.fetchone()[0])


def _recover_expired(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE clickhouse_outbox
            SET status = CASE WHEN attempt_count >= %s THEN 'dead_letter' ELSE 'retryable' END,
                lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
                available_at = NOW(), updated_at = NOW(),
                last_error = COALESCE(last_error, 'delivery lease expired')
            WHERE status = 'processing' AND lease_expires_at < NOW()
            """,
            (MAX_ATTEMPTS,),
        )


def claim_batch(conn, worker_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Claim a bounded batch and commit the lease before network I/O."""
    token = str(uuid.uuid4())
    _recover_expired(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH candidates AS (
                SELECT id FROM clickhouse_outbox
                WHERE status IN ('pending', 'retryable') AND available_at <= NOW()
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED LIMIT %s
            )
            UPDATE clickhouse_outbox o
            SET status = 'processing', attempt_count = attempt_count + 1,
                lease_owner = %s, lease_token = %s, lease_expires_at = %s,
                updated_at = NOW()
            FROM candidates c WHERE o.id = c.id
            RETURNING o.*
            """,
            (limit, worker_id, token, datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)),
        )
        rows = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
    conn.commit()
    return rows


def _finish(conn, row_id: str, worker_id: str, lease_token: str, *, success: bool, error: str | None = None) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE clickhouse_outbox
            SET status = CASE WHEN %s THEN 'succeeded'
                              WHEN attempt_count >= %s THEN 'dead_letter'
                              ELSE 'retryable' END,
                available_at = CASE WHEN %s THEN available_at ELSE NOW() + INTERVAL '1 minute' END,
                delivered_at = CASE WHEN %s THEN NOW() ELSE delivered_at END,
                last_error = %s, lease_owner = NULL, lease_token = NULL,
                lease_expires_at = NULL, updated_at = NOW()
            WHERE id = %s AND status = 'processing'
              AND lease_owner = %s AND lease_token = %s
            """,
            (success, MAX_ATTEMPTS, success, success, error, row_id, worker_id, lease_token),
        )
        changed = cur.rowcount == 1
    conn.commit()
    return changed


def deliver_batch(conn, worker_id: str, limit: int = 100) -> dict[str, int]:
    """Deliver one claimed batch; each row has independent failure handling."""
    rows = claim_batch(conn, worker_id, limit)
    if not rows:
        return {"claimed": 0, "delivered": 0, "failed": 0}
    delivered = failed = 0
    client = None
    try:
        client = get_clickhouse()
        if client is None:
            raise RuntimeError("ClickHouse client unavailable")
        for row in rows:
            try:
                client.insert(
                    row["target_table"],
                    row["rows"],
                    column_names=row["columns"],
                )
                ok = _finish(conn, str(row["id"]), worker_id, str(row["lease_token"]), success=True)
                delivered += int(ok)
            except Exception as exc:
                logger.warning("ClickHouse outbox delivery failed for %s: %s", row["event_key"], exc)
                _finish(conn, str(row["id"]), worker_id, str(row["lease_token"]), success=False, error=str(exc))
                failed += 1
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()
    return {"claimed": len(rows), "delivered": delivered, "failed": failed}


def reconcile_pending(conn, limit: int = 1000) -> dict[str, int]:
    """Return durable delivery gaps that can be repaired by the normal worker."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE status IN ('pending', 'retryable')),
                   COUNT(*) FILTER (WHERE status = 'dead_letter'),
                   COUNT(*) FILTER (WHERE status = 'succeeded')
            FROM clickhouse_outbox
            """
        )
        pending, dead, succeeded = cur.fetchone()
    return {"pending": pending or 0, "dead_letter": dead or 0, "succeeded": succeeded or 0, "limit": limit}


if __name__ == "__main__":
    import argparse
    import json

    from services.ingestion.base import get_db

    parser = argparse.ArgumentParser(description="Deliver PostgreSQL-to-ClickHouse outbox rows")
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--worker-id", default=f"clickhouse-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    conn = get_db()
    try:
        if args.reconcile:
            result = reconcile_pending(conn, args.limit)
        elif args.run_once:
            result = deliver_batch(conn, args.worker_id, args.limit)
        else:
            parser.print_help()
            result = {}
        print(json.dumps(result, indent=2, default=str))
    finally:
        conn.close()
