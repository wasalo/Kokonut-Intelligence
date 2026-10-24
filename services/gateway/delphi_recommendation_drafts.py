"""Location-scoped creation of facilitator recommendation drafts."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class DelphiDraftInvalid(ValueError):
    """A Delphi draft request has invalid identifiers, bounds, or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiDraftInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str) -> int:
    if isinstance(value, bool):
        raise DelphiDraftInvalid(f"{field} must be an integer between 0 and 10000")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiDraftInvalid(f"{field} must be an integer between 0 and 10000") from exc
    if str(parsed) != str(value).strip() or not 0 <= parsed <= 10000:
        raise DelphiDraftInvalid(f"{field} must be an integer between 0 and 10000")
    return parsed


def _open_scoped_connection(operator_id: str, location_id: str, connection_factory):
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
            action="draft",
        )
        return connection
    except Exception:
        try:
            connection.rollback()
        finally:
            connection.close()
        raise


def list_location_delphi_draftable_studies(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded open/closed studies visible to a location draft grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit")
    if not 1 <= page_size <= 50:
        raise DelphiDraftInvalid("Limit must be an integer between 1 and 50")
    page_offset = _page_value(offset, "Offset")

    connection = _open_scoped_connection(operator_id, location_id, connection_factory)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_delphi_draftable_studies(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = cursor.fetchall()
        return {
            "location_id": location_id,
            "offset": page_offset,
            "studies": [
                {
                    "study_id": str(row[0]),
                    "title": row[1],
                    "status": row[2],
                    "updated_at": row[3],
                }
                for row in rows[:page_size]
            ],
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


def create_location_delphi_recommendation_draft(
    operator_id: str,
    location_id: str,
    study_id: str,
    *,
    request_id: str,
    recommendation_text: str,
    summary: str | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay one exact draft under signed location context."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    study_id = _normalize_uuid(study_id, "study")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(recommendation_text, str):
        raise DelphiDraftInvalid("Recommendation text must be a string")
    recommendation_text = recommendation_text.strip()
    if not recommendation_text or len(recommendation_text) > 20000:
        raise DelphiDraftInvalid("Recommendation text must contain 1 to 20000 characters")
    if summary is not None:
        if not isinstance(summary, str):
            raise DelphiDraftInvalid("Summary must be a string")
        summary = summary.strip()
        if len(summary) > 4000:
            raise DelphiDraftInvalid("Summary must contain at most 4000 characters")
        summary = summary or None

    connection = _open_scoped_connection(operator_id, location_id, connection_factory)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_delphi_recommendation_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text
                       )""",
                (location_id, study_id, request_id, summary, recommendation_text),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi draft function returned no recommendation")
        connection.commit()
        recommendation_id, study_id, status, created_at = row
        return {
            "recommendation_id": str(recommendation_id),
            "study_id": str(study_id),
            "status": status,
            "created_at": created_at,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
