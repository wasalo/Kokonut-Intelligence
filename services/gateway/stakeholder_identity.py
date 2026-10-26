"""Consent-gated, location-scoped Kernel stakeholder identity review."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_MAX_PAGE_SIZE = 50
_MATCH_METHODS = {"manual", "exact_identifier", "verified_document", "community_review"}
_EVIDENCE_CODES = {
    "verified_identifier", "document_review", "participant_confirmation", "community_review"
}
_DECISION_CODES = {
    "match_confirmed", "insufficient_evidence", "conflicting_identity", "source_not_eligible"
}


class StakeholderIdentityInvalid(ValueError):
    """An identity proposal, decision, or review cursor is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StakeholderIdentityInvalid(f"Invalid {field} identifier") from exc


def _normalize_confidence(value: object) -> Decimal:
    if isinstance(value, bool):
        raise StakeholderIdentityInvalid("confidence must be between 0 and 1")
    try:
        confidence = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StakeholderIdentityInvalid("confidence must be between 0 and 1") from exc
    if not confidence.is_finite() or not Decimal("0") <= confidence <= Decimal("1"):
        raise StakeholderIdentityInvalid("confidence must be between 0 and 1")
    if confidence != confidence.quantize(Decimal("0.0001")):
        raise StakeholderIdentityInvalid("confidence supports at most four decimal places")
    return confidence


def _normalize_cursor_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StakeholderIdentityInvalid("Invalid review cursor timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StakeholderIdentityInvalid("Review cursor timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def _open_connection(factory: Callable, *, readonly: bool):
    connection = factory()
    try:
        with connection.cursor() as cursor:
            if readonly:
                cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
    except Exception:
        try:
            connection.rollback()
        finally:
            connection.close()
        raise
    return connection


def propose_location_party_identity(
    operator_id: str,
    location_id: str,
    source_profile_id: str,
    candidate_party_id: str,
    request_id: str,
    match_method: str,
    evidence_code: str,
    confidence: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record a structured proposal; raw feedback and free-text evidence are not accepted."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    source_profile_id = _normalize_uuid(source_profile_id, "source profile")
    candidate_party_id = _normalize_uuid(candidate_party_id, "candidate party")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(match_method, str) or match_method not in _MATCH_METHODS:
        raise StakeholderIdentityInvalid("match_method is not supported")
    if not isinstance(evidence_code, str) or evidence_code not in _EVIDENCE_CODES:
        raise StakeholderIdentityInvalid("evidence_code is not supported")
    normalized_confidence = _normalize_confidence(confidence)

    connection = _open_connection(connection_factory or _connection_factory(), readonly=False)
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="stakeholder_identity",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_party_identity(
                           %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                           %s, %s, %s::numeric
                       )""",
                (
                    location_id,
                    source_profile_id,
                    candidate_party_id,
                    request_id,
                    match_method,
                    evidence_code,
                    normalized_confidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("identity proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_location_party_identity_cases(
    operator_id: str,
    location_id: str,
    *,
    limit: str | int = 50,
    cursor_created_at: str | datetime | None = None,
    cursor_case_id: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Read a bounded location queue; SQL withholds source IDs and raw feedback."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, str):
        if not limit.isdecimal():
            raise StakeholderIdentityInvalid("limit must be an integer between 1 and 50")
        limit = int(limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise StakeholderIdentityInvalid("limit must be an integer between 1 and 50")
    before_created_at = _normalize_cursor_time(cursor_created_at)
    before_case_id = _normalize_uuid(cursor_case_id, "cursor case") if cursor_case_id else None
    if (before_created_at is None) != (before_case_id is None):
        raise StakeholderIdentityInvalid("cursor_created_at and cursor_case_id must be provided together")

    connection = _open_connection(connection_factory or _connection_factory(), readonly=True)
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="stakeholder_identity",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_party_identity_cases(
                           %s::uuid, %s::integer, %s::timestamptz, %s::uuid
                       )""",
                (location_id, limit + 1, before_created_at, before_case_id),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = {
                "created_at": last["created_at"].isoformat(),
                "case_id": str(last["case_id"]),
            }
        return {"location_id": location_id, "items": items, "next_cursor": next_cursor}
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def decide_location_party_identity(
    operator_id: str,
    location_id: str,
    case_id: str,
    request_id: str,
    decision: str,
    reason_code: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Apply one append-only independent decision to a pending case."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    case_id = _normalize_uuid(case_id, "case")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"approve", "reject"}:
        raise StakeholderIdentityInvalid("decision must be approve or reject")
    if not isinstance(reason_code, str) or reason_code not in _DECISION_CODES:
        raise StakeholderIdentityInvalid("reason_code is not supported")

    connection = _open_connection(connection_factory or _connection_factory(), readonly=False)
    try:
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="stakeholder_identity",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.decide_location_party_identity(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s
                       )""",
                (location_id, case_id, request_id, decision, reason_code),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("identity decision returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
