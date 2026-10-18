"""Scheduler worker loop.

Runs the scheduler tick loop in the worker container,
replacing the static crontab.
"""

from __future__ import annotations

import signal
import time
import uuid

from services.common.database import get_db
from services.common.errors import safe_exception_class
from services.common.logging import get_logger
from services.scheduler.backend import get_scheduler

logger = get_logger("scheduler.worker")

_running = True


def _shutdown(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def run_worker(tick_interval: int = 30, worker_id: str | None = None):
    """Run the scheduler worker loop."""
    if tick_interval <= 0:
        raise ValueError("tick_interval must be positive")

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    logger.info("Scheduler worker started (tick=%ds, worker=%s)", tick_interval, worker_id)

    try:
        while _running:
            _run_tick(worker_id)

            # Sleep in small increments so we respond to signals quickly. A
            # later tick obtains a new connection after a transient DB outage.
            for _ in range(tick_interval):
                if not _running:
                    break
                time.sleep(1.0)
    finally:
        logger.info("Scheduler worker stopped")


def _run_tick(worker_id: str) -> dict[str, int] | None:
    """Run one tick with a disposable connection so broken sessions are discarded."""
    conn = None
    try:
        conn = get_db(connect_timeout=5)
        engine = get_scheduler(conn, worker_id=worker_id)
        stats = engine.tick()
        if stats["launched"] > 0 or stats["failed"] > 0:
            logger.info(
                "Tick complete: launched=%d failed=%d skipped=%d no_resources=%d",
                stats["launched"], stats["failed"], stats["skipped"], stats["no_resources"],
            )
        return stats
    except Exception as exc:
        # Do not call rollback on a connection that may itself have failed. A
        # close discards the transaction; the next loop iteration reconnects.
        logger.error("Scheduler tick failed (%s)", safe_exception_class(exc))
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                logger.warning(
                    "Failed to close scheduler tick connection (%s)", safe_exception_class(exc)
                )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scheduler Worker")
    parser.add_argument("--tick-interval", type=int, default=30, help="Seconds between ticks")
    parser.add_argument("--worker-id", default=None, help="Worker identifier")
    args = parser.parse_args()

    run_worker(tick_interval=args.tick_interval, worker_id=args.worker_id)


if __name__ == "__main__":
    main()
