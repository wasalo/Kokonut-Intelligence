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
    PublicDriverCatalogEntry,
    PublicDriverCatalogPage,
    PublicLocation,
)

LOCATION = {
    "id": "a0000000-0000-4000-8000-000000000001",
    "name": "Kokonut Adelphi",
    "country": "DO",
    "region": "Samaná",
    "status": "active",
}
CRISP_ASSESSMENT = {
    "assessment_id": "b0000000-0000-4000-8000-000000000001",
    "location_id": LOCATION["id"],
    "period_start": "2026-01-01",
    "period_end": "2026-06-30",
    "methodology_version": "crisp-1",
    "composite_score": 82.0,
    "rating": "AA",
    "confidence_level": "high",
    "evidence_maturity_level": 3,
    "score_computed_at": "2026-10-14T12:35:00+00:00",
    "status": "published",
}
METRIC_SUMMARY = {
    "location_id": LOCATION["id"],
    "computed": [
        {
            "metric_key": "soil_carbon",
            "display_name": "Soil carbon",
            "unit": "t/ha",
            "value": 12.5,
            "computed_at": "2026-10-14T12:30:00Z",
        }
    ],
    "total_computed": 1,
}
LOCATION_SUMMARY = {
    "summary_type": "public_location_summary",
    "location_id": LOCATION["id"],
    "location": LOCATION,
    "metrics": {"metric_count": 1, "latest_computed_at": "2026-10-14T12:30:00Z"},
    "attestations": {
        "total_attestations": 2,
        "published_count": 2,
        "latest_attestation": "2026-10-14T12:35:00+00:00",
    },
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


def test_public_api_uses_a_bounded_default_request_timeout() -> None:
    session = FakeSession([FakeResponse(200, {"data": [LOCATION]})])
    client = KokonutPublicApiClient("https://gateway.example", session=session)

    client.locations.list()

    assert session.calls[0][1] == {"timeout": 10.0}


@pytest.mark.parametrize(
    "timeout",
    [None, 0, -1, float("nan"), float("inf"), 10**1000, True, "10"],
)
def test_public_api_rejects_invalid_request_timeouts(timeout: Any) -> None:
    with pytest.raises(ValueError, match="timeout must be a finite positive number of seconds"):
        KokonutPublicApiClient("https://gateway.example", timeout=timeout)


def test_all_native_public_reads_share_paths_headers_and_typed_payloads() -> None:
    crisp_time = "2026-10-14T12:35:00+00:00"
    summary_payload = {
        **LOCATION_SUMMARY,
        "attestations": {
            **LOCATION_SUMMARY["attestations"],
            "latest_attestation": crisp_time,
        },
    }
    session = FakeSession(
        [
            FakeResponse(200, {"data": [LOCATION]}),
            FakeResponse(200, {"data": LOCATION}),
            FakeResponse(
                200,
                {"data": METRIC_SUMMARY},
            ),
            FakeResponse(
                200,
                {
                    "data": {
                        **CRISP_ASSESSMENT,
                        "score_computed_at": crisp_time,
                    }
                },
            ),
            FakeResponse(200, {"data": summary_payload}),
        ]
    )
    client = KokonutPublicApiClient("https://gateway.example///", api_key="test-key", timeout=4.5, session=session)

    locations = client.locations.list()
    location = client.locations.get(LOCATION["id"])
    metrics = client.metrics.get(LOCATION["id"])
    crisp = client.crisp.get(LOCATION["id"])
    summary = client.analytics.get_summary(LOCATION["id"])

    assert len(locations) == 1
    assert isinstance(locations[0], PublicLocation)
    assert (locations[0].id, locations[0].name, locations[0].region) == (
        LOCATION["id"],
        "Kokonut Adelphi",
        "Samaná",
    )
    assert (location.id, location.name) == (LOCATION["id"], "Kokonut Adelphi")
    assert (metrics.location_id, metrics.total_computed) == (LOCATION["id"], 1)
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
        f"https://gateway.example/api/v1/locations/{LOCATION['id']}",
        f"https://gateway.example/api/v1/metrics/{LOCATION['id']}",
        f"https://gateway.example/api/v1/crisp/{LOCATION['id']}",
        f"https://gateway.example/api/v1/analytics/{LOCATION['id']}/summary",
    ]
    assert all(kwargs == {"timeout": 4.5} for _, kwargs in session.calls)
    assert session.headers == {"Accept": "application/json", "x-api-key": "test-key"}


@pytest.mark.parametrize(
    ("requested_location_id", "summary"),
    [
        (LOCATION["id"], METRIC_SUMMARY),
        (
            LOCATION["id"].upper(),
            {
                **METRIC_SUMMARY,
                "computed": [],
                "total_computed": 0,
            },
        ),
        (
            LOCATION["id"],
            {
                **METRIC_SUMMARY,
                "computed": [
                    {
                        **METRIC_SUMMARY["computed"][0],
                        "unit": None,
                        "value": None,
                        "computed_at": None,
                    }
                ],
            },
        ),
    ],
)
def test_metric_sdk_accepts_exact_scoped_summaries(
    requested_location_id: str, summary: dict[str, Any]
) -> None:
    client = KokonutPublicApiClient(
        "https://gateway.example",
        session=FakeSession([FakeResponse(200, {"data": summary})]),
    )

    result = client.metrics.get(requested_location_id)

    assert result.location_id == LOCATION["id"]
    assert result.total_computed == len(result.computed)


@pytest.mark.parametrize(
    "summary",
    [
        {**METRIC_SUMMARY, "unexpected": "field"},
        {key: value for key, value in METRIC_SUMMARY.items() if key != "total_computed"},
        {**METRIC_SUMMARY, "location_id": "not-a-uuid"},
        {**METRIC_SUMMARY, "location_id": "c0000000-0000-4000-8000-000000000001"},
        {**METRIC_SUMMARY, "computed": {}},
        {**METRIC_SUMMARY, "total_computed": -1},
        {**METRIC_SUMMARY, "total_computed": 1.5},
        {**METRIC_SUMMARY, "total_computed": True},
        {**METRIC_SUMMARY, "total_computed": 0},
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "extra": "field"}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [
                {
                    key: value
                    for key, value in METRIC_SUMMARY["computed"][0].items()
                    if key != "unit"
                }
            ],
        },
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "metric_key": 1}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "display_name": None}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "unit": 4}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "value": True}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "value": float("inf")}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [{**METRIC_SUMMARY["computed"][0], "value": "12.5"}],
        },
        {
            **METRIC_SUMMARY,
            "computed": [
                {**METRIC_SUMMARY["computed"][0], "computed_at": "2026-10-14T12:30:00"}
            ],
        },
        {
            **METRIC_SUMMARY,
            "computed": [
                {**METRIC_SUMMARY["computed"][0], "computed_at": "2026-02-30T12:30:00Z"}
            ],
        },
    ],
)
def test_metric_sdk_rejects_malformed_or_wrong_scope_summaries(
    summary: dict[str, Any],
) -> None:
    response = FakeResponse(200, {"data": summary})
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        client.metrics.get(LOCATION["id"])

    assert exc_info.value.status_code == 200
    assert exc_info.value.response is response


@pytest.mark.parametrize(
    ("requested_location_id", "summary"),
    [
        (LOCATION["id"], LOCATION_SUMMARY),
        (
            LOCATION["id"].upper(),
            {
                **LOCATION_SUMMARY,
                "location": {**LOCATION, "country": None, "region": None},
                "metrics": {"metric_count": 0, "latest_computed_at": None},
                "attestations": {
                    "total_attestations": 1,
                    "published_count": 1,
                    "latest_attestation": None,
                },
            },
        ),
        (
            LOCATION["id"],
            {
                **LOCATION_SUMMARY,
                "attestations": {
                    "total_attestations": 2,
                    "published_count": 1,
                    "latest_attestation": "2026-10-14T12:35:00+00:00",
                },
            },
        ),
    ],
)
def test_location_summary_sdk_accepts_exact_scoped_payloads_with_consistent_counts(
    requested_location_id: str, summary: dict[str, Any]
) -> None:
    client = KokonutPublicApiClient(
        "https://gateway.example",
        session=FakeSession([FakeResponse(200, {"data": summary})]),
    )

    result = client.analytics.get_summary(requested_location_id)

    assert result.location_id == LOCATION["id"]
    assert result.location.id == LOCATION["id"]
    assert result.metrics.metric_count >= 0
    assert result.attestations.published_count == summary["attestations"]["published_count"]


