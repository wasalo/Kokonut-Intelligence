"""Irrigation status reads are exact-location, bounded, and private."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.irrigation_status import get_location_irrigation_status  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_irrigation_status_policy_is_exact_location_read():
    location_id = str(uuid4())
    path = f"/operator/api/irrigation/{location_id}/status"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "precision_irrigation",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = []
        self.one = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))
        self.conn.events.append("sql")
        if "SELECT COUNT(*)" in query:
            self.one = (2,)
            return
        self.description = [(name,) for name in (
            "id", "name", "zone_code", "soil_type", "area_m2", "depth_cm",
            "zone_status", "target_min_pct", "target_max_pct",
            "irrigation_trigger_pct", "refill_to_pct", "growth_stage",
            "current_moisture_pct", "last_moisture_reading",
            "next_irrigation_start", "next_irrigation_volume_l",
            "next_irrigation_status", "last_irrigation_at", "last_irrigation_volume_l",
        )]
        self.rows = [
            (
                str(uuid4()), "North", "N-1", "loam", Decimal("1000"), Decimal("30"),
                "active", Decimal("40"), Decimal("60"), Decimal("35"), Decimal("65"),
                "vegetative", Decimal("30"), datetime(2026, 10, 22, 8),
                datetime(2026, 10, 24, 6), Decimal("120"), "pending",
                datetime(2026, 10, 20, 7), Decimal("75"),
            ),
            (
                str(uuid4()), "South", "S-1", "sandy loam", Decimal("500"), Decimal("25"),
                "active", Decimal("35"), Decimal("58"), Decimal("30"), Decimal("60"),
                "flowering", Decimal("50"), datetime(2026, 10, 22, 9),
                None, None, None, None, None,
            ),
        ]

    def fetchone(self):
        return self.one

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


def test_irrigation_status_sets_context_before_scoped_queries_and_bounds_output():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "precision_irrigation",
            "action": "read",
        }
        conn.events.append("tenant_context")

    with patch("services.gateway.irrigation_status.set_operator_tenant_context", set_context):
        result = get_location_irrigation_status(
            operator_id,
            location_id,
            limit=1,
            offset=0,
            connection_factory=lambda: conn,
        )

    reads = [(query, params) for query, params in conn.queries if "irrigation_zone" in query]
    assert len(reads) == 2
    assert all("location_id = %s::uuid" in query for query, _ in reads)
    assert conn.queries[0:3] == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.events == ["sql", "sql", "sql", "tenant_context", "sql", "sql"]
    count_query, count_params = reads[0]
    detail_query, detail_params = reads[1]
    assert "status = 'active'" in count_query
    assert "iz.status = 'active'" in detail_query
    assert "sr.location_id = iz.location_id" in detail_query
    assert detail_params == (location_id, 2, 0)
    assert count_params == (location_id,)
    assert result["total_active_zones"] == 2
    assert result["has_more"] is True
    assert result["zones"] == [{
        "zone_id": result["zones"][0]["zone_id"],
        "name": "North",
        "zone_code": "N-1",
        "soil_type": "loam",
        "area_m2": 1000.0,
        "depth_cm": 30.0,
        "zone_status": "active",
        "current_moisture_pct": 30.0,
        "last_moisture_reading": "2026-10-22T08:00:00",
        "moisture_status": "below_trigger",
        "target_min_pct": 40.0,
        "target_max_pct": 60.0,
        "irrigation_trigger_pct": 35.0,
        "refill_to_pct": 65.0,
        "growth_stage": "vegetative",
        "next_irrigation_start": "2026-10-24T06:00:00",
        "next_irrigation_volume_l": 120.0,
        "next_irrigation_status": "pending",
        "last_irrigation_at": "2026-10-20T07:00:00",
        "last_irrigation_volume_l": 75.0,
    }]
    assert "sensor_device_id" not in result["zones"][0]
    assert "metadata" not in result["zones"][0]
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (51, 0), (25, -1), (25, 10_001), (True, 0)],
)
def test_irrigation_status_rejects_invalid_page_before_database(limit, offset):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid selectors must fail before opening PostgreSQL")

    with pytest.raises(ValueError):
        get_location_irrigation_status(
            str(uuid4()), str(uuid4()), limit=limit, offset=offset,
            connection_factory=connection_factory,
        )
    assert opened is False


def test_irrigation_status_rejects_invalid_location_before_database():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid UUID must fail before connecting")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        get_location_irrigation_status(
            str(uuid4()), "not-a-location", connection_factory=connection_factory
        )
    assert opened is False


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


def test_irrigation_status_route_authenticates_and_returns_no_store(
    monkeypatch, gateway_audit_spool
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "precision_irrigation", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.irrigation_status.get_location_irrigation_status",
        lambda op, loc, **_kwargs: {
            "location_id": loc, "total_active_zones": 0, "zones": []
        },
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/irrigation/{location_id}/status")

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_irrigation_status_route_denies_missing_location_grant_before_handler(
    monkeypatch, gateway_audit_spool
):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
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

    def unexpected_status(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("a missing tenant grant must deny before data access")

    monkeypatch.setattr(
        "services.gateway.irrigation_status.get_location_irrigation_status",
        unexpected_status,
    )
    location_id = str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/irrigation/{location_id}/status")

    assert response.status_code == 403
    assert called is False


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=51", "offset=-1", "offset=10001"]
)
def test_irrigation_route_publishes_and_enforces_pagination_bounds(
    monkeypatch, gateway_audit_spool, query
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "precision_irrigation", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    called = False

    def unexpected_status(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("invalid pagination must fail before service invocation")

    monkeypatch.setattr(
        "services.gateway.irrigation_status.get_location_irrigation_status",
        unexpected_status,
    )
    app = create_app()
    path = f"/operator/api/irrigation/{location_id}/status"
    parameters = app.openapi()["paths"]["/operator/api/irrigation/{location_id}/status"]["get"]["parameters"]
    by_name = {parameter["name"]: parameter["schema"] for parameter in parameters}
    assert by_name["limit"]["default"] == 25
    assert by_name["limit"]["minimum"] == 1
    assert by_name["limit"]["maximum"] == 50
    assert by_name["offset"]["default"] == 0
    assert by_name["offset"]["minimum"] == 0
    assert by_name["offset"]["maximum"] == 10_000

    with TestClient(app, cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"{path}?{query}")

    assert response.status_code == 422
    assert called is False
