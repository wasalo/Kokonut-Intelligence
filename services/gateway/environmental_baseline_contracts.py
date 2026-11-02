"""Strict request and response contracts for baseline capture."""

from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_serializer,
    field_validator,
    model_validator,
)

_RequestUUID = Annotated[
    UUID, BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value)
]
_Number = StrictInt | StrictFloat
_METRIC_NAME = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")
_MAX_BASELINE_VALUE = Decimal("99999999.9999")


def _response_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("baseline_value must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("baseline_value must be numeric") from exc
    if not number.is_finite():
        raise ValueError("baseline_value must be finite")
    return number


def _strict_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("measurement_date must use YYYY-MM-DD") from exc
        if parsed.isoformat() == value:
            return parsed
    raise ValueError("measurement_date must use YYYY-MM-DD")


def _valid_evidence_url(value: str) -> bool:
    if not value or len(value) > 2048 or _CONTROL_CHARACTER.search(value):
        return False
    if any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme.lower() in {"http", "https"}
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


class EnvironmentalBaselineCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _RequestUUID
    plot_id: _RequestUUID | None = None
    metric_name: StrictStr = Field(min_length=1, max_length=100)
    baseline_value: _Number
    unit: StrictStr | None = Field(default=None, max_length=50)
    measurement_date: date
    measurement_method: StrictStr = Field(min_length=1, max_length=100)
    source: StrictStr | None = Field(default=None, max_length=255)
    evidence_urls: list[StrictStr] = Field(default_factory=list, max_length=10)
    notes: StrictStr | None = Field(default=None, max_length=2000)

    @field_validator("measurement_date", mode="before")
    @classmethod
    def parse_measurement_date(cls, value):
        return _strict_date(value)

    @field_validator("metric_name", mode="before")
    @classmethod
    def normalize_metric_name(cls, value):
        if isinstance(value, str) and _CONTROL_CHARACTER.search(value):
            raise ValueError("metric_name is invalid")
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("unit", "measurement_method", "source", "notes", mode="before")
    @classmethod
    def normalize_text(cls, value):
        if isinstance(value, str) and _CONTROL_CHARACTER.search(value):
            raise ValueError("text values must not contain control characters")
        return value.strip() if isinstance(value, str) else value

    @field_validator("evidence_urls")
    @classmethod
    def validate_evidence_urls(cls, values):
        if any(not _valid_evidence_url(value) for value in values):
            raise ValueError("evidence_urls must contain at most 10 bounded HTTP(S) URLs")
        return values

    @model_validator(mode="after")
    def validate_capture(self):
        if not _METRIC_NAME.fullmatch(self.metric_name):
            raise ValueError("metric_name must be a lowercase identifier")
        if not self.measurement_method or _CONTROL_CHARACTER.search(self.measurement_method):
            raise ValueError("measurement_method is invalid")
        for field_name in ("unit", "source", "notes"):
            value = getattr(self, field_name)
            if value is not None and _CONTROL_CHARACTER.search(value):
                raise ValueError(f"{field_name} is invalid")
        value = self.baseline_value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("baseline_value must be numeric")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("baseline_value must be finite")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("baseline_value must be numeric") from exc
        if (
            not decimal_value.is_finite()
            or abs(decimal_value) > _MAX_BASELINE_VALUE
            or decimal_value != decimal_value.quantize(Decimal("0.0001"))
        ):
            raise ValueError("baseline_value exceeds NUMERIC(12,4) bounds")
        return self


class EnvironmentalBaselineCaptureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    baseline_id: _RequestUUID
    location_id: _RequestUUID
    plot_id: _RequestUUID | None
    metric_name: StrictStr
    baseline_value: Decimal
    unit: StrictStr | None
    measurement_date: date
    measurement_method: StrictStr
    source: StrictStr | None
    status: Literal["recorded"]
    replayed: bool

    @field_validator("measurement_date", mode="before")
    @classmethod
    def parse_response_measurement_date(cls, value):
        return _strict_date(value)

    @field_validator("baseline_value", mode="before")
    @classmethod
    def parse_response_baseline_value(cls, value):
        return _response_decimal(value)

    @field_serializer("baseline_value")
    def serialize_response_baseline_value(self, value):
        return float(value)
