#!/usr/bin/env python3
"""Exercise a worker crash after a synthetic handler effect commits."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid5

from services.common.database import get_db

EXPECTED_PROJECT = "kokonut-kernel-recovery-handler-b2-20261011"
NAMESPACE = UUID("bd76196b-7f36-481a-8c4f-319cfc7f8ec4")
HANDLER_NAME = "crisp_cache_invalidator"
EVENT_TYPE = "crisp_scored"
HANDLER_MODULE = "services.cache.events"
HANDLER_FUNCTION = "handle_crisp_scored"
TARGET_WORKER = "kernel-b2-crash-after-effect"
RECOVERY_WORKER = "kernel-b2-crash-recovery"
CACHE_TYPE = "crisp"
INVALIDATION_REASON = "crisp_scored:crisp_scored"


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
            SELECT id, timeout_seconds FROM event_handler
            WHERE handler_name = %s AND event_type = %s
              AND module_path = %s AND function_name = %s AND is_enabled = TRUE
            """,
            (HANDLER_NAME, EVENT_TYPE, HANDLER_MODULE, HANDLER_FUNCTION),
        )
        handler = cur.fetchone()
        if not handler:
            raise RuntimeError("Expected enabled synthetic CRISP handler is absent")
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
                    f"kernel-crash-after-effect:{run_id}:{label}",
                    CACHE_TYPE,
                    str(location),
                    parameters,
                    result,
                    f"kernel-crash-{label}",
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
            (str(event_id), EVENT_TYPE, payload, metadata),
        )
    conn.commit()
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_id": str(event_id),
        "handler_id": str(handler[0]),
        "handler_timeout_seconds": handler[1],
        "handler": f"{HANDLER_MODULE}.{HANDLER_FUNCTION}",
        "event_type": EVENT_TYPE,
        "target_location_id": str(target_location),
        "sentinel_location_id": str(sentinel_location),
        "cache_rows": 2,
        "expected_crash_worker": TARGET_WORKER,
        "expected_recovery_worker": RECOVERY_WORKER,
        "scope": "One synthetic event and two synthetic CRISP cache rows; no farm/domain records or external integrations.",
    }


def read_state(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event.event_type, event.status, event.worker_id, event.lease_owner,
                   event.retry_count, event.lease_expires_at,
                   delivery.status, delivery.attempt_count
            FROM platform_event event
            LEFT JOIN event_handler_delivery delivery ON delivery.event_id = event.id
            WHERE event.id = %s AND event.metadata->>'kernel_recovery_probe' = %s
            """,
            (str(event_id), run_id),
        )
        event = cur.fetchone()
        if event is None:
            raise RuntimeError("Synthetic event is absent")
        cur.execute(
            """
            SELECT location_id::text, count(*), count(*) FILTER (WHERE is_valid),
                   count(*) FILTER (WHERE NOT is_valid),
                   count(*) FILTER (WHERE invalidation_reason = %s)
            FROM cache_entry
            WHERE metadata->>'kernel_recovery_probe' = %s
            GROUP BY location_id ORDER BY location_id
            """,
            (INVALIDATION_REASON, run_id),
        )
        cache_groups = cur.fetchall()
        cur.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE status = 'success')
            FROM event_handler_log WHERE event_id = %s
            """,
            (str(event_id),),
        )
        log_counts = cur.fetchone()

    return {
        "run_id": run_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "event_type": event[0],
        "event_status": event[1],
        "worker_id": event[2],
        "lease_owner": event[3],
        "retry_count": event[4],
        "lease_expires_at": event[5].isoformat() if event[5] else None,
        "delivery_status": event[6],
        "delivery_attempt_count": event[7],
        "handler_log_count": log_counts[0],
        "successful_handler_log_count": log_counts[1],
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
        "expected_target_cache_invalidated": str(target_location),
        "expected_sentinel_cache_preserved": str(sentinel_location),
    }


def observe(conn, run_id: str) -> dict:
    return read_state(conn, run_id)


