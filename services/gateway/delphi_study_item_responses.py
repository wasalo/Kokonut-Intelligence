"""Strict response contract for location-scoped Delphi study-item creation."""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    model_validator,
)


def _response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


def _response_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


def _response_score(value):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise ValueError("score value is invalid")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("score value is invalid")
    try:
        score = value if isinstance(value, Decimal) else Decimal(str(value))
        normalized = score.quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("score value is invalid") from exc
    if (
        not score.is_finite()
        or normalized != score
        or not Decimal("-9999.9999") <= score <= Decimal("9999.9999")
    ):
        raise ValueError("score value is outside NUMERIC(8,4)")
    return score


_DelphiStudyItemResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_DelphiStudyItemResponseTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(_response_datetime),
]
_DelphiStudyItemScore = Annotated[
    Decimal,
    BeforeValidator(_response_score),
    Field(
        max_digits=8,
        decimal_places=4,
        ge=Decimal("-9999.9999"),
        le=Decimal("9999.9999"),
    ),
]


class DelphiStudyItemCreateResponse(BaseModel):
    """Exact persisted item projection, including whether this was a replay."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    item_id: _DelphiStudyItemResponseUUID
    study_id: _DelphiStudyItemResponseUUID
    location_id: _DelphiStudyItemResponseUUID
    item_type: Literal["issue", "goal", "option"]
    label: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    description: Annotated[StrictStr, Field(min_length=1, max_length=4000)] | None
    scale: Literal[
        "desirability",
        "feasibility_technical",
        "feasibility_political",
        "probability",
    ]
    min_value: _DelphiStudyItemScore
    max_value: _DelphiStudyItemScore
    created_at: _DelphiStudyItemResponseTimestamp
    replayed: StrictBool

    @model_validator(mode="after")
    def validate_score_range(self):
        if self.min_value >= self.max_value:
            raise ValueError("minimum score must be below maximum score")
        return self
