"""CLI for the event bus.

Usage:
    python3 -m services.events --process [--batch-size N] [--worker-id ID]
    python3 -m services.events --event-worker [--worker-id ID]
    python3 -m services.events --notification-worker [--worker-id ID]
    python3 -m services.events --isolated-notification-worker [--worker-id ID]
    python3 -m services.events --stats
    python3 -m services.events --cleanup [--actor OPERATOR]
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
import os
import sys
import time
from uuid import UUID

from services.common.cli import print_json
from services.common.errors import safe_exception_class
from services.common.logging import get_logger

logger = get_logger("events.cli")


def _preflight_fork_location(parser: argparse.ArgumentParser, args) -> None:
    """Validate a supplied fork location before opening the event DB connection."""
    if args.location_id is None:
        return
    try:
        args.location_id = str(UUID(args.location_id))
    except (AttributeError, TypeError, ValueError):
        parser.error("--location-id must be a valid UUID")


def cmd_process(args):
    from services.events.backend import get_event_store

    bus = get_event_store()
    try:
        result = bus.process_pending(
            batch_size=args.batch_size,
            worker_id=args.worker_id,
        )
        print_json(result)
        return 0 if result["failed"] == 0 else 1
    finally:
        bus.close()


def _run_worker(args, *, process_events: bool, deliver_notifications: bool,
                isolated_notification_delivery: bool = False,
                isolated_event_dispatch: bool = False):
    if args.poll_interval <= 0:
        raise ValueError("poll_interval must be positive")

    from services.core.features import is_enabled

    isolated_event_dispatch_requested = isolated_event_dispatch
    process_events = process_events and is_enabled("event_bus")
    isolated_event_dispatch = (
        isolated_event_dispatch
        and process_events
        and is_enabled("isolated_event_dispatch")
    )
    if isolated_event_dispatch_requested and not isolated_event_dispatch:
        logger.info("Isolated EventBus worker is disabled by feature configuration")
        return 0
    deliver_notifications = deliver_notifications and is_enabled("notification_delivery")
    isolated_notification_delivery = (
        isolated_notification_delivery
        and is_enabled("notification_delivery")
        and is_enabled("isolated_notification_delivery")
    )
    deliver_notifications = deliver_notifications or isolated_notification_delivery
    if not process_events and not deliver_notifications:
        logger.info("Event and notification workers are disabled by feature configuration")
        return 0

    try:
        while True:
            bus = None
            iteration_failed = False
            result = {"processed": 0, "failed": 0}
            notifications = {"claimed": 0}
            try:
                if process_events:
                    if isolated_event_dispatch:
                        from services.events.dispatch_worker import run_once

                        result = run_once(
                            args.worker_id, args.batch_size, args.lease_seconds
                        )
                    else:
                        from services.events.backend import get_event_store

                        bus = get_event_store(lease_seconds=args.lease_seconds, connect_timeout=5)
                        result = bus.process_pending(args.batch_size, args.worker_id)
                if deliver_notifications:
                    if isolated_notification_delivery:
                        from services.events.notification_delivery_worker import run_once

                        notifications = run_once(
                            args.worker_id, args.batch_size, args.lease_seconds
                        )
                    else:
                        from services.common.database import get_connection
                        from services.events.notification_outbox import deliver_batch

                        with get_connection(connect_timeout=5) as conn:
                            notifications = deliver_batch(conn, args.worker_id, args.batch_size)
            except KeyboardInterrupt:
                return 0
            except Exception as exc:
                # A dead connection is discarded with this iteration's bus;
                # the next poll gets a fresh event and notification connection.
                logger.error(
                    "Event worker iteration failed (%s)", safe_exception_class(exc)
                )
                iteration_failed = True
            finally:
                if bus is not None:
                    try:
                        bus.close()
                    except Exception as exc:
                        logger.warning(
                            "Failed to close event worker bus (%s)", safe_exception_class(exc)
                        )

            if iteration_failed:
                time.sleep(args.poll_interval)
                continue

            # Lease loss means another worker owns the event; this worker has
            # no immediate event work. Notification failures also have a
            # durable backoff, so an empty claim can safely sleep.
            if (result["processed"] == 0 and result["failed"] == 0
                    and notifications["claimed"] == 0):
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        return 0


def cmd_worker(args):
    """Compatibility worker that dispatches events and sends notifications."""
    return _run_worker(args, process_events=True, deliver_notifications=True)


def cmd_event_worker(args):
    """Continuously dispatch durable domain events without sending notifications."""
    return _run_worker(args, process_events=True, deliver_notifications=False)


def cmd_isolated_event_worker(args):
    """Dispatch global events through the dedicated bounded database identity."""
    return _run_worker(
        args,
        process_events=True,
        deliver_notifications=False,
        isolated_event_dispatch=True,
    )


def cmd_notification_worker(args):
    """Continuously deliver durable notification intents without dispatching events."""
    return _run_worker(args, process_events=False, deliver_notifications=True)


def cmd_isolated_notification_worker(args):
    """Deliver notification intents through the dedicated worker login."""
    return _run_worker(
        args,
        process_events=False,
        deliver_notifications=False,
        isolated_notification_delivery=True,
    )


def cmd_stats(args):
    from services.events.backend import get_event_store

    bus = get_event_store()
    try:
        stats = bus.get_stats()
    finally:
        bus.close()
    print("Event Bus Statistics (last 24h):")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")
    return 0


def cmd_cleanup(args):
    from services.events.retention import require_event_retention_cleanup

    try:
        require_event_retention_cleanup()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    from services.events.backend import get_event_store

    bus = get_event_store()
    try:
        deleted = bus.cleanup_old_events(actor=args.actor)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        bus.close()
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
                    print("    Error: [details redacted]")
                print()
            return 0
    finally:
        conn.close()


def cmd_replay_dead_letter(args):
    from services.events.backend import get_event_store

    bus = get_event_store()
    try:
        changed = bus.replay_dead_letter(args.event_id, args.actor)
        print("Dead letter queued for replay" if changed else "Pending dead letter not found")
        return 0 if changed else 1
    finally:
        bus.close()


def cmd_dispose_dead_letter(args):
    from services.events.backend import get_event_store

    bus = get_event_store()
    try:
        changed = bus.dispose_dead_letter(
            args.event_id, args.disposition, args.actor, args.reason
        )
        print("Dead letter disposition recorded" if changed else "Pending dead letter not found")
        return 0 if changed else 1
    finally:
        bus.close()


def cmd_notification_process(args):
    from services.common.database import get_connection
    from services.events.notification_outbox import deliver_batch

    with get_connection() as conn:
        result = deliver_batch(conn, args.worker_id, args.batch_size)
    print_json(result)
    return 0 if result["failed"] == 0 and result["lease_lost"] == 0 else 1


def cmd_notification_stats(args):
    from services.common.database import get_connection
    from services.events.notification_outbox import get_stats

    with get_connection() as conn:
        result = get_stats(conn)
    print_json(result)
    return 0


def cmd_notification_list_dead_letter(args):
    from services.common.database import get_connection
    from services.events.notification_outbox import list_dead_letters

    with get_connection() as conn:
        result = list_dead_letters(conn, args.limit)
    print_json(result)
    return 0


def cmd_notification_replay_dead_letter(args):
    from services.common.database import get_connection
    from services.events.notification_outbox import replay_dead_letter

    with get_connection() as conn:
        changed = replay_dead_letter(
            conn, args.notification_id, actor=args.notification_actor, reason=args.reason
        )
    print_json({"replayed": changed, "notification_id": args.notification_id})
    return 0 if changed else 1


def cmd_notification_dispose_dead_letter(args):
    from services.common.database import get_connection
    from services.events.notification_outbox import dispose_dead_letter

    with get_connection() as conn:
        changed = dispose_dead_letter(
            conn,
            args.notification_id,
            disposition=args.disposition,
            actor=args.notification_actor,
            reason=args.reason,
        )
    print_json({"disposed": changed, "notification_id": args.notification_id,
                "disposition": args.disposition})
    return 0 if changed else 1


def main():
    parser = argparse.ArgumentParser(description="Event Bus CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--process", action="store_true", help="Process pending events")
    group.add_argument("--worker", action="store_true",
                       help="Compatibility mode: dispatch events and deliver notifications")
    group.add_argument("--event-worker", action="store_true",
                       help="Continuously dispatch events without delivering notifications")
    group.add_argument("--isolated-event-worker", action="store_true",
                       help="Dispatch events using the dedicated bounded database identity")
    group.add_argument("--notification-worker", action="store_true",
                       help="Continuously deliver notifications without dispatching events")
    group.add_argument("--isolated-notification-worker", action="store_true",
                       help="Deliver notifications using the dedicated bounded database identity")
    group.add_argument("--stats", action="store_true", help="Show event statistics")
    group.add_argument("--cleanup", action="store_true", help="Clean up old events")
    group.add_argument("--list-handlers", action="store_true", help="List registered handlers")
    group.add_argument("--list-dead-letter", action="store_true", help="List dead letter events")
    group.add_argument("--replay-dead-letter", action="store_true", help="Replay a dead letter")
    group.add_argument("--dispose-dead-letter", action="store_true", help="Resolve/discard a dead letter")
    group.add_argument("--notification-process", action="store_true",
                       help="Deliver one batch of durable notifications")
    group.add_argument("--notification-stats", action="store_true",
                       help="Show notification counts, oldest open age, and storage capacity")
    group.add_argument("--notification-list-dead-letter", action="store_true",
                       help="List notification deliveries requiring operator review")
    group.add_argument("--notification-replay-dead-letter", action="store_true",
                       help="Replay one dead-letter notification with actor and reason")
    group.add_argument("--notification-dispose-dead-letter", action="store_true",
                       help="Resolve/discard one dead-letter notification with actor and reason")
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
    parser.add_argument("--limit", type=int, default=20, help="Max dead letter entries")
    parser.add_argument("--event-id", help="Original event UUID")
    parser.add_argument("--notification-id", help="Notification outbox UUID")
    parser.add_argument("--notification-actor", help="Operator identity for notification dead-letter actions")
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
    elif args.event_worker:
        rc = cmd_event_worker(args)
    elif args.isolated_event_worker:
        rc = cmd_isolated_event_worker(args)
    elif args.notification_worker:
        rc = cmd_notification_worker(args)
    elif args.isolated_notification_worker:
        rc = cmd_isolated_notification_worker(args)
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
    elif args.notification_process:
        rc = cmd_notification_process(args)
    elif args.notification_stats:
        rc = cmd_notification_stats(args)
    elif args.notification_list_dead_letter:
        rc = cmd_notification_list_dead_letter(args)
    elif args.notification_replay_dead_letter:
        if not args.notification_id or not args.notification_actor or not args.reason:
            parser.error("--notification-id, --notification-actor and --reason are required for notification replay")
        rc = cmd_notification_replay_dead_letter(args)
    elif args.notification_dispose_dead_letter:
        if not args.notification_id or not args.disposition or not args.notification_actor or not args.reason:
            parser.error(
                "--notification-id, --disposition, --notification-actor and --reason "
                "are required for notification disposition"
            )
        rc = cmd_notification_dispose_dead_letter(args)
    elif args.fork_opportunities:
        _preflight_fork_location(parser, args)
        rc = cmd_fork_opportunities(args)
    elif args.propose_fork:
        _preflight_fork_location(parser, args)
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
    print_json(result)
    return 0


def cmd_propose_fork(args):
    from services.events.fork_detector import propose_fork_opportunities

    result = propose_fork_opportunities(
        _get_conn(), location_id=args.location_id, actor=args.actor
    )
    print_json(result)
    return 0


def cmd_process_event(args):
    import json as _json

    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    data = _json.loads(args.event_data) if args.event_data else {}
    transfers = engine.process_event(
        args.source_domain, args.event_type, data, source_event_id=args.event_id
    )
    print_json(transfers)
    return 0


def cmd_pending_transfers(args):
    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    transfers = engine.get_pending_transfers(target_domain=args.target_domain)
    print_json(transfers)
    return 0


def cmd_resolve_transfer(args):
    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    result = engine.resolve_transfer(args.transfer_id, args.outcome, args.reason)
    print_json(result)
    return 0


def cmd_add_rule(args):
    from services.events.insight_transfer import InsightTransferEngine

    engine = InsightTransferEngine(conn=_get_conn())
    result = engine.add_rule(
        args.source_domain, args.target_domain, args.pattern, {}
    )
    print_json(result)
    return 0


def _get_conn():
    from services.common.database import get_db

    return get_db()


if __name__ == "__main__":
    main()
