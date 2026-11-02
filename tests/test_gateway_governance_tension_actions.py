"""Governed OIDC tension intake and submission keep human attribution explicit."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway import operator_cli  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.governance_tension_actions import (  # noqa: E402
    GovernanceTensionInvalid,
    report_governance_tension,
    submit_governance_tension,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
TENSION_ID = str(uuid4())


def _payload(**updates):
    result = {
        "request_id": REQUEST_ID,
        "title": "Unclear harvest accountability",
        "description": "The current record does not identify who confirms the harvest count.",
        "tension_type": "unclear_accountability",
        "severity": 3,
        "urgency": 2,
    }
    result.update(updates)
    return result


def _action_result(*, status: str, tension_id: str = TENSION_ID, operator_id: str = OPERATOR_ID):
    return {
        "tension_id": tension_id,
        "tension_key": f"gateway:{operator_id}:{REQUEST_ID}",
        "title": "Unclear harvest accountability",
        "description": "The current record does not identify who confirms the harvest count.",
        "tension_type": "unclear_accountability",
        "severity": 3,
        "urgency": 2,
        "status": status,
        "created_at": "2026-10-18T00:00:00Z",
    }


def _public_action_result(result):
    return {
        **{key: value for key, value in result.items() if key != "tension_key"},
        "created_at": result["created_at"].replace("Z", "+00:00"),
    }


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.row = connection.result

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.row


class _Connection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.result = {
            "tension_id": TENSION_ID,
            "tension_key": f"gateway:{OPERATOR_ID}:{REQUEST_ID}",
            "title": "Unclear harvest accountability",
            "description": "The current record does not identify who confirms the harvest count.",
            "tension_type": "unclear_accountability",
            "severity": 3,
            "urgency": 2,
            "status": "draft",
            "created_at": "2026-10-18T00:00:00Z",
        }
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


def test_create_and_submit_use_signed_action_context_on_same_connection(monkeypatch):
    connection = _Connection()
    context_calls = []

    def set_context(conn, **kwargs):
        context_calls.append((conn, kwargs))

    monkeypatch.setattr(
        "services.gateway.governance_tension_actions.set_operator_tenant_context",
        set_context,
    )
    def factory():
        return connection

    draft = report_governance_tension(
        OPERATOR_ID, LOCATION_ID, _payload(), connection_factory=factory
    )
    assert draft["status"] == "draft"
    assert connection.queries[-1][0].startswith(
        "SELECT * FROM kokonut_security.report_governance_tension"
    )
    assert context_calls == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tension",
        "action": "create",
    })]
    assert connection.committed and not connection.rolled_back and connection.closed

    submitted_connection = _Connection()
    submitted_connection.result = {**draft, "status": "submitted"}
    context_calls.clear()
    submitted = submit_governance_tension(
        OPERATOR_ID,
        LOCATION_ID,
        TENSION_ID,
        connection_factory=lambda: submitted_connection,
    )
    assert submitted["status"] == "submitted"
    assert submitted_connection.queries[-1][0].startswith(
        "SELECT * FROM kokonut_security.submit_governance_tension"
    )
    assert context_calls == [(submitted_connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tension",
        "action": "submit",
    })]
    assert submitted_connection.committed and not submitted_connection.rolled_back


def test_invalid_or_untrusted_fields_fail_before_database_access():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid content must fail before database access")

    with pytest.raises(GovernanceTensionInvalid, match="unsupported fields"):
        report_governance_tension(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(party_id=str(uuid4())),
            connection_factory=connection_factory,
        )
    with pytest.raises(GovernanceTensionInvalid, match="integers"):
        report_governance_tension(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(severity=True),
            connection_factory=connection_factory,
        )
    with pytest.raises(GovernanceTensionInvalid, match="object"):
        report_governance_tension(
            OPERATOR_ID,
            LOCATION_ID,
            [],  # type: ignore[arg-type]
            connection_factory=connection_factory,
        )
    assert not opened


def test_context_denial_rolls_back_and_never_calls_governance_function(monkeypatch):
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("synthetic revoked scope")

    monkeypatch.setattr(
        "services.gateway.governance_tension_actions.set_operator_tenant_context", deny
    )
    with pytest.raises(TenantContextDenied):
        submit_governance_tension(
            OPERATOR_ID,
            LOCATION_ID,
            TENSION_ID,
            connection_factory=lambda: connection,
        )
    assert len(connection.queries) == 2
    assert connection.rolled_back and connection.closed and not connection.committed


def test_tension_routes_require_exact_oidc_scope_and_never_accept_party_identity(
    monkeypatch,
):
    class InMemoryAudit:
        def __init__(self):
            pass

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
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def csrf_valid(self, *_args):
            return True

        def has_scope(self, operator_id, resource, action, location_id):
            return (operator_id, resource, action, location_id) in {
                (OPERATOR_ID, "governance_tension", "create", LOCATION_ID),
                (OPERATOR_ID, "governance_tension", "submit", LOCATION_ID),
            }

        def list_scopes(self, _operator_id):
            return []

        def revoke_session(self, _session_id):
            return None

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    created = _action_result(status="draft")
    submitted = _action_result(status="submitted")
    create_mock = patch(
        "services.gateway.governance_tension_actions.report_governance_tension",
        return_value=created,
    )
    submit_mock = patch(
        "services.gateway.governance_tension_actions.submit_governance_tension",
        return_value=submitted,
    )
    with create_mock as create_call, submit_mock as submit_call:
        with TestClient(create_app(), base_url="https://operator.example") as client:
            client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
            client.cookies.set("kokonut_operator_csrf", "synthetic-csrf", path="/operator")
            invalid_request_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions",
                json=_payload(party_id=str(uuid4())),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            other_location_id = str(uuid4())
            denied_response = client.post(
                f"/operator/api/governance/{other_location_id}/tensions",
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            create_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions",
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            create_replay_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions",
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            submit_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions/{TENSION_ID}/submit",
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            submit_replay_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions/{TENSION_ID}/submit",
                headers={"x-csrf-token": "synthetic-csrf"},
            )

    assert invalid_request_response.status_code == 400
    assert invalid_request_response.headers["cache-control"] == "no-store"
    assert denied_response.status_code == 403
    for response in (create_response, create_replay_response):
        assert response.status_code == 201
        assert response.headers["cache-control"] == "no-store"
        assert "cookie" in {
            value.strip().lower() for value in response.headers["vary"].split(",")
        }
        assert response.json() == _public_action_result(created)
        assert "tension_key" not in response.json()
    for response in (submit_response, submit_replay_response):
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "cookie" in {
            value.strip().lower() for value in response.headers["vary"].split(",")
        }
        assert response.json() == _public_action_result(submitted)
        assert "tension_key" not in response.json()
    assert create_call.call_count == 2
    assert all(
        call.args == (OPERATOR_ID, LOCATION_ID, _payload()) and not call.kwargs
        for call in create_call.call_args_list
    )
    assert submit_call.call_count == 2
    assert all(
        call.args == (OPERATOR_ID, LOCATION_ID, TENSION_ID) and not call.kwargs
        for call in submit_call.call_args_list
    )

    schema = client.app.openapi()
    paths = schema["paths"]
    create_operation = paths["/operator/api/governance/{location_id}/tensions"]["post"]
    submit_operation = paths[
        "/operator/api/governance/{location_id}/tensions/{tension_id}/submit"
    ]["post"]
    create_request = create_operation["requestBody"]["content"]["application/json"]["schema"]
    assert create_request["additionalProperties"] is False
    assert set(create_request["required"]) == {
        "request_id", "title", "description", "tension_type", "severity", "urgency"
    }
    assert "requestBody" not in submit_operation
    assert create_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/GovernanceTensionMutationResponse"
    }
    assert submit_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/GovernanceTensionSubmittedResponse"
    }
    public_create_schema = schema["components"]["schemas"]["GovernanceTensionMutationResponse"]
    public_submit_schema = schema["components"]["schemas"]["GovernanceTensionSubmittedResponse"]
    assert "tension_key" not in public_create_schema["properties"]
    assert "tension_key" not in public_submit_schema["properties"]
    assert public_submit_schema["properties"]["status"]["const"] == "submitted"


def test_tension_mutation_routes_sanitize_malformed_action_results(monkeypatch):
    class InMemoryAudit:
        def __init__(self):
            pass

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

    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def csrf_valid(self, *_args):
            return True

        def has_scope(self, operator_id, resource, action, location_id):
            return (operator_id, resource, action, location_id) in {
                (OPERATOR_ID, "governance_tension", "create", LOCATION_ID),
                (OPERATOR_ID, "governance_tension", "submit", LOCATION_ID),
            }

        def list_scopes(self, _operator_id):
            return []

        def revoke_session(self, _session_id):
            return None

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    malformed_create = _action_result(status="draft", operator_id=str(uuid4()))
    malformed_submit = _action_result(status="submitted", tension_id=str(uuid4()))
    with (
        patch(
            "services.gateway.governance_tension_actions.report_governance_tension",
            return_value=malformed_create,
        ),
        patch(
            "services.gateway.governance_tension_actions.submit_governance_tension",
            return_value=malformed_submit,
        ),
    ):
        with TestClient(create_app(), base_url="https://operator.example") as client:
            client.cookies.set("kokonut_operator_session", "synthetic-session", path="/operator")
            client.cookies.set("kokonut_operator_csrf", "synthetic-csrf", path="/operator")
            create_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions",
                json=_payload(),
                headers={"x-csrf-token": "synthetic-csrf"},
            )
            submit_response = client.post(
                f"/operator/api/governance/{LOCATION_ID}/tensions/{TENSION_ID}/submit",
                headers={"x-csrf-token": "synthetic-csrf"},
            )

    for response in (create_response, submit_response):
        assert response.status_code == 500, response.text
        assert response.json() == {"error": "Governance tension action unavailable"}
        assert response.headers["cache-control"] == "no-store"
        assert "cookie" in {
            value.strip().lower() for value in response.headers["vary"].split(",")
        }
        assert "tension_key" not in response.text
        assert OPERATOR_ID not in response.text


def test_tension_routes_have_only_exact_location_scopes():
    create_path = f"/operator/api/governance/{LOCATION_ID}/tensions"
    submit_path = f"{create_path}/{TENSION_ID}/submit"
    assert auth_route_policy("POST", create_path, enabled=True) == {
        "resource": "governance_tension",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", submit_path, enabled=True)["action"] == "submit"
    assert auth_route_policy("GET", create_path, enabled=True)["action"] == "read"
    assert auth_route_policy("POST", create_path + "/extra", enabled=True) is None
    assert auth_route_policy("POST", create_path, enabled=False) is None


def test_binding_cli_passes_only_explicit_operator_and_party_uuids(monkeypatch):
    class AdminConnection:
        def __init__(self):
            self.calls = []
            self.entered = False

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))
            return SimpleNamespace(first=lambda: {"binding_id": "binding-id"})

    connection = AdminConnection()
    printed = []
    monkeypatch.setattr(operator_cli, "get_connection", lambda: connection)
    monkeypatch.setattr(operator_cli, "print_json", printed.append)
    args = SimpleNamespace(
        operator_id=OPERATOR_ID,
        party_id=str(uuid4()),
        bound_by="identity administrator",
        reason="Verified against the approved member register",
    )

    operator_cli.bind_governance_party(args)

    assert connection.entered
    assert connection.calls[0] == ("SET LOCAL ROLE kokonut_governance_identity_admin", None)
    assert connection.calls[1][0].startswith(
        "SELECT * FROM kokonut_security.bind_operator_governance_party"
    )
    assert connection.calls[1][1] == {
        "operator_id": OPERATOR_ID,
        "party_id": args.party_id,
        "bound_by": "identity administrator",
        "reason": "Verified against the approved member register",
    }
    assert printed == [{"binding_id": "binding-id"}]


def test_binding_cli_rejects_empty_reason_before_connecting(monkeypatch):
    connected = False

    def unexpected_connection():
        nonlocal connected
        connected = True
        raise AssertionError("invalid binding request must fail before database access")

    monkeypatch.setattr(operator_cli, "get_connection", unexpected_connection)
    with pytest.raises(ValueError, match="bound-by and reason"):
        operator_cli.bind_governance_party(
            SimpleNamespace(
                operator_id=OPERATOR_ID,
                party_id=str(uuid4()),
                bound_by=" ",
                reason="",
            )
        )
    assert not connected
