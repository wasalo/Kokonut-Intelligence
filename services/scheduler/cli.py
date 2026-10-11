"""CLI for the task scheduler.

Usage:
    python3 -m services.scheduler --status
    python3 -m services.scheduler --tick
    python3 -m services.scheduler --enable TASK_NAME
    python3 -m services.scheduler --disable TASK_NAME
    python3 -m services.scheduler --run-now TASK_NAME
    python3 -m services.scheduler --list-runs [--limit N]
    python3 -m services.scheduler --worker [--tick-interval N]
"""

from __future__ import annotations

import argparse
import sys

from services.common.cli import print_json


def cmd_status(args):
    from services.common.database import get_db
    from services.scheduler.backend import get_scheduler

    conn = get_db()
    try:
        engine = get_scheduler(conn)
        status = engine.get_status()
        print(f"Worker: {status['worker_id']}")
        print(f"Tasks: {status['tasks']['enabled']} enabled, "
              f"{status['tasks']['disabled']} disabled, "
              f"{status['tasks']['running']} running, "
              f"{status['tasks']['failing']} failing")
        print()

        if status["task_list"]:
            print(f"{'Name':<30} {'Priority':<10} {'Cron':<20} {'Status':<12} {'Next Run':<20}")
            print("-" * 92)
            for t in status["task_list"]:
                print(
                    f"{t['name']:<30} {t['priority']:<10} {t['cron']:<20} "
                    f"{t['status'] or 'pending':<12} {t['next_run'] or 'n/a':<20}"
                )

        if status["resources"]:
            print("\nResources:")
            for r in status["resources"]:
                print(f"  {r['name']}: {r['running']}/{r['max']} ({r['type']})")
        return 0
    finally:
        conn.close()


def cmd_tick(args):
    from services.common.database import get_db
    from services.scheduler.backend import get_scheduler

    conn = get_db()
    try:
        engine = get_scheduler(conn, worker_id=args.worker_id)
        stats = engine.tick()
        print_json(stats)
        return 0
    finally:
        conn.close()


def cmd_enable(args):
    from services.common.cli import get_connection
    from services.scheduler.activation import enable_schedule

    with get_connection() as conn:
        enabled = enable_schedule(conn, args.task_name, include_dependencies=bool(args.task_name_graph))
    print_json({"enabled": enabled, "already_enabled": not enabled})
    return 0


def cmd_disable(args):
    from services.common.database import get_db

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scheduled_task
                SET is_enabled = FALSE, updated_at = NOW()
                WHERE name = %s
                RETURNING name
                """,
                (args.task_name,),
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                print(f"Disabled task: {row[0]}")
                return 0
            else:
                print(f"Task not found: {args.task_name}")
                return 1
    finally:
        conn.close()


def cmd_run_now(args):
    import subprocess
    import sys as _sys

    from services.common.database import get_db
    from services.security.execution_allowlist import validate_scheduled_module

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT module_path, command_args, timeout_seconds FROM scheduled_task WHERE name = %s",
                (args.task_name,),
            )
            row = cur.fetchone()
            if not row:
                print(f"Task not found: {args.task_name}")
                return 1

            module_path, command_args, timeout = row
            validate_scheduled_module(module_path)
            print(f"Running {args.task_name} ({module_path})...")
            result = subprocess.run(
                [_sys.executable, "-m", module_path, *list(command_args or [])],
                timeout=timeout,
            )
            return result.returncode
    finally:
        conn.close()


def cmd_list_runs(args):
    from services.common.database import get_db

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tr.id, st.name, tr.status, tr.started_at,
                       tr.completed_at, tr.duration_ms, tr.error_message
                FROM task_run tr
                JOIN scheduled_task st ON tr.task_id = st.id
                ORDER BY tr.started_at DESC
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
            if not rows:
                print("No task runs found.")
                return 0

            for run_id, name, status, started, completed, duration, error in rows:
                dur_str = f"{duration}ms" if duration else "n/a"
                print(f"  [{started}] {name}: {status} ({dur_str})")
                if error:
                    print(f"    Error: {error[:120]}")
            return 0
    finally:
        conn.close()


def cmd_worker(args):
    from services.scheduler.worker import run_worker
    run_worker(tick_interval=args.tick_interval, worker_id=args.worker_id)


def cmd_job_plan(args):
    from services.scheduler.job_plan import build_job_plan

    print_json(build_job_plan(args.job_plan, args.cadence, location_id=args.location_id))


def cmd_check_graph(args):
    from services.common.cli import get_connection
    from services.scheduler.graph import audit_graph

    with get_connection() as conn:
        tasks = conn.execute(
            """SELECT id, name, module_path, command_args, cron_expression,
                      depends_on, dependency_mode, is_enabled, next_run_at,
                      retry_at, last_status FROM scheduled_task ORDER BY name"""
        ).all()
    report = audit_graph(tasks)
    print_json(report)
    if not report["valid"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Task Scheduler CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Show scheduler status")
    group.add_argument("--tick", action="store_true", help="Run one scheduler tick")
    group.add_argument("--enable", dest="task_name", help="Enable a task")
    group.add_argument("--enable-graph", dest="task_name_graph", help="Validate and atomically enable a task and its prerequisites")
    group.add_argument("--disable", dest="task_name_disable", help="Disable a task")
    group.add_argument("--run-now", dest="task_name_run", help="Run a task immediately")
    group.add_argument("--list-runs", action="store_true", help="List recent task runs")
    group.add_argument("--worker", action="store_true", help="Start the scheduler worker")
    group.add_argument("--job-plan", help="Print a disabled definition for a known Kernel job; no database writes")
    group.add_argument("--check-graph", action="store_true", help="Audit stored task dependencies without activation")

    parser.add_argument("--tick-interval", type=int, default=30, help="Worker tick interval (seconds)")
    parser.add_argument("--worker-id", default=None, help="Worker identifier")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--cadence", choices=["hourly", "every-6h", "daily", "weekly"], default="daily")
    parser.add_argument("--location-id", help="Location UUID for weather or climate job planning")

    args = parser.parse_args()

    if args.check_graph:
        from services.common.cli import run

        run(cmd_check_graph, args)
        rc = 0
    elif args.job_plan:
        from services.common.cli import run

        run(cmd_job_plan, args)
        rc = 0
    elif args.status:
        rc = cmd_status(args)
    elif args.tick:
        rc = cmd_tick(args)
    elif args.task_name:
        from services.common.cli import run

        run(cmd_enable, args)
        rc = 0
    elif args.task_name_graph:
        from services.common.cli import run

        args.task_name = args.task_name_graph
        run(cmd_enable, args)
        rc = 0
    elif args.task_name_disable:
        args.task_name = args.task_name_disable
        rc = cmd_disable(args)
    elif args.task_name_run:
        args.task_name = args.task_name_run
        rc = cmd_run_now(args)
    elif args.list_runs:
        rc = cmd_list_runs(args)
    elif args.worker:
        rc = cmd_worker(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
