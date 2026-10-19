"""Audited create and draft-edit operations for governance circles and roles."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class GovernanceDefinitionMutationInvalid(ValueError):
    """A governance definition create or edit request is malformed."""


class GovernanceDefinitionMutationConflict(RuntimeError):
    """A governance definition cannot be created or edited in its current state."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceDefinitionMutationInvalid(f"Invalid {field} identifier") from exc


def _mapping(cursor, row) -> dict:
    description = getattr(cursor, "description", None)
    if description:
        return {column.name: value for column, value in zip(description, row)}
    return dict(row)


def _text_field(content: dict, field: str, *, required: bool, maximum: int | None = None) -> None:
    if field not in content:
        if required:
            raise GovernanceDefinitionMutationInvalid(f"{field} is required")
        return
    value = content[field]
    if not isinstance(value, str):
        raise GovernanceDefinitionMutationInvalid(f"{field} must be text")
    if required and not value.strip():
        raise GovernanceDefinitionMutationInvalid(f"{field} must not be empty")
    if maximum is not None and len(value) > maximum:
        raise GovernanceDefinitionMutationInvalid(f"{field} must contain at most {maximum} characters")
    content[field] = value.strip() if required or value else value


def _request(entity_type: str, action: str, payload: object) -> tuple[str, str, dict]:
    if entity_type not in {"circle", "role"} or action not in {"create", "update"}:
        raise GovernanceDefinitionMutationInvalid("entity type or mutation action is not supported")
    if not isinstance(payload, dict):
        raise GovernanceDefinitionMutationInvalid("Governance definition content must be an object")

    common_fields = {"request_id", "reason"}
    if entity_type == "circle":
        mutable_fields = {"circle_key", "name", "purpose", "description", "parent_circle_id"}
        required_fields = {"circle_key", "name", "purpose"} if action == "create" else set()
    elif action == "create":
        mutable_fields = {"circle_id", "role_key", "name", "purpose"}
        required_fields = set(mutable_fields)
    else:
        mutable_fields = {"role_key", "name", "purpose"}
        required_fields = set()

    if set(payload) - common_fields - mutable_fields:
        raise GovernanceDefinitionMutationInvalid("Governance definition content contains unsupported fields")
    if not common_fields.issubset(payload):
        raise GovernanceDefinitionMutationInvalid("request_id and reason are required")
    content = {key: value for key, value in payload.items() if key not in common_fields}
    if not content and action == "update":
        raise GovernanceDefinitionMutationInvalid("At least one definition field must be updated")
    if not required_fields.issubset(content):
        missing = sorted(required_fields - set(content))[0]
        raise GovernanceDefinitionMutationInvalid(f"{missing} is required")

    for field in ("circle_key", "role_key"):
        if field in content:
            _text_field(content, field, required=True, maximum=120)
    if "name" in content:
        _text_field(content, "name", required=True, maximum=255)
    if "purpose" in content:
        _text_field(content, "purpose", required=True, maximum=10_000)
    if "description" in content:
        _text_field(content, "description", required=False, maximum=10_000)
    for field in ("parent_circle_id", "circle_id"):
        if field in content:
            if field == "parent_circle_id" and content[field] is None:
                continue
            content[field] = _normalize_uuid(content[field], field)

    request_id = _normalize_uuid(payload["request_id"], "request")
    reason = payload["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise GovernanceDefinitionMutationInvalid("reason must contain 1 to 2000 characters")
    return request_id, reason.strip(), content


def mutate_governance_definition(
    operator_id: str,
    location_id: str,
    entity_type: str,
    action: str,
    entity_id: str | None,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a circle/role or edit a draft in one signed tenant transaction."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if action == "create" and entity_id is not None:
        raise GovernanceDefinitionMutationInvalid("create requests cannot include a definition identifier")
    if action == "update" and entity_id is None:
        raise GovernanceDefinitionMutationInvalid("update requests require a definition identifier")
    normalized_entity_id = _normalize_uuid(entity_id, "governance definition") if entity_id else None
    request_id, reason, content = _request(entity_type, action, payload)

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
                """SELECT * FROM kokonut_security.mutate_governance_definition(
                           %s::uuid, %s, %s::uuid, %s::uuid, %s, %s::jsonb, %s
                       )""",
                (
                    location_id,
                    entity_type,
                    normalized_entity_id,
                    request_id,
                    action,
                    json.dumps(content, separators=(",", ":")),
                    reason,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise GovernanceDefinitionMutationConflict("Governance definition mutation returned no result")
            result = _mapping(cursor, row)
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()
