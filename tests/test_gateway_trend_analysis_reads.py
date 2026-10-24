"""Saved trend reads use a signed location scope and bounded paging."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.operator_auth import auth_route_policy
from services.gateway.trend_analysis_reads import list_location_trend_estimates

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
        if "FROM trend_estimate" in query:
            self.description = [(name,) for name in (
                "metric_key", "period_start", "period_end", "data_points", "slope",
                "intercept", "r_squared", "standard_error", "slope_p_value", "direction",
                "confidence_level", "slope_ci_lower", "slope_ci_upper", "time_unit", "computed_at",
            )]
            self.rows = (
                ("soil_carbon", "2026-01-01", "2026-03-01", 10, 0.1, 1.0, float("nan"), 0.01,
                 0.02, "improving", "high", 0.08, 0.12, "day", "2026-03-02"),
                ("water_use", "2026-01-01", "2026-03-01", 8, -0.1, 2.0, 0.8, 0.02,
                 0.04, "declining", "moderate", -0.12, -0.08, "day", "2026-03-01"),
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


def test_latest_estimate_pages_set_tenant_context_before_exact_location_query(monkeypatch):
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
            "resource": "trend_analysis",
            "action": "read",
        }

    monkeypatch.setattr(_Cursor, "execute", execute)
    monkeypatch.setattr(
        "services.gateway.trend_analysis_reads.set_operator_tenant_context", set_context
    )
    result = list_location_trend_estimates(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=2,
        connection_factory=lambda: connection,
    )

    assert order[:4] == ["query", "query", "query", "context"]
    query, params = next((query, params) for query, params in connection.queries if "FROM trend_estimate" in query)
    assert "DISTINCT ON (metric_key)" in query
    assert "WHERE location_id = %s::uuid" in query
    assert "ORDER BY metric_key, computed_at DESC, id DESC" in query
    assert "model_params" not in query and "metadata" not in query and "computed_by" not in query
    assert params == (LOCATION_ID, 2, 2)
    assert result["has_more"] is True
    assert result["items"] == [{
        "metric_key": "soil_carbon",
        "period_start": "2026-01-01",
        "period_end": "2026-03-01",
        "data_points": 10,
        "slope": 0.1,
        "intercept": 1.0,
        "r_squared": None,
        "standard_error": 0.01,
        "slope_p_value": 0.02,
        "direction": "improving",
        "confidence_level": "high",
        "slope_ci_lower": 0.08,
        "slope_ci_upper": 0.12,
        "time_unit": "day",
        "computed_at": "2026-03-02",
    }]
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_scope_or_page_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        list_location_trend_estimates(OPERATOR_ID, "bad", connection_factory=connect)
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_trend_estimates(OPERATOR_ID, LOCATION_ID, limit=51, connection_factory=connect)
    with pytest.raises(ValueError, match="offset must be between"):
        list_location_trend_estimates(OPERATOR_ID, LOCATION_ID, offset=-1, connection_factory=connect)
    assert not called


def test_trend_route_policy_is_exact_location_scoped_read_only():
    path = f"/operator/api/trends/{LOCATION_ID}/estimates"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "trend_analysis",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None


def _register_route(monkeypatch, reader):
    from services.gateway.trend_analysis_routes import register_trend_analysis_routes

    monkeypatch.setattr(
        "services.gateway.trend_analysis_reads.list_location_trend_estimates", reader
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_trend_analysis_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_http_route_is_no_store_and_passes_page_and_operator(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert limit == 3
        assert offset == 6
        return {"location_id": location_id, "items": [], "limit": limit, "offset": offset, "has_more": False}

    app = _register_route(monkeypatch, reader)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/trends/{LOCATION_ID}/estimates?limit=3&offset=6")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 6


def test_http_route_denies_missing_tenant_grant(monkeypatch):
    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _register_route(monkeypatch, deny)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/trends/{LOCATION_ID}/estimates")
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
