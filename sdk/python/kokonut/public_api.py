"""Typed client for the versioned native Kokonut public API."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Literal, Optional
from urllib.parse import quote
from uuid import UUID

import requests

from .generated_public_api import (
    PUBLIC_API_PATHS_V1,
    ApiPublicCrispAssessment,
    ApiPublicDriverCatalogResponse,
    ApiPublicLocation,
    ApiPublicLocationSummary,
    ApiPublicMetric,
    ApiPublicMetricSummary,
)

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_RFC3339_DATETIME_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T(?P<hour>[0-9]{2}):"
    r"(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})(?:\.[0-9]+)?"
    r"(?P<zone>Z|[+-](?P<offset_hour>[0-9]{2}):(?P<offset_minute>[0-9]{2}))$"
)


def _normalized_uuid(value: Any) -> str | None:
    if not isinstance(value, str) or not _UUID_PATTERN.fullmatch(value):
        return None
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_rfc3339_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = _RFC3339_DATETIME_PATTERN.fullmatch(value)
    if match is None:
        return False
    if (
        int(match["hour"]) > 23
        or int(match["minute"]) > 59
        or int(match["second"]) > 59
    ):
        return False
    if match["zone"] != "Z" and (
        int(match["offset_hour"]) > 23 or int(match["offset_minute"]) > 59
    ):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _is_public_crisp_assessment(value: Any, requested_location_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "assessment_id",
        "location_id",
        "period_start",
        "period_end",
        "methodology_version",
        "composite_score",
        "rating",
        "confidence_level",
        "evidence_maturity_level",
        "score_computed_at",
        "status",
    }:
        return False

    expected_location_id = _normalized_uuid(requested_location_id)
    if expected_location_id is None:
        return False
    if _normalized_uuid(value["assessment_id"]) is None:
        return False
    if _normalized_uuid(value["location_id"]) != expected_location_id:
        return False

    score = value["composite_score"]
    maturity = value["evidence_maturity_level"]
    return (
        _is_iso_date(value["period_start"])
        and _is_iso_date(value["period_end"])
        and isinstance(value["methodology_version"], str)
        and (
            score is None
            or (
                not isinstance(score, bool)
                and isinstance(score, (int, float))
                and 0 <= score <= 100
            )
        )
        and (
            value["rating"] is None
            or (
                isinstance(value["rating"], str)
                and value["rating"] in {"AAA", "AA", "A", "B", "C", "D"}
            )
        )
        and (
            value["confidence_level"] is None
            or (
                isinstance(value["confidence_level"], str)
                and value["confidence_level"]
                in {"high", "moderate", "low", "insufficient_evidence"}
            )
        )
        and (
            maturity is None
            or (isinstance(maturity, int) and not isinstance(maturity, bool))
        )
        and (
            value["score_computed_at"] is None
            or _is_rfc3339_datetime(value["score_computed_at"])
        )
        and isinstance(value["status"], str)
        and value["status"] == "published"
    )


def _is_public_metric_summary(value: Any, requested_location_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "location_id",
        "computed",
        "total_computed",
    }:
        return False

    expected_location_id = _normalized_uuid(requested_location_id)
    computed = value["computed"]
    total_computed = value["total_computed"]
    if (
        expected_location_id is None
        or _normalized_uuid(value["location_id"]) != expected_location_id
        or not isinstance(computed, list)
        or isinstance(total_computed, bool)
        or not isinstance(total_computed, int)
        or total_computed < 0
        or total_computed != len(computed)
    ):
        return False

    for row in computed:
        if not isinstance(row, dict) or set(row) != {
            "metric_key",
            "display_name",
            "unit",
            "value",
            "computed_at",
        }:
            return False
        metric_value = row["value"]
        if (
            not isinstance(row["metric_key"], str)
            or not isinstance(row["display_name"], str)
            or (row["unit"] is not None and not isinstance(row["unit"], str))
            or (
                metric_value is not None
                and not _is_finite_number(metric_value)
            )
            or (
                row["computed_at"] is not None
                and not _is_rfc3339_datetime(row["computed_at"])
            )
        ):
            return False
    return True


def _is_nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_public_location_summary(value: Any, requested_location_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "summary_type",
        "location_id",
        "location",
        "metrics",
        "attestations",
    }:
        return False

    expected_location_id = _normalized_uuid(requested_location_id)
    location = value["location"]
    metrics = value["metrics"]
    attestations = value["attestations"]
    if (
        expected_location_id is None
        or value["summary_type"] != "public_location_summary"
        or _normalized_uuid(value["location_id"]) != expected_location_id
        or not _is_public_location(location)
        or _normalized_uuid(location["id"]) != expected_location_id
        or not isinstance(metrics, dict)
        or set(metrics) != {"metric_count", "latest_computed_at"}
        or not isinstance(attestations, dict)
        or set(attestations)
        != {"total_attestations", "published_count", "latest_attestation"}
    ):
        return False

    return (
        _is_nonnegative_integer(metrics["metric_count"])
        and (
            metrics["latest_computed_at"] is None
            or _is_rfc3339_datetime(metrics["latest_computed_at"])
        )
        and _is_nonnegative_integer(attestations["total_attestations"])
        and _is_nonnegative_integer(attestations["published_count"])
        and (
            attestations["latest_attestation"] is None
            or _is_rfc3339_datetime(attestations["latest_attestation"])
        )
    )


@dataclass(frozen=True)
class PublicLocation:
    id: str
    name: str
    country: Optional[str]
    region: Optional[str]
    status: Literal["active"]

    @classmethod
    def from_payload(cls, payload: ApiPublicLocation) -> "PublicLocation":
        return cls(
            id=str(payload["id"]),
            name=str(payload["name"]),
            country=payload.get("country"),
            region=payload.get("region"),
            status=payload["status"],
        )


def _is_public_location(value: Any) -> bool:
    """Return whether a payload matches the Gateway's exact location model."""
    if not isinstance(value, dict) or set(value) != {
        "id", "name", "country", "region", "status"
    }:
        return False

    location_id = value["id"]
    if not isinstance(location_id, str):
        return False
    try:
        parsed_id = UUID(location_id)
    except (TypeError, ValueError, AttributeError):
        return False
    if str(parsed_id) != location_id.lower():
        return False

    return (
        isinstance(value["name"], str)
        and (value["country"] is None or isinstance(value["country"], str))
        and (value["region"] is None or isinstance(value["region"], str))
        and isinstance(value["status"], str)
        and value["status"] == "active"
    )


