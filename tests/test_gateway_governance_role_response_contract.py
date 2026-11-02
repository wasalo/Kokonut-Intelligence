"""Strict response contract for the private governance role registry page."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi.encoders import jsonable_encoder  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = str(uuid4())
ROLE_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 28, tzinfo=timezone.utc)


@pytest.fixture
def isolated_audit(monkeypatch):
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


def _app_with_operator(monkeypatch):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return True

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    return create_app()


def _role():
    return {
        "id": ROLE_ID,
        "role_key": "steward",
        "name": "Steward",
        "purpose": "Coordinate approved stewardship decisions.",
        "status": "active",
        "effective_from": None,
        "effective_until": None,
        "review_due_at": None,
        "created_at": CREATED_AT,
        "circle_key": "adelphi-council",
        "circle_name": "Adelphi Council",
        "circle_status": "active",
        "active_accountability_count": 2,
        "current_assignment_count": 1,
        "applicable_authority_domain_count": 3,
    }


def _page(**overrides):
    page = {"location_id": LOCATION_ID, "items": [_role()], "next_cursor": None}
    page.update(overrides)
    return page


def _request(monkeypatch, isolated_audit, result, *, limit=50):
    service = Mock(return_value=result)
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_roles", service
    )
    app = _app_with_operator(monkeypatch)
    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/roles", params={"limit": limit}
        )
    return response, service


def test_governance_role_list_openapi_publishes_exact_read_projection(
    monkeypatch, isolated_audit
):
    app = _app_with_operator(monkeypatch)
    operation = app.openapi()["paths"]["/operator/api/governance/{location_id}/roles"]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("GovernanceRoleListResponse")

    components = app.openapi()["components"]["schemas"]
    item = components["GovernanceRoleListItemResponse"]
    assert set(item["properties"]) == {
        "id",
        "role_key",
        "name",
        "purpose",
        "status",
        "effective_from",
        "effective_until",
        "review_due_at",
        "created_at",
        "circle_key",
        "circle_name",
        "circle_status",
        "active_accountability_count",
        "current_assignment_count",
        "applicable_authority_domain_count",
    }
    assert item["additionalProperties"] is False


def test_governance_role_list_returns_exact_page_and_preserves_private_headers(
    monkeypatch, isolated_audit
):
    response, service = _request(monkeypatch, isolated_audit, _page())

    assert response.status_code == 200
    assert response.json() == jsonable_encoder(_page())
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"].split(", ")
    service.assert_called_once()


@pytest.mark.parametrize(
    "page,limit",
    [
        ({**_page(), "location_id": str(uuid4())}, 50),
        ({**_page(), "items": [{**_role(), "private_notes": "never expose"}]}, 50),
        ({**_page(), "items": [{**_role(), "current_assignment_count": -1}]}, 50),
        ({**_page(), "next_cursor": str(uuid4())}, 50),
        (_page(), 0),
    ],
)
def test_governance_role_list_rejects_malformed_or_out_of_scope_projection(
    monkeypatch, isolated_audit, page, limit
):
    response, _service = _request(monkeypatch, isolated_audit, page, limit=limit)

    if limit == 0:
        assert response.status_code == 422
    else:
        assert response.status_code == 500
        assert response.json() == {"error": "Governance role registry unavailable"}
        assert response.headers["cache-control"] == "no-store"
        assert "Cookie" in response.headers["vary"].split(", ")


def test_governance_role_list_rejects_more_items_than_requested_limit(
    monkeypatch, isolated_audit
):
    response, _service = _request(monkeypatch, isolated_audit, _page(), limit=1)
    assert response.status_code == 200

    response, _service = _request(
        monkeypatch,
        isolated_audit,
        _page(items=[_role(), {**_role(), "id": str(uuid4())}]),
        limit=1,
    )
    assert response.status_code == 500


def test_governance_role_list_requires_cursor_to_be_last_item_id(
    monkeypatch, isolated_audit
):
    page = _page(next_cursor=ROLE_ID)
    response, _service = _request(monkeypatch, isolated_audit, page)
    assert response.status_code == 200

    page["next_cursor"] = str(uuid4())
    response, _service = _request(monkeypatch, isolated_audit, page)
    assert response.status_code == 500
