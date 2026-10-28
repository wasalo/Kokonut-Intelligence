"""The competitive-landscape route publishes and enforces its service page bounds."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _app(monkeypatch, calls):
    from services.gateway.competitive_landscape_routes import (
        register_competitive_landscape_routes,
    )

    def list_summaries(*args, **kwargs):
        calls.append((args, kwargs))
        return {"location_id": LOCATION_ID, "landscapes": [], "has_more": False}

    monkeypatch.setattr(
        "services.gateway.competitive_landscape_reads.list_location_competitive_landscape_summaries",
        list_summaries,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_competitive_landscape_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
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


def test_competitive_landscape_pagination_matches_reader_contract(monkeypatch):
    app = _app(monkeypatch, [])

    operation = app.openapi()["paths"][
        "/operator/api/competitive-landscape/{location_id}/summaries"
    ]["get"]
    parameters = {parameter["name"]: parameter["schema"] for parameter in operation["parameters"]}

    assert parameters["limit"] == {
        "type": "integer",
        "maximum": 50,
        "minimum": 1,
        "default": 25,
        "title": "Limit",
    }
    assert parameters["offset"] == {
        "type": "integer",
        "maximum": 10000,
        "minimum": 0,
        "default": 0,
        "title": "Offset",
    }


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=51", "offset=-1", "offset=10001"],
)
def test_invalid_competitive_landscape_page_fails_before_service(monkeypatch, query):
    calls = []
    app = _app(monkeypatch, calls)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/competitive-landscape/{LOCATION_ID}/summaries?{query}"
        )

    assert response.status_code == 422
    assert calls == []
