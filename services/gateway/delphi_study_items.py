"""Location-scoped Delphi questionnaire item drafts."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

ALLOWED_ITEM_TYPES = frozenset({"issue", "goal", "option"})
ALLOWED_SCALES = frozenset(
    {"desirability", "feasibility_technical", "feasibility_political", "probability"}
)
_SCORE_QUANTUM = Decimal("0.0001")
_SCORE_MIN = Decimal("-9999.9999")
_SCORE_MAX = Decimal("9999.9999")


class DelphiStudyItemInvalid(ValueError):
    """A Delphi questionnaire item request has invalid identifiers or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiStudyItemInvalid(f"Invalid {field} identifier") from exc


def _score(value, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise DelphiStudyItemInvalid(f"{field} must be a finite numeric score")
    if isinstance(value, float) and not math.isfinite(value):
        raise DelphiStudyItemInvalid(f"{field} must be a finite numeric score")
    try:
        number = Decimal(str(value))
        normalized = number.quantize(_SCORE_QUANTUM)
    except (InvalidOperation, ValueError) as exc:
        raise DelphiStudyItemInvalid(f"{field} must be a finite numeric score") from exc
    if not number.is_finite() or normalized != number or not _SCORE_MIN <= number <= _SCORE_MAX:
        raise DelphiStudyItemInvalid(f"{field} must fit NUMERIC(8,4)")
    return normalized


def _normalize_item_fields(
    item_type: str,
    label: str,
    description: str | None,
    scale: str,
    min_value,
    max_value,
) -> tuple[str, str, str | None, str, Decimal, Decimal]:
    if not isinstance(item_type, str) or item_type not in ALLOWED_ITEM_TYPES:
        raise DelphiStudyItemInvalid("Item type is not supported")
    if not isinstance(label, str):
        raise DelphiStudyItemInvalid("Item label must be a string")
    label = label.strip()
    if not 1 <= len(label) <= 255:
        raise DelphiStudyItemInvalid("Item label must contain 1 to 255 characters")
    if description is not None:
        if not isinstance(description, str):
            raise DelphiStudyItemInvalid("Item description must be a string")
        description = description.strip() or None
        if description is not None and len(description) > 4000:
            raise DelphiStudyItemInvalid("Item description must contain at most 4000 characters")
    if not isinstance(scale, str) or scale not in ALLOWED_SCALES:
        raise DelphiStudyItemInvalid("Item scale is not supported")
    minimum = _score(min_value, "Minimum value")
    maximum = _score(max_value, "Maximum value")
    if minimum >= maximum:
        raise DelphiStudyItemInvalid("Minimum value must be below maximum value")
    return item_type, label, description, scale, minimum, maximum


def create_location_delphi_study_item(
    operator_id: str,
    location_id: str,
    study_id: str,
    *,
    request_id: str,
    item_type: str = "option",
    label: str,
    description: str | None = None,
    scale: str = "desirability",
    min_value=-1,
    max_value=1,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay one bounded questionnaire item on a private draft study."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    study_id = _normalize_uuid(study_id, "study")
    request_id = _normalize_uuid(request_id, "request")
    item_type, label, description, scale, minimum, maximum = _normalize_item_fields(
        item_type, label, description, scale, min_value, max_value
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
            action="draft",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_delphi_study_item(
                           %s::uuid, %s::uuid, %s::text, %s::text, %s::text,
                           %s::text, %s::numeric, %s::numeric, %s::uuid
                       )""",
                (
                    location_id,
                    study_id,
                    item_type,
                    label,
                    description,
                    scale,
                    minimum,
                    maximum,
                    request_id,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi study item function returned no item")
        connection.commit()
        return {
            "item_id": str(row[0]),
            "study_id": str(row[1]),
            "location_id": str(row[2]),
            "item_type": row[3],
            "label": row[4],
            "description": row[5],
            "scale": row[6],
            "min_value": row[7],
            "max_value": row[8],
            "created_at": row[9],
            "replayed": bool(row[10]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
