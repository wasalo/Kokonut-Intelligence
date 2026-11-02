"""Tenant-scoped, auditable human review for Delphi recommendation drafts."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class DelphiReviewInvalid(ValueError):
    """A Delphi review request has invalid identifiers, bounds, or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiReviewInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, maximum: int, minimum: int) -> int:
    if isinstance(value, bool):
        raise DelphiReviewInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiReviewInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise DelphiReviewInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    return parsed


def list_location_delphi_recommendation_reviews(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded draft content only to an exact location reviewer."""
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
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_delphi_recommendation_reviews(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = cursor.fetchall()

        reviews = []
        for row in rows[:page_size]:
            recommendation_id, study_id, title, study_status, summary, text, created_at, ready, blockers = row
            reviews.append(
                {
                    "recommendation_id": str(recommendation_id),
                    "study_id": str(study_id),
                    "study_title": title,
                    "study_status": study_status,
                    "summary": summary,
                    "recommendation_text": text,
                    "created_at": created_at,
                    "review_ready": ready,
                    "blocked_reasons": blockers or [],
                }
            )
        return {
            "location_id": location_id,
            "offset": page_offset,
            "recommendations": reviews,
            "has_more": len(rows) > page_size and page_offset + page_size <= 10_000,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def decide_location_delphi_recommendation(
    operator_id: str,
    location_id: str,
    recommendation_id: str,
    *,
    decision: str,
    request_id: str,
    reason_code: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one idempotent human decision using the signed tenant context."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    recommendation_id = _normalize_uuid(recommendation_id, "recommendation")
    request_id = _normalize_uuid(request_id, "request")
    if decision not in {"approve", "reject"}:
        raise DelphiReviewInvalid("Decision must be approve or reject")
    if reason_code not in {
        "approved_after_review",
        "insufficient_evidence",
        "privacy_concern",
        "minority_report_open",
        "other",
    }:
        raise DelphiReviewInvalid("Reason code is not supported")
    if (decision == "approve") != (reason_code == "approved_after_review"):
        raise DelphiReviewInvalid("Decision and reason code do not match")

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
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.decide_location_delphi_recommendation(
                           %s::uuid, %s::uuid, %s::text, %s::uuid, %s::text
                       )""",
                (location_id, recommendation_id, decision, request_id, reason_code),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi review function returned no decision")
        connection.commit()
        review_id, recommendation_id, study_id, final_decision, status, decided_at = row
        return {
            "review_id": str(review_id),
            "recommendation_id": str(recommendation_id),
            "study_id": str(study_id),
            "decision": final_decision,
            "status": status,
            "decided_at": decided_at,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
