#!/usr/bin/env python3
"""Exercise the split Standard API/worker profile through a disposable DB outage.

This is an opt-in Docker acceptance check. It composes only the Kernel
candidate and Standard overlays, strips all published ports, marks the single
runtime network internal, applies checksummed schema migrations only, and
removes the unique Compose project and volumes on every exit path.
"""

from __future__ import annotations

import copy
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_COMPOSE = ROOT / "docker-compose.kernel-candidate.yml"
STANDARD_COMPOSE = ROOT / "docker-compose.kernel-standard.yml"
PROXY_COMPOSE = ROOT / "docker-compose.kernel-proxy.yml"
DEFAULT_TIMEOUT_SECONDS = 180
HEARTBEAT_PATH = "/var/lib/kokonut/worker-progress/supervisor.json"


class AcceptanceError(RuntimeError):
    """A disposable Standard-profile acceptance assertion failed."""


def _run(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout: float | None = None,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        password = environment.get("POSTGRES_PASSWORD", "")
        if password:
            detail = detail.replace(password, "[redacted]")
        raise AcceptanceError(
            f"{command[0]} {command[1] if len(command) > 1 else ''} failed "
            f"({result.returncode}): {detail[-2400:]}"
        )
    return result


def _heartbeat_is_removed(worker_id: str, environment: dict[str, str]) -> bool:
    result = subprocess.run(
        ["docker", "cp", f"{worker_id}:{HEARTBEAT_PATH}", "-"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode == 0:
        return False
    error = result.stderr.decode("utf-8", errors="replace").lower()
    if not any(marker in error for marker in ("no such file or directory", "could not find the file")):
        raise AcceptanceError("could not inspect heartbeat removal after worker shutdown")
    return True


def _compose_command(project: str, manifest: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "--env-file",
        "/dev/null",
        "-p",
        project,
        "-f",
        str(manifest),
    ]


def _compose_environment(sensor_root: Path) -> dict[str, str]:
    # Keep Docker's connection settings but do not inherit arbitrary host
    # provider credentials into Compose interpolation or container env.
    environment = {
        name: os.environ[name]
        for name in (
            "PATH",
            "HOME",
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_CONFIG",
            "DOCKER_TLS_VERIFY",
            "DOCKER_CERT_PATH",
        )
        if os.environ.get(name)
    }
    password = secrets.token_urlsafe(32)
    environment.update(
        {
            "POSTGRES_PASSWORD": password,
            "KOKONUT_RUNTIME_USER": "kokonut",
            "KOKONUT_RUNTIME_PASSWORD": password,
            "KOKONUT_ENV": "development",
            "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
            "KOKONUT_ALLOW_PLAINTEXT_ENV": "true",
            "KOKONUT_FEATURE_SCHEDULER": "true",
            "KOKONUT_FEATURE_EVENT_BUS": "true",
            "KOKONUT_FEATURE_NOTIFICATION_DELIVERY": "true",
            "KOKONUT_KERNEL_PORT": "8098",
            "KOKONUT_SENSOR_CSV_HOST_DIR": str(sensor_root),
            "ALERT_SMTP_HOST": "",
            "ALERT_SMTP_USER": "",
            "ALERT_SMTP_PASSWORD": "",
            "ALERT_EMAIL_TO": "",
            "ALERT_WEBHOOK_URL": "",
            "CLICKHOUSE_PASSWORD": "",
            "REDIS_PASSWORD": "",
            "DIRECTUS_SECRET": "disposable-standard-probe",
        }
    )
    return environment


def _isolated_compose_model(model: dict[str, Any]) -> dict[str, Any]:
    """Retain the real Standard merge while forcing portless internal runtime."""
    isolated = copy.deepcopy(model)
    required = {"database", "app", "worker"}
    services = isolated.get("services")
    if not isinstance(services, dict) or not required <= set(services):
        raise AcceptanceError("merged Standard Compose model lacks database/app/worker")
    selected = ["database", "app", "worker"]
    if "proxy" in services:
        selected.append("proxy")
    isolated["services"] = {name: services[name] for name in selected}

    for service in isolated["services"].values():
        service.pop("ports", None)
        networks = service.get("networks", {})
        if not isinstance(networks, dict) or not networks:
            raise AcceptanceError("Standard service has no explicit runtime network")
    networks = isolated.get("networks")
    if not isinstance(networks, dict) or "kernel" not in networks:
        raise AcceptanceError("Standard Compose model has no kernel network")
    if len(networks) != 1:
        raise AcceptanceError("disposable acceptance expects one Standard runtime network")
    networks["kernel"]["internal"] = True

    app = isolated["services"]["app"]
    worker = isolated["services"]["worker"]
    for service in (app, worker):
        environment = service.setdefault("environment", {})
        if not isinstance(environment, dict):
            raise AcceptanceError("resolved service environment is not a mapping")
        environment.update(
            {
                "KOKONUT_ENV": "development",
                "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
                "KOKONUT_ALLOW_PLAINTEXT_ENV": "true",
                "KOKONUT_FEATURE_SCHEDULER": "true",
                "KOKONUT_FEATURE_EVENT_BUS": "true",
                "KOKONUT_FEATURE_NOTIFICATION_DELIVERY": "true",
            }
        )
    worker["stop_grace_period"] = "15s"
    worker["healthcheck"] = {
        "test": ["CMD", "python3", "-m", "services.core.worker_progress", "--check"],
        "interval": "2s",
        "timeout": "4s",
        "retries": 3,
        "start_period": "5s",
    }
    app["healthcheck"] = {
        "test": [
            "CMD",
            "python3",
            "-c",
            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=3).close()",
        ],
        "interval": "2s",
        "timeout": "4s",
        "retries": 3,
        "start_period": "5s",
    }
    _validate_split_commands(app, worker)
    return isolated


def _validate_split_commands(app: dict[str, Any], worker: dict[str, Any]) -> None:
    app_command = app.get("command")
    worker_command = worker.get("command")
    if not isinstance(app_command, list) or not isinstance(worker_command, list):
        raise AcceptanceError("API and worker commands must be explicit argument arrays")
    if "--require-schema" not in app_command or "--require-schema" not in worker_command:
        raise AcceptanceError("both Standard roles must require schema readiness")
    if "--workers-only" in app_command or "--with-workers" in app_command:
        raise AcceptanceError("Standard API command unexpectedly starts worker children")
    if "--workers-only" not in worker_command or "--with-workers" in worker_command:
        raise AcceptanceError("Standard worker command does not select workers-only mode")


def _service_id(project: str, manifest: Path, environment: dict[str, str], service: str) -> str:
    result = _run(
        [*_compose_command(project, manifest), "ps", "-q", service],
        environment=environment,
    )
    container_id = result.stdout.strip()
    if not container_id:
        result = _run(
            [*_compose_command(project, manifest), "ps", "--all", "-q", service],
            environment=environment,
            check=False,
        )
        container_id = result.stdout.strip()
    if not container_id:
        raise AcceptanceError(f"Compose has no container for service {service}")
    return container_id


def _failure_diagnostics(
    project: str, manifest: Path, environment: dict[str, str]
) -> str:
    if not manifest.exists():
        return ""
    outputs = []
    for command in (
        [*_compose_command(project, manifest), "ps", "--all"],
        [*_compose_command(project, manifest), "logs", "--no-color", "--tail=60"],
    ):
        result = _run(command, environment=environment, check=False, timeout=20)
        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        for secret_name in ("POSTGRES_PASSWORD", "KOKONUT_RUNTIME_PASSWORD", "DIRECTUS_SECRET"):
            secret = environment.get(secret_name, "")
            if secret:
                output = output.replace(secret, "[redacted]")
        outputs.append(output)
    return "\nDisposable Compose diagnostics:\n" + "\n".join(outputs)[-8000:]


def _inspect_container(
    container_id: str, environment: dict[str, str]
) -> dict[str, Any]:
    result = _run(["docker", "inspect", container_id], environment=environment)
    try:
        value = json.loads(result.stdout)[0]
    except (IndexError, json.JSONDecodeError) as exc:
        raise AcceptanceError("Docker returned invalid container inspection data") from exc
    return value


def _health_status(container: dict[str, Any]) -> str:
    state = container.get("State", {})
    health = state.get("Health", {})
    return str(health.get("Status", state.get("Status", "unknown")))


def _wait_for_health(
    project: str,
    manifest: Path,
    environment: dict[str, str],
    service: str,
    expected: str,
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last = _inspect_container(
                _service_id(project, manifest, environment, service), environment
            )
        except AcceptanceError:
            time.sleep(0.25)
            continue
        if _health_status(last) == expected:
            return last
        if last.get("State", {}).get("Status") == "exited":
            raise AcceptanceError(f"Standard {service} container exited before becoming {expected}")
        time.sleep(0.25)
    raise TimeoutError(
        f"Standard {service} did not become {expected}; last status={_health_status(last)}"
    )


def _container_has_no_published_ports(container: dict[str, Any]) -> bool:
    bindings = container.get("NetworkSettings", {}).get("Ports", {})
    return not any(binding for binding in bindings.values() if binding)


def _worker_probe(
    project: str, manifest: Path, environment: dict[str, str]
) -> dict[str, Any]:
    result = _run(
        [
            *_compose_command(project, manifest),
            "exec",
            "-T",
            "worker",
            "python3",
            "-m",
            "services.core.worker_progress",
            "--check",
        ],
        environment=environment,
        check=False,
        timeout=10,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceError("worker health probe returned malformed JSON") from exc
    if result.returncode != 0 and payload.get("status") != "unhealthy":
        raise AcceptanceError("worker health probe failed without an unhealthy result")
    return payload


def _heartbeat_metadata(
    project: str, manifest: Path, environment: dict[str, str]
) -> dict[str, Any]:
    probe = f"""
import json, os, stat
from pathlib import Path
path = Path({HEARTBEAT_PATH!r})
try:
    directory = path.parent.lstat()
    record = path.lstat()
    payload = json.loads(path.read_text(encoding='utf-8'))
    result = {{
        'directory_private': stat.S_ISDIR(directory.st_mode) and not (directory.st_mode & 0o077),
        'file_private': stat.S_ISREG(record.st_mode) and not (record.st_mode & 0o077),
        'shape_valid': set(payload) == {{'children', 'generation', 'monotonic_ns', 'pid'}},
    }}
except (OSError, ValueError, TypeError):
    result = {{'directory_private': False, 'file_private': False, 'shape_valid': False}}
print(json.dumps(result, sort_keys=True))
"""
    result = _run(
        [*_compose_command(project, manifest), "exec", "-T", "worker", "python3", "-c", probe],
        environment=environment,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceError("heartbeat metadata probe returned malformed JSON") from exc
    if not all(payload.values()):
        raise AcceptanceError("worker heartbeat permissions or shape are invalid")
    return payload


def _main(timeout: float) -> dict[str, Any]:
    project = f"kokonut-standard-recovery-{uuid.uuid4().hex[:10]}"
    with tempfile.TemporaryDirectory(prefix="kokonut-standard-recovery-") as temporary:
        temp_root = Path(temporary)
        sensor_root = temp_root / "sensor-inputs"
        sensor_root.mkdir(mode=0o700)
        manifest = temp_root / "compose.json"
        environment = _compose_environment(sensor_root)
        result = {
            "result": "failed",
            "profile": "standard",
            "project": project,
            "host_ports_published": False,
            "runtime_network_internal": False,
            "candidate_legacy_production_touched": False,
        }

        try:
            config_command = [
                "docker",
                "compose",
                "--project-directory",
                str(ROOT),
                "--env-file",
                "/dev/null",
                "-p",
                project,
                "-f",
                str(BASE_COMPOSE),
                "-f",
                str(STANDARD_COMPOSE),
                "-f",
                str(PROXY_COMPOSE),
                "config",
                "--format",
                "json",
            ]
            config_result = _run(
                config_command, environment=environment, timeout=30
            )
            try:
                model = json.loads(config_result.stdout)
            except json.JSONDecodeError as exc:
                raise AcceptanceError("Compose returned invalid resolved configuration") from exc
            model = _isolated_compose_model(model)
            manifest.write_text(json.dumps(model, sort_keys=True), encoding="utf-8")
            manifest.chmod(0o600)

            compose = _compose_command(project, manifest)
            _run([*compose, "build", "app", "worker"], environment=environment, timeout=2400)
            _run([*compose, "up", "-d", "database"], environment=environment, timeout=120)
            database = _wait_for_health(
                project, manifest, environment, "database", "healthy", timeout
            )
            result["database_image"] = database.get("Config", {}).get("Image")

            missing_schema = _run(
                [
                    *compose,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "app",
                    "python3",
                    "-m",
                    "services.core.runtime",
                    "--workers-only",
                    "--require-schema",
                ],
                environment=environment,
                timeout=30,
                check=False,
            )
            missing_schema_log = missing_schema.stdout + missing_schema.stderr
            if missing_schema.returncode == 0 or "Kernel schema readiness failed" not in missing_schema_log:
                raise AcceptanceError("Standard runtime did not fail closed before migrations")
            if "Started Kernel process" in missing_schema_log:
                raise AcceptanceError("Standard runtime spawned a child before schema readiness")
            result["required_schema_missing_fails_closed"] = True

            migration_environment = environment.copy()
            migration_environment.update(
                {
                    "PG_HOST": "database",
                    "PG_PORT": "5432",
                    "PG_DB": "kokonut_intelligence",
                    "PG_USER": "kokonut",
                    "PG_PASSWORD": environment["POSTGRES_PASSWORD"],
                }
            )
            migration = _run(
                [
                    sys.executable,
                    "-m",
                    "services.migration",
                    "--compose-project",
                    project,
                    "--compose-file",
                    str(manifest),
                    "migrate",
                    "--schemas-only",
                ],
                environment=migration_environment,
                timeout=2400,
            )
            schema_files = sorted(
                (
                    path
                    for path in (ROOT / "schemas" / "postgres").glob("*.sql")
                    if path.stem.split("_", 1)[0].isdigit()
                ),
                key=lambda path: int(path.stem.split("_", 1)[0]),
            )
            expected_schemas = len(schema_files)
            expected_latest_migration = f"schema:{schema_files[-1].name}"
            expected_summary = f"Applied: {expected_schemas}, Failed: 0"
            if expected_summary not in migration.stdout:
                raise AcceptanceError("ordered migration runner did not report all schema files applied")
            ledger = _run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-XAt",
                    "-F",
                    "|",
                    "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    "SELECT COUNT(*) FILTER (WHERE migration_id LIKE 'schema:%' AND status='applied'), "
                    "COUNT(*) FILTER (WHERE migration_id LIKE 'schema:%' AND status<>'applied'), "
                    "COUNT(*) FILTER (WHERE migration_id LIKE 'seed:%'), "
                    "MAX(migration_id) FILTER (WHERE migration_id LIKE 'schema:%' AND status='applied') "
                    "FROM public.schema_migration;",
                ],
                environment=environment,
            )
            expected_ledger = f"{expected_schemas}|0|0|{expected_latest_migration}"
            if ledger.stdout.strip() != expected_ledger:
                raise AcceptanceError("schema-only migration ledger did not match expected counts")
            result["migrations"] = {
                "schemas_applied": expected_schemas,
                "schemas_failed": 0,
                "seed_rows": 0,
                "latest_schema_migration": expected_latest_migration,
            }

            _run([*compose, "up", "-d", "app", "worker", "proxy"], environment=environment, timeout=120)
            app = _wait_for_health(project, manifest, environment, "app", "healthy", timeout)
            worker = _wait_for_health(project, manifest, environment, "worker", "healthy", timeout)
            containers = [("app", app), ("worker", worker), ("database", database)]
            try:
                proxy = _inspect_container(
                    _service_id(project, manifest, environment, "proxy"), environment
                )
            except AcceptanceError as exc:
                if "no container for service proxy" in str(exc):
                    proxy = None
                else:
                    raise
            if proxy is not None:
                if proxy.get("State", {}).get("Status") != "running":
                    raise AcceptanceError("default Standard Caddy proxy did not start")
                containers.append(("proxy", proxy))
            for name, container in containers:
                if not _container_has_no_published_ports(container):
                    raise AcceptanceError(f"disposable {name} container unexpectedly publishes a host port")
            result["host_ports_published"] = False

            network = model["networks"]["kernel"]
            network_name = network.get("name", f"{project}_kernel")
            network_probe = _run(
                ["docker", "network", "inspect", "--format", "{{.Internal}}", network_name],
                environment=environment,
            )
            if network_probe.stdout.strip().lower() != "true":
                raise AcceptanceError("disposable Standard network is not marked internal")
            result["runtime_network_internal"] = True
            _validate_split_commands(
                {"command": app.get("Config", {}).get("Cmd")},
                {"command": worker.get("Config", {}).get("Cmd")},
            )
            result["api_worker_split"] = True

            probe = _worker_probe(project, manifest, environment)
            if (
                probe.get("status") != "healthy"
                or probe.get("supervisor", {}).get("alive") is not True
                or probe.get("supervisor", {}).get("children_alive") is not True
            ):
                raise AcceptanceError(
                    "Standard worker probe did not confirm healthy supervisor, children, and schema state"
                )
            heartbeat = _heartbeat_metadata(project, manifest, environment)
            result["startup"] = {
                "api_healthy": _health_status(app) == "healthy",
                "worker_healthy": _health_status(worker) == "healthy",
                "proxy_running": proxy is not None and proxy.get("State", {}).get("Status") == "running",
                "worker_probe": "healthy",
                "worker_children_alive": True,
                "private_supervisor_heartbeat": heartbeat,
            }

            worker_restarts_before = int(worker.get("RestartCount", 0))
            _run([*compose, "stop", "--timeout", "1", "database"], environment=environment, timeout=30)
            degraded = False
            outage_deadline = time.monotonic() + timeout
            outage_status = "unknown"
            while time.monotonic() < outage_deadline:
                current = _inspect_container(
                    _service_id(project, manifest, environment, "worker"), environment
                )
                outage_status = _health_status(current)
                if outage_status == "unhealthy" or int(current.get("RestartCount", 0)) > worker_restarts_before:
                    degraded = True
                    break
                time.sleep(0.5)
            if not degraded:
                raise TimeoutError("worker health/restart state did not reflect the database outage")
            _run([*compose, "start", "database"], environment=environment, timeout=30)
            recovered_database = _wait_for_health(
                project, manifest, environment, "database", "healthy", timeout
            )
            recovered_worker = _wait_for_health(
                project, manifest, environment, "worker", "healthy", timeout
            )
            recovered_app = _wait_for_health(
                project, manifest, environment, "app", "healthy", timeout
            )
            recovery_probe = _worker_probe(project, manifest, environment)
            if (
                recovery_probe.get("status") != "healthy"
                or recovery_probe.get("supervisor", {}).get("alive") is not True
                or recovery_probe.get("supervisor", {}).get("children_alive") is not True
            ):
                raise AcceptanceError("worker did not report healthy recovery after database restart")
            self_recovered = _heartbeat_metadata(project, manifest, environment)
            result["database_outage_recovery"] = {
                "worker_degraded_state_observed": outage_status,
                "database_healthy_after_restart": _health_status(recovered_database) == "healthy",
                "api_healthy_after_restart": _health_status(recovered_app) == "healthy",
                "worker_healthy_after_restart": _health_status(recovered_worker) == "healthy",
                "worker_restart_count": int(recovered_worker.get("RestartCount", 0)),
                "private_supervisor_heartbeat_after_restart": self_recovered,
            }

            _run([*compose, "stop", "--timeout", "12", "worker"], environment=environment, timeout=30)
            worker_id = _service_id(project, manifest, environment, "worker")
            stopped_worker = _inspect_container(worker_id, environment)
            if stopped_worker.get("State", {}).get("Status") != "exited":
                raise AcceptanceError("worker did not stop cleanly")
            if not _heartbeat_is_removed(worker_id, environment):
                raise AcceptanceError("worker supervisor heartbeat remained after graceful shutdown")
            outstanding = _run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-XAt",
                    "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    "SELECT "
                    "(SELECT COUNT(*) FROM task_run WHERE status='running') + "
                    "(SELECT COUNT(*) FROM scheduled_task "
                    " WHERE lease_token IS NOT NULL AND lease_expires_at > NOW()) + "
                    "(SELECT COUNT(*) FROM platform_event WHERE status='processing') + "
                    "(SELECT COUNT(*) FROM notification_outbox WHERE status='processing');",
                ],
                environment=environment,
            )
            if outstanding.stdout.strip() != "0":
                raise AcceptanceError("durable work remained actively leased after worker shutdown")
            result["shutdown"] = {
                "worker_container_stopped": True,
                "supervisor_heartbeat_removed": True,
                "active_work_leases_after_shutdown": 0,
            }
            result["result"] = "passed"
            result["limitations"] = [
                "This is a short disposable restart/recovery check, not 24-hour endurance or scale acceptance.",
                "The internal Compose network has no Internet egress; no real providers, seeds, candidate, legacy, or production data are used.",
                "A healthy worker process and supervisor heartbeat do not prove every idle child is responsive or every business handler has output parity.",
                "The seed-free run verifies that shutdown leaves no active leases; it does not claim to exercise lease recovery during a long-running handler.",
            ]
            return result
        except Exception as exc:
            diagnostics = _failure_diagnostics(project, manifest, environment)
            if diagnostics:
                raise AcceptanceError(f"{exc}{diagnostics}") from exc
            raise
        finally:
            _run(
                [*_compose_command(project, manifest), "down", "--volumes", "--remove-orphans", "--rmi", "local"],
                environment=environment,
                timeout=120,
                check=False,
            )


def main() -> int:
    try:
        timeout = float(os.environ.get("KOKONUT_STANDARD_RECOVERY_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
        if not 15 <= timeout <= 1800:
            raise ValueError("KOKONUT_STANDARD_RECOVERY_TIMEOUT must be between 15 and 1800 seconds")
        result = _main(timeout)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps({"result": "failed", "error": f"{type(exc).__name__}: {exc}"}, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
