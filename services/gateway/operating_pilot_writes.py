"""Authenticated, exact-location draft actions for operating-pilot data."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Any, Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_WORK_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$")
_COMPETENCY_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,119}$")
_PRIORITIES = {"low", "medium", "high", "critical"}


class OperatingPilotWriteInvalid(ValueError):
    """A demand draft does not satisfy the bounded write contract."""


def _normalize_uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise OperatingPilotWriteInvalid(f"Invalid {field} identifier") from exc


def _normalize_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise OperatingPilotWriteInvalid(f"{field} must be an ISO date")
    try:
        normalized = date.fromisoformat(value)
    except ValueError as exc:
        raise OperatingPilotWriteInvalid(f"{field} must be an ISO date") from exc
    if normalized.isoformat() != value:
        raise OperatingPilotWriteInvalid(f"{field} must be an ISO date")
    return normalized


def _normalize_demand_payload(payload: Any) -> tuple[str, date, date, Decimal, str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Demand draft body must be an object")
    work_type = payload.get("work_type")
    if not isinstance(work_type, str) or not _WORK_TYPE.fullmatch(work_type.strip()):
        raise OperatingPilotWriteInvalid("Work type must be 1 to 50 safe characters")
    work_type = work_type.strip()
    start = _normalize_date(payload.get("period_start"), "period_start")
    end = _normalize_date(payload.get("period_end"), "period_end")
    if end < start or (end - start).days > 366:
        raise OperatingPilotWriteInvalid("Demand period must be ordered and no longer than 367 days")
    hours = payload.get("required_hours")
    if isinstance(hours, bool) or not isinstance(hours, (int, float, str, Decimal)):
        raise OperatingPilotWriteInvalid("Required hours must be a positive decimal")
    try:
        required_hours = Decimal(str(hours))
    except (InvalidOperation, ValueError) as exc:
        raise OperatingPilotWriteInvalid("Required hours must be a positive decimal") from exc
    if (
        not required_hours.is_finite()
        or required_hours <= 0
        or required_hours > Decimal("100000")
        or required_hours.as_tuple().exponent < -2
    ):
        raise OperatingPilotWriteInvalid(
            "Required hours must be positive, at most 100000, and use at most two decimals"
        )
    priority = payload.get("priority", "medium")
    if not isinstance(priority, str) or priority not in _PRIORITIES:
        raise OperatingPilotWriteInvalid("Priority must be low, medium, high, or critical")
    description = payload.get("description")
    if description is not None:
        if not isinstance(description, str) or len(description) > 2000 or "\x00" in description:
            raise OperatingPilotWriteInvalid("Description must be text of at most 2000 characters")
        description = description.strip() or None
    unexpected = set(payload) - {"work_type", "period_start", "period_end", "required_hours", "priority", "description"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Demand draft contains unsupported fields")
    return work_type, start, end, required_hours, priority, description


def _normalize_capacity_payload(payload: Any) -> tuple[date, date, Decimal, Decimal, Decimal, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Capacity draft body must be an object")
    start = _normalize_date(payload.get("period_start"), "period_start")
    end = _normalize_date(payload.get("period_end"), "period_end")
    if end < start or (end - start).days > 366:
        raise OperatingPilotWriteInvalid("Capacity period must be ordered and no longer than 367 days")
    hours = {}
    for field in ("available_hours", "committed_hours", "protected_hours"):
        value = payload.get(field, 0 if field != "available_hours" else None)
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise OperatingPilotWriteInvalid(f"{field} must be a non-negative decimal")
        try:
            normalized = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise OperatingPilotWriteInvalid(f"{field} must be a non-negative decimal") from exc
        if (
            not normalized.is_finite()
            or normalized < 0
            or normalized > Decimal("100000")
            or normalized.as_tuple().exponent < -2
        ):
            raise OperatingPilotWriteInvalid(
                f"{field} must be non-negative, at most 100000, and use at most two decimals"
            )
        hours[field] = normalized
    if hours["committed_hours"] + hours["protected_hours"] > hours["available_hours"]:
        raise OperatingPilotWriteInvalid("Committed and protected hours cannot exceed available hours")
    notes = payload.get("notes")
    if notes is not None:
        if not isinstance(notes, str) or len(notes) > 2000 or "\x00" in notes:
            raise OperatingPilotWriteInvalid("Private notes must be text of at most 2000 characters")
        notes = notes.strip() or None
    unexpected = set(payload) - {
        "period_start", "period_end", "available_hours", "committed_hours", "protected_hours", "notes"
    }
    if unexpected:
        raise OperatingPilotWriteInvalid("Capacity draft contains unsupported fields")
    return (
        start,
        end,
        hours["available_hours"],
        hours["committed_hours"],
        hours["protected_hours"],
        notes,
    )


def _normalize_resource_request_payload(payload: Any) -> tuple[str, str, str, date]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Resource draft body must be an object")
    resource_type = payload.get("resource_type")
    if not isinstance(resource_type, str) or not _WORK_TYPE.fullmatch(resource_type.strip()):
        raise OperatingPilotWriteInvalid("Resource type must be 1 to 50 safe characters")
    description = payload.get("description")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 2000
        or "\x00" in description
    ):
        raise OperatingPilotWriteInvalid("Description must be text of 1 to 2000 characters")
    urgency = payload.get("urgency", "medium")
    if not isinstance(urgency, str) or urgency not in _PRIORITIES:
        raise OperatingPilotWriteInvalid("Urgency must be low, medium, high, or critical")
    requested_by = _normalize_date(payload.get("requested_by"), "requested_by")
    unexpected = set(payload) - {"resource_type", "description", "urgency", "requested_by"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Resource draft contains unsupported fields")
    return resource_type.strip(), description.strip(), urgency, requested_by


def _normalize_competency_draft_payload(
    payload: Any,
) -> tuple[str, Decimal, Decimal, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Competency draft body must be an object")
    competency_key = payload.get("competency_key")
    if not isinstance(competency_key, str) or not _COMPETENCY_KEY.fullmatch(
        competency_key.strip()
    ):
        raise OperatingPilotWriteInvalid(
            "Competency key must be 1 to 120 letters, numbers, dots, underscores, or hyphens"
        )
    competency_key = competency_key.strip().lower()

    levels: dict[str, Decimal] = {}
    for field in ("current_level", "target_level"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise OperatingPilotWriteInvalid(f"{field} must be a decimal from 0 to 5")
        try:
            normalized = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise OperatingPilotWriteInvalid(f"{field} must be a decimal from 0 to 5") from exc
        if (
            not normalized.is_finite()
            or normalized < 0
            or normalized > 5
            or normalized.as_tuple().exponent < -2
        ):
            raise OperatingPilotWriteInvalid(
                f"{field} must be from 0 to 5 and use at most two decimals"
            )
        levels[field] = normalized
    if levels["target_level"] < levels["current_level"]:
        raise OperatingPilotWriteInvalid("Target level cannot be below the self-assessed level")

    evidence_note = payload.get("evidence_note")
    if evidence_note is not None:
        if (
            not isinstance(evidence_note, str)
            or len(evidence_note) > 2000
            or "\x00" in evidence_note
        ):
            raise OperatingPilotWriteInvalid(
                "Private evidence note must be text of at most 2000 characters"
            )
        evidence_note = evidence_note.strip() or None
    unexpected = set(payload) - {
        "competency_key", "current_level", "target_level", "evidence_note"
    }
    if unexpected:
        raise OperatingPilotWriteInvalid("Competency draft contains unsupported fields")
    return competency_key, levels["current_level"], levels["target_level"], evidence_note


def _normalize_capacity_review_payload(payload: Any) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Capacity review body must be an object")
    decision = payload.get("decision")
    if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
        raise OperatingPilotWriteInvalid("Decision must be approved or rejected")
    reason = payload.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > 2000 or "\x00" in reason:
            raise OperatingPilotWriteInvalid("Review reason must be text of at most 2000 characters")
        reason = reason.strip() or None
    if decision == "rejected" and reason is None:
        raise OperatingPilotWriteInvalid("A reason is required when rejecting a capacity submission")
    unexpected = set(payload) - {"decision", "reason"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Capacity review contains unsupported fields")
    return decision, reason


def _normalize_resource_review_payload(payload: Any) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Resource review body must be an object")
    decision = payload.get("decision")
    if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
        raise OperatingPilotWriteInvalid("Decision must be approved or rejected")
    reason = payload.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > 2000 or "\x00" in reason:
            raise OperatingPilotWriteInvalid("Review reason must be text of at most 2000 characters")
        reason = reason.strip() or None
    if decision == "rejected" and reason is None:
        raise OperatingPilotWriteInvalid("A reason is required when rejecting a resource request")
    unexpected = set(payload) - {"decision", "reason"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Resource review contains unsupported fields")
    return decision, reason


def _normalize_competency_review_payload(payload: Any) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Competency review body must be an object")
    decision = payload.get("decision")
    if not isinstance(decision, str) or decision not in {"verified", "rejected"}:
        raise OperatingPilotWriteInvalid("Decision must be verified or rejected")
    reason = payload.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > 2000 or "\x00" in reason:
            raise OperatingPilotWriteInvalid("Review reason must be text of at most 2000 characters")
        reason = reason.strip() or None
    if decision == "rejected" and reason is None:
        raise OperatingPilotWriteInvalid("A reason is required when rejecting a competency assessment")
    if decision == "verified" and reason is not None:
        raise OperatingPilotWriteInvalid("A review reason is only accepted when rejecting an assessment")
    unexpected = set(payload) - {"decision", "reason"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Competency review contains unsupported fields")
    return decision, reason


def _normalize_demand_review_payload(payload: Any) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Demand review body must be an object")
    decision = payload.get("decision")
    if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
        raise OperatingPilotWriteInvalid("Decision must be approved or rejected")
    reason = payload.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > 2000 or "\x00" in reason:
            raise OperatingPilotWriteInvalid("Review reason must be text of at most 2000 characters")
        reason = reason.strip() or None
    if decision == "rejected" and reason is None:
        raise OperatingPilotWriteInvalid("A reason is required when rejecting a demand submission")
    unexpected = set(payload) - {"decision", "reason"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Demand review contains unsupported fields")
    return decision, reason


def _normalize_work_claim_payload(payload: Any) -> Decimal | None:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Work-claim body must be an object")
    proposed_hours = payload.get("proposed_effort_hours")
    if proposed_hours is not None:
        if isinstance(proposed_hours, bool) or not isinstance(
            proposed_hours, (int, float, str, Decimal)
        ):
            raise OperatingPilotWriteInvalid("Proposed effort must be a non-negative decimal")
        try:
            proposed_hours = Decimal(str(proposed_hours))
        except (InvalidOperation, ValueError) as exc:
            raise OperatingPilotWriteInvalid("Proposed effort must be a non-negative decimal") from exc
        if (
            not proposed_hours.is_finite()
            or proposed_hours < 0
            or proposed_hours > Decimal("100000")
            or proposed_hours.as_tuple().exponent < -2
        ):
            raise OperatingPilotWriteInvalid(
                "Proposed effort must be non-negative, at most 100000, and use at most two decimals"
            )
    unexpected = set(payload) - {"proposed_effort_hours"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Work claim contains unsupported fields")
    return proposed_hours


def _normalize_work_claim_review_payload(payload: Any) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        raise OperatingPilotWriteInvalid("Work-claim review body must be an object")
    decision = payload.get("decision")
    if not isinstance(decision, str) or decision not in {"accepted", "rejected"}:
        raise OperatingPilotWriteInvalid("Decision must be accepted or rejected")
    reason = payload.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > 2000 or "\x00" in reason:
            raise OperatingPilotWriteInvalid("Review reason must be text of at most 2000 characters")
        reason = reason.strip() or None
    if decision == "rejected" and reason is None:
        raise OperatingPilotWriteInvalid("A reason is required when rejecting a work claim")
    unexpected = set(payload) - {"decision", "reason"}
    if unexpected:
        raise OperatingPilotWriteInvalid("Work-claim review contains unsupported fields")
    return decision, reason


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def create_location_operating_pilot_demand_draft(
    operator_id: str,
    location_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay a private draft; this action cannot submit or approve it."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    work_type, start, end, hours, priority, description = _normalize_demand_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.create_location_operating_pilot_demand_draft(
                           %s::uuid, %s::uuid, %s::text, %s::date, %s::date,
                           %s::numeric, %s::text, %s::text)""",
                (location_id, request_id, work_type, start, end, hours, priority, description),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot demand draft returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_operating_pilot_resource_draft(
    operator_id: str,
    location_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay a private resource-request draft without submitting it."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    resource_type, description, urgency, requested_by = _normalize_resource_request_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.create_location_operating_pilot_resource_draft(
                           %s::uuid, %s::uuid, %s::text, %s::text, %s::text, %s::date)""",
                (location_id, request_id, resource_type, description, urgency, requested_by),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot resource draft returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_operating_pilot_competency_draft(
    operator_id: str,
    location_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a private, self-reported competency draft without asserting verification."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    competency_key, current_level, target_level, evidence_note = (
        _normalize_competency_draft_payload(payload)
    )
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.create_location_operating_pilot_competency_draft(
                           %s::uuid, %s::uuid, %s::text, %s::numeric,
                           %s::numeric, %s::text)""",
                (
                    location_id,
                    request_id,
                    competency_key,
                    current_level,
                    target_level,
                    evidence_note,
                ),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot competency draft returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def revise_location_operating_pilot_competency_draft(
    operator_id: str,
    location_id: str,
    draft_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Supersede and replace the caller's own competency draft or rejected assessment."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    draft_id = _normalize_uuid(draft_id, "draft")
    request_id = _normalize_uuid(request_id, "request")
    competency_key, current_level, target_level, evidence_note = (
        _normalize_competency_draft_payload(payload)
    )
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="edit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.revise_location_operating_pilot_competency_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::text,
                           %s::numeric, %s::numeric, %s::text)""",
                (
                    location_id,
                    draft_id,
                    request_id,
                    competency_key,
                    current_level,
                    target_level,
                    evidence_note,
                ),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot competency revision returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_operating_pilot_competency_draft(
    operator_id: str,
    location_id: str,
    draft_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit only the caller's own competency draft for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    draft_id = _normalize_uuid(draft_id, "draft")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="submit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.submit_location_operating_pilot_competency_draft(
                           %s::uuid, %s::uuid, %s::uuid)""",
                (location_id, draft_id, request_id),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot competency submission returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def revise_location_operating_pilot_resource_draft(
    operator_id: str,
    location_id: str,
    draft_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Supersede and replace the caller's own unsubmitted resource draft."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    draft_id = _normalize_uuid(draft_id, "draft")
    request_id = _normalize_uuid(request_id, "request")
    resource_type, description, urgency, requested_by = _normalize_resource_request_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="edit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.revise_location_operating_pilot_resource_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text,
                           %s::text, %s::date)""",
                (location_id, draft_id, request_id, resource_type, description, urgency, requested_by),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot resource revision returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_operating_pilot_resource_draft(
    operator_id: str,
    location_id: str,
    draft_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit only the caller's own private resource draft for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    draft_id = _normalize_uuid(draft_id, "draft")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="submit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.submit_location_operating_pilot_resource_draft(
                           %s::uuid, %s::uuid, %s::uuid)""",
                (location_id, draft_id, request_id),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot resource submission returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def revise_location_operating_pilot_demand_draft(
    operator_id: str,
    location_id: str,
    signal_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Supersede and replace the caller's own unsubmitted demand draft."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    signal_id = _normalize_uuid(signal_id, "signal")
    request_id = _normalize_uuid(request_id, "request")
    work_type, start, end, hours, priority, description = _normalize_demand_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="edit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.revise_location_operating_pilot_demand_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::date,
                           %s::date, %s::numeric, %s::text, %s::text)""",
                (
                    location_id,
                    signal_id,
                    request_id,
                    work_type,
                    start,
                    end,
                    hours,
                    priority,
                    description,
                ),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot demand revision returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_operating_pilot_demand(
    operator_id: str,
    location_id: str,
    signal_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one exact-location independent approve/reject demand decision."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    signal_id = _normalize_uuid(signal_id, "signal")
    request_id = _normalize_uuid(request_id, "request")
    decision, reason = _normalize_demand_review_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.review_location_operating_pilot_demand(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text)""",
                (location_id, signal_id, request_id, decision, reason),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot demand review returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def claim_location_operating_pilot_work(
    operator_id: str,
    location_id: str,
    work_item_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an idempotent, self-attributed claim proposal for open work."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    work_item_id = _normalize_uuid(work_item_id, "work item")
    request_id = _normalize_uuid(request_id, "request")
    proposed_hours = _normalize_work_claim_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="claim_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.claim_location_operating_pilot_work(
                           %s::uuid, %s::uuid, %s::uuid, %s::numeric)""",
                (location_id, work_item_id, request_id, proposed_hours),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot work claim returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_operating_pilot_work_claim(
    operator_id: str,
    location_id: str,
    claim_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an independent accept/reject decision for a location claim proposal."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    claim_id = _normalize_uuid(claim_id, "claim")
    request_id = _normalize_uuid(request_id, "request")
    decision, reason = _normalize_work_claim_review_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.review_location_operating_pilot_work_claim(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text)""",
                (location_id, claim_id, request_id, decision, reason),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot work-claim review returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def allocate_location_operating_pilot_work_claim(
    operator_id: str,
    location_id: str,
    claim_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Allocate one independently accepted claim under a separate location grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    claim_id = _normalize_uuid(claim_id, "claim")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="allocate",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.allocate_location_operating_pilot_work_claim("
                "%s::uuid, %s::uuid, %s::uuid)",
                (location_id, claim_id, request_id),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot work-claim allocation returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_operating_pilot_capacity_draft(
    operator_id: str,
    location_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay the operator's own private, unsubmitted capacity draft."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    start, end, available, committed, protected, notes = _normalize_capacity_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.create_location_operating_pilot_capacity_draft(
                           %s::uuid, %s::uuid, %s::date, %s::date,
                           %s::numeric, %s::numeric, %s::numeric, %s::text)""",
                (location_id, request_id, start, end, available, committed, protected, notes),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot capacity draft returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def revise_location_operating_pilot_capacity_draft(
    operator_id: str,
    location_id: str,
    profile_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Supersede and replace the caller's own draft or rejected capacity record."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    profile_id = _normalize_uuid(profile_id, "profile")
    request_id = _normalize_uuid(request_id, "request")
    start, end, available, committed, protected, notes = _normalize_capacity_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="edit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.revise_location_operating_pilot_capacity_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::date, %s::date,
                           %s::numeric, %s::numeric, %s::numeric, %s::text)""",
                (
                    location_id,
                    profile_id,
                    request_id,
                    start,
                    end,
                    available,
                    committed,
                    protected,
                    notes,
                ),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot capacity revision returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_operating_pilot_capacity_draft(
    operator_id: str,
    location_id: str,
    profile_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit only the caller's own private capacity draft for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    profile_id = _normalize_uuid(profile_id, "profile")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="submit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.submit_location_operating_pilot_capacity_draft(
                           %s::uuid, %s::uuid, %s::uuid)""",
                (location_id, profile_id, request_id),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot capacity submission returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_operating_pilot_demand_draft(
    operator_id: str,
    location_id: str,
    signal_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit only the caller's own private operating demand draft for review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    signal_id = _normalize_uuid(signal_id, "signal")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="submit_own",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.submit_location_operating_pilot_demand_draft(
                           %s::uuid, %s::uuid, %s::uuid)""",
                (location_id, signal_id, request_id),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot demand submission returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_operating_pilot_competency_assessment(
    operator_id: str,
    location_id: str,
    draft_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Verify or reject one submitted competency assessment as an independent reviewer."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    draft_id = _normalize_uuid(draft_id, "draft")
    request_id = _normalize_uuid(request_id, "request")
    decision, reason = _normalize_competency_review_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.review_location_operating_pilot_competency(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text)""",
                (location_id, draft_id, request_id, decision, reason),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot competency review returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_operating_pilot_capacity(
    operator_id: str,
    location_id: str,
    profile_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one exact-location independent approve/reject decision."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    profile_id = _normalize_uuid(profile_id, "profile")
    request_id = _normalize_uuid(request_id, "request")
    decision, reason = _normalize_capacity_review_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.review_location_operating_pilot_capacity(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text)""",
                (location_id, profile_id, request_id, decision, reason),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating-pilot capacity review returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_operating_pilot_resource_request(
    operator_id: str,
    location_id: str,
    resource_request_id: str,
    request_id: str,
    payload: Any,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one exact-location independent decision without fulfilling the request."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    resource_request_id = _normalize_uuid(resource_request_id, "resource_request")
    request_id = _normalize_uuid(request_id, "request")
    decision, reason = _normalize_resource_review_payload(payload)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.review_location_operating_pilot_resource_request(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text)""",
                (location_id, resource_request_id, request_id, decision, reason),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating resource review returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fulfill_location_operating_pilot_resource_request(
    operator_id: str,
    location_id: str,
    resource_request_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an exact-location human confirmation for an approved request."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    resource_request_id = _normalize_uuid(resource_request_id, "resource_request")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="operating_pilot",
            action="fulfill",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.fulfill_location_operating_pilot_resource_request(
                           %s::uuid, %s::uuid, %s::uuid)""",
                (location_id, resource_request_id, request_id),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Operating resource fulfillment returned no result")
            result = row[0]
            if isinstance(result, str):
                result = json.loads(result)
        connection.commit()
        return {"location_id": location_id, **result}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
