"""Focused contracts for Kernel child-process shutdown and failure handling."""

from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from services.common.worker_environment import (
    SCHEDULED_WORKER_KEYS,
    worker_subprocess_environment,
)
from services.core import runtime, worker_progress


class _Process:
    def __init__(self, pid: int, exit_code: int | None = None, timeout: bool = False):
        self.pid = pid
        self.exit_code = exit_code
        self.timeout = timeout
        self.wait_calls: list[float | None] = []

    def poll(self):
        return self.exit_code

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if timeout is not None and self.timeout:
            self.timeout = False
            raise subprocess.TimeoutExpired("kernel-child", timeout)
        return self.exit_code


def test_default_supervisor_heartbeat_uses_user_writable_state_path():
    expected = Path.home() / ".local" / "state" / "kokonut" / "worker-progress" / "supervisor.json"

    assert Path(runtime.DEFAULT_SUPERVISOR_HEARTBEAT_FILE) == expected
    assert Path(worker_progress.DEFAULT_HEARTBEAT_FILE) == expected
    assert not str(expected).startswith("/tmp/")


def _install_signal_fakes(monkeypatch, *, stop_on_sleep: bool = False):
    handlers = {}
    registrations = []

    def fake_signal(signum, handler):
        registrations.append((signum, handler))
        if callable(handler):
            handlers[signum] = handler
            return f"previous-{signum}"
        return None

    def fake_sleep(_seconds):
        if stop_on_sleep:
            handlers[signal.SIGTERM](signal.SIGTERM, None)

    monkeypatch.setattr(runtime.signal, "signal", fake_signal)
    monkeypatch.setattr(runtime.time, "sleep", fake_sleep)
    return handlers, registrations


def test_shutdown_terminates_process_group_then_forces_cleanup(monkeypatch):
    process = _Process(101, timeout=True)
    spawned = []
    group_signals = []
    handlers, registrations = _install_signal_fakes(monkeypatch, stop_on_sleep=True)
    monkeypatch.setattr(runtime, "commands", lambda *_args, **_kwargs: [("api", ["api-command"])])
    monkeypatch.setattr(runtime, "worker_subprocess_environment", lambda **_kwargs: {"PATH": "/synthetic/bin"})
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda argv, **kwargs: spawned.append((argv, kwargs)) or process,
    )
    monkeypatch.setattr(runtime.os, "killpg", lambda pid, sig: group_signals.append((pid, sig)))

    result = runtime.run(shutdown_seconds=0.1)

    assert result == 0
    assert spawned == [(
        ["api-command"],
        {"start_new_session": True, "env": {"PATH": "/synthetic/bin"}},
    )]
    assert group_signals == [(101, signal.SIGTERM), (101, signal.SIGKILL)]
    assert len(process.wait_calls) == 2
    assert process.wait_calls[0] is not None
    assert process.wait_calls[1] is None
    assert handlers[signal.SIGTERM]
    assert (signal.SIGTERM, "previous-15") in registrations
    assert (signal.SIGINT, "previous-2") in registrations


