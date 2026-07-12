"""Scheduler worker loop.

Runs the scheduler tick loop in the worker container,
replacing the static crontab.
"""

from __future__ import annotations

import signal
import sys
import time

from services.common.logging import get_logger
from services.ingestion.base import get_db
from services.scheduler.engine import SchedulerEngine

logger = get_logger("scheduler.worker")

_running = True


def _shutdown(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def run_worker(tick_interval: int = 30, worker_id: str | None = None):
    """Run the scheduler worker loop."""
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    conn = get_db()
    engine = SchedulerEngine(conn, worker_id=worker_id)

    logger.info("Scheduler worker started (tick=%ds, worker=%s)", tick_interval, engine._worker_id)

    while _running:
        try:
            stats = engine.tick()
            if stats["launched"] > 0 or stats["failed"] > 0:
                logger.info(
                    "Tick complete: launched=%d skipped=%d no_resources=%d",
                    stats["launched"], stats["skipped"], stats["no_resources"],
                )
        except Exception:
            logger.exception("Scheduler tick failed")

        # Sleep in small increments so we respond to signals quickly
        for _ in range(tick_interval):
            if not _running:
                break
            time.sleep(1.0)

    logger.info("Scheduler worker stopped")
    conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scheduler Worker")
    parser.add_argument("--tick-interval", type=int, default=30, help="Seconds between ticks")
    parser.add_argument("--worker-id", default=None, help="Worker identifier")
    args = parser.parse_args()

    run_worker(tick_interval=args.tick_interval, worker_id=args.worker_id)


if __name__ == "__main__":
    main()
