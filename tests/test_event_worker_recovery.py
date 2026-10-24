"""Event worker connection recovery checks without PostgreSQL or providers."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, call, patch

from services.events import cli as events_cli
from services.events.cli import cmd_event_worker, cmd_notification_worker, cmd_worker


def _args():
    return SimpleNamespace(
        poll_interval=0.01,
        batch_size=10,
        worker_id="event-worker-test",
        lease_seconds=30,
    )


class EventWorkerRecoveryTests(TestCase):
    def test_cli_selects_independent_worker_modes(self):
        for flag, command in (
            ("--worker", events_cli.cmd_worker),
            ("--event-worker", events_cli.cmd_event_worker),
            ("--notification-worker", events_cli.cmd_notification_worker),
        ):
            with self.subTest(flag=flag):
                with patch.object(events_cli.sys, "argv", ["services.events", flag]):
                    with patch.object(events_cli, command.__name__, return_value=0) as handler:
                        with self.assertRaises(SystemExit) as raised:
                            events_cli.main()

                self.assertEqual(raised.exception.code, 0)
                handler.assert_called_once()

    def test_compatibility_worker_runs_event_and_notification_modes(self):
        with patch("services.events.cli._run_worker", return_value=0) as run_worker:
            self.assertEqual(cmd_worker(_args()), 0)

        run_worker.assert_called_once_with(
            _args(), process_events=True, deliver_notifications=True
        )

    def test_event_worker_does_not_open_notification_connection(self):
        bus = Mock()
        bus.process_pending.return_value = {"processed": 0, "failed": 0}

        with (
            patch("services.events.backend.get_event_store", return_value=bus),
            patch("services.common.database.get_connection") as get_connection,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_event_worker(_args()), 0)

        bus.process_pending.assert_called_once_with(10, "event-worker-test")
        bus.close.assert_called_once()
        get_connection.assert_not_called()

    def test_notification_worker_does_not_open_event_store(self):
        connection = object()

        with (
            patch("services.common.database.get_connection", return_value=nullcontext(connection)),
            patch("services.events.notification_outbox.deliver_batch", return_value={"claimed": 0}) as deliver,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_notification_worker(_args()), 0)

        deliver.assert_called_once_with(connection, "event-worker-test", 10)
        get_event_store.assert_not_called()

    def test_event_worker_feature_off_returns_before_opening_connections(self):
        with (
            patch("services.core.features.is_enabled", return_value=False),
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.common.database.get_connection") as get_connection,
        ):
            self.assertEqual(cmd_event_worker(_args()), 0)

        get_event_store.assert_not_called()
        get_connection.assert_not_called()

    def test_combined_worker_runs_only_the_enabled_loop(self):
        bus = Mock()
        bus.process_pending.return_value = {"processed": 0, "failed": 0}
        feature_states = {"event_bus": True, "notification_delivery": False}

        with (
            patch("services.core.features.is_enabled", side_effect=feature_states.get),
            patch("services.events.backend.get_event_store", return_value=bus),
            patch("services.common.database.get_connection") as get_connection,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_worker(_args()), 0)

        bus.process_pending.assert_called_once_with(10, "event-worker-test")
        bus.close.assert_called_once()
        get_connection.assert_not_called()

    def test_notification_worker_can_run_when_event_bus_is_disabled(self):
        connection = object()
        feature_states = {"event_bus": False, "notification_delivery": True}

        with (
            patch("services.core.features.is_enabled", side_effect=feature_states.get),
            patch("services.common.database.get_connection", return_value=nullcontext(connection)),
            patch("services.events.notification_outbox.deliver_batch", return_value={"claimed": 0}) as deliver,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_notification_worker(_args()), 0)

        deliver.assert_called_once_with(connection, "event-worker-test", 10)
        get_event_store.assert_not_called()

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
            patch("services.events.cli.logger.error") as log_error,
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
        log_error.assert_called_once_with("Event worker iteration failed (%s)", "OSError")

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
            patch("services.events.cli.logger.error") as log_error,
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
        log_error.assert_called_once_with("Event worker iteration failed (%s)", "OSError")

    def test_bus_close_failure_logs_only_exception_class(self):
        bus = Mock()
        bus.process_pending.return_value = {"processed": 0, "failed": 0}
        bus.close.side_effect = RuntimeError("postgresql://operator:secret@db.internal/kokonut")

        with (
            patch("services.events.backend.get_event_store", return_value=bus),
            patch("services.common.database.get_connection") as get_connection,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
            patch("services.events.cli.logger.warning") as log_warning,
        ):
            self.assertEqual(cmd_event_worker(_args()), 0)

        get_connection.assert_not_called()
        log_warning.assert_called_once_with(
            "Failed to close event worker bus (%s)", "RuntimeError"
        )

    def test_worker_rejects_nonpositive_poll_interval(self):
        args = _args()
        args.poll_interval = 0

        with patch("services.events.backend.get_event_store") as get_bus:
            with self.assertRaisesRegex(ValueError, "poll_interval must be positive"):
                cmd_worker(args)

        get_bus.assert_not_called()

