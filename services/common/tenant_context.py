"""Transaction-local PostgreSQL context for verified tenant scopes.

This module is a building block for row-level security, not an RLS rollout.
Call it inside the same open transaction as the scoped query. Operator access
refuses legacy NULL-tenant grants; mobile-device and Gateway API-key access
require current database-verified credentials and ownership. Setters clear
prior local context first.
"""

from __future__ import annotations

import hashlib
import json
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any
from uuid import UUID

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_OPERATOR_SESSION_TOKEN_HASH: ContextVar[str | None] = ContextVar(
    "kokonut_operator_session_token_hash", default=None
)
_CONTEXT_SETTINGS = (
    "kokonut.tenant_id",
    "kokonut.location_id",
    "kokonut.actor_id",
    "kokonut.actor_type",
    "kokonut.context_payload",
    "kokonut.context_signature",
)


class TenantContextDenied(PermissionError):
    """Raised when an operator lacks a verified tenant-qualified grant."""


def bind_operator_session_token_hash(token_hash: str) -> Token[str | None]:
    """Bind the authenticated opaque OIDC session hash to this request context."""
    if not isinstance(token_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", token_hash):
        raise ValueError("operator-session-token-hash must be a SHA-256 hex digest")
    return _OPERATOR_SESSION_TOKEN_HASH.set(token_hash)


def reset_operator_session_token_hash(token: Token[str | None]) -> None:
    """Restore the previous request-local operator session proof."""
    _OPERATOR_SESSION_TOKEN_HASH.reset(token)


def current_operator_session_token_hash() -> str | None:
    """Return only the hash bound by authenticated OIDC request middleware."""
    return _OPERATOR_SESSION_TOKEN_HASH.get()


@dataclass(frozen=True)
class OperatorTenantContext:
    """Database-derived context to use for one operator transaction."""

    tenant_id: str
    location_id: str
    actor_id: str
    actor_type: str = "operator"


@dataclass(frozen=True)
class MobileDeviceTenantContext:
    """Database-derived context for a currently authorized field device."""

    tenant_id: str
    location_id: str
    actor_id: str
    actor_type: str = "mobile_device"


@dataclass(frozen=True)
class GatewayTenantContext:
    """Database-verified API-key context for one Gateway transaction."""

    tenant_id: str
    location_id: str
    actor_id: str
    actor_type: str = "gateway_api_key"


@dataclass(frozen=True)
class WorkerTenantContext:
    """Database-derived scope for one worker transaction and operation."""

    tenant_id: str
    location_id: str
    actor_id: str
    resource: str
    action: str
    actor_type: str = "system_worker"


def _normalize_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{label} must be a UUID") from exc


def clear_tenant_context(connection: Any) -> None:
    """Clear signed context within the current transaction; never commits it."""
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT "
            + ", ".join("set_config(%s, '', TRUE)" for _ in _CONTEXT_SETTINGS),
            _CONTEXT_SETTINGS,
        )


def clear_operator_tenant_context(connection: Any) -> None:
    """Compatibility alias retained for existing operator request paths."""
    clear_tenant_context(connection)


def set_worker_tenant_context(
    connection: Any,
    *,
    credential: str,
    location_id: str,
    resource: str,
    action: str,
) -> WorkerTenantContext:
    """Set database-signed scope for one worker operation in this transaction.

    The raw high-entropy credential is hashed in memory and is never sent to
    PostgreSQL. The caller must provide it from a worker-only secret source;
    event payloads and scheduler arguments are not credential sources. The
    transaction-local role switch also prevents the shared runtime login from
    calling the worker context setter.
    """
    return _set_worker_context(
        connection,
        credential=credential,
        location_id=location_id,
        resource=resource,
        action=action,
        switch_to_execution_role=True,
    )


def set_agent_summary_source_tenant_context(
    connection: Any,
    *,
    credential: str,
    location_id: str,
) -> WorkerTenantContext:
    """Set a signed read scope on an isolated AI-summary source login.

    Unlike general workers, these source-only logins must not join
    ``kokonut_worker_execution``: that role can call unrelated worker
    functions. Migrations 543 and 544 grant each login only the bounded
    context setter and its NOLOGIN source-view reader role.
    """
    return set_agent_source_tenant_context(
        connection,
        credential=credential,
        location_id=location_id,
        resource="ai_summary",
        action="read",
    )


def set_agent_summary_draft_tenant_context(
    connection: Any,
    *,
    credential: str,
    location_id: str,
) -> WorkerTenantContext:
    """Set a signed exact-location draft scope for a registered agent task.

    Task source logins do not receive the broad ``kokonut_worker_execution``
    role. After the signed scope is installed, they may switch to the narrow
    function-only ``kokonut_agent_task_summary_writer`` role.
    """
    context = _set_worker_context(
        connection,
        credential=credential,
        location_id=location_id,
        resource="ai_summary",
        action="draft",
        switch_to_execution_role=False,
    )
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE kokonut_agent_task_summary_writer")
        cursor.execute(
            "SELECT kokonut_security.register_current_ai_summary_worker_task()"
        )
    return context


