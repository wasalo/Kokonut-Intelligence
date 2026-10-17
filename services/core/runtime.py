"""Supervise the existing API, scheduler, and event processes in one container."""

from __future__ import annotations

import argparse
import math
import os
import signal
import subprocess
import sys
import time
import uuid

from services.common.logging import get_logger
from services.common.worker_environment import (
    SCHEDULED_WORKER_KEYS,
    worker_subprocess_environment,
)

logger = get_logger("core.runtime")


def commands(port: int, with_workers: bool, workers_only: bool = False) -> list[tuple[str, list[str]]]:
    from services.core.features import is_enabled

    children = [] if workers_only else [
        ("api", [sys.executable, "-m", "services.gateway.cli", "--serve", "--port", str(port)])
    ]
    # Each supervisor lifetime gets distinct lease ownership, including replicas.
    worker_id = f"kernel-{uuid.uuid4().hex}"
    if (with_workers or workers_only) and is_enabled("scheduler"):
        children.append(
            ("scheduler", [sys.executable, "-m", "services.scheduler.worker", "--worker-id", f"{worker_id}-scheduler"])
        )
    if (with_workers or workers_only) and is_enabled("event_bus"):
        children.append(
            ("events", [sys.executable, "-m", "services.events", "--event-worker", "--worker-id", f"{worker_id}-events"])
        )
    if (with_workers or workers_only) and is_enabled("notification_delivery"):
        children.append(
            ("notifications", [sys.executable, "-m", "services.events", "--notification-worker",
                               "--worker-id", f"{worker_id}-notifications"])
        )
    return children


def run(port: int = 8099, with_workers: bool = False, shutdown_seconds: float = 30,
        workers_only: bool = False, require_schema: bool = False) -> int:
    """Exit on any unexpected child exit; Compose owns restart policy."""
    stopping = False
    children: list[tuple[str, subprocess.Popen]] = []
    old_handlers = {}

    if require_schema:
        from services.core.schema_readiness import SchemaReadinessError, require_schema_ready

        try:
            require_schema_ready()
        except SchemaReadinessError as exc:
            logger.error("Kernel schema readiness failed (%s); review migration status before startup", exc)
            return 1
        except Exception as exc:
            # Database errors may contain connection details; report only type.
            logger.error("Kernel schema readiness failed (%s); review migration status before startup",
                         type(exc).__name__)
            return 1

    def shutdown(signum, frame):
        nonlocal stopping
        stopping = True
        logger.info("Kernel shutdown requested (signal=%s)", signum)

    def send_group(process, signum):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            old_handlers[signum] = signal.signal(signum, shutdown)
        child_commands = commands(port, with_workers, workers_only)
        if not child_commands:
            raise ValueError("Workers-only runtime requires at least one enabled worker")
        for name, argv in child_commands:
            if stopping:
                break
            worker_key = {
                "scheduler": "scheduler",
                "events": "event_bus",
                "notifications": "notification_enqueue",
            }.get(name)
            allowed_worker_keys = (
                ("scheduler", *SCHEDULED_WORKER_KEYS)
                if name == "scheduler"
                else (worker_key,) if worker_key is not None else ()
            )
            process = subprocess.Popen(
                argv,
                start_new_session=True,
                env=worker_subprocess_environment(allowed_worker_keys=allowed_worker_keys),
            )
            children.append((name, process))
            logger.info("Started Kernel process %s (pid=%s)", name, process.pid)

        while not stopping:
            for name, process in children:
                code = process.poll()
                if code is not None:
                    logger.error("Kernel process %s exited unexpectedly (code=%s)", name, code)
                    return 1
            time.sleep(0.25)
        return 0
    finally:
        # Signal groups even if a parent exited, so its task descendants stop too.
        for _, process in children:
            send_group(process, signal.SIGTERM)
        deadline = time.monotonic() + shutdown_seconds
        for _, process in children:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for _, process in children:
            send_group(process, signal.SIGKILL)
            process.wait()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut Kernel process supervisor (Linux/POSIX)")
    parser.add_argument("--port", type=int, default=8099)
    roles = parser.add_mutually_exclusive_group()
    roles.add_argument("--with-workers", action="store_true", help="Run enabled durable workers alongside the API")
    roles.add_argument("--workers-only", action="store_true", help="Run enabled durable workers without an API")
    parser.add_argument("--shutdown-seconds", type=float, default=30)
    parser.add_argument("--require-schema", action="store_true",
                        help="Require applied checksums for bundled schemas before spawning processes")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not math.isfinite(args.shutdown_seconds) or args.shutdown_seconds <= 0:
        parser.error("--shutdown-seconds must be positive")
    raise SystemExit(run(args.port, args.with_workers, args.shutdown_seconds,
                        args.workers_only, args.require_schema))


if __name__ == "__main__":
    main()
