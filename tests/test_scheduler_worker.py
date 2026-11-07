"""Scheduler worker recovery tests without a live PostgreSQL dependency."""

from unittest import TestCase
from unittest.mock import Mock, call, patch

from services.scheduler import worker as scheduler_worker
from services.scheduler.worker import _run_tick


class SchedulerWorkerRecoveryTests(TestCase):
    def test_worker_pulses_after_ticks_and_during_idle_sleep(self):
        with (
            patch("services.scheduler.worker._running", True),
            patch("services.scheduler.worker.signal.signal"),
            patch(
                "services.scheduler.worker._run_tick",
                side_effect=lambda _worker_id: setattr(scheduler_worker, "_running", False),
            ),
            patch("services.scheduler.worker.pulse_worker_progress") as pulse,
            patch("services.scheduler.worker.time.sleep"),
        ):
            scheduler_worker.run_worker(tick_interval=1, worker_id="synthetic-worker")

        self.assertEqual(pulse.call_count, 2)

    def test_each_tick_uses_and_closes_a_bounded_connection(self):
        first_conn = Mock()
        second_conn = Mock()
        first_engine = Mock()
        first_engine.tick.side_effect = RuntimeError("database connection lost")
        second_engine = Mock()
        stats = {"launched": 0, "failed": 0, "skipped": 0, "no_resources": 0}
        second_engine.tick.return_value = stats

        with (
            patch("services.scheduler.worker.get_scheduler_connection", side_effect=[first_conn, second_conn]) as get_connection,
            patch("services.scheduler.worker.get_scheduler", side_effect=[first_engine, second_engine]) as get_scheduler,
            patch("services.scheduler.worker.logger.error") as log_error,
        ):
            self.assertIsNone(_run_tick("worker-stable"))
            self.assertEqual(_run_tick("worker-stable"), stats)

        self.assertEqual(get_connection.call_count, 2)
        self.assertEqual(
            get_scheduler.call_args_list,
            [call(first_conn, worker_id="worker-stable"), call(second_conn, worker_id="worker-stable")],
        )
        first_conn.close.assert_called_once()
        second_conn.close.assert_called_once()
        first_conn.rollback.assert_not_called()
        log_error.assert_called_once_with("Scheduler tick failed (%s)", "RuntimeError")

    def test_connection_failure_is_retried_by_the_next_tick(self):
        conn = Mock()
        engine = Mock()
        engine.tick.return_value = {"launched": 0, "failed": 0, "skipped": 0, "no_resources": 0}

        with (
            patch("services.scheduler.worker.get_scheduler_connection", side_effect=[OSError("database unavailable"), conn]),
            patch("services.scheduler.worker.get_scheduler", return_value=engine),
            patch("services.scheduler.worker.logger.error"),
        ):
            self.assertIsNone(_run_tick("worker-stable"))
            self.assertIsNotNone(_run_tick("worker-stable"))

        engine.tick.assert_called_once()
        conn.close.assert_called_once()

    def test_close_failure_is_contained_and_redacted(self):
        conn = Mock()
        conn.close.side_effect = RuntimeError("postgresql://operator:secret@db.internal/kokonut")
        engine = Mock()
        stats = {"launched": 0, "failed": 0, "skipped": 0, "no_resources": 0}
        engine.tick.return_value = stats

        with (
            patch("services.scheduler.worker.get_scheduler_connection", return_value=conn),
            patch("services.scheduler.worker.get_scheduler", return_value=engine),
            patch("services.scheduler.worker.logger.warning") as log_warning,
        ):
            self.assertEqual(_run_tick("worker-stable"), stats)

        log_warning.assert_called_once_with(
            "Failed to close scheduler tick connection (%s)", "RuntimeError"
        )