def set_agent_source_tenant_context(
    connection: Any,
    *,
    credential: str,
    location_id: str,
    resource: str,
    action: str,
) -> WorkerTenantContext:
    """Set signed scope for a source-only agent login without role escalation.

    Agent source identities may select only their NOLOGIN view-reader role;
    they do not join the broader ``kokonut_worker_execution`` role. The
    database view contract must match the requested resource/action pair.
    """
    return _set_worker_context(
        connection,
        credential=credential,
        location_id=location_id,
        resource=resource,
        action=action,
        switch_to_execution_role=False,
    )


def _set_worker_context(
    connection: Any,
    *,
    credential: str,
    location_id: str,
    resource: str,
    action: str,
    switch_to_execution_role: bool,
) -> WorkerTenantContext:
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    # Clear first so a caught validation or role-switch failure cannot leave a
    # prior request's signed scope available on a reused connection.
    clear_tenant_context(connection)
    if not isinstance(credential, str) or len(credential) > 4096:
        raise ValueError("worker credential must contain 32 to 4096 UTF-8 bytes")
    try:
        credential_bytes = credential.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("worker credential must be valid UTF-8 text") from exc
    if not 32 <= len(credential_bytes) <= 4096:
        raise ValueError("worker credential must contain 32 to 4096 UTF-8 bytes")
    requested_location_id = _normalize_uuid(location_id, "location-id")
    if not isinstance(resource, str) or not _IDENTIFIER_RE.fullmatch(resource):
        raise ValueError("resource must be a lowercase identifier")
    if not isinstance(action, str) or not _IDENTIFIER_RE.fullmatch(action):
        raise ValueError("action must be a lowercase identifier")

    credential_hash = hashlib.sha256(credential_bytes).hexdigest()
    with connection.cursor() as cursor:
        if switch_to_execution_role:
            cursor.execute("SET LOCAL ROLE kokonut_worker_execution")
        cursor.execute(
            """
            SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
              FROM kokonut_security.set_worker_tenant_context(%s, %s::uuid, %s, %s)
            """,
            (credential_hash, requested_location_id, resource, action),
        )
        row = cursor.fetchone()
        if row is None:
            raise TenantContextDenied(
                "worker credential lacks an active grant for this location and operation"
            )
        tenant_id, validated_location_id, actor_id, actor_type = map(str, row)
        if actor_type != "system_worker":
            raise TenantContextDenied("database returned an invalid worker context")

    return WorkerTenantContext(
        tenant_id=tenant_id,
        location_id=validated_location_id,
        actor_id=actor_id,
        resource=resource,
        action=action,
    )


