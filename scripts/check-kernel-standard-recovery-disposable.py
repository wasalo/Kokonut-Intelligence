#!/usr/bin/env python3
"""Exercise the split Standard API/worker profile through a disposable DB outage.

This is an opt-in Docker acceptance check. It composes only the Kernel
candidate and Standard overlays, strips all published ports, marks the single
runtime network internal, applies checksummed schema migrations only, and
removes the unique Compose project and volumes on every exit path.
"""

from __future__ import annotations

import copy
import hashlib
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
RUNTIME_ROLE_COMPOSE = ROOT / "docker-compose.kernel-runtime-role.yml"
DEFAULT_TIMEOUT_SECONDS = 180
HEARTBEAT_PATH = "/var/lib/kokonut/worker-progress/supervisor.json"


class AcceptanceError(RuntimeError):
    """A disposable Standard-profile acceptance assertion failed."""


def _ordered_schema_migration_files(directory: Path) -> list[Path]:
    """Return the numeric schema sources in migration-runner order."""
    return sorted(
        (
            path
            for path in directory.glob("*.sql")
            if path.stem.split("_", 1)[0].isdigit()
        ),
        key=lambda path: (int(path.stem.split("_", 1)[0]), path.name),
    )


def _snapshot_schema_migrations(
    source_directory: Path, snapshot_directory: Path
) -> tuple[list[Path], str]:
    """Copy an immutable, ordered schema set and reject source races.

    The migration CLI discovers files at run time. Supplying its schema
    directory with this private copy prevents a migration added or edited
    during acceptance from changing which SQL bytes the disposable database
    receives.
    """
    source_files = _ordered_schema_migration_files(source_directory)
    if not source_files:
        raise AcceptanceError("no ordered schema migrations were found")

    snapshot_directory.mkdir(parents=True, mode=0o700)
    captured: list[tuple[str, str]] = []
    try:
        for source in source_files:
            content = source.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            (snapshot_directory / source.name).write_bytes(content)
            captured.append((source.name, digest))

        current = [
            (path.name, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in _ordered_schema_migration_files(source_directory)
        ]
        if current != captured:
            raise AcceptanceError(
                "schema migration sources changed while the recovery snapshot was being captured"
            )

        copied = [
            (path.name, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in _ordered_schema_migration_files(snapshot_directory)
        ]
        if copied != captured:
            raise AcceptanceError("schema migration snapshot failed its content verification")
    except OSError as exc:
        raise AcceptanceError("could not capture a stable schema migration snapshot") from exc

    manifest = "\n".join(f"{name}\t{digest}" for name, digest in captured)
    snapshot_digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    return _ordered_schema_migration_files(snapshot_directory), snapshot_digest


def _migration_runner_command(
    project: str, manifest: Path, schema_directory: Path
) -> list[str]:
    """Run the repository migration CLI against the captured schema directory."""
    bootstrap = (
        "import sys; from pathlib import Path; "
        "from services.migration import cli; "
        "cli.SCHEMA_DIR = Path(sys.argv.pop(1)); "
        "sys.argv[0] = 'services.migration'; cli.main()"
    )
    return [
        sys.executable,
        "-c",
        bootstrap,
        str(schema_directory),
        "--compose-project",
        project,
        "--compose-file",
        str(manifest),
        "migrate",
        "--schemas-only",
    ]


def _image_schema_snapshot_probe() -> str:
    """Return a container-side manifest probe for the schema tree in the image."""
    return """
import hashlib
import json
from pathlib import Path

directory = Path('/app/schemas/postgres')
files = sorted(
    (path for path in directory.glob('*.sql') if path.stem.split('_', 1)[0].isdigit()),
    key=lambda path: (int(path.stem.split('_', 1)[0]), path.name),
)
manifest = chr(10).join(
    f"{path.name}\\t{hashlib.sha256(path.read_bytes()).hexdigest()}" for path in files
)
print(json.dumps({
    'count': len(files),
    'latest': f"schema:{files[-1].name}" if files else None,
    'sha256': hashlib.sha256(manifest.encode('utf-8')).hexdigest(),
}, sort_keys=True))
""".strip()


def _assert_image_schema_snapshot(
    output: str, *, expected_count: int, expected_latest: str, expected_digest: str
) -> dict[str, Any]:
    """Require the built API image to contain the exact captured migration bytes."""
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise AcceptanceError("built app image returned a malformed schema snapshot probe") from exc
    if not isinstance(payload, dict):
        raise AcceptanceError("built app image returned a malformed schema snapshot probe")
    expected = {
        "count": expected_count,
        "latest": expected_latest,
        "sha256": expected_digest,
    }
    if payload != expected:
        raise AcceptanceError(
            "built app image schema inventory does not match the captured migration snapshot "
            f"(expected count={expected_count}, latest={expected_latest}, sha256={expected_digest}; "
            f"observed count={payload.get('count')}, latest={payload.get('latest')}, "
            f"sha256={payload.get('sha256')})"
        )
    return payload


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
        detail = _redact_secrets((result.stderr or result.stdout).strip(), environment)
        raise AcceptanceError(
            f"{command[0]} {command[1] if len(command) > 1 else ''} failed "
            f"({result.returncode}): {detail[-2400:]}"
        )
    return result


def _redact_secrets(value: str, environment: dict[str, str]) -> str:
    for secret_name in (
        "POSTGRES_PASSWORD",
        "KOKONUT_DB_ADMIN_PASSWORD",
        "KOKONUT_RUNTIME_PASSWORD",
        "KOKONUT_OPERATOR_AUTH_PASSWORD",
        "KOKONUT_RATE_LIMIT_MAINTENANCE_PASSWORD",
        "KOKONUT_RATE_LIMIT_MAINTENANCE_DSN",
        "DIRECTUS_SECRET",
    ):
        secret = environment.get(secret_name, "")
        if secret:
            value = value.replace(secret, "[redacted]")
    return value


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
    runtime_password = secrets.token_urlsafe(32)
    operator_auth_password = secrets.token_urlsafe(32)
    rate_limit_maintenance_password = secrets.token_urlsafe(32)
    environment.update(
        {
            "POSTGRES_PASSWORD": password,
            "KOKONUT_DB_ADMIN_USER": "kokonut",
            "KOKONUT_DB_ADMIN_PASSWORD": password,
            "KOKONUT_RUNTIME_USER": "kokonut_runtime",
            "KOKONUT_RUNTIME_PASSWORD": runtime_password,
            "KOKONUT_OPERATOR_AUTH_USER": "kokonut_operator_auth",
            "KOKONUT_OPERATOR_AUTH_PASSWORD": operator_auth_password,
            "KOKONUT_RATE_LIMIT_MAINTENANCE_USER": (
                "kokonut_rate_limit_maintenance_login"
            ),
            "KOKONUT_RATE_LIMIT_MAINTENANCE_PASSWORD": rate_limit_maintenance_password,
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
    required = {"database", "app", "worker", "runtime-role-bootstrap"}
    services = isolated.get("services")
    if not isinstance(services, dict) or not required <= set(services):
        raise AcceptanceError("merged Standard Compose model lacks database/app/worker")
    selected = ["database", "app", "worker", "runtime-role-bootstrap"]
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

    _validate_explicit_runtime_role_bootstrap(
        isolated["services"]["app"],
        isolated["services"]["worker"],
        isolated["services"]["runtime-role-bootstrap"],
    )

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


def _validate_explicit_runtime_role_bootstrap(
    app: dict[str, Any], worker: dict[str, Any], bootstrap: dict[str, Any]
) -> None:
    profiles = bootstrap.get("profiles")
    if not isinstance(profiles, list) or "runtime-admin" not in profiles:
        raise AcceptanceError("runtime-role bootstrap must remain behind the runtime-admin profile")
    for name, service in (("app", app), ("worker", worker)):
        dependencies = service.get("depends_on", {})
        if isinstance(dependencies, dict) and "runtime-role-bootstrap" in dependencies:
            raise AcceptanceError(
                f"Standard {name} must not auto-run the privileged runtime-role bootstrap"
            )
        if isinstance(dependencies, list) and "runtime-role-bootstrap" in dependencies:
            raise AcceptanceError(
                f"Standard {name} must not auto-run the privileged runtime-role bootstrap"
            )


def _validate_split_commands(app: dict[str, Any], worker: dict[str, Any]) -> None:
    app_command = app.get("command")
    worker_command = worker.get("command")
    if not isinstance(app_command, list) or not isinstance(worker_command, list):
        raise AcceptanceError("API and worker commands must be explicit argument arrays")
    if "--require-schema" not in app_command or "--require-schema" not in worker_command:
        raise AcceptanceError("both Standard roles must require schema readiness")
    if "--require-runtime-role" not in app_command or "--require-runtime-role" not in worker_command:
        raise AcceptanceError("both Standard roles must require the non-admin runtime-role gate")
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
        outputs.append(_redact_secrets(output, environment))
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


def _runtime_role_attributes(output: str) -> dict[str, bool]:
    fields = output.strip().split("|")
    if len(fields) != 10 or any(value not in {"t", "f"} for value in fields):
        raise AcceptanceError("runtime role attribute query returned malformed output")
    attributes = {
        "login": fields[0] == "t",
        "inherit": fields[1] == "t",
        "superuser": fields[2] == "t",
        "create_database": fields[3] == "t",
        "create_role": fields[4] == "t",
        "replication": fields[5] == "t",
        "bypass_rls": fields[6] == "t",
        "owns_database": fields[7] == "t",
        "member_of_database_owner": fields[8] == "t",
        "has_role_memberships": fields[9] == "t",
    }
    if attributes != {
        "login": True,
        "inherit": False,
        "superuser": False,
        "create_database": False,
        "create_role": False,
        "replication": False,
        "bypass_rls": False,
        "owns_database": False,
        "member_of_database_owner": False,
        "has_role_memberships": False,
    }:
        raise AcceptanceError("kokonut_runtime role attributes exceed the least-privilege login contract")
    return attributes


def _assert_runtime_role_gate_rejected(returncode: int, output: str) -> None:
    if returncode == 0 or "runtime_role_unsafe" not in output:
        raise AcceptanceError("unsafe admin database credentials passed the runtime-role readiness gate")
    if "Started Kernel process" in output:
        raise AcceptanceError("runtime supervisor spawned a worker before rejecting the unsafe database role")


def _query_runtime_role_attributes(
    project: str, manifest: Path, environment: dict[str, str]
) -> dict[str, bool]:
    result = _run(
        [
            *_compose_command(project, manifest),
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
            "SELECT runtime_role.rolcanlogin, runtime_role.rolinherit, "
            "runtime_role.rolsuper, runtime_role.rolcreatedb, "
            "runtime_role.rolcreaterole, runtime_role.rolreplication, "
            "runtime_role.rolbypassrls, database_row.datdba = runtime_role.oid, "
            "(database_row.datdba <> runtime_role.oid AND "
            "pg_catalog.pg_has_role(runtime_role.oid, database_row.datdba, 'MEMBER')), "
            "EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members AS membership "
            "WHERE membership.member = runtime_role.oid) "
            "FROM pg_catalog.pg_roles AS runtime_role "
            "JOIN pg_catalog.pg_database AS database_row "
            "ON database_row.datname = pg_catalog.current_database() "
            "WHERE runtime_role.rolname='kokonut_runtime';",
        ],
        environment=environment,
    )
    return _runtime_role_attributes(result.stdout)


def _runtime_identity(
    project: str, manifest: Path, environment: dict[str, str], service: str
) -> str:
    query = """from services.common.database import get_db
connection = get_db()
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user')
        print(cursor.fetchone()[0])
finally:
    connection.close()
"""
    result = _run(
        [
            *_compose_command(project, manifest),
            "exec",
            "-T",
            service,
            "python3",
            "-c",
            query,
        ],
        environment=environment,
    )
    return result.stdout.strip()


def _assert_runtime_write_denied(
    project: str, manifest: Path, environment: dict[str, str]
) -> None:
    probe = """from services.common.database import get_db
connection = get_db()
try:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO public.schema_version (version, description) VALUES (%s, %s)',
                ('standard-recovery-denial-probe', 'rolled back privilege probe'),
            )
    except Exception as exc:
        connection.rollback()
        if type(exc).__name__ != 'InsufficientPrivilege':
            raise
        print('denied')
    else:
        connection.rollback()
        raise SystemExit('runtime login unexpectedly wrote schema_version')
finally:
    connection.close()
"""
    result = _run(
        [
            *_compose_command(project, manifest),
            "exec",
            "-T",
            "app",
            "python3",
            "-c",
            probe,
        ],
        environment=environment,
    )
    if result.stdout.strip() != "denied":
        raise AcceptanceError("kokonut_runtime could not prove schema_version DML remains denied")


def _assert_gateway_rate_limit_boundary(
    project: str, manifest: Path, environment: dict[str, str]
) -> None:
    """Verify the private bucket ACL and both bounded function identities."""
    compose = _compose_command(project, manifest)
    query = """SELECT
        has_table_privilege('kokonut_runtime', 'public.gateway_rate_bucket', 'SELECT'),
        has_table_privilege('kokonut_runtime', 'public.gateway_rate_bucket', 'INSERT'),
        has_table_privilege('kokonut_runtime', 'public.gateway_rate_bucket', 'UPDATE'),
        has_table_privilege('kokonut_runtime', 'public.gateway_rate_bucket', 'DELETE'),
        has_table_privilege('kokonut_directus_runtime', 'public.gateway_rate_bucket', 'SELECT'),
        has_table_privilege('kokonut_directus_runtime', 'public.gateway_rate_bucket', 'INSERT'),
        has_table_privilege('kokonut_directus_runtime', 'public.gateway_rate_bucket', 'UPDATE'),
        has_table_privilege('kokonut_directus_runtime', 'public.gateway_rate_bucket', 'DELETE'),
        has_table_privilege('kokonut_rate_limit_maintenance_login',
            'public.gateway_rate_bucket', 'SELECT'),
        has_table_privilege('kokonut_rate_limit_maintenance_login',
            'public.gateway_rate_bucket', 'INSERT'),
        has_table_privilege('kokonut_rate_limit_maintenance_login',
            'public.gateway_rate_bucket', 'UPDATE'),
        has_table_privilege('kokonut_rate_limit_maintenance_login',
            'public.gateway_rate_bucket', 'DELETE'),
        has_function_privilege('kokonut_runtime',
            'kokonut_security.consume_gateway_rate_bucket(text,integer,boolean)', 'EXECUTE'),
        has_function_privilege('kokonut_runtime',
            'kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(integer)', 'EXECUTE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security.consume_gateway_rate_bucket(text,integer,boolean)', 'EXECUTE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(integer)', 'EXECUTE'),
        has_schema_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security', 'USAGE'),
        has_schema_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_rate_limit_maintenance', 'USAGE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security.resolve_mobile_device_token(text)', 'EXECUTE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security.redeem_mobile_enrollment(text,text,text,text,text,text,text,text)', 'EXECUTE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security.set_mobile_device_context(text,text,uuid)', 'EXECUTE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security.current_tenant_context()', 'EXECUTE'),
        has_function_privilege('kokonut_rate_limit_maintenance_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'),
        (SELECT pg_catalog.pg_get_userbyid(proowner)
           FROM pg_catalog.pg_proc
          WHERE oid = 'kokonut_security.consume_gateway_rate_bucket(text,integer,boolean)'::regprocedure),
        (SELECT pg_catalog.pg_get_userbyid(proowner)
           FROM pg_catalog.pg_proc
          WHERE oid = 'kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(integer)'::regprocedure),
        (SELECT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls
           FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_gateway_rate_limit_owner'),
        (SELECT relrowsecurity AND relforcerowsecurity
           FROM pg_catalog.pg_class WHERE oid = 'public.gateway_rate_bucket'::regclass),
        (SELECT access_mode
           FROM kokonut_security.directus_relation_privilege_policy
          WHERE schema_name = 'public' AND relation_name = 'gateway_rate_bucket');"""
    acl = _run(
        [
            *compose,
            "exec", "-T", "database", "psql", "-XAt", "-F", "|",
            "-U", "kokonut", "-d", "kokonut_intelligence",
            "-v", "ON_ERROR_STOP=1", "-c", query,
        ],
        environment=environment,
    )
    expected_acl = (
        "f|f|f|f|f|f|f|f|f|f|f|f|t|f|f|t|t|t|f|f|f|f|f|"
        "kokonut_gateway_rate_limit_owner|kokonut_gateway_rate_limit_owner|f|t|no_access"
    )
    if acl.stdout.strip() != expected_acl:
        raise AcceptanceError(
            "migration 712 did not establish the private rate-limit table and function ACL; "
            f"received {acl.stdout.strip()}"
        )

    caller_hash_a = "a" * 64
    caller_hash_b = "b" * 64
    consume = f"""SET ROLE kokonut_runtime;
SELECT allowed::text || '|' || retry_after_seconds::text
  FROM kokonut_security.consume_gateway_rate_bucket('{caller_hash_a}', 100, true);
SELECT allowed::text || '|' || retry_after_seconds::text
  FROM kokonut_security.consume_gateway_rate_bucket('{caller_hash_a}', 100, true);
SELECT allowed::text || '|' || retry_after_seconds::text
  FROM kokonut_security.consume_gateway_rate_bucket('{caller_hash_b}', 100, false);
SELECT allowed::text || '|' || retry_after_seconds::text
  FROM kokonut_security.consume_gateway_rate_bucket('{caller_hash_b}', 100, true);
RESET ROLE;"""
    runtime_result = _run(
        [
            *compose,
            "exec", "-T", "database", "psql", "-XAtq",
            "-U", "kokonut", "-d", "kokonut_intelligence",
            "-v", "ON_ERROR_STOP=1", "-c", consume,
        ],
        environment=environment,
    )
    decisions = runtime_result.stdout.splitlines()
    if (
        len(decisions) != 4
        or decisions[0] != "true|1"
        or not decisions[1].startswith("false|")
        or decisions[2] != "true|1"
        or decisions[3] != "true|1"
    ):
        raise AcceptanceError(
            "runtime consume function did not preserve refill, deny, and check-only behavior; "
            f"received {decisions!r}"
        )

    for role in ("kokonut_runtime", "kokonut_directus_runtime"):
        denied = _run(
            [
                *compose,
                "exec", "-T", "database", "psql", "-XAt",
                "-U", "kokonut", "-d", "kokonut_intelligence",
                "-v", "ON_ERROR_STOP=1", "-c",
                f"SET ROLE {role}; SELECT count(*) FROM public.gateway_rate_bucket;",
            ],
            environment=environment,
            check=False,
        )
        if denied.returncode == 0 or "permission denied" not in denied.stderr.lower():
            raise AcceptanceError(
                f"{role} retained direct access to gateway_rate_bucket"
            )

    denied_context = _run(
        [
            *compose,
            "exec", "-T", "database", "psql", "-XAtq",
            "-U", "kokonut", "-d", "kokonut_intelligence",
            "-v", "ON_ERROR_STOP=1", "-c",
            "SET ROLE kokonut_rate_limit_maintenance_login; "
            "SELECT * FROM kokonut_security.set_gateway_tenant_context("
            "NULL, NULL, NULL, NULL, NULL);",
        ],
        environment=environment,
        check=False,
    )
    if denied_context.returncode == 0 or "permission denied for function set_gateway_tenant_context" not in (
        denied_context.stderr.lower()
    ):
        raise AcceptanceError(
            "rate-limit maintenance login retained access to a private Gateway context function"
        )

    cleanup = _run(
        [
            *compose,
            "exec", "-T", "database", "psql", "-XAtq",
            "-U", "kokonut", "-d", "kokonut_intelligence",
            "-v", "ON_ERROR_STOP=1", "-c",
            "SET ROLE kokonut_rate_limit_maintenance_login; "
            "SELECT kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(5); RESET ROLE;",
        ],
        environment=environment,
    )
    if cleanup.stdout.strip() != "0":
        raise AcceptanceError("dedicated rate-limit maintenance function did not return a bounded count")


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
                str(RUNTIME_ROLE_COMPOSE),
                "-f",
                str(PROXY_COMPOSE),
                "--profile",
                "runtime-admin",
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

            # Freeze migration inputs before building the app/worker image.
            # Readiness checks run from the image's schema tree, so migration
            # replay and runtime readiness must consume the same bytes.
            snapshot_directory = temp_root / "postgres-schema-snapshot"
            schema_files, snapshot_digest = _snapshot_schema_migrations(
                ROOT / "schemas" / "postgres", snapshot_directory
            )
            expected_schemas = len(schema_files)
            expected_latest_migration = f"schema:{schema_files[-1].name}"

            compose = _compose_command(project, manifest)
            _run([*compose, "build", "app", "worker"], environment=environment, timeout=2400)
            for service in ("app", "worker"):
                image_schema_probe = _run(
                    [
                        *compose,
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        service,
                        "python3",
                        "-c",
                        _image_schema_snapshot_probe(),
                    ],
                    environment=environment,
                    timeout=30,
                )
                _assert_image_schema_snapshot(
                    image_schema_probe.stdout,
                    expected_count=expected_schemas,
                    expected_latest=expected_latest_migration,
                    expected_digest=snapshot_digest,
                )
            result["migration_snapshot"] = {
                "schema_count": expected_schemas,
                "latest_migration": expected_latest_migration,
                "sha256": snapshot_digest,
                "app_image_matches": True,
                "worker_image_matches": True,
            }
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
                    "-e",
                    "PG_USER=kokonut",
                    "-e",
                    f"PG_PASSWORD={environment['POSTGRES_PASSWORD']}",
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
            # Point the ordered migration CLI at the same content-verified
            # schema snapshot that was checked into the built app image.
            migration = _run(
                _migration_runner_command(project, manifest, snapshot_directory),
                environment=migration_environment,
                timeout=2400,
            )
            expected_summary = f"Applied: {expected_schemas}, Failed: 0"
            if expected_summary not in migration.stdout:
                runner_output = _redact_secrets(
                    f"{migration.stdout}\n{migration.stderr}", environment
                ).strip()
                output_tail = runner_output[-2000:] if runner_output else "<no runner output>"
                raise AcceptanceError(
                    "ordered migration runner did not report all schema files from the "
                    f"pre-run snapshot applied (expected {expected_summary}; "
                    f"latest {expected_latest_migration}); runner output tail:\n{output_tail}"
                )
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
                "source_snapshot_sha256": snapshot_digest,
            }

            unsafe_runtime_role = _run(
                [
                    *compose,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "-e",
                    "PG_USER=kokonut",
                    "-e",
                    f"PG_PASSWORD={environment['POSTGRES_PASSWORD']}",
                    "app",
                    "python3",
                    "-m",
                    "services.core.runtime",
                    "--workers-only",
                    "--require-runtime-role",
                ],
                environment=environment,
                timeout=30,
                check=False,
            )
            _assert_runtime_role_gate_rejected(
                unsafe_runtime_role.returncode,
                unsafe_runtime_role.stdout + unsafe_runtime_role.stderr,
            )
            result["unsafe_admin_runtime_role_fails_before_children"] = True

            _run(
                [
                    *compose,
                    "--profile",
                    "runtime-admin",
                    "run",
                    "--rm",
                    "-T",
                    "runtime-role-bootstrap",
                ],
                environment=environment,
                timeout=600,
            )
            _assert_gateway_rate_limit_boundary(project, manifest, environment)
            role_attributes = _query_runtime_role_attributes(project, manifest, environment)
            _run([*compose, "up", "-d", "app", "worker", "proxy"], environment=environment, timeout=120)
            app = _wait_for_health(project, manifest, environment, "app", "healthy", timeout)
            worker = _wait_for_health(project, manifest, environment, "worker", "healthy", timeout)
            app_identity = _runtime_identity(project, manifest, environment, "app")
            worker_identity = _runtime_identity(project, manifest, environment, "worker")
            if app_identity != "kokonut_runtime" or worker_identity != "kokonut_runtime":
                raise AcceptanceError("Standard app and worker did not connect as kokonut_runtime")
            _assert_runtime_write_denied(project, manifest, environment)
            _assert_gateway_rate_limit_boundary(project, manifest, environment)

            _run(
                [
                    *compose,
                    "--profile",
                    "runtime-admin",
                    "run",
                    "--rm",
                    "-T",
                    "runtime-role-bootstrap",
                ],
                environment=environment,
                timeout=600,
            )
            role_attributes_after_reapply = _query_runtime_role_attributes(
                project, manifest, environment
            )
            _assert_runtime_write_denied(project, manifest, environment)
            result["runtime_role"] = {
                "bootstrap_profile": "runtime-admin",
                "bootstrap_ran_explicitly_after_migrations": True,
                "role_attributes": role_attributes,
                "app_database_user": app_identity,
                "worker_database_user": worker_identity,
                "schema_version_insert_denied_after_initial_provision": True,
                "schema_version_insert_denied_after_provisioner_reapply": True,
                "role_attributes_preserved_after_reapply": (
                    role_attributes_after_reapply == role_attributes
                ),
            }
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