@pytest.mark.parametrize(
    "summary",
    [
        {**LOCATION_SUMMARY, "unexpected": "field"},
        {key: value for key, value in LOCATION_SUMMARY.items() if key != "summary_type"},
        {**LOCATION_SUMMARY, "summary_type": "other"},
        {**LOCATION_SUMMARY, "location_id": "not-a-uuid"},
        {**LOCATION_SUMMARY, "location_id": "c0000000-0000-4000-8000-000000000001"},
        {
            **LOCATION_SUMMARY,
            "location": {**LOCATION, "id": "c0000000-0000-4000-8000-000000000001"},
        },
        {**LOCATION_SUMMARY, "location": {**LOCATION, "status": "draft"}},
        {
            **LOCATION_SUMMARY,
            "location": {key: value for key, value in LOCATION.items() if key != "region"},
        },
        {**LOCATION_SUMMARY, "location": {**LOCATION, "extra": "field"}},
        {
            **LOCATION_SUMMARY,
            "metrics": {
                key: value
                for key, value in LOCATION_SUMMARY["metrics"].items()
                if key != "latest_computed_at"
            },
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {**LOCATION_SUMMARY["metrics"], "extra": "field"},
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {"metric_count": -1, "latest_computed_at": None},
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {"metric_count": True, "latest_computed_at": None},
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {"metric_count": 1.5, "latest_computed_at": None},
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {"metric_count": 1, "latest_computed_at": "2026-10-14T12:30:00"},
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {"metric_count": 0, "latest_computed_at": "2026-10-14T12:30:00Z"},
        },
        {
            **LOCATION_SUMMARY,
            "metrics": {"metric_count": 1, "latest_computed_at": None},
        },
        {
            **LOCATION_SUMMARY,
            "attestations": {
                key: value
                for key, value in LOCATION_SUMMARY["attestations"].items()
                if key != "published_count"
            },
        },
        {
            **LOCATION_SUMMARY,
            "attestations": {**LOCATION_SUMMARY["attestations"], "extra": "field"},
        },
        {
            **LOCATION_SUMMARY,
            "attestations": {
                **LOCATION_SUMMARY["attestations"],
                "total_attestations": -1,
            },
        },
        {
            **LOCATION_SUMMARY,
            "attestations": {
                **LOCATION_SUMMARY["attestations"],
                "published_count": True,
            },
        },
        {
            **LOCATION_SUMMARY,
            "attestations": {
                **LOCATION_SUMMARY["attestations"],
                "total_attestations": 1,
                "published_count": 2,
            },
        },
        {
            **LOCATION_SUMMARY,
            "attestations": {
                **LOCATION_SUMMARY["attestations"],
                "latest_attestation": "2026-10-14T12:35:00+01:60",
            },
        },
    ],
)
def test_location_summary_sdk_rejects_malformed_or_wrong_scope_payloads(
    summary: dict[str, Any],
) -> None:
    response = FakeResponse(200, {"data": summary})
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        client.analytics.get_summary(LOCATION["id"])

    assert exc_info.value.status_code == 200
    assert exc_info.value.response is response


