"""Event worker connection recovery checks without PostgreSQL or providers."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, call, patch

from services.events import cli as events_cli
from services.events.cli import (
    cmd_event_worker,
    cmd_isolated_event_worker,
    cmd_notification_process,
    cmd_notification_worker,
    cmd_process,
    cmd_worker,
)


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
            ("--isolated-event-worker", events_cli.cmd_isolated_event_worker),
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

    def test_isolated_event_worker_uses_only_dispatch_worker_entrypoint(self):
        feature_states = {"event_bus": True, "isolated_event_dispatch": True,
                          "notification_delivery": False}
        with (
            patch("services.core.features.is_enabled", side_effect=feature_states.get),
            patch(
                "services.events.dispatch_worker.run_once",
                return_value={"processed": 0, "failed": 0},
            ) as run_once,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_isolated_event_worker(_args()), 0)

        run_once.assert_called_once_with("event-worker-test", 10, 30)
        get_event_store.assert_not_called()

    def test_isolated_event_worker_feature_off_does_not_fall_back_to_shared_database(self):
        for feature_states in (
            {"event_bus": True, "isolated_event_dispatch": False},
            {"event_bus": False, "isolated_event_dispatch": True},
        ):
            with self.subTest(features=feature_states):
                with (
                    patch("services.core.features.is_enabled", side_effect=feature_states.get),
                    patch("services.events.dispatch_worker.run_once") as run_once,
                    patch("services.events.backend.get_event_store") as get_event_store,
                    patch("services.common.database.get_connection") as get_connection,
                ):
                    self.assertEqual(cmd_isolated_event_worker(_args()), 0)

                run_once.assert_not_called()
                get_event_store.assert_not_called()
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

    def test_workers_reject_invalid_poll_intervals_before_features_or_connections(self):
        for worker in (cmd_worker, cmd_event_worker, cmd_notification_worker):
            for poll_interval in (float("nan"), float("inf"), -float("inf"), 0, -1):
                with self.subTest(worker=worker.__name__, poll_interval=poll_interval):
                    args = _args()
                    args.poll_interval = poll_interval

                    with (
                        patch("services.core.features.is_enabled") as is_enabled,
                        patch("services.events.backend.get_event_store") as get_bus,
                        patch("services.common.database.get_connection") as get_connection,
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "poll_interval must be finite and positive"
                        ):
                            worker(args)

                    is_enabled.assert_not_called()
                    get_bus.assert_not_called()
                    get_connection.assert_not_called()

    def test_workers_reject_invalid_leases_before_features_or_connections(self):
        for worker in (cmd_worker, cmd_event_worker, cmd_notification_worker):
            for lease_seconds in (29, 3601, 0, -1, True, False, 30.0, "30", None):
                with self.subTest(worker=worker.__name__, lease_seconds=lease_seconds):
                    args = _args()
                    args.lease_seconds = lease_seconds

                    with (
                        patch("services.core.features.is_enabled") as is_enabled,
                        patch("services.events.backend.get_event_store") as get_bus,
                        patch("services.common.database.get_connection") as get_connection,
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "lease must be between 30 and 3600"
                        ):
                            worker(args)

                    is_enabled.assert_not_called()
                    get_bus.assert_not_called()
                    get_connection.assert_not_called()

    def test_event_worker_accepts_lease_boundaries_and_forwards_them(self):
        for lease_seconds in (30, 3600):
            with self.subTest(lease_seconds=lease_seconds):
                args = _args()
                args.lease_seconds = lease_seconds
                bus = Mock()
                bus.process_pending.return_value = {"processed": 0, "failed": 0}

                with (
                    patch("services.core.features.is_enabled", return_value=True),
                    patch("services.events.backend.get_event_store", return_value=bus) as get_bus,
                    patch("services.common.database.get_connection") as get_connection,
                    patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
                ):
                    self.assertEqual(cmd_event_worker(args), 0)

                get_bus.assert_called_once_with(lease_seconds=lease_seconds, connect_timeout=5)
                bus.process_pending.assert_called_once_with(10, "event-worker-test")
                bus.close.assert_called_once()
                get_connection.assert_not_called()

    def test_event_entrypoints_reject_invalid_batch_sizes_before_connections(self):
        for batch_size in (0, -1, 101):
            for command in (cmd_process, cmd_worker, cmd_event_worker):
                with self.subTest(batch_size=batch_size, command=command.__name__):
                    args = _args()
                    args.batch_size = batch_size

                    with (
                        patch("services.core.features.is_enabled") as is_enabled,
                        patch("services.events.backend.get_event_store") as get_bus,
                        patch("services.common.database.get_connection") as get_connection,
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "batch_size must be between 1 and 100"
                        ):
                            command(args)

                    is_enabled.assert_not_called()
                    get_bus.assert_not_called()
                    get_connection.assert_not_called()

    def test_event_process_accepts_batch_boundaries_and_forwards_them(self):
        for batch_size in (1, 100):
            with self.subTest(batch_size=batch_size):
                args = _args()
                args.batch_size = batch_size
                bus = Mock()
                bus.process_pending.return_value = {"failed": 0}

                with (
                    patch("services.events.backend.get_event_store", return_value=bus),
                    patch("services.events.cli.print_json"),
                ):
                    self.assertEqual(cmd_process(args), 0)

                bus.process_pending.assert_called_once_with(
                    batch_size=batch_size,
                    worker_id="event-worker-test",
                )
                bus.close.assert_called_once()

    def test_persistent_event_worker_accepts_batch_boundaries_and_forwards_them(self):
        for batch_size in (1, 100):
            with self.subTest(batch_size=batch_size):
                args = _args()
                args.batch_size = batch_size
                bus = Mock()
                bus.process_pending.return_value = {"processed": 0, "failed": 0}

                with (
                    patch("services.core.features.is_enabled", return_value=True),
                    patch("services.events.backend.get_event_store", return_value=bus),
                    patch("services.common.database.get_connection") as get_connection,
                    patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
                ):
                    self.assertEqual(cmd_event_worker(args), 0)

                bus.process_pending.assert_called_once_with(batch_size, "event-worker-test")
                bus.close.assert_called_once()
                get_connection.assert_not_called()

    def test_notification_process_rejects_above_provider_bound_before_connection(self):
        args = _args()
        args.batch_size = 501

        with patch("services.common.database.get_connection") as get_connection:
            with self.assertRaisesRegex(
                ValueError, "batch_size must be between 1 and 500"
            ):
                cmd_notification_process(args)

        get_connection.assert_not_called()

    def test_notification_only_worker_keeps_its_500_item_bound(self):
        args = _args()
        args.batch_size = 500
        connection = object()

        with (
            patch("services.core.features.is_enabled", return_value=True),
            patch("services.common.database.get_connection", return_value=nullcontext(connection)),
            patch("services.events.notification_outbox.deliver_batch", return_value={"claimed": 0}) as deliver,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_notification_worker(args), 0)

        get_event_store.assert_not_called()
        deliver.assert_called_once_with(connection, "event-worker-test", 500)

