"""Strict operator report-export request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
)


def _uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


def _aware_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Timestamp value is invalid") from exc
    raise ValueError("Timestamp value is invalid")


_ResponseUUID = Annotated[UUID, BeforeValidator(_uuid)]
_ResponseDateTime = Annotated[AwareDatetime, BeforeValidator(_aware_datetime)]
ReportExportStatus = Literal[
    "pending",
    "processing",
    "retryable",
    "dead_letter",
    "completed",
    "cancelled",
]


class ReportExportCreateRequest(BaseModel):
    """Only a snapshot identifier and caller-generated idempotency UUID."""

    model_config = ConfigDict(extra="forbid", strict=True)

    report_snapshot_id: _ResponseUUID
    idempotency_key: _ResponseUUID


class ReportExportCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _ResponseUUID
    status: ReportExportStatus
    created_at: _ResponseDateTime


class ReportExportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _ResponseUUID
    snapshot_id: _ResponseUUID
    location_id: _ResponseUUID
    status: ReportExportStatus
    attempt_count: int = Field(ge=0)
    artifact_size: int | None = Field(default=None, gt=0, le=524288)
    created_at: _ResponseDateTime
    updated_at: _ResponseDateTime
    completed_at: _ResponseDateTime | None
    last_error_class: str | None = Field(
        default=None,
        max_length=80,
        pattern=r"^[A-Za-z][A-Za-z0-9_]{0,79}$",
    )


class ReportExportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _ResponseUUID
    data: list[ReportExportSummary] = Field(max_length=50)


class ReportExportDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _ResponseUUID
    data: ReportExportSummary
