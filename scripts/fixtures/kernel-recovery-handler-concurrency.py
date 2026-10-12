#!/usr/bin/env python3
"""Prepare, observe, or verify a synthetic concurrent event-handler recovery run."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

from services.common.database import get_db

EXPECTED_EVENTS = 16
TARGET_CACHE_ENTRIES = 16
SENTINEL_CACHE_ENTRIES = 3
NAMESPACE = UUID("24a8c513-69a8-4e24-a47c-7ad613cd6b13")
EXPECTED_PROJECT = "kokonut-kernel-recovery-handler-b2-20261011"
HANDLERS = {
    "metric": {
        "event_type": "metric_computed",
        "handler_name": "metric_cache_invalidator",
        "module": "services.cache.events",
        "function": "handle_metric_computed",
        "computation_type": "analytics",
        "invalidation_reason": "metric_computed:metric_computed",
    },
    "crisp": {
        "event_type": "crisp_scored",
        "handler_name": "crisp_cache_invalidator",
        "module": "services.cache.events",
        "function": "handle_crisp_scored",
        "computation_type": "crisp",
        "invalidation_reason": "crisp_scored:crisp_scored",
    },
}


def connect():
    if (os.environ.get("KOKONUT_ENV") != "production"
            or os.environ.get("PG_HOST") != "database"
            or os.environ.get("PG_DB") != "kokonut_intelligence"
            or os.environ.get("KOKONUT_RECOVERY_FIXTURE_PROJECT") != EXPECTED_PROJECT):
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


def identities(run_id: str) -> tuple[UUID, UUID]:
    return uuid5(NAMESPACE, f"location:{run_id}"), uuid5(NAMESPACE, f"sentinel:{run_id}")


def prepare(conn, run_id: str, handler_key: str) -> dict:
    spec = HANDLERS[handler_key]
    target_location, sentinel_location = identities(run_id)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM event_handler
            WHERE handler_name = %s AND event_type = %s
              AND module_path = %s AND function_name = %s AND is_enabled = TRUE
        """, (spec["handler_name"], spec["event_type"],
              spec["module"], spec["function"]))
        handler = cur.fetchone()
        if not handler:
            raise RuntimeError(f"Expected enabled {handler_key} cache handler is absent")
        cur.execute("""
            SELECT
              (SELECT count(*) FROM platform_event
               WHERE metadata->>'kernel_recovery_probe' = %s)
              + (SELECT count(*) FROM cache_entry
                 WHERE metadata->>'kernel_recovery_probe' = %s)
        """, (run_id, run_id))
        if cur.fetchone()[0] != 0:
            raise RuntimeError("Probe run ID already exists; refusing to reuse synthetic state")
        cur.execute("""
            SELECT count(*) FROM platform_event
            WHERE status = 'pending'
               OR (status = 'processing' AND lease_expires_at < NOW())
        """)
        if cur.fetchone()[0] != 0:
            raise RuntimeError("Unrelated claimable event exists; refusing to run a global worker")

        for index in range(TARGET_CACHE_ENTRIES + SENTINEL_CACHE_ENTRIES):
            location = target_location if index < TARGET_CACHE_ENTRIES else sentinel_location
            cache_key = f"kernel-handler:{run_id}:{index}"
            parameters = json.dumps({"kernel_recovery_probe": run_id, "index": index})
            result = json.dumps({"synthetic": True, "index": index})
            metadata = json.dumps({"kernel_recovery_probe": run_id})
            cur.execute("""
                INSERT INTO cache_entry
                    (cache_key, computation_type, location_id, parameters, result,
                     result_hash, computed_by, expires_at, size_bytes, metadata)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb,
                        %s, 'kernel-recovery-fixture', NOW() + INTERVAL '1 day',
                        %s, %s::jsonb)
            """, (cache_key, spec["computation_type"], str(location), parameters, result,
                  f"kernel-probe-{index:02d}", len(result), metadata))

        event_ids = [uuid4() for _ in range(EXPECTED_EVENTS)]
        for event_id in event_ids:
            payload = json.dumps({
                "location_id": str(target_location),
                "kernel_recovery_probe": run_id,
            })
            metadata = json.dumps({"kernel_recovery_probe": run_id})
            cur.execute("""
                INSERT INTO platform_event (id, event_type, payload, priority,
                    status, max_retries, metadata)
                VALUES (%s, %s, %s::jsonb, 'normal', 'pending', 1, %s::jsonb)
            """, (str(event_id), spec["event_type"], payload, metadata))
    conn.commit()
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "handler_key": handler_key,
        "event_type": spec["event_type"],
        "cache_type": spec["computation_type"],
        "handler": f"{spec['module']}.{spec['function']}",
        "handler_id": str(handler[0]),
        "target_location_id": str(target_location),
        "sentinel_location_id": str(sentinel_location),
        "event_ids": [str(event_id) for event_id in event_ids],
        "events": EXPECTED_EVENTS,
        "target_cache_entries": TARGET_CACHE_ENTRIES,
        "sentinel_cache_entries": SENTINEL_CACHE_ENTRIES,
        "scope": f"Synthetic {spec['event_type']} events and {spec['computation_type']} cache rows only; no farm/domain records or external integrations.",
    }


