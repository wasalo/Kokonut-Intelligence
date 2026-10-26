"""Audited tactical session creation for the Gateway."""

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
_CONTENT_FIELDS = {
    "circle_id",
    "session_type",
    "title",
    "scheduled_at",
    "facilitator_role_id",
    "recorder_role_id",
    "agenda_scope",
}


class GovernanceTacticalSessionInvalid(ValueError):
    """A tactical session creation request is malformed."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceTacticalSessionInvalid(f"Invalid {field} identifier") from exc


def _mapping(cursor, row) -> dict:
    description = getattr(cursor, "description", None)
    if description:
        return {column.name: value for column, value in zip(description, row)}
    return dict(row)


def _session_request(payload: object) -> tuple[str, str, dict]:
    if not isinstance(payload, dict):
        raise GovernanceTacticalSessionInvalid("Tactical session content must be an object")
    envelope = {"request_id", "reason"}
    if set(payload) - envelope - _CONTENT_FIELDS:
        raise GovernanceTacticalSessionInvalid("Tactical session content contains unsupported fields")
    if not envelope.issubset(payload):
        raise GovernanceTacticalSessionInvalid("request_id and reason are required")
    content = {key: value for key, value in payload.items() if key not in envelope}
    required = {"circle_id", "session_type", "title"}
    if not required.issubset(content):
        missing = sorted(required - set(content))[0]
        raise GovernanceTacticalSessionInvalid(f"{missing} is required")

    content["circle_id"] = _normalize_uuid(content["circle_id"], "circle")
    for key in ("facilitator_role_id", "recorder_role_id"):
        if key in content and content[key] is not None:
            content[key] = _normalize_uuid(content[key], key.removesuffix("_id"))
    session_type = content["session_type"]
    if not isinstance(session_type, str) or session_type not in _SESSION_TYPES:
        raise GovernanceTacticalSessionInvalid("session_type is not supported")
    title = content["title"]
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 255:
        raise GovernanceTacticalSessionInvalid("title must contain 1 to 255 characters")
    content["title"] = title.strip()

    if "scheduled_at" in content and content["scheduled_at"] is not None:
        scheduled_at = content["scheduled_at"]
        if not isinstance(scheduled_at, str):
            raise GovernanceTacticalSessionInvalid("scheduled_at must be an ISO timestamp or null")
        try:
            parsed_schedule = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GovernanceTacticalSessionInvalid("scheduled_at must be a valid ISO timestamp") from exc
        if parsed_schedule.tzinfo is None or parsed_schedule.utcoffset() is None:
            raise GovernanceTacticalSessionInvalid("scheduled_at must include a timezone")
        content["scheduled_at"] = parsed_schedule.isoformat()

    if "agenda_scope" in content and content["agenda_scope"] is not None:
        agenda_scope = content["agenda_scope"]
        if not isinstance(agenda_scope, str) or len(agenda_scope) > 10_000:
            raise GovernanceTacticalSessionInvalid("agenda_scope must be text up to 10000 characters or null")
    request_id = _normalize_uuid(payload["request_id"], "request")
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
        raise GovernanceTacticalSessionInvalid("reason must contain 1 to 2000 characters")
    return request_id, reason.strip(), content


def create_governance_tactical_session(
    operator_id: str,
    location_id: str,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a planned session in one signed, exact-scope transaction."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id, reason, content = _session_request(payload)
    conn = (connection_factory or _connection_factory())()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            conn,
            operator_id=operator_id,
            location_id=location_id,
            resource="governance_tactical",
            action="create",
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_governance_tactical_session(
                           %s::uuid, %s::uuid, %s::jsonb, %s
                       )""",
                (
                    location_id,
                    request_id,
                    json.dumps(content, separators=(",", ":")),
                    reason,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("tactical session creation returned no result")
            result = _mapping(cursor, row)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
