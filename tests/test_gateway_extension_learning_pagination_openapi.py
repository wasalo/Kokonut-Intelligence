"""Route-level pagination bounds for extension-learning list reads."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _app(monkeypatch, calls):
    from services.gateway.extension_learning_routes import register_extension_learning_routes

    def list_modules(*args, **kwargs):
        calls.append((args, kwargs))
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.list_location_extension_modules",
        list_modules,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_extension_learning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_extension_learning_pagination_is_bounded_in_openapi(monkeypatch):
    calls = []
    app = _app(monkeypatch, calls)

    operation = app.openapi()["paths"]["/operator/api/extension-learning/{location_id}/modules"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["limit"]["schema"] == {
        "type": "integer",
        "maximum": 50,
        "minimum": 1,
        "default": 25,
        "title": "Limit",
    }
    assert parameters["offset"]["schema"] == {
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
def test_extension_learning_invalid_pagination_fails_before_service(monkeypatch, query):
    calls = []
    app = _app(monkeypatch, calls)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/extension-learning/{LOCATION_ID}/modules?{query}"
        )

    assert response.status_code == 422
    assert calls == []
