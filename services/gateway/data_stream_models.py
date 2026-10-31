"""Strict request and response contracts for Gateway Data Stream writes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

DataStreamPostType = Literal[
    "field_update",
    "monitoring_report",
    "photo",
    "satellite_image",
    "sensor_reading",
    "soil_analysis",
    "water_analysis",
    "biodiversity_survey",
    "harvest_report",
    "weather_report",
    "financial_report",
    "community_update",
    "training_record",
    "intervention_record",
    "compliance_record",
]


class DataStreamPostCreateRequest(BaseModel):
    """Caller-controlled fields for creating a draft post in one location."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, allow_inf_nan=False)

    location_id: UUID
    post_type: DataStreamPostType = "monitoring_report"
    title: str = Field(min_length=1, max_length=255)
    content: str | None = ""
    expires_at: AwareDatetime | None = None

    @field_validator("expires_at", mode="before")
    @classmethod
    def require_iso8601_expiry_string(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("expires_at must be an ISO-8601 timestamp string")
        return value


class DataStreamPostCreateResponse(BaseModel):
    """Stable response for a successfully created draft post."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    post_id: UUID
