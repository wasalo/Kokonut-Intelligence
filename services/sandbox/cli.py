"""CLI for sandboxed analysis environments.

Usage:
    python3 -m services.sandbox --create --location-id UUID [--type TYPE]
    python3 -m services.sandbox --destroy --env-id UUID
    python3 -m services.sandbox --run --env-id UUID --module PATH [--timeout N]
    python3 -m services.sandbox --list [--location-id UUID]
    python3 -m services.sandbox --runs [--env-id UUID] [--limit N]
    python3 -m services.sandbox --limits --env-id UUID
"""

from __future__ import annotations

import argparse
import sys
from services.common.cli import print_json

def cmd_create(args):
    from services.sandbox.environment import AnalysisEnvironment

    env = AnalysisEnvironment()
    env_id = env.create(args.location_id, env_type=args.env_type)
    print(f"Created environment: {env_id}")
    return 0


def cmd_destroy(args):
    from services.sandbox.environment import AnalysisEnvironment

    env = AnalysisEnvironment()
    ok = env.destroy(args.env_id)
    if ok:
        print(f"Destroyed environment: {args.env_id}")
        return 0
    else:
        print(f"Failed to destroy environment: {args.env_id}")
        return 1


def cmd_run(args):
    from services.sandbox.environment import AnalysisEnvironment

    env = AnalysisEnvironment()
    result = env.run(
        env_id=args.env_id,
        module_path=args.module,
        timeout_seconds=args.timeout,
    )
    print_json(result)
    return 0 if result.get("status") == "completed" else 1


def cmd_list(args):
    from services.sandbox.environment import AnalysisEnvironment

    env = AnalysisEnvironment()
    envs = env.list_environments(location_id=args.location_id)
    if not envs:
        print("No environments found.")
        return 0

    print(f"{'ID':<38} {'Location':<38} {'Type':<20} {'Status':<12} {'Created'}")
    print("-" * 120)
    for e in envs:
        print(
            f"{e['env_id']:<38} {e['location_id']:<38} {e['env_type']:<20} "
            f"{e['status']:<12} {e['created_at']}"
        )
    return 0


def cmd_runs(args):
    from services.sandbox.environment import AnalysisEnvironment

    env = AnalysisEnvironment()
    runs = env.list_runs(env_id=args.env_id, limit=args.limit)
    if not runs:
        print("No runs found.")
        return 0

    print(f"{'Run ID':<38} {'Type':<20} {'Status':<12} {'Duration':<12} {'Module'}")
    print("-" * 110)
    for r in runs:
        dur = f"{r['duration_ms']}ms" if r['duration_ms'] else "n/a"
        print(
            f"{r['run_id']:<38} {r['env_type']:<20} {r['status']:<12} "
            f"{dur:<12} {r['module_path']}"
        )
    return 0


def cmd_limits(args):
    from services.sandbox.monitor import ResourceMonitor

    monitor = ResourceMonitor()
    limits = monitor.check_limits(args.env_id)
    print_json(limits)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Sandbox CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true", help="Create an environment")
    group.add_argument("--destroy", action="store_true", help="Destroy an environment")
    group.add_argument("--run", action="store_true", help="Run in sandbox")
    group.add_argument("--list", action="store_true", help="List environments")
    group.add_argument("--runs", action="store_true", help="List runs")
    group.add_argument("--limits", action="store_true", help="Check resource limits")

    parser.add_argument("--env-id", help="Environment UUID")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--env-type", default="sandbox", help="Environment type")
    parser.add_argument("--module", help="Module path to run")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    parser.add_argument("--limit", type=int, default=20, help="Max results")

    args = parser.parse_args()

    if args.create:
        if not args.location_id:
            parser.error("--create requires --location-id")
        rc = cmd_create(args)
    elif args.destroy:
        if not args.env_id:
            parser.error("--destroy requires --env-id")
        rc = cmd_destroy(args)
    elif args.run:
        if not args.env_id or not args.module:
            parser.error("--run requires --env-id and --module")
        rc = cmd_run(args)
    elif args.list:
        rc = cmd_list(args)
    elif args.runs:
        rc = cmd_runs(args)
    elif args.limits:
        if not args.env_id:
            parser.error("--limits requires --env-id")
        rc = cmd_limits(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
