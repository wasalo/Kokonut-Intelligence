"""The traceability list publishes and enforces its bounded page contract."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402


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
