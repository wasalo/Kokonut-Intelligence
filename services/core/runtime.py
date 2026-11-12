"""Supervise the existing API, scheduler, and event processes in one container."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable, Mapping

from services.common.logging import get_logger
from services.common.worker_environment import (
    API_MEDIA_CONFIG_FILE_ENV,
    COOLIFY_MEDIA_SECRET_HOST_FILE_ENV,
    SCHEDULED_WORKER_KEYS,
    event_dispatch_worker_keys,
    worker_subprocess_environment,
)
from services.core.worker_progress import (
    WORKER_PROGRESS_NAME_ENV,
    remove_worker_progress_heartbeat,
)

logger = get_logger("core.runtime")

SUPERVISOR_HEARTBEAT_FILE_ENV = "KOKONUT_WORKER_PROGRESS_HEARTBEAT_FILE"
DEFAULT_SUPERVISOR_HEARTBEAT_FILE = str(
    Path.home() / ".local" / "state" / "kokonut" / "worker-progress" / "supervisor.json"
)
SUPERVISOR_HEARTBEAT_INTERVAL_SECONDS = 5
_API_MEDIA_ENVIRONMENT_KEYS = frozenset({
    "MOBILE_MEDIA_PROVIDER",
    "MOBILE_MEDIA_ENCRYPTION_KEY",
    "MOBILE_MEDIA_LOCAL_DIRECTORY",
    "MOBILE_MEDIA_LOCAL_KEY",
    "MOBILE_MEDIA_S3_ENDPOINT",
    "MOBILE_MEDIA_S3_BUCKET",
    "MOBILE_MEDIA_S3_ACCESS_KEY_ID",
    "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
    "MOBILE_MEDIA_S3_REGION",
})


class _SupervisorHeartbeat:
    """Atomically publish private, process-local supervisor liveness state."""

    def __init__(
        self,
        path: str | Path,
        *,
        pid: int | None = None,
        generation: str | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.path = Path(path)
        self.pid = os.getpid() if pid is None else pid
        self.generation = uuid.uuid4().hex if generation is None else generation
        self._monotonic_ns = monotonic_ns

    def pulse(self, children: dict[str, int] | None = None) -> None:
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = parent.lstat()
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != os.getuid()
            or directory.st_mode & 0o077
        ):
            raise OSError("worker heartbeat directory is not private")

        payload = {
            "children": children or {},
            "generation": self.generation,
            "monotonic_ns": self._monotonic_ns(),
            "pid": self.pid,
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def close(self) -> None:
        """Remove only the heartbeat generation owned by this supervisor."""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("generation") == self.generation:
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError, AttributeError):
            pass


def _supervisor_heartbeat() -> _SupervisorHeartbeat:
    path = os.environ.get(
        SUPERVISOR_HEARTBEAT_FILE_ENV,
        DEFAULT_SUPERVISOR_HEARTBEAT_FILE,
    )
    return _SupervisorHeartbeat(path)


def _read_api_media_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load the Gateway-only media environment from a private mounted file."""
    source = os.environ if environ is None else environ
    configured_path = source.get(API_MEDIA_CONFIG_FILE_ENV, "").strip()
    if not configured_path:
        return {}

    descriptor = -1
    try:
        descriptor = os.open(
            configured_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        file_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid not in {0, os.getuid()}
            or file_stat.st_mode & 0o027
            or file_stat.st_mode & 0o111
        ):
            raise ValueError("private media configuration file permissions are invalid")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            content = handle.read()
    except OSError as exc:
        raise ValueError("private media configuration file is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if not separator or key not in _API_MEDIA_ENVIRONMENT_KEYS:
            raise ValueError(
                f"private media configuration has an invalid entry on line {line_number}"
            )
        if key in values:
            raise ValueError(f"private media configuration duplicates {key}")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    if not values:
        raise ValueError("private media configuration is empty")
    provider = values.get("MOBILE_MEDIA_PROVIDER", "s3").strip().lower()
    if provider not in {"local", "s3"}:
        raise ValueError("private media configuration has an unsupported provider")
    if not (values.get("MOBILE_MEDIA_ENCRYPTION_KEY") or values.get("MOBILE_MEDIA_LOCAL_KEY")):
        raise ValueError("private media configuration is missing its encryption key")
    if provider == "s3":
        required = (
            "MOBILE_MEDIA_S3_ENDPOINT",
            "MOBILE_MEDIA_S3_BUCKET",
            "MOBILE_MEDIA_S3_ACCESS_KEY_ID",
            "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
            "MOBILE_MEDIA_S3_REGION",
        )
        missing = [key for key in required if not values.get(key, "").strip()]
        if missing:
            raise ValueError(
                "private media configuration is missing: " + ", ".join(missing)
            )
    elif not values.get("MOBILE_MEDIA_LOCAL_DIRECTORY", "").strip():
        raise ValueError("private media configuration is missing MOBILE_MEDIA_LOCAL_DIRECTORY")
    return values


def commands(port: int, with_workers: bool, workers_only: bool = False) -> list[tuple[str, list[str]]]:
    from services.core.features import is_enabled

    children = [] if workers_only else [
        ("api", [sys.executable, "-m", "services.gateway.cli", "--serve", "--port", str(port)])
    ]
    # Each supervisor lifetime gets distinct lease ownership, including replicas.
    worker_id = f"kernel-{uuid.uuid4().hex}"
    if (with_workers or workers_only) and is_enabled("scheduler"):
        children.append(
            ("scheduler", [sys.executable, "-m", "services.scheduler.worker", "--worker-id", f"{worker_id}-scheduler"])
        )
    if (with_workers or workers_only) and is_enabled("event_bus"):
        event_command = (
            "--isolated-event-worker"
            if is_enabled("isolated_event_dispatch")
            else "--event-worker"
        )
        children.append(
            ("events", [sys.executable, "-m", "services.events", event_command, "--worker-id", f"{worker_id}-events"])
        )
    if (with_workers or workers_only) and is_enabled("notification_delivery"):
        notification_command = (
            "--isolated-notification-worker"
            if is_enabled("isolated_notification_delivery")
            else "--notification-worker"
        )
        children.append(
            ("notifications", [sys.executable, "-m", "services.events", notification_command,
                               "--worker-id", f"{worker_id}-notifications"])
        )
    return children


def run(port: int = 8099, with_workers: bool = False, shutdown_seconds: float = 30,
        workers_only: bool = False, require_schema: bool = False,
        require_runtime_role: bool = False) -> int:
    """Exit on any unexpected child exit; Compose owns restart policy."""
    stopping = False
    children: list[tuple[str, subprocess.Popen]] = []
    old_handlers = {}
    heartbeat: _SupervisorHeartbeat | None = None
    media_file_configured = bool(os.environ.get(API_MEDIA_CONFIG_FILE_ENV, "").strip())
    api_media_environment: dict[str, str] = {}

    if media_file_configured and not workers_only:
        try:
            api_media_environment = _read_api_media_environment()
        except ValueError as exc:
            logger.error(
                "Kernel private-media configuration failed validation (%s)",
                type(exc).__name__,
            )
            return 1

    if require_schema or require_runtime_role:
        from services.core.schema_readiness import SchemaReadinessError, require_schema_ready

        try:
            require_schema_ready(require_runtime_role=require_runtime_role)
        except SchemaReadinessError as exc:
            logger.error("Kernel schema readiness failed (%s); review migration status before startup", exc)
            return 1
        except Exception as exc:
            # Database errors may contain connection details; report only type.
            logger.error("Kernel schema readiness failed (%s); review migration status before startup",
                         type(exc).__name__)
            return 1

    def shutdown(signum, frame):
        nonlocal stopping
        stopping = True
        logger.info("Kernel shutdown requested (signal=%s)", signum)

    def send_group(process, signum):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            old_handlers[signum] = signal.signal(signum, shutdown)
        child_commands = commands(port, with_workers, workers_only)
        if not child_commands:
            raise ValueError("Workers-only runtime requires at least one enabled worker")
        if workers_only or with_workers:
            heartbeat = _supervisor_heartbeat()
            heartbeat.pulse()
        next_heartbeat = time.monotonic() + SUPERVISOR_HEARTBEAT_INTERVAL_SECONDS
        for name, argv in child_commands:
            if stopping:
                break
            isolated_event_dispatch = (
                name == "events" and "--isolated-event-worker" in argv
            )
            isolated_notification_delivery = (
                name == "notifications" and "--isolated-notification-worker" in argv
            )
            if isolated_event_dispatch:
                environment_options = {
                    "allowed_worker_keys": event_dispatch_worker_keys(),
                    "isolated_worker_key": "event_dispatch",
                }
            elif isolated_notification_delivery:
                environment_options = {
                    "allowed_worker_keys": ("notification_delivery",),
                    "isolated_worker_key": "notification_delivery",
                }
            elif name == "api":
                # The Gateway uses the shared runtime login plus dedicated OIDC
                # and ClickHouse outbox operator credentials.
                environment_options = {
                    "allowed_worker_keys": ("operator_auth", "clickhouse_outbox_operator"),
                    "include_api_only_media_environment": True,
                }
            elif name == "scheduler":
                environment_options = {
                    "allowed_worker_keys": (
                        "scheduler",
                        *SCHEDULED_WORKER_KEYS,
                        *event_dispatch_worker_keys(),
                    ),
                }
            else:
                # Default-off event and notification workers remain supervised
                # but carry no shared database credentials until their
                # dedicated login and feature flag are configured.
                environment_options = {
                    "allowed_worker_keys": (),
                    "strip_shared_database_credentials": True,
                }
            if name == "scheduler" and "KOKONUT_SCHEDULER_DATABASE_URL" in os.environ:
                environment_options["isolated_worker_key"] = "scheduler"
            if media_file_configured:
                child_source = dict(os.environ)
                child_source.pop(API_MEDIA_CONFIG_FILE_ENV, None)
                child_source.pop(COOLIFY_MEDIA_SECRET_HOST_FILE_ENV, None)
                for media_key in _API_MEDIA_ENVIRONMENT_KEYS:
                    child_source.pop(media_key, None)
                if name == "api":
                    child_source.update(api_media_environment)
                child_environment = worker_subprocess_environment(
                    **environment_options,
                    environ=child_source,
                )
            else:
                child_environment = worker_subprocess_environment(**environment_options)
            if name in {"scheduler", "events", "notifications"}:
                child_environment[WORKER_PROGRESS_NAME_ENV] = name
            process = subprocess.Popen(
                argv,
                start_new_session=True,
                env=child_environment,
            )
            children.append((name, process))
            logger.info("Started Kernel process %s (pid=%s)", name, process.pid)

        def worker_children() -> dict[str, int]:
            return {
                name: process.pid
                for name, process in children
                if name in {"scheduler", "events", "notifications"}
            }

        if heartbeat is not None:
            heartbeat.pulse(worker_children())

        while not stopping:
            for name, process in children:
                code = process.poll()
                if code is not None:
                    logger.error("Kernel process %s exited unexpectedly (code=%s)", name, code)
                    return 1
            now = time.monotonic()
            if heartbeat is not None and now >= next_heartbeat:
                heartbeat.pulse(worker_children())
                next_heartbeat = now + SUPERVISOR_HEARTBEAT_INTERVAL_SECONDS
            time.sleep(0.25)
        return 0
    finally:
        # Signal groups even if a parent exited, so its task descendants stop too.
        for _, process in children:
            send_group(process, signal.SIGTERM)
        deadline = time.monotonic() + shutdown_seconds
        for _, process in children:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for _, process in children:
            send_group(process, signal.SIGKILL)
            process.wait()
        for name, process in children:
            if name in {"scheduler", "events", "notifications"}:
                remove_worker_progress_heartbeat(name, process.pid)
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
        if heartbeat is not None:
            heartbeat.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut Kernel process supervisor (Linux/POSIX)")
    parser.add_argument("--port", type=int, default=8099)
    roles = parser.add_mutually_exclusive_group()
    roles.add_argument("--with-workers", action="store_true", help="Run enabled durable workers alongside the API")
    roles.add_argument("--workers-only", action="store_true", help="Run enabled durable workers without an API")
    parser.add_argument("--shutdown-seconds", type=float, default=30)
    parser.add_argument("--require-schema", action="store_true",
                        help="Require applied checksums for bundled schemas before spawning processes")
    parser.add_argument("--require-runtime-role", action="store_true",
                        help="Require a non-owner, non-privileged database login before schema readiness and child startup")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not math.isfinite(args.shutdown_seconds) or args.shutdown_seconds <= 0:
        parser.error("--shutdown-seconds must be positive")
    raise SystemExit(run(args.port, args.with_workers, args.shutdown_seconds,
                        args.workers_only, args.require_schema, args.require_runtime_role))


if __name__ == "__main__":
    main()
