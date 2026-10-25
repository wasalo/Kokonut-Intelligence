"""Pseudonymous Delphi invite preview, consent, and withdrawal operations."""

from __future__ import annotations

import re
from functools import partial
from typing import Callable
from uuid import UUID

_TOKEN = re.compile(r"^[0-9a-f]{64}$")


class DelphiParticipantAcceptanceInvalid(ValueError):
    """A participant token, request identifier, or consent value is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _token(value: str, field: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        raise DelphiParticipantAcceptanceInvalid(f"Invalid {field}")
    return value


def _request_id(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiParticipantAcceptanceInvalid("Invalid request identifier") from exc


def _call(function_name: str, params: tuple, connection_factory: Callable | None) -> tuple:
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            placeholders = ", ".join(["%s"] * len(params))
            cursor.execute(
                f"SELECT * FROM kokonut_security.{function_name}({placeholders})", params
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"{function_name} returned no result")
        connection.commit()
        return row
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def preview_location_delphi_participant_invite(
    invite_token: str, *, connection_factory: Callable | None = None
) -> dict:
    """Return the approved notice bound to a still-pending study invite."""
    invite_token = _token(invite_token, "invite token")
    row = _call(
        "preview_location_delphi_participant_invite",
        (invite_token,),
        connection_factory,
    )
    return {
        "study_title": row[0],
        "notice_version": row[1],
        "notice_text": row[2],
        "notice_digest": row[3],
        "expires_at": row[4],
    }


def accept_location_delphi_participant_invite(
    invite_token: str,
    notice_digest: str,
    session_token: str,
    csrf_token: str,
    request_id: str,
    *,
    accepted: bool,
    connection_factory: Callable | None = None,
) -> dict:
    """Accept the exact displayed notice and create a revocable opaque session."""
    invite_token = _token(invite_token, "invite token")
    notice_digest = _token(notice_digest, "consent notice digest")
    session_token = _token(session_token, "participant session token")
    csrf_token = _token(csrf_token, "participant CSRF token")
    request_id = _request_id(request_id)
    if accepted is not True:
        raise DelphiParticipantAcceptanceInvalid("Explicit consent acceptance is required")
    if session_token == csrf_token:
        raise DelphiParticipantAcceptanceInvalid("Participant session and CSRF tokens must differ")
    row = _call(
        "accept_location_delphi_participant_invite",
        (invite_token, notice_digest, session_token, csrf_token, request_id, accepted),
        connection_factory,
    )
    return {
        "status": row[0],
        "notice_version": row[1],
        "notice_digest": row[2],
        "accepted_at": row[3],
        "session_expires_at": row[4],
        "replayed": bool(row[5]),
    }


def withdraw_location_delphi_participant(
    session_token: str,
    csrf_token: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Withdraw consent, revoke this session, and keep prior records private."""
    session_token = _token(session_token, "participant session token")
    csrf_token = _token(csrf_token, "participant CSRF token")
    request_id = _request_id(request_id)
    row = _call(
        "withdraw_location_delphi_participant",
        (session_token, csrf_token, request_id),
        connection_factory,
    )
    return {"status": row[0], "withdrawn_at": row[1], "replayed": bool(row[2])}
