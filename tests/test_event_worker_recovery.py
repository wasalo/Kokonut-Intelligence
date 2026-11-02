"""Event worker connection recovery checks without PostgreSQL or providers."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import call, patch

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
    def test_idle_worker_sleep_keeps_progress_heartbeat_fresh(self):
        with (
            patch("services.events.cli.pulse_worker_progress") as pulse,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            with self.assertRaises(KeyboardInterrupt):
                events_cli._sleep_with_worker_progress(30)

        pulse.assert_called_once_with()

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
            _args(),
            process_events=True,
            deliver_notifications=True,
            isolated_notification_delivery=True,
            isolated_event_dispatch=True,
        )

    def test_event_worker_does_not_open_notification_connection(self):
        outcome = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}

        with (
            patch(
                "services.core.features.is_enabled",
                side_effect={"event_bus": True, "isolated_event_dispatch": True}.get,
            ),
            patch("services.events.dispatch_worker.run_once", return_value=outcome) as run_once,
            patch("services.common.database.get_connection") as get_connection,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_event_worker(_args()), 0)

        run_once.assert_called_once_with("event-worker-test", 10, 30)
        get_connection.assert_not_called()

    def test_isolated_event_worker_uses_only_dispatch_worker_entrypoint(self):
        feature_states = {
            "event_bus": True,
            "isolated_event_dispatch": True,
            "notification_delivery": False,
        }
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
                    patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
                ):
                    self.assertEqual(cmd_isolated_event_worker(_args()), 0)

                run_once.assert_not_called()
                get_event_store.assert_not_called()
                get_connection.assert_not_called()

    def test_event_dispatch_feature_off_pauses_without_database_or_shared_fallback(self):
        feature_combinations = (
            {"event_bus": False, "isolated_event_dispatch": False},
            {"event_bus": False, "isolated_event_dispatch": True},
            {"event_bus": True, "isolated_event_dispatch": False},
        )
        paused = {
            "status": "paused",
            "reason": "event dispatch requires the isolated worker to be enabled",
        }

        for features in feature_combinations:
            with self.subTest(features=features):
                with (
                    patch("services.core.features.is_enabled", side_effect=features.get),
                    patch("services.events.dispatch_worker.run_once") as run_once,
                    patch("services.events.cli.subprocess.run") as subprocess_run,
                    patch("services.events.backend.get_event_store") as get_event_store,
                    patch("services.common.database.get_connection") as get_connection,
                    patch("services.events.cli.print_json") as print_json,
                ):
                    self.assertEqual(cmd_process(_args()), 0)

                print_json.assert_called_once_with(paused)
                run_once.assert_not_called()
                subprocess_run.assert_not_called()
                get_event_store.assert_not_called()
                get_connection.assert_not_called()

    def test_event_process_launches_filtered_child_without_shared_identity(self):
        args = _args()
        args.batch_size = 7
        features = {"event_bus": True, "isolated_event_dispatch": True}
        child_environment = {
            "KOKONUT_ISOLATED_WORKER_KEY": "event_dispatch",
            "KOKONUT_EVENT_DISPATCH_DATABASE_URL": "postgresql://isolated",
        }

        with (
            patch("services.core.features.is_enabled", side_effect=features.get),
            patch(
                "services.common.worker_environment.isolated_worker_key",
                return_value=None,
            ),
            patch(
                "services.common.worker_environment.scheduled_module_worker_environment",
                return_value=child_environment,
            ) as filtered_environment,
            patch(
                "services.events.cli.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ) as subprocess_run,
            patch("services.events.dispatch_worker.run_once") as run_once,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.common.database.get_connection") as get_connection,
        ):
            self.assertEqual(cmd_process(args), 0)

        command, = subprocess_run.call_args.args
        self.assertEqual(command[1:4], ["-m", "services.events.dispatch_worker", "--run-once"])
        self.assertIn("--batch-size", command)
        self.assertEqual(command[command.index("--batch-size") + 1], "7")
        filtered_environment.assert_called_once_with(
            "services.events", ("--process", "--batch-size", "7")
        )
        self.assertEqual(subprocess_run.call_args.kwargs["env"], child_environment)
        run_once.assert_not_called()
        get_event_store.assert_not_called()
        get_connection.assert_not_called()

    def test_notification_worker_does_not_open_event_store(self):
        with (
            patch("services.core.features.is_enabled", return_value=True),
            patch(
                "services.events.notification_delivery_worker.run_batches",
                return_value={"claimed": 0, "delivered": 0, "failed": 0, "lease_lost": 0},
            ) as deliver,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_notification_worker(_args()), 0)

        deliver.assert_called_once_with("event-worker-test", 10, 30)
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

    def test_supervised_event_worker_idles_without_shared_database_when_isolation_is_off(self):
        features = {"event_bus": True, "isolated_event_dispatch": False}

        with (
            patch("services.core.features.is_enabled", side_effect=features.get),
            patch("services.events.dispatch_worker.run_once") as run_once,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.common.database.get_connection") as get_connection,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_event_worker(_args()), 0)

        run_once.assert_not_called()
        get_event_store.assert_not_called()
        get_connection.assert_not_called()

    def test_combined_worker_runs_only_the_enabled_loop(self):
        outcome = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}
        feature_states = {
            "event_bus": True,
            "isolated_event_dispatch": True,
            "notification_delivery": False,
            "isolated_notification_delivery": False,
        }

        with (
            patch("services.core.features.is_enabled", side_effect=feature_states.get),
            patch("services.events.dispatch_worker.run_once", return_value=outcome) as run_once,
            patch("services.common.database.get_connection") as get_connection,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_worker(_args()), 0)

        run_once.assert_called_once_with("event-worker-test", 10, 30)
        get_connection.assert_not_called()

    def test_notification_worker_can_run_when_event_bus_is_disabled(self):
        feature_states = {
            "event_bus": False,
            "notification_delivery": True,
            "isolated_notification_delivery": True,
        }

        with (
            patch("services.core.features.is_enabled", side_effect=feature_states.get),
            patch(
                "services.events.notification_delivery_worker.run_batches",
                return_value={"claimed": 0, "delivered": 0, "failed": 0, "lease_lost": 0},
            ) as deliver,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_notification_worker(_args()), 0)

        deliver.assert_called_once_with("event-worker-test", 10, 30)
        get_event_store.assert_not_called()

    def test_event_store_failure_discards_bus_and_retries_with_fresh_instance(self):
        outcome = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}
        features = {"event_bus": True, "isolated_event_dispatch": True, "notification_delivery": False}

        with (
            patch("services.core.features.is_enabled", side_effect=features.get),
            patch("services.events.dispatch_worker.run_once", side_effect=[OSError("database connection lost"), outcome]) as run_once,
            patch("services.common.database.get_connection") as get_conn,
            patch("services.events.cli.time.sleep", side_effect=[None, KeyboardInterrupt]),
            patch("services.events.cli.logger.error") as log_error,
        ):
            self.assertEqual(cmd_worker(_args()), 0)

        expected_call = call("event-worker-test", 10, 30)
        self.assertEqual(run_once.call_args_list, [expected_call, expected_call])
        get_conn.assert_not_called()
        log_error.assert_called_once_with("Event worker iteration failed (%s)", "OSError")

    def test_notification_connection_failure_also_recreates_event_bus(self):
        empty_result = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}
        features = {
            "event_bus": True,
            "isolated_event_dispatch": True,
            "notification_delivery": True,
            "isolated_notification_delivery": True,
        }

        with (
            patch("services.core.features.is_enabled", side_effect=features.get),
            patch("services.events.dispatch_worker.run_once", return_value=empty_result) as run_once,
            patch("services.events.notification_delivery_worker.run_batches",
                  side_effect=[OSError("notification database unavailable"), {"claimed": 0}]) as deliver,
            patch("services.events.cli.time.sleep", side_effect=[None, KeyboardInterrupt]),
            patch("services.events.cli.logger.error") as log_error,
        ):
            self.assertEqual(cmd_worker(_args()), 0)

        self.assertEqual(run_once.call_count, 2)
        expected_call = call("event-worker-test", 10, 30)
        self.assertEqual(deliver.call_args_list, [expected_call, expected_call])
        log_error.assert_called_once_with("Event worker iteration failed (%s)", "OSError")

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
                outcome = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}
                features = {"event_bus": True, "isolated_event_dispatch": True}

                with (
                    patch("services.core.features.is_enabled", side_effect=features.get),
                    patch("services.events.dispatch_worker.run_once", return_value=outcome) as run_once,
                    patch("services.events.backend.get_event_store") as get_bus,
                    patch("services.common.database.get_connection") as get_connection,
                    patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
                ):
                    self.assertEqual(cmd_event_worker(args), 0)

                run_once.assert_called_once_with("event-worker-test", 10, lease_seconds)
                get_bus.assert_not_called()
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

    def test_event_process_uses_only_the_isolated_worker_when_marked(self):
        for batch_size in (1, 100):
            with self.subTest(batch_size=batch_size):
                args = _args()
                args.batch_size = batch_size
                features = {"event_bus": True, "isolated_event_dispatch": True}
                outcome = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}

                with (
                    patch("services.core.features.is_enabled", side_effect=features.get),
                    patch(
                        "services.common.worker_environment.isolated_worker_key",
                        return_value="event_dispatch",
                    ),
                    patch("services.events.dispatch_worker.run_once", return_value=outcome) as run_once,
                    patch("services.events.cli.subprocess.run") as subprocess_run,
                    patch("services.events.backend.get_event_store") as get_event_store,
                    patch("services.common.database.get_connection") as get_connection,
                ):
                    self.assertEqual(cmd_process(args), 0)

                run_once.assert_called_once_with("event-worker-test", batch_size, 30)
                subprocess_run.assert_not_called()
                get_event_store.assert_not_called()
                get_connection.assert_not_called()

    def test_persistent_event_worker_accepts_batch_boundaries_and_forwards_them(self):
        for batch_size in (1, 100):
            with self.subTest(batch_size=batch_size):
                args = _args()
                args.batch_size = batch_size
                outcome = {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 0}
                features = {"event_bus": True, "isolated_event_dispatch": True}

                with (
                    patch("services.core.features.is_enabled", side_effect=features.get),
                    patch("services.events.dispatch_worker.run_once", return_value=outcome) as run_once,
                    patch("services.events.backend.get_event_store") as get_event_store,
                    patch("services.common.database.get_connection") as get_connection,
                    patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
                ):
                    self.assertEqual(cmd_event_worker(args), 0)

                run_once.assert_called_once_with("event-worker-test", batch_size, 30)
                get_event_store.assert_not_called()
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

        with (
            patch("services.core.features.is_enabled", return_value=True),
            patch(
                "services.events.notification_delivery_worker.run_batches",
                return_value={"claimed": 0, "delivered": 0, "failed": 0, "lease_lost": 0},
            ) as deliver,
            patch("services.events.backend.get_event_store") as get_event_store,
            patch("services.events.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            self.assertEqual(cmd_notification_worker(args), 0)

        get_event_store.assert_not_called()
        deliver.assert_called_once_with("event-worker-test", 500, 30)

