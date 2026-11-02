"""Gateway pagination bounds match service validation and are advertised in OpenAPI."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

PAGINATED_ROUTES = (
    (
        "/operator/api/ecocredits/{location_id}/batches",
        "services.gateway.ecocredits.list_location_ecocredit_batches",
    ),
    (
        "/operator/api/attestations/{location_id}",
        "services.gateway.attestations.list_location_attestations",
    ),
)


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
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource in {"ecocredit", "attestation"}
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    return create_app(), location_id


@pytest.mark.parametrize("path, _service_path", PAGINATED_ROUTES)
def test_openapi_pagination_contract_matches_service_bounds(isolated_gateway, path, _service_path):
    app, _location_id = isolated_gateway
    operation = app.openapi()["paths"][path]["get"]
    limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")

    assert limit["schema"]["type"] == "integer"
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 100
    assert limit["schema"]["default"] == 50


@pytest.mark.parametrize(
    "path_template, service_path",
    PAGINATED_ROUTES,
)
@pytest.mark.parametrize("limit", [0, 101])
def test_out_of_range_limit_is_rejected_before_service_access(
    monkeypatch, isolated_gateway, path_template, service_path, limit
):
    app, location_id = isolated_gateway

    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject the limit before service/database access")

    monkeypatch.setattr(service_path, unexpected_service)
    path = path_template.replace("{location_id}", location_id)
    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(path, params={"limit": limit})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "limit"]
