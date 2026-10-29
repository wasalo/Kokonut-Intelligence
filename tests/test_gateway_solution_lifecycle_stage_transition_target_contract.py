"""Strict contract checks for location-scoped stage-transition targets."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.operator_auth import auth_route_policy

LOCATION_ID = "00000000-0000-4000-8000-000000000001"
OTHER_LOCATION_ID = "00000000-0000-4000-8000-000000000002"
OPERATOR_ID = "00000000-0000-4000-8000-000000000003"


def _solution(solution_id="00000000-0000-4000-8000-000000000004"):
    return {
        "solution_id": solution_id,
        "solution_name": "Soil cover",
        "solution_type": "practice",
        "current_stage": "testing",
        "solution_status": "active",
        "updated_at": datetime(2026, 10, 20, tzinfo=timezone.utc),
    }


def _page(**overrides):
    return {
        "location_id": LOCATION_ID,
        "offset": 3,
        "solutions": [_solution()],
        "has_more": False,
        "next_offset": None,
        **overrides,
    }


def _app(monkeypatch, result, *, provider=object()):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_stage_transition_targets",
        result if callable(result) else lambda *_args, **_kwargs: result,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
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


def test_stage_transition_target_route_publishes_strict_openapi_contract(monkeypatch):
    app = _app(monkeypatch, _page())
    openapi = app.openapi()
    operation = openapi["paths"][
        "/operator/api/solution-lifecycle/{location_id}/stage-transition-targets"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema["$ref"].endswith(
        "/SolutionLifecycleStageTransitionTargetPageResponse"
    )

    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000

    schemas = openapi["components"]["schemas"]
    page_schema = schemas["SolutionLifecycleStageTransitionTargetPageResponse"]
    assert set(page_schema["properties"]) == {
        "location_id", "offset", "solutions", "has_more", "next_offset"
    }
    assert page_schema["additionalProperties"] is False
    item_schema = schemas["SolutionLifecycleStageTransitionTargetItemResponse"]
    assert set(item_schema["properties"]) == {
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "updated_at",
    }
    assert item_schema["additionalProperties"] is False


def test_stage_transition_target_route_returns_bound_private_page(monkeypatch):
    app = _app(monkeypatch, _page())
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/stage-transition-targets"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "5", "offset": "3"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == {
        "location_id": LOCATION_ID,
        "offset": 3,
        "solutions": [
            {
                **_solution(),
                "updated_at": "2026-10-20T00:00:00+00:00",
            }
        ],
        "has_more": False,
        "next_offset": None,
    }


@pytest.mark.parametrize(
    "result,query",
    [
        (_page(location_id=OTHER_LOCATION_ID), {"limit": "5", "offset": "3"}),
        (_page(offset=2), {"limit": "5", "offset": "3"}),
        (
            _page(has_more=True, next_offset=4),
            {"limit": "2", "offset": "3"},
        ),
        (
            _page(
                solutions=[_solution(), _solution("00000000-0000-4000-8000-000000000005")],
                has_more=True,
                next_offset=4,
            ),
            {"limit": "1", "offset": "3"},
        ),
        (_page(surprise="private"), {"limit": "5", "offset": "3"}),
        (
            _page(solutions=[{**_solution(), "current_stage": "unknown"}]),
            {"limit": "5", "offset": "3"},
        ),
        (
            _page(
                solutions=[_solution(), _solution()],
                has_more=True,
                next_offset=5,
            ),
            {"limit": "2", "offset": "3"},
        ),
    ],
    ids=[
        "wrong-location", "wrong-offset", "wrong-continuation", "over-limit-page",
        "extra-page-field", "invalid-stage", "duplicate-solution",
    ],
)
def test_stage_transition_target_route_rejects_malformed_projection_no_store(
    monkeypatch, result, query
):
    app = _app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/stage-transition-targets"
    with TestClient(app) as client:
        response = client.get(path, params=query)

    assert response.status_code == 500
    assert response.json() == {
        "error": "Solution stage-transition targets unavailable"
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_stage_transition_target_route_preserves_location_grant_and_oidc_behavior(
    monkeypatch,
):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/stage-transition-targets"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }

    def denied(*_args, **_kwargs):
        raise TenantContextDenied("private detail")

    app = _app(monkeypatch, denied)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": "Tenant-qualified solution lifecycle access is required"
    }

    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, None, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    disabled = FastAPI()
    disabled.include_router(router)
    with TestClient(disabled) as client:
        response = client.get(path)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