def test_supervisor_heartbeat_is_atomic_private_and_refreshes(tmp_path):
    path = tmp_path / "heartbeat" / "supervisor.json"
    timestamps = iter((1_000_000_000, 6_000_000_000))
    heartbeat = runtime._SupervisorHeartbeat(
        path,
        pid=os.getpid(),
        generation="a" * 32,
        monotonic_ns=lambda: next(timestamps),
    )

    heartbeat.pulse()
    first = json.loads(path.read_text())
    assert first == {
        "children": {},
        "generation": "a" * 32,
        "monotonic_ns": 1_000_000_000,
        "pid": os.getpid(),
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert list(path.parent.glob(".supervisor.json.*")) == []

    heartbeat.pulse()
    assert json.loads(path.read_text())["monotonic_ns"] == 6_000_000_000
    heartbeat.close()
    assert not path.exists()


def test_worker_runtime_pulses_and_removes_heartbeat_on_shutdown(monkeypatch, tmp_path):
    heartbeat_path = tmp_path / "worker" / "supervisor.json"
    monkeypatch.setenv(runtime.SUPERVISOR_HEARTBEAT_FILE_ENV, str(heartbeat_path))
    process = _Process(401)
    child_heartbeat_path = heartbeat_path.with_name("scheduler.json")
    spawned = []
    handlers = {}
    sleeps = 0
    monotonic_values = iter((0.0, 4.0, 5.0, 5.0, 5.0))

    def fake_signal(signum, handler):
        if callable(handler):
            handlers[signum] = handler
            return f"previous-{signum}"
        return None

    def fake_sleep(_seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 1:
            assert heartbeat_path.exists()
            return
        handlers[signal.SIGTERM](signal.SIGTERM, None)

    monkeypatch.setattr(runtime.signal, "signal", fake_signal)
    monkeypatch.setattr(runtime.time, "sleep", fake_sleep)
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(runtime, "commands", lambda *_args, **_kwargs: [("scheduler", ["scheduler"])])
    monkeypatch.setattr(runtime, "worker_subprocess_environment", lambda **_kwargs: {"PATH": "/synthetic/bin"})
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda argv, **kwargs: (
            spawned.append((argv, kwargs)),
            child_heartbeat_path.write_text(json.dumps({
                "generation": "a" * 32,
                "monotonic_ns": time.monotonic_ns(),
                "pid": process.pid,
                "worker": "scheduler",
            })),
            process,
        )[-1],
    )
    monkeypatch.setattr(runtime.os, "killpg", lambda *_args: None)

    assert runtime.run(workers_only=True, shutdown_seconds=1) == 0
    assert spawned[0][0] == ["scheduler"]
    assert sleeps == 2
    assert not heartbeat_path.exists()
    assert not child_heartbeat_path.exists()


def test_supervisor_removes_only_the_reaped_child_heartbeat(monkeypatch, tmp_path):
    path = tmp_path / "worker" / "supervisor.json"
    path.parent.mkdir(mode=0o700)
    child_path = path.with_name("events.json")
    child_path.write_text(json.dumps({
        "generation": "b" * 32,
        "monotonic_ns": time.monotonic_ns(),
        "pid": 512,
        "worker": "events",
    }))

    assert worker_progress.remove_worker_progress_heartbeat("events", 511, path=path) is False
    assert child_path.exists()
    assert worker_progress.remove_worker_progress_heartbeat("events", 512, path=path) is True
    assert not child_path.exists()


def test_supervisor_scopes_each_worker_key_to_its_process(monkeypatch, tmp_path):
    monkeypatch.setenv(
        runtime.SUPERVISOR_HEARTBEAT_FILE_ENV,
        str(tmp_path / "worker" / "supervisor.json"),
    )
    processes = iter((_Process(111), _Process(112), _Process(113), _Process(114)))
    spawned = []
    environment_options = []
    dispatch_keys = ("event_dispatch", "sensor_anomaly")
    monkeypatch.setattr(runtime, "event_dispatch_worker_keys", lambda: dispatch_keys)
    _install_signal_fakes(monkeypatch, stop_on_sleep=True)
    monkeypatch.setattr(
        runtime,
        "commands",
        lambda *_args, **_kwargs: [
            ("api", ["api"]),
            ("scheduler", ["scheduler"]),
            ("events", ["events"]),
            ("notifications", ["notifications"]),
        ],
    )

    def filtered_environment(**kwargs):
        environment_options.append(kwargs)
        return {"VISIBLE_WORKER_KEYS": ",".join(kwargs.get("allowed_worker_keys", ())) }

    monkeypatch.setattr(runtime, "worker_subprocess_environment", filtered_environment)
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda argv, **kwargs: spawned.append((argv, kwargs)) or next(processes),
    )
    monkeypatch.setattr(runtime.os, "killpg", lambda *_args: None)

    assert runtime.run(with_workers=True) == 0

    scheduler_allowlist = ("scheduler", *SCHEDULED_WORKER_KEYS, *dispatch_keys)
    assert environment_options == [
        {
            "allowed_worker_keys": ("operator_auth", "clickhouse_outbox_operator"),
            "include_api_only_media_environment": True,
        },
        {"allowed_worker_keys": scheduler_allowlist},
        {"allowed_worker_keys": (), "strip_shared_database_credentials": True},
        {"allowed_worker_keys": (), "strip_shared_database_credentials": True},
    ]
    assert [call[1]["env"]["VISIBLE_WORKER_KEYS"] for call in spawned] == [
        "operator_auth,clickhouse_outbox_operator",
        ",".join(scheduler_allowlist),
        "",
        "",
    ]
    assert [call[1]["env"].get(runtime.WORKER_PROGRESS_NAME_ENV) for call in spawned] == [
        None, "scheduler", "events", "notifications"
    ]


