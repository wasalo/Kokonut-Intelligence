"""Strict, aggregate-only response contract for pollinator health summaries."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.pollinator_health_routes import (  # noqa: E402
    register_pollinator_health_routes,
)


def _summary_payload(location_id):
    return {
        "location_id": location_id,
        "verified_observations": [{
            "pollinator_type": "wild_bee",
            "observation_method": "transect",
            "status": "verified",
            "record_count": 2,
            "total_observed": 42.0,
            "mean_duration_minutes": 15.0,
            "first_observation_date": "2026-03-01",
            "last_observation_date": "2026-03-20",
        }],
        "observation_trends": [{
            "pollinator_type": "wild_bee",
            "observation_count": 2,
            "avg_count": 21.0,
            "max_count": 30,
            "first_observation_date": "2026-03-01",
            "last_observation_date": "2026-03-20",
            "total_count": 42.0,
            "trend": "increasing",
            "change_pct": 20.0,
        }],
        "habitat_inventory": [{
            "habitat_type": "wildflower_strip",
            "condition": "good",
            "status": "active",
            "record_count": 1,
            "total_area_m2": 240.0,
        }],
        "verified_pesticide_impacts": [{
            "toxicity_class": "moderate",
            "pollinator_mortality_observed": False,
            "record_count": 1,
            "mean_mortality_pct": 0.0,
            "first_application_date": "2026-03-04",
            "last_application_date": "2026-03-04",
        }],
        "pesticide_risk_summary": {
            "period_days": 90,
            "total_applications": 1,
            "overall_risk": "low",
            "risk_distribution": {
                "low": 0,
                "moderate": 1,
                "high": 0,
                "very_high": 0,
                "unknown": 0,
            },
            "mortality_events": 0,
        },
        "active_hives": [{
            "colony_strength": "strong",
            "queen_status": "present",
            "hive_count": 2,
            "total_honey_yield_kg": 12.0,
            "mean_varroa_count": 0.5,
            "last_inspection_date": "2026-03-19",
        }],
        "active_hive_summary": {
            "total_hives": 2,
            "avg_colony_strength_score": 8.5,
        },
    }


def _route_app(provider, database_error_type=Exception):
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_pollinator_health_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=database_error_type)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=str(uuid4()))
        )
        return await call_next(request)

    return app


def test_pollinator_summary_publishes_strict_openapi_response_schema():
    app = _route_app(object())
    openapi = app.openapi()
    response_schema = openapi["paths"][
        "/operator/api/pollinators/{location_id}/summary"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {
        "$ref": "#/components/schemas/PollinatorHealthSummaryResponse"
    }
    schemas = openapi["components"]["schemas"]
    for name in (
        "PollinatorHealthSummaryResponse",
        "PollinatorObservationAggregate",
        "PollinatorObservationTrend",
        "PollinatorHabitatAggregate",
        "VerifiedPesticideImpactAggregate",
        "PesticideRiskSummary",
        "PesticideRiskDistribution",
        "ActiveHiveAggregate",
        "ActiveHiveSummary",
    ):
        assert schemas[name]["additionalProperties"] is False
    summary = schemas["PollinatorHealthSummaryResponse"]["properties"]
    assert summary["verified_observations"]["maxItems"] == 108
    assert summary["observation_trends"]["maxItems"] == 9
    assert summary["habitat_inventory"]["maxItems"] == 140
    assert summary["verified_pesticide_impacts"]["maxItems"] == 10
    assert summary["active_hives"]["maxItems"] == 25


def test_pollinator_summary_returns_valid_aggregate_and_private_headers(monkeypatch):
    location_id = str(uuid4())
    expected = _summary_payload(location_id)
    monkeypatch.setattr(
        "services.gateway.pollinator_health_reads.get_location_pollinator_summary",
        lambda _operator, scoped_location: expected
        if scoped_location == location_id
        else None,
    )

    with TestClient(_route_app(object())) as client:
        response = client.get(f"/operator/api/pollinators/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


@pytest.mark.parametrize(
    "invalid_field",
    [
        "top_level_extra",
        "nested_extra",
        "unknown_type",
        "negative_count",
        "missing_risk_key",
        "non_finite",
        "group_limit",
        "location_mismatch",
    ],
)
def test_pollinator_summary_rejects_invalid_service_projection(
    monkeypatch, invalid_field
):
    location_id = str(uuid4())
    payload = deepcopy(_summary_payload(location_id))
    if invalid_field == "top_level_extra":
        payload["private_source_ids"] = [str(uuid4())]
    elif invalid_field == "nested_extra":
        payload["verified_observations"][0]["notes"] = "private"
    elif invalid_field == "unknown_type":
        payload["habitat_inventory"][0]["habitat_type"] = "unknown"
    elif invalid_field == "negative_count":
        payload["active_hive_summary"]["total_hives"] = -1
    elif invalid_field == "missing_risk_key":
        del payload["pesticide_risk_summary"]["risk_distribution"]["unknown"]
    elif invalid_field == "non_finite":
        payload["observation_trends"][0]["change_pct"] = float("nan")
    elif invalid_field == "group_limit":
        payload["verified_observations"] = [
            deepcopy(payload["verified_observations"][0]) for _ in range(109)
        ]
    else:
        payload["location_id"] = str(uuid4())
    monkeypatch.setattr(
        "services.gateway.pollinator_health_reads.get_location_pollinator_summary",
        lambda *_args, **_kwargs: payload,
    )

    with TestClient(_route_app(object())) as client:
        response = client.get(f"/operator/api/pollinators/{location_id}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "Pollinator summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


class _SyntheticDatabaseError(Exception):
    pass


@pytest.mark.parametrize(
    ("provider", "error", "status_code", "body", "retry_after"),
    [
        (None, None, 404, {"error": "Operator OIDC is disabled"}, None),
        (
            object(), TenantContextDenied("revoked"), 403,
            {"error": "Tenant-qualified operator access is required"}, None,
        ),
        (
            object(), ValueError("Invalid operator or location identifier"), 400,
            {"error": "Invalid operator or location identifier"}, None,
        ),
        (
            object(), _SyntheticDatabaseError("failure"), 503,
            {"error": "Pollinator summary unavailable"}, "30",
        ),
    ],
)
def test_pollinator_summary_preserves_existing_error_contract(
    monkeypatch, provider, error, status_code, body, retry_after
):
    if error is not None:
        def fail_summary(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(
            "services.gateway.pollinator_health_reads.get_location_pollinator_summary",
            fail_summary,
        )
    with TestClient(
        _route_app(provider, _SyntheticDatabaseError)
    ) as client:
        response = client.get(f"/operator/api/pollinators/{uuid4()}/summary")

    assert response.status_code == status_code
    assert response.json() == body
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    if retry_after is None:
        assert "retry-after" not in response.headers
    else:
        assert response.headers["retry-after"] == retry_after
