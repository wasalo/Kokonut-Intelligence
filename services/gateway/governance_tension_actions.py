"""Tenant-scoped Gateway intake and submission for governance tensions."""

from __future__ import annotations

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
