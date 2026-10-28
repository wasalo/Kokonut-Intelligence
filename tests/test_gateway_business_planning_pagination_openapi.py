"""Business-planning Gateway pagination is bounded at the HTTP boundary."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402


def _app(monkeypatch):
    from services.gateway.business_planning_routes import register_business_planning_routes

    location_id = str(uuid4())
    calls = []

    def reader(*_args, **_kwargs):
        calls.append(True)
        return {"location_id": location_id, "canvases": []}

    monkeypatch.setattr(
        "services.gateway.business_planning_reads.list_location_business_model_canvases",
        reader,
    )

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    app = FastAPI()
    router = APIRouter()
    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=str(uuid4()))
        )
        return await call_next(request)

    return app, location_id, calls


def test_business_planning_canvas_list_publishes_service_bounds(monkeypatch):
    app, location_id, calls = _app(monkeypatch)
    schema = app.openapi()["paths"]["/operator/api/business-planning/{location_id}/canvases"]["get"]
    parameters = {parameter["name"]: parameter for parameter in schema["parameters"]}

    assert parameters["limit"]["schema"]["default"] == 25
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["default"] == 0
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000

    with TestClient(app) as client:
        response = client.get(f"/operator/api/business-planning/{location_id}/canvases")

    assert response.status_code == 200
    assert calls == [True]


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=51", "offset=-1", "offset=10001"],
)
def test_business_planning_canvas_list_rejects_invalid_pagination_before_reader(monkeypatch, query):
    app, location_id, calls = _app(monkeypatch)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/business-planning/{location_id}/canvases?{query}")

    assert response.status_code == 422
    assert calls == []
