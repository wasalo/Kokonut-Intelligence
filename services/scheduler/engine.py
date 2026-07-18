"""Task scheduler engine.

Replaces cron with a database-driven, observable, priority-aware
task scheduler with dependency resolution and resource management.
"""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from services.common.logging import get_logger
from services.scheduler.parser import next_run_time
from services.scheduler.resources import ResourcePool
from services.security.execution_allowlist import validate_scheduled_module

logger = get_logger("scheduler.engine")


class SchedulerLeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the run it is completing."""


class SchedulerEngine:
    """Core scheduler that tick-checks and dispatches tasks."""

    def __init__(self, conn, worker_id: str | None = None):
        self._conn = conn
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._resources = ResourcePool(conn)

    def tick(self) -> dict[str, int]:
        """Run one scheduler tick. Returns execution stats."""
        stats = {"launched": 0, "failed": 0, "skipped": 0, "no_resources": 0}
        while True:
            task = self._claim_next()
            if not task:
                break
            run_id, task_id, name, module_path, command_args, priority, timeout = task
            resource_name = self._resource_for_task(priority)
            if resource_name and not self._resources.wait_for_resource(
                resource_name, timeout=5.0, worker_id=self._worker_id
            ):
                logger.warning("No resources available for task %s", name)
                self._release_unstarted(run_id, task_id)
                stats["no_resources"] += 1
                break

            try:
                stats["launched"] += 1
                if not self._execute_task(
                    run_id, task_id, name, module_path, command_args, timeout, resource_name
                ):
                    stats["failed"] += 1
            finally:
                if resource_name:
                    self._resources.release(resource_name)

        return stats

    def _claim_next(self):
        """Atomically lease one due task, create its run, and advance its cadence."""
        now = datetime.now(timezone.utc)
        try:
            with self._conn.cursor() as cur:
                # Recover work whose worker died. A later claim gets a fresh run.
                cur.execute(
                    """
                    UPDATE task_run tr SET status = 'failed', completed_at = %s,
                        error_message = 'Scheduler lease expired'
                    FROM scheduled_task st
                    WHERE tr.task_id = st.id AND tr.status = 'running'
                      AND st.lease_expires_at <= %s
                    """,
                    (now, now),
                )
                cur.execute(
                    """
                    UPDATE scheduled_task SET
                        retry_at = CASE WHEN retry_attempt < max_retries THEN %s END,
                        retry_attempt = CASE WHEN retry_attempt < max_retries
                                             THEN retry_attempt + 1 ELSE 0 END,
                        lease_owner = NULL, lease_expires_at = NULL,
                        last_status = 'failed', updated_at = %s
                    WHERE lease_expires_at <= %s AND last_status = 'running'
                    """,
                    (now, now, now),
                )
                cur.execute(
                    """
                    SELECT st.id, st.name, st.module_path, st.command_args,
                           st.cron_expression, st.priority, st.timeout_seconds,
                           st.retry_attempt, st.retry_at, st.allow_overlap
                    FROM scheduled_task st
                    WHERE st.is_enabled = TRUE
                      AND (st.lease_expires_at IS NULL OR st.lease_expires_at <= %s)
                      AND (st.retry_at <= %s OR
                           (st.retry_at IS NULL AND (st.next_run_at IS NULL OR st.next_run_at <= %s)))
                      AND NOT EXISTS (
                          SELECT 1 FROM unnest(st.depends_on) dep
                          LEFT JOIN scheduled_task dependency ON dependency.id = dep
                          WHERE dependency.last_status IS DISTINCT FROM 'completed'
                      )
                      AND (st.allow_overlap OR NOT EXISTS (
                          SELECT 1 FROM task_run tr
                          WHERE tr.task_id = st.id AND tr.status = 'running'
                      ))
                    ORDER BY CASE st.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                             WHEN 'normal' THEN 2 ELSE 3 END,
                             COALESCE(st.retry_at, st.next_run_at, '-infinity')
                    FOR UPDATE OF st SKIP LOCKED
                    LIMIT 1
                    """,
                    (now, now, now),
                )
                row = cur.fetchone()
                if not row:
                    self._conn.commit()
                    return None
                task_id, name, module_path, args, cron, priority, timeout, retry_attempt, retry_at, overlap = row
                run_id = str(uuid.uuid4())
                attempt = retry_attempt + 1
                next_run = next_run_time(cron, after=now) if retry_at is None else None
                cur.execute(
                    """
                    INSERT INTO task_run
                        (id, task_id, status, worker_id, attempt_count, retry_count, allow_overlap)
                    VALUES (%s, %s, 'running', %s, %s, %s, %s)
                    """,
                    (run_id, task_id, self._worker_id, attempt, attempt - 1, overlap),
                )
                cur.execute(
                    """
                    UPDATE scheduled_task SET
                        last_run_at = %s, last_status = 'running',
                        next_run_at = COALESCE(%s, next_run_at), retry_at = NULL,
                        lease_owner = %s, lease_expires_at = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (now, next_run, self._worker_id, now + timedelta(seconds=timeout + 60), now, task_id),
                )
            self._conn.commit()
            logger.info("Claimed task %s (run %s, attempt %d)", name, run_id[:8], attempt)
            return run_id, task_id, name, module_path, list(args or []), priority, timeout
        except Exception:
            self._conn.rollback()
            raise

    def _resource_for_task(self, priority: str) -> str | None:
        """Map task priority to a resource name."""
        if priority == "critical":
            return "db_connection"
        return None  # No resource gating for non-critical tasks

    def _release_unstarted(self, run_id: str, task_id: str) -> None:
        """Make a claimed task immediately eligible when dispatch cannot start it."""
        now = datetime.now(timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE task_run SET status = 'cancelled', completed_at = %s WHERE id = %s",
                (now, run_id),
            )
            cur.execute(
                """UPDATE scheduled_task SET retry_at = %s, lease_owner = NULL,
                       lease_expires_at = NULL, last_status = 'cancelled', updated_at = %s
                   WHERE id = %s""",
                (now, now, task_id),
            )
        self._conn.commit()

    def _execute_task(
        self,
        run_id: str,
        task_id: str,
        name: str,
        module_path: str,
        command_args: list,
        timeout: int,
        resource_name: str | None,
    ) -> bool:
        """Execute the task as a subprocess and record the result."""
        start_time = time.monotonic()
        try:
            validate_scheduled_module(module_path)
            result = subprocess.run(
                [sys.executable, "-m", module_path, *command_args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)

            if result.returncode == 0:
                self._complete_task(
                    task_id, run_id, "completed", duration_ms,
                    stdout=result.stdout[-2000:] if result.stdout else None,
                )
                return True
            else:
                self._complete_task(
                    task_id, run_id, "failed", duration_ms,
                    error=(result.stderr or result.stdout)[-2000:],
                )
                return False

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._complete_task(task_id, run_id, "timeout", duration_ms, "Task timed out")
            return False

        except SchedulerLeaseLostError:
            raise

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._complete_task(
                task_id, run_id, "failed", duration_ms, str(exc), retry_immediately=True
            )
            return False

    def _complete_task(
        self,
        task_id: str,
        run_id: str,
        status: str,
        duration_ms: int,
        error: str | None = None,
        stdout: str | None = None,
        retry_immediately: bool = False,
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
                WHERE id = %s AND worker_id = %s AND status = 'running'
                """,
                (status, now, duration_ms, error, stdout, run_id, self._worker_id),
            )
            if cur.rowcount != 1:
                self._conn.rollback()
                raise SchedulerLeaseLostError(
                    f"Run {run_id} is no longer owned by worker {self._worker_id}"
                )

            cur.execute("SELECT attempt_count, max_retries, retry_delay_seconds FROM task_run JOIN scheduled_task ON scheduled_task.id = task_run.task_id WHERE task_run.id = %s", (run_id,))
            attempt, max_retries, retry_delay = cur.fetchone()

            # Update scheduled_task and persist retry eligibility.
            if status == "completed":
                cur.execute(
                    """
                    UPDATE scheduled_task
                    SET last_status = %s, last_duration_ms = %s,
                        consecutive_failures = 0, retry_attempt = 0, retry_at = NULL,
                        lease_owner = NULL, lease_expires_at = NULL, updated_at = %s
                    WHERE id = %s AND lease_owner = %s AND lease_expires_at > %s
                      AND EXISTS (
                          SELECT 1 FROM task_run tr
                          WHERE tr.id = %s AND tr.task_id = scheduled_task.id
                            AND tr.worker_id = %s AND tr.status = %s
                      )
                    """,
                    (status, duration_ms, now, task_id, self._worker_id, now,
                     run_id, self._worker_id, status),
                )
            else:
                retry_at = (
                    now if retry_immediately else now + timedelta(seconds=retry_delay)
                ) if attempt <= max_retries else None
                cur.execute(
                    """
                    UPDATE scheduled_task
                    SET last_status = %s, last_duration_ms = %s,
                        consecutive_failures = consecutive_failures + 1,
                        retry_attempt = %s, retry_at = %s,
                        lease_owner = NULL, lease_expires_at = NULL,
                        updated_at = %s
                    WHERE id = %s AND lease_owner = %s AND lease_expires_at > %s
                      AND EXISTS (
                          SELECT 1 FROM task_run tr
                          WHERE tr.id = %s AND tr.task_id = scheduled_task.id
                            AND tr.worker_id = %s AND tr.status = %s
                      )
                    """,
                    (status, duration_ms, attempt if retry_at else 0, retry_at, now,
                     task_id, self._worker_id, now, run_id, self._worker_id, status),
                )
            if cur.rowcount != 1:
                self._conn.rollback()
                raise SchedulerLeaseLostError(
                    f"Lease for task {task_id} was lost by worker {self._worker_id}"
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
