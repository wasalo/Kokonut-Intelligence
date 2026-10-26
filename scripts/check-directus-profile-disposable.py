#!/usr/bin/env python3
"""Start the optional Directus profile on a fresh disposable Kernel database."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from directus_permission_snapshot import (
    MANAGED_POLICY_IDS,
    custom_permission_license_restricted,
    permission_snapshot_query,
    summarize_permission_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
PROJECT = f"kokonut-directus-profile-check-{uuid.uuid4().hex[:10]}"
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-23-recovery/directus-effective-permissions.json"
SNAPSHOT_EVIDENCE = ROOT / "docs/refactor/builds/2026-10-23-recovery/directus-effective-permission-rows.json"
DASHBOARD_EVIDENCE = ROOT / "docs/refactor/builds/2026-10-26-recovery/directus-dashboard-field-allowlist-disposable.json"
METRIC_VALUE_EVIDENCE = ROOT / "docs/refactor/builds/2026-10-26-recovery/directus-metric-value-location-scope.json"
PERMISSION_SEED = ROOT / "config/directus/permissions.sql"
EXPECTED_PERMISSION_ROWS = 175
EXPECTED_DASHBOARD_AUDITOR_FIELDS = (
    "id,name,description,dataset_type,location_id,query_id,refresh_interval_minutes,"
    "last_refreshed_at,status,metadata,created_at,updated_at,updated_by"
)
EXPECTED_METRIC_VALUE_AUDITOR_FIELDS = (
    "id,metric_id,location_id,period_start,period_end,value,unit,"
    "computation_method,computed_at,verified,verified_at"
)


def free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def run(
    command: list[str],
    *,
    env: dict[str, str],
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def compose_base() -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "docker-compose.kernel-candidate.yml"),
        "-f",
        str(ROOT / "docker-compose.kernel-directus.yml"),
    ]


def require_success(result: subprocess.CompletedProcess[str], action: str, env: dict[str, str]) -> None:
    if result.returncode == 0:
        return
    diagnostic = "\n".join((result.stdout or "", result.stderr or ""))
    for name in (
        "POSTGRES_PASSWORD",
        "DIRECTUS_SECRET",
        "ADMIN_PASSWORD",
        "KOKONUT_DIRECTUS_RUNTIME_PASSWORD",
    ):
        diagnostic = diagnostic.replace(env[name], "[redacted]")
    raise RuntimeError(f"{action} failed ({result.returncode}):\n" + "\n".join(diagnostic.splitlines()[-35:]))


def request(
    url: str,
    *,
    body: dict[str, object] | None = None,
    token: str | None = None,
) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            payload = response.read()
            try:
                return response.status, json.loads(payload)
            except json.JSONDecodeError:
                return response.status, payload.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload) if payload else ""
        except json.JSONDecodeError:
            return exc.code, payload.decode("utf-8", errors="replace")


def api_error_codes(payload: dict | str) -> list[str]:
    if not isinstance(payload, dict):
        return []
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return []
    return [
        str(error.get("extensions", {}).get("code"))
        for error in errors
        if isinstance(error, dict) and isinstance(error.get("extensions"), dict)
        and error["extensions"].get("code")
    ]


def api_error_messages(payload: dict | str) -> list[str]:
    if not isinstance(payload, dict):
        return []
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return []
    return [
        str(error["message"])
        for error in errors
        if isinstance(error, dict) and isinstance(error.get("message"), str)
    ]


def main() -> int:
    port = free_loopback_port()
    admin_email = "directus-profile-check@example.com"
    secrets_by_name = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "DIRECTUS_SECRET": secrets.token_urlsafe(48),
        "ADMIN_PASSWORD": secrets.token_urlsafe(32),
        "KOKONUT_DIRECTUS_RUNTIME_PASSWORD": secrets.token_urlsafe(32),
    }
    env = os.environ.copy()
    for name in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME"):
        env.pop(name, None)
    env.update(secrets_by_name)
    env.update(
        {
            "ADMIN_EMAIL": admin_email,
            "KOKONUT_KERNEL_DIRECTUS_BIND": "127.0.0.1",
            "KOKONUT_KERNEL_DIRECTUS_PORT": str(port),
            "KOKONUT_DIRECTUS_PUBLIC_URL": f"http://127.0.0.1:{port}",
            "KOKONUT_DIRECTUS_RUNTIME_USER": "kokonut_directus_runtime",
            "KOKONUT_DB_ADMIN_USER": "kokonut",
        }
    )
    compose = compose_base()
    evidence: dict[str, object] = {
        "status": "failed",
        "project": PROJECT,
        "database": "fresh isolated Kernel PostgreSQL volume",
        "profile": "optional Directus overlay",
        "secrets_logged": False,
        "candidate_or_legacy_database_used": False,
    }
    first_permission_rows: list[dict] | None = None

    try:
        build_extensions = run(["make", "hooks-build"], env=env)
        require_success(build_extensions, "Directus extension build", env)

        database_start = run([*compose, "up", "-d", "database"], env=env)
        require_success(database_start, "disposable Kernel database start", env)
        database_ready = False
        database_deadline = time.monotonic() + 90
        while time.monotonic() < database_deadline:
            readiness = run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "pg_isready",
                    "-h", "127.0.0.1", "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                ],
                env=env,
            )
            if readiness.returncode == 0:
                database_ready = True
                break
            time.sleep(1)
        if not database_ready:
            container_status = run([*compose, "ps", "--all"], env=env)
            database_logs = run(
                [*compose, "logs", "--no-color", "--tail", "40", "database"], env=env
            )
            diagnostics = "\n".join(
                (
                    "disposable Kernel PostgreSQL did not become ready",
                    "compose ps:",
                    container_status.stdout or container_status.stderr,
                    "database logs:",
                    database_logs.stdout or database_logs.stderr,
                )
            )
            for secret in secrets_by_name.values():
                diagnostics = diagnostics.replace(secret, "[redacted]")
            raise RuntimeError(diagnostics)

        schema_setup = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "CREATE SCHEMA kokonut AUTHORIZATION kokonut",
            ],
            env=env,
        )
        require_success(schema_setup, "migration-owned Kokonut schema fixture", env)

        agent_task_setup = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                """
                CREATE TABLE public.agent_task (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    task_type varchar(100) NOT NULL,
                    subject_type varchar(100),
                    subject_id uuid,
                    requested_by uuid,
                    inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
                    output jsonb,
                    error_message text,
                    execution_status varchar(50) DEFAULT 'queued',
                    review_status varchar(50) DEFAULT 'draft',
                    high_risk boolean DEFAULT false,
                    requires_human_approval boolean DEFAULT false,
                    created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now()
                )
                """,
            ],
            env=env,
        )
        require_success(agent_task_setup, "synthetic Directus agent_task collection", env)

        role = run([*compose, "--profile", "directus-admin", "run", "--rm", "directus-role-bootstrap"], env=env)
        require_success(role, "Directus role bootstrap", env)
        bootstrap = run([*compose, "--profile", "directus-admin", "run", "--rm", "directus-bootstrap"], env=env)
        require_success(bootstrap, "owner-backed Directus bootstrap", env)

        permission_seed = PERMISSION_SEED.read_text(encoding="utf-8")
        permission_seed_command = [
            *compose,
            "exec",
            "-T",
            "database",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
        ]
        seed_first = run(permission_seed_command, env=env, input_text=permission_seed)
        require_success(seed_first, "Directus permission seed", env)
        policy_ids = ",\n".join(f"'{policy_id}'" for policy_id in MANAGED_POLICY_IDS)
        permission_counts_query = f"""
            SELECT
                count(*) FILTER (WHERE collection = 'farm_activity'),
                count(*) FILTER (WHERE collection = 'field_note')
              FROM public.directus_permissions
             WHERE policy IN ({policy_ids})
        """

        def permission_counts() -> tuple[int, int]:
            result = run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-X",
                    "-t",
                    "-A",
                    "-F",
                    "|",
                    "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                    "-c",
                    permission_counts_query,
                ],
                env=env,
            )
            require_success(result, "Directus permission seed verification", env)
            values = result.stdout.strip().split("|")
            if len(values) != 2 or not all(value.isdigit() for value in values):
                raise RuntimeError("Directus permission seed returned an unexpected count shape")
            return int(values[0]), int(values[1])

        def effective_permission_rows() -> list[dict]:
            result = run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-X",
                    "-t",
                    "-A",
                    "-U",
                    "kokonut",
                    "-d",
                    "kokonut_intelligence",
                    "-c",
                    permission_snapshot_query(),
                ],
                env=env,
            )
            require_success(result, "Directus effective permission snapshot", env)
            try:
                rows = json.loads(result.stdout.strip())
            except json.JSONDecodeError as exc:
                raise RuntimeError("Directus permission snapshot returned invalid JSON") from exc
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise RuntimeError("Directus permission snapshot returned an unexpected shape")
            return rows

        first_counts = permission_counts()
        if first_counts[0] != 0 or first_counts[1] == 0:
            raise RuntimeError("Directus seed must remove farm_activity while preserving other role permissions")
        first_permission_rows = effective_permission_rows()
        if len(first_permission_rows) != EXPECTED_PERMISSION_ROWS:
            raise RuntimeError(
                "fresh Directus seed effective row count differs from its curated source inventory"
            )
        dashboard_permissions = [
            row for row in first_permission_rows
            if row.get("collection") == "dashboard_dataset"
            and row.get("action") == "read"
        ]
        if (
            len(dashboard_permissions) != 1
            or dashboard_permissions[0].get("policy") != "Auditor Policy"
            or dashboard_permissions[0].get("fields") != EXPECTED_DASHBOARD_AUDITOR_FIELDS
            or "query_sql" in str(dashboard_permissions[0].get("fields"))
        ):
            raise RuntimeError(
                "Directus dashboard read permission must explicitly exclude archived query_sql"
            )
        metric_value_permissions = [
            row for row in first_permission_rows
            if row.get("collection") == "metric_value"
            and row.get("action") == "read"
        ]
        if (
            len(metric_value_permissions) != 1
            or metric_value_permissions[0].get("policy") != "Auditor Policy"
            or metric_value_permissions[0].get("fields") != EXPECTED_METRIC_VALUE_AUDITOR_FIELDS
            or any(
                field in str(metric_value_permissions[0].get("fields"))
                for field in ("source_record_ids", "metadata", "verified_by", "verification_notes")
            )
        ):
            raise RuntimeError(
                "Directus metric-value read permission must use the reviewed result-field allowlist"
            )
        if any(row.get("collection") == "farm_activity" for row in first_permission_rows):
            raise RuntimeError("managed farm_activity permissions remain after the fresh seed")
        legacy_wildcard = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-X",
                "-q",
                "-t",
                "-A",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-c",
                "UPDATE public.directus_permissions SET fields = '*' "
                "WHERE policy = 'b1000000-0000-0000-0000-000000000009' "
                "AND collection = 'dashboard_dataset' AND action = 'read' "
                "RETURNING fields",
            ],
            env=env,
        )
        require_success(legacy_wildcard, "legacy dashboard permission fixture", env)
        if legacy_wildcard.stdout.strip() != "*":
            raise RuntimeError("failed to establish the legacy dashboard wildcard fixture")
        metric_wildcard = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-X",
                "-q",
                "-t",
                "-A",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-c",
                "UPDATE public.directus_permissions SET fields = '*' "
                "WHERE policy = 'b1000000-0000-0000-0000-000000000009' "
                "AND collection = 'metric_value' AND action = 'read' "
                "RETURNING fields",
            ],
            env=env,
        )
        require_success(metric_wildcard, "legacy metric-value permission fixture", env)
        if metric_wildcard.stdout.strip() != "*":
            raise RuntimeError("failed to establish the legacy metric-value wildcard fixture")
        seed_replay = run(permission_seed_command, env=env, input_text=permission_seed)
        require_success(seed_replay, "Directus permission seed replay", env)
        replay_counts = permission_counts()
        if replay_counts != first_counts:
            raise RuntimeError("Directus permission seed replay changed curated role-permission counts")
        replay_permission_rows = effective_permission_rows()
        if replay_permission_rows != first_permission_rows:
            raise RuntimeError("Directus permission seed replay changed the effective permission snapshot")

        start = run([*compose, "up", "-d", "directus"], env=env)
        require_success(start, "Directus runtime start", env)

        base_url = f"http://127.0.0.1:{port}"
        ping_status = 0
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                ping_status, _ = request(f"{base_url}/server/ping")
                if ping_status == 200:
                    break
            except (OSError, TimeoutError):
                pass
            time.sleep(1)
        if ping_status != 200:
            raise RuntimeError("Directus did not become healthy on its loopback endpoint")

        login_status, login = request(
            f"{base_url}/auth/login",
            body={"email": admin_email, "password": secrets_by_name["ADMIN_PASSWORD"]},
        )
        if login_status != 200 or not isinstance(login, dict) or not login.get("data", {}).get("access_token"):
            raise RuntimeError(f"Directus owner login failed with HTTP {login_status}")
        admin_token = login["data"]["access_token"]

        def create_role_user(role_id: str, role_name: str) -> tuple[str, str]:
            email = f"{role_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:12]}@example.com"
            password = secrets.token_urlsafe(32)
            status, payload = request(
                f"{base_url}/users",
                token=admin_token,
                body={"email": email, "password": password, "role": role_id, "status": "active"},
            )
            user_id = payload.get("data", {}).get("id") if isinstance(payload, dict) else None
            if status not in (200, 201) or not isinstance(user_id, str):
                raise RuntimeError(f"synthetic {role_name} Directus user creation failed with HTTP {status}")
            return email, password

        def role_login(email: str, password: str, role_name: str, role_id: str) -> str:
            status, payload = request(
                f"{base_url}/auth/login",
                body={"email": email, "password": password},
            )
            access_token = (
                payload.get("data", {}).get("access_token") if isinstance(payload, dict) else None
            )
            if status != 200 or not isinstance(access_token, str):
                raise RuntimeError(f"synthetic {role_name} Directus login failed with HTTP {status}")
            me_status, me_payload = request(f"{base_url}/users/me", token=access_token)
            actual_role = (
                me_payload.get("data", {}).get("role")
                if isinstance(me_payload, dict)
                else None
            )
            if me_status != 200 or actual_role != role_id:
                raise RuntimeError(
                    f"synthetic {role_name} Directus identity role mismatch (HTTP {me_status})"
                )
            return access_token

        agent_write_email, agent_write_password = create_role_user(
            "a1000000-0000-0000-0000-000000000007", "Agent Write"
        )
        field_worker_email, field_worker_password = create_role_user(
            "a1000000-0000-0000-0000-000000000001", "Field Worker"
        )
        agent_write_role_id = "a1000000-0000-0000-0000-000000000007"
        field_worker_role_id = "a1000000-0000-0000-0000-000000000001"
        agent_write_token = role_login(
            agent_write_email, agent_write_password, "Agent Write", agent_write_role_id
        )
        field_worker_token = role_login(
            field_worker_email, field_worker_password, "Field Worker", field_worker_role_id
        )

        api_permission_status, api_permission_payload = request(
            f"{base_url}/permissions",
            token=admin_token,
            body={
                "collection": "agent_task",
                "action": "create",
                "permissions": {},
                "validation": {},
                "fields": ["task_type", "inputs", "subject_id", "subject_type", "requested_by"],
                "policy": "b1000000-0000-0000-0000-000000000007",
            },
        )
        permission_api_restricted = custom_permission_license_restricted(
            api_permission_status, api_permission_payload
        )
        if api_permission_status not in (200, 201) and not permission_api_restricted:
            raise RuntimeError(
                "Directus permission API returned an unexpected result "
                f"(HTTP {api_permission_status}; codes {api_error_codes(api_permission_payload)}; "
                f"messages {api_error_messages(api_permission_payload)})"
            )

        permissions_me_status, permissions_me_payload = request(
            f"{base_url}/permissions/me", token=agent_write_token
        )
        permissions_me_data = (
            permissions_me_payload.get("data")
            if isinstance(permissions_me_payload, dict)
            else None
        )
        raw_agent_task_permissions = (
            permissions_me_data.get("agent_task", {})
            if isinstance(permissions_me_data, dict)
            else {}
        )
        agent_task_permissions = {
            action: {
                "access": permission.get("access"),
                "fields": permission.get("fields"),
            }
            for action, permission in raw_agent_task_permissions.items()
            if isinstance(permission, dict)
        }

        agent_read_status, agent_read_payload = request(
            f"{base_url}/items/agent_task", token=agent_write_token
        )
        if agent_read_status != 200:
            raise RuntimeError(
                "Agent Write could not read its permitted agent_task collection "
                f"(HTTP {agent_read_status}; Directus error codes "
                f"{api_error_codes(agent_read_payload)}; messages "
                f"{api_error_messages(agent_read_payload)})"
            )

        allowed_create_status, allowed_create = request(
            f"{base_url}/items/agent_task",
            token=agent_write_token,
            body={
                "task_type": "cids_export",
                "subject_type": "synthetic_acceptance",
                "inputs": {"fixture": True},
            },
        )
        if permission_api_restricted:
            if allowed_create_status not in (401, 403, 404):
                raise RuntimeError(
                    "Agent Write unexpectedly created an item while Directus custom permissions "
                    f"are license-restricted (HTTP {allowed_create_status})"
                )
            if agent_task_permissions.get("create", {}).get("access") != "none":
                raise RuntimeError(
                    "Directus custom permission license restriction did not fail closed for Agent Write"
                )
            forbidden_field_status = None
        else:
            if allowed_create_status not in (200, 201):
                raise RuntimeError(
                    "Agent Write could not create an allowlisted agent_task after the Directus API "
                    f"accepted its grant (HTTP {allowed_create_status}; codes "
                    f"{api_error_codes(allowed_create)}; messages {api_error_messages(allowed_create)}; "
                    f"permissions/me HTTP {permissions_me_status}, agent_task {agent_task_permissions})"
                )

            forbidden_field_status, _ = request(
                f"{base_url}/items/agent_task",
                token=agent_write_token,
                body={
                    "task_type": "cids_export",
                    "inputs": {"fixture": "forbidden field"},
                    "review_status": "published",
                },
            )
            if forbidden_field_status not in (400, 403, 422):
                raise RuntimeError(
                    "Agent Write forbidden-field create did not fail closed "
                    f"(HTTP {forbidden_field_status})"
                )

        ungranted_create_status, _ = request(
            f"{base_url}/items/agent_task",
            token=field_worker_token,
            body={"task_type": "cids_export", "inputs": {"fixture": "ungranted role"}},
        )
        if ungranted_create_status not in (401, 403, 404):
            raise RuntimeError(
                "Field Worker could create agent_task without a create permission "
                f"(HTTP {ungranted_create_status})"
            )

        task_count = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-X",
                "-t",
                "-A",
                "-c",
                "SELECT count(*) FROM public.agent_task",
            ],
            env=env,
        )
        require_success(task_count, "synthetic Directus agent_task row count", env)
        expected_task_count = "0" if permission_api_restricted else "1"
        if task_count.stdout.strip() != expected_task_count:
            raise RuntimeError("Directus denied/forbidden agent_task requests changed the synthetic row count")

        database_result = run(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "psql",
                "-U",
                "kokonut",
                "-d",
                "kokonut_intelligence",
                "-X",
                "-t",
                "-A",
                "-c",
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND usename = 'kokonut_directus_runtime'",
            ],
            env=env,
        )
        require_success(database_result, "Directus runtime database identity check", env)
        if not database_result.stdout.strip().isdigit() or int(database_result.stdout.strip()) < 1:
            raise RuntimeError("Directus connections did not use the dedicated runtime role")

        evidence.update(
            {
                "status": "passed",
                "directus_health": ping_status,
                "owner_login": login_status,
                "runtime_database_identity": "kokonut_directus_runtime",
                "owner_backed_bootstrap": "passed",
                "role_api_acceptance": {
                    "collection": "agent_task",
                    "permission_management_api_status": api_permission_status,
                    "custom_permissions_license_restricted": permission_api_restricted,
                    "permission_management_error_codes": api_error_codes(api_permission_payload),
                    "agent_write_effective_permissions": agent_task_permissions,
                    "agent_write_allowlisted_create_status": allowed_create_status,
                    "agent_write_forbidden_field_status": forbidden_field_status,
                    "field_worker_ungranted_create_status": ungranted_create_status,
                    "persisted_synthetic_rows": int(expected_task_count),
                    "denied_operations_preserved_row_count": True,
                    "synthetic_role_users_removed_with_database": True,
                },
                "permission_seed": {
                    "first_application": "passed",
                    "replay": "passed",
                    "repository_managed_farm_activity_permissions": first_counts[0],
                    "other_curated_permissions": first_counts[1],
                    **summarize_permission_snapshot(first_permission_rows),
                    "legacy_dashboard_wildcard_repaired": True,
                    "legacy_metric_value_wildcard_repaired": True,
                    "replay_snapshot_unchanged": True,
                },
                "loopback_only": True,
            }
        )
    finally:
        cleanup = run([*compose, "down", "--volumes", "--remove-orphans"], env=env)
        evidence["cleanup"] = "passed" if cleanup.returncode == 0 else "failed"
        evidence["checked_at"] = datetime.now(timezone.utc).isoformat()
        if cleanup.returncode:
            raise RuntimeError("failed to remove the disposable Directus profile project")
        if evidence["status"] == "passed":
            if first_permission_rows is None:
                raise RuntimeError("passed Directus evidence is missing its effective permission snapshot")
            EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            source_bytes = PERMISSION_SEED.read_bytes()
            snapshot = {
                "format_version": 1,
                "result": "passed",
                "runtime": "Directus 12.1.1",
                "database": "fresh isolated Kernel PostgreSQL volume",
                "database_identity": "kokonut_directus_runtime",
                "permission_seed": "config/directus/permissions.sql",
                "permission_seed_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "applied_and_replayed": True,
                "replay_snapshot_unchanged": True,
                "limitations": [
                    "This captures repository-managed policies in a fresh disposable profile, not a populated deployment.",
                    "Built-in Directus policies and operator-created custom policies are excluded.",
                    "The snapshot describes effective stored role/field/row filters after the seed, but does not test API requests for every role or hook side effect.",
                    "No candidate or legacy database, provider credentials, or business records were used.",
                ],
                "summary": summarize_permission_snapshot(first_permission_rows),
                "permissions": first_permission_rows,
            }
            SNAPSHOT_EVIDENCE.write_text(
                json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            dashboard_evidence = {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "result": "passed",
                "runtime": "Directus 12.1.1",
                "database": "fresh isolated Kernel PostgreSQL volume",
                "database_identity": "kokonut_directus_runtime",
                "candidate_or_legacy_database_used": False,
                "permission_seed_applied_and_replayed": True,
                "legacy_dashboard_wildcard_repaired": True,
                "replay_snapshot_unchanged": True,
                "permission": next(
                    row for row in first_permission_rows
                    if row.get("policy") == "Auditor Policy"
                    and row.get("collection") == "dashboard_dataset"
                    and row.get("action") == "read"
                ),
                "limitations": [
                    "Fresh repository-managed policy fixture only; custom/operator-edited policies are excluded.",
                    "No populated dashboard records or external consumers were used.",
                ],
            }
            DASHBOARD_EVIDENCE.write_text(
                json.dumps(dashboard_evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            metric_value_evidence = {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "result": "passed",
                "runtime": "Directus 12.1.1",
                "database": "fresh isolated Kernel PostgreSQL volume",
                "database_identity": "kokonut_directus_runtime",
                "candidate_or_legacy_database_used": False,
                "permission_seed_applied_and_replayed": True,
                "legacy_wildcard_repaired": True,
                "replay_snapshot_unchanged": True,
                "permission": next(
                    row for row in first_permission_rows
                    if row.get("policy") == "Auditor Policy"
                    and row.get("collection") == "metric_value"
                    and row.get("action") == "read"
                ),
                "limitations": [
                    "Fresh repository-managed policy fixture only; custom/operator-edited policies are excluded.",
                    "No metric rows, populated tenant grants, or live API read were used.",
                    "The source hook enforces exact location grants and denies null-location results; this profile verifies stored permission state only.",
                ],
            }
            METRIC_VALUE_EVIDENCE.write_text(
                json.dumps(metric_value_evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    if evidence["status"] == "passed":
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    print(json.dumps(evidence, indent=2, sort_keys=True), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
