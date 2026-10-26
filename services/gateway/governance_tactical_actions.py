"""Human-authorized location-scoped tactical item lifecycle actions."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_ACTIONS = frozenset({"start", "dispose", "cancel"})
_DISPOSITION_TYPES = frozenset(
    {
        "next_action",
        "delegate",
        "create_work_item",
        "create_proposal",
        "escalate",
        "defer",
        "no_action",
    }
)


class GovernanceTacticalActionInvalid(ValueError):
    """A tactical action request is malformed."""


class GovernanceTacticalActionConflict(RuntimeError):
    """A tactical item has already changed or the transition is unavailable."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_id(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceTacticalActionInvalid(f"Invalid {field} identifier") from exc


def _row(cursor) -> dict:
    row = cursor.fetchone()
    if row is None:
        raise GovernanceTacticalActionConflict("Tactical action did not return a result")
    description = getattr(cursor, "description", None)
    if description:
        return {column.name: value for column, value in zip(description, row)}
    return dict(row)


def transition_governance_tactical_item(
    operator_id: str,
    location_id: str,
    item_id: str,
    action: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Run one exact-grant transition and keep the decision in one transaction."""
    if action not in _ACTIONS:
        raise GovernanceTacticalActionInvalid("action is not supported")
    if not isinstance(payload, dict):
        raise GovernanceTacticalActionInvalid("Tactical action content must be an object")
    expected = {"request_id", "reason"}
    if action == "dispose":
        expected |= {"disposition_type", "disposition_summary"}
    if set(payload) != expected:
        raise GovernanceTacticalActionInvalid(
            "Tactical action content has missing or unsupported fields"
        )

    operator_id = _normalize_id(operator_id, "operator")
    location_id = _normalize_id(location_id, "location")
    item_id = _normalize_id(item_id, "item")
    request_id = _normalize_id(payload["request_id"], "request")
    reason = payload["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise GovernanceTacticalActionInvalid("reason must contain 1 to 2000 characters")

    disposition_type = None
    disposition_summary = None
    if action == "dispose":
        disposition_type = payload["disposition_type"]
        disposition_summary = payload["disposition_summary"]
        if not isinstance(disposition_type, str) or disposition_type not in _DISPOSITION_TYPES:
            raise GovernanceTacticalActionInvalid("disposition_type is not supported")
        if not isinstance(disposition_summary, str) or not 1 <= len(disposition_summary.strip()) <= 4000:
            raise GovernanceTacticalActionInvalid(
                "disposition_summary must contain 1 to 4000 characters"
            )

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
            resource="governance_tactical",
            action=action,
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_governance_tactical_item(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s
                       )""",
                (
                    location_id,
                    item_id,
                    request_id,
                    action,
                    reason.strip(),
                    disposition_type,
                    disposition_summary.strip() if disposition_summary else None,
                ),
            )
            result = _row(cursor)
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()
