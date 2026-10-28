"""Route-level pagination bounds for the stakeholder identity review queue."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _app(monkeypatch, calls):
    from services.gateway.stakeholder_identity_routes import register_stakeholder_identity_routes

    def list_cases(*args, **kwargs):
        calls.append((args, kwargs))
        return {"location_id": LOCATION_ID, "items": [], "next_cursor": None}

    monkeypatch.setattr(
        "services.gateway.stakeholder_identity.list_location_party_identity_cases",
        list_cases,
    )
    import psycopg2

    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_stakeholder_identity_routes(router, object(), run_in_threadpool, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_stakeholder_identity_limit_is_bounded_in_openapi(monkeypatch):
    calls = []
    app = _app(monkeypatch, calls)

    operation = app.openapi()["paths"]["/operator/api/stakeholder-identity/{location_id}/cases"]["get"]
    limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")

    assert limit["schema"] == {
        "type": "integer",
        "maximum": 50,
        "minimum": 1,
        "default": 50,
        "title": "Limit",
    }


@pytest.mark.parametrize("limit", [0, 51])
def test_invalid_limit_fails_before_service_access(monkeypatch, limit):
    calls = []
    app = _app(monkeypatch, calls)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            params={"limit": limit},
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "limit"]
    assert calls == []
