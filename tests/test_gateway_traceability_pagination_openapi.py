"""The traceability list publishes and enforces its bounded page contract."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _route_app(location_id, page):
    from services.gateway.traceability_routes import register_traceability_routes

    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return page

    import psycopg2

    register_traceability_routes(router, object(), run_in_threadpool, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


@pytest.fixture
def isolated_gateway(monkeypatch):
    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    operator_id = str(uuid4())
    location_id = str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "traceability"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    return create_app(), location_id


def test_traceability_pagination_contract_is_visible_in_openapi(isolated_gateway):
    app, _location_id = isolated_gateway
    operation = app.openapi()["paths"]["/operator/api/traceability/{location_id}/batches"]["get"]
    parameters = {parameter["name"]: parameter["schema"] for parameter in operation["parameters"]}

    assert parameters["limit"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "default": 25,
        "title": "Limit",
    }
    assert parameters["offset"]["minimum"] == 0
    assert parameters["offset"]["maximum"] == 10_000
    assert parameters["offset"]["default"] == 0


@pytest.mark.parametrize(
    ("parameter", "value"),
    [("limit", 0), ("limit", 51), ("offset", -1), ("offset", 10_001)],
)
def test_invalid_traceability_page_is_rejected_before_service_access(
    monkeypatch, isolated_gateway, parameter, value
):
    app, location_id = isolated_gateway

    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject invalid pagination before service access")

    monkeypatch.setattr(
        "services.gateway.traceability.list_location_traceability_batches", unexpected_service
    )
    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/traceability/{location_id}/batches", params={parameter: value}
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", parameter]
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


def _batch_item(batch_id="55555555-5555-4555-8555-555555555555"):
    return {
        "id": batch_id,
        "batch_number": "PB-1",
        "crop_name": "plantain",
        "variety": None,
        "quantity": "12.5000",
        "unit": "kg",
        "harvest_date": "2026-10-28",
        "organic": True,
        "status": "active",
        "created_at": "2026-10-28T12:00:00+00:00",
    }


def test_traceability_accepts_request_bound_final_page(isolated_gateway):
    _gateway, location_id = isolated_gateway
    page = {
        "location_id": location_id,
        "items": [],
        "limit": 1,
        "offset": 10_000,
        "has_more": False,
    }
    app = _route_app(location_id, page)

    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/traceability/{location_id}/batches",
            params={"limit": 1, "offset": 10_000},
        )

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


@pytest.mark.parametrize(
    ("query", "corruption"),
    [
        ("", "location"),
        ("limit=1", "limit"),
        ("offset=5", "offset"),
        ("limit=1", "oversized_items"),
        ("", "non_boolean_has_more"),
        ("", "short_continuation_page"),
        ("limit=1&offset=10000", "unreachable_continuation"),
    ],
)
def test_traceability_rejects_unbound_or_malformed_pages(
    isolated_gateway, query, corruption
):
    _gateway, location_id = isolated_gateway
    page = {
        "location_id": location_id,
        "items": [],
        "limit": 1 if "limit=1" in query else 25,
        "offset": 5 if "offset=5" in query else 0,
        "has_more": False,
    }
    if corruption == "location":
        page["location_id"] = str(uuid4())
    elif corruption == "limit":
        page["limit"] = 2
    elif corruption == "offset":
        page["offset"] = 6
    elif corruption == "oversized_items":
        page["items"] = [_batch_item(), _batch_item("66666666-6666-4666-8666-666666666666")]
    elif corruption == "non_boolean_has_more":
        page["has_more"] = 1
    elif corruption == "short_continuation_page":
        page["has_more"] = True
    else:
        page["items"] = [_batch_item()]
        page["has_more"] = True
        page["limit"] = 1
        page["offset"] = 10_000
    app = _route_app(location_id, page)
    suffix = f"?{query}" if query else ""

    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/traceability/{location_id}/batches{suffix}"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Traceability batch list unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }
