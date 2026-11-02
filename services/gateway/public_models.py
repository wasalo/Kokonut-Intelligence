"""Explicit field contracts for the first native public read routes."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    evidence_maturity_level: int | None = Field(ge=0, le=6)
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


class PublicLocationIriContext(PublicModel):
    schema_: Literal["http://schema.org/"] = Field(alias="schema")
    kokonut_: Literal["https://kokonut.network/ontology#"] = Field(alias="kokonut")


class PublicLocationIriPreviousVersion(PublicModel):
    id: str = Field(alias="@id", pattern=r"^kokonut:location:[0-9a-f-]{36}:v[1-9][0-9]{0,8}$")


class PublicLocationIriDocument(PublicModel):
    """Exact, hashed public JSON-LD contract for a published location IRI."""

    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        allow_inf_nan=False,
        strict=True,
    )

    context: PublicLocationIriContext = Field(alias="@context")
    id: str = Field(alias="@id", pattern=r"^kokonut:location:[0-9a-f-]{36}:v[1-9][0-9]{0,8}$")
    type: Literal["kokonut:location"] = Field(alias="@type")
    name: str = Field(alias="schema:name", min_length=1, max_length=255)
    country: str | None = Field(alias="schema:addressCountry", max_length=255)
    region: str | None = Field(alias="schema:addressRegion", max_length=255)
    status: Literal["active"] = Field(alias="kokonut:status")
    version: int = Field(alias="kokonut:version", strict=True, ge=1, le=999_999_999)
    previous_version: PublicLocationIriPreviousVersion | None = Field(
        default=None, alias="kokonut:previousVersion"
    )
    projection_hash: str = Field(
        alias="kokonut:publicProjectionHash", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    hash_algorithm: Literal["sha256"] = Field(alias="kokonut:hashAlgorithm")

    @model_validator(mode="after")
    def validate_location_version_and_projection_hash(self):
        iri_pattern = re.compile(
            r"^kokonut:location:(?P<location>[0-9a-f-]{36}):v(?P<version>[1-9][0-9]{0,8})$"
        )
        match = iri_pattern.fullmatch(self.id)
        if match is None or str(UUID(match.group("location"))) != match.group("location"):
            raise ValueError("location IRI must be canonical")
        if int(match.group("version")) != self.version:
            raise ValueError("location IRI version must match the document version")
        if self.previous_version is not None:
            previous = iri_pattern.fullmatch(self.previous_version.id)
            if (
                previous is None
                or previous.group("location") != match.group("location")
                or int(previous.group("version")) != self.version - 1
            ):
                raise ValueError("previous location IRI must reference the immediately prior version")

        unsigned_document = self.model_dump(
            mode="json",
            by_alias=True,
            exclude={"projection_hash", "hash_algorithm"},
        )
        if self.previous_version is None:
            unsigned_document.pop("kokonut:previousVersion", None)
        canonical = json.dumps(
            unsigned_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        expected_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if self.projection_hash != expected_hash:
            raise ValueError("public projection hash does not match the document")
        return self


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

    @model_validator(mode="after")
    def validate_latest_timestamp_matches_count(self):
        if (self.metric_count == 0) != (self.latest_computed_at is None):
            raise ValueError("latest_computed_at must match metric_count")
        return self


class PublicAttestationCounts(PublicModel):
    total_attestations: int = Field(ge=0)
    published_count: int = Field(ge=0)
    latest_attestation: datetime | None

    @model_validator(mode="after")
    def validate_published_count_subset(self):
        if self.published_count > self.total_attestations:
            raise ValueError("published_count must not exceed total_attestations")
        return self


class PublicLocationSummary(PublicModel):
    summary_type: Literal["public_location_summary"]
    location_id: UUID
    location: PublicLocation
    metrics: PublicMetricCounts
    attestations: PublicAttestationCounts


class PublicLocationSummaryEnvelope(PublicModel):
    data: PublicLocationSummary
