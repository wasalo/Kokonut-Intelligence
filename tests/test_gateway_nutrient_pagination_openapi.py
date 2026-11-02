"""Nutrient list pagination is bounded and described in OpenAPI."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

PAGINATED_ROUTES = (
    (
        "/operator/api/nutrients/{location_id}/balances",
        "services.gateway.nutrient_balances.get_location_nutrient_balances",
    ),
    (
        "/operator/api/nutrients/{location_id}/soil-tests",
        "services.gateway.nutrient_soil_tests.get_location_soil_tests",
    ),
    (
        "/operator/api/nutrients/{location_id}/events/{event_type}",
        "services.gateway.nutrient_events.get_location_nutrient_events",
    ),
)


@pytest.fixture
def isolated_gateway(monkeypatch):
    operator_id = str(uuid4())
    location_id = str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "nutrient_budget"
                and action == "read"
                and scoped_location == location_id
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

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    return create_app(), location_id


@pytest.mark.parametrize("path_template, _service_path", PAGINATED_ROUTES)
def test_openapi_pagination_contract_matches_nutrient_service_limit(
    isolated_gateway, path_template, _service_path
):
    app, _location_id = isolated_gateway
    operation = app.openapi()["paths"][path_template]["get"]
    limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")
    offset = next(parameter for parameter in operation["parameters"] if parameter["name"] == "offset")

    assert limit["schema"]["type"] == "integer"
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 50
    assert limit["schema"]["default"] == 25
    assert offset["schema"]["type"] == "integer"
    assert offset["schema"]["minimum"] == 0
    assert offset["schema"]["maximum"] == 10_000
    assert offset["schema"]["default"] == 0


def test_openapi_declares_operator_cookie_only_on_authenticated_operations(
    isolated_gateway,
):
    app, _location_id = isolated_gateway
    schema = app.openapi()
    cookie_scheme = schema["components"]["securitySchemes"]["OperatorSessionCookie"]

    assert cookie_scheme == {
        "type": "apiKey",
        "in": "cookie",
        "name": "kokonut_operator_session",
        "description": "HTTP-only OIDC operator session cookie.",
    }
    for path, _service_path in PAGINATED_ROUTES:
        assert schema["paths"][path]["get"]["security"] == [
            {"OperatorSessionCookie": []}
        ]
    for path, path_item in schema["paths"].items():
        if path.startswith("/operator/api/"):
            for method, operation in path_item.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    assert operation["security"] == [
                        {"OperatorSessionCookie": []}
                    ]

    private_auth_operations = (
        ("/operator/auth/session", "get"),
        ("/operator/auth/logout", "post"),
    )
    for path, method in private_auth_operations:
        assert schema["paths"][path][method]["security"] == [
            {"OperatorSessionCookie": []}
        ]

    public_operations = (
        ("/operator/auth/login", "get"),
        ("/operator/auth/callback", "get"),
        ("/operator/", "get"),
        ("/api/drivers", "get"),
        ("/health", "get"),
    )
    for path, method in public_operations:
        assert "security" not in schema["paths"][path][method]


@pytest.mark.parametrize("path_template, service_path", PAGINATED_ROUTES)
@pytest.mark.parametrize("limit", [0, 51])
def test_invalid_limit_is_rejected_before_service_access(
    monkeypatch, isolated_gateway, path_template, service_path, limit
):
    app, location_id = isolated_gateway

    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject the limit before service/database access")

    monkeypatch.setattr(service_path, unexpected_service)
    path = path_template.replace("{location_id}", location_id).replace("{event_type}", "inputs")
    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(path, params={"limit": limit})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "limit"]


@pytest.mark.parametrize("path_template, service_path", PAGINATED_ROUTES)
@pytest.mark.parametrize("offset", [-1, 10_001])
def test_invalid_offset_is_rejected_before_service_access(
    monkeypatch, isolated_gateway, path_template, service_path, offset
):
    app, location_id = isolated_gateway

    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject the offset before service/database access")

    monkeypatch.setattr(service_path, unexpected_service)
    path = path_template.replace("{location_id}", location_id).replace("{event_type}", "inputs")
    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(path, params={"offset": offset})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "offset"]
