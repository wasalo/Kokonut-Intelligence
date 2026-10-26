"""Human-authorized lifecycle transitions for governance circles and roles."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_ACTIONS = frozenset({"submit", "approve", "reject", "activate", "suspend", "retire"})
_ENTITY_ACTIONS = {
    "circle": _ACTIONS - {"approve"},
    "role": _ACTIONS,
}


class GovernanceDefinitionActionInvalid(ValueError):
    """A governance definition transition request is malformed."""


class GovernanceDefinitionActionConflict(RuntimeError):
    """The governance definition cannot make the requested transition."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_id(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceDefinitionActionInvalid(f"Invalid {field} identifier") from exc


def _row(cursor) -> dict:
    row = cursor.fetchone()
    if row is None:
        raise GovernanceDefinitionActionConflict("Governance transition did not return a result")
    description = getattr(cursor, "description", None)
    if description:
        return {column.name: value for column, value in zip(description, row)}
    return dict(row)


def transition_governance_definition(
    operator_id: str,
    location_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Apply one bounded definition transition in the signed location transaction."""
    if entity_type not in _ENTITY_ACTIONS or action not in _ENTITY_ACTIONS[entity_type]:
        raise GovernanceDefinitionActionInvalid("entity type or lifecycle action is not supported")
    if not isinstance(payload, dict) or set(payload) != {"request_id", "reason"}:
        raise GovernanceDefinitionActionInvalid(
            "Governance lifecycle content must contain only request_id and reason"
        )
    operator_id = _normalize_id(operator_id, "operator")
    location_id = _normalize_id(location_id, "location")
    entity_id = _normalize_id(entity_id, "governance definition")
    request_id = _normalize_id(payload["request_id"], "request")
    reason = payload["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise GovernanceDefinitionActionInvalid("reason must contain 1 to 2000 characters")

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
            action=action,
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_governance_definition(
                           %s::uuid, %s, %s::uuid, %s::uuid, %s, %s
                       )""",
                (location_id, entity_type, entity_id, request_id, action, reason.strip()),
            )
            result = _row(cursor)
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()
