"""CLI for the event bus.

Usage:
    python3 -m services.events --process [--batch-size N] [--worker-id ID]
    python3 -m services.events --stats
    python3 -m services.events --cleanup [--days N]
    python3 -m services.events --list-handlers
    python3 -m services.events --list-dead-letter
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def cmd_process(args):
    from services.events.bus import EventBus

    bus = EventBus()
    result = bus.process_pending(
        batch_size=args.batch_size,
        worker_id=args.worker_id,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["failed"] == 0 else 1


def cmd_worker(args):
    from services.events.bus import EventBus

    bus = EventBus(lease_seconds=args.lease_seconds)
    try:
        while True:
            result = bus.process_pending(args.batch_size, args.worker_id)
            if not any(result.values()):
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        return 0
    finally:
        bus.close()


def cmd_stats(args):
    from services.events.bus import EventBus

    bus = EventBus()
    stats = bus.get_stats()
    print("Event Bus Statistics (last 24h):")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")
    return 0


def cmd_cleanup(args):
    from services.events.bus import EventBus

    bus = EventBus()
    deleted = bus.cleanup_old_events(days=args.days)
    print(f"Cleaned up {deleted} old events")
    return 0


def cmd_list_handlers(args):
    from services.ingestion.base import get_db

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT handler_name, event_type, module_path,
                       function_name, is_enabled, priority_order
                FROM event_handler
                ORDER BY event_type, priority_order
                """
            )
            rows = cur.fetchall()
            if not rows:
                print("No event handlers registered.")
                return 0

            print(f"{'Handler':<30} {'Event Type':<25} {'Enabled':<10} {'Priority':<10}")
            print("-" * 75)
            for name, etype, module, func, enabled, prio in rows:
                print(f"{name:<30} {etype:<25} {'yes' if enabled else 'no':<10} {prio:<10}")
            print(f"\nTotal: {len(rows)} handlers")
            return 0
    finally:
        conn.close()


def cmd_list_dead_letter(args):
    from services.ingestion.base import get_db

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT original_event_id, event_type, failure_count,
                       last_error, created_at, disposition
                FROM event_dead_letter
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
            if not rows:
                print("No dead letter events.")
                return 0

            for eid, etype, fcount, error, created, disposition in rows:
                print(f"  [{created}] {etype} (failures: {fcount}, {disposition})")
                print(f"    ID: {eid}")
                if error:
                    print(f"    Error: {error[:100]}")
                print()
            return 0
    finally:
        conn.close()


def cmd_replay_dead_letter(args):
    from services.events.bus import EventBus

    bus = EventBus()
    try:
        changed = bus.replay_dead_letter(args.event_id, args.actor)
        print("Dead letter queued for replay" if changed else "Pending dead letter not found")
        return 0 if changed else 1
    finally:
        bus.close()


def cmd_dispose_dead_letter(args):
    from services.events.bus import EventBus

    bus = EventBus()
    try:
        changed = bus.dispose_dead_letter(
            args.event_id, args.disposition, args.actor, args.reason
        )
        print("Dead letter disposition recorded" if changed else "Pending dead letter not found")
        return 0 if changed else 1
    finally:
        bus.close()


def main():
    parser = argparse.ArgumentParser(description="Event Bus CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--process", action="store_true", help="Process pending events")
    group.add_argument("--worker", action="store_true", help="Continuously process events")
    group.add_argument("--stats", action="store_true", help="Show event statistics")
    group.add_argument("--cleanup", action="store_true", help="Clean up old events")
    group.add_argument("--list-handlers", action="store_true", help="List registered handlers")
    group.add_argument("--list-dead-letter", action="store_true", help="List dead letter events")
    group.add_argument("--replay-dead-letter", action="store_true", help="Replay a dead letter")
    group.add_argument("--dispose-dead-letter", action="store_true", help="Resolve/discard a dead letter")

    parser.add_argument("--batch-size", type=int, default=100, help="Events per batch")
    parser.add_argument("--worker-id", default=os.environ.get("HOSTNAME", "cli"), help="Worker identifier")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--days", type=int, default=30, help="Days to keep events")
    parser.add_argument("--limit", type=int, default=20, help="Max dead letter entries")
    parser.add_argument("--event-id", help="Original event UUID")
    parser.add_argument("--actor", default="cli", help="Operator recording the action")
    parser.add_argument("--disposition", choices=("resolved", "discarded"))
    parser.add_argument("--reason", default="", help="Disposition reason")

    args = parser.parse_args()

    if args.process:
        rc = cmd_process(args)
    elif args.worker:
        rc = cmd_worker(args)
    elif args.stats:
        rc = cmd_stats(args)
    elif args.cleanup:
        rc = cmd_cleanup(args)
    elif args.list_handlers:
        rc = cmd_list_handlers(args)
    elif args.list_dead_letter:
        rc = cmd_list_dead_letter(args)
    elif args.replay_dead_letter:
        if not args.event_id:
            parser.error("--event-id is required for replay")
        rc = cmd_replay_dead_letter(args)
    elif args.dispose_dead_letter:
        if not args.event_id or not args.disposition:
            parser.error("--event-id and --disposition are required")
        rc = cmd_dispose_dead_letter(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
