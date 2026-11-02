"""Versioned participant consent notices with independent location review."""

from __future__ import annotations

import re
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$")
_COLLECTION_SCOPE_ORDER = ("questionnaire_responses", "minority_reports")
_COLLECTION_SCOPES = frozenset(_COLLECTION_SCOPE_ORDER)
_APPROVAL_REASON = "approved_after_independent_review"
_REJECTION_REASONS = frozenset(
    {"privacy_scope_incomplete", "purpose_unclear", "withdrawal_terms_incomplete", "other"}
)


class DelphiConsentNoticeInvalid(ValueError):
    """A consent notice request has invalid identifiers, bounds, or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiConsentNoticeInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, maximum: int, minimum: int) -> int:
    if isinstance(value, bool):
        raise DelphiConsentNoticeInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiConsentNoticeInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise DelphiConsentNoticeInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    return parsed


def _collection_scopes(value: list[str] | tuple[str, ...]) -> list[str]:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or len(value) > len(_COLLECTION_SCOPE_ORDER)
    ):
        raise DelphiConsentNoticeInvalid(
            "Select questionnaire responses and any additional covered activity"
        )
    if any(not isinstance(scope, str) or scope not in _COLLECTION_SCOPES for scope in value):
        raise DelphiConsentNoticeInvalid("A participant activity scope is not supported")
    if len(set(value)) != len(value) or "questionnaire_responses" not in value:
        raise DelphiConsentNoticeInvalid("Questionnaire responses must be explicitly included once")
    return [scope for scope in _COLLECTION_SCOPE_ORDER if scope in value]


def submit_location_delphi_consent_notice(
    operator_id: str,
    location_id: str,
    study_id: str,
    *,
    version: str,
    notice_text: str,
    collection_scopes: list[str] | tuple[str, ...],
    request_id: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit an immutable consent notice for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    study_id = _normalize_uuid(study_id, "study")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise DelphiConsentNoticeInvalid("Version must be a bounded version identifier")
    if not isinstance(notice_text, str) or not 1 <= len(notice_text.strip()) <= 12000:
        raise DelphiConsentNoticeInvalid("Notice text must contain 1 to 12,000 characters")
    collection_scopes = _collection_scopes(collection_scopes)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="delphi",
            action="consent_draft",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_delphi_consent_notice_scoped(
                           %s::uuid, %s::uuid, %s::text, %s::text, %s::text[], %s::uuid
                       )""",
                (location_id, study_id, version, notice_text, collection_scopes, request_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi consent notice function returned no notice")
        connection.commit()
        return {
            "notice_id": str(row[0]),
            "location_id": str(row[1]),
            "study_id": str(row[2]),
            "version": row[3],
            "status": row[4],
            "notice_digest": row[5],
            "created_at": row[6],
            "replayed": bool(row[7]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_delphi_consent_notices(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read bounded submitted notice content and a self-review blocker."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 50, 1)
    page_offset = _page_value(offset, "Offset", 10000, 0)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="delphi",
            action="consent_review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_delphi_consent_notices_scoped(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = cursor.fetchall()
        notices = []
        for row in rows[:page_size]:
            notice_id, study_id, title, version, text, digest, created_at, ready, blockers, scopes = row
            notices.append(
                {
                    "notice_id": str(notice_id),
                    "study_id": str(study_id),
                    "study_title": title,
                    "version": version,
                    "notice_text": text,
                    "notice_digest": digest,
                    "created_at": created_at,
                    "review_ready": bool(ready),
                    "blocked_reasons": list(blockers or []),
                    "collection_scopes": list(scopes or []),
                }
            )
        return {
            "location_id": location_id,
            "offset": page_offset,
            "notices": notices,
            "has_more": len(rows) > page_size and page_offset + page_size <= 10000,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def decide_location_delphi_consent_notice(
    operator_id: str,
    location_id: str,
    notice_id: str,
    *,
    decision: str,
    request_id: str,
    reason_code: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an independent, retry-safe approval or rejection."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    notice_id = _normalize_uuid(notice_id, "notice")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"approve", "reject"}:
        raise DelphiConsentNoticeInvalid("Decision must be approve or reject")
    allowed_reasons = {_APPROVAL_REASON} if decision == "approve" else _REJECTION_REASONS
    if not isinstance(reason_code, str) or reason_code not in allowed_reasons:
        raise DelphiConsentNoticeInvalid("Reason code is not supported for this decision")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="delphi",
            action="consent_review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.decide_location_delphi_consent_notice(
                           %s::uuid, %s::uuid, %s::text, %s::uuid, %s::text
                       )""",
                (location_id, notice_id, decision, request_id, reason_code),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi consent notice decision function returned no decision")
        connection.commit()
        return {
            "decision_id": str(row[0]),
            "notice_id": str(row[1]),
            "study_id": str(row[2]),
            "decision": row[3],
            "status": row[4],
            "decided_at": row[5],
            "replayed": bool(row[6]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
