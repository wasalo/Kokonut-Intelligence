"""Read-only location-scoped Delphi consultation summaries."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class DelphiConsultationInvalid(ValueError):
    """A Delphi consultation query has invalid identifiers or bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiConsultationInvalid(f"Invalid {field} identifier") from exc


def list_location_delphi_consultations(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded studies and consent-aware aggregates for one location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, bool):
        raise DelphiConsultationInvalid("Limit must be an integer between 1 and 50")
    try:
        page_size = int(limit)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiConsultationInvalid("Limit must be an integer between 1 and 50") from exc
    if str(page_size) != str(limit).strip() or not 1 <= page_size <= 50:
        raise DelphiConsultationInvalid("Limit must be an integer between 1 and 50")
    if isinstance(offset, bool):
        raise DelphiConsultationInvalid("Offset must be an integer between 0 and 10000")
    try:
        page_offset = int(offset)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiConsultationInvalid("Offset must be an integer between 0 and 10000") from exc
    if str(page_offset) != str(offset).strip() or not 0 <= page_offset <= 10000:
        raise DelphiConsultationInvalid("Offset must be an integer between 0 and 10000")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        # Setting context locks the current session and grant state. The bounded
        # projection itself is STABLE and this transaction performs no writes.
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="delphi",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_delphi_consultations(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = cursor.fetchall()

        studies = []
        for row in rows[:page_size]:
            study_id, title, description, variation, status, opened_at, closed_at, created_at, items = row
            studies.append(
                {
                    "study_id": str(study_id),
                    "title": title,
                    "description": description,
                    "variation": variation,
                    "status": status,
                    "opened_at": opened_at,
                    "closed_at": closed_at,
                    "created_at": created_at,
                    "items": items if items is not None else [],
                }
            )
        return {
            "location_id": location_id,
            "offset": page_offset,
            "studies": studies,
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