def test_supervisor_preserves_shared_runtime_login_for_api_only(monkeypatch):
    process = _Process(115)
    spawned = []
    source_environment = {
        "PATH": "/synthetic/bin",
        "PG_HOST": "database",
        "PG_PORT": "5432",
        "PG_DB": "kokonut_intelligence",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "synthetic-runtime-password",
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": (
            "postgresql://anomaly:synthetic@database/db"
        ),
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "synthetic-anomaly-secret",
        "KOKONUT_WEATHER_WORKER_CREDENTIAL": "synthetic-weather-secret",
        "KOKONUT_OPERATOR_AUTH_USER": "kokonut_operator_auth",
        "KOKONUT_OPERATOR_AUTH_PASSWORD": "synthetic-operator-auth-secret",
        "KOKONUT_CLICKHOUSE_OUTBOX_OPERATOR_PASSWORD": "synthetic-outbox-operator-secret",
    }
    _install_signal_fakes(monkeypatch, stop_on_sleep=True)
    monkeypatch.setattr(runtime, "commands", lambda *_args, **_kwargs: [("api", ["api"])])

    def filtered_environment(**kwargs):
        return worker_subprocess_environment(**kwargs, environ=source_environment)

    monkeypatch.setattr(runtime, "worker_subprocess_environment", filtered_environment)
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda argv, **kwargs: spawned.append((argv, kwargs)) or process,
    )
    monkeypatch.setattr(runtime.os, "killpg", lambda *_args: None)

    assert runtime.run() == 0

    api_environment = spawned[0][1]["env"]
    for name in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD"):
        assert api_environment[name] == source_environment[name]
    for name in (
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL",
        "KOKONUT_WEATHER_WORKER_CREDENTIAL",
    ):
        assert name not in api_environment
    for name in (
        "KOKONUT_OPERATOR_AUTH_USER",
        "KOKONUT_OPERATOR_AUTH_PASSWORD",
        "KOKONUT_CLICKHOUSE_OUTBOX_OPERATOR_PASSWORD",
    ):
        assert api_environment[name] == source_environment[name]


def test_commands_start_event_and_notification_workers_independently(monkeypatch):
    from services.core import features

    enabled = {
        "scheduler": False,
        "event_bus": True,
        "notification_delivery": False,
    }
    monkeypatch.setattr(features, "is_enabled", lambda name: enabled.get(name, False))

    children = runtime.commands(8099, with_workers=True)

    assert [name for name, _ in children] == ["api", "events"]
    assert children[1][1][3] == "--event-worker"

    enabled["isolated_event_dispatch"] = True
    children = runtime.commands(8099, with_workers=True)
    assert [name for name, _ in children] == ["api", "events"]
    assert children[1][1][3] == "--isolated-event-worker"

    enabled.update(event_bus=False, notification_delivery=True)
    children = runtime.commands(8099, with_workers=True)

    assert [name for name, _ in children] == ["api", "notifications"]
    assert children[1][1][3] == "--notification-worker"

    enabled["isolated_notification_delivery"] = True
    children = runtime.commands(8099, with_workers=True)

    assert [name for name, _ in children] == ["api", "notifications"]
    assert children[1][1][3] == "--isolated-notification-worker"

    enabled["notification_delivery"] = False
    assert [name for name, _ in runtime.commands(8099, with_workers=True)] == ["api"]


