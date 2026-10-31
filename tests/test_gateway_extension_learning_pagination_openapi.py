"""Route-level pagination bounds for extension-learning list reads."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _app(monkeypatch, calls, response=None):
    from services.gateway.extension_learning_routes import register_extension_learning_routes

    def list_modules(operator_id, location_id, **kwargs):
        calls.append(((operator_id, location_id), kwargs))
        page = {
            "location_id": location_id,
            "items": [],
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
            "has_more": False,
        }
        return response(page) if response is not None else page

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


def _module_item():
    return {
        "id": "33333333-3333-4333-8333-333333333333",
        "module_name": "Compost",
        "category": "soil_health",
        "difficulty": "beginner",
        "content_type": "guide",
        "duration_minutes": 20,
        "language": "en",
    }


def test_extension_learning_route_accepts_request_bound_final_page(monkeypatch):
    calls = []
    app = _app(monkeypatch, calls)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/extension-learning/{LOCATION_ID}/modules",
            params={"limit": 1, "offset": 10_000},
        )

    assert response.status_code == 200
    assert response.json() == {
        "location_id": LOCATION_ID,
        "items": [],
        "limit": 1,
        "offset": 10_000,
        "has_more": False,
    }
    assert calls == [
        ((OPERATOR_ID, LOCATION_ID), {
            "category": None,
            "difficulty": None,
            "content_type": None,
            "limit": 1,
            "offset": 10_000,
        })
    ]


@pytest.mark.parametrize(
    ("query", "corruption"),
    [
        ("", "location"),
        ("", "limit"),
        ("", "offset"),
        ("limit=1", "oversized_items"),
        ("", "non_boolean_has_more"),
        ("", "short_continuation_page"),
        ("limit=1&offset=10000", "unreachable_continuation"),
    ],
)
def test_extension_learning_route_rejects_unbound_or_malformed_pages(
    monkeypatch, query, corruption
):
    calls = []

    def corrupt(page):
        if corruption == "location":
            page["location_id"] = "44444444-4444-4444-8444-444444444444"
        elif corruption == "limit":
            page["limit"] += 1
        elif corruption == "offset":
            page["offset"] += 1
        elif corruption == "oversized_items":
            page["items"] = [_module_item(), _module_item()]
        elif corruption == "non_boolean_has_more":
            page["has_more"] = 1
        elif corruption == "short_continuation_page":
            page["has_more"] = True
        else:
            page["items"] = [_module_item()]
            page["has_more"] = True
        return page

    app = _app(monkeypatch, calls, response=corrupt)
    suffix = f"?{query}" if query else ""
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/extension-learning/{LOCATION_ID}/modules{suffix}"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Extension module catalog unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert len(calls) == 1


def test_extension_learning_query_validation_response_is_private(monkeypatch):
    from services.gateway.app import create_app

    operator_id = OPERATOR_ID
    session = SimpleNamespace(
        session_id="test-session",
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    class Provider:
        settings = SimpleNamespace(state_secret="synthetic-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, scoped_operator, resource, action, location_id):
            return (
                scoped_operator == operator_id
                and resource == "extension_learning"
                and action == "read"
                and location_id == LOCATION_ID
            )

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())

    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject invalid pagination before service access")

    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.list_location_extension_modules",
        unexpected_service,
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/extension-learning/{LOCATION_ID}/modules?limit=0"
        )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }
    assert response.json()["detail"][0]["loc"] == ["query", "limit"]
