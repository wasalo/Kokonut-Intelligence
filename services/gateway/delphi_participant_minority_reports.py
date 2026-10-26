"""Pseudonymous participant submission of private Delphi minority reports."""

from __future__ import annotations

import re
from functools import partial
from typing import Callable
from uuid import UUID


class DelphiParticipantMinorityReportInvalid(ValueError):
    """A participant minority-report request has invalid fields."""


_TOKEN = re.compile(r"^[0-9a-f]{64}$")


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _token(value: str, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise DelphiParticipantMinorityReportInvalid(f"Invalid participant {field}")
    return value


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiParticipantMinorityReportInvalid(f"Invalid {field} identifier") from exc


def _text(value: str, field: str, maximum: int, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise DelphiParticipantMinorityReportInvalid(f"Invalid minority-report {field}")
    normalized = value.strip()
    if optional and not normalized:
        return None
    if not 1 <= len(normalized) <= maximum:
        raise DelphiParticipantMinorityReportInvalid(
            f"Minority-report {field} must contain 1 to {maximum} characters"
        )
    return normalized


def submit_location_delphi_participant_minority_report(
    session_token: str,
    csrf_token: str,
    *,
    item_id: str | None,
    title: str,
    position_summary: str,
    rationale: str,
    implications: str | None,
    request_id: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an immutable report only through its consent-bound SQL function."""
    session_token = _token(session_token, "session token")
    csrf_token = _token(csrf_token, "CSRF token")
    if session_token == csrf_token:
        raise DelphiParticipantMinorityReportInvalid(
            "Participant session and CSRF tokens must differ"
        )
    normalized_item_id = None if item_id is None else _uuid(item_id, "item")
    normalized_title = _text(title, "title", 255)
    normalized_position = _text(position_summary, "position summary", 4000)
    normalized_rationale = _text(rationale, "rationale", 8000)
    normalized_implications = _text(implications, "implications", 3000, optional=True)
    normalized_request_id = _uuid(request_id, "request")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_delphi_participant_minority_report(
                           %s::text, %s::text, %s::uuid, %s::text, %s::text,
                           %s::text, %s::text, %s::uuid
                       )""",
                (
                    session_token,
                    csrf_token,
                    normalized_item_id,
                    normalized_title,
                    normalized_position,
                    normalized_rationale,
                    normalized_implications,
                    normalized_request_id,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi participant minority-report function returned no result")
        connection.commit()
        status, report_id, submitted_at, replayed = row
        return {
            "status": status,
            "report_id": str(report_id),
            "submitted_at": submitted_at,
            "replayed": bool(replayed),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
