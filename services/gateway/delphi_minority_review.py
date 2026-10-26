"""Tenant-scoped, private human review for Delphi minority reports."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class DelphiMinorityReviewInvalid(ValueError):
    """A Delphi minority-report review request has invalid fields or bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiMinorityReviewInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, maximum: int, minimum: int) -> int:
    if isinstance(value, bool):
        raise DelphiMinorityReviewInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiMinorityReviewInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise DelphiMinorityReviewInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return parsed


def list_location_delphi_minority_reports(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List active-consent submitted content for exact-location reviewers."""
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
                """SELECT * FROM kokonut_security.list_location_delphi_minority_reports(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = cursor.fetchall()

        reports = []
        for row in rows[:page_size]:
            (
                report_id,
                study_id,
                study_title,
                item_id,
                item_label,
                report_title,
                position_summary,
                rationale,
                implications,
                submitted_at,
                created_at,
            ) = row
            reports.append(
                {
                    "report_id": str(report_id),
                    "study_id": str(study_id),
                    "study_title": study_title,
                    "item_id": str(item_id) if item_id else None,
                    "item_label": item_label,
                    "title": report_title,
                    "position_summary": position_summary,
                    "rationale": rationale,
                    "implications": implications,
                    "submitted_at": submitted_at,
                    "created_at": created_at,
                }
            )
        return {
            "location_id": location_id,
            "offset": page_offset,
            "reports": reports,
            "has_more": len(rows) > page_size,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def decide_location_delphi_minority_report(
    operator_id: str,
    location_id: str,
    report_id: str,
    *,
    decision: str,
    request_id: str,
    reason_code: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an idempotent, private verified/rejected decision."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    report_id = _normalize_uuid(report_id, "report")
    request_id = _normalize_uuid(request_id, "request")
    if decision not in {"verified", "rejected"}:
        raise DelphiMinorityReviewInvalid("Decision must be verified or rejected")
    if reason_code not in {
        "evidence_considered",
        "out_of_scope",
        "privacy_concern",
        "insufficient_evidence",
        "other",
    }:
        raise DelphiMinorityReviewInvalid("Reason code is not supported")
    if (decision == "verified") != (reason_code == "evidence_considered"):
        raise DelphiMinorityReviewInvalid("Decision and reason code do not match")

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
                """SELECT * FROM kokonut_security.decide_location_delphi_minority_report(
                           %s::uuid, %s::uuid, %s::text, %s::uuid, %s::text
                       )""",
                (location_id, report_id, decision, request_id, reason_code),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi minority-report review function returned no decision")
        connection.commit()
        review_id, report_id, study_id, final_decision, status, decided_at = row
        return {
            "review_id": str(review_id),
            "report_id": str(report_id),
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
