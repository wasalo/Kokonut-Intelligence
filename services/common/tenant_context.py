"""Transaction-local PostgreSQL context for verified tenant scopes.

This module is a building block for row-level security, not an RLS rollout.
Call it inside the same open transaction as the scoped query. Operator access
refuses legacy NULL-tenant grants; mobile-device access requires a device pinned
to the location's current verified owner. Both clear prior local context first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_CONTEXT_SETTINGS = (
    "kokonut.tenant_id",
    "kokonut.location_id",
    "kokonut.actor_id",
    "kokonut.actor_type",
)


class TenantContextDenied(PermissionError):
    """Raised when an operator lacks a verified tenant-qualified grant."""


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
) -> MobileDeviceTenantContext:
    """Set context only for a device enrolled under the current verified owner.

    The active location owner is locked until the caller ends its transaction.
    An owner transfer therefore serializes with protected device work; after
    transfer, a device pinned to the former owner fails closed and must be
    enrolled again. Legacy devices without a tenant binding are denied.
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

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT device.tenant_organization_id::text,
                   device.location_id::text,
                   device.id::text
              FROM mobile_device AS device
              JOIN location AS loc ON loc.id = device.location_id
              JOIN location_tenant_owner_verification AS owner
                ON owner.location_id = loc.id
               AND owner.organization_id = loc.organization_id
               AND owner.revoked_at IS NULL
              JOIN organization AS tenant
                ON tenant.id = owner.organization_id
               AND tenant.status = 'active'
             WHERE device.device_id = %s
               AND device.location_id = %s::uuid
               AND loc.status = 'active'
               AND device.status = 'active'
               AND device.device_token_hash IS NOT NULL
               AND device.tenant_organization_id IS NOT NULL
               AND device.tenant_organization_id = loc.organization_id
             FOR SHARE OF device, loc, owner, tenant
            """,
            (device_id, requested_location_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise TenantContextDenied(
                "device is not enrolled under the current verified location owner"
            )
        tenant_id, validated_location_id, actor_id = map(str, row)
        _set_transaction_tenant_context(
            connection,
            tenant_id=tenant_id,
            location_id=validated_location_id,
            actor_id=actor_id,
            actor_type="mobile_device",
        )

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

    The tenant is read from the active tenant-qualified grant and the database's
    current owner/share verification. Browser-provided organization IDs are
    deliberately not accepted. `required_scopes` adds grants that must all
    resolve to the same tenant as the primary resource/action. The caller owns
    commit/rollback and must perform its protected work before ending this
    transaction.
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
    if len(set(scope_pairs)) != len(scope_pairs):
        raise ValueError("required scopes must be unique")

    actor_id = _normalize_uuid(operator_id, "operator-id")
    requested_location_id = _normalize_uuid(location_id, "location-id")

    with connection.cursor() as cursor:
        if len(scope_pairs) == 1:
            cursor.execute(
                """SELECT grant_row.organization_id::text,
                          grant_row.location_id::text,
                          grant_row.operator_id::text
                     FROM operator_scope_grant AS grant_row
                    WHERE grant_row.operator_id = %s::uuid
                      AND grant_row.location_id = %s::uuid
                      AND grant_row.resource = %s
                      AND grant_row.action = %s
                      AND grant_row.organization_id IS NOT NULL
                      AND grant_row.revoked_at IS NULL
                      AND operator_scope_grant_allows(
                          grant_row.operator_id, grant_row.resource,
                          grant_row.action, grant_row.location_id
                      )
                    LIMIT 2""",
                (actor_id, requested_location_id, resource, action),
            )
            row = cursor.fetchone()
            if row is None:
                raise TenantContextDenied(
                    "active tenant-qualified operator grant was not found"
                )
            if cursor.fetchone() is not None:
                raise TenantContextDenied(
                    "multiple active tenant-qualified grants make the requested scope ambiguous"
                )
            tenant_id, validated_location_id, validated_actor_id = row
        else:
            requested_values = ", ".join("(%s, %s)" for _ in scope_pairs)
            requested_params = tuple(value for pair in scope_pairs for value in pair)
            cursor.execute(
                f"""WITH requested_scope(resource, action) AS (
                        VALUES {requested_values}
                    )
                    SELECT requested_scope.resource,
                           requested_scope.action,
                           grant_row.organization_id::text,
                           grant_row.location_id::text,
                           grant_row.operator_id::text
                      FROM requested_scope
                      JOIN operator_scope_grant AS grant_row
                        ON grant_row.resource = requested_scope.resource
                       AND grant_row.action = requested_scope.action
                     WHERE grant_row.operator_id = %s::uuid
                       AND grant_row.location_id = %s::uuid
                       AND grant_row.organization_id IS NOT NULL
                       AND grant_row.revoked_at IS NULL
                       AND operator_scope_grant_allows(
                           grant_row.operator_id, grant_row.resource,
                           grant_row.action, grant_row.location_id
                       )
                     ORDER BY requested_scope.resource, requested_scope.action
                     LIMIT %s""",
                (
                    *requested_params,
                    actor_id,
                    requested_location_id,
                    len(scope_pairs) + 1,
                ),
            )
            rows = cursor.fetchall()
            actual_pairs = {(row[0], row[1]) for row in rows}
            tenant_ids = {row[2] for row in rows}
            if (
                len(rows) != len(scope_pairs)
                or actual_pairs != set(scope_pairs)
                or len(tenant_ids) != 1
            ):
                raise TenantContextDenied(
                    "required tenant-qualified grants are missing, ambiguous, "
                    "or resolve to different tenant scopes"
                )
            tenant_id, validated_location_id, validated_actor_id = rows[0][2:]

        _set_transaction_tenant_context(
            connection,
            tenant_id=str(tenant_id),
            location_id=str(validated_location_id),
            actor_id=str(validated_actor_id),
            actor_type="operator",
        )

    return OperatorTenantContext(
        tenant_id=str(tenant_id),
        location_id=str(validated_location_id),
        actor_id=str(validated_actor_id),
    )
