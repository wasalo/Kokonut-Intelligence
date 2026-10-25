"""Location-scoped Delphi study opening and closure."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class DelphiStudyLifecycleInvalid(ValueError):
    """A Delphi lifecycle request has invalid identifiers or action."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiStudyLifecycleInvalid(f"Invalid {field} identifier") from exc


def transition_location_delphi_study(
    operator_id: str,
    location_id: str,
    study_id: str,
    action: str,
    *,
    request_id: str,
    connection_factory: Callable | None = None,
) -> dict:
    """Open a prepared study or close an open study under an exact grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    study_id = _normalize_uuid(study_id, "study")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(action, str) or action not in {"open", "close"}:
        raise DelphiStudyLifecycleInvalid("Lifecycle action must be open or close")

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
            action=action,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_location_delphi_study(
                           %s::uuid, %s::uuid, %s::text, %s::uuid
                       )""",
                (location_id, study_id, action, request_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi lifecycle function returned no study")
        connection.commit()
        return {
            "study_id": str(row[0]),
            "location_id": str(row[1]),
            "status": row[2],
            "opened_at": row[3],
            "closed_at": row[4],
            "replayed": bool(row[5]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_delphi_study_open_readiness(
    operator_id: str,
    location_id: str,
    study_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return fixed readiness blockers without exposing panel size or identity."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    study_id = _normalize_uuid(study_id, "study")

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
            action="open",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.get_location_delphi_study_open_readiness(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, study_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi readiness function returned no study")
        connection.commit()
        return {
            "study_id": str(row[0]),
            "location_id": str(row[1]),
            "status": row[2],
            "has_question": bool(row[3]),
            "minimum_policy_valid": bool(row[4]),
            "consent_minimum_met": bool(row[5]),
            "eligible_to_open": bool(row[6]),
            "blocker_codes": list(row[7] or []),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
