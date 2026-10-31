"""Tenant-scoped Gateway intake, submission, and lifecycle actions."""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_TENSION_TYPES = frozenset(
    {
        "unmet_interest",
        "unclear_accountability",
        "authority_gap",
        "authority_conflict",
        "commitment_risk",
        "representation_gap",
        "consent_gap",
        "evidence_gap",
        "harm_risk",
        "policy_gap",
        "cross_circle_dependency",
        "role_overload",
    }
)
_TENSION_ACTIONS = frozenset(
    {"triage", "start", "link", "link_work_item", "resolve", "defer"}
)
_LINK_TYPES = frozenset(
    {
        "interest",
        "commitment",
        "work_item",
        "decision",
        "grievance",
        "evidence",
        "relationship",
        "proposal",
        "outcome",
    }
)


def _normalize_action_payload(action: str, payload: object) -> tuple[str, str, dict]:
    """Validate an action body before opening PostgreSQL.

    The future migration contract is
    `kokonut_security.mutate_governance_tension_action(UUID location_id,
    UUID tension_id, TEXT action, UUID request_id, JSONB content, TEXT reason)`.
    It returns exactly `(tension_id UUID, action TEXT, status TEXT,
    updated_at TIMESTAMPTZ, request_id UUID, link_id UUID NULL)`. The function
    must verify the signed operator context and exact action grant, bind the
    tension and every linked object to `location_id`, enforce the state graph,
    persist an idempotent request receipt, and append the lifecycle event
    atomically. The response never includes actor identities.
    """
    if action not in _TENSION_ACTIONS:
        raise GovernanceTensionInvalid("Governance tension action is not supported")
    if not isinstance(payload, dict):
        raise GovernanceTensionInvalid("Governance tension action must be an object")
    common = {"request_id", "reason"}
    extra = {
        "triage": {"owner_role_id", "owner_party_id", "review_due_at", "note"},
        "start": set(),
        "link": {"link_type", "entity_type", "entity_id", "summary"},
        "link_work_item": {"work_item_id"},
        "resolve": {"resolution_summary"},
        "defer": {"deferred_until", "note"},
    }[action]
    if not common.issubset(payload) or set(payload) - common - extra:
        raise GovernanceTensionInvalid(
            "Governance tension action has missing or unsupported fields"
        )
    try:
        request_id = str(UUID(payload["request_id"]))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceTensionInvalid("Invalid request identifier") from exc
    reason = payload["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000 or "\x00" in reason:
        raise GovernanceTensionInvalid("reason must contain 1 to 2000 characters")
    content = {key: value for key, value in payload.items() if key not in common}

    def normalize_uuid(field: str) -> None:
        if field not in content:
            raise GovernanceTensionInvalid(f"{field} is required")
        value = content[field]
        if value is None and field in {"owner_role_id", "owner_party_id"}:
            return
        try:
            content[field] = str(UUID(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise GovernanceTensionInvalid(f"Invalid {field.removesuffix('_id')} identifier") from exc

    if action == "triage":
        if not content.get("owner_role_id") and not content.get("owner_party_id"):
            raise GovernanceTensionInvalid("triage requires an owner role or party")
        for field in ("owner_role_id", "owner_party_id"):
            if field in content and content[field] is not None:
                normalize_uuid(field)
        if "review_due_at" in content and content["review_due_at"] is not None:
            content["review_due_at"] = _normalize_tension_timestamp(
                content["review_due_at"], "review_due_at"
            )
        if "note" in content:
            content["note"] = _bounded_optional_text(content["note"], "note", 2000)
    elif action == "link":
        link_type = content.get("link_type")
        if not isinstance(link_type, str) or link_type not in _LINK_TYPES:
            raise GovernanceTensionInvalid("link_type is not supported")
        entity_type = content.get("entity_type")
        if not isinstance(entity_type, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", entity_type):
            raise GovernanceTensionInvalid("entity_type is not supported")
        normalize_uuid("entity_id")
        if "summary" in content:
            content["summary"] = _bounded_optional_text(content["summary"], "summary", 4000)
    elif action == "link_work_item":
        normalize_uuid("work_item_id")
    elif action == "resolve":
        summary = content.get("resolution_summary")
        if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 4000 or "\x00" in summary:
            raise GovernanceTensionInvalid(
                "resolution_summary must contain 1 to 4000 characters"
            )
        content["resolution_summary"] = summary.strip()
    elif action == "defer":
        if "deferred_until" not in content:
            raise GovernanceTensionInvalid("deferred_until is required")
        content["deferred_until"] = _normalize_tension_timestamp(
            content["deferred_until"], "deferred_until"
        )
        if "note" in content:
            content["note"] = _bounded_optional_text(content["note"], "note", 2000)

    return request_id, reason.strip(), content


def _normalize_tension_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise GovernanceTensionInvalid(f"{field} must be an ISO timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GovernanceTensionInvalid(f"{field} must be a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GovernanceTensionInvalid(f"{field} must include a timezone")
    return parsed.isoformat()


def _bounded_optional_text(value: object, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise GovernanceTensionInvalid(f"{field} must be text up to {maximum} characters or null")
    return value.strip() or None


class GovernanceTensionConflict(RuntimeError):
    """The requested tension lifecycle transition cannot be applied."""


class GovernanceTensionInvalid(ValueError):
    """The request body or identifiers are malformed."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_ids(operator_id: str, location_id: str, *other_ids: str) -> tuple[str, ...]:
    try:
        return tuple(str(UUID(value)) for value in (operator_id, location_id, *other_ids))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceTensionInvalid("Invalid operator, location, request, or tension identifier") from exc


def _row(cursor, *, operation: str) -> dict:
    row = cursor.fetchone()
    if row is None:
        raise GovernanceTensionConflict(f"Governance tension {operation} did not return a result")
    if getattr(cursor, "description", None):
        return {column.name: value for column, value in zip(cursor.description, row)}
    return dict(row)


def report_governance_tension(
    operator_id: str,
    location_id: str,
    payload: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay the caller's own attributed location tension draft."""
    if not isinstance(payload, dict):
        raise GovernanceTensionInvalid("Governance tension content must be an object")
    allowed = {"request_id", "title", "description", "tension_type", "severity", "urgency"}
    if set(payload) != allowed:
        raise GovernanceTensionInvalid("Governance tension content has missing or unsupported fields")
    operator_id, location_id, request_id = _normalize_ids(
        operator_id, location_id, payload["request_id"]
    )
    title = payload["title"]
    description = payload["description"]
    tension_type = payload["tension_type"]
    severity = payload["severity"]
    urgency = payload["urgency"]
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 255:
        raise GovernanceTensionInvalid("title must contain 1 to 255 characters")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 10000:
        raise GovernanceTensionInvalid("description must contain 1 to 10000 characters")
    if not isinstance(tension_type, str) or tension_type not in _TENSION_TYPES:
        raise GovernanceTensionInvalid("tension_type is not supported")
    if any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5
           for value in (severity, urgency)):
        raise GovernanceTensionInvalid("severity and urgency must be integers between 1 and 5")

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
            resource="governance_tension",
            action="create",
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.report_governance_tension(
                           %s::uuid, %s::uuid, %s, %s, %s, %s::smallint, %s::smallint
                       )""",
                (
                    location_id,
                    request_id,
                    title.strip(),
                    description.strip(),
                    tension_type,
                    severity,
                    urgency,
                ),
            )
            result = _row(cursor, operation="report")
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()


def submit_governance_tension(
    operator_id: str,
    location_id: str,
    tension_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit only the authenticated operator's own location-scoped draft."""
    operator_id, location_id, tension_id = _normalize_ids(
        operator_id, location_id, tension_id
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
            resource="governance_tension",
            action="submit",
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_governance_tension(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, tension_id),
            )
            result = _row(cursor, operation="submit")
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()


def mutate_governance_tension_action(
    operator_id: str,
    location_id: str,
    tension_id: str,
    action: str,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Run an audited location-scoped tension lifecycle action.

    The database API is the exact six-argument migration contract documented
    by `_normalize_action_payload`; one call owns one transaction, and retries
    reuse the action's request UUID.
    """
    if action not in _TENSION_ACTIONS:
        raise GovernanceTensionInvalid("Governance tension action is not supported")
    request_id, reason, content = _normalize_action_payload(action, payload)
    operator_id, location_id, tension_id = _normalize_ids(
        operator_id, location_id, tension_id
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
            resource="governance_tension",
            action=action,
        )
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.mutate_governance_tension_action(
                           %s::uuid, %s::uuid, %s, %s::uuid, %s::jsonb, %s
                       )""",
                (
                    location_id,
                    tension_id,
                    action,
                    request_id,
                    json.dumps(content, separators=(",", ":")),
                    reason,
                ),
            )
            result = _row(cursor, operation=action)
        conn.commit()
        committed = True
        return result
    finally:
        if not committed:
            conn.rollback()
        conn.close()
