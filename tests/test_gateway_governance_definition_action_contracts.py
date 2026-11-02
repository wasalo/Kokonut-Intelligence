"""Strict Gateway contracts for migration-442 governance lifecycle actions."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
OTHER_LOCATION_ID = str(uuid4())
DEFINITION_ID = str(uuid4())
EVENT_ID = str(uuid4())
ACTOR_PARTY_ID = str(uuid4())
REQUEST_ID = str(uuid4())

_ACTION_CASES = (
    ("circle", "submit", "draft", "submitted", "GovernanceCircleSubmittedResponse"),
    ("circle", "reject", "draft", "rejected", "GovernanceCircleRejectedResponse"),
    ("circle", "activate", "submitted", "active", "GovernanceCircleActivatedResponse"),
    ("circle", "suspend", "active", "suspended", "GovernanceCircleSuspendedResponse"),
    ("circle", "retire", "suspended", "retired", "GovernanceCircleRetiredResponse"),
    ("role", "submit", "draft", "submitted", "GovernanceRoleSubmittedResponse"),
    ("role", "approve", "submitted", "approved", "GovernanceRoleApprovedResponse"),
    ("role", "reject", "submitted", "rejected", "GovernanceRoleRejectedResponse"),
    ("role", "activate", "approved", "active", "GovernanceRoleActivatedResponse"),
    ("role", "suspend", "active", "suspended", "GovernanceRoleSuspendedResponse"),
    ("role", "retire", "active", "retired", "GovernanceRoleRetiredResponse"),
)

_PUBLIC_FIELDS = {
    "event_id",
    "entity_type",
    "entity_id",
    "action",
    "prior_status",
    "resulting_status",
    "created_at",
}


class _InMemoryAudit:
    def replay_pending(self, _limit=100):
        return 0

    def log(self, **_event):
        return None

    def capture_status(self):
        return "ok"

    def reserve_mutation(self):
        return object()

    def release_mutation(self, _reservation):
        return None


def _client(monkeypatch, granted_scopes=None):
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", _InMemoryAudit)
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )
    allowed = set(granted_scopes or ())

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def csrf_valid(self, request, _session):
            return request.headers.get("x-csrf-token") == request.cookies.get(
                "kokonut_operator_csrf"
            )

        def has_scope(self, operator_id, resource, action, location_id):
            return (operator_id, resource, action, location_id) in allowed

        def list_scopes(self, _operator_id):
            return []

        def revoke_session(self, _session_id):
            return None

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    client = TestClient(create_app(), base_url="https://operator.example")
    client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
    client.cookies.set("kokonut_operator_csrf", "synthetic-csrf", path="/operator")
    return client


def _path(entity_type, action, *, location_id=LOCATION_ID, entity_id=DEFINITION_ID):
    return (
        f"/operator/api/governance/{location_id}/{entity_type}s/"
        f"{entity_id}/{action}"
    )


def _route_path_template(entity_type, action):
    identifier = "circle_id" if entity_type == "circle" else "role_id"
    return f"/operator/api/governance/{{location_id}}/{entity_type}s/{{{identifier}}}/{action}"


def _payload(**updates):
    result = {
        "request_id": REQUEST_ID,
        "reason": "The governance record is ready for this transition.",
    }
    result.update(updates)
    return result


def _action_result(entity_type, action, prior_status, resulting_status, **updates):
    result = {
        "event_id": EVENT_ID,
        "entity_type": entity_type,
        "entity_id": DEFINITION_ID,
        "action": action,
        "prior_status": prior_status,
        "resulting_status": resulting_status,
        "actor_party_id": ACTOR_PARTY_ID,
        "created_at": "2026-10-30T12:00:00Z",
    }
    result.update(updates)
    return result


def _public_result(result):
    return {
        **{key: value for key, value in result.items() if key != "actor_party_id"},
        "created_at": result["created_at"].replace("Z", "+00:00"),
    }


@pytest.mark.parametrize(
    ("entity_type", "action", "prior_status", "resulting_status", "response_model"),
    _ACTION_CASES,
)
def test_lifecycle_routes_publish_action_specific_openapi_and_public_receipts(
    monkeypatch, entity_type, action, prior_status, resulting_status, response_model
):
    result = _action_result(entity_type, action, prior_status, resulting_status)
    granted_scopes = {(OPERATOR_ID, "governance_roles", action, LOCATION_ID)}
    with patch(
        "services.gateway.governance_definition_actions.transition_governance_definition",
        side_effect=[result, result],
    ) as transition:
        with _client(monkeypatch, granted_scopes) as client:
            route = _path(entity_type, action)
            first = client.post(
                route,
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            retry = client.post(
                route,
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            schema = client.app.openapi()

    expected = _public_result(result)
    for response in (first, retry):
        assert response.status_code == 200
        assert response.json() == expected
        assert set(response.json()) == _PUBLIC_FIELDS
        assert "actor_party_id" not in response.json()
        assert response.headers["cache-control"] == "no-store"
        assert "cookie" in {
            value.strip().lower() for value in response.headers["vary"].split(",")
        }

    assert transition.call_count == 2
    expected_call = (
        OPERATOR_ID,
        LOCATION_ID,
        entity_type,
        DEFINITION_ID,
        action,
        _payload(),
    )
    assert all(call.args == expected_call and not call.kwargs for call in transition.call_args_list)

    operation = schema["paths"][_route_path_template(entity_type, action)]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {"request_id", "reason"}
    assert set(request_schema["properties"]) == {"request_id", "reason"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": f"#/components/schemas/{response_model}"
    }
    response_schema = schema["components"]["schemas"][response_model]
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["properties"]) == _PUBLIC_FIELDS
    assert set(response_schema["required"]) == _PUBLIC_FIELDS
    assert "actor_party_id" not in response_schema["properties"]
    assert response_schema["properties"]["entity_type"].get("const") == entity_type
    assert response_schema["properties"]["action"].get("const") == action
    assert response_schema["properties"]["resulting_status"].get("const") == resulting_status


@pytest.mark.parametrize(
    "updates",
    [
        {"entity_type": "circle"},
        {"entity_id": str(uuid4())},
        {"action": "reject"},
        {"prior_status": "draft"},
        {"resulting_status": "active"},
        {"unexpected_internal": "do not leak"},
    ],
)
def test_malformed_lifecycle_results_are_sanitized_without_store(monkeypatch, updates):
    base = _action_result("role", "approve", "submitted", "approved")
    malformed = {**base, **updates}
    grants = {(OPERATOR_ID, "governance_roles", "approve", LOCATION_ID)}
    with patch(
        "services.gateway.governance_definition_actions.transition_governance_definition",
        return_value=malformed,
    ):
        with _client(monkeypatch, grants) as client:
            response = client.post(
                _path("role", "approve"),
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )

    assert response.status_code == 500
    assert response.json() == {"error": "Governance definition action unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "actor_party_id" not in response.text
    assert ACTOR_PARTY_ID not in response.text
    assert "do not leak" not in response.text


def test_lifecycle_routes_require_the_exact_action_grant_and_valid_csrf(monkeypatch):
    submit_grant = {(OPERATOR_ID, "governance_roles", "submit", LOCATION_ID)}
    with patch(
        "services.gateway.governance_definition_actions.transition_governance_definition",
        side_effect=AssertionError("denied requests must not call the transition service"),
    ) as transition:
        with _client(monkeypatch, submit_grant) as client:
            wrong_action = client.post(
                _path("circle", "retire"),
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            wrong_location = client.post(
                _path("circle", "submit", location_id=OTHER_LOCATION_ID),
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            missing_csrf = client.post(
                _path("circle", "submit"),
                json=_payload(),
            )

    assert wrong_action.status_code == 403
    assert wrong_location.status_code == 403
    assert missing_csrf.status_code == 403
    transition.assert_not_called()

    for entity_type, action, *_ in _ACTION_CASES:
        policy = auth_route_policy("POST", _path(entity_type, action), enabled=True)
        assert policy == {
            "resource": "governance_roles",
            "action": action,
            "public": False,
            "location_id": LOCATION_ID,
            "scope_required": True,
            "operator_auth": True,
        }