@pytest.mark.parametrize(
    ("requested_location_id", "assessment"),
    [
        (LOCATION["id"], CRISP_ASSESSMENT),
        (
            LOCATION["id"].upper(),
            {**CRISP_ASSESSMENT, "score_computed_at": "2026-10-14T12:35:00.123456Z"},
        ),
        (
            LOCATION["id"],
            {
                **CRISP_ASSESSMENT,
                "composite_score": None,
                "rating": None,
                "confidence_level": None,
                "evidence_maturity_level": None,
                "score_computed_at": None,
            },
        ),
        (LOCATION["id"], {**CRISP_ASSESSMENT, "composite_score": 0}),
        (LOCATION["id"], {**CRISP_ASSESSMENT, "composite_score": 100}),
        (LOCATION["id"], {**CRISP_ASSESSMENT, "evidence_maturity_level": 0}),
        (LOCATION["id"], {**CRISP_ASSESSMENT, "evidence_maturity_level": 6}),
    ],
)
def test_crisp_sdk_accepts_valid_scoped_assessments(
    requested_location_id: str, assessment: dict[str, Any]
) -> None:
    client = KokonutPublicApiClient(
        "https://gateway.example",
        session=FakeSession([FakeResponse(200, {"data": assessment})]),
    )

    result = client.crisp.get(requested_location_id)

    assert result.location_id == LOCATION["id"]
    assert result.status == "published"


@pytest.mark.parametrize(
    "assessment",
    [
        {**CRISP_ASSESSMENT, "unexpected": "field"},
        {key: value for key, value in CRISP_ASSESSMENT.items() if key != "status"},
        {**CRISP_ASSESSMENT, "assessment_id": "assessment-1"},
        {**CRISP_ASSESSMENT, "location_id": "not-a-uuid"},
        {**CRISP_ASSESSMENT, "location_id": "c0000000-0000-4000-8000-000000000001"},
        {**CRISP_ASSESSMENT, "period_start": "2026-02-30"},
        {**CRISP_ASSESSMENT, "period_end": 20260630},
        {**CRISP_ASSESSMENT, "methodology_version": 1},
        {**CRISP_ASSESSMENT, "composite_score": -0.01},
        {**CRISP_ASSESSMENT, "composite_score": 100.01},
        {**CRISP_ASSESSMENT, "composite_score": True},
        {**CRISP_ASSESSMENT, "composite_score": float("nan")},
        {**CRISP_ASSESSMENT, "rating": "F"},
        {**CRISP_ASSESSMENT, "rating": []},
        {**CRISP_ASSESSMENT, "confidence_level": "certain"},
        {**CRISP_ASSESSMENT, "confidence_level": 1},
        {**CRISP_ASSESSMENT, "evidence_maturity_level": 1.5},
        {**CRISP_ASSESSMENT, "evidence_maturity_level": True},
        {**CRISP_ASSESSMENT, "evidence_maturity_level": -1},
        {**CRISP_ASSESSMENT, "evidence_maturity_level": 7},
        {**CRISP_ASSESSMENT, "score_computed_at": "2026-10-14T12:35:00"},
        {**CRISP_ASSESSMENT, "score_computed_at": "2026-02-30T12:35:00Z"},
        {**CRISP_ASSESSMENT, "score_computed_at": "2026-10-14 12:35:00Z"},
        {**CRISP_ASSESSMENT, "score_computed_at": "2026-10-14T12:35:00+25:00"},
        {**CRISP_ASSESSMENT, "score_computed_at": "2026-10-14T12:35:00+01:60"},
        {**CRISP_ASSESSMENT, "status": "verified"},
    ],
)
def test_crisp_sdk_rejects_malformed_or_wrong_scope_assessments(
    assessment: dict[str, Any],
) -> None:
    response = FakeResponse(200, {"data": assessment})
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        client.crisp.get(LOCATION["id"])

    assert exc_info.value.status_code == 200
    assert exc_info.value.response is response


def test_crisp_sdk_rejects_a_malformed_requested_location_before_accepting_response() -> None:
    response = FakeResponse(200, {"data": CRISP_ASSESSMENT})
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope"):
        client.crisp.get("location-1")

    assert len(client.session.calls) == 1


