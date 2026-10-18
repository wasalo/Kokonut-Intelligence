"""True-cost Gateway access stays location-scoped and read-only."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.gateway.true_cost import get_true_cost_summary  # noqa: E402


def test_true_cost_operator_policy_requires_exact_location_read_scope():
    location_id = str(uuid4())

    policy = auth_route_policy(
        "GET", f"/operator/api/true-cost/{location_id}/summary", enabled=True
    )

    assert policy == {
        "resource": "true_cost_accounting",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "POST", f"/operator/api/true-cost/{location_id}/summary", enabled=True
    ) is None
    assert auth_route_policy(
        "GET", f"/operator/api/true-cost/{location_id}/summary/extra", enabled=True
    ) is None
    assert auth_route_policy(
        "GET", f"/operator/api/true-cost/{location_id}/summary", enabled=False
    ) is None


class _Cursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))


class _Connection:
    autocommit = False

    def __init__(self):
        self.statements = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self.statements)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_true_cost_summary_sets_context_before_all_analytics_on_same_read_only_connection():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    calls = []
    labels = (
        "statement",
        "hidden",
        "natural",
        "social",
        "flows",
        "dependencies",
    )

    def analytics(label):
        def call(connection, scoped_location_id):
            assert connection is conn
            assert scoped_location_id == location_id
            calls.append(label)
            return {"section": label}

        return call

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "true_cost_accounting",
            "action": "read",
        }
        calls.append("tenant_context")

    with (
        patch("services.gateway.true_cost.set_operator_tenant_context", set_context),
        patch(
            "services.gateway.true_cost.compute_true_cost_statement", analytics("statement")
        ),
        patch(
            "services.gateway.true_cost.compute_hidden_cost_summary", analytics("hidden")
        ),
        patch(
            "services.gateway.true_cost.compute_natural_capital_valuation", analytics("natural")
        ),
        patch(
            "services.gateway.true_cost.compute_social_impact_valuation", analytics("social")
        ),
        patch(
            "services.gateway.true_cost.compute_capital_flow_summary", analytics("flows")
        ),
        patch(
            "services.gateway.true_cost.compute_cross_capital_dependencies",
            analytics("dependencies"),
        ),
    ):
        result = get_true_cost_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert calls == ["tenant_context", *labels]
    assert [query for query, _params in conn.statements] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert result == {
        "location_id": location_id,
        "true_cost_statement": {"section": "statement"},
        "hidden_costs": {"section": "hidden"},
        "natural_capital": {"section": "natural"},
        "social_impact": {"section": "social"},
        "capital_flows": {"section": "flows"},
        "cross_capital_dependencies": {"section": "dependencies"},
    }
    assert conn.rolled_back and conn.closed


def test_invalid_true_cost_scope_fails_before_database_connection():
    connection_requested = False

    def connection_factory():
        nonlocal connection_requested
        connection_requested = True
        raise AssertionError("invalid input must fail before opening PostgreSQL")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_true_cost_summary("not-an-operator", str(uuid4()), connection_factory=connection_factory)

    assert connection_requested is False


@pytest.fixture
def gateway_audit_spool(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "gateway-audit.sqlite3")
    )
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS", "1000")
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD", "0")

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


def test_true_cost_route_uses_operator_auth_and_returns_no_store_summary(
    monkeypatch, gateway_audit_spool
):
    operator_id, location_id = str(uuid4()), str(uuid4())
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
                and resource == "true_cost_accounting"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary",
        lambda scoped_operator, scoped_location: {
            "location_id": scoped_location,
            "true_cost_statement": {"true_profit_usd": 12.5},
        },
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


def test_true_cost_route_denies_operator_without_location_scope(
    monkeypatch, gateway_audit_spool
):
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
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    summary_called = False

    def unexpected_summary(*_args):
        nonlocal summary_called
        summary_called = True
        raise AssertionError("authorization denial must happen before the handler")

    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary", unexpected_summary
    )
    location_id = str(uuid4())

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 403
    assert summary_called is False


def test_true_cost_route_fails_closed_when_database_context_rejects_revoked_grant(
    monkeypatch, gateway_audit_spool
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return True

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())

    def reject_stale_scope(*_args):
        raise TenantContextDenied("synthetic revoked database grant")

    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary", reject_stale_scope
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 403
    assert response.json() == {
        "error": "Tenant-qualified operator access is required"
    }
