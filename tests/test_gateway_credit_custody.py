"""Aggregate credit-custody Gateway reads keep approval private and scoped."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.credit_custody import get_credit_custody_summary  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_credit_custody_policy_requires_both_location_read_grants():
    location_id = str(uuid4())
    path = f"/operator/api/credit-custody/{location_id}/summary"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "carbon_credit",
        "action": "read",
        "additional_scopes": [
            {"resource": "credit_retirement", "action": "read"}
        ],
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/records", enabled=True) is None
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
        if "FROM carbon_credit" in query:
            self.single = (3, Decimal("90.0000"), Decimal("4.0000"), Decimal("2.0000"),
                           Decimal("84.0000"), Decimal("1200.00"))
            self.connection.events.append("credit_summary")
        elif "FROM credit_retirement" in query:
            self.rows = [
                ("draft", 1, Decimal("2.0000"), Decimal("50.00")),
                ("verified", 1, Decimal("4.0000"), Decimal("100.00")),
            ]
            self.connection.events.append("retirement_summary")

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


def test_custody_summary_sets_both_signed_scopes_before_private_free_aggregates():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "carbon_credit",
            "action": "read",
            "required_scopes": (("credit_retirement", "read"),),
        }
        connection.events.append("tenant_context")

    with patch("services.gateway.credit_custody.set_operator_tenant_context", set_context):
        result = get_credit_custody_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert conn.events == ["tenant_context", "credit_summary", "retirement_summary"]
    assert conn.queries[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.queries[3][1] == (location_id,)
    assert conn.queries[4][1] == (location_id,)
    assert "beneficiary" not in conn.queries[4][0]
    assert "statement" not in conn.queries[4][0]
    assert "evidence" not in conn.queries[4][0]
    assert "idempotency_key" not in conn.queries[4][0]
    assert result == {
        "location_id": location_id,
        "total_credits": 3,
        "credit_totals": {
            "issuable_tonnes": "90.0000",
            "retired_tonnes": "4.0000",
            "reserved_tonnes": "2.0000",
            "available_tonnes": "84.0000",
            "recorded_total_value_usd": "1200.00",
        },
        "retirements_by_status": [
            {"status": "draft", "count": 1, "requested_tonnes": "2.0000", "requested_value_usd": "50.00"},
            {"status": "verified", "count": 1, "requested_tonnes": "4.0000", "requested_value_usd": "100.00"},
        ],
    }
    assert conn.rolled_back and conn.closed


def test_invalid_custody_scope_fails_before_connection():
    requested = False

    def connection_factory():
        nonlocal requested
        requested = True
        raise AssertionError("invalid selector must not open a connection")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_credit_custody_summary("bad", str(uuid4()), connection_factory=connection_factory)
    assert requested is False


def test_retirement_scope_denial_rolls_back_before_aggregate_queries():
    conn = _Connection()
    with patch(
        "services.gateway.credit_custody.set_operator_tenant_context",
        side_effect=TenantContextDenied("missing retirement grant"),
    ):
        with pytest.raises(TenantContextDenied):
            get_credit_custody_summary(
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


def test_credit_custody_http_route_uses_scoped_handler_and_no_store_headers(
    monkeypatch, isolated_audit
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

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource in {"carbon_credit", "credit_retirement"}
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    summary = {"location_id": location_id, "total_credits": 0, "credit_totals": {}}
    monkeypatch.setattr("services.gateway.credit_custody.get_credit_custody_summary", lambda *_args: summary)
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/credit-custody/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == summary
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_credit_custody_http_route_requires_retirement_scope_before_service(
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

        def has_scope(self, _operator_id, resource, action, _location_id):
            return resource == "carbon_credit" and action == "read"

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    service_called = False

    def unexpected_service(*_args):
        nonlocal service_called
        service_called = True
        raise AssertionError("missing retirement scope must precede database access")

    monkeypatch.setattr("services.gateway.credit_custody.get_credit_custody_summary", unexpected_service)
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/credit-custody/{uuid4()}/summary")

    assert response.status_code == 403
    assert service_called is False
