"""Energy Kernel reads are private, bounded, and location-scoped."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.energy_monitoring import get_location_energy_summary  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))
        if "FROM energy_reading AS er" in query:
            self.description = [(name,) for name in (
                "reading_type", "source_type", "activity_type", "reading_count",
                "total_kwh", "first_reading_date", "last_reading_date",
            )]
            self.rows = [
                ("consumption", "solar", "irrigation", 2, Decimal("10.50"), date(2026, 1, 2), date(2026, 1, 3)),
                ("production", "solar", "unspecified", 1, Decimal("8"), date(2026, 1, 4), date(2026, 1, 4)),
            ]

    def fetchall(self):
        return self.rows


class _Connection:
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


def test_energy_summary_requires_exact_policy_and_rejects_near_misses():
    location_id = str(uuid4())
    expected = {
        "resource": "energy_monitoring",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", f"/operator/api/energy/{location_id}/summary", enabled=True) == expected
    assert auth_route_policy("POST", f"/operator/api/energy/{location_id}/summary", enabled=True) is None
    assert auth_route_policy("GET", f"/operator/api/energy/{location_id}/summary/extra", enabled=True) is None


def test_energy_summary_uses_signed_context_and_verified_aggregates_only():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "energy_monitoring",
            "action": "read",
        }
        conn.events.append("tenant_context")

    def record_execute(self, query, params=None):
        conn.events.append("query")
        original_execute(self, query, params)

    original_execute = _Cursor.execute
    with patch("services.gateway.energy_monitoring.set_operator_tenant_context", set_context), patch.object(
        _Cursor, "execute", record_execute
    ):
        result = get_location_energy_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    query, params = next((query, params) for query, params in conn.queries if "FROM energy_reading AS er" in query)
    assert "er.location_id = %s::uuid" in query
    assert "er.status IN ('verified', 'approved')" in query
    assert "es.location_id = er.location_id" in query
    for private_field in ("cost_per_kwh", "total_cost", "source_name", "equipment_id", "notes", "metadata"):
        assert private_field not in query
    assert params == (location_id,)
    assert conn.events == ["query", "query", "query", "tenant_context", "query"]
    assert result == {
        "location_id": location_id,
        "unit": "kWh",
        "verified_reading_count": 3,
        "groups": [
            {
                "reading_type": "consumption", "source_type": "solar",
                "activity_type": "irrigation", "reading_count": 2,
                "total_kwh": 10.5, "first_reading_date": "2026-01-02",
                "last_reading_date": "2026-01-03",
            },
            {
                "reading_type": "production", "source_type": "solar",
                "activity_type": "unspecified", "reading_count": 1,
                "total_kwh": 8.0, "first_reading_date": "2026-01-04",
                "last_reading_date": "2026-01-04",
            },
        ],
    }
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize("bad_operator,bad_location", [("bad", str(uuid4())), (str(uuid4()), "bad")])
def test_invalid_energy_scope_fails_before_database_connection(bad_operator, bad_location):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid identifiers must fail before connecting")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_location_energy_summary(bad_operator, bad_location, connection_factory=connection_factory)
    assert not opened


@pytest.fixture
def gateway_audit_spool(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "audit.sqlite3"))
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


def test_energy_route_requires_grant_and_returns_no_store_summary(monkeypatch, gateway_audit_spool):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "energy_monitoring", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    expected = {"location_id": location_id, "unit": "kWh", "verified_reading_count": 0, "groups": []}
    monkeypatch.setattr(
        "services.gateway.energy_monitoring.get_location_energy_summary",
        lambda op, loc: expected if (op, loc) == (operator_id, location_id) else None,
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/energy/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_energy_route_denies_missing_location_grant_before_query(monkeypatch, gateway_audit_spool):
    location_id = str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    called = False

    def unexpected_summary(*_args):
        nonlocal called
        called = True
        raise AssertionError("a missing grant must deny before entering the query")

    monkeypatch.setattr(
        "services.gateway.energy_monitoring.get_location_energy_summary", unexpected_summary
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/energy/{location_id}/summary")

    assert response.status_code == 403
    assert called is False
