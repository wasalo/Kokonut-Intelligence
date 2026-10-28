"""Strict response contract for location-scoped farm activity intake summaries."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


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


_FarmActivityIntakeUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_FarmActivityIntakeTimestamp = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]


class FarmActivityIntakeSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _FarmActivityIntakeUUID
    location_id: _FarmActivityIntakeUUID
    form_id: Literal["farm_activity_v1"]
    form_version: Literal["1.2.0"]
    collected_at: _FarmActivityIntakeTimestamp
    synced_at: _FarmActivityIntakeTimestamp | None
    activity_type: str | None
    activity_date: str | None
    eligible_for_use: Literal[True]


class FarmActivityIntakeQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: list[FarmActivityIntakeSummaryResponse] = Field(max_length=100)
    location_id: _FarmActivityIntakeUUID

    @model_validator(mode="after")
    def validate_location_scope(self):
        if any(row.location_id != self.location_id for row in self.data):
            raise ValueError("farm activity intake row does not match request location")
        return self
