"""Strict OpenAPI and runtime contract for private governance circle detail."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
CIRCLE_ID = str(uuid4())
PARENT_CIRCLE_ID = str(uuid4())


def _detail(**overrides):
    result = {
        "location_id": LOCATION_ID,
        "circle": {
            "id": UUID(CIRCLE_ID),
            "circle_key": "adelphi-stewardship",
            "name": "Adelphi Stewardship",
            "purpose": "Coordinate farm stewardship.",
            "description": "Location governance circle.",
            "parent_circle_id": UUID(PARENT_CIRCLE_ID),
            "status": "draft",
        },
    }
    return {**result, **overrides}


def _client(monkeypatch, service):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return True

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr(
        "services.gateway.governance_operations.get_location_governance_circle_detail",
        service,
    )
    return TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"})


def test_circle_detail_route_returns_exact_projection_and_preserves_cache_policy(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return _detail()

    with _client(monkeypatch, service) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/circles/{CIRCLE_ID}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json()["circle"]["id"] == CIRCLE_ID
    assert response.json()["circle"]["parent_circle_id"] == PARENT_CIRCLE_ID
    assert calls == [(OPERATOR_ID, LOCATION_ID, CIRCLE_ID)]


@pytest.mark.parametrize(
    "projection",
    [
        _detail(circle={**_detail()["circle"], "private_metadata": {"secret": True}}),
        _detail(location_id=str(uuid4())),
        _detail(circle={**_detail()["circle"], "id": UUID(str(uuid4()))}),
        _detail(circle={**_detail()["circle"], "status": "published"}),
        _detail(circle={**_detail()["circle"], "parent_circle_id": "not-a-uuid"}),
        _detail(circle={key: value for key, value in _detail()["circle"].items() if key != "description"}),
        _detail(circle={**_detail()["circle"], "name": "x" * 256}),
        _detail(circle={**_detail()["circle"], "description": True}),
    ],
)
def test_circle_detail_route_fails_closed_for_invalid_projection(monkeypatch, projection):
    with _client(monkeypatch, lambda *_args: projection) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/circles/{CIRCLE_ID}")

    assert response.status_code == 500
    assert response.json() == {"error": "Governance circle detail unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "private_metadata" not in response.text


def test_circle_detail_tenant_denial_remains_forbidden_and_uncached(monkeypatch):
    def denied(*_args):
        raise TenantContextDenied("synthetic revoked grant")

    with _client(monkeypatch, denied) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/circles/{CIRCLE_ID}")

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]


def test_circle_detail_route_publishes_strict_exact_openapi_contract(monkeypatch):
    with _client(monkeypatch, lambda *_args: _detail()) as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/operator/api/governance/{location_id}/circles/{circle_id}"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/GovernanceCircleDetailResponse"
    }
    for model in ("GovernanceCircleDetailResponse", "GovernanceCircleDetailItemResponse"):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
    assert set(
        schema["components"]["schemas"]["GovernanceCircleDetailItemResponse"]["properties"]
    ) == {
        "id",
        "circle_key",
        "name",
        "purpose",
        "description",
        "parent_circle_id",
        "status",
    }
