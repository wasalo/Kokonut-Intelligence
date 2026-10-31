"""Strict OpenAPI and runtime contract for private governance role detail."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROLE_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def _detail(**overrides):
    response = {
        "location_id": LOCATION_ID,
        "role": {
            "id": UUID(ROLE_ID),
            "role_key": "steward",
            "name": "Farm steward",
            "purpose": "Coordinate farm stewardship.",
            "status": "active",
            "effective_from": CREATED_AT,
            "effective_until": None,
            "review_due_at": None,
            "created_at": CREATED_AT,
            "circle_key": "adelphi-stewardship",
            "circle_name": "Adelphi Stewardship",
            "circle_status": "active",
        },
        "accountabilities": [
            {
                "accountability": "Maintain seasonal field plans.",
                "priority": 2,
                "required": True,
            }
        ],
        "accountabilities_truncated": False,
        "authority_domains": [
            {
                "domain_type": "farm_operations",
                "domain_key": "field_plan",
                "scope_type": "location",
                "authority_level": "recommend",
                "requires_human_approval": True,
            }
        ],
        "authority_domains_truncated": False,
    }
    return {**response, **overrides}


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
        "services.gateway.governance_operations.get_location_governance_role_detail", service
    )
    return TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"})


def test_role_detail_route_returns_exact_source_projection_and_preserves_cache_policy(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return _detail()

    with _client(monkeypatch, service) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json()["role"]["id"] == ROLE_ID
    assert response.json()["accountabilities"][0]["priority"] == 2
    assert calls == [(OPERATOR_ID, LOCATION_ID, ROLE_ID)]


@pytest.mark.parametrize(
    "projection",
    [
        _detail(role={**_detail()["role"], "metadata": {"private": True}}),
        _detail(location_id=str(uuid4())),
        _detail(role={**_detail()["role"], "id": UUID(str(uuid4()))}),
        _detail(accountabilities=[{"accountability": "x", "priority": "2", "required": True}]),
        _detail(authority_domains=[{**_detail()["authority_domains"][0], "scope_type": "unknown"}]),
    ],
)
def test_role_detail_route_fails_closed_for_invalid_projection(monkeypatch, projection):
    with _client(monkeypatch, lambda *_args: projection) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}")

    assert response.status_code == 500
    assert response.json() == {"error": "Governance role detail unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "private" not in response.text


def test_role_detail_tenant_denial_remains_forbidden_and_uncached(monkeypatch):
    def denied(*_args):
        raise TenantContextDenied("revoked")

    with _client(monkeypatch, denied) as client:
        response = client.get(f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}")

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]


def test_role_detail_route_publishes_strict_exact_openapi_contract(monkeypatch):
    with _client(monkeypatch, lambda *_args: _detail()) as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/operator/api/governance/{location_id}/roles/{role_id}"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/GovernanceRoleDetailResponse"
    }
    for model in (
        "GovernanceRoleDetailResponse",
        "GovernanceRoleDetailRoleResponse",
        "GovernanceRoleAccountabilityResponse",
        "GovernanceRoleAuthorityDomainResponse",
    ):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
