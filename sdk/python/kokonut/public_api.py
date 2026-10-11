"""Typed client for the versioned native Kokonut public API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Optional
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class PublicLocation:
    id: str
    name: str
    country: Optional[str]
    region: Optional[str]
    status: Literal["active"]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicLocation":
        return cls(
            id=str(payload["id"]),
            name=str(payload["name"]),
            country=payload.get("country"),
            region=payload.get("region"),
            status=payload["status"],
        )


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


@dataclass(frozen=True)
class PublicMetric:
    metric_key: str
    display_name: str
    unit: Optional[str]
    value: Optional[float]
    computed_at: Optional[datetime]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicMetric":
        raw_value = payload.get("value")
        return cls(
            metric_key=str(payload["metric_key"]),
            display_name=str(payload["display_name"]),
            unit=payload.get("unit"),
            value=None if raw_value is None else float(raw_value),
            computed_at=_parse_datetime(payload.get("computed_at")),
        )


@dataclass(frozen=True)
class PublicMetricSummary:
    location_id: str
    computed: list[PublicMetric]
    total_computed: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicMetricSummary":
        return cls(
            location_id=str(payload["location_id"]),
            computed=[PublicMetric.from_payload(row) for row in payload["computed"]],
            total_computed=int(payload["total_computed"]),
        )


@dataclass(frozen=True)
class PublicCrispAssessment:
    assessment_id: str
    location_id: str
    period_start: date
    period_end: date
    methodology_version: str
    composite_score: Optional[float]
    rating: Optional[str]
    confidence_level: Optional[str]
    evidence_maturity_level: Optional[int]
    score_computed_at: Optional[datetime]
    status: Literal["published"]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicCrispAssessment":
        score = payload.get("composite_score")
        maturity = payload.get("evidence_maturity_level")
        return cls(
            assessment_id=str(payload["assessment_id"]),
            location_id=str(payload["location_id"]),
            period_start=date.fromisoformat(str(payload["period_start"])),
            period_end=date.fromisoformat(str(payload["period_end"])),
            methodology_version=str(payload["methodology_version"]),
            composite_score=None if score is None else float(score),
            rating=payload.get("rating"),
            confidence_level=payload.get("confidence_level"),
            evidence_maturity_level=None if maturity is None else int(maturity),
            score_computed_at=_parse_datetime(payload.get("score_computed_at")),
            status=payload["status"],
        )


@dataclass(frozen=True)
class PublicMetricCounts:
    metric_count: int
    latest_computed_at: Optional[datetime]


@dataclass(frozen=True)
class PublicAttestationCounts:
    total_attestations: int
    published_count: int
    latest_attestation: Optional[datetime]


@dataclass(frozen=True)
class PublicLocationSummary:
    summary_type: Literal["public_location_summary"]
    location_id: str
    location: PublicLocation
    metrics: PublicMetricCounts
    attestations: PublicAttestationCounts

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicLocationSummary":
        metrics = payload["metrics"]
        attestations = payload["attestations"]
        return cls(
            summary_type=payload["summary_type"],
            location_id=str(payload["location_id"]),
            location=PublicLocation.from_payload(payload["location"]),
            metrics=PublicMetricCounts(
                metric_count=int(metrics["metric_count"]),
                latest_computed_at=_parse_datetime(metrics.get("latest_computed_at")),
            ),
            attestations=PublicAttestationCounts(
                total_attestations=int(attestations["total_attestations"]),
                published_count=int(attestations["published_count"]),
                latest_attestation=_parse_datetime(attestations.get("latest_attestation")),
            ),
        )


class PublicApiError(Exception):
    """Raised when the versioned public API returns an unsuccessful response."""

    def __init__(self, message: str, status_code: int = 0, response: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PublicLocationMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def list(self) -> list[PublicLocation]:
        return [PublicLocation.from_payload(row) for row in self._client._get("/locations")["data"]]

    def get(self, location_id: str) -> PublicLocation:
        path_id = quote(location_id, safe="")
        payload = self._client._get(f"/locations/{path_id}")["data"]
        return PublicLocation.from_payload(payload)


class PublicMetricMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def get(self, location_id: str) -> PublicMetricSummary:
        path_id = quote(location_id, safe="")
        payload = self._client._get(f"/metrics/{path_id}")["data"]
        return PublicMetricSummary.from_payload(payload)


class PublicCrispMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def get(self, location_id: str) -> PublicCrispAssessment:
        path_id = quote(location_id, safe="")
        payload = self._client._get(f"/crisp/{path_id}")["data"]
        return PublicCrispAssessment.from_payload(payload)


class PublicAnalyticsMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def get_summary(self, location_id: str) -> PublicLocationSummary:
        path_id = quote(location_id, safe="")
        payload = self._client._get(f"/analytics/{path_id}/summary")["data"]
        return PublicLocationSummary.from_payload(payload)


class KokonutPublicApiClient:
    """Client for stable `/api/v1` reads on the Kokonut Gateway.

    `base_url` is the Gateway origin (for example `http://localhost:8098`),
    not the legacy Directus origin used by :class:`KokonutClient`.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        if api_key:
            self.session.headers["x-api-key"] = api_key
        self.locations = PublicLocationMethods(self)
        self.metrics = PublicMetricMethods(self)
        self.crisp = PublicCrispMethods(self)
        self.analytics = PublicAnalyticsMethods(self)

    def close(self) -> None:
        self.session.close()

    def _get(self, path: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        if not response.ok:
            try:
                body = response.json()
                message = body.get("error", response.text) if isinstance(body, dict) else response.text
            except ValueError:
                message = response.text or f"HTTP {response.status_code}"
            raise PublicApiError(message, response.status_code, response)
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("data"), (dict, list)):
            raise PublicApiError("Invalid public API response envelope", response.status_code, response)
        return body
