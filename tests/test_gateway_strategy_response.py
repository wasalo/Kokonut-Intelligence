"""Strict success response contract for location strategy plan reads."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.strategy_routes import register_strategy_routes  # noqa: E402


def _plan(plan_id=None):
    return {
        "strategy_plan_id": plan_id or str(uuid4()),
        "plan_name": "Water resilience strategy",
        "version": 2,
        "plan_status": "active",
        "visibility": "limited",
        "planning_horizon_start": date(2026, 1, 1),
        "planning_horizon_end": date(2030, 12, 31),
        "updated_at": datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
        "cascade_mode": "adapted",
        "cascade_status": "aligned",
        "has_parent_strategy": True,
        "objective_count": 4,
        "initiative_count": 6,
        "completed_initiative_count": 2,
        "investment_case_count": 3,
        "recommended_investment_count": 1,
        "open_coherence_finding_count": 1,
        "blocking_finding_count": 0,
        "structural_gate_status": "ready",
        "open_review_task_count": 2,
        "submitted_allocation_count": 1,
        "approved_allocation_count": 1,
    }


def _response(location_id, *, plans=None, offset=0, has_more=False, next_offset=None):
    return {
        "location_id": location_id,
        "offset": offset,
        "plans": [_plan()] if plans is None else plans,
        "has_more": has_more,
        "next_offset": next_offset,
    }


def _app(provider, db_error=RuntimeError):
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_strategy_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=db_error))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=str(uuid4()))
        )
        return await call_next(request)

    return app


def test_strategy_success_schema_is_published_and_bounded():
    app = _app(object())
    operation = app.openapi()["paths"][
        "/operator/api/strategy/{location_id}/plans"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/StrategyPlanListResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    for name in ("StrategyPlanListResponse", "StrategyPlanSummary"):
        assert schemas[name]["additionalProperties"] is False
    response_properties = schemas["StrategyPlanListResponse"]["properties"]
    assert response_properties["plans"]["maxItems"] == 50
    assert response_properties["offset"]["maximum"] == 10_000
    assert response_properties["next_offset"]["anyOf"][0]["maximum"] == 10_000
    plan_properties = schemas["StrategyPlanSummary"]["properties"]
    assert plan_properties["plan_status"]["enum"] == [
        "draft", "submitted", "approved", "active", "superseded", "retired"
    ]
    assert plan_properties["cascade_mode"]["enum"] == ["inherited", "adapted", "independent"]
    assert plan_properties["structural_gate_status"]["enum"] == ["ready", "blocked"]


def test_strategy_route_returns_only_the_validated_projection(monkeypatch):
    location_id = str(uuid4())
    payload = _response(location_id)
    monkeypatch.setattr(
        "services.gateway.strategy_reads.list_location_strategy_plan_summaries",
        lambda *_args, **_kwargs: payload,
    )
    with TestClient(_app(object())) as client:
        response = client.get(f"/operator/api/strategy/{location_id}/plans")

    assert response.status_code == 200
    body = response.json()
    assert body["location_id"] == location_id
    assert body["plans"][0]["strategy_plan_id"] == payload["plans"][0]["strategy_plan_id"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    ("offset", "has_more", "next_offset"),
    [(9_999, True, 10_000), (10_000, False, None)],
)
def test_strategy_route_accepts_only_reachable_boundary_continuations(
    monkeypatch, offset, has_more, next_offset
):
    location_id = str(uuid4())
    payload = _response(
        location_id,
        offset=offset,
        has_more=has_more,
        next_offset=next_offset,
    )
    monkeypatch.setattr(
        "services.gateway.strategy_reads.list_location_strategy_plan_summaries",
        lambda *_args, **_kwargs: payload,
    )
    with TestClient(_app(object())) as client:
        response = client.get(
            f"/operator/api/strategy/{location_id}/plans",
            params={"limit": 1, "offset": offset},
        )

    assert response.status_code == 200
    assert response.json()["next_offset"] == next_offset
    assert response.json()["has_more"] is has_more


@pytest.mark.parametrize(
    "invalid_field",
    [
        "top_level_extra",
        "nested_extra",
        "unknown_status",
        "negative_count",
        "boolean_count",
        "naive_timestamp",
        "reversed_horizon",
        "location_mismatch",
        "offset_mismatch",
        "pagination_mismatch",
        "next_offset_out_of_range",
        "oversized_page",
    ],
)
def test_strategy_route_rejects_invalid_projection_with_private_error(monkeypatch, invalid_field):
    location_id = str(uuid4())
    payload = _response(location_id)
    if invalid_field == "top_level_extra":
        payload["execution_authorized"] = True
    elif invalid_field == "nested_extra":
        payload["plans"][0]["diagnosis_summary"] = "private text"
    elif invalid_field == "unknown_status":
        payload["plans"][0]["plan_status"] = "published"
    elif invalid_field == "negative_count":
        payload["plans"][0]["initiative_count"] = -1
    elif invalid_field == "boolean_count":
        payload["plans"][0]["objective_count"] = True
    elif invalid_field == "naive_timestamp":
        payload["plans"][0]["updated_at"] = datetime(2026, 10, 19, 12, 0)
    elif invalid_field == "reversed_horizon":
        payload["plans"][0]["planning_horizon_start"] = date(2031, 1, 1)
    elif invalid_field == "location_mismatch":
        payload["location_id"] = str(uuid4())
    elif invalid_field == "offset_mismatch":
        payload["offset"] = 1
    elif invalid_field == "pagination_mismatch":
        payload["has_more"] = True
    elif invalid_field == "next_offset_out_of_range":
        payload["has_more"] = True
        payload["next_offset"] = 10_001
    else:
        payload["plans"] = [_plan() for _ in range(51)]

    monkeypatch.setattr(
        "services.gateway.strategy_reads.list_location_strategy_plan_summaries",
        lambda *_args, **_kwargs: payload,
    )
    with TestClient(_app(object())) as client:
        response = client.get(f"/operator/api/strategy/{location_id}/plans")

    assert response.status_code == 500
    assert response.json() == {"error": "Strategy plan read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_strategy_database_failure_keeps_retry_contract(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("private database details")

    monkeypatch.setattr(
        "services.gateway.strategy_reads.list_location_strategy_plan_summaries", fail
    )
    location_id = str(uuid4())
    with TestClient(_app(object())) as client:
        response = client.get(f"/operator/api/strategy/{location_id}/plans")

    assert response.status_code == 503
    assert response.json() == {"error": "Strategy plan read unavailable"}
    assert response.headers["retry-after"] == "30"
    assert response.headers["cache-control"] == "no-store"


def test_strategy_disabled_oidc_remains_hidden():
    location_id = str(uuid4())
    with TestClient(_app(None)) as client:
        response = client.get(f"/operator/api/strategy/{location_id}/plans")

    assert response.status_code == 404
    assert response.json() == {"error": "Operator OIDC is disabled"}
    assert response.headers["cache-control"] == "no-store"
