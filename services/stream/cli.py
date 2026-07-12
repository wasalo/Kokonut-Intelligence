"""CLI for the stream processor.

Usage:
    python3 -m services.stream --run [--batch-size N]
    python3 -m services.stream --stats
    python3 -m services.stream --windows --sensor ID --metric NAME
    python3 -m services.stream --alerts [--severity LEVEL]
    python3 -m services.stream --acknowledge ALERT_ID --by USER
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_run(args):
    from services.stream.processor import StreamProcessor

    processor = StreamProcessor()
    stats = processor.process_buffer(batch_size=args.batch_size)
    print(json.dumps(stats, indent=2))
    return 0


def cmd_stats(args):
    from services.stream.processor import StreamProcessor

    processor = StreamProcessor()
    stats = processor.stats()
    print(json.dumps(stats, indent=2))
    return 0


def cmd_windows(args):
    from services.stream.windows import WindowAggregator

    aggregator = WindowAggregator()
    windows = aggregator.get_windows(args.sensor, args.metric, args.window_size)
    if not windows:
        print("No windows found.")
        return 0

    print(f"{'Window Start':<22} {'Window End':<22} {'Min':<10} {'Max':<10} {'Avg':<10} {'Samples':<10}")
    print("-" * 86)
    for w in windows:
        print(
            f"{w['window_start']:<22} {w['window_end']:<22} "
            f"{w['min_value']:<10.2f} {w['max_value']:<10.2f} "
            f"{w['avg_value'] or 0:<10.2f} {w['sample_count']:<10}"
        )
    return 0


def cmd_alerts(args):
    from services.stream.alerts import StreamAlertEvaluator

    evaluator = StreamAlertEvaluator()
    alerts = evaluator.list_unacknowledged(severity=args.severity)
    if not alerts:
        print("No unacknowledged alerts.")
        return 0

    for a in alerts:
        print(f"  [{a['severity'].upper()}] {a['alert_type']}: {a['message']}")
        print(f"    ID: {a['alert_id']}")
        print(f"    Sensor: {a['sensor_device_id']}")
        print(f"    Time: {a['created_at']}")
        print()
    return 0


def cmd_acknowledge(args):
    from services.stream.alerts import StreamAlertEvaluator

    evaluator = StreamAlertEvaluator()
    ok = evaluator.acknowledge(args.alert_id, args.by)
    if ok:
        print(f"Acknowledged alert: {args.alert_id}")
        return 0
    else:
        print(f"Failed to acknowledge alert: {args.alert_id}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Stream Processor CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true", help="Process buffered readings")
    group.add_argument("--stats", action="store_true", help="Show stream statistics")
    group.add_argument("--windows", action="store_true", help="Show windowed aggregations")
    group.add_argument("--alerts", action="store_true", help="List unacknowledged alerts")
    group.add_argument("--acknowledge", action="store_true", help="Acknowledge an alert")

    parser.add_argument("--batch-size", type=int, default=500, help="Buffer batch size")
    parser.add_argument("--sensor", help="Sensor device UUID")
    parser.add_argument("--metric", help="Metric name")
    parser.add_argument("--window-size", default="5min", help="Window size (1min/5min/15min/1hour)")
    parser.add_argument("--severity", help="Filter by severity")
    parser.add_argument("--alert-id", help="Alert UUID to acknowledge")
    parser.add_argument("--by", help="Acknowledger name")

    args = parser.parse_args()

    if args.run:
        rc = cmd_run(args)
    elif args.stats:
        rc = cmd_stats(args)
    elif args.windows:
        if not args.sensor or not args.metric:
            parser.error("--windows requires --sensor and --metric")
        rc = cmd_windows(args)
    elif args.alerts:
        rc = cmd_alerts(args)
    elif args.acknowledge:
        if not args.alert_id or not args.by:
            parser.error("--acknowledge requires --alert-id and --by")
        rc = cmd_acknowledge(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
