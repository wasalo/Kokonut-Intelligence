"""Task scheduler engine.

Replaces cron with a database-driven, observable, priority-aware
task scheduler with dependency resolution and resource management.
"""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from services.common.logging import get_logger
from services.scheduler.parser import next_run_time, describe_cron
from services.scheduler.resources import ResourcePool

logger = get_logger("scheduler.engine")


class SchedulerEngine:
    """Core scheduler that tick-checks and dispatches tasks."""

    def __init__(self, conn, worker_id: str | None = None):
        self._conn = conn
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._resources = ResourcePool(conn)

    def tick(self) -> dict[str, int]:
        """Run one scheduler tick. Returns execution stats."""
        stats = {"launched": 0, "skipped": 0, "no_resources": 0}
        now = datetime.now(timezone.utc)

        with self._conn.cursor() as cur:
            # Find tasks due to run
            cur.execute(
                """
                SELECT id, name, module_path, cron_expression, priority,
                       timeout_seconds, max_retries, retry_delay_seconds,
                       depends_on, consecutive_failures
                FROM scheduled_task
                WHERE is_enabled = TRUE
                  AND (next_run_at IS NULL OR next_run_at <= %s)
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    next_run_at
                """,
                (now,),
            )
            tasks = cur.fetchall()

        for task_row in tasks:
            task_id, name, module_path, cron_expr, priority, timeout, max_retries, retry_delay, deps, failures = task_row

            # Check dependencies
            if deps and not self._dependencies_met(deps, task_id):
                logger.debug("Task %s waiting on dependencies", name)
                stats["skipped"] += 1
                continue

            # Acquire resources
            resource_name = self._resource_for_task(priority)
            if resource_name and not self._resources.wait_for_resource(
                resource_name, timeout=5.0, worker_id=self._worker_id
            ):
                logger.warning("No resources available for task %s", name)
                stats["no_resources"] += 1
                continue

            # Launch task
            run_id = self._start_task(task_id, name, module_path, priority, timeout)
            if run_id:
                stats["launched"] += 1
                self._execute_task(run_id, task_id, name, module_path, timeout, resource_name)

            # Schedule next run
            self._schedule_next(task_id, cron_expr, now)

        return stats

    def _dependencies_met(self, deps: list, current_task_id: str) -> bool:
        """Check if all dependencies have completed recently."""
        with self._conn.cursor() as cur:
            for dep_id in deps:
                cur.execute(
                    """
                    SELECT last_status
                    FROM scheduled_task
                    WHERE id = %s
                    """,
                    (dep_id,),
                )
                row = cur.fetchone()
                if not row or row[0] != "completed":
                    return False
        return True

    def _resource_for_task(self, priority: str) -> str | None:
        """Map task priority to a resource name."""
        if priority == "critical":
            return "db_connection"
        return None  # No resource gating for non-critical tasks

    def _start_task(
        self, task_id: str, name: str, module_path: str, priority: str, timeout: int
    ) -> str | None:
        """Create a task_run record and mark task as running."""
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with self._conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO task_run (id, task_id, status, worker_id)
                    VALUES (%s, %s, 'running', %s)
                    """,
                    (run_id, task_id, self._worker_id),
                )
                cur.execute(
                    """
                    UPDATE scheduled_task
                    SET last_run_at = %s, last_status = 'running', updated_at = %s
                    WHERE id = %s
                    """,
                    (now, now, task_id),
                )
                self._conn.commit()
                logger.info("Started task %s (run %s)", name, run_id[:8])
                return run_id
            except Exception:
                self._conn.rollback()
                logger.exception("Failed to start task %s", name)
                return None

    def _execute_task(
        self,
        run_id: str,
        task_id: str,
        name: str,
        module_path: str,
        timeout: int,
        resource_name: str | None,
    ) -> None:
        """Execute the task as a subprocess and record the result."""
        start_time = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, "-m", module_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)

            if result.returncode == 0:
                self._complete_task(task_id, run_id, "completed", duration_ms, result.stdout[-2000:] if result.stdout else None)
            else:
                self._complete_task(
                    task_id, run_id, "failed", duration_ms,
                    error=(result.stderr or result.stdout)[-2000:],
                )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._complete_task(task_id, run_id, "timeout", duration_ms, "Task timed out")

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._complete_task(task_id, run_id, "failed", duration_ms, str(exc))

        finally:
            if resource_name:
                self._resources.release(resource_name)

    def _complete_task(
        self,
        task_id: str,
        run_id: str,
        status: str,
        duration_ms: int,
        error: str | None = None,
        stdout: str | None = None,
    ) -> None:
        """Record task completion and update task state."""
        now = datetime.now(timezone.utc)

        with self._conn.cursor() as cur:
            # Update task_run
            cur.execute(
                """
                UPDATE task_run
                SET status = %s, completed_at = %s, duration_ms = %s,
                    error_message = %s, stdout = %s
                WHERE id = %s
                """,
                (status, now, duration_ms, error, stdout, run_id),
            )

            # Update scheduled_task
            if status == "completed":
                cur.execute(
                    """
                    UPDATE scheduled_task
                    SET last_status = %s, last_duration_ms = %s,
                        consecutive_failures = 0, updated_at = %s
                    WHERE id = %s
                    """,
                    (status, duration_ms, now, task_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE scheduled_task
                    SET last_status = %s, last_duration_ms = %s,
                        consecutive_failures = consecutive_failures + 1,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (status, duration_ms, now, task_id),
                )

            # Publish event
            event_type = "task_completed" if status == "completed" else "task_failed"
            cur.execute(
                """
                INSERT INTO platform_event (event_type, source_table, source_id, payload, priority)
                VALUES (%s, 'task_run', %s, %s, 'normal')
                """,
                (
                    event_type,
                    run_id,
                    f'{{"task_id": "{task_id}", "run_id": "{run_id}", '
                    f'"status": "{status}", "duration_ms": {duration_ms}}}',
                ),
            )

        self._conn.commit()
        log_fn = logger.info if status == "completed" else logger.warning
        log_fn("Task %s finished: %s (%dms)", task_id[:8], status, duration_ms)

    def _schedule_next(self, task_id: str, cron_expr: str, now: datetime) -> None:
        """Compute and store the next run time."""
        try:
            nxt = next_run_time(cron_expr, after=now)
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE scheduled_task
                    SET next_run_at = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (nxt, now, task_id),
                )
            self._conn.commit()
        except Exception:
            logger.exception("Failed to schedule next run for task %s", task_id)

    def get_status(self) -> dict:
        """Get scheduler status."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE is_enabled) as enabled,
                    COUNT(*) FILTER (WHERE NOT is_enabled) as disabled,
                    COUNT(*) FILTER (WHERE last_status = 'running') as running,
                    COUNT(*) FILTER (WHERE last_status = 'failed'
                                     AND consecutive_failures > 0) as failing
                FROM scheduled_task
                """
            )
            counts = cur.fetchone()

            cur.execute(
                """
                SELECT name, module_path, cron_expression, priority,
                       last_status, last_run_at, next_run_at,
                       consecutive_failures
                FROM scheduled_task
                WHERE is_enabled = TRUE
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 3
                    END
                """
            )
            tasks = [
                {
                    "name": r[0],
                    "module": r[1],
                    "cron": r[2],
                    "priority": r[3],
                    "status": r[4],
                    "last_run": r[5].isoformat() if r[5] else None,
                    "next_run": r[6].isoformat() if r[6] else None,
                    "failures": r[7],
                }
                for r in cur.fetchall()
            ]

            resources = self._resources.get_status()

        return {
            "worker_id": self._worker_id,
            "tasks": {"enabled": counts[0], "disabled": counts[1], "running": counts[2], "failing": counts[3]},
            "task_list": tasks,
            "resources": resources,
        }
