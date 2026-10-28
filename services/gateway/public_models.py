"""Explicit field contracts for the first native public read routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, allow_inf_nan=False)


class PublicError(PublicModel):
    error: str


class PublicMetric(PublicModel):
    metric_key: str
    display_name: str
    unit: str | None
    value: float | None
    computed_at: datetime | None


class PublicMetricSummary(PublicModel):
    location_id: UUID
    computed: list[PublicMetric]
    total_computed: int = Field(ge=0)


class PublicMetricSummaryEnvelope(PublicModel):
    data: PublicMetricSummary


class PublicCrispAssessment(PublicModel):
    assessment_id: UUID
    location_id: UUID
    period_start: date
    period_end: date
    methodology_version: str
    composite_score: float | None = Field(ge=0, le=100)
    rating: Literal["AAA", "AA", "A", "B", "C", "D"] | None
    confidence_level: Literal["high", "moderate", "low", "insufficient_evidence"] | None
    evidence_maturity_level: int | None
    score_computed_at: datetime | None
    status: Literal["published"]


class PublicCrispAssessmentEnvelope(PublicModel):
    data: PublicCrispAssessment


class PublicLocation(PublicModel):
    id: UUID
    name: str
    country: str | None
    region: str | None
    status: Literal["active"]


class PublicLocationListResponse(PublicModel):
    data: list[PublicLocation]


class PublicLocationResponse(PublicModel):
    data: PublicLocation


class PublicDriverCatalogEntry(PublicModel):
    """Non-sensitive public metadata for an available data-source driver."""

    driver_name: str = Field(max_length=100)
    driver_version: str = Field(max_length=20)
    driver_type: Literal[
        "sensor", "remote_sensing", "market", "blockchain", "weather", "climate", "gis"
    ]


class PublicDriverCatalogResponse(PublicModel):
    drivers: list[PublicDriverCatalogEntry]
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=5000)
    has_more: bool


class PublicDriverCatalogEnvelope(PublicModel):
    data: PublicDriverCatalogResponse


class PublicMetricCounts(PublicModel):
    metric_count: int = Field(ge=0)
    latest_computed_at: datetime | None


class PublicAttestationCounts(PublicModel):
    total_attestations: int = Field(ge=0)
    published_count: int = Field(ge=0)
    latest_attestation: datetime | None


class PublicLocationSummary(PublicModel):
    summary_type: Literal["public_location_summary"]
    location_id: UUID
    location: PublicLocation
    metrics: PublicMetricCounts
    attestations: PublicAttestationCounts


class PublicLocationSummaryEnvelope(PublicModel):
    data: PublicLocationSummary
