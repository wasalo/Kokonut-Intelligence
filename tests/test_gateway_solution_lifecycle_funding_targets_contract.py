"""Strict response-contract checks for solution funding targets."""

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


def _solution(solution_id="00000000-0000-4000-8000-000000000004", **overrides):
    return {
        "solution_id": solution_id,
        "solution_name": "Soil restoration",
        "solution_type": "practice",
        "current_stage": "testing",
        "solution_status": "active",
        **overrides,
    }


def _page(**overrides):
    return {
        "location_id": LOCATION_ID,
        "offset": 5,
        "solutions": [_solution()],
        "has_more": False,
        "next_offset": None,
        **overrides,
    }


def _app(monkeypatch, reader, *, provider=object()):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_funding_targets",
        reader if callable(reader) else lambda *_args, **_kwargs: reader,
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


def test_funding_targets_route_publishes_strict_openapi_contract(monkeypatch):
    app = _app(monkeypatch, _page())
    openapi = app.openapi()
    route = "/operator/api/solution-lifecycle/{location_id}/funding/targets"
    operation = openapi["paths"][route]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema["$ref"].endswith(
        "/SolutionLifecycleFundingTargetsPageResponse"
    )
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"] == {
        "type": "integer", "minimum": 1, "maximum": 50,
        "default": 25, "title": "Limit",
    }
    assert parameters["offset"]["schema"] == {
        "type": "integer", "minimum": 0, "maximum": 10000,
        "default": 0, "title": "Offset",
    }

    schemas = openapi["components"]["schemas"]
    page_schema = schemas["SolutionLifecycleFundingTargetsPageResponse"]
    assert set(page_schema["properties"]) == {
        "location_id", "offset", "solutions", "has_more", "next_offset"
    }
    assert set(page_schema["required"]) == set(page_schema["properties"])
    assert page_schema["additionalProperties"] is False
    item_schema = schemas["SolutionLifecycleFundingTargetItemResponse"]
    assert set(item_schema["properties"]) == {
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status",
    }
    assert set(item_schema["required"]) == set(item_schema["properties"])
    assert item_schema["additionalProperties"] is False


def test_funding_targets_route_returns_location_and_page_bound_no_store_response(monkeypatch):
    calls = []

    def reader(*args, **kwargs):
        calls.append((args, kwargs))
        return _page()

    app = _app(monkeypatch, reader)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/targets"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "2", "offset": "5"})

    assert response.status_code == 200
    assert response.json() == _page()
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 5})]


def _wrong_location(page):
    page["location_id"] = OTHER_LOCATION_ID


def _wrong_offset(page):
    page["offset"] = 4


def _missing_field(page):
    del page["solutions"][0]["solution_type"]


def _extra_field(page):
    page["solutions"][0]["funding_rationale"] = "private"


def _invalid_type(page):
    page["solutions"][0]["solution_type"] = "unknown"


def _invalid_stage(page):
    page["solutions"][0]["current_stage"] = "unknown"


def _invalid_status(page):
    page["solutions"][0]["solution_status"] = "draft"


def _overlong_name(page):
    page["solutions"][0]["solution_name"] = "s" * 256


def _over_limit(page):
    page.update(
        solutions=[
            _solution("00000000-0000-4000-8000-000000000004"),
            _solution("00000000-0000-4000-8000-000000000005"),
            _solution("00000000-0000-4000-8000-000000000006"),
        ],
        has_more=True,
        next_offset=7,
    )


def _bad_continuation(page):
    page.update(has_more=True, next_offset=6)


def _duplicate_solution(page):
    page.update(solutions=[_solution(), _solution()], has_more=True, next_offset=7)


def _name_tie_break_order(page):
    page.update(
        solutions=[
            _solution("00000000-0000-4000-8000-000000000005"),
            _solution("00000000-0000-4000-8000-000000000004"),
        ],
        has_more=True,
        next_offset=7,
    )


def _extra_page_field(page):
    page["unexpected"] = True


@pytest.mark.parametrize(
    "mutate,query",
    [
        (_wrong_location, {"limit": "2", "offset": "5"}),
        (_wrong_offset, {"limit": "2", "offset": "5"}),
        (_missing_field, {"limit": "2", "offset": "5"}),
        (_extra_field, {"limit": "2", "offset": "5"}),
        (_invalid_type, {"limit": "2", "offset": "5"}),
        (_invalid_stage, {"limit": "2", "offset": "5"}),
        (_invalid_status, {"limit": "2", "offset": "5"}),
        (_overlong_name, {"limit": "2", "offset": "5"}),
        (_over_limit, {"limit": "2", "offset": "5"}),
        (_bad_continuation, {"limit": "2", "offset": "5"}),
        (_duplicate_solution, {"limit": "2", "offset": "5"}),
        (_name_tie_break_order, {"limit": "2", "offset": "5"}),
        (_extra_page_field, {"limit": "2", "offset": "5"}),
    ],
    ids=[
        "wrong-location", "wrong-offset", "missing-field", "private-field",
        "invalid-type", "invalid-stage", "invalid-status", "overlong-name",
        "over-limit-page", "bad-continuation", "duplicate-solution-id",
        "same-name-id-order", "extra-page-field",
    ],
)
def test_funding_targets_route_fails_closed_on_malformed_projection(
    monkeypatch, mutate, query
):
    result = _page()
    mutate(result)
    app = _app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/targets"
    with TestClient(app) as client:
        response = client.get(path, params=query)

    assert response.status_code == 500
    assert response.json() == {"error": "Solution funding targets unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_funding_targets_route_preserves_tenant_and_oidc_denials(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/targets"
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
    assert response.json() == {
        "error": "Tenant-qualified solution lifecycle access is required"
    }
    assert response.headers["cache-control"] == "no-store"

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
