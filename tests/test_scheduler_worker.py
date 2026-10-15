"""Scheduler worker recovery tests without a live PostgreSQL dependency."""

from unittest import TestCase
from unittest.mock import Mock, call, patch

from services.scheduler.worker import _run_tick


class SchedulerWorkerRecoveryTests(TestCase):
    def test_each_tick_uses_and_closes_a_bounded_connection(self):
        first_conn = Mock()
        second_conn = Mock()
        first_engine = Mock()
        first_engine.tick.side_effect = RuntimeError("database connection lost")
        second_engine = Mock()
        stats = {"launched": 0, "failed": 0, "skipped": 0, "no_resources": 0}
        second_engine.tick.return_value = stats

        with (
            patch("services.scheduler.worker.get_db", side_effect=[first_conn, second_conn]) as get_db,
            patch("services.scheduler.worker.get_scheduler", side_effect=[first_engine, second_engine]) as get_scheduler,
            patch("services.scheduler.worker.logger.exception") as log_exception,
        ):
            self.assertIsNone(_run_tick("worker-stable"))
            self.assertEqual(_run_tick("worker-stable"), stats)

        self.assertEqual(get_db.call_args_list, [call(connect_timeout=5), call(connect_timeout=5)])
        self.assertEqual(
            get_scheduler.call_args_list,
            [call(first_conn, worker_id="worker-stable"), call(second_conn, worker_id="worker-stable")],
        )
        first_conn.close.assert_called_once()
        second_conn.close.assert_called_once()
        first_conn.rollback.assert_not_called()
        log_exception.assert_called_once_with("Scheduler tick failed")

    def test_connection_failure_is_retried_by_the_next_tick(self):
        conn = Mock()
        engine = Mock()
        engine.tick.return_value = {"launched": 0, "failed": 0, "skipped": 0, "no_resources": 0}

        with (
            patch("services.scheduler.worker.get_db", side_effect=[OSError("database unavailable"), conn]),
            patch("services.scheduler.worker.get_scheduler", return_value=engine),
            patch("services.scheduler.worker.logger.exception"),
        ):
            self.assertIsNone(_run_tick("worker-stable"))
            self.assertIsNotNone(_run_tick("worker-stable"))

        engine.tick.assert_called_once()
        conn.close.assert_called_once()

