"""CLI for the event bus.

Usage:
    python3 -m services.events --process [--batch-size N] [--worker-id ID]
    python3 -m services.events --stats
    python3 -m services.events --cleanup [--days N]
    python3 -m services.events --list-handlers
    python3 -m services.events --list-dead-letter
    python3 -m services.events --fork-opportunities [--location-id UUID]
    python3 -m services.events --propose-fork [--location-id UUID]
    python3 -m services.events --process-event --source-domain DOM --event-type TYPE [--event-data '{}']
    python3 -m services.events --pending-transfers [--target-domain DOM]
    python3 -m services.events --resolve-transfer --transfer-id UUID --outcome helpful
    python3 -m services.events --add-rule --source-domain DOM --target-domain DOM --pattern TYPE
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
    from services.common.database import get_db

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
    from services.common.database import get_db

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
    group.add_argument("--fork-opportunities", action="store_true",
                       help="List fork opportunities (one event resolving >=2 pending transfers/decisions)")
    group.add_argument("--propose-fork", action="store_true",
                       help="Write DRAFT tactical_opportunity rows for detected forks")
    group.add_argument("--process-event", action="store_true",
                       help="Process a cross-domain insight event (requires --source-domain/--event-type)")
    group.add_argument("--pending-transfers", action="store_true",
                       help="List pending cross-domain insight transfers")
    group.add_argument("--resolve-transfer", action="store_true",
                       help="Resolve a transfer as helpful/not_helpful (requires --transfer-id/--outcome)")
    group.add_argument("--add-rule", action="store_true",
                       help="Add a cross-domain rule (requires --source-domain/--target-domain/--pattern)")

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
    parser.add_argument("--location-id", help="Scope fork opportunities to a location")
    parser.add_argument("--source-domain", help="Insight event/rule source domain")
    parser.add_argument("--event-type", help="Insight event type")
    parser.add_argument("--target-domain", help="Insight rule target domain")
    parser.add_argument("--pattern", help="Insight rule event pattern")
    parser.add_argument("--transfer-id", help="Transfer UUID to resolve")
    parser.add_argument("--outcome", choices=("helpful", "not_helpful"), help="Transfer outcome")
    parser.add_argument("--event-data", default="{}", help="JSON event payload for --process-event")

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
    elif args.fork_opportunities:
        rc = cmd_fork_opportunities(args)
    elif args.propose_fork:
        rc = cmd_propose_fork(args)
    elif args.process_event:
        if not (args.source_domain and args.event_type):
            parser.error("--source-domain and --event-type are required")
        rc = cmd_process_event(args)
    elif args.pending_transfers:
        rc = cmd_pending_transfers(args)
    elif args.resolve_transfer:
        if not (args.transfer_id and args.outcome):
            parser.error("--transfer-id and --outcome are required")
        rc = cmd_resolve_transfer(args)
    elif args.add_rule:
        if not (args.source_domain and args.target_domain and args.pattern):
            parser.error("--source-domain, --target-domain and --pattern are required")
        rc = cmd_add_rule(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


def cmd_fork_opportunities(args):
    from services.events.fork_detector import detect_fork_opportunities

    result = detect_fork_opportunities(_get_conn(), location_id=args.location_id)
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_propose_fork(args):
    from services.events.fork_detector import propose_fork_opportunities

    result = propose_fork_opportunities(
        _get_conn(), location_id=args.location_id, actor=args.actor
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_process_event(args):
    import json as _json

    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    data = _json.loads(args.event_data) if args.event_data else {}
    transfers = engine.process_event(
        args.source_domain, args.event_type, data, source_event_id=args.event_id
    )
    print(json.dumps(transfers, indent=2, default=str))
    return 0


def cmd_pending_transfers(args):
    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    transfers = engine.get_pending_transfers(target_domain=args.target_domain)
    print(json.dumps(transfers, indent=2, default=str))
    return 0


def cmd_resolve_transfer(args):
    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    result = engine.resolve_transfer(args.transfer_id, args.outcome, args.reason)
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_add_rule(args):
    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    result = engine.add_rule(
        args.source_domain, args.target_domain, args.pattern, {}
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


def _get_conn():
    from services.common.database import get_db

    return get_db()


if __name__ == "__main__":
    main()