def test_driver_catalog_sdk_preserves_bounded_pagination_and_typed_entries() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "data": {
                        "drivers": [
                            {
                                "driver_name": "weather_openweathermap",
                                "driver_version": "1.2.0",
                                "driver_type": "weather",
                            }
                        ],
                        "limit": 1,
                        "offset": 12,
                        "has_more": True,
                    }
                },
            )
        ]
    )
    client = KokonutPublicApiClient("https://gateway.example", session=session)

    page = client.drivers.list(limit=1, offset=12)

    assert isinstance(page, PublicDriverCatalogPage)
    assert page == PublicDriverCatalogPage(
        drivers=[
            PublicDriverCatalogEntry(
                driver_name="weather_openweathermap",
                driver_version="1.2.0",
                driver_type="weather",
            )
        ],
        limit=1,
        offset=12,
        has_more=True,
    )
    assert session.calls == [
        (
            "https://gateway.example/api/v1/drivers?limit=1&offset=12",
            {"timeout": 10.0},
        )
    ]


@pytest.mark.parametrize(
    "catalog",
    [
        {"drivers": [], "limit": 7, "offset": 12, "has_more": "false"},
        {
            "drivers": [
                {"driver_name": "weather", "driver_version": "1", "driver_type": "weather"}
            ],
            "limit": 7,
            "offset": 12,
            "has_more": True,
        },
        {"drivers": [], "limit": True, "offset": 12, "has_more": False},
        {"drivers": [], "limit": 7, "offset": 5001, "has_more": False},
        {"drivers": [], "limit": 7, "offset": 13, "has_more": False},
        {"drivers": [], "limit": 7, "offset": 12, "has_more": False, "debug": "extra"},
        {
            "drivers": [
                {"driver_name": "weather", "driver_version": "1", "driver_type": "unknown"}
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        },
        {
            "drivers": [
                {"driver_name": 4, "driver_version": "1", "driver_type": "weather"}
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        },
        {
            "drivers": [
                {"driver_name": "weather", "driver_version": "1", "driver_type": []}
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        },
        {
            "drivers": [
                {
                    "driver_name": "weather",
                    "driver_version": "1",
                    "driver_type": "weather",
                    "private": "extra",
                }
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        },
        {
            "drivers": [
                {"driver_name": "w" * 101, "driver_version": "1", "driver_type": "weather"}
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        },
        {
            "drivers": [
                {"driver_name": "weather", "driver_version": "v" * 21, "driver_type": "weather"}
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        },
    ],
)
def test_driver_catalog_sdk_rejects_malformed_typed_response(catalog: dict[str, Any]) -> None:
    response = FakeResponse(200, {"data": catalog})
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        client.drivers.list(limit=7, offset=12)

    assert exc_info.value.response is response


def test_driver_catalog_sdk_rejects_more_when_next_page_exceeds_offset_bound() -> None:
    driver = {
        "driver_name": "weather",
        "driver_version": "1",
        "driver_type": "weather",
    }
    response = FakeResponse(
        200,
        {
            "data": {
                "drivers": [driver.copy() for _ in range(7)],
                "limit": 7,
                "offset": 4994,
                "has_more": True,
            }
        },
    )
    client = KokonutPublicApiClient("https://gateway.example", session=FakeSession([response]))

    with pytest.raises(PublicApiError, match="Invalid public API response envelope"):
        client.drivers.list(limit=7, offset=4994)


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (51, 0), (1.5, 0), (True, 0), (1, -1), (1, 5001), (1, 0.5)],
)
def test_driver_catalog_sdk_rejects_invalid_pages_before_transport(
    limit: Any, offset: Any
) -> None:
    session = FakeSession([])
    client = KokonutPublicApiClient("https://gateway.example", session=session)

    with pytest.raises(ValueError):
        client.drivers.list(limit=limit, offset=offset)

    assert session.calls == []


@pytest.mark.parametrize(
    ("response", "message", "status"),
    [
        (FakeResponse(403, {"error": "scope denied"}), "scope denied", 403),
        (
            FakeResponse(400, {"error": "Invalid location identifier"}),
            "Invalid location identifier",
            400,
        ),
        (FakeResponse(400, {"error": "invalid", "debug": "extra"}), "HTTP 400", 400),
        (FakeResponse(400, {"error": 7}), "HTTP 400", 400),
        (
            FakeResponse(
                422,
                {"detail": [{"loc": ["query", "limit"], "msg": "Input should be >= 1"}]},
            ),
            "HTTP 422",
            422,
        ),
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
        (
            FakeResponse(200, {"data": [LOCATION], "debug": "extra"}),
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
    assert exc_info.value.response is response


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
            return client.locations.get(LOCATION["id"])

    with pytest.raises(PublicApiError, match="Invalid public API response envelope"):
        request()


@pytest.mark.parametrize("method", ["list", "get"])
def test_public_api_accepts_exact_location_with_nullable_fields(method: str) -> None:
    location = {
        **LOCATION,
        "country": None,
        "region": None,
    }
    client = KokonutPublicApiClient(
        "https://gateway.example",
        session=FakeSession(
            [FakeResponse(200, {"data": [location] if method == "list" else location})]
        ),
    )

    if method == "list":
        result = client.locations.list()
        assert len(result) == 1
        parsed = result[0]
    else:
        parsed = client.locations.get(LOCATION["id"])

    assert isinstance(parsed, PublicLocation)
    assert parsed.id == LOCATION["id"]
    assert parsed.country is None
    assert parsed.region is None
    assert parsed.status == "active"


@pytest.mark.parametrize("method", ["list", "get"])
@pytest.mark.parametrize(
    "location",
    [
        {**LOCATION, "id": "not-a-uuid"},
        {**LOCATION, "name": 4},
        {**LOCATION, "country": 4},
        {**LOCATION, "region": []},
        {**LOCATION, "status": "published"},
        {key: value for key, value in LOCATION.items() if key != "region"},
        {**LOCATION, "unexpected": "field"},
    ],
)
def test_public_api_rejects_malformed_location_rows(method: str, location: dict[str, Any]) -> None:
    data = [location] if method == "list" else location
    response = FakeResponse(200, {"data": data})
    client = KokonutPublicApiClient(
        "https://gateway.example",
        session=FakeSession([response]),
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        if method == "list":
            client.locations.list()
        else:
            client.locations.get(LOCATION["id"])

    assert exc_info.value.status_code == 200
    assert exc_info.value.response is response


def test_public_api_location_detail_binds_response_id_after_uuid_normalization() -> None:
    session = FakeSession([FakeResponse(200, {"data": LOCATION})])
    client = KokonutPublicApiClient("https://gateway.example", session=session)

    result = client.locations.get(LOCATION["id"].upper())

    assert result.id == LOCATION["id"]
    assert session.calls[0][0] == (
        f"https://gateway.example/api/v1/locations/{LOCATION['id'].upper()}"
    )


def test_public_api_location_detail_rejects_a_valid_but_mismatched_response_id() -> None:
    response = FakeResponse(
        200,
        {"data": {**LOCATION, "id": "c0000000-0000-4000-8000-000000000001"}},
    )
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        client.locations.get(LOCATION["id"])

    assert exc_info.value.response is response


def test_public_api_location_detail_continues_to_encode_path_segments() -> None:
    session = FakeSession([FakeResponse(200, {"data": LOCATION})])
    client = KokonutPublicApiClient("https://gateway.example", session=session)

    with pytest.raises(PublicApiError, match="Invalid public API response envelope"):
        client.locations.get("a/b +?")

    assert session.calls[0][0] == "https://gateway.example/api/v1/locations/a%2Fb%20%2B%3F"


def test_public_api_rejects_extra_fields_on_success_envelopes() -> None:
    response = FakeResponse(200, {"data": LOCATION, "debug": "unexpected"})
    client = KokonutPublicApiClient(
        "https://gateway.example", session=FakeSession([response])
    )

    with pytest.raises(PublicApiError, match="Invalid public API response envelope") as exc_info:
        client.locations.get(LOCATION["id"])

    assert exc_info.value.response is response
