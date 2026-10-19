"""Audited, location-scoped tactical item and session content mutations."""

from __future__ import annotations

import json
from datetime import datetime
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_SESSION_TYPES = {
    "weekly_review",
    "stakeholder_health",
    "relationship_review",
    "risk_triage",
    "governance_followup",
}
_ITEM_FIELDS = {
    "requested_next_action",
    "tension_id",
    "work_item_id",
    "decision_id",
    "owner_role_id",
    "owner_party_id",
    "priority",
    "due_at",
}
_SESSION_FIELDS = {
    "session_type",
    "title",
    "scheduled_at",
    "facilitator_role_id",
    "recorder_role_id",
    "agenda_scope",
}


class GovernanceTacticalMutationInvalid(ValueError):
    """A tactical content request is malformed."""


class GovernanceTacticalMutationConflict(RuntimeError):
    """A tactical record changed or cannot be edited in its current state."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: object, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceTacticalMutationInvalid(f"Invalid {field} identifier") from exc


def _normalize_timestamp(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GovernanceTacticalMutationInvalid(f"{field} must be an ISO timestamp or null")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GovernanceTacticalMutationInvalid(f"{field} must be a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GovernanceTacticalMutationInvalid(f"{field} must include a timezone")
    return parsed.isoformat()


def _mapping(cursor, row) -> dict:
    description = getattr(cursor, "description", None)
    if description:
        return {column.name: value for column, value in zip(description, row)}
    return dict(row)


def _content(operation: str, target_id: str | None, payload: object) -> tuple[str, str, str, dict]:
    if operation not in {"create_item", "update_item", "update_session"}:
        raise GovernanceTacticalMutationInvalid("operation is not supported")
    if not isinstance(payload, dict):
        raise GovernanceTacticalMutationInvalid("Tactical content must be an object")
    if not {"request_id", "reason"}.issubset(payload):
        raise GovernanceTacticalMutationInvalid("request_id and reason are required")
    fields = set(payload) - {"request_id", "reason"}
    allowed = _ITEM_FIELDS | {"session_id"} if operation == "create_item" else (
        _ITEM_FIELDS if operation == "update_item" else _SESSION_FIELDS
    )
    if fields - allowed:
        raise GovernanceTacticalMutationInvalid("Tactical content contains unsupported fields")
    normalized_target = _normalize_uuid(target_id, "target") if target_id is not None else None
    if operation == "create_item" and normalized_target is not None:
        raise GovernanceTacticalMutationInvalid("create_item does not accept a target identifier")
    if operation != "create_item" and normalized_target is None:
        raise GovernanceTacticalMutationInvalid("target identifier is required")
    if operation == "create_item" and not {"session_id", "requested_next_action"}.issubset(fields):
        raise GovernanceTacticalMutationInvalid("session_id and requested_next_action are required")
    if operation != "create_item" and not fields:
        raise GovernanceTacticalMutationInvalid("At least one content field is required")

    request_id = _normalize_uuid(payload["request_id"], "request")
    reason = payload["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise GovernanceTacticalMutationInvalid("reason must contain 1 to 2000 characters")

    content = {key: payload[key] for key in fields}
    uuid_fields = {
        "session_id", "tension_id", "work_item_id", "decision_id", "owner_role_id",
        "owner_party_id", "facilitator_role_id", "recorder_role_id",
    }
    for field in uuid_fields & fields:
        value = content[field]
        if value is not None:
            content[field] = _normalize_uuid(value, field.removesuffix("_id"))

    if "requested_next_action" in fields:
        value = content["requested_next_action"]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 4000:
            raise GovernanceTacticalMutationInvalid(
                "requested_next_action must contain 1 to 4000 characters"
            )
        content["requested_next_action"] = value.strip()
    if "priority" in fields:
        value = content["priority"]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise GovernanceTacticalMutationInvalid("priority must be an integer between 1 and 5")
    if "due_at" in fields:
        content["due_at"] = _normalize_timestamp(content["due_at"], "due_at")
    if "scheduled_at" in fields:
        content["scheduled_at"] = _normalize_timestamp(content["scheduled_at"], "scheduled_at")
    if "session_type" in fields:
        if not isinstance(content["session_type"], str) or content["session_type"] not in _SESSION_TYPES:
            raise GovernanceTacticalMutationInvalid("session_type is not supported")
    if "title" in fields:
        value = content["title"]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 255:
            raise GovernanceTacticalMutationInvalid("title must contain 1 to 255 characters")
        content["title"] = value.strip()
    if "agenda_scope" in fields and content["agenda_scope"] is not None:
        value = content["agenda_scope"]
        if not isinstance(value, str) or len(value) > 10000:
            raise GovernanceTacticalMutationInvalid("agenda_scope must be text up to 10000 characters or null")
        content["agenda_scope"] = value.strip() or None
    return request_id, normalized_target, reason.strip(), content


def mutate_governance_tactical_content(
    operator_id: str,
    location_id: str,
    operation: str,
    target_id: str | None,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an item or edit open item/planned session content in one transaction."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id, target_id, reason, content = _content(operation, target_id, payload)
    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_tactical",
            action="create" if operation == "create_item" else "update",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.mutate_governance_tactical_content(
                           %s::uuid, %s, %s::uuid, %s::uuid, %s::jsonb, %s
                       )""",
                (
                    location_id,
                    operation,
                    target_id,
                    request_id,
                    json.dumps(content, separators=(",", ":")),
                    reason,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise GovernanceTacticalMutationConflict(
                    "Tactical content mutation returned no result"
                )
            result = _mapping(cursor, row)
        connection.commit()
        committed = True
        return result
    finally:
        if not committed:
            connection.rollback()
        connection.close()
