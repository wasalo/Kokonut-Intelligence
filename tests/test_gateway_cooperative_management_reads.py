"""Cooperative reads are private, location-scoped, and aggregate-only."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.cooperative_management_reads import (
    get_location_cooperative_management_summary,
)
from services.gateway.operator_auth import auth_route_policy

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "FROM cooperative AS c" in query:
            self.description = [(name,) for name in (
                "cooperative_type", "cooperative_status", "cooperative_count", "active_member_count"
            )]
            self.rows = (("equipment_sharing", "active", 2, 8),)
        elif "FROM shared_asset AS a" in query:
            self.description = [(name,) for name in ("asset_type", "asset_status", "asset_count")]
            self.rows = (("tractor", "available", 1),)
        elif "FROM asset_booking AS b" in query:
            self.description = [(name,) for name in ("booking_status", "booking_count")]
            self.rows = (("confirmed", 3),)

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self):
        self.queries = []
        self.rollback_count = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


def test_summary_sets_signed_location_context_before_scoped_aggregate_queries(monkeypatch):
    connection = _Connection()
    sequence = []
    original_execute = _Cursor.execute

    def execute(self, query, params=None):
        sequence.append("query")
        original_execute(self, query, params)

    def set_context(conn, **kwargs):
        sequence.append("context")
        assert conn is connection
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "cooperative_management",
            "action": "read",
        }

    monkeypatch.setattr(_Cursor, "execute", execute)
    monkeypatch.setattr(
        "services.gateway.cooperative_management_reads.set_operator_tenant_context",
        set_context,
    )
    result = get_location_cooperative_management_summary(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    assert sequence[:4] == ["query", "query", "query", "context"]
    queries = [query for query, _ in connection.queries if "FROM " in query]
    assert len(queries) == 3
    assert connection.queries[:3] == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert all("%s::uuid" in query for query in queries)
    assert all("location_id" in query for query in queries)
    assert "cm.location_id = %s::uuid" in queries[0]
    assert "c.location_id = %s::uuid" in queries[1]
    assert "cm.location_id = %s::uuid" in queries[2]
    assert [params for query, params in connection.queries if "FROM " in query] == [
        (LOCATION_ID, LOCATION_ID),
        (LOCATION_ID, LOCATION_ID),
        (LOCATION_ID, LOCATION_ID, LOCATION_ID),
    ]
    assert "ELSE 'other'" in queries[0]
    assert result == {
        "location_id": LOCATION_ID,
        "cooperatives": [{
            "cooperative_type": "equipment_sharing",
            "cooperative_status": "active",
            "cooperative_count": 2,
            "active_member_count": 8,
        }],
        "assets": [{"asset_type": "tractor", "asset_status": "available", "asset_count": 1}],
        "bookings": [{"booking_status": "confirmed", "booking_count": 3}],
    }
    forbidden = (
        "member_name", "farmer_id", "credential", "kyc", "purpose", "start_time",
        "end_time", "total_cost", "latitude", "longitude", "metadata", "damage_notes",
    )
    assert not any(field in " ".join(queries).lower() for field in forbidden)
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_operator_or_location_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid operator identifier"):
        get_location_cooperative_management_summary("bad", LOCATION_ID, connection_factory=connect)
    with pytest.raises(ValueError, match="Invalid location identifier"):
        get_location_cooperative_management_summary(OPERATOR_ID, "bad", connection_factory=connect)
    assert not called


def test_cooperative_route_policy_is_exact_location_scoped_read_only():
    path = f"/operator/api/cooperatives/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "cooperative_management",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None


def _register_route(monkeypatch, summary):
    from services.gateway.cooperative_management_routes import (
        register_cooperative_management_routes,
    )

    monkeypatch.setattr(
        "services.gateway.cooperative_management_reads.get_location_cooperative_management_summary",
        summary,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_cooperative_management_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_http_summary_is_no_store_and_uses_operator_identity(monkeypatch):
    def summary(operator_id, location_id):
        assert operator_id == OPERATOR_ID
        return {"location_id": location_id, "cooperatives": [], "assets": [], "bookings": []}

    app = _register_route(monkeypatch, summary)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/cooperatives/{LOCATION_ID}/summary")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID


def test_http_summary_denies_missing_signed_grant(monkeypatch):
    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _register_route(monkeypatch, deny)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/cooperatives/{LOCATION_ID}/summary")
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
