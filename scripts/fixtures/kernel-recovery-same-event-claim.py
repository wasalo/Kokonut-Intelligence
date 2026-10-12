#!/usr/bin/env python3
"""Prepare, observe, and verify synthetic same-event recovery checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid5

from services.common.database import get_db

EXPECTED_PROJECT = "kokonut-kernel-recovery-handler-b2-20261011"
EXPECTED_WORKER = "kernel-b2-same-event-a"
RETRY_WORKER = "kernel-b2-same-event-retry"
NAMESPACE = UUID("cbd4b44c-f128-4320-a51b-b81fa938a8de")
HANDLER = {
    "name": "crisp_cache_invalidator",
    "event_type": "crisp_scored",
    "module": "services.cache.events",
    "function": "handle_crisp_scored",
    "cache_type": "crisp",
    "reason": "crisp_scored:crisp_scored",
}


def connect():
    if (
        os.environ.get("KOKONUT_ENV") != "production"
        or os.environ.get("PG_HOST") != "database"
        or os.environ.get("PG_DB") != "kokonut_intelligence"
        or os.environ.get("KOKONUT_RECOVERY_FIXTURE_PROJECT") != EXPECTED_PROJECT
    ):
        raise RuntimeError("Refusing to run outside the private recovery Compose database")
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        database, user = cur.fetchone()
    if database != "kokonut_intelligence" or user != "kokonut":
        conn.close()
        raise RuntimeError("Unexpected recovery database identity")
    return conn


def parse_run_id(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError("run-id must be a UUID") from exc


def identifiers(run_id: str) -> tuple[UUID, UUID, UUID]:
    return (
        uuid5(NAMESPACE, f"event:{run_id}"),
        uuid5(NAMESPACE, f"target:{run_id}"),
        uuid5(NAMESPACE, f"sentinel:{run_id}"),
    )


def prepare(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM event_handler
            WHERE handler_name = %s AND event_type = %s
              AND module_path = %s AND function_name = %s AND is_enabled = TRUE
            """,
            (HANDLER["name"], HANDLER["event_type"], HANDLER["module"], HANDLER["function"]),
        )
        handler = cur.fetchone()
        if not handler:
            raise RuntimeError("Expected enabled CRISP cache handler is absent")
        cur.execute(
            """
            SELECT
              (SELECT count(*) FROM platform_event
               WHERE metadata->>'kernel_recovery_probe' = %s)
              + (SELECT count(*) FROM cache_entry
                 WHERE metadata->>'kernel_recovery_probe' = %s)
            """,
            (run_id, run_id),
        )
        if cur.fetchone()[0] != 0:
            raise RuntimeError("Probe run ID already exists; refusing to reuse synthetic state")
        cur.execute(
            """
            SELECT count(*) FROM platform_event
            WHERE status = 'pending'
               OR (status = 'processing' AND lease_expires_at < NOW())
            """
        )
        if cur.fetchone()[0] != 0:
            raise RuntimeError("Unrelated claimable event exists; refusing to run a global worker")

        for label, location in (("target", target_location), ("sentinel", sentinel_location)):
            parameters = json.dumps({"kernel_recovery_probe": run_id, "role": label})
            result = json.dumps({"synthetic": True, "role": label})
            metadata = json.dumps({"kernel_recovery_probe": run_id})
            cur.execute(
                """
                INSERT INTO cache_entry
                    (cache_key, computation_type, location_id, parameters, result,
                     result_hash, computed_by, expires_at, size_bytes, metadata)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb,
                        %s, 'kernel-recovery-fixture', NOW() + INTERVAL '1 day',
                        %s, %s::jsonb)
                """,
                (
                    f"kernel-same-event:{run_id}:{label}",
                    HANDLER["cache_type"],
                    str(location),
                    parameters,
                    result,
                    f"kernel-same-event-{label}",
                    len(result),
                    metadata,
                ),
            )

        payload = json.dumps(
            {"location_id": str(target_location), "kernel_recovery_probe": run_id}
        )
        metadata = json.dumps({"kernel_recovery_probe": run_id})
        cur.execute(
            """
            INSERT INTO platform_event
                (id, event_type, payload, priority, status, max_retries, metadata)
            VALUES (%s, %s, %s::jsonb, 'normal', 'pending', 2, %s::jsonb)
            """,
            (str(event_id), HANDLER["event_type"], payload, metadata),
        )
    conn.commit()
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_id": str(event_id),
        "handler_id": str(handler[0]),
        "handler": f"{HANDLER['module']}.{HANDLER['function']}",
        "event_type": HANDLER["event_type"],
        "target_location_id": str(target_location),
        "sentinel_location_id": str(sentinel_location),
        "cache_rows": 2,
        "max_retries": 2,
        "expected_first_worker": EXPECTED_WORKER,
        "scope": "One synthetic event and two synthetic CRISP cache rows; no farm/domain records or external integrations.",
    }


def observe(conn, run_id: str) -> dict:
    event_id, _, _ = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event.event_type, event.status, event.worker_id, event.lease_owner,
                   event.retry_count, delivery.status, delivery.attempt_count
            FROM platform_event event
            LEFT JOIN event_handler_delivery delivery ON delivery.event_id = event.id
            WHERE event.id = %s AND event.metadata->>'kernel_recovery_probe' = %s
            """,
            (str(event_id), run_id),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Synthetic event is absent")
    return {
        "run_id": run_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "event_type": row[0],
        "event_status": row[1],
        "worker_id": row[2],
        "lease_owner": row[3],
        "retry_count": row[4],
        "delivery_status": row[5],
        "delivery_attempt_count": row[6],
    }


def expire_lease(conn, run_id: str) -> dict:
    event_id, _, _ = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE platform_event event
            SET lease_expires_at = NOW() - INTERVAL '1 second'
            WHERE event.id = %s AND event.event_type = %s
              AND event.status = 'processing' AND event.worker_id = %s
              AND event.lease_owner = %s AND event.lease_expires_at > NOW()
              AND event.metadata->>'kernel_recovery_probe' = %s
              AND EXISTS (
                  SELECT 1 FROM event_handler_delivery delivery
                  WHERE delivery.event_id = event.id
                    AND delivery.status = 'processing'
                    AND delivery.attempt_count = 1
              )
            RETURNING event.id, event.lease_expires_at
            """,
            (
                str(event_id),
                HANDLER["event_type"],
                EXPECTED_WORKER,
                EXPECTED_WORKER,
                run_id,
            ),
        )
        updated = cur.fetchone()
    if updated is None:
        conn.rollback()
        raise RuntimeError("Refusing to expire a lease that does not match the active synthetic event")
    conn.commit()
    return {
        "run_id": run_id,
        "event_id": str(updated[0]),
        "lease_expired": True,
        "lease_expires_at": updated[1].isoformat(),
        "delivery_attempt_count": 1,
        "scope": "Expired only the active lease of this marked synthetic event; no other rows changed.",
    }


def hold_cache_lock(conn, run_id: str) -> dict:
    """Hold a synthetic cache-table lock until stdin receives `release`."""
    event_id, _, _ = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_type, status, worker_id, lease_owner
            FROM platform_event
            WHERE id = %s AND metadata->>'kernel_recovery_probe' = %s
            """,
            (str(event_id), run_id),
        )
        event = cur.fetchone()
    if event is None or event[0] != HANDLER["event_type"]:
        raise RuntimeError("Refusing to lock cache for a missing or unmarked synthetic event")
    if event[1] not in ("pending", "processing"):
        raise RuntimeError(f"Refusing to lock cache for event in state {event[1]!r}")
    if event[1] == "processing" and (event[2], event[3]) != (EXPECTED_WORKER, EXPECTED_WORKER):
        raise RuntimeError("Refusing to lock cache after ownership moved from the expected first worker")
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("LOCK TABLE cache_entry IN SHARE MODE")
    print(json.dumps({"run_id": run_id, "cache_table_lock_acquired": True}), flush=True)
    if sys.stdin.readline().strip() != "release":
        conn.rollback()
        raise RuntimeError("Lock holder closed without the explicit release token")
    conn.commit()
    return {
        "run_id": run_id,
        "cache_table_lock_acquired": True,
        "cache_table_lock_released": True,
        "scope": "Held only a SHARE lock on cache_entry for this isolated synthetic retry probe.",
    }


def verify(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE event_type = %s),
                   count(*) FILTER (WHERE status = 'completed'),
                   count(*) FILTER (WHERE lease_owner IS NULL),
                   count(*) FILTER (WHERE worker_id = %s),
                   min(retry_count), max(retry_count)
            FROM platform_event
            WHERE id = %s AND metadata->>'kernel_recovery_probe' = %s
            """,
            (HANDLER["event_type"], EXPECTED_WORKER, str(event_id), run_id),
        )
        event_counts = cur.fetchone()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'success'),
                   min(attempt_count), max(attempt_count)
            FROM event_handler_delivery WHERE event_id = %s
            """,
            (str(event_id),),
        )
        delivery_counts = cur.fetchone()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'success')
            FROM event_handler_log WHERE event_id = %s
            """,
            (str(event_id),),
        )
        log_counts = cur.fetchone()
        cur.execute(
            """
            SELECT location_id::text, count(*), count(*) FILTER (WHERE is_valid),
                   count(*) FILTER (WHERE NOT is_valid),
                   count(*) FILTER (WHERE invalidation_reason = %s)
            FROM cache_entry
            WHERE metadata->>'kernel_recovery_probe' = %s
            GROUP BY location_id ORDER BY location_id
            """,
            (HANDLER["reason"], run_id),
        )
        cache_groups = cur.fetchall()

    if event_counts != (1, 1, 1, 1, 1, 0, 0):
        raise AssertionError(f"Unexpected event state: {event_counts}")
    if delivery_counts != (1, 1, 1, 1):
        raise AssertionError(f"Unexpected handler delivery state: {delivery_counts}")
    if log_counts != (1, 1):
        raise AssertionError(f"Unexpected handler log state: {log_counts}")
    expected_cache = sorted(
        [
            (str(target_location), 1, 0, 1, 1),
            (str(sentinel_location), 1, 1, 0, 0),
        ]
    )
    if sorted(cache_groups) != expected_cache:
        raise AssertionError(f"Cache effect/scope mismatch: {cache_groups}")
    return {
        "run_id": run_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "event_id": str(event_id),
        "event_completed": 1,
        "worker_id": EXPECTED_WORKER,
        "retry_count": 0,
        "successful_delivery_receipts": 1,
        "delivery_attempt_count": 1,
        "successful_handler_logs": 1,
        "target_cache_rows_invalidated": 1,
        "sentinel_cache_rows_preserved": 1,
        "cache_groups": [
            {
                "location_id": row[0],
                "total": row[1],
                "valid": row[2],
                "invalid": row[3],
                "expected_reason": row[4],
            }
            for row in cache_groups
        ],
        "scope": "Real PostgreSQL active-lease exclusion and one allowlisted cache effect; synthetic-only, no external effects or domain writes.",
    }


def verify_reclaim(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE event_type = %s),
                   count(*) FILTER (WHERE status = 'completed'),
                   count(*) FILTER (WHERE lease_owner IS NULL),
                   count(*) FILTER (WHERE worker_id = 'kernel-b2-same-event-b'),
                   min(retry_count), max(retry_count)
            FROM platform_event
            WHERE id = %s AND metadata->>'kernel_recovery_probe' = %s
            """,
            (HANDLER["event_type"], str(event_id), run_id),
        )
        event_counts = cur.fetchone()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'success'),
                   min(attempt_count), max(attempt_count)
            FROM event_handler_delivery WHERE event_id = %s
            """,
            (str(event_id),),
        )
        delivery_counts = cur.fetchone()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'success')
            FROM event_handler_log WHERE event_id = %s
            """,
            (str(event_id),),
        )
        log_counts = cur.fetchone()
        cur.execute(
            """
            SELECT location_id::text, count(*), count(*) FILTER (WHERE is_valid),
                   count(*) FILTER (WHERE NOT is_valid),
                   count(*) FILTER (WHERE invalidation_reason = %s)
            FROM cache_entry
            WHERE metadata->>'kernel_recovery_probe' = %s
            GROUP BY location_id ORDER BY location_id
            """,
            (HANDLER["reason"], run_id),
        )
        cache_groups = cur.fetchall()

    if event_counts != (1, 1, 1, 1, 1, 0, 0):
        raise AssertionError(f"Unexpected reclaimed event state: {event_counts}")
    if delivery_counts != (1, 1, 2, 2):
        raise AssertionError(f"Expected one successful delivery after two attempts: {delivery_counts}")
    if log_counts != (2, 2):
        raise AssertionError(f"Expected two successful handler logs: {log_counts}")
    expected_cache = sorted(
        [
            (str(target_location), 1, 0, 1, 1),
            (str(sentinel_location), 1, 1, 0, 0),
        ]
    )
    if sorted(cache_groups) != expected_cache:
        raise AssertionError(f"Cache effect/scope mismatch: {cache_groups}")
    return {
        "run_id": run_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "event_id": str(event_id),
        "event_completed": 1,
        "final_worker_id": "kernel-b2-same-event-b",
        "event_retry_count": 0,
        "successful_delivery_receipts": 1,
        "delivery_attempt_count": 2,
        "successful_handler_logs": 2,
        "target_cache_rows_invalidated": 1,
        "sentinel_cache_rows_preserved": 1,
        "cache_groups": [
            {
                "location_id": row[0],
                "total": row[1],
                "valid": row[2],
                "invalid": row[3],
                "expected_reason": row[4],
            }
            for row in cache_groups
        ],
        "scope": "Real PostgreSQL expired-lease reclaim and duplicate allowlisted handler invocation; synthetic-only, no external effects or domain writes.",
    }


def verify_timeout_retry(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE event_type = %s),
                   count(*) FILTER (WHERE status = 'completed'),
                   count(*) FILTER (WHERE lease_owner IS NULL),
                   count(*) FILTER (WHERE worker_id = %s),
                   min(retry_count), max(retry_count)
            FROM platform_event
            WHERE id = %s AND metadata->>'kernel_recovery_probe' = %s
            """,
            (HANDLER["event_type"], RETRY_WORKER, str(event_id), run_id),
        )
        event_counts = cur.fetchone()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'success'),
                   min(attempt_count), max(attempt_count)
            FROM event_handler_delivery WHERE event_id = %s
            """,
            (str(event_id),),
        )
        delivery_counts = cur.fetchone()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'timeout'),
                   count(*) FILTER (WHERE status = 'success')
            FROM event_handler_log WHERE event_id = %s
            """,
            (str(event_id),),
        )
        log_counts = cur.fetchone()
        cur.execute(
            """
            SELECT location_id::text, count(*), count(*) FILTER (WHERE is_valid),
                   count(*) FILTER (WHERE NOT is_valid),
                   count(*) FILTER (WHERE invalidation_reason = %s)
            FROM cache_entry
            WHERE metadata->>'kernel_recovery_probe' = %s
            GROUP BY location_id ORDER BY location_id
            """,
            (HANDLER["reason"], run_id),
        )
        cache_groups = cur.fetchall()

    if event_counts != (1, 1, 1, 1, 1, 1, 1):
        raise AssertionError(f"Unexpected event state after timeout retry: {event_counts}")
    if delivery_counts != (1, 1, 2, 2):
        raise AssertionError(f"Expected one successful delivery after two attempts: {delivery_counts}")
    if log_counts != (2, 1, 1):
        raise AssertionError(f"Expected one timeout and one successful handler log: {log_counts}")
    expected_cache = sorted(
        [
            (str(target_location), 1, 0, 1, 1),
            (str(sentinel_location), 1, 1, 0, 0),
        ]
    )
    if sorted(cache_groups) != expected_cache:
        raise AssertionError(f"Cache effect/scope mismatch: {cache_groups}")
    return {
        "run_id": run_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "event_id": str(event_id),
        "event_completed": 1,
        "initial_worker_id": EXPECTED_WORKER,
        "final_worker_id": RETRY_WORKER,
        "event_retry_count": 1,
        "successful_delivery_receipts": 1,
        "delivery_attempt_count": 2,
        "handler_logs": {"total": 2, "timeout": 1, "success": 1},
        "target_cache_rows_invalidated": 1,
        "sentinel_cache_rows_preserved": 1,
        "cache_groups": [
            {
                "location_id": row[0],
                "total": row[1],
                "valid": row[2],
                "invalid": row[3],
                "expected_reason": row[4],
            }
            for row in cache_groups
        ],
        "scope": "Real PostgreSQL handler timeout followed by durable retry and successful allowlisted cache effect; synthetic-only, no external effects or domain writes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=(
            "prepare",
            "observe",
            "hold-cache-lock",
            "expire-lease",
            "verify",
            "verify-reclaim",
            "verify-timeout-retry",
        ),
    )
    parser.add_argument("--run-id", required=True, type=parse_run_id)
    args = parser.parse_args()
    conn = connect()
    try:
        if args.mode == "prepare":
            output = prepare(conn, args.run_id)
        elif args.mode == "observe":
            output = observe(conn, args.run_id)
        elif args.mode == "hold-cache-lock":
            output = hold_cache_lock(conn, args.run_id)
        elif args.mode == "expire-lease":
            output = expire_lease(conn, args.run_id)
        elif args.mode == "verify-reclaim":
            output = verify_reclaim(conn, args.run_id)
        elif args.mode == "verify-timeout-retry":
            output = verify_timeout_retry(conn, args.run_id)
        else:
            output = verify(conn, args.run_id)
        print(json.dumps(output, sort_keys=True))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"same-event recovery probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
