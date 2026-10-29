"""Strict response models for the private report-review read projections."""

import json
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)

MAX_REPORT_DETAIL_BYTES = 512 * 1024


def _response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


def _response_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date value is invalid") from exc
    raise ValueError("date value is invalid")


def _response_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


_ReportResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_ReportResponseDate = Annotated[date, BeforeValidator(_response_date)]
_ReportResponseDateTime = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]


class SubmittedReportSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _ReportResponseUUID
    report_name: str = Field(max_length=255)
    report_type: str | None = Field(max_length=100)
    status: Literal["submitted"]
    period_start: _ReportResponseDate | None
    period_end: _ReportResponseDate | None
    snapshot_hash: str | None = Field(max_length=255)
    created_at: _ReportResponseDateTime | None
    location_name: str = Field(max_length=255)


class ReportReviewQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: list[SubmittedReportSummaryResponse] = Field(max_length=100)
    location_id: _ReportResponseUUID


class SubmittedReportDetail(SubmittedReportSummaryResponse):
    report_data: dict[str, Any] = Field(
        description="Frozen JSON report object, limited to 524288 UTF-8 bytes."
    )

    @field_validator("report_data")
    @classmethod
    def validate_report_payload(cls, value):
        try:
            encoded = json.dumps(
                value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
            raise ValueError("Report payload must contain JSON-compatible values") from exc
        if len(encoded) > MAX_REPORT_DETAIL_BYTES:
            raise ValueError("Report payload exceeds the private review response limit")
        return value


class SubmittedReportDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    data: SubmittedReportDetail


class ReportReviewErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str