def crash_worker(conn, run_id: str) -> dict:
    event_id, _, _ = identifiers(run_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_type, status, metadata->>'kernel_recovery_probe'
            FROM platform_event WHERE id = %s
            """,
            (str(event_id),),
        )
        event = cur.fetchone()
        cur.execute(
            """
            SELECT count(*) FROM platform_event
            WHERE status = 'pending'
               OR (status = 'processing' AND lease_expires_at < NOW())
            """
        )
        claimable_count = cur.fetchone()[0]
    if event != (EVENT_TYPE, "pending", run_id) or claimable_count != 1:
        raise RuntimeError("Crash worker guard rejected unexpected claimable event state")
    conn.close()

    from services.events.bus import EventBus

    bus = EventBus(lease_seconds=1)
    invoke_handler = bus._invoke_handler

    def crash_after_committed_effect(module_path, function_name, event_type, payload, timeout_seconds):
        outcome = invoke_handler(
            module_path, function_name, event_type, payload, timeout_seconds
        )
        if (
            module_path == HANDLER_MODULE
            and function_name == HANDLER_FUNCTION
            and event_type == EVENT_TYPE
            and payload.get("kernel_recovery_probe") == run_id
            and outcome[0] == "success"
        ):
            state_conn = connect()
            try:
                state = read_state(state_conn, run_id)
            finally:
                state_conn.close()
            expected = sorted(
                [
                    (state["expected_target_cache_invalidated"], 1, 0, 1, 1),
                    (state["expected_sentinel_cache_preserved"], 1, 1, 0, 0),
                ]
            )
            actual = sorted(
                (
                    row["location_id"], row["total"], row["valid"],
                    row["invalid"], row["expected_reason"],
                )
                for row in state["cache_groups"]
            )
            if (
                state["event_status"] != "processing"
                or state["worker_id"] != TARGET_WORKER
                or state["lease_owner"] != TARGET_WORKER
                or state["delivery_status"] != "processing"
                or state["delivery_attempt_count"] != 1
                or state["handler_log_count"] != 0
                or actual != expected
            ):
                print(json.dumps({"unexpected_state_before_crash": state}), file=sys.stderr, flush=True)
                os._exit(87)
            print(
                json.dumps(
                    {
                        "simulated_process_crash": True,
                        "crash_point": "after_handler_success_and_committed_cache_effect_before_receipt_update",
                        "run_id": run_id,
                        "event_id": str(event_id),
                        "target_cache_invalidated": 1,
                        "sentinel_cache_preserved": 1,
                        "delivery_receipt_still_processing": True,
                        "worker_id": TARGET_WORKER,
                    }
                ),
                flush=True,
            )
            os._exit(86)
        return outcome

    bus._invoke_handler = crash_after_committed_effect
    stats = bus.process_pending(batch_size=1, worker_id=TARGET_WORKER)
    bus.close()
    raise RuntimeError(f"Expected crash point was missed; worker returned {stats}")


def expire_lease(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    state = read_state(conn, run_id)
    expected = sorted(
        [
            (str(target_location), 1, 0, 1, 1),
            (str(sentinel_location), 1, 1, 0, 0),
        ]
    )
    actual = sorted(
        (
            row["location_id"], row["total"], row["valid"],
            row["invalid"], row["expected_reason"],
        )
        for row in state["cache_groups"]
    )
    if (
        state["event_status"] != "processing"
        or state["worker_id"] != TARGET_WORKER
        or state["lease_owner"] != TARGET_WORKER
        or state["delivery_status"] != "processing"
        or state["delivery_attempt_count"] != 1
        or state["handler_log_count"] != 0
        or actual != expected
    ):
        raise RuntimeError("Refusing to expire lease: post-crash synthetic state does not match")
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
            RETURNING event.lease_expires_at
            """,
            (str(event_id), EVENT_TYPE, TARGET_WORKER, TARGET_WORKER, run_id),
        )
        updated = cur.fetchone()
    if updated is None:
        conn.rollback()
        raise RuntimeError("Refusing to expire a lease not owned by the crashed synthetic worker")
    conn.commit()
    return {
        "run_id": run_id,
        "event_id": str(event_id),
        "lease_expired": True,
        "lease_expires_at": updated[0].isoformat(),
        "crash_worker": TARGET_WORKER,
        "delivery_status": "processing",
        "delivery_attempt_count": 1,
        "scope": "Expired only the synthetic crashed worker's event lease; no unrelated rows changed.",
    }


def verify(conn, run_id: str) -> dict:
    event_id, target_location, sentinel_location = identifiers(run_id)
    state = read_state(conn, run_id)
    expected = sorted(
        [
            (str(target_location), 1, 0, 1, 1),
            (str(sentinel_location), 1, 1, 0, 0),
        ]
    )
    actual = sorted(
        (
            row["location_id"], row["total"], row["valid"],
            row["invalid"], row["expected_reason"],
        )
        for row in state["cache_groups"]
    )
    if (
        state["event_type"] != EVENT_TYPE
        or state["event_status"] != "completed"
        or state["worker_id"] != RECOVERY_WORKER
        or state["lease_owner"] is not None
        or state["retry_count"] != 0
        or state["delivery_status"] != "success"
        or state["delivery_attempt_count"] != 2
        or state["handler_log_count"] != 1
        or state["successful_handler_log_count"] != 1
        or actual != expected
    ):
        raise AssertionError(f"Post-crash recovery state mismatch: {state}")
    return {
        "run_id": run_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "event_id": str(event_id),
        "event_completed": True,
        "final_worker_id": RECOVERY_WORKER,
        "retry_count": state["retry_count"],
        "delivery_attempt_count": state["delivery_attempt_count"],
        "successful_handler_logs": state["successful_handler_log_count"],
        "target_cache_rows_invalidated_once": 1,
        "sentinel_cache_rows_preserved": 1,
        "effect_was_committed_before_crash": True,
        "receipt_was_not_committed_before_crash": True,
        "recovery_reinvoked_idempotent_handler": True,
        "scope": "Real PostgreSQL lease recovery and allowlisted cache handler; synthetic-only, no external effects or domain writes.",
        "cache_groups": state["cache_groups"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("prepare", "observe", "crash-worker", "expire-lease", "verify")
    )
    parser.add_argument("--run-id", required=True, type=parse_run_id)
    args = parser.parse_args()
    conn = connect()
    try:
        if args.mode == "prepare":
            output = prepare(conn, args.run_id)
        elif args.mode == "observe":
            output = observe(conn, args.run_id)
        elif args.mode == "crash-worker":
            crash_worker(conn, args.run_id)
            return 2
        elif args.mode == "expire-lease":
            output = expire_lease(conn, args.run_id)
        else:
            output = verify(conn, args.run_id)
        print(json.dumps(output, indent=2))
        return 0
    finally:
        if not conn.closed:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
