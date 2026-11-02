"""Strict response-contract checks for location-scoped solution experiments."""

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


def _experiment(
    experiment_id="f0000000-0000-4000-8000-000000000001",
    created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
):
    return {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "solution_name": "Soil cover",
        "solution_type": "practice",
        "current_stage": "testing",
        "solution_status": "active",
        "experiment_id": experiment_id,
        "protocol_version": "v2",
        "experiment_status": "completed",
        "duration_days": 42,
        "primary_metric_count": 2,
        "secondary_metric_count": 1,
        "experiment_created_at": created_at,
        "experiment_updated_at": datetime(2026, 10, 19, tzinfo=timezone.utc),
        "started_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 10, 18, tzinfo=timezone.utc),
        "latest_result_outcome": "validated",
        "latest_result_reviewed_at": datetime(2026, 10, 19, tzinfo=timezone.utc),
    }


def _page(**overrides):
    return {
        "location_id": LOCATION_ID,
        "offset": 3,
        "experiments": [_experiment()],
        "has_more": False,
        "next_offset": None,
        **overrides,
    }


def _app(monkeypatch, result, *, provider=object()):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_experiments",
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


def test_experiments_route_publishes_strict_openapi_projection(monkeypatch):
    app = _app(monkeypatch, _page())
    openapi = app.openapi()
    route = "/operator/api/solution-lifecycle/{location_id}/experiments"
    operation = openapi["paths"][route]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema["$ref"].endswith("/SolutionLifecycleExperimentPageResponse")

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
    page_schema = schemas["SolutionLifecycleExperimentPageResponse"]
    assert set(page_schema["properties"]) == {
        "location_id", "offset", "experiments", "has_more", "next_offset"
    }
    assert set(page_schema["required"]) == set(page_schema["properties"])
    assert page_schema["additionalProperties"] is False
    item_schema = schemas["SolutionLifecycleExperimentItemResponse"]
    assert set(item_schema["properties"]) == {
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "experiment_id", "protocol_version", "experiment_status",
        "duration_days", "primary_metric_count", "secondary_metric_count",
        "experiment_created_at", "experiment_updated_at", "started_at", "completed_at",
        "latest_result_outcome", "latest_result_reviewed_at",
    }
    assert set(item_schema["required"]) == set(item_schema["properties"])
    assert item_schema["additionalProperties"] is False


def test_experiments_route_returns_request_bound_private_page(monkeypatch):
    result = _page()
    app = _app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "2", "offset": "3"})

    expected_experiment = _experiment()
    for key in (
        "experiment_created_at", "experiment_updated_at", "started_at", "completed_at",
        "latest_result_reviewed_at",
    ):
        expected_experiment[key] = expected_experiment[key].isoformat()
    assert response.status_code == 200
    assert response.json() == {
        "location_id": LOCATION_ID,
        "offset": 3,
        "experiments": [expected_experiment],
        "has_more": False,
        "next_offset": None,
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def _wrong_location(page):
    page["location_id"] = OTHER_LOCATION_ID


def _wrong_offset(page):
    page["offset"] = 2


def _missing_field(page):
    del page["experiments"][0]["protocol_version"]


def _extra_private_field(page):
    page["experiments"][0]["evidence"] = ["must not leak"]


def _invalid_status(page):
    page["experiments"][0]["experiment_status"] = "unknown"


def _invalid_duration(page):
    page["experiments"][0]["duration_days"] = 0


def _invalid_metric_count(page):
    page["experiments"][0]["primary_metric_count"] = "2"


def _latest_result_mismatch(page):
    page["experiments"][0]["latest_result_reviewed_at"] = None


def _out_of_order(page):
    page.update(
        experiments=[
            _experiment(created_at=datetime(2026, 10, 17, tzinfo=timezone.utc)),
            _experiment(
                "f0000000-0000-4000-8000-000000000002",
                datetime(2026, 10, 19, tzinfo=timezone.utc),
            ),
        ],
        has_more=True,
        next_offset=5,
    )


def _tie_break_order(page):
    page.update(
        experiments=[
            _experiment("f0000000-0000-4000-8000-000000000002"),
            _experiment("f0000000-0000-4000-8000-000000000001"),
        ],
        has_more=True,
        next_offset=5,
    )


def _duplicate_experiment(page):
    page.update(experiments=[_experiment(), _experiment()], has_more=True, next_offset=5)


def _over_limit(page):
    page.update(
        experiments=[
            _experiment("f0000000-0000-4000-8000-000000000001"),
            _experiment("f0000000-0000-4000-8000-000000000002"),
            _experiment("f0000000-0000-4000-8000-000000000003"),
        ],
        has_more=True,
        next_offset=5,
    )


def _bad_continuation(page):
    page.update(has_more=True, next_offset=4)


def _extra_page_field(page):
    page["unexpected"] = True


@pytest.mark.parametrize(
    "mutate,query",
    [
        (_wrong_location, {"limit": "2", "offset": "3"}),
        (_wrong_offset, {"limit": "2", "offset": "3"}),
        (_missing_field, {"limit": "2", "offset": "3"}),
        (_extra_private_field, {"limit": "2", "offset": "3"}),
        (_invalid_status, {"limit": "2", "offset": "3"}),
        (_invalid_duration, {"limit": "2", "offset": "3"}),
        (_invalid_metric_count, {"limit": "2", "offset": "3"}),
        (_latest_result_mismatch, {"limit": "2", "offset": "3"}),
        (_out_of_order, {"limit": "2", "offset": "3"}),
        (_tie_break_order, {"limit": "2", "offset": "3"}),
        (_duplicate_experiment, {"limit": "2", "offset": "3"}),
        (_over_limit, {"limit": "2", "offset": "3"}),
        (_bad_continuation, {"limit": "2", "offset": "3"}),
        (_extra_page_field, {"limit": "2", "offset": "3"}),
    ],
    ids=[
        "wrong-location", "wrong-offset", "missing-field", "extra-private-field",
        "invalid-status", "invalid-duration", "invalid-metric-count",
        "latest-result-mismatch", "out-of-order", "tie-break-order", "duplicate-id",
        "over-limit-page", "bad-continuation", "extra-page-field",
    ],
)
def test_experiments_route_rejects_malformed_projection_with_generic_no_store(
    monkeypatch, mutate, query
):
    result = _page()
    mutate(result)
    app = _app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments"
    with TestClient(app) as client:
        response = client.get(path, params=query)

    assert response.status_code == 500
    assert response.json() == {
        "error": "Solution lifecycle experiments unavailable"
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_experiments_route_preserves_scope_and_oidc_fail_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments"
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
