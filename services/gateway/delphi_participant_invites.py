"""One-time participant invites bound to approved Delphi consent notices."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_REVOKE_REASONS = frozenset(
    {"sent_to_wrong_recipient", "token_exposed", "study_cancelled", "notice_replaced", "other"}
)


class DelphiParticipantInviteInvalid(ValueError):
    """An invite request has an invalid identifier, lifetime, or reason."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiParticipantInviteInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, maximum: int, minimum: int) -> int:
    if isinstance(value, bool):
        raise DelphiParticipantInviteInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiParticipantInviteInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise DelphiParticipantInviteInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return parsed


def list_location_delphi_participant_invites(
    operator_id: str,
    location_id: str,
    study_id: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded lifecycle metadata without exposing invite credentials."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    study_id = _uuid(study_id, "study")
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
            action="invite",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.list_location_delphi_participant_invites(
                           %s::uuid, %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, study_id, page_size, page_offset),
            )
            row = cursor.fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("Delphi invite inventory function returned no result")
        result = row[0]
        if isinstance(result, str):
            import json

            result = json.loads(result)
        if not isinstance(result, dict):
            raise RuntimeError("Delphi invite inventory returned an invalid payload")
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def issue_location_delphi_participant_invite(
    operator_id: str,
    location_id: str,
    study_id: str,
    *,
    lifetime_seconds: int,
    request_id: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Issue an invite; a retry returns metadata but never reveals its token again."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    study_id = _uuid(study_id, "study")
    request_id = _uuid(request_id, "request")
    if (
        isinstance(lifetime_seconds, bool)
        or not isinstance(lifetime_seconds, int)
        or not 3600 <= lifetime_seconds <= 2_592_000
    ):
        raise DelphiParticipantInviteInvalid(
            "Invite lifetime must be between one hour and thirty days"
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
            resource="delphi",
            action="invite",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.issue_location_delphi_participant_invite(
                           %s::uuid, %s::uuid, %s::integer, %s::uuid
                       )""",
                (location_id, study_id, lifetime_seconds, request_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi invite function returned no result")
        connection.commit()
        return {
            "invite_id": str(row[0]),
            "location_id": str(row[1]),
            "study_id": str(row[2]),
            "consent_notice_id": str(row[3]),
            "consent_notice_version": row[4],
            "consent_notice_digest": row[5],
            "invite_token": row[6],
            "expires_at": row[7],
            "status": row[8],
            "replayed": bool(row[9]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def revoke_location_delphi_participant_invite(
    operator_id: str,
    location_id: str,
    invite_id: str,
    *,
    request_id: str,
    reason_code: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Revoke a pending invite with an immutable, retry-safe reason receipt."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    invite_id = _uuid(invite_id, "invite")
    request_id = _uuid(request_id, "request")
    if not isinstance(reason_code, str) or reason_code not in _REVOKE_REASONS:
        raise DelphiParticipantInviteInvalid("Invite revoke reason is not supported")

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
            action="invite_revoke",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.revoke_location_delphi_participant_invite(
                           %s::uuid, %s::uuid, %s::uuid, %s::text
                       )""",
                (location_id, invite_id, request_id, reason_code),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi invite revoke function returned no result")
        connection.commit()
        return {
            "invite_id": str(row[0]),
            "study_id": str(row[1]),
            "status": row[2],
            "revoked_at": row[3],
            "replayed": bool(row[4]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
