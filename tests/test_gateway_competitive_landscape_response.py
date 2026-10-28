"""Strict OpenAPI and runtime contract for competitive-landscape reads."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.competitive_landscape_routes import (
    CompetitiveLandscapeSummaryPage,
)

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _summary():
    return {
        "landscape_id": str(uuid4()),
        "strategy_plan_id": str(uuid4()),
        "industry": "Regenerative agriculture",
        "geography": "Dominican Republic",
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 12, 31),
        "landscape_status": "verified",
        "confidence": "moderate",
        "updated_at": datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
        "actor_count": 4,
        "high_or_critical_actor_count": 1,
        "force_observation_count": 5,
        "average_force_pressure": 61.25,
        "worsening_force_count": 2,
        "signal_count": 3,
        "unreviewed_critical_signal_count": 1,
        "verified_advantage_count": 2,
        "average_verified_defensibility": 72.5,
        "verified_advantage_outcome_count": 1,
        "latest_verified_outcome_period_end": date(2026, 9, 30),
    }


def _app(monkeypatch, result=None, error=None, provider=object()):
    from services.gateway.competitive_landscape_routes import (
        register_competitive_landscape_routes,
    )

    def read(*_args, **_kwargs):
        if error:
            raise error
        return result if result is not None else {
            "location_id": LOCATION_ID,
            "offset": 0,
            "landscapes": [_summary()],
            "has_more": False,
            "next_offset": None,
        }

    monkeypatch.setattr(
        "services.gateway.competitive_landscape_reads.list_location_competitive_landscape_summaries",
        read,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_competitive_landscape_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_response_model_matches_source_projection_and_is_strict():
    payload = {
        "location_id": LOCATION_ID,
        "offset": 0,
        "landscapes": [_summary()],
        "has_more": False,
        "next_offset": None,
    }
    validated = CompetitiveLandscapeSummaryPage.model_validate(payload)
    assert len(validated.landscapes) == 1
    assert validated.landscapes[0].landscape_status == "verified"
    assert validated.landscapes[0].latest_verified_outcome_period_end == date(2026, 9, 30)

    with pytest.raises(ValueError):
        CompetitiveLandscapeSummaryPage.model_validate({**payload, "unreviewed": True})
    with pytest.raises(ValueError):
        CompetitiveLandscapeSummaryPage.model_validate(
            {**payload, "landscapes": [{**_summary(), "actor_names": ["private"]}]}
        )


def test_openapi_publishes_exact_success_response_contract(monkeypatch):
    app = _app(monkeypatch)
    operation = app.openapi()["paths"][
        "/operator/api/competitive-landscape/{location_id}/summaries"
    ]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["$ref"].endswith("/CompetitiveLandscapeSummaryPage")

    schemas = app.openapi()["components"]["schemas"]
    summary = schemas["CompetitiveLandscapeSummary"]["properties"]
    assert set(summary) == set(_summary())
    assert schemas["CompetitiveLandscapeSummary"]["additionalProperties"] is False
    assert schemas["CompetitiveLandscapeSummaryPage"]["additionalProperties"] is False


def test_valid_response_is_serialized_and_no_store(monkeypatch):
    app = _app(monkeypatch)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["landscapes"][0]["average_force_pressure"] == 61.25
    assert response.json()["landscapes"][0]["period_start"] == "2026-01-01"


def test_response_contract_allows_maximum_next_offset_but_rejects_past_it(monkeypatch):
    near_ceiling = {
        "location_id": LOCATION_ID,
        "offset": 9975,
        "landscapes": [],
        "has_more": True,
        "next_offset": 10000,
    }
    app = _app(monkeypatch, result=near_ceiling)
    with TestClient(app) as client:
        allowed = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries?limit=25&offset=9975"
        )
    assert allowed.status_code == 200
    assert allowed.json()["next_offset"] == 10000

    beyond_ceiling = {**near_ceiling, "next_offset": 10001}
    app = _app(monkeypatch, result=beyond_ceiling)
    with TestClient(app) as client:
        rejected = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries?limit=25&offset=9975"
        )
    assert rejected.status_code == 500
    assert rejected.json() == {"error": "Competitive landscape read unavailable"}


@pytest.mark.parametrize(
    "override",
    [
        {"location_id": "33333333-3333-4333-8333-333333333333"},
        {"has_more": True},
        {"landscapes": [{**_summary(), "confidence": "certain"}]},
        {"landscapes": [{**_summary(), "average_force_pressure": 101}]},
        {"landscapes": [{**_summary(), "actor_names": ["private"]}]},
    ],
)
def test_invalid_response_fails_closed_without_leaking_projection(monkeypatch, override):
    result = {
        "location_id": LOCATION_ID,
        "offset": 0,
        "landscapes": [_summary()],
        "has_more": False,
        "next_offset": None,
        **override,
    }
    app = _app(monkeypatch, result=result)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Competitive landscape read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_existing_access_and_database_error_semantics_remain(monkeypatch):
    app = _app(monkeypatch, error=TenantContextDenied("denied"))
    with TestClient(app) as client:
        denied = client.get(f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries")
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "no-store"

    class DatabaseFailure(Exception):
        pgcode = "08006"

    app = _app(monkeypatch, error=DatabaseFailure("private details"))
    with TestClient(app) as client:
        unavailable = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries"
        )
    assert unavailable.status_code == 503
    assert unavailable.headers["retry-after"] == "30"
    assert unavailable.headers["cache-control"] == "no-store"
    assert "private details" not in unavailable.text

