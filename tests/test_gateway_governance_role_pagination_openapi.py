"""Governance list routes publish and enforce their service page-size bounds."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = str(uuid4())
ROUTES = (
    "/operator/api/governance/{location_id}/roles",
    "/operator/api/governance/{location_id}/assignment-proposals",
    "/operator/api/governance/{location_id}/assignment-review-queue",
    "/operator/api/governance/{location_id}/tactical-items",
    "/operator/api/governance/{location_id}/tactical-sessions",
    "/operator/api/governance/{location_id}/tensions",
)


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


def test_governance_list_routes_publish_service_page_limit_in_openapi(
    monkeypatch, isolated_audit
):
    app = _app_with_operator(monkeypatch)
    schema = app.openapi()

    for path in ROUTES:
        parameter = next(
            item
            for item in schema["paths"][path]["get"]["parameters"]
            if item["name"] == "limit"
        )
        assert parameter["schema"] == {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 50,
            "title": "Limit",
        }


def test_tactical_session_openapi_declares_exact_page_and_item_contract(
    monkeypatch, isolated_audit
):
    schema = _app_with_operator(monkeypatch).openapi()
    operation = schema["paths"][
        "/operator/api/governance/{location_id}/tactical-sessions"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    page_name = response_schema["$ref"].rsplit("/", 1)[-1]
    page_schema = schema["components"]["schemas"][page_name]

    assert set(page_schema["properties"]) == {"location_id", "items", "next_cursor"}
    item_ref = page_schema["properties"]["items"]["items"]["$ref"]
    item_name = item_ref.rsplit("/", 1)[-1]
    assert set(schema["components"]["schemas"][item_name]["properties"]) == {
        "id",
        "session_type",
        "title",
        "scheduled_at",
        "status",
        "created_at",
        "circle_key",
        "circle_name",
        "item_count",
        "open_item_count",
        "disposed_item_count",
        "overdue_item_count",
    }


def test_assignment_review_queue_openapi_declares_strict_migration_projection(
    monkeypatch, isolated_audit
):
    schema = _app_with_operator(monkeypatch).openapi()
    operation = schema["paths"][
        "/operator/api/governance/{location_id}/assignment-review-queue"
    ]["get"]
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    page = schema["components"]["schemas"][response_ref.rsplit("/", 1)[-1]]
    item_ref = page["properties"]["items"]["items"]["$ref"]
    item = schema["components"]["schemas"][item_ref.rsplit("/", 1)[-1]]

    assert page["additionalProperties"] is False
    assert set(page["properties"]) == {"location_id", "items", "next_cursor"}
    assert page["properties"]["items"]["maxItems"] == 100
    assert item["additionalProperties"] is False
    assert set(item["properties"]) == {
        "assignment_id", "request_id", "role_id", "role_key", "role_name",
        "nominee_party_id", "nominee_name", "nominee_status",
        "submitted_by_party_id", "submitted_by_name", "assignment_type", "mandate",
        "role_status", "created_at",
    }
    assert item["properties"]["assignment_type"]["enum"] == [
        "primary", "delegate", "representative", "interim"
    ]
    assert {"400", "403", "404", "500", "503"}.issubset(operation["responses"])


def test_governance_list_routes_reject_invalid_limits_before_service_access(
    monkeypatch, isolated_audit
):
    service = Mock(side_effect=AssertionError("invalid paging must fail before service access"))
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_roles", service
    )
    monkeypatch.setattr(
        "services.gateway.governance_assignment_proposal_reads.list_own_governance_assignment_proposals",
        service,
    )
    monkeypatch.setattr(
        "services.gateway.governance_assignment_review.list_governance_assignment_reviews",
        service,
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_items",
        service,
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_sessions",
        service,
    )
    monkeypatch.setattr(
        "services.gateway.governance_tension_review.list_location_governance_tensions",
        service,
    )
    app = _app_with_operator(monkeypatch)

    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        for path in ROUTES:
            for invalid_limit in (0, 101):
                response = client.get(
                    path.format(location_id=LOCATION_ID), params={"limit": invalid_limit}
                )
                assert response.status_code == 422, (path, invalid_limit)

    service.assert_not_called()