def test_commands_omit_both_workers_when_features_are_disabled(monkeypatch):
    from services.core import features

    monkeypatch.setattr(features, "is_enabled", lambda _name: False)

    assert [name for name, _ in runtime.commands(8099, with_workers=True)] == ["api"]
    assert runtime.commands(8099, with_workers=False) == [
        ("api", [sys.executable, "-m", "services.gateway.cli", "--serve", "--port", "8099"])
    ]


def test_supervisor_marks_isolated_event_worker_and_keeps_exact_handler_secrets(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(
        runtime.SUPERVISOR_HEARTBEAT_FILE_ENV,
        str(tmp_path / "worker" / "supervisor.json"),
    )
    processes = iter((_Process(121), _Process(122)))
    spawned = []
    environment_options = []
    monkeypatch.setattr(
        runtime, "event_dispatch_worker_keys", lambda: ("event_dispatch", "sensor_anomaly")
    )
    _install_signal_fakes(monkeypatch, stop_on_sleep=True)
    monkeypatch.setattr(
        runtime,
        "commands",
        lambda *_args, **_kwargs: [("api", ["api"]), ("events", ["isolated-events", "--isolated-event-worker"])],
    )
    def filtered_environment(**kwargs):
        environment_options.append(kwargs)
        return {"ISOLATED": kwargs.get("isolated_worker_key", "")}

    monkeypatch.setattr(runtime, "worker_subprocess_environment", filtered_environment)
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda argv, **kwargs: spawned.append((argv, kwargs)) or next(processes),
    )
    monkeypatch.setattr(runtime.os, "killpg", lambda *_args: None)

    assert runtime.run(with_workers=True) == 0

    event_kwargs = environment_options[1]
    assert event_kwargs["isolated_worker_key"] == "event_dispatch"
    assert event_kwargs["allowed_worker_keys"] == ("event_dispatch", "sensor_anomaly")
    assert spawned[1][1]["env"] == {
        "ISOLATED": "event_dispatch",
        runtime.WORKER_PROGRESS_NAME_ENV: "events",
    }


