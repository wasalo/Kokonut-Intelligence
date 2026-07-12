"""CLI for the driver registry.

Usage:
    python3 -m services.drivers --list [--type TYPE]
    python3 -m services.drivers --list-instances [--driver NAME]
    python3 -m services.drivers --install --driver NAME --instance-name NAME --config '{}'
    python3 -m services.drivers --test --driver NAME
    python3 -m services.drivers --test-instance --instance-id UUID
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_list(args):
    from services.drivers.registry import DriverRegistry

    registry = DriverRegistry()
    drivers = registry.list_drivers(driver_type=args.type)

    if not drivers:
        print("No drivers registered.")
        return 0

    print(f"{'Driver':<30} {'Version':<10} {'Type':<18} {'Enabled':<10} {'Author':<15}")
    print("-" * 83)
    for d in drivers:
        enabled = "yes" if d["is_enabled"] else "no"
        print(
            f"{d['driver_name']:<30} {d['driver_version']:<10} {d['driver_type']:<18} "
            f"{enabled:<10} {d['author'] or '':<15}"
        )
    print(f"\nTotal: {len(drivers)} drivers")
    return 0


def cmd_list_instances(args):
    from services.drivers.registry import DriverRegistry

    registry = DriverRegistry()
    instances = registry.list_instances(driver_name=args.driver)

    if not instances:
        print("No driver instances configured.")
        return 0

    print(f"{'Instance':<25} {'Driver':<25} {'Status':<10} {'Runs':<8} {'Fails':<8}")
    print("-" * 76)
    for inst in instances:
        status = inst["last_status"] or "never"
        print(
            f"{inst['instance_name']:<25} {inst['driver_name']:<25} "
            f"{status:<10} {inst['run_count']:<8} {inst['consecutive_failures']:<8}"
        )
    print(f"\nTotal: {len(instances)} instances")
    return 0


def cmd_install(args):
    from services.drivers.registry import DriverRegistry

    registry = DriverRegistry()
    try:
        config = json.loads(args.config) if args.config else {}
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON config: {exc}")
        return 1

    instance_id = registry.create_instance(
        driver_name=args.driver,
        instance_name=args.instance_name,
        config=config,
        location_id=args.location_id,
    )
    print(f"Installed instance: {args.instance_name} (id={instance_id})")
    return 0


def cmd_test(args):
    from services.drivers.registry import DriverRegistry

    registry = DriverRegistry()
    result = registry.test_driver(args.driver)

    if result["healthy"]:
        print(f"✓ {result['driver_name']}: {result['message']}")
        return 0
    else:
        print(f"✗ {result['driver_name']}: {result['message']}")
        return 1


def cmd_test_instance(args):
    from services.drivers.registry import DriverRegistry
    from services.ingestion.base import get_db

    registry = DriverRegistry()
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT di.config, dr.module_path, dr.class_name, dr.driver_name
                FROM driver_instance di
                JOIN driver_registry dr ON di.driver_id = dr.id
                WHERE di.id = %s
                """,
                (args.instance_id,),
            )
            row = cur.fetchone()
            if not row:
                print(f"Instance not found: {args.instance_id}")
                return 1

            config, module_path, class_name, driver_name = row
    finally:
        conn.close()

    result = registry.test_driver(driver_name, config=config)
    if result["healthy"]:
        print(f"✓ Instance {args.instance_id}: {result['message']}")
        return 0
    else:
        print(f"✗ Instance {args.instance_id}: {result['message']}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Driver Registry CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List registered drivers")
    group.add_argument("--list-instances", action="store_true", help="List driver instances")
    group.add_argument("--install", action="store_true", help="Install a driver instance")
    group.add_argument("--test", action="store_true", help="Test a driver")
    group.add_argument("--test-instance", action="store_true", help="Test a driver instance")

    parser.add_argument("--type", help="Filter by driver type")
    parser.add_argument("--driver", help="Driver name")
    parser.add_argument("--instance-name", help="Instance name (for --install)")
    parser.add_argument("--instance-id", help="Instance UUID (for --test-instance)")
    parser.add_argument("--config", help="JSON config (for --install)")
    parser.add_argument("--location-id", help="Location UUID (for --install)")

    args = parser.parse_args()

    if args.list:
        rc = cmd_list(args)
    elif args.list_instances:
        rc = cmd_list_instances(args)
    elif args.install:
        if not args.driver or not args.instance_name:
            parser.error("--install requires --driver and --instance-name")
        rc = cmd_install(args)
    elif args.test:
        if not args.driver:
            parser.error("--test requires --driver")
        rc = cmd_test(args)
    elif args.test_instance:
        if not args.instance_id:
            parser.error("--test-instance requires --instance-id")
        rc = cmd_test_instance(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
