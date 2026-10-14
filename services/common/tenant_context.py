"""Transaction-local PostgreSQL context for verified tenant scopes.

This module is a building block for row-level security, not an RLS rollout.
Call it inside the same open transaction as the scoped query. Operator access
refuses legacy NULL-tenant grants; mobile-device access requires a device pinned
to the location's current verified owner. Both clear prior local context first.
"""

from __future__ import annotations

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
    """Current-owner context for a route already authorized by the Gateway.

    This carries application-verified scope into the transaction. It does not
    turn a custom PostgreSQL setting into a database credential or replace the
    Gateway's route authorization.
    """

    tenant_id: str
    location_id: str
    actor_id: str
    actor_type: str = "gateway"


def _normalize_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{label} must be a UUID") from exc


def clear_operator_tenant_context(connection: Any) -> None:
    """Clear context within the current transaction; never commits it."""
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT "
            + ", ".join("set_config(%s, '', TRUE)" for _ in _CONTEXT_SETTINGS),
            _CONTEXT_SETTINGS,
        )


def _set_transaction_tenant_context(
    connection: Any,
    *,
    tenant_id: str,
    location_id: str,
    actor_id: str,
    actor_type: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT "
            + ", ".join("set_config(%s, %s, TRUE)" for _ in _CONTEXT_SETTINGS),
            (
                _CONTEXT_SETTINGS[0], tenant_id,
                _CONTEXT_SETTINGS[1], location_id,
                _CONTEXT_SETTINGS[2], actor_id,
                _CONTEXT_SETTINGS[3], actor_type,
            ),
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
    gateway_caller: str,
    location_id: str,
    resource: str,
    action: str,
) -> GatewayTenantContext:
    """Carry a Gateway-authorized route's current-owner scope into its write.

    Call only after Gateway middleware has authenticated the principal and
    authorized the route's resource/action/location. This function revalidates
    and locks the current verified location owner in the same transaction; it
    does not independently prove that the principal has the Gateway grant.
    """
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    clear_operator_tenant_context(connection)
    if (
        not isinstance(gateway_caller, str)
        or not gateway_caller.strip()
        or len(gateway_caller) > 200
        or any(ord(char) < 32 or ord(char) == 127 for char in gateway_caller)
    ):
        raise ValueError("gateway-caller must be a non-empty identifier of at most 200 characters")
    if not isinstance(resource, str) or not _IDENTIFIER_RE.fullmatch(resource):
        raise ValueError("resource must be a lowercase identifier")
    if not isinstance(action, str) or not _IDENTIFIER_RE.fullmatch(action):
        raise ValueError("action must be a lowercase identifier")
    requested_location_id = _normalize_uuid(location_id, "location-id")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT owner.organization_id::text, loc.id::text
              FROM location AS loc
              JOIN location_tenant_owner_verification AS owner
                ON owner.location_id = loc.id
               AND owner.organization_id = loc.organization_id
               AND owner.revoked_at IS NULL
              JOIN organization AS tenant
                ON tenant.id = owner.organization_id
               AND tenant.status = 'active'
             WHERE loc.id = %s::uuid
               AND loc.status = 'active'
             FOR SHARE OF loc, owner, tenant
            """,
            (requested_location_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise TenantContextDenied(
                "an active location with a current verified owner is required"
            )
        tenant_id, validated_location_id = map(str, row)
        _set_transaction_tenant_context(
            connection,
            tenant_id=tenant_id,
            location_id=validated_location_id,
            actor_id=gateway_caller.strip(),
            actor_type="gateway",
        )

    return GatewayTenantContext(
        tenant_id=tenant_id,
        location_id=validated_location_id,
        actor_id=gateway_caller.strip(),
    )
