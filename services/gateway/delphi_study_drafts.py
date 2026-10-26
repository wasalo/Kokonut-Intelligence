"""Location-scoped creation of private Delphi study drafts."""

from __future__ import annotations

import json
import math
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

DEFAULT_STOPPING_CRITERIA = {
    "max_duration_hours": 720,
    "stability_pct": 5.0,
    "min_participants": 3,
    "iqr_threshold": 1.0,
}
ALLOWED_VARIATIONS = frozenset(
    {"classic", "policy", "argument", "disaggregative", "real_time", "fast_track"}
)
ALLOWED_FACILITATORS = frozenset({"agent", "human", "hybrid"})


class DelphiStudyDraftInvalid(ValueError):
    """A Delphi study draft request has invalid identifiers or fields."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DelphiStudyDraftInvalid(f"Invalid {field} identifier") from exc


def _criteria_number(value, field: str, *, minimum: float, maximum: float, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DelphiStudyDraftInvalid(f"{field} must be a number between {minimum:g} and {maximum:g}")
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise DelphiStudyDraftInvalid(f"{field} must be a number between {minimum:g} and {maximum:g}")
    if integer and int(value) != value:
        raise DelphiStudyDraftInvalid(f"{field} must be a whole number")
    return int(value) if integer else float(value)


def _normalize_criteria(value: dict | None) -> dict:
    if value is None:
        return dict(DEFAULT_STOPPING_CRITERIA)
    if not isinstance(value, dict):
        raise DelphiStudyDraftInvalid("Stopping criteria must be an object")
    unknown = set(value) - set(DEFAULT_STOPPING_CRITERIA)
    if unknown:
        raise DelphiStudyDraftInvalid("Stopping criteria contain unsupported fields")
    criteria = {**DEFAULT_STOPPING_CRITERIA, **value}
    return {
        "max_duration_hours": _criteria_number(
            criteria["max_duration_hours"], "max_duration_hours", minimum=1, maximum=8760, integer=True
        ),
        "stability_pct": _criteria_number(
            criteria["stability_pct"], "stability_pct", minimum=0, maximum=100
        ),
        "min_participants": _criteria_number(
            criteria["min_participants"], "min_participants", minimum=3, maximum=10000, integer=True
        ),
        "iqr_threshold": _criteria_number(
            criteria["iqr_threshold"], "iqr_threshold", minimum=0, maximum=2
        ),
    }


def create_location_delphi_study_draft(
    operator_id: str,
    location_id: str,
    *,
    request_id: str,
    title: str,
    description: str | None = None,
    variation: str = "real_time",
    facilitator_type: str = "agent",
    stopping_criteria: dict | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or replay a draft study with an exact signed location grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(title, str):
        raise DelphiStudyDraftInvalid("Title must be a string")
    title = title.strip()
    if not 1 <= len(title) <= 255:
        raise DelphiStudyDraftInvalid("Title must contain 1 to 255 characters")
    if description is not None:
        if not isinstance(description, str):
            raise DelphiStudyDraftInvalid("Description must be a string")
        description = description.strip() or None
        if description is not None and len(description) > 4000:
            raise DelphiStudyDraftInvalid("Description must contain at most 4000 characters")
    if not isinstance(variation, str) or variation not in ALLOWED_VARIATIONS:
        raise DelphiStudyDraftInvalid("Variation is not supported")
    if not isinstance(facilitator_type, str) or facilitator_type not in ALLOWED_FACILITATORS:
        raise DelphiStudyDraftInvalid("Facilitator type is not supported")
    criteria = _normalize_criteria(stopping_criteria)

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
                """SELECT * FROM kokonut_security.create_location_delphi_study_draft(
                           %s::uuid, %s::uuid, %s::text, %s::text, %s::text,
                           %s::jsonb, %s::uuid
                       )""",
                (
                    location_id,
                    title,
                    description,
                    variation,
                    facilitator_type,
                    json.dumps(criteria, sort_keys=True),
                    request_id,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Delphi study draft function returned no study")
        connection.commit()
        return {
            "study_id": str(row[0]),
            "location_id": location_id,
            "title": row[1],
            "status": row[2],
            "created_at": row[3],
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
