"""Private workspace reads and consented Delphi contribution writes."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.gateway.delphi_participant_acceptance import _request_id, _token


class DelphiParticipantWorkspaceInvalid(ValueError):
    """A participant workspace request has invalid fields or bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _bounded_integer(value: int | str, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise DelphiParticipantWorkspaceInvalid(f"Invalid {field}")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DelphiParticipantWorkspaceInvalid(f"Invalid {field}") from exc
    if str(normalized) != str(value).strip() or not minimum <= normalized <= maximum:
        raise DelphiParticipantWorkspaceInvalid(f"Invalid {field}")
    return normalized


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


def get_location_delphi_participant_workspace(
    session_token: str,
    *,
    limit: int | str = 50,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded question metadata and only this participant's answers."""
    session_token = _token(session_token, "participant session token")
    page_size = _bounded_integer(limit, "limit", 1, 50)
    page_offset = _bounded_integer(offset, "offset", 0, 10000)
    (workspace,) = _call(
        "get_location_delphi_participant_workspace",
        (session_token, page_size, page_offset),
        connection_factory,
    )
    if isinstance(workspace, str):
        try:
            workspace = json.loads(workspace)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Delphi participant workspace returned invalid JSON") from exc
    if not isinstance(workspace, dict):
        raise RuntimeError("Delphi participant workspace returned an invalid shape")
    return workspace


def submit_location_delphi_participant_contribution(
    session_token: str,
    csrf_token: str,
    item_id: str,
    score: int | float | str | Decimal,
    reasoning: str | None,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Upsert one participant's answer through the bounded database function."""
    session_token = _token(session_token, "participant session token")
    csrf_token = _token(csrf_token, "participant CSRF token")
    if session_token == csrf_token:
        raise DelphiParticipantWorkspaceInvalid("Participant session and CSRF tokens must differ")
    try:
        normalized_item_id = str(UUID(str(item_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiParticipantWorkspaceInvalid("Invalid questionnaire item identifier") from exc
    request_id = _request_id(request_id)
    if isinstance(score, bool):
        raise DelphiParticipantWorkspaceInvalid("Invalid participant score")
    try:
        normalized_score = Decimal(str(score))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DelphiParticipantWorkspaceInvalid("Invalid participant score") from exc
    if not normalized_score.is_finite():
        raise DelphiParticipantWorkspaceInvalid("Invalid participant score")
    try:
        has_excess_precision = normalized_score.quantize(Decimal("0.0001")) != normalized_score
    except InvalidOperation as exc:
        raise DelphiParticipantWorkspaceInvalid("Participant score is outside the supported range") from exc
    if has_excess_precision:
        raise DelphiParticipantWorkspaceInvalid("Participant score must use at most four decimals")
    if normalized_score < Decimal("-9999.9999") or normalized_score > Decimal("9999.9999"):
        raise DelphiParticipantWorkspaceInvalid("Participant score is outside the supported range")
    if reasoning is not None and (
        not isinstance(reasoning, str) or len(reasoning) > 4000
    ):
        raise DelphiParticipantWorkspaceInvalid("Participant reasoning is too long")

    row = _call(
        "submit_location_delphi_participant_contribution",
        (
            session_token,
            csrf_token,
            normalized_item_id,
            normalized_score,
            reasoning,
            request_id,
        ),
        connection_factory,
    )
    return {
        "status": row[0],
        "item_id": str(row[1]),
        "contribution_id": str(row[2]),
        "updated_at": row[3],
        "replayed": bool(row[4]),
    }