def _is_public_location_list(value: Any) -> bool:
    return isinstance(value, list) and all(_is_public_location(row) for row in value)


@dataclass(frozen=True)
class PublicDriverCatalogEntry:
    driver_name: str
    driver_version: str
    driver_type: Literal[
        "sensor", "remote_sensing", "market", "blockchain", "weather", "climate", "gis"
    ]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicDriverCatalogEntry":
        return cls(
            driver_name=str(payload["driver_name"]),
            driver_version=str(payload["driver_version"]),
            driver_type=payload["driver_type"],
        )


@dataclass(frozen=True)
class PublicDriverCatalogPage:
    drivers: list[PublicDriverCatalogEntry]
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def from_payload(
        cls, payload: ApiPublicDriverCatalogResponse
    ) -> "PublicDriverCatalogPage":
        return cls(
            drivers=[
                PublicDriverCatalogEntry.from_payload(row)
                for row in payload["drivers"]
            ],
            limit=int(payload["limit"]),
            offset=int(payload["offset"]),
            has_more=bool(payload["has_more"]),
        )


def _validate_driver_page(limit: int, offset: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer from 1 through 50")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 5000:
        raise ValueError("offset must be an integer from 0 through 5000")


def _is_driver_catalog_response(
    value: Any, *, expected_limit: int, expected_offset: int
) -> bool:
    if not isinstance(value, dict):
        return False
    if set(value) != {"drivers", "limit", "offset", "has_more"}:
        return False
    drivers = value.get("drivers")
    limit = value.get("limit")
    offset = value.get("offset")
    if (
        not isinstance(drivers, list)
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 50
        or isinstance(offset, bool)
        or not isinstance(offset, int)
        or not 0 <= offset <= 5000
        or limit != expected_limit
        or offset != expected_offset
        or not isinstance(value.get("has_more"), bool)
    ):
        return False
    driver_types = {
        "sensor",
        "remote_sensing",
        "market",
        "blockchain",
        "weather",
        "climate",
        "gis",
    }
    return all(
        isinstance(row, dict)
        and set(row) == {"driver_name", "driver_version", "driver_type"}
        and isinstance(row.get("driver_name"), str)
        and len(row["driver_name"]) <= 100
        and isinstance(row.get("driver_version"), str)
        and len(row["driver_version"]) <= 20
        and isinstance(row.get("driver_type"), str)
        and row["driver_type"] in driver_types
        for row in drivers
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
    def from_payload(cls, payload: ApiPublicMetric) -> "PublicMetric":
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
    def from_payload(cls, payload: ApiPublicMetricSummary) -> "PublicMetricSummary":
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
    def from_payload(cls, payload: ApiPublicCrispAssessment) -> "PublicCrispAssessment":
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
    def from_payload(cls, payload: ApiPublicLocationSummary) -> "PublicLocationSummary":
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
        path = PUBLIC_API_PATHS_V1["listPublicLocationsV1"]
        return [
            PublicLocation.from_payload(row)
            for row in self._client._get(
                path,
                data_shape="array",
                data_validator=_is_public_location_list,
            )["data"]
        ]

    def get(self, location_id: str) -> PublicLocation:
        path = self._client._path("getPublicLocationV1", location_id=location_id)
        payload = self._client._get(
            path,
            data_shape="object",
            data_validator=lambda value: _is_public_location(value)
            and _normalized_uuid(value["id"]) == _normalized_uuid(location_id),
        )["data"]
        return PublicLocation.from_payload(payload)


class PublicDriverMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def list(self, *, limit: int = 50, offset: int = 0) -> PublicDriverCatalogPage:
        _validate_driver_page(limit, offset)
        path = PUBLIC_API_PATHS_V1["listPublicDriversV1"]
        payload = self._client._get(
            f"{path}?limit={limit}&offset={offset}",
            data_shape="object",
            data_validator=lambda value: _is_driver_catalog_response(
                value, expected_limit=limit, expected_offset=offset
            ),
        )["data"]
        return PublicDriverCatalogPage.from_payload(payload)


class PublicMetricMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def get(self, location_id: str) -> PublicMetricSummary:
        path = self._client._path("getPublicMetricSummaryV1", location_id=location_id)
        payload = self._client._get(
            path,
            data_shape="object",
            data_validator=lambda value: _is_public_metric_summary(value, location_id),
        )["data"]
        return PublicMetricSummary.from_payload(payload)


class PublicCrispMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def get(self, location_id: str) -> PublicCrispAssessment:
        path = self._client._path("getPublicCrispAssessmentV1", location_id=location_id)
        payload = self._client._get(
            path,
            data_shape="object",
            data_validator=lambda value: _is_public_crisp_assessment(value, location_id),
        )["data"]
        return PublicCrispAssessment.from_payload(payload)


class PublicAnalyticsMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def get_summary(self, location_id: str) -> PublicLocationSummary:
        path = self._client._path("getPublicLocationSummaryV1", location_id=location_id)
        payload = self._client._get(
            path,
            data_shape="object",
            data_validator=lambda value: _is_public_location_summary(value, location_id),
        )["data"]
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
        try:
            valid_timeout = (
                not isinstance(timeout, bool)
                and isinstance(timeout, (int, float))
                and math.isfinite(timeout)
                and timeout > 0
            )
        except (OverflowError, TypeError):
            valid_timeout = False
        if not valid_timeout:
            raise ValueError("timeout must be a finite positive number of seconds")
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        if api_key:
            self.session.headers["x-api-key"] = api_key
        self.locations = PublicLocationMethods(self)
        self.drivers = PublicDriverMethods(self)
        self.metrics = PublicMetricMethods(self)
        self.crisp = PublicCrispMethods(self)
        self.analytics = PublicAnalyticsMethods(self)

    def close(self) -> None:
        self.session.close()

    def _path(self, operation_id: str, **path_params: str) -> str:
        template = PUBLIC_API_PATHS_V1[operation_id]
        encoded_params = {
            name: quote(value, safe="") for name, value in path_params.items()
        }
        return template.format(**encoded_params)

    def _get(
        self,
        path: str,
        *,
        data_shape: Literal["array", "object"],
        data_validator: Optional[Callable[[Any], bool]] = None,
    ) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        if not response.ok:
            try:
                body = response.json()
                error_message = (
                    body["error"]
                    if isinstance(body, dict) and set(body) == {"error"}
                    else None
                )
                if isinstance(error_message, str):
                    message = error_message
                else:
                    message = f"HTTP {response.status_code}"
            except ValueError:
                message = f"HTTP {response.status_code}"
            raise PublicApiError(message, response.status_code, response)
        try:
            body = response.json()
        except ValueError as exc:
            raise PublicApiError(
                "Invalid JSON response from Kokonut Gateway",
                response.status_code,
                response,
            ) from exc
        if not isinstance(body, dict) or set(body) != {"data"}:
            raise PublicApiError("Invalid public API response envelope", response.status_code, response)
        data = body.get("data")
        valid_data = isinstance(data, list) if data_shape == "array" else isinstance(data, dict)
        if not valid_data or (data_validator is not None and not data_validator(data)):
            raise PublicApiError("Invalid public API response envelope", response.status_code, response)
        return body
