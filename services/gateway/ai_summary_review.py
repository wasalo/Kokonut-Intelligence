"""Tenant-scoped human review for agent-created AI summary drafts."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class AiSummaryReviewInvalid(ValueError):
    """An AI-summary review request contains invalid identifiers or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AiSummaryReviewInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, maximum: int, minimum: int) -> int:
    if isinstance(value, bool):
        raise AiSummaryReviewInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AiSummaryReviewInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise AiSummaryReviewInvalid(f"{field} must be an integer between {minimum} and {maximum}")
    return parsed


def list_location_ai_summary_reviews(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return a bounded review page for the exact signed location grant."""
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
            resource="ai_summary",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_ai_summary_reviews_with_creator(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = cursor.fetchall()

        reviews = []
        for row in rows[:page_size]:
            (
                summary_id,
                summary_type,
                content,
                content_truncated,
                source_tables,
                model_version,
                created_at,
                review_ready,
                blocked_reasons,
                source_references,
                creator_task_key,
                creator_run_id,
                creator_kind,
                creator_operator_id,
                creator_request_id,
            ) = row
            reviews.append(
                {
                    "summary_id": str(summary_id),
                    "summary_type": summary_type,
                    "content": content,
                    "content_truncated": content_truncated,
                    "source_tables": source_tables or [],
                    "source_references": source_references or {},
                    "model_version": model_version,
                    "created_at": created_at,
                    "review_ready": review_ready,
                    "blocked_reasons": blocked_reasons or [],
                    "creator_task_key": creator_task_key,
                    "creator_run_id": str(creator_run_id) if creator_run_id else None,
                    "creator_kind": creator_kind,
                    "creator_operator_id": str(creator_operator_id) if creator_operator_id else None,
                    "creator_request_id": str(creator_request_id) if creator_request_id else None,
                }
            )
        return {
            "location_id": location_id,
            "offset": page_offset,
            "summaries": reviews,
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


def decide_location_ai_summary_review(
    operator_id: str,
    location_id: str,
    summary_id: str,
    *,
    decision: str,
    request_id: str,
    reason_code: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one idempotent human decision; approval verifies but never publishes."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    summary_id = _normalize_uuid(summary_id, "summary")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"approve", "reject"}:
        raise AiSummaryReviewInvalid("Decision must be approve or reject")
    if not isinstance(reason_code, str):
        raise AiSummaryReviewInvalid("Reason code must be a string")
    if reason_code not in {
        "approved_after_review",
        "insufficient_evidence",
        "privacy_concern",
        "unsupported_claim",
        "other",
    }:
        raise AiSummaryReviewInvalid("Reason code is not supported")
    if (decision == "approve") != (reason_code == "approved_after_review"):
        raise AiSummaryReviewInvalid("Decision and reason code do not match")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="ai_summary",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.decide_location_ai_summary_review(
                           %s::uuid, %s::uuid, %s::text, %s::uuid, %s::text
                       )""",
                (location_id, summary_id, decision, request_id, reason_code),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("AI summary review function returned no decision")
        connection.commit()
        return {
            "review_id": str(row[0]),
            "summary_id": str(row[1]),
            "decision": row[2],
            "resulting_status": row[3],
            "created_at": row[4],
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
