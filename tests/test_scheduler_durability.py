"""Focused scheduler durability tests without a live PostgreSQL dependency."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from services.scheduler.engine import SchedulerEngine
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
