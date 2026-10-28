"""Generated response payload types from the native public v1 OpenAPI snapshot."""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict, Union

class ApiPublicAttestationCounts(TypedDict):
    latest_attestation: Optional[str]
    published_count: int
    total_attestations: int


class ApiPublicCrispAssessment(TypedDict):
    assessment_id: str
    composite_score: Optional[float]
    confidence_level: Optional[Literal['high', 'moderate', 'low', 'insufficient_evidence']]
    evidence_maturity_level: Optional[int]
    location_id: str
    methodology_version: str
    period_end: str
    period_start: str
    rating: Optional[Literal['AAA', 'AA', 'A', 'B', 'C', 'D']]
    score_computed_at: Optional[str]
    status: Literal['published']


class ApiPublicCrispAssessmentEnvelope(TypedDict):
    data: ApiPublicCrispAssessment


class ApiPublicDriverCatalogEntry(TypedDict):
    driver_name: str
    driver_type: Literal['sensor', 'remote_sensing', 'market', 'blockchain', 'weather', 'climate', 'gis']
    driver_version: str


class ApiPublicDriverCatalogEnvelope(TypedDict):
    data: ApiPublicDriverCatalogResponse


class ApiPublicDriverCatalogResponse(TypedDict):
    drivers: list[ApiPublicDriverCatalogEntry]
    has_more: bool
    limit: int
    offset: int


class ApiPublicError(TypedDict):
    error: str


class ApiPublicLocation(TypedDict):
    country: Optional[str]
    id: str
    name: str
    region: Optional[str]
    status: Literal['active']


class ApiPublicLocationListResponse(TypedDict):
    data: list[ApiPublicLocation]


class ApiPublicLocationResponse(TypedDict):
    data: ApiPublicLocation


class ApiPublicLocationSummary(TypedDict):
    attestations: ApiPublicAttestationCounts
    location: ApiPublicLocation
    location_id: str
    metrics: ApiPublicMetricCounts
    summary_type: Literal['public_location_summary']


class ApiPublicLocationSummaryEnvelope(TypedDict):
    data: ApiPublicLocationSummary


class ApiPublicMetric(TypedDict):
    computed_at: Optional[str]
    display_name: str
    metric_key: str
    unit: Optional[str]
    value: Optional[float]


class ApiPublicMetricCounts(TypedDict):
    latest_computed_at: Optional[str]
    metric_count: int


class ApiPublicMetricSummary(TypedDict):
    computed: list[ApiPublicMetric]
    location_id: str
    total_computed: int


class ApiPublicMetricSummaryEnvelope(TypedDict):
    data: ApiPublicMetricSummary


PUBLIC_API_PATHS_V1 = {
    'getPublicCrispAssessmentV1': '/crisp/{location_id}',
    'getPublicLocationSummaryV1': '/analytics/{location_id}/summary',
    'getPublicLocationV1': '/locations/{location_id}',
    'getPublicMetricSummaryV1': '/metrics/{location_id}',
    'listPublicDriversV1': '/drivers',
    'listPublicLocationsV1': '/locations',
}
