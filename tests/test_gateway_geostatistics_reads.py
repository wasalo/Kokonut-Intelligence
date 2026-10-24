"""Saved geostatistics reads require exact signed location grants."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.geostatistics_reads import list_location_spatial_autocorrelation
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
        if "FROM spatial_autocorrelation" in query:
            self.description = [(name,) for name in (
                "property_key", "metric", "statistic_value", "expected_value",
                "p_value", "z_score", "n_samples", "spatial_weights_type",
                "distance_threshold", "k_neighbors", "computed_at",
            )]
            self.rows = (
                ("soil_carbon", "morans_i", 0.7, 0.1, float("nan"), 2.1, 30,
                 "knn", float("inf"), 8, "2026-03-03"),
                ("soil_carbon", "gearys_c", 0.8, 1.0, 0.03, 2.4, 30,
                 "distance", 500.0, None, "2026-03-02"),
            )

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


def test_autocorrelation_read_sets_signed_scope_and_filters_exact_location(monkeypatch):
    connection = _Connection()
    order = []
    original_execute = _Cursor.execute

    def execute(self, query, params=None):
        order.append("query")
        original_execute(self, query, params)

    def set_context(conn, **kwargs):
        order.append("context")
        assert conn is connection
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "geostatistics",
            "action": "read",
        }

    monkeypatch.setattr(_Cursor, "execute", execute)
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.set_operator_tenant_context", set_context
    )
    result = list_location_spatial_autocorrelation(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=4,
        connection_factory=lambda: connection,
    )

    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM spatial_autocorrelation" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "DISTINCT ON (property_key, metric)" in query
    assert "ORDER BY property_key, metric, computed_at DESC, id DESC" in query
    assert "interpretation" not in query and "metadata" not in query
    assert params == (LOCATION_ID, 2, 4)
    assert result["location_id"] == LOCATION_ID
    assert result["items"][0]["metric"] == "morans_i"
    assert result["items"][0]["p_value"] is None
    assert result["items"][0]["distance_threshold"] is None
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_autocorrelation_scope_or_page_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        list_location_spatial_autocorrelation(
            OPERATOR_ID, "bad", connection_factory=connect
        )
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_spatial_autocorrelation(
            OPERATOR_ID, LOCATION_ID, limit=51, connection_factory=connect
        )
    with pytest.raises(ValueError, match="offset must be between"):
        list_location_spatial_autocorrelation(
            OPERATOR_ID, LOCATION_ID, offset=-1, connection_factory=connect
        )
    assert not called


def test_geostatistics_route_policy_is_exact_location_scoped_read_only():
    path = f"/operator/api/geostatistics/{LOCATION_ID}/autocorrelation"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None


def _app(monkeypatch, reader):
    from services.gateway.geostatistics_routes import register_geostatistics_routes

    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_spatial_autocorrelation",
        reader,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_geostatistics_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_http_route_is_no_store_and_passes_page_scope(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert limit == 3
        assert offset == 6
        return {
            "location_id": location_id,
            "items": [],
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }

    app = _app(monkeypatch, reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/autocorrelation?limit=3&offset=6"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 6


def test_http_route_denies_missing_tenant_grant(monkeypatch):
    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _app(monkeypatch, deny)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/autocorrelation"
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
