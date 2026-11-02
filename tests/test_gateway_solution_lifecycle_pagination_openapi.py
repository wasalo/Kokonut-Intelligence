"""OpenAPI and pre-service bounds for solution-lifecycle list routes."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "00000000-0000-4000-8000-000000000001"
_SPECIAL_LIMITS = {
    "/operator/api/solution-lifecycle/{location_id}/adoption/programs/drafts": (10, 25),
    "/operator/api/solution-lifecycle/{location_id}/adoption/programs/redesigns": (25, 50),
    "/operator/api/solution-lifecycle/{location_id}/adoption/programs/review-queue": (10, 25),
    "/operator/api/solution-lifecycle/{location_id}/adoption/readiness/review-queue": (25, 100),
    "/operator/api/solution-lifecycle/{location_id}/adoption/configurations/drafts": (10, 25),
    "/operator/api/solution-lifecycle/{location_id}/adoption/configurations/review-queue": (10, 25),
}


def _app():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid pagination must be rejected before service invocation")

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app = FastAPI()
    app.include_router(router)
    return app


def _pagination_routes(openapi):
    routes = []
    for path, operations in openapi["paths"].items():
        operation = operations.get("get")
        if operation is None:
            continue
        parameters = {parameter["name"]: parameter for parameter in operation.get("parameters", [])}
        if "limit" in parameters:
            routes.append((path, parameters))
    return routes


def test_solution_lifecycle_list_routes_publish_reader_bounds():
    routes = _pagination_routes(_app().openapi())

    assert len(routes) == 25
    for path, parameters in routes:
        default_limit, maximum = _SPECIAL_LIMITS.get(path, (25, 50))
        assert parameters["limit"]["schema"] == {
            "type": "integer",
            "minimum": 1,
            "maximum": maximum,
            "default": default_limit,
            "title": "Limit",
        }
        assert parameters["offset"]["schema"] == {
            "type": "integer",
            "minimum": 0,
            "maximum": 10000,
            "default": 0,
            "title": "Offset",
        }


@pytest.mark.parametrize("query", [{"limit": "0"}, {"limit": "101"}, {"offset": "-1"}])
def test_solution_lifecycle_list_routes_reject_bad_pages_before_service(query):
    app = _app()
    routes = _pagination_routes(app.openapi())
    with TestClient(app) as client:
        for path, _parameters in routes:
            request_path = path.replace("{location_id}", LOCATION_ID)
            response = client.get(request_path, params=query)
            assert response.status_code == 422, (path, query, response.text)
