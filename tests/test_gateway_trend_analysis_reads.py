"""Saved trend reads use a signed location scope and bounded paging."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.operator_auth import auth_route_policy
from services.gateway.trend_analysis_reads import (
    get_location_seasonal_decomposition,
    list_location_change_points,
    list_location_trend_estimates,
    list_location_trend_smoothing,
)

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
        elif "FROM trend_smoothing" in query:
            self.description = [(name,) for name in (
                "metric_key", "smoothing_type", "timestamp", "original_value",
                "smoothed_value", "computed_at",
            )]
            self.rows = (
                ("soil_carbon", "moving_average", "2026-03-02", 4.0, float("inf"), "2026-03-03"),
                ("soil_carbon", "exponential", "2026-03-01", 3.0, 3.5, "2026-03-02"),
            )
        elif "FROM change_point" in query:
            self.description = [(name,) for name in (
                "metric_key", "detection_method", "change_point_index",
                "change_point_timestamp", "magnitude", "direction", "confidence",
                "segment_count", "status", "detected_at",
            )]
            self.rows = (
                ("soil_carbon", "cusum", 14, "2026-03-02", 0.7, "increase", float("nan"), 2, "confirmed", "2026-03-03"),
                ("soil_carbon", "pelt", 10, "2026-03-01", 0.4, "variance_change", 0.9, 3, "detected", "2026-03-02"),
            )
        elif "FROM seasonal_decomposition" in query:
            self.description = [(name,) for name in (
                "metric_key", "decomposition_method", "period", "trend_component",
                "seasonal_component", "residual_component", "seasonal_strength",
                "trend_strength", "residual_variance", "data_points",
                "trend_component_points", "seasonal_component_points",
                "residual_component_points", "truncated", "computed_at",
            )]
            self.rows = ((
                "soil_carbon", "stl", 12, [1.0, 2.0, float("nan")],
                [0.2, 0.3, 0.4], [None, -0.1, "invalid"], float("inf"),
                0.8, 0.05, 240, 240, 240, 240, True, "2026-03-03",
            ),)

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


def test_smoothing_read_uses_signed_scope_and_only_selected_metric(monkeypatch):
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
    result = list_location_trend_smoothing(
        OPERATOR_ID,
        LOCATION_ID,
        "soil_carbon",
        limit=2,
        connection_factory=lambda: connection,
    )

    query, params = next(
        (query, params) for query, params in connection.queries if "FROM trend_smoothing" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "AND metric_key = %s" in query
    assert "ORDER BY timestamp DESC, computed_at DESC, id DESC" in query
    assert "alpha" not in query and "beta" not in query and "metadata" not in query
    assert params == (LOCATION_ID, "soil_carbon", 2)
    assert result["location_id"] == LOCATION_ID
    assert result["metric_key"] == "soil_carbon"
    assert result["items"][0]["smoothed_value"] is None
    assert result["items"][1]["smoothed_value"] == 3.5
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_smoothing_key_or_limit_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="metric_key must be"):
        list_location_trend_smoothing(
            OPERATOR_ID, LOCATION_ID, "\nunsafe", connection_factory=connect
        )
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_trend_smoothing(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", limit=101, connection_factory=connect
        )
    assert not called


def test_change_point_read_uses_signed_scope_and_preserves_stored_status(monkeypatch):
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
    result = list_location_change_points(
        OPERATOR_ID,
        LOCATION_ID,
        "soil_carbon",
        limit=2,
        connection_factory=lambda: connection,
    )

    query, params = next(
        (query, params) for query, params in connection.queries if "FROM change_point" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "AND metric_key = %s" in query
    assert "ORDER BY detected_at DESC, id DESC" in query
    assert "metadata" not in query and "classification" not in query
    assert params == (LOCATION_ID, "soil_carbon", 2)
    assert result["location_id"] == LOCATION_ID
    assert result["metric_key"] == "soil_carbon"
    assert result["items"][0]["status"] == "confirmed"
    assert result["items"][0]["confidence"] is None
    assert result["items"][1]["status"] == "detected"
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_change_point_key_or_limit_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="metric_key must be"):
        list_location_change_points(
            OPERATOR_ID, LOCATION_ID, "bad\tkey", connection_factory=connect
        )
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_change_points(
            OPERATOR_ID, LOCATION_ID, "soil_carbon", limit=101, connection_factory=connect
        )
    assert not called


def test_seasonal_decomposition_read_is_signed_scoped_and_bounded(monkeypatch):
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
    result = get_location_seasonal_decomposition(
        OPERATOR_ID,
        LOCATION_ID,
        "soil_carbon",
        connection_factory=lambda: connection,
    )

    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM seasonal_decomposition" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "AND metric_key = %s" in query
    assert "ORDER BY computed_at DESC, id DESC" in query
    assert "jsonb_path_query_array" in query and "$[0 to 199]" in query
    assert "metadata" not in query
    assert params == (LOCATION_ID, "soil_carbon")
    assert result["location_id"] == LOCATION_ID
    assert result["metric_key"] == "soil_carbon"
    assert result["item"]["decomposition_method"] == "stl"
    assert result["item"]["trend_component"] == [1.0, 2.0, None]
    assert result["item"]["residual_component"] == [None, -0.1, None]
    assert result["item"]["seasonal_strength"] is None
    assert result["item"]["truncated"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_decomposition_key_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="metric_key must be"):
        get_location_seasonal_decomposition(
            OPERATOR_ID, LOCATION_ID, "bad\nkey", connection_factory=connect
        )
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
    smoothing_path = f"/operator/api/trends/{LOCATION_ID}/smoothing"
    assert auth_route_policy("GET", smoothing_path, enabled=True) == {
        "resource": "trend_analysis",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", smoothing_path, enabled=True) is None
    change_points_path = f"/operator/api/trends/{LOCATION_ID}/change-points"
    assert auth_route_policy("GET", change_points_path, enabled=True) == {
        "resource": "trend_analysis",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", change_points_path, enabled=True) is None
    decomposition_path = f"/operator/api/trends/{LOCATION_ID}/decomposition"
    assert auth_route_policy("GET", decomposition_path, enabled=True) == {
        "resource": "trend_analysis",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", decomposition_path, enabled=True) is None


def _register_route(
    monkeypatch, reader, smoothing_reader=None, change_points_reader=None,
    decomposition_reader=None,
):
    from services.gateway.trend_analysis_routes import register_trend_analysis_routes

    monkeypatch.setattr(
        "services.gateway.trend_analysis_reads.list_location_trend_estimates", reader
    )
    if smoothing_reader is not None:
        monkeypatch.setattr(
            "services.gateway.trend_analysis_reads.list_location_trend_smoothing",
            smoothing_reader,
        )
    if change_points_reader is not None:
        monkeypatch.setattr(
            "services.gateway.trend_analysis_reads.list_location_change_points",
            change_points_reader,
        )
    if decomposition_reader is not None:
        monkeypatch.setattr(
            "services.gateway.trend_analysis_reads.get_location_seasonal_decomposition",
            decomposition_reader,
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


def test_smoothing_http_route_is_no_store_and_passes_metric_key(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {
            "location_id": LOCATION_ID,
            "items": [],
            "limit": 25,
            "offset": 0,
            "has_more": False,
        }

    def smoothing_reader(operator_id, location_id, metric_key, *, limit):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert metric_key == "soil_carbon"
        assert limit == 40
        return {"location_id": location_id, "metric_key": metric_key, "items": []}

    app = _register_route(monkeypatch, estimates_reader, smoothing_reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/smoothing?metric_key=soil_carbon&limit=40"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["metric_key"] == "soil_carbon"


def test_smoothing_http_route_denies_missing_tenant_grant(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {
            "location_id": LOCATION_ID,
            "items": [],
            "limit": 25,
            "offset": 0,
            "has_more": False,
        }

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _register_route(monkeypatch, estimates_reader, deny)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/smoothing?metric_key=soil_carbon"
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_change_points_http_route_is_no_store_and_passes_metric_key(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def change_points_reader(operator_id, location_id, metric_key, *, limit):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert metric_key == "soil_carbon"
        assert limit == 40
        return {"location_id": location_id, "metric_key": metric_key, "items": []}

    app = _register_route(monkeypatch, estimates_reader, change_points_reader=change_points_reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/change-points?metric_key=soil_carbon&limit=40"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["metric_key"] == "soil_carbon"


def test_change_points_http_route_denies_missing_tenant_grant(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _register_route(monkeypatch, estimates_reader, change_points_reader=deny)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/change-points?metric_key=soil_carbon"
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_decomposition_http_route_is_no_store_and_passes_metric_key(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def decomposition_reader(operator_id, location_id, metric_key):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert metric_key == "soil_carbon"
        return {"location_id": location_id, "metric_key": metric_key, "item": None}

    app = _register_route(
        monkeypatch, estimates_reader, decomposition_reader=decomposition_reader
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/decomposition?metric_key=soil_carbon"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["item"] is None


def test_decomposition_http_route_denies_missing_tenant_grant(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _register_route(
        monkeypatch, estimates_reader, decomposition_reader=deny
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/decomposition?metric_key=soil_carbon"
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
