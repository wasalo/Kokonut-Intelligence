"""Tenant-scoped, proposal-only governance role nominations."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_ASSIGNMENT_TYPES = frozenset({"primary", "delegate", "representative", "interim"})


class GovernanceAssignmentInvalid(ValueError):
    """The role nomination request is malformed."""


class GovernanceAssignmentConflict(RuntimeError):
    """The nomination cannot be applied to the current role state."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, location_id: str, role_id: str, payload: dict) -> tuple[str, ...]:
    try:
        return tuple(
            str(UUID(value))
            for value in (operator_id, location_id, role_id, payload["request_id"], payload["party_id"])
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise GovernanceAssignmentInvalid("Invalid operator, location, role, request, or party identifier") from exc


def propose_governance_role_assignment(
    operator_id: str,
    location_id: str,
    role_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay a proposed assignment without activating it."""
    if not isinstance(payload, dict) or set(payload) != {
        "request_id", "party_id", "assignment_type", "mandate"
    }:
        raise GovernanceAssignmentInvalid(
            "Role nomination must contain request_id, party_id, assignment_type, and mandate"
        )
    operator_id, location_id, role_id, request_id, party_id = _normalize_ids(
        operator_id, location_id, role_id, payload
    )
    assignment_type = payload["assignment_type"]
    if not isinstance(assignment_type, str) or assignment_type not in _ASSIGNMENT_TYPES:
        raise GovernanceAssignmentInvalid("assignment_type is not supported")
    mandate = payload["mandate"]
    if mandate is not None and (
        not isinstance(mandate, str) or len(mandate) > 2000
    ):
        raise GovernanceAssignmentInvalid("mandate must contain at most 2000 characters")
    mandate = mandate.strip() or None if isinstance(mandate, str) else None
    if assignment_type == "delegate" and mandate is None:
        raise GovernanceAssignmentInvalid("delegated role nominations require a mandate")

    conn = (connection_factory or _connection_factory())()
    committed = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_roles",
            action="create",
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_governance_role_assignment(
                           %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s
                       )""",
                (location_id, request_id, role_id, party_id, assignment_type, mandate),
            )
            row = cursor.fetchone()
            if row is None:
                raise GovernanceAssignmentConflict("Role nomination did not return a result")
            columns = (column.name for column in (cursor.description or ()))
            result = dict(zip(columns, row))
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()
