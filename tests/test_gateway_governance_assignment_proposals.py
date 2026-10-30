"""Proposal-only Gateway role assignment creation is tenant scoped."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_assignment_proposals as proposals
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROLE_ID = str(uuid4())
PARTY_ID = str(uuid4())
REQUEST_ID = str(uuid4())
ASSIGNMENT_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 18, tzinfo=timezone.utc)


class _Cursor:
    description = [
        SimpleNamespace(name="assignment_id"),
        SimpleNamespace(name="role_id"),
        SimpleNamespace(name="assignment_type"),
        SimpleNamespace(name="status"),
        SimpleNamespace(name="created_at"),
    ]

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append(("sql", " ".join(query.split()), params))
        if "propose_governance_role_assignment" in query:
            self.connection.row = (
                ASSIGNMENT_ID, ROLE_ID, "primary", "proposed", CREATED_AT
            )

    def fetchone(self):
        return self.connection.row


class _Connection:
    autocommit = False

    def __init__(self):
        self.operations = []
        self.row = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _payload(**overrides):
    payload = {
        "request_id": REQUEST_ID,
        "party_id": PARTY_ID,
        "assignment_type": "primary",
        "mandate": None,
    }
    payload.update(overrides)
    return payload


def test_proposal_sets_signed_context_before_call_and_commits_proposed_result():
    conn = _Connection()
    events = []

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "governance_roles",
            "action": "create",
        }
        events.append("context")

    class RecordingCursor(_Cursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "propose_governance_role_assignment" in query:
                events.append("function")

    conn.cursor = lambda: RecordingCursor(conn)
    with patch.object(proposals, "set_operator_tenant_context", set_context):
        result = proposals.propose_governance_role_assignment(
            OPERATOR_ID,
            LOCATION_ID,
            ROLE_ID,
            _payload(),
            connection_factory=lambda: conn,
        )

    assert events == ["context", "function"]
    assert conn.operations[0][1:] == ("SET LOCAL statement_timeout = '8s'", None)
    assert conn.operations[1][1:] == ("SET LOCAL lock_timeout = '2s'", None)
    assert conn.operations[2][2] == (
        LOCATION_ID, REQUEST_ID, ROLE_ID, PARTY_ID, "primary", None
    )
    assert result == {
        "assignment_id": ASSIGNMENT_ID,
        "role_id": ROLE_ID,
        "assignment_type": "primary",
        "status": "proposed",
        "created_at": CREATED_AT,
    }
    assert conn.committed and not conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    ("operator_id", "location_id", "role_id", "payload", "message"),
    [
        ("bad", LOCATION_ID, ROLE_ID, _payload(), "Invalid operator"),
        (OPERATOR_ID, LOCATION_ID, ROLE_ID, {**_payload(), "extra": True}, "must contain"),
        (OPERATOR_ID, LOCATION_ID, ROLE_ID, _payload(assignment_type="invalid"), "not supported"),
        (OPERATOR_ID, LOCATION_ID, ROLE_ID, _payload(assignment_type="delegate"), "require a mandate"),
        (OPERATOR_ID, LOCATION_ID, ROLE_ID, _payload(mandate="x" * 2001), "at most 2000"),
    ],
)
def test_malformed_proposal_fails_before_opening_database(
    operator_id, location_id, role_id, payload, message
):
    with pytest.raises(proposals.GovernanceAssignmentInvalid, match=message):
        proposals.propose_governance_role_assignment(
            operator_id,
            location_id,
            role_id,
            payload,
            connection_factory=lambda: pytest.fail("database must not open"),
        )


def test_tenant_denial_rolls_back_and_closes_without_calling_proposal_function():
    conn = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(proposals, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            proposals.propose_governance_role_assignment(
                OPERATOR_ID,
                LOCATION_ID,
                ROLE_ID,
                _payload(),
                connection_factory=lambda: conn,
            )

    assert not any("propose_governance_role_assignment" in query for _, query, _ in conn.operations)
    assert conn.rolled_back and conn.closed and not conn.committed


def test_route_policy_allows_only_exact_scoped_proposal_post():
    path = f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "governance_roles",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/approve", enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def _operator_proposal_client(monkeypatch, *, create_allowed=True, csrf_allowed=True):
    class InMemoryAudit:
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

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def csrf_valid(self, *_args):
            return csrf_allowed

        def has_scope(self, operator_id, resource, action, location_id):
            return create_allowed and (operator_id, resource, action, location_id) == (
                OPERATOR_ID, "governance_roles", "create", LOCATION_ID
            )

        def list_scopes(self, _operator_id):
            return []

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    client = TestClient(create_app(), base_url="https://operator.example")
    client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
    client.cookies.set("kokonut_operator_csrf", "synthetic-csrf", path="/operator")
    return client


def _assert_varies_by_cookie(response):
    assert "Cookie" in {value.strip() for value in response.headers.get("vary", "").split(",")}


def test_http_proposal_route_requires_csrf_scope_and_returns_no_store(monkeypatch):
    created = {
        "assignment_id": ASSIGNMENT_ID,
        "role_id": ROLE_ID,
        "assignment_type": "primary",
        "status": "proposed",
        "created_at": CREATED_AT,
    }
    with patch(
        "services.gateway.governance_assignment_proposals.propose_governance_role_assignment",
        return_value=created,
    ) as propose_call:
        with _operator_proposal_client(monkeypatch) as client:
            response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments",
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    _assert_varies_by_cookie(response)
    assert set(response.json()) == {
        "assignment_id", "role_id", "assignment_type", "status", "created_at"
    }
    assert response.json()["assignment_id"] == ASSIGNMENT_ID
    assert response.json()["role_id"] == ROLE_ID
    assert response.json()["assignment_type"] == "primary"
    assert response.json()["status"] == "proposed"
    assert datetime.fromisoformat(response.json()["created_at"].replace("Z", "+00:00")) == CREATED_AT
    assert "operator_id" not in response.json()
    assert "party_id" not in response.json()
    propose_call.assert_called_once_with(OPERATOR_ID, LOCATION_ID, ROLE_ID, _payload())


def test_http_proposal_route_denies_missing_create_grant_before_service(monkeypatch):
    with patch(
        "services.gateway.governance_assignment_proposals.propose_governance_role_assignment",
        side_effect=AssertionError("unauthorized request must not reach the service"),
    ), _operator_proposal_client(monkeypatch, create_allowed=False) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments",
            json=_payload(),
            headers={"x-csrf-token": "synthetic-csrf"},
        )

    assert response.status_code == 403


def test_http_proposal_route_denies_invalid_csrf_before_service(monkeypatch):
    with patch(
        "services.gateway.governance_assignment_proposals.propose_governance_role_assignment",
        side_effect=AssertionError("CSRF denial must not reach the service"),
    ), _operator_proposal_client(monkeypatch, csrf_allowed=False) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments",
            json=_payload(),
            headers={"x-csrf-token": "synthetic-csrf"},
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["reason"] == "csrf_validation_failed"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(operator_id=OPERATOR_ID),
        lambda payload: payload.pop("mandate"),
        lambda payload: payload.update(request_id="not-a-uuid"),
        lambda payload: payload.update(party_id="not-a-uuid"),
        lambda payload: payload.update(assignment_type="observer"),
        lambda payload: payload.update(assignment_type="delegate", mandate=None),
        lambda payload: payload.update(mandate="x" * 2001),
    ],
    ids=["extra-identity-field", "missing-required-field", "bad-request-id", "bad-party-id", "bad-assignment-type", "delegate-without-mandate", "mandate-too-long"],
)
def test_http_proposal_route_rejects_invalid_request_before_service(monkeypatch, mutate):
    payload = _payload()
    mutate(payload)
    with patch(
        "services.gateway.governance_assignment_proposals.propose_governance_role_assignment",
        side_effect=AssertionError("invalid request must not reach the service"),
    ), _operator_proposal_client(monkeypatch) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments",
            json=payload,
            headers={"x-csrf-token": "synthetic-csrf"},
        )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    _assert_varies_by_cookie(response)
    assert response.json() == {"error": "Role nomination request or path is invalid"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(operator_id=OPERATOR_ID),
        lambda result: result.update(role_id=str(uuid4())),
        lambda result: result.update(assignment_type="delegate"),
        lambda result: result.update(status="active"),
        lambda result: result.pop("created_at"),
        lambda result: result.update(created_at="2026-10-18T00:00:00"),
        lambda result: result.update(created_at="not-a-timestamp"),
    ],
    ids=["extra-identity-field", "wrong-role", "wrong-assignment-type", "not-proposed", "missing-timestamp", "naive-timestamp", "invalid-timestamp"],
)
def test_http_proposal_route_rejects_malformed_result_without_store(monkeypatch, mutate):
    result = {
        "assignment_id": ASSIGNMENT_ID,
        "role_id": ROLE_ID,
        "assignment_type": "primary",
        "status": "proposed",
        "created_at": CREATED_AT,
    }
    mutate(result)

    with patch(
        "services.gateway.governance_assignment_proposals.propose_governance_role_assignment",
        return_value=result,
    ), _operator_proposal_client(monkeypatch) as client:
        response = client.post(
            f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}/assignments",
            json=_payload(),
            headers={"x-csrf-token": "synthetic-csrf"},
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    _assert_varies_by_cookie(response)
    assert response.json() == {"error": "Governance role nomination unavailable"}


def test_http_proposal_route_openapi_declares_exact_request_and_response_contract(monkeypatch):
    with _operator_proposal_client(monkeypatch) as client:
        operation = client.app.openapi()["paths"][
            "/operator/api/governance/{location_id}/roles/{role_id}/assignments"
        ]["post"]

    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert set(request_schema["properties"]) == {
        "request_id", "party_id", "assignment_type", "mandate"
    }
    assert set(request_schema["required"]) == {
        "request_id", "party_id", "assignment_type", "mandate"
    }
    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["assignment_type"]["enum"] == [
        "primary", "delegate", "representative", "interim"
    ]
    assert operation["responses"]["201"]["description"]
    response_schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/GovernanceAssignmentProposalResponse")
    response_contract = client.app.openapi()["components"]["schemas"][
        "GovernanceAssignmentProposalResponse"
    ]
    assert set(response_contract["properties"]) == {
        "assignment_id", "role_id", "assignment_type", "status", "created_at"
    }
    assert response_contract["additionalProperties"] is False
    assert response_contract["properties"]["status"]["const"] == "proposed"
    assert operation["responses"]["201"]["headers"]["Cache-Control"]["schema"]["example"] == "no-store"
    assert operation["responses"]["201"]["headers"]["Vary"]["schema"]["example"] == "Cookie"
