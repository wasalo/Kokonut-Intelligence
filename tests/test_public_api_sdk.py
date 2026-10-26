"""Offline contract tests for the Python native public API SDK."""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

SDK_PATH = Path(__file__).resolve().parents[1] / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from kokonut.public_api import (  # noqa: E402
    KokonutPublicApiClient,
    PublicApiError,
    PublicLocation,
)

LOCATION = {
    "id": "location-1",
    "name": "Kokonut Adelphi",
    "country": "DO",
    "region": "Samaná",
    "status": "active",
}


class FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, *, invalid_json: bool = False):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.payload = payload
        self.invalid_json = invalid_json

    def json(self) -> Any:
        if self.invalid_json:
            raise ValueError("invalid json")
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.headers: dict[str, str] = {}
        self.responses = iter(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        return next(self.responses)

    def close(self) -> None:
        self.closed = True


def test_all_native_public_reads_share_paths_headers_and_typed_payloads() -> None:
    metric_time = "2026-10-14T12:30:00Z"
    crisp_time = "2026-10-14T12:35:00+00:00"
    session = FakeSession(
        [
            FakeResponse(200, {"data": [LOCATION]}),
            FakeResponse(200, {"data": LOCATION}),
            FakeResponse(
                200,
                {
                    "data": {
                        "location_id": "location-1",
                        "computed": [
                            {
                                "metric_key": "soil_carbon",
                                "display_name": "Soil carbon",
                                "unit": "t/ha",
                                "value": 12.5,
                                "computed_at": metric_time,
                            }
                        ],
                        "total_computed": 1,
                    }
                },
            ),
            FakeResponse(
                200,
                {
                    "data": {
                        "assessment_id": "assessment-1",
                        "location_id": "location-1",
                        "period_start": "2026-01-01",
                        "period_end": "2026-06-30",
                        "methodology_version": "crisp-1",
                        "composite_score": 82.0,
                        "rating": "AA",
                        "confidence_level": "high",
                        "evidence_maturity_level": 3,
                        "score_computed_at": crisp_time,
                        "status": "published",
                    }
                },
            ),
            FakeResponse(
                200,
                {
                    "data": {
                        "summary_type": "public_location_summary",
                        "location_id": "location-1",
                        "location": LOCATION,
                        "metrics": {
                            "metric_count": 1,
                            "latest_computed_at": metric_time,
                        },
                        "attestations": {
                            "total_attestations": 2,
                            "published_count": 2,
                            "latest_attestation": crisp_time,
                        },
                    }
                },
            ),
        ]
    )
    client = KokonutPublicApiClient("https://gateway.example///", api_key="test-key", timeout=4.5, session=session)

    locations = client.locations.list()
    location = client.locations.get("a/b +?")
    metrics = client.metrics.get("location-1")
    crisp = client.crisp.get("location-1")
    summary = client.analytics.get_summary("location-1")

    assert len(locations) == 1
    assert isinstance(locations[0], PublicLocation)
    assert (locations[0].id, locations[0].name, locations[0].region) == (
        "location-1",
        "Kokonut Adelphi",
        "Samaná",
    )
    assert (location.id, location.name) == ("location-1", "Kokonut Adelphi")
    assert (metrics.location_id, metrics.total_computed) == ("location-1", 1)
    assert metrics.computed[0].computed_at == datetime(2026, 10, 14, 12, 30, tzinfo=timezone.utc)
    assert (crisp.period_start, crisp.period_end, crisp.status) == (
        date(2026, 1, 1),
        date(2026, 6, 30),
        "published",
    )
    assert crisp.score_computed_at == datetime(2026, 10, 14, 12, 35, tzinfo=timezone.utc)
    assert (summary.location.name, summary.metrics.metric_count) == ("Kokonut Adelphi", 1)
    assert summary.attestations.latest_attestation == datetime(2026, 10, 14, 12, 35, tzinfo=timezone.utc)

    assert [url for url, _ in session.calls] == [
        "https://gateway.example/api/v1/locations",
        "https://gateway.example/api/v1/locations/a%2Fb%20%2B%3F",
        "https://gateway.example/api/v1/metrics/location-1",
        "https://gateway.example/api/v1/crisp/location-1",
        "https://gateway.example/api/v1/analytics/location-1/summary",
    ]
    assert all(kwargs == {"timeout": 4.5} for _, kwargs in session.calls)
    assert session.headers == {"Accept": "application/json", "x-api-key": "test-key"}


@pytest.mark.parametrize(
    ("response", "message", "status"),
    [
        (FakeResponse(403, {"error": "scope denied"}), "scope denied", 403),
        (FakeResponse(502, {"unexpected": True}), "HTTP 502", 502),
        (FakeResponse(502, invalid_json=True), "HTTP 502", 502),
        (
            FakeResponse(200, invalid_json=True),
            "Invalid JSON response from Kokonut Gateway",
            200,
        ),
        (
            FakeResponse(200, {"data": None}),
            "Invalid public API response envelope",
            200,
        ),
    ],
)
def test_public_api_errors_are_stable(response: FakeResponse, message: str, status: int) -> None:
    client = KokonutPublicApiClient("https://gateway.example", session=FakeSession([response]))

    with pytest.raises(PublicApiError, match=message) as exc_info:
        client.locations.list()

    assert exc_info.value.status_code == status


@pytest.mark.parametrize(
    ("method", "data"),
    [
        ("list", LOCATION),
        ("get", [LOCATION]),
    ],
)
def test_public_api_rejects_wrong_top_level_data_shape(method: str, data: Any) -> None:
    client = KokonutPublicApiClient(
        "https://gateway.example",
        session=FakeSession([FakeResponse(200, {"data": data})]),
    )
    if method == "list":
        request = client.locations.list
    else:
        def request():
            return client.locations.get("location-1")

    with pytest.raises(PublicApiError, match="Invalid public API response envelope"):
        request()