def test_supervisor_isolates_notification_delivery_database_and_preserves_provider_config(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(
        runtime.SUPERVISOR_HEARTBEAT_FILE_ENV,
        str(tmp_path / "worker" / "supervisor.json"),
    )
    process = _Process(131)
    spawned = []
    environment_options = []
    source_environment = {
        "PATH": "/synthetic/bin",
        "PG_HOST": "database",
        "PG_PORT": "5432",
        "PG_DB": "kokonut_intelligence",
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "synthetic-runtime-password",
        "POSTGRES_PASSWORD": "synthetic-admin-password",
        "KOKONUT_RUNTIME_USER": "kokonut_runtime",
        "KOKONUT_RUNTIME_PASSWORD": "synthetic-runtime-password",
        "KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL": (
            "postgresql://kokonut_notification_delivery_login:synthetic-secret@database/db"
        ),
        "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": (
            "postgresql://kokonut_notification_enqueue_login:synthetic-secret@database/db"
        ),
        "KOKONUT_EVENT_DISPATCH_DATABASE_URL": (
            "postgresql://kokonut_event_dispatch_login:synthetic-secret@database/db"
        ),
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": (
            "postgresql://kokonut_worker_login:synthetic-secret@database/db"
        ),
        "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_DELIVERY": "true",
        "ALERT_WEBHOOK_URL": "https://hooks.example.test/synthetic-token",
        "ALERT_SMTP_HOST": "smtp.example.test",
        "ALERT_SMTP_PORT": "587",
        "ALERT_SMTP_TLS_MODE": "starttls",
        "ALERT_SMTP_USER": "synthetic-smtp-user",
        "ALERT_SMTP_PASSWORD": "synthetic-smtp-password",
        "ALERT_EMAIL_FROM": "alerts@example.test",
        "ALERT_EMAIL_TO": "ops@example.test",
        "DIRECTUS_URL": "http://directus:8055",
        "DIRECTUS_ADMIN_TOKEN": "synthetic-directus-token",
        "CELO_RPC_URL": "https://rpc.example.test/synthetic-token",
    }
    _install_signal_fakes(monkeypatch, stop_on_sleep=True)
    monkeypatch.setattr(
        runtime,
        "commands",
        lambda *_args, **_kwargs: [
            ("notifications", ["events", "--isolated-notification-worker"])
        ],
    )

    def filtered_environment(**kwargs):
        environment_options.append(kwargs)
        return worker_subprocess_environment(**kwargs, environ=source_environment)

    monkeypatch.setattr(runtime, "worker_subprocess_environment", filtered_environment)
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda argv, **kwargs: spawned.append((argv, kwargs)) or process,
    )
    monkeypatch.setattr(runtime.os, "killpg", lambda *_args: None)

    assert runtime.run(workers_only=True) == 0

    assert environment_options == [
        {
            "allowed_worker_keys": ("notification_delivery",),
            "isolated_worker_key": "notification_delivery",
        }
    ]
    child_environment = spawned[0][1]["env"]
    assert child_environment["KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL"] == (
        source_environment["KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL"]
    )
    for unrelated_key in (
        "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL",
        "KOKONUT_EVENT_DISPATCH_DATABASE_URL",
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL",
        "CELO_RPC_URL",
    ):
        assert unrelated_key not in child_environment
    for shared_key in (
        "PG_HOST",
        "PG_PORT",
        "PG_DB",
        "PG_USER",
        "PG_PASSWORD",
        "POSTGRES_PASSWORD",
        "KOKONUT_RUNTIME_USER",
        "KOKONUT_RUNTIME_PASSWORD",
    ):
        assert shared_key not in child_environment
    for provider_key in (
        "ALERT_WEBHOOK_URL",
        "ALERT_SMTP_HOST",
        "ALERT_SMTP_PORT",
        "ALERT_SMTP_TLS_MODE",
        "ALERT_SMTP_USER",
        "ALERT_SMTP_PASSWORD",
        "ALERT_EMAIL_FROM",
        "ALERT_EMAIL_TO",
        "DIRECTUS_URL",
        "DIRECTUS_ADMIN_TOKEN",
    ):
        assert child_environment[provider_key] == source_environment[provider_key]


def test_unexpected_zero_exit_fails_supervisor_and_stops_siblings(monkeypatch):
    api = _Process(201, exit_code=0)
    worker = _Process(202)
    processes = iter((api, worker))
    stopped = []
    _install_signal_fakes(monkeypatch)
    monkeypatch.setattr(
        runtime,
        "commands",
        lambda *_args, **_kwargs: [("api", ["api"]), ("events", ["events"])],
    )
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: next(processes))
    monkeypatch.setattr(runtime.os, "killpg", lambda pid, sig: stopped.append((pid, sig)))

    result = runtime.run()

    assert result == 1
    assert stopped == [
        (201, signal.SIGTERM),
        (202, signal.SIGTERM),
        (201, signal.SIGKILL),
        (202, signal.SIGKILL),
    ]
    assert len(api.wait_calls) == len(worker.wait_calls) == 2


