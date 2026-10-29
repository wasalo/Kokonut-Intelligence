"""Strict response contracts for private Field Collector enrollment routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, StringConstraints


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


_MobileEnrollmentResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_MobileEnrollmentResponseDateTime = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]
_MobileEnrollmentCode = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_-]{43}$", min_length=43, max_length=43),
]


class MobileEnrollmentCreateResponse(BaseModel):
    """The one-time code is returned only by the private create operation."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    enrollment_id: _MobileEnrollmentResponseUUID
    enrollment_code: _MobileEnrollmentCode
    expires_at: _MobileEnrollmentResponseDateTime
