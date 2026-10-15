"""Event worker connection recovery checks without PostgreSQL or providers."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, call, patch

from services.events.cli import cmd_worker


def _args():
    return SimpleNamespace(
        poll_interval=0.01,
        batch_size=10,
        worker_id="event-worker-test",
        lease_seconds=30,
    )


class EventWorkerRecoveryTests(TestCase):
    def test_event_store_failure_discards_bus_and_retries_with_fresh_instance(self):
        failed_bus = Mock()
        failed_bus.process_pending.side_effect = OSError("database connection lost")
        recovered_bus = Mock()
        recovered_bus.process_pending.return_value = {"processed": 0, "failed": 0}
        notification_conn = object()

        with (
            patch("services.events.backend.get_event_store", side_effect=[failed_bus, recovered_bus]) as get_bus,
            patch("services.common.database.get_connection", return_value=nullcontext(notification_conn)) as get_conn,
            patch("services.events.notification_outbox.deliver_batch", return_value={"claimed": 0}) as deliver,
            patch("services.events.cli.time.sleep", side_effect=[None, KeyboardInterrupt]),
            patch("services.events.cli.logger.exception") as log_exception,
        ):
            self.assertEqual(cmd_worker(_args()), 0)

        self.assertEqual(
            get_bus.call_args_list,
            [
                call(lease_seconds=30, connect_timeout=5),
                call(lease_seconds=30, connect_timeout=5),
            ],
        )
        failed_bus.close.assert_called_once()
        recovered_bus.close.assert_called_once()
        failed_bus.process_pending.assert_called_once_with(10, "event-worker-test")
        recovered_bus.process_pending.assert_called_once_with(10, "event-worker-test")
        get_conn.assert_called_once_with(connect_timeout=5)
        deliver.assert_called_once_with(notification_conn, "event-worker-test", 10)
        log_exception.assert_called_once_with("Event worker iteration failed")

    def test_notification_connection_failure_also_recreates_event_bus(self):
        first_bus = Mock()
        second_bus = Mock()
        empty_result = {"processed": 0, "failed": 0}
        first_bus.process_pending.return_value = empty_result
        second_bus.process_pending.return_value = empty_result
        notification_conn = object()

        with (
            patch("services.events.backend.get_event_store", side_effect=[first_bus, second_bus]) as get_bus,
            patch(
                "services.common.database.get_connection",
                side_effect=[OSError("notification database unavailable"), nullcontext(notification_conn)],
            ) as get_conn,
            patch("services.events.notification_outbox.deliver_batch", return_value={"claimed": 0}) as deliver,
            patch("services.events.cli.time.sleep", side_effect=[None, KeyboardInterrupt]),
            patch("services.events.cli.logger.exception") as log_exception,
        ):
            self.assertEqual(cmd_worker(_args()), 0)

        self.assertEqual(get_bus.call_count, 2)
        self.assertEqual(
            get_bus.call_args_list,
            [
                call(lease_seconds=30, connect_timeout=5),
                call(lease_seconds=30, connect_timeout=5),
            ],
        )
        first_bus.close.assert_called_once()
        second_bus.close.assert_called_once()
        self.assertEqual(get_conn.call_count, 2)
        self.assertEqual(get_conn.call_args_list, [call(connect_timeout=5), call(connect_timeout=5)])
        deliver.assert_called_once_with(notification_conn, "event-worker-test", 10)
        log_exception.assert_called_once_with("Event worker iteration failed")

    def test_worker_rejects_nonpositive_poll_interval(self):
        args = _args()
        args.poll_interval = 0

        with patch("services.events.backend.get_event_store") as get_bus:
            with self.assertRaisesRegex(ValueError, "poll_interval must be positive"):
                cmd_worker(args)

        get_bus.assert_not_called()