def test_partial_launch_failure_cleans_up_already_started_child(monkeypatch):
    process = _Process(301)
    calls = iter((process, RuntimeError("spawn failed")))
    group_signals = []
    _install_signal_fakes(monkeypatch)
    monkeypatch.setattr(
        runtime,
        "commands",
        lambda *_args, **_kwargs: [("api", ["api"]), ("events", ["events"])],
    )

    def fake_popen(*_args, **_kwargs):
        outcome = next(calls)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runtime.os, "killpg", lambda pid, sig: group_signals.append((pid, sig)))

    with pytest.raises(RuntimeError, match="spawn failed"):
        runtime.run()

    assert group_signals == [(301, signal.SIGTERM), (301, signal.SIGKILL)]
    assert len(process.wait_calls) == 2


@pytest.mark.skipif(sys.platform == "win32", reason="Kernel supervisor uses POSIX process groups")
def test_real_shutdown_signal_reaches_child_and_grandchild_process_group(tmp_path):
    child_ready = tmp_path / "child-ready"
    grandchild_ready = tmp_path / "grandchild-ready"
    child_stopped = tmp_path / "child-stopped"
    grandchild_stopped = tmp_path / "grandchild-stopped"
    grandchild_script = tmp_path / "grandchild.py"
    child_script = tmp_path / "child.py"
    supervisor_script = tmp_path / "supervisor.py"

    grandchild_script.write_text(
        "import signal, time\n"
        f"from pathlib import Path\nready = Path({str(grandchild_ready)!r})\n"
        f"stopped = Path({str(grandchild_stopped)!r})\n"
        "stopping = False\n"
        "def stop(*_):\n"
        "    global stopping\n"
        "    stopped.write_text('SIGTERM')\n"
        "    stopping = True\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "ready.write_text('ready')\n"
        "while not stopping: time.sleep(0.01)\n"
    )
    child_script.write_text(
        "import os, signal, subprocess, sys, time\n"
        f"from pathlib import Path\nready = Path({str(child_ready)!r})\n"
        f"stopped = Path({str(child_stopped)!r})\n"
        f"grandchild = subprocess.Popen([sys.executable, {str(grandchild_script)!r}])\n"
        "stopping = False\n"
        "def stop(*_):\n"
        "    global stopping\n"
        "    stopped.write_text('SIGTERM')\n"
        "    stopping = True\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "ready.write_text(str(os.getpid()))\n"
        "while not stopping: time.sleep(0.01)\n"
        "grandchild.wait(timeout=5)\n"
    )
    supervisor_script.write_text(
        "import sys\n"
        "from services.core import runtime\n"
        f"runtime.commands = lambda *_args, **_kwargs: [('probe', [sys.executable, {str(child_script)!r}])]\n"
        "raise SystemExit(runtime.run(shutdown_seconds=2))\n"
    )

    repo_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(repo_root), environment.get("PYTHONPATH", "")) if part
    )
    supervisor = subprocess.Popen(
        [sys.executable, str(supervisor_script)],
        cwd=repo_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not (
            child_ready.exists() and grandchild_ready.exists()
        ):
            if supervisor.poll() is not None:
                stdout, stderr = supervisor.communicate()
                raise AssertionError(f"supervisor exited before child startup: {stdout}\n{stderr}")
            time.sleep(0.02)
        assert child_ready.exists() and grandchild_ready.exists(), "child process group did not become ready"

        supervisor.send_signal(signal.SIGTERM)
        stdout, stderr = supervisor.communicate(timeout=10)

        assert supervisor.returncode == 0, f"supervisor failed to stop cleanly: {stdout}\n{stderr}"
        assert child_stopped.read_text() == "SIGTERM"
        assert grandchild_stopped.read_text() == "SIGTERM"
    finally:
        if supervisor.poll() is None:
            supervisor.send_signal(signal.SIGTERM)
            try:
                supervisor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                supervisor.kill()
                supervisor.wait(timeout=5)
        if child_ready.exists():
            try:
                os.killpg(int(child_ready.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