def set_mobile_device_tenant_context(
    connection: Any,
    *,
    device_id: str,
    location_id: str,
    device_token_hash: str,
) -> MobileDeviceTenantContext:
    """Set signed, transaction-bound context for a verified mobile device.

    PostgreSQL validates the token hash and current owner, locks the relevant
    rows, and signs a backend/transaction-bound context proof. A custom GUC by
    itself is forgeable; RLS policies must read the signed
    ``kokonut_security.current_tenant_context()`` accessor instead.
    """
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    clear_operator_tenant_context(connection)
    if (
        not isinstance(device_id, str)
        or not device_id.strip()
        or len(device_id) > 200
    ):
        raise ValueError("device-id must be a non-empty identifier of at most 200 characters")
    requested_location_id = _normalize_uuid(location_id, "location-id")
    if not isinstance(device_token_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", device_token_hash):
        raise ValueError("device-token-hash must be a SHA-256 hex digest")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
              FROM kokonut_security.set_mobile_device_context(%s, %s, %s::uuid)
            """,
            (device_token_hash, device_id, requested_location_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise TenantContextDenied(
                "device is not enrolled under the current verified location owner"
            )
        tenant_id, validated_location_id, actor_id, actor_type = map(str, row)
        if actor_type != "mobile_device":
            raise TenantContextDenied("database returned an invalid mobile context")

    return MobileDeviceTenantContext(
        tenant_id=tenant_id,
        location_id=validated_location_id,
        actor_id=actor_id,
    )


def set_operator_tenant_context(
    connection: Any,
    *,
    operator_id: str,
    location_id: str,
    resource: str,
    action: str,
    required_scopes: tuple[tuple[str, str], ...] = (),
) -> OperatorTenantContext:
    """Validate and set an operator's tenant context in the current transaction.

    PostgreSQL verifies the opaque session-token hash bound by authenticated
    Gateway middleware, checks the active tenant-qualified grants/current
    owner or share, locks those rows, and signs context for this transaction.
    Browser-provided organization IDs are deliberately not accepted.
    `required_scopes` adds grants that must all resolve to the same tenant as
    the primary resource/action. The caller owns commit/rollback and must
    perform its protected work before ending this transaction.
    """
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    # Clear before validating even the caller's selectors. If an invalid
    # second scope is caught by application code, a prior scope must not stay
    # active in the same transaction.
    clear_operator_tenant_context(connection)

    if not isinstance(required_scopes, (tuple, list)):
        raise ValueError("required-scopes must be a sequence of resource/action pairs")
    scope_pairs = [(resource, action)]
    for scope in required_scopes:
        if not isinstance(scope, (tuple, list)) or len(scope) != 2:
            raise ValueError("each required scope must contain a resource and action")
        scope_pairs.append((scope[0], scope[1]))
    if any(
        not isinstance(scope_resource, str)
        or not _IDENTIFIER_RE.fullmatch(scope_resource)
        for scope_resource, _ in scope_pairs
    ):
        raise ValueError("resource must be a lowercase identifier")
    if any(
        not isinstance(scope_action, str) or not _IDENTIFIER_RE.fullmatch(scope_action)
        for _, scope_action in scope_pairs
    ):
        raise ValueError("action must be a lowercase identifier")
    if len(scope_pairs) > 17:
        raise ValueError("at most 16 additional tenant scopes may be required")
    if len(set(scope_pairs)) != len(scope_pairs):
        raise ValueError("required scopes must be unique")

    actor_id = _normalize_uuid(operator_id, "operator-id")
    requested_location_id = _normalize_uuid(location_id, "location-id")
    session_token_hash = current_operator_session_token_hash()
    if session_token_hash is None:
        raise TenantContextDenied("an authenticated operator session is required")

    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
                 FROM kokonut_security.set_operator_tenant_context(
                     %s, %s::uuid, %s::uuid, %s, %s, %s::jsonb
                 )""",
            (
                session_token_hash,
                actor_id,
                requested_location_id,
                resource,
                action,
                json.dumps(
                    [
                        {"resource": required_resource, "action": required_action}
                        for required_resource, required_action in required_scopes
                    ],
                    separators=(",", ":"),
                ),
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise TenantContextDenied(
                "operator session or tenant-qualified grants are no longer active"
            )
        tenant_id, validated_location_id, validated_actor_id, actor_type = map(str, row)
        if actor_type != "operator":
            raise TenantContextDenied("database returned an invalid operator context")

    return OperatorTenantContext(
        tenant_id=str(tenant_id),
        location_id=str(validated_location_id),
        actor_id=str(validated_actor_id),
    )


def set_gateway_tenant_context(
    connection: Any,
    *,
    credential_type: str,
    credential_hash: str,
    location_id: str,
    resource: str,
    action: str,
) -> GatewayTenantContext:
    """Set signed tenant context after DB verifies the Gateway credential's exact scope.

    The credential hash is supplied by Gateway authentication middleware and
    is never logged. PostgreSQL rechecks API-key or capability-token status,
    expiry, exact location scope, and current owner before signing context.
    """
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    clear_operator_tenant_context(connection)
    if credential_type not in {"api_key", "capability_token"}:
        raise ValueError("credential-type must be api_key or capability_token")
    if not isinstance(credential_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", credential_hash):
        raise ValueError("credential-hash must be a SHA-256 hex digest")
    if not isinstance(resource, str) or not _IDENTIFIER_RE.fullmatch(resource):
        raise ValueError("resource must be a lowercase identifier")
    if not isinstance(action, str) or not _IDENTIFIER_RE.fullmatch(action):
        raise ValueError("action must be a lowercase identifier")
    requested_location_id = _normalize_uuid(location_id, "location-id")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tenant_id::text, location_id::text, actor_id::text, actor_type
              FROM kokonut_security.set_gateway_tenant_context(
                  %s, %s, %s::uuid, %s, %s
              )
            """,
            (credential_type, credential_hash, requested_location_id, resource, action),
        )
        row = cursor.fetchone()
        if row is None:
            raise TenantContextDenied(
                "active credential scope and current verified location owner are required"
            )
        tenant_id, validated_location_id, actor_id, actor_type = map(str, row)
        if actor_type not in {"gateway_api_key", "gateway_capability"}:
            raise TenantContextDenied("database returned an invalid Gateway context")

    return GatewayTenantContext(
        tenant_id=tenant_id,
        location_id=validated_location_id,
        actor_id=actor_id,
        actor_type=actor_type,
    )