def observe(conn, run_id: str, handler_key: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status, count(*) FROM platform_event
            WHERE metadata->>'kernel_recovery_probe' = %s
            GROUP BY status ORDER BY status
        """, (run_id,))
        status_counts = dict(cur.fetchall())
        cur.execute("""
            SELECT count(*), count(DISTINCT lease_owner),
                   COALESCE(json_agg(DISTINCT lease_owner) FILTER (WHERE lease_owner IS NOT NULL), '[]'::json)
            FROM platform_event
            WHERE metadata->>'kernel_recovery_probe' = %s AND status = 'processing'
        """, (run_id,))
        processing_count, owner_count, owners = cur.fetchone()
        cur.execute("""
            SELECT d.status, count(*) FROM event_handler_delivery d
            JOIN platform_event e ON e.id = d.event_id
            WHERE e.metadata->>'kernel_recovery_probe' = %s
            GROUP BY status ORDER BY status
        """, (run_id,))
        delivery_counts = dict(cur.fetchall())
    return {
        "run_id": run_id,
        "handler_key": handler_key,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "event_status_counts": status_counts,
        "processing_events": processing_count,
        "distinct_processing_workers": owner_count,
        "processing_worker_ids": owners,
        "delivery_status_counts": delivery_counts,
    }


def verify(conn, run_id: str, handler_key: str) -> dict:
    spec = HANDLERS[handler_key]
    target_location, sentinel_location = identities(run_id)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT count(*), count(*) FILTER (WHERE status = 'completed'),
                   count(*) FILTER (WHERE lease_owner IS NULL)
            FROM platform_event
            WHERE metadata->>'kernel_recovery_probe' = %s AND event_type = %s
        """, (run_id, spec["event_type"]))
        event_total, completed, released = cur.fetchone()
        cur.execute("""
            SELECT count(*), count(*) FILTER (WHERE d.status = 'success'),
                   min(d.attempt_count), max(d.attempt_count)
            FROM event_handler_delivery d
            JOIN platform_event e ON e.id = d.event_id
            WHERE e.metadata->>'kernel_recovery_probe' = %s
        """, (run_id,))
        delivery_total, successful_deliveries, min_attempts, max_attempts = cur.fetchone()
        cur.execute("""
            SELECT count(*), count(*) FILTER (WHERE l.status = 'success')
            FROM event_handler_log l
            JOIN platform_event e ON e.id = l.event_id
            WHERE e.metadata->>'kernel_recovery_probe' = %s
        """, (run_id,))
        log_total, successful_logs = cur.fetchone()
        cur.execute("""
            SELECT computation_type, location_id::text, count(*), count(*) FILTER (WHERE is_valid),
                   count(*) FILTER (WHERE NOT is_valid),
                   count(*) FILTER (WHERE invalidation_reason = %s)
            FROM cache_entry
            WHERE metadata->>'kernel_recovery_probe' = %s
            GROUP BY computation_type, location_id ORDER BY computation_type, location_id
        """, (spec["invalidation_reason"], run_id))
        cache_groups = cur.fetchall()

    expected_target = (spec["computation_type"], str(target_location), TARGET_CACHE_ENTRIES, 0,
                       TARGET_CACHE_ENTRIES, TARGET_CACHE_ENTRIES)
    expected_sentinel = (spec["computation_type"], str(sentinel_location), SENTINEL_CACHE_ENTRIES,
                         SENTINEL_CACHE_ENTRIES, 0, 0)
    if (event_total, completed, released) != (EXPECTED_EVENTS, EXPECTED_EVENTS, EXPECTED_EVENTS):
        raise AssertionError(f"Unexpected event state: {(event_total, completed, released)}")
    if (delivery_total, successful_deliveries, min_attempts, max_attempts) != (
            EXPECTED_EVENTS, EXPECTED_EVENTS, 1, 1):
        raise AssertionError("Deliveries were missing, failed, or retried")
    if (log_total, successful_logs) != (EXPECTED_EVENTS, EXPECTED_EVENTS):
        raise AssertionError("Handler log count/status does not match expected deliveries")
    if sorted(cache_groups) != sorted([expected_target, expected_sentinel]):
        raise AssertionError(f"Cache invalidation scope/effect mismatch: {cache_groups}")

    return {
        "run_id": run_id,
        "handler_key": handler_key,
        "event_type": spec["event_type"],
        "cache_type": spec["computation_type"],
        "handler": f"{spec['module']}.{spec['function']}",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "events_completed": completed,
        "event_leases_released": released,
        "successful_deliveries": successful_deliveries,
        "delivery_attempts_min_max": [min_attempts, max_attempts],
        "successful_handler_logs": successful_logs,
        "target_cache_invalidated": TARGET_CACHE_ENTRIES,
        "sentinel_cache_preserved": SENTINEL_CACHE_ENTRIES,
        "cache_groups": [
            {"cache_type": row[0], "location_id": row[1], "total": row[2],
             "valid": row[3], "invalid": row[4], "expected_reason": row[5]}
            for row in cache_groups
        ],
        "scope": "Real PostgreSQL event claims and allowlisted cache-handler effects; synthetic-only, no external effects or domain writes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "observe", "verify"))
    parser.add_argument("--run-id", required=True, type=parse_run_id)
    parser.add_argument("--handler", choices=tuple(HANDLERS), default="metric")
    args = parser.parse_args()
    conn = connect()
    try:
        if args.mode == "prepare":
            output = prepare(conn, args.run_id, args.handler)
        elif args.mode == "observe":
            output = observe(conn, args.run_id, args.handler)
        else:
            output = verify(conn, args.run_id, args.handler)
        print(json.dumps(output, sort_keys=True))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"recovery handler probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
