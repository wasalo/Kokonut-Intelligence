"""Focused scheduler durability tests without a live PostgreSQL dependency."""

import subprocess
import sys
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from services.scheduler import engine as scheduler_engine
from services.scheduler.engine import SchedulerEngine, SchedulerLeaseLostError
from services.scheduler.parser import next_run_time


class SchedulerDurabilityTests(TestCase):
    def test_isolated_tick_skips_unmapped_and_invalid_tasks_before_claiming_mapped_work(self):
        unsupported_id = "00000000-0000-0000-0000-000000000001"
        invalid_id = "00000000-0000-0000-0000-000000000002"
        mapped_id = "00000000-0000-0000-0000-000000000003"
        location_id = "a9aa6466-0754-4b7c-b20c-155a81134eaa"
        rows = [
            (unsupported_id, "services.metrics", ["--compute", "--all", "--location-id", location_id]),
            (invalid_id, "services.ingestion.climate_data", ["--all"]),
            (mapped_id, "services.ingestion.weather_worker", ["--location-id", location_id]),
        ]
        conn = _SchedulerClaimConnection(
            enabled_tasks=rows,
            candidates=[
                _scheduler_claim_row(unsupported_id, "metrics", rows[0][1], rows[0][2], "high"),
                _scheduler_claim_row(invalid_id, "climate", rows[1][1], rows[1][2], "high"),
                _scheduler_claim_row(mapped_id, "weather", rows[2][1], rows[2][2], "normal"),
            ],
        )
        engine = SchedulerEngine(conn, worker_id="test-worker")

        with (
            patch("services.scheduler.engine.scheduler_database_is_selected", return_value=True),
            patch.object(engine, "_execute_task", return_value=True) as execute,
        ):
            stats = engine.tick()

        self.assertEqual(stats, {"launched": 1, "failed": 0, "skipped": 2, "no_resources": 0})
        self.assertEqual([claim[1] for claim in conn.claimed_task_runs], [mapped_id])
        self.assertEqual([update[-1] for update in conn.claim_updates], [mapped_id])
        self.assertEqual(execute.call_args.args[1], mapped_id)
        selection_queries = [
            (sql, params)
            for sql, params in conn.executed
            if "SELECT st.id, st.name, st.module_path" in sql
        ]
        self.assertTrue(all("ANY(%s::uuid[])" in sql for sql, _ in selection_queries))
        self.assertTrue(all(params[1] == [unsupported_id, invalid_id] for _, params in selection_queries))

    def test_isolated_claim_rechecks_locked_candidate_and_excludes_race_without_mutation(self):
        raced_id = "00000000-0000-0000-0000-000000000011"
        mapped_id = "00000000-0000-0000-0000-000000000012"
        location_id = "a9aa6466-0754-4b7c-b20c-155a81134eaa"
        mapped_args = ["--location-id", location_id]
        raced_row = _scheduler_claim_row(
            raced_id, "metrics", "services.metrics", ["--compute", "--all", "--location-id", location_id], "high"
        )
        mapped_row = _scheduler_claim_row(
            mapped_id, "weather", "services.ingestion.weather_worker", mapped_args, "normal"
        )
        # The unsupported task is enabled after the per-tick inventory scan.
        conn = _SchedulerClaimConnection(enabled_tasks=[], candidates=[raced_row, mapped_row])
        engine = SchedulerEngine(conn, worker_id="test-worker")
        isolated_skips = {}

        with patch.object(engine, "_execute_task", return_value=True) as execute:
            claimed = engine._claim_next(isolated_skips)

        self.assertEqual(claimed[1], mapped_id)
        self.assertEqual(isolated_skips, {raced_id: "unmapped_worker_identity"})
        self.assertEqual([claim[1] for claim in conn.claimed_task_runs], [mapped_id])
        self.assertEqual([update[-1] for update in conn.claim_updates], [mapped_id])
        selection_queries = [
            (sql, params)
            for sql, params in conn.executed
            if "SELECT st.id, st.name, st.module_path" in sql
        ]
        self.assertEqual(len(selection_queries), 2)
        self.assertNotIn("ANY(%s::uuid[])", selection_queries[0][0])
        self.assertIn("ANY(%s::uuid[])", selection_queries[1][0])
        self.assertEqual(selection_queries[1][1][1], [raced_id])
        self.assertNotIn(raced_id, [claim[1] for claim in conn.claimed_task_runs])
        execute.assert_not_called()

    def test_event_dispatch_operation_resolves_to_its_isolated_database_identity(self):
        from services.common.worker_environment import scheduled_module_worker_key

        self.assertEqual(scheduled_module_worker_key("services.events", ["--process"]), "event_dispatch")
        self.assertEqual(
            scheduled_module_worker_key("services.events", ["--notification-process"]),
            "notification_delivery",
        )

    def test_isolated_recovery_cleans_expired_disabled_task_without_claiming_it(self):
        disabled_id = "00000000-0000-0000-0000-000000000021"
        conn = _SchedulerClaimConnection(
            enabled_tasks=[],
            candidates=[],
            expired_tasks=[
                (disabled_id, "services.metrics", ["--compute", "--all"])
            ],
        )
        engine = SchedulerEngine(conn, worker_id="test-worker")
        isolated_skips = {}

        claimed = engine._claim_next(isolated_skips)

        self.assertIsNone(claimed)
        self.assertEqual(isolated_skips, {})
        self.assertEqual(conn.recovered_task_runs[0][1], disabled_id)
        self.assertEqual(conn.recovered_schedule_rows[0][3], disabled_id)
        self.assertEqual(conn.claimed_task_runs, [])
        self.assertEqual(conn.claim_updates, [])

    def test_cron_sunday_uses_cron_weekday_numbering(self):
        start = datetime(2026, 7, 11, 4, 0, tzinfo=timezone.utc)  # Saturday
        self.assertEqual(
            next_run_time("0 3 * * 0", after=start),
            datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc),
        )

    def test_bounded_scheduler_task_wait_pulses_the_supervised_worker(self):
        process = Mock()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["synthetic-command"], 5),
            ("complete", ""),
        ]
        with (
            patch("services.scheduler.engine.time.monotonic", side_effect=(0, 1, 2)),
            patch("services.scheduler.engine.pulse_worker_progress") as pulse,
        ):
            output = scheduler_engine._communicate_with_progress(
                process, ["synthetic-command"], 10
            )

        self.assertEqual(output, ("complete", ""))
        pulse.assert_called_once_with()

    def test_execute_passes_structured_arguments_and_records_success(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()
        completed = Mock(returncode=0, stdout="ok", stderr="")
        completed.communicate.return_value = ("ok", "")

        child_env = {"PATH": "/synthetic/bin"}
        with (
            patch("services.scheduler.engine.scheduled_module_worker_environment", return_value=child_env),
            patch("services.scheduler.engine.subprocess.Popen", return_value=completed) as spawn,
        ):
            result = engine._execute_task(
                "run",
                "task",
                "metrics",
                "services.metrics",
                ["--compute", "--all", "--location-id", "a9aa6466-0754-4b7c-b20c-155a81134eaa"],
                30,
                None,
            )

        self.assertTrue(result)
        spawn.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "services.metrics",
                "--compute",
                "--all",
                "--location-id",
                "a9aa6466-0754-4b7c-b20c-155a81134eaa",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=child_env,
        )
        completed.communicate.assert_called_once_with(timeout=5)
        engine._complete_task.assert_called_once()

    def test_noi_snapshot_dispatch_forwards_only_its_worker_secret_key(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()
        completed = Mock(returncode=0, stdout='{"reconciled":1}', stderr="")
        completed.communicate.return_value = ('{"reconciled":1}', "")
        child_env = {"KOKONUT_NOI_SNAPSHOT_WORKER_CREDENTIAL": "synthetic"}
        with (
            patch("services.scheduler.engine.scheduled_module_worker_environment", return_value=child_env) as environment,
            patch("services.scheduler.engine.subprocess.Popen", return_value=completed) as spawn,
        ):
            result = engine._execute_task(
                "run", "task", "noi_snapshots",
                "services.metrics.noi_snapshot_worker",
                ["--location-id", "a9aa6466-0754-4b7c-b20c-155a81134eaa"],
                30, None,
            )

        self.assertTrue(result)
        environment.assert_called_once_with(
            "services.metrics.noi_snapshot_worker",
            ("--location-id", "a9aa6466-0754-4b7c-b20c-155a81134eaa"),
        )
        self.assertIs(spawn.call_args.kwargs["env"], child_env)

    def test_execute_records_spawn_failure_for_retry(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()

        with patch(
            "services.scheduler.engine.subprocess.Popen",
            side_effect=OSError("synthetic spawn diagnostic marker"),
        ):
            result = engine._execute_task("run", "task", "events", "services.events", ["--process"], 30, None)

        self.assertFalse(result)
        self.assertEqual(engine._complete_task.call_args.args[2], "failed")
        self.assertEqual(
            engine._complete_task.call_args.args[4],
            "Scheduled task execution failed (OSError)",
        )
        self.assertTrue(engine._complete_task.call_args.kwargs["retry_immediately"])

    def test_execute_failure_redacts_child_stdout_and_stderr(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()
        failed = Mock(
            returncode=9,
            stdout="synthetic stdout diagnostic marker",
            stderr="synthetic stderr diagnostic marker",
        )
        failed.communicate.return_value = (
            "synthetic stdout diagnostic marker",
            "synthetic stderr diagnostic marker",
        )

        with (
            patch(
                "services.scheduler.engine.scheduled_module_worker_environment",
                return_value={"PATH": "/synthetic/bin"},
            ),
                patch("services.scheduler.engine.subprocess.Popen", return_value=failed),
        ):
            result = engine._execute_task(
                "run", "task", "events", "services.events", ["--process"], 30, None
            )

        self.assertFalse(result)
        self.assertEqual(engine._complete_task.call_args.args[2], "failed")
        self.assertEqual(
            engine._complete_task.call_args.kwargs["error"],
            "Scheduled command failed (exit code 9)",
        )
        self.assertNotIn("synthetic", repr(engine._complete_task.call_args))

    def test_execute_rejects_unregistered_module_before_spawn(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()

        with patch("services.scheduler.engine.subprocess.Popen") as run:
            result = engine._execute_task("run", "task", "untrusted", "os", ["--help"], 30, None)

        self.assertFalse(result)
        run.assert_not_called()
        self.assertEqual(engine._complete_task.call_args.args[2], "failed")

    def test_execute_rejects_invalid_command_without_spawning_or_retrying(self):
        engine = object.__new__(SchedulerEngine)
        engine._complete_task = Mock()

        with patch("services.scheduler.engine.subprocess.Popen") as run:
            result = engine._execute_task(
                "run",
                "task",
                "climate",
                "services.ingestion.climate_data",
                ["--all"],
                30,
                None,
            )

        self.assertFalse(result)
        run.assert_not_called()
        self.assertEqual(engine._complete_task.call_args.args[2], "failed")
        self.assertFalse(engine._complete_task.call_args.kwargs["retryable"])

    def test_nonretryable_command_failure_has_no_retry_deadline(self):
        engine = object.__new__(SchedulerEngine)
        engine._worker_id = "worker-a"
        conn = _RetryPolicyConnection()
        engine._conn = conn

        engine._complete_task("task", "run", "failed", 5, "invalid command", retryable=False)

        schedule_update = conn.cursor_value.executed[2]
        self.assertIn("UPDATE scheduled_task", schedule_update[0])
        self.assertEqual(schedule_update[1][2], 0)
        self.assertIsNone(schedule_update[1][3])
        self.assertIn("one_shot_completed_at", schedule_update[0])
        self.assertTrue(conn.committed)

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
        self.assertIn("one_shot_completed_at", lease_update)
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


class _RetryPolicyCursor:
    def __init__(self):
        self.rowcount = 1
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return (1, 3, 60)


class _RetryPolicyConnection:
    def __init__(self):
        self.cursor_value = _RetryPolicyCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True


def _scheduler_claim_row(task_id, name, module_path, command_args, priority):
    return (
        task_id,
        name,
        module_path,
        command_args,
        "0 * * * *",
        priority,
        30,
        0,
        None,
        False,
        datetime.now(timezone.utc),
    )


class _SchedulerClaimCursor:
    def __init__(self, conn):
        self.conn = conn
        self._row = None
        self._rows = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        self._row = None
        self._rows = None
        if "SELECT id, module_path, command_args" in sql:
            self._rows = list(self.conn.enabled_tasks)
        elif "SELECT st.id" in sql and "last_status = 'running'" in sql:
            self._row = next(
                (
                    (task[0],)
                    for task in self.conn.expired_tasks
                    if task[0] not in self.conn.recovered_ids
                ),
                None,
            )
        elif "SELECT st.id, st.name, st.module_path" in sql:
            excluded = params[1] if "ANY(%s::uuid[])" in sql else []
            self._row = next(
                (
                    candidate
                    for candidate in self.conn.candidates
                    if candidate[0] not in self.conn.claimed_ids
                    and candidate[0] not in excluded
                ),
                None,
            )
        elif "INSERT INTO task_run" in sql:
            self.conn.claimed_task_runs.append(params)
            self.conn.claimed_ids.add(str(params[1]))
        elif "UPDATE task_run tr SET status = 'failed'" in sql:
            self.conn.recovered_task_runs.append(params)
            self.conn.recovered_ids.add(str(params[1]))
        elif "UPDATE scheduled_task SET" in sql and "retry_at = CASE" in sql:
            self.conn.recovered_schedule_rows.append(params)
        elif "UPDATE scheduled_task SET" in sql and "last_run_at = %s" in sql:
            self.conn.claim_updates.append(params)

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows or []


class _SchedulerClaimConnection:
    def __init__(self, enabled_tasks, candidates, expired_tasks=None):
        self.enabled_tasks = enabled_tasks
        self.candidates = candidates
        self.expired_tasks = expired_tasks or []
        self.executed = []
        self.claimed_task_runs = []
        self.claim_updates = []
        self.claimed_ids = set()
        self.recovered_task_runs = []
        self.recovered_schedule_rows = []
        self.recovered_ids = set()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _SchedulerClaimCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
