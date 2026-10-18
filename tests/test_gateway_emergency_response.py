"""Emergency-response Gateway reads are private, scoped, and aggregate-only."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.emergency_response import (  # noqa: E402
    get_emergency_response_summary,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_emergency_summary_policy_requires_exact_location_read_scope():
    location_id = str(uuid4())
    path = f"/operator/api/emergency-response/{location_id}/summary"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "emergency_response",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/details", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.single = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "AS total_incidents" in query:
            self.single = (5, 2, 1, 3, 4.333, 2, 1, 1234.555, 18.25)
            self.connection.events.append("aggregate")
        elif "GROUP BY incident_type" in query:
            self.rows = [("drought", 3, 1, 1, 25.0, 1000.125)]
            self.connection.events.append("by_type")
        elif "GROUP BY severity" in query:
            self.rows = [("high", 4, 2, 1, 18.25, 1234.555)]
            self.connection.events.append("by_severity")

    def fetchone(self):
        return self.single

    def fetchall(self):
        return self.rows


class _Connection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.events = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_emergency_summary_sets_signed_context_before_scoped_aggregate_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "emergency_response",
            "action": "read",
        }
        connection.events.append("tenant_context")

    with patch(
        "services.gateway.emergency_response.set_operator_tenant_context", set_context
    ):
        result = get_emergency_response_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert conn.events == ["tenant_context", "aggregate", "by_type", "by_severity"]
    assert [query for query, _params in conn.queries[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert all(
        params == (location_id,)
        for _query, params in conn.queries[3:]
    )
    assert result == {
        "location_id": location_id,
        "total_incidents": 5,
        "resolved_incidents": 2,
        "escalated_incidents": 1,
        "recovered_incidents": 3,
        "avg_response_time_days": 4.3,
        "deadline_assessed_incidents": 2,
        "deadline_met_incidents": 1,
        "deadline_compliance_pct": 50.0,
        "financial_impact_usd": 1234.56,
        "avg_affected_area_pct": 18.2,
        "by_type": [
            {
                "incident_type": "drought",
                "count": 3,
                "resolved_count": 1,
                "escalated_count": 1,
                "avg_affected_area_pct": 25.0,
                "financial_impact_usd": 1000.12,
            }
        ],
        "by_severity": [
            {
                "severity": "high",
                "count": 4,
                "resolved_count": 2,
                "escalated_count": 1,
                "avg_affected_area_pct": 18.2,
                "financial_impact_usd": 1234.56,
            }
        ],
    }
    assert "incidents" not in result
    assert conn.rolled_back and conn.closed


def test_invalid_emergency_scope_fails_before_connection():
    requested = False

    def connection_factory():
        nonlocal requested
        requested = True
        raise AssertionError("invalid scope must not open PostgreSQL")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_emergency_response_summary(
            "not-an-operator", str(uuid4()), connection_factory=connection_factory
        )

    assert requested is False


def test_emergency_tenant_denial_rolls_back_and_closes_connection():
    conn = _Connection()
    with patch(
        "services.gateway.emergency_response.set_operator_tenant_context",
        side_effect=TenantContextDenied("synthetic revoked grant"),
    ):
        with pytest.raises(TenantContextDenied):
            get_emergency_response_summary(
                str(uuid4()), str(uuid4()), connection_factory=lambda: conn
            )

    assert len(conn.queries) == 3
    assert conn.rolled_back and conn.closed


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


def test_emergency_summary_http_route_checks_scope_before_calling_service(
    monkeypatch, isolated_audit
):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    service_called = False

    def unexpected_service(*_args):
        nonlocal service_called
        service_called = True
        raise AssertionError("authorization denial must precede service access")

    monkeypatch.setattr(
        "services.gateway.emergency_response.get_emergency_response_summary",
        unexpected_service,
    )
    location_id = str(uuid4())

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(
            f"/operator/api/emergency-response/{location_id}/summary"
        )

    assert response.status_code == 403
    assert service_called is False


def test_emergency_summary_http_route_returns_no_store_aggregate(monkeypatch, isolated_audit):
    operator_id, location_id = str(uuid4()), str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "emergency_response"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.emergency_response.get_emergency_response_summary",
        lambda scoped_operator, scoped_location: {
            "location_id": scoped_location,
            "total_incidents": 2,
            "financial_impact_usd": 700.0,
        },
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(
            f"/operator/api/emergency-response/{location_id}/summary"
        )

    assert response.status_code == 200
    assert response.json()["total_incidents"] == 2
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }
