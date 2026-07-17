"""Focused scheduler durability tests without a live PostgreSQL dependency."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from services.scheduler.engine import SchedulerEngine, SchedulerLeaseLostError
from services.scheduler.parser import next_run_time


class SchedulerDurabilityTests(TestCase):
    def test_cron_sunday_uses_cron_weekday_numbering(self):
        start = datetime(2026, 7, 11, 4, 0, tzinfo=timezone.utc)  # Saturday
        self.assertEqual(
            next_run_time("0 3 * * 0", after=start),
            datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc),
        )

    def test_execute_passes_structured_arguments_and_records_success(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()
        completed = Mock(returncode=0, stdout="ok", stderr="")

        with patch("services.scheduler.engine.subprocess.run", return_value=completed) as run:
            result = engine._execute_task(
                "run", "task", "metrics", "services.metrics",
                ["--compute", "--all-locations"], 30, None,
            )

        self.assertTrue(result)
        run.assert_called_once_with(
            [__import__("sys").executable, "-m", "services.metrics", "--compute", "--all-locations"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        engine._complete_task.assert_called_once()

    def test_execute_records_spawn_failure_for_retry(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()

        with patch("services.scheduler.engine.subprocess.run", side_effect=OSError("spawn failed")):
            result = engine._execute_task(
                "run", "task", "events", "services.events", ["--process"], 30, None
            )

        self.assertFalse(result)
        self.assertEqual(engine._complete_task.call_args.args[2], "failed")

    def test_completion_rejects_run_not_owned_by_worker(self):
        engine = object.__new__(SchedulerEngine)
        engine._worker_id = "worker-a"
        conn = _CompletionConnection(task_run_rowcount=0)
        engine._conn = conn

        with self.assertRaises(SchedulerLeaseLostError):
            engine._complete_task("task", "run", "completed", 12)

        self.assertTrue(conn.rolled_back)
        self.assertNotIn("INSERT INTO platform_event", conn._cursor.executed_sql)

    def test_completion_rejects_expired_or_replaced_lease(self):
        engine = object.__new__(SchedulerEngine)
        engine._worker_id = "worker-a"
        conn = _CompletionConnection(task_run_rowcount=1, task_rowcount=0)
        engine._conn = conn

        with self.assertRaises(SchedulerLeaseLostError):
            engine._complete_task("task", "run", "completed", 12)

        lease_update = conn._cursor.executed_sql[2]
        self.assertIn("lease_owner = %s", lease_update)
        self.assertIn("lease_expires_at > %s", lease_update)
        self.assertTrue(conn.rolled_back)


class _CompletionCursor:
    def __init__(self, task_run_rowcount, task_rowcount):
        self.task_run_rowcount = task_run_rowcount
        self.task_rowcount = task_rowcount
        self.rowcount = 0
        self.executed_sql = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.executed_sql.append(sql)
        if "UPDATE task_run" in sql:
            self.rowcount = self.task_run_rowcount
        elif "UPDATE scheduled_task" in sql:
            self.rowcount = self.task_rowcount
        else:
            self.rowcount = 1

    def fetchone(self):
        return (1, 3, 60)


class _CompletionConnection:
    def __init__(self, task_run_rowcount, task_rowcount=1):
        self._cursor = _CompletionCursor(task_run_rowcount, task_rowcount)
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        raise AssertionError("lost lease must not commit")
