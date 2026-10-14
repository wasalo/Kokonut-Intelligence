"""Transaction-local PostgreSQL context for verified operator tenant scopes.

This module is a building block for row-level security, not an RLS rollout.
Call it inside the same open transaction as the scoped query. It refuses legacy
NULL-tenant grants and clears any prior local context before validating the
requested scope.
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


def set_operator_tenant_context(
    connection: Any,
    *,
    operator_id: str,
    location_id: str,
    resource: str,
    action: str,
) -> OperatorTenantContext:
    """Validate and set an operator's tenant context in the current transaction.

    The tenant is read from the active tenant-qualified grant and the database's
    current owner/share verification. Browser-provided organization IDs are
    deliberately not accepted. The caller owns commit/rollback and must perform
    its protected work before ending this transaction.
    """
    if getattr(connection, "autocommit", True):
        raise ValueError("tenant context requires a non-autocommit transaction")

    # Clear before validating even the caller's selectors. If an invalid
    # second scope is caught by application code, a prior scope must not stay
    # active in the same transaction.
    clear_operator_tenant_context(connection)

    if not isinstance(resource, str) or not _IDENTIFIER_RE.fullmatch(resource):
        raise ValueError("resource must be a lowercase identifier")
    if not isinstance(action, str) or not _IDENTIFIER_RE.fullmatch(action):
        raise ValueError("action must be a lowercase identifier")

    actor_id = _normalize_uuid(operator_id, "operator-id")
    requested_location_id = _normalize_uuid(location_id, "location-id")

    with connection.cursor() as cursor:
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

        cursor.execute(
            "SELECT "
            + ", ".join("set_config(%s, %s, TRUE)" for _ in _CONTEXT_SETTINGS),
            (
                _CONTEXT_SETTINGS[0],
                str(tenant_id),
                _CONTEXT_SETTINGS[1],
                str(validated_location_id),
                _CONTEXT_SETTINGS[2],
                str(validated_actor_id),
                _CONTEXT_SETTINGS[3],
                "operator",
            ),
        )

    return OperatorTenantContext(
        tenant_id=str(tenant_id),
        location_id=str(validated_location_id),
        actor_id=str(validated_actor_id),
    )
