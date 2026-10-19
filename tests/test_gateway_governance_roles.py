"""Tenant-scoped governance summary is bounded and privacy-preserving."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.governance_roles import (  # noqa: E402
    get_location_governance_summary,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402

CIRCLE_ID = str(uuid4())


def test_governance_summary_policy_requires_exact_location_read_scope():
    location_id = str(uuid4())
    path = f"/operator/api/governance/{location_id}/summary"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "governance_roles",
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
        self.rows = []
        self.single = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        normalized = " ".join(query.split())
        if normalized.startswith("SET "):
            return
        if "governance_tactical_session" in query:
            self.single = (2, 4, 1, 3)
            self.connection.events.append("tactical")
        elif "FROM governance_circle c" in query:
            self.rows = [(CIRCLE_ID, "adelphi-stewardship", "Adelphi Stewardship", "active", None, 4, 1, 3, 1, 2)]
            self.connection.events.append("circles")
        elif "FROM governance_tension" in query:
            self.single = (5, 2, 1, 1)
            self.connection.events.append("tensions")

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


def test_summary_sets_tenant_context_before_scoped_aggregate_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "governance_roles",
            "action": "read",
        }
        connection.events.append("tenant_context")

    with patch("services.gateway.governance_roles.set_operator_tenant_context", set_context):
        result = get_location_governance_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert conn.events == ["tenant_context", "circles", "tensions", "tactical"]
    assert [query for query, _params in conn.queries[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert conn.queries[3][1] == (location_id, location_id)
    assert conn.queries[4][1] == (location_id,)
    assert conn.queries[5][1] == (location_id,)
    assert result == {
        "location_id": location_id,
        "circles": [{
            "id": CIRCLE_ID,
            "circle_key": "adelphi-stewardship",
            "name": "Adelphi Stewardship",
            "status": "active",
            "review_due_at": None,
            "active_role_count": 4,
            "overdue_role_review_count": 1,
            "active_assignment_count": 3,
            "proposed_assignment_count": 1,
            "active_authority_domain_count": 2,
        }],
        "tensions": {
            "total": 5,
            "unresolved": 2,
            "high_severity_unresolved": 1,
            "overdue_reviews": 1,
        },
        "tactical": {
            "sessions": 2,
            "open_items": 4,
            "overdue_items": 1,
            "disposed_items": 3,
        },
    }
    for query, _params in conn.queries[3:]:
        lowered = query.lower()
        assert "description" not in lowered
        assert "display_name" not in lowered
        assert "policy_text" not in lowered
        assert "requested_next_action" not in lowered
        assert "notes" not in lowered
    assert conn.rolled_back and conn.closed


def test_invalid_identifiers_fail_before_opening_database():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid identifiers must fail before database access")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_location_governance_summary(
            "invalid", str(uuid4()), connection_factory=connection_factory
        )

    assert not opened


def test_tenant_denial_rolls_back_without_running_governance_queries():
    conn = _Connection()
    with patch(
        "services.gateway.governance_roles.set_operator_tenant_context",
        side_effect=TenantContextDenied("synthetic revoked grant"),
    ):
        with pytest.raises(TenantContextDenied):
            get_location_governance_summary(
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


def test_http_route_requires_location_governance_grant_before_service(
    monkeypatch, isolated_audit
):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    called = False

    def unexpected_service(*_args):
        nonlocal called
        called = True
        raise AssertionError("denied request must not query governance data")

    monkeypatch.setattr(
        "services.gateway.governance_roles.get_location_governance_summary",
        unexpected_service,
    )
    location_id = str(uuid4())

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/governance/{location_id}/summary")

    assert response.status_code == 403
    assert called is False


def test_http_route_returns_no_store_scoped_summary(monkeypatch, isolated_audit):
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
                and resource == "governance_roles"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.governance_roles.get_location_governance_summary",
        lambda scoped_operator, scoped_location: {
            "location_id": scoped_location,
            "circles": [],
            "tensions": {"total": 0},
            "tactical": {"open_items": 0},
        },
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/governance/{location_id}/summary")

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }
