"""Pollinator Gateway page bounds are documented and rejected pre-service."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import pollinator_health_reads, pollinator_health_routes

_LOCATION = "22222222-2222-4222-8222-222222222222"
_OPERATOR = "11111111-1111-4111-8111-111111111111"

_ROUTES = {
    "/operator/api/pollinators/{location_id}/review-queue": (25, 50),
    "/operator/api/pollinators/{location_id}/habitats": (50, 50),
    "/operator/api/pollinators/{location_id}/hives": (50, 50),
}


def _client(monkeypatch, called):
    import psycopg2

    def record(*_args, **_kwargs):
        called.append(True)
        return {}

    monkeypatch.setattr(pollinator_health_reads, "list_location_pollinator_review_queue", record)
    monkeypatch.setattr(pollinator_health_reads, "get_location_pollinator_habitat_details", record)
    monkeypatch.setattr(pollinator_health_reads, "get_location_pollinator_hive_details", record)

    app = FastAPI()

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    router = APIRouter()
    pollinator_health_routes.register_pollinator_health_routes(
        router, provider=object(), run_in_threadpool=run_in_threadpool, psycopg2=psycopg2
    )
    app.include_router(router)
    return TestClient(app), app


@pytest.mark.parametrize(
    "path,default_limit,max_limit",
    [(path, *bounds) for path, bounds in _ROUTES.items()],
)
def test_pollinator_list_openapi_publishes_service_page_bounds(monkeypatch, path, default_limit, max_limit):
    client, app = _client(monkeypatch, [])
    del client

    operation = app.openapi()["paths"][path]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    limit = parameters["limit"]["schema"]
    offset = parameters["offset"]["schema"]

    assert limit["default"] == default_limit
    assert limit["minimum"] == 1
    assert limit["maximum"] == max_limit
    assert offset["default"] == 0
    assert offset["minimum"] == 0
    assert offset["maximum"] == 10000


@pytest.mark.parametrize(
    "route,invalid_query",
    [
        ("review-queue", {"limit": 0}),
        ("review-queue", {"limit": 51}),
        ("review-queue", {"offset": -1}),
        ("review-queue", {"offset": 10001}),
        ("habitats", {"limit": 0}),
        ("habitats", {"limit": 51}),
        ("habitats", {"offset": -1}),
        ("habitats", {"offset": 10001}),
        ("hives", {"limit": 0}),
        ("hives", {"limit": 51}),
        ("hives", {"offset": -1}),
        ("hives", {"offset": 10001}),
    ],
)
def test_pollinator_list_rejects_invalid_page_before_service(monkeypatch, route, invalid_query):
    called = []
    client, _app = _client(monkeypatch, called)

    response = client.get(
        f"/operator/api/pollinators/{_LOCATION}/{route}", params=invalid_query
    )

    assert response.status_code == 422
    assert called == []
