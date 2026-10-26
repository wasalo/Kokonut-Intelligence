#!/usr/bin/env python3
"""Exercise the real scheduler engine across a disposable PostgreSQL restart."""

from __future__ import annotations

import json
import os
import queue
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _docker(*args: str, check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args], input=stdin, capture_output=True, text=True, check=False
    )
    if check and result.returncode:
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr.strip()}")
    return result


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_log(
    process: subprocess.Popen[str],
    output: queue.Queue[str | None],
    expected: str,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Scheduler worker exited with status {process.returncode}")
        try:
            line = output.get(timeout=min(0.2, deadline - time.monotonic()))
        except queue.Empty:
            continue
        if line is None:
            raise RuntimeError("Scheduler worker output closed before database recovery")
        if expected in line:
            return
    raise TimeoutError(f"Scheduler worker did not log {expected!r} within {timeout:g}s")


def _wait_until_ready(name: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready = _docker(
            "exec",
            name,
            "pg_isready",
            "-h",
            "127.0.0.1",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.25)
    raise TimeoutError("disposable PostgreSQL did not become ready")


def _sql(name: str, statement: str) -> str:
    result = _docker(
        "exec",
        name,
        "psql",
        "-q",
        "-XAt",
        "-F",
        "|",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        "127.0.0.1",
        "-U",
        "kokonut",
        "-d",
        "kokonut_intelligence",
        "-c",
        statement,
    )
    return result.stdout.strip()


def _create_task(name: str, suffix: str) -> str:
    task_name = f"reconnect_probe_{suffix}_{uuid.uuid4().hex[:8]}"
    return _sql(
        name,
        "INSERT INTO scheduled_task "
        "(name, module_path, cron_expression, timeout_seconds, command_args, next_run_at) "
        "VALUES ("
        f"'{task_name}', 'services.events', '* * * * *', 30, "
        "'[\"--process\",\"--batch-size\",\"10\"]'::jsonb, NOW() - INTERVAL '1 minute') "
        "RETURNING id",
    )


def _wait_for_completed(name: str, task_id: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _sql(
            name,
            "SELECT status, COALESCE(worker_id, '') FROM task_run "
            f"WHERE task_id = '{task_id}' ORDER BY started_at DESC LIMIT 1",
        ).split("|")
        if len(values) == 2 and values[0] == "completed" and values[1]:
            return values[1]
        time.sleep(0.25)
    raise TimeoutError("SchedulerEngine did not complete the synthetic task")


def _wait_for_running_claim(
    name: str,
    task_id: str,
    worker_id: str,
    process: subprocess.Popen[str],
    timeout: float,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"claiming scheduler worker exited with status {process.returncode}")
        run_id = _sql(
            name,
            "SELECT id FROM task_run "
            f"WHERE task_id = '{task_id}' AND status = 'running' "
            f"AND worker_id = '{worker_id}' ORDER BY started_at DESC LIMIT 1",
        )
        if run_id:
            return run_id
        time.sleep(0.25)
    raise TimeoutError("scheduler crash probe did not persist its task lease")


def _wait_for_effect_before_task_ack(
    name: str,
    task_id: str,
    event_id: str,
    worker_id: str,
    process: subprocess.Popen[str],
    timeout: float,
) -> str:
    """Wait until the child commits its effect while its scheduler parent is paused."""
    deadline = time.monotonic() + timeout
    last_state = "not observed"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"post-effect scheduler probe exited with status {process.returncode}"
            )
        run_id = _sql(
            name,
            "SELECT id FROM task_run "
            f"WHERE task_id = '{task_id}' AND status = 'running' "
            f"AND worker_id = '{worker_id}' ORDER BY started_at DESC LIMIT 1",
        )
        event_status = _sql(
            name,
            f"SELECT status FROM platform_event WHERE id = '{event_id}'",
        )
        delivery = _sql(
            name,
            "SELECT status || '|' || attempt_count::text || '|' "
            "|| COALESCE(left(last_error, 500), '') FROM event_handler_delivery "
            f"WHERE event_id = '{event_id}'",
        )
        effect_count = _sql(
            name,
            "SELECT count(*) FROM notification_outbox "
            f"WHERE source_event_id = '{event_id}'",
        )
        task_state = _sql(
            name,
            "SELECT status FROM task_run "
            f"WHERE task_id = '{task_id}' ORDER BY started_at DESC LIMIT 1",
        )
        last_state = (
            f"task={task_state!r},event={event_status!r},delivery={delivery!r},"
            f"outbox_rows={effect_count!r}"
        )
        if (
            run_id
            and event_status == "completed"
            and delivery.startswith("success|1|")
            and effect_count == "1"
        ):
            return run_id
        time.sleep(0.25)
    raise TimeoutError(
        "scheduler did not pause after the event and notification effect committed; "
        f"last database state: {last_state}"
    )


def main() -> int:
    image = os.environ.get("SCHEDULER_ENGINE_RECONNECT_POSTGRES_IMAGE", "postgres:16-alpine")
    timeout = float(os.environ.get("SCHEDULER_ENGINE_RECONNECT_TIMEOUT", "45"))
    name = f"kokonut-scheduler-engine-reconnect-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    password = secrets.token_urlsafe(24)
    process: subprocess.Popen[str] | None = None
    output: queue.Queue[str | None] = queue.Queue()
    worker_id = "scheduler-engine-reconnect-probe"
    result: dict[str, object] = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "database_image": image,
        "database_port_binding": "127.0.0.1 only",
        "database_volume": False,
        "candidate_or_legacy_modified": False,
        "external_provider_calls": 0,
    }

    try:
        _docker(
            "run",
            "--detach",
            "--name",
            name,
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--env",
            "POSTGRES_DB=kokonut_intelligence",
            "--env",
            "POSTGRES_USER=kokonut",
            "--env",
            f"POSTGRES_PASSWORD={password}",
            image,
        )
        _wait_until_ready(name, timeout)

        migrations = (
            "116_event_bus.sql",
            "117_task_scheduler.sql",
            "164_scheduler_durability.sql",
            "165_event_bus_durability.sql",
            "297_event_handler_registration_fix.sql",
            "337_scheduler_ownership.sql",
            "371_scheduler_run_windows.sql",
            "375_notification_outbox.sql",
        )
        for migration in migrations:
            sql = (ROOT / "schemas" / "postgres" / migration).read_text()
            _docker(
                "exec",
                "-i",
                name,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-h",
                "127.0.0.1",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                stdin=sql,
            )
        _docker(
            "exec",
            name,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            "127.0.0.1",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            "-c",
            "ALTER TABLE public.notification_outbox "
            "ADD COLUMN IF NOT EXISTS location_id UUID",
        )

        env = os.environ.copy()
        env.update(
            {
                "KOKONUT_ENV": "development",
                "KOKONUT_ENV_SECRETS_LOADED_BY_SCRIPT": "true",
                "PG_HOST": "127.0.0.1",
                "PG_PORT": str(port),
                "PG_DB": "kokonut_intelligence",
                "PG_USER": "kokonut",
                "PG_PASSWORD": password,
                "CLICKHOUSE_ENABLED": "false",
                "KOKONUT_FEATURE_DIRECTUS": "false",
                "KOKONUT_FEATURE_CLICKHOUSE": "false",
                "KOKONUT_FEATURE_GRPC": "false",
                "KOKONUT_FEATURE_METABASE": "false",
                "KOKONUT_FEATURE_MQTT": "false",
                "KOKONUT_FEATURE_PREFECT": "false",
                "KOKONUT_FEATURE_LEGACY_DATASET_SQL": "false",
                "ALERT_WEBHOOK_URL": "",
                "ALERT_SMTP_HOST": "",
                "ALERT_EMAIL_TO": "",
                "DIRECTUS_ADMIN_TOKEN": "",
                "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE": "false",
            }
        )
        worker_code = f"""
from services.scheduler.worker import run_worker
run_worker(tick_interval=1, worker_id={worker_id!r})
"""
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", worker_code],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def collect_output() -> None:
            assert process is not None and process.stdout is not None
            for output_line in process.stdout:
                output.put(output_line.rstrip())
            output.put(None)

        threading.Thread(target=collect_output, daemon=True).start()
        task_before = _create_task(name, "before")
        first_worker = _wait_for_completed(name, task_before, timeout)
        if first_worker != worker_id:
            raise RuntimeError("pre-outage task was not claimed by the probe worker")

        _docker("stop", "--time", "1", name)
        _wait_for_log(process, output, "Scheduler tick failed", timeout)
        if process.poll() is not None:
            raise RuntimeError("scheduler worker exited during the database outage")

        _docker("start", name)
        _wait_until_ready(name, timeout)
        task_after = _create_task(name, "after")
        second_worker = _wait_for_completed(name, task_after, timeout)
        if second_worker != worker_id:
            raise RuntimeError("post-outage task was not claimed by the probe worker")

        process.send_signal(signal.SIGINT)
        process.wait(timeout=5)
        process = None

        crash_task = _create_task(name, "crash")
        crash_worker_id = "scheduler-engine-crash-probe"
        crash_code = f"""
import time
from services.common.database import get_db
from services.scheduler.engine import SchedulerEngine

connection = get_db(connect_timeout=5)
engine = SchedulerEngine(connection, worker_id={crash_worker_id!r})
claim = engine._claim_next()
if claim is None:
    raise SystemExit("no due task was claimed")
print(claim[0], flush=True)
time.sleep(60)
"""
        crash_process = subprocess.Popen(
            [sys.executable, "-u", "-c", crash_code],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            first_run_id = _wait_for_running_claim(
                name, crash_task, crash_worker_id, crash_process, timeout
            )
            crash_process.kill()
            crash_process.wait(timeout=5)
            expired = _sql(
                name,
                "UPDATE scheduled_task SET lease_expires_at = NOW() - INTERVAL '1 second' "
                f"WHERE id = '{crash_task}' AND lease_owner = '{crash_worker_id}' "
                f"AND lease_token = '{first_run_id}' "
                "RETURNING id",
            )
            if expired != crash_task:
                raise RuntimeError("failed to expire the crashed scheduler task lease")
            reclaim_code = """
import json
from services.scheduler.worker import _run_tick

print(json.dumps(_run_tick("scheduler-engine-crash-recovery")), flush=True)
"""
            reclaim = subprocess.run(
                [sys.executable, "-u", "-c", reclaim_code],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if reclaim.returncode:
                raise RuntimeError("replacement scheduler worker failed its recovery tick")
            run_history = _sql(
                name,
                "SELECT string_agg(status || ',' || COALESCE(worker_id, '') || ',' "
                "|| attempt_count::text, ';' ORDER BY started_at) "
                f"FROM task_run WHERE task_id = '{crash_task}'",
            )
            expected_history = (
                "failed,scheduler-engine-crash-probe,1;"
                "completed,scheduler-engine-crash-recovery,2"
            )
            if run_history != expected_history:
                raise RuntimeError(
                    f"unexpected scheduler crash/reclaim history: {run_history}"
                )
        finally:
            if crash_process.poll() is None:
                crash_process.kill()
                crash_process.wait(timeout=5)

        effect_event = str(uuid.uuid4())
        effect_location = str(uuid.uuid4())
        effect_task = _create_task(name, "effect_crash")
        _sql(
            name,
            "INSERT INTO platform_event (id, event_type, payload, status, max_retries) VALUES "
            f"('{effect_event}', 'data_stale', "
            f"'{{\"severity\":\"warning\",\"metric\":\"synthetic_recovery_probe\","
            f"\"value\":1,\"threshold\":0,\"location_id\":\"{effect_location}\"}}'::jsonb, "
            "'pending', 3)",
        )
        effect_worker_id = "scheduler-engine-effect-crash-probe"
        effect_code = f"""
import time
import services.scheduler.engine as scheduler_engine
from services.scheduler.worker import _run_tick

original_run = scheduler_engine.subprocess.run
def pause_after_child(*args, **kwargs):
    result = original_run(*args, **kwargs)
    print("task child returned; scheduler acknowledgement paused", flush=True)
    time.sleep(60)
    return result

scheduler_engine.subprocess.run = pause_after_child
_run_tick({effect_worker_id!r})
"""
        effect_process = subprocess.Popen(
            [sys.executable, "-u", "-c", effect_code],
            cwd=ROOT,
            env={**env, "ALERT_WEBHOOK_URL": "https://notifications.invalid/synthetic"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            effect_run_id = _wait_for_effect_before_task_ack(
                name,
                effect_task,
                effect_event,
                effect_worker_id,
                effect_process,
                timeout,
            )
        except Exception as exc:
            if effect_process.poll() is None:
                effect_process.kill()
                effect_process.wait(timeout=5)
            child_output = (
                effect_process.stdout.read()[-4000:]
                if effect_process.stdout is not None
                else ""
            )
            raise RuntimeError(f"{exc}; scheduler probe output: {child_output}") from exc
        try:
            effect_process.kill()
            effect_process.wait(timeout=5)
            expired = _sql(
                name,
                "UPDATE scheduled_task SET lease_expires_at = NOW() - INTERVAL '1 second' "
                f"WHERE id = '{effect_task}' AND lease_owner = '{effect_worker_id}' "
                f"AND lease_token = '{effect_run_id}' RETURNING id",
            )
            if expired != effect_task:
                raise RuntimeError("failed to expire the post-effect scheduler task lease")
            reclaim = subprocess.run(
                [sys.executable, "-c", reclaim_code],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if reclaim.returncode:
                raise RuntimeError("replacement scheduler worker failed post-effect recovery")
            effect_history = _sql(
                name,
                "SELECT string_agg(status || ',' || COALESCE(worker_id, '') || ',' "
                "|| attempt_count::text, ';' ORDER BY started_at) "
                f"FROM task_run WHERE task_id = '{effect_task}'",
            )
            expected_effect_history = (
                "failed,scheduler-engine-effect-crash-probe,1;"
                "completed,scheduler-engine-crash-recovery,2"
            )
            if effect_history != expected_effect_history:
                raise RuntimeError(
                    f"unexpected post-effect scheduler crash history: {effect_history}"
                )
            effect_rows = _sql(
                name,
                "SELECT count(*), count(DISTINCT id) FROM notification_outbox "
                f"WHERE source_event_id = '{effect_event}'",
            )
            if effect_rows != "1|1":
                raise RuntimeError(
                    f"scheduler retry duplicated the committed notification effect: {effect_rows}"
                )
            delivery = _sql(
                name,
                "SELECT status, attempt_count FROM event_handler_delivery "
                f"WHERE event_id = '{effect_event}'",
            )
            if delivery != "success|1":
                raise RuntimeError(
                    f"scheduler retry redelivered the already-committed event handler: {delivery}"
                )
        finally:
            if effect_process.poll() is None:
                effect_process.kill()
                effect_process.wait(timeout=5)

        result.update(
            {
                "result": "passed",
                "scheduler_engine": "real SchedulerEngine",
                "worker_alive_during_outage": True,
                "database_restart_reconnected": True,
                "task_before_restart_completed": True,
                "task_after_restart_completed": True,
                "both_runs_claimed_by_same_worker": True,
                "scheduler_worker_killed_after_claim": True,
                "scheduler_task_lease_reclaimed": True,
                "scheduler_crash_run_history": run_history,
                "scheduler_crashed_after_effect_commit": True,
                "post_effect_task_run_history": effect_history,
                "post_effect_event_id": effect_event,
                "post_effect_notification_rows": effect_rows,
                "post_effect_event_handler_delivery": delivery,
                "retry_did_not_duplicate_committed_effect": True,
                "task_command": "python -m services.events --process --batch-size 10",
                "worker_id": worker_id,
                "migrations_replayed": list(migrations),
                "limitations": [
                    "Only the scheduler, event bus, notification, and durable ownership migrations were replayed; the full schema ledger was not applied. The disposable notification table adds the nullable location_id column from migration 406 without applying unrelated anomaly-table changes.",
                    "The bounded task ran EventBus processing against an empty synthetic queue; no domain provider or external service ran.",
                    "One crash probe killed the scheduler after its durable lease claim but before it launched the task subprocess. A second killed the parent after the task child processed a synthetic data_stale event and committed its notification outbox effect, while the parent was paused before task completion; the replacement attempt observed the completed event and did not duplicate the notification row.",
                    "The synthetic webhook destination is configuration only; no delivery worker or external network request was run.",
                    "The PostgreSQL container had no volume and was bound only to loopback.",
                ],
            }
        )
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        _docker("rm", "--force", name, check=False)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"result": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise
