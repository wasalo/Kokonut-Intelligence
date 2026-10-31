"""Strict request and receipt contracts for location-scoped metric writes."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
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


def _date(value):
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Date must use YYYY-MM-DD") from exc
        if parsed.isoformat() != value:
            raise ValueError("Date must use YYYY-MM-DD")
        return parsed
    raise ValueError("Date must use YYYY-MM-DD")


_RequestUUID = Annotated[UUID, BeforeValidator(_uuid)]
_OptionalDate = Annotated[date | None, BeforeValidator(_date)]
_MetricNumber = StrictInt | StrictFloat


class _MetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class MetricValueComputeRequest(_MetricModel):
    request_id: _RequestUUID
    metric_key: str = Field(min_length=1, max_length=100, strict=True, pattern=r"^[a-z][a-z0-9_]*$")
    period_start: _OptionalDate = None
    period_end: _OptionalDate = None

    @model_validator(mode="after")
    def validate_period(self):
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_start > self.period_end
        ):
            raise ValueError("period_start must not be after period_end")
        return self


class MetricValueComputeResponse(_MetricModel):
    metric_value_id: _RequestUUID
    metric_key: str = Field(min_length=1, max_length=100, strict=True)
    display_name: str = Field(min_length=1, max_length=255, strict=True)
    location_id: _RequestUUID
    period_start: _OptionalDate
    period_end: _OptionalDate
    value: _MetricNumber | None
    unit: str | None = Field(max_length=50, strict=True)
    status: Literal["draft"]
    verified: Literal[False]
    request_id: _RequestUUID
    created_at: AwareDatetime
    created: bool

    @field_validator("value", mode="before")
    @classmethod
    def normalize_numeric_value(cls, value):
        if isinstance(value, Decimal):
            return float(value)
        return value

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("created_at must be an ISO timestamp") from exc
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("created_at must include a timezone")
        return value


class MetricValueVerifyRequest(_MetricModel):
    request_id: _RequestUUID
    verification_notes: str | None = Field(default=None, max_length=2000, strict=True)

    @field_validator("verification_notes")
    @classmethod
    def normalize_notes(cls, value):
        if value is None:
            return None
        normalized = value.strip()
        if "\x00" in normalized:
            raise ValueError("verification_notes cannot contain null characters")
        return normalized or None


class MetricValueVerifyResponse(_MetricModel):
    metric_value_id: _RequestUUID
    location_id: _RequestUUID
    metric_key: str = Field(min_length=1, max_length=100, strict=True)
    status: Literal["verified"]
    verified: Literal[True]
    verified_at: AwareDatetime
    request_id: _RequestUUID
    replayed: bool

    @field_validator("verified_at", mode="before")
    @classmethod
    def parse_verified_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("verified_at must be an ISO timestamp") from exc
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("verified_at must include a timezone")
        return value


class MetricValueListItem(_MetricModel):
    metric_value_id: _RequestUUID
    metric_key: str = Field(min_length=1, max_length=100, strict=True)
    display_name: str = Field(min_length=1, max_length=255, strict=True)
    period_start: _OptionalDate
    period_end: _OptionalDate
    value: _MetricNumber | None
    unit: str | None = Field(max_length=50, strict=True)
    status: Literal["draft", "verified"]
    computed_at: AwareDatetime
    verified_at: AwareDatetime | None

    @field_validator("value", mode="before")
    @classmethod
    def normalize_numeric_value(cls, value):
        if isinstance(value, Decimal):
            return float(value)
        return value

    @field_validator("computed_at", "verified_at", mode="before")
    @classmethod
    def parse_timestamps(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Metric timestamp must be ISO formatted") from exc
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("Metric timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_lifecycle_timestamps(self):
        if (self.status == "draft") != (self.verified_at is None):
            raise ValueError("Metric state and verification timestamp disagree")
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_start > self.period_end
        ):
            raise ValueError("Metric period is invalid")
        return self


class MetricValueListResponse(_MetricModel):
    location_id: _RequestUUID
    cursor: str = Field(min_length=1, max_length=5, strict=True, pattern=r"^(0|[1-9][0-9]*)$")
    limit: int = Field(ge=1, le=100, strict=True)
    next_cursor: str | None = Field(default=None, max_length=5, strict=True)
    has_more: bool
    items: list[MetricValueListItem] = Field(max_length=100)

    @field_validator("next_cursor")
    @classmethod
    def validate_next_cursor_format(cls, value):
        if value is not None and not re.fullmatch(r"(0|[1-9][0-9]*)", value):
            raise ValueError("next_cursor must be a canonical numeric cursor")
        return value

    @model_validator(mode="after")
    def validate_page(self):
        offset = int(self.cursor)
        if offset > 10_000 or len(self.items) > self.limit:
            raise ValueError("Metric page exceeds its bound")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("Metric continuation marker is inconsistent")
        if self.has_more:
            expected = offset + self.limit
            if expected > 10_000 or self.next_cursor != str(expected) or len(self.items) != self.limit:
                raise ValueError("Metric continuation cursor is inconsistent")
        elif len(self.items) < self.limit and self.next_cursor is not None:
            raise ValueError("Final metric page must not expose a cursor")

        seen = set()
        previous = None
        for item in self.items:
            if item.metric_value_id in seen:
                raise ValueError("Metric page contains duplicate IDs")
            seen.add(item.metric_value_id)
            ordering_key = (item.computed_at, item.metric_value_id.int)
            if previous is not None and ordering_key > previous:
                raise ValueError("Metric page ordering is invalid")
            previous = ordering_key
        return self
