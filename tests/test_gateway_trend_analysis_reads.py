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
    get_location_time_series_forecast,
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
        elif "FROM time_series_forecast" in query:
            self.description = [(name,) for name in (
                "metric_key", "model_type", "forecast_values", "intervals",
                "interval_confidence", "forecast_horizon", "time_unit",
                "training_points", "status", "truncated", "forecast_at",
            )]
            self.rows = ((
                "soil_carbon", "arima", [4.0, float("inf"), "invalid"],
                [
                    {"step": 1, "forecast": 4.0, "lower": 3.0, "upper": 5.0, "private": "omit"},
                    {"step": True, "forecast": float("nan"), "lower": None, "upper": 6.0},
                ],
                0.95, 2, "day", 30, "active", True, "2026-03-03",
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


def test_forecast_read_is_signed_scoped_bounded_and_fixed_projection(monkeypatch):
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
    result = get_location_time_series_forecast(
        OPERATOR_ID,
        LOCATION_ID,
        "soil_carbon",
        connection_factory=lambda: connection,
    )

    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM time_series_forecast" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "AND metric_key = %s" in query
    assert "ORDER BY forecast_at DESC, id DESC" in query
    assert "$[0 to 99]" in query and "model_params" not in query and "metadata" not in query
    assert "THEN jsonb_array_length(forecast_values) > 100 ELSE FALSE END" in query
    assert "AND jsonb_array_length(forecast_values)" not in query
    assert params == (LOCATION_ID, "soil_carbon")
    assert result["item"]["forecast_values"] == [4.0, None, None]
    assert result["item"]["intervals"] == [
        {"step": 1, "forecast": 4.0, "lower": 3.0, "upper": 5.0},
        {"step": 2, "forecast": None, "lower": None, "upper": 6.0},
    ]
    assert result["item"]["truncated"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_forecast_metric_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="metric_key must be"):
        get_location_time_series_forecast(
            OPERATOR_ID, LOCATION_ID, "bad\tkey", connection_factory=connect
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
    forecast_path = f"/operator/api/trends/{LOCATION_ID}/forecast"
    assert auth_route_policy("GET", forecast_path, enabled=True) == {
        "resource": "trend_analysis",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", forecast_path, enabled=True) == {
        "resource": "trend_analysis",
        "action": "compute",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("DELETE", forecast_path, enabled=True) is None


def test_forecast_create_openapi_publishes_strict_request_and_created_reused_results(monkeypatch):
    app = _register_route(monkeypatch, lambda *_args, **_kwargs: {})
    operation = app.openapi()["paths"]["/operator/api/trends/{location_id}/forecast"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    responses = app.openapi()["components"]["schemas"]
    result_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]

    assert request_schema["additionalProperties"] is False
    assert set(request_schema["properties"]) == {
        "metric_key", "forecast_horizon", "confidence"
    }
    assert request_schema["required"] == ["metric_key"]
    assert request_schema["properties"]["forecast_horizon"]["minimum"] == 1
    assert request_schema["properties"]["forecast_horizon"]["maximum"] == 100
    assert request_schema["properties"]["confidence"]["enum"] == [0.9, 0.95, 0.99]
    assert result_schema["discriminator"]["propertyName"] == "created"
    assert {ref.rsplit("/", 1)[-1] for ref in result_schema["discriminator"]["mapping"].values()} == {
        "TrendForecastCreatedResponse", "TrendForecastReusedResponse"
    }
    assert responses["TrendForecastCreatedResponse"]["additionalProperties"] is False
    assert "forecast_at" in responses["TrendForecastCreatedResponse"]["properties"]
    assert "forecast_at" not in responses["TrendForecastReusedResponse"]["properties"]
    created_result_schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert created_result_schema["oneOf"] == result_schema["oneOf"]
    assert created_result_schema["discriminator"] == result_schema["discriminator"]


@pytest.mark.parametrize(
    ("created", "expected_status", "includes_forecast_at"),
    [(True, 201, True), (False, 200, False)],
)
def test_forecast_create_preserves_created_and_reused_response_shapes(
    monkeypatch, created, expected_status, includes_forecast_at
):
    forecast_id = "33333333-3333-4333-8333-333333333333"
    result = {
        "location_id": LOCATION_ID,
        "metric_key": "soil_carbon",
        "forecast_id": forecast_id,
        "status": "active",
        "created": created,
        "forecast_horizon": 12,
        "time_unit": "day",
        "training_points": 3,
    }
    if includes_forecast_at:
        result["forecast_at"] = "2026-10-29T12:00:00+00:00"
    calls = []

    def writer(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    app = _register_route(monkeypatch, lambda *_args, **_kwargs: {}, forecast_writer=writer)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast",
            json={"metric_key": "soil_carbon", "forecast_horizon": 12, "confidence": 0.95},
        )

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    expected = dict(result)
    if includes_forecast_at:
        expected["forecast_at"] = "2026-10-29T12:00:00Z"
    assert response.json() == expected
    assert calls == [
        ((OPERATOR_ID, LOCATION_ID, "soil_carbon"), {"forecast_horizon": 12, "confidence": 0.95})
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"forecast_horizon": 12},
        {"metric_key": "soil_carbon", "forecast_horizon": 0},
        {"metric_key": "soil_carbon", "forecast_horizon": 101},
        {"metric_key": "soil_carbon", "forecast_horizon": True},
        {"metric_key": "soil_carbon", "confidence": 0.93},
        {"metric_key": "soil_carbon", "confidence": "0.95"},
        {"metric_key": "soil_carbon", "confidence": True},
        {"metric_key": " soil_carbon "},
        {"metric_key": "soil_carbon", "unexpected": "field"},
    ],
)
def test_invalid_forecast_create_request_fails_before_service(monkeypatch, payload):
    calls = []

    def writer(*args, **kwargs):
        calls.append((args, kwargs))
        return {}

    app = _register_route(monkeypatch, lambda *_args, **_kwargs: {}, forecast_writer=writer)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast", json=payload
        )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Forecast request is invalid"}
    assert calls == []


@pytest.mark.parametrize(
    "result",
    [
        {"created": True},
        {
            "location_id": "99999999-9999-4999-8999-999999999999",
            "metric_key": "soil_carbon",
            "forecast_id": "33333333-3333-4333-8333-333333333333",
            "status": "active",
            "created": True,
            "forecast_horizon": 12,
            "time_unit": "day",
            "training_points": 3,
            "forecast_at": "2026-10-29T12:00:00+00:00",
        },
        {
            "location_id": LOCATION_ID,
            "metric_key": "soil_carbon",
            "forecast_id": "33333333-3333-4333-8333-333333333333",
            "status": "active",
            "created": False,
            "forecast_horizon": 12,
            "time_unit": "day",
            "training_points": 3,
            "forecast_at": "2026-10-29T12:00:00+00:00",
        },
    ],
)
def test_malformed_or_mismatched_forecast_result_fails_closed(monkeypatch, result):
    app = _register_route(
        monkeypatch, lambda *_args, **_kwargs: {}, forecast_writer=lambda *_args, **_kwargs: result
    )
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast",
            json={"metric_key": "soil_carbon"},
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Trend forecast compute unavailable"}


def _register_route(
    monkeypatch, reader, smoothing_reader=None, change_points_reader=None,
    decomposition_reader=None, forecast_reader=None, forecast_writer=None,
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
    if forecast_reader is not None:
        monkeypatch.setattr(
            "services.gateway.trend_analysis_reads.get_location_time_series_forecast",
            forecast_reader,
        )
    if forecast_writer is not None:
        monkeypatch.setattr(
            "services.gateway.trend_forecast_compute.create_location_time_series_forecast",
            forecast_writer,
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


def test_forecast_http_route_is_no_store_and_passes_metric_key(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def forecast_reader(operator_id, location_id, metric_key):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert metric_key == "soil_carbon"
        return {"location_id": location_id, "metric_key": metric_key, "item": None}

    app = _register_route(monkeypatch, estimates_reader, forecast_reader=forecast_reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/forecast?metric_key=soil_carbon"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["item"] is None


def test_forecast_http_route_denies_missing_tenant_grant(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _register_route(monkeypatch, estimates_reader, forecast_reader=deny)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/trends/{LOCATION_ID}/forecast?metric_key=soil_carbon"
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_forecast_compute_http_route_is_no_store_and_passes_bounded_request(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def forecast_writer(operator_id, location_id, metric_key, *, forecast_horizon, confidence):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert metric_key == "soil_carbon"
        assert forecast_horizon == 12
        assert confidence == 0.95
        return {
            "location_id": location_id,
            "metric_key": metric_key,
            "forecast_id": "33333333-3333-4333-8333-333333333333",
            "status": "active",
            "created": True,
            "forecast_horizon": forecast_horizon,
            "time_unit": "day",
            "training_points": 3,
            "forecast_at": "2026-10-29T12:00:00+00:00",
        }

    app = _register_route(
        monkeypatch, estimates_reader, forecast_writer=forecast_writer
    )
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast",
            json={"metric_key": "soil_carbon", "forecast_horizon": 12, "confidence": 0.95},
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["created"] is True


def test_forecast_compute_http_route_denies_missing_tenant_grant(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing compute grant")

    app = _register_route(monkeypatch, estimates_reader, forecast_writer=deny)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast",
            json={"metric_key": "soil_carbon"},
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_forecast_compute_http_route_rejects_unknown_fields_before_writer(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("invalid body must fail before compute")

    app = _register_route(monkeypatch, estimates_reader, forecast_writer=should_not_run)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast",
            json={"metric_key": "soil_carbon", "arbitrary_sql": "SELECT 1"},
        )
    assert response.status_code == 400


def test_forecast_compute_http_route_bounds_request_body_before_writer(monkeypatch):
    def estimates_reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("oversized body must fail before compute")

    app = _register_route(monkeypatch, estimates_reader, forecast_writer=should_not_run)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/trends/{LOCATION_ID}/forecast",
            content=b" " * 4097,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert "4 KiB" in response.json()["error"]


def test_paged_trend_routes_publish_service_bounds_in_openapi(monkeypatch):
    def reader(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "items": [], "limit": 25, "offset": 0, "has_more": False}

    app = _register_route(monkeypatch, reader)
    openapi = app.openapi()["paths"]
    expected = {
        "/operator/api/trends/{location_id}/estimates": {
            "limit": (25, 1, 50),
            "offset": (0, 0, 10_000),
        },
        "/operator/api/trends/{location_id}/change-points": {
            "limit": (100, 1, 100),
        },
        "/operator/api/trends/{location_id}/smoothing": {
            "limit": (100, 1, 100),
        },
    }
    for path, bounds in expected.items():
        parameters = {
            parameter["name"]: parameter["schema"]
            for parameter in openapi[path]["get"]["parameters"]
        }
        for name, (default, minimum, maximum) in bounds.items():
            assert parameters[name]["default"] == default
            assert parameters[name]["minimum"] == minimum
            assert parameters[name]["maximum"] == maximum


@pytest.mark.parametrize(
    ("path", "query"),
    [
        ("estimates", "limit=0"),
        ("estimates", "limit=51"),
        ("estimates", "offset=-1"),
        ("estimates", "offset=10001"),
        ("change-points", "metric_key=soil_carbon&limit=0"),
        ("change-points", "metric_key=soil_carbon&limit=101"),
        ("smoothing", "metric_key=soil_carbon&limit=0"),
        ("smoothing", "metric_key=soil_carbon&limit=101"),
    ],
)
def test_invalid_trend_page_bounds_fail_before_service(monkeypatch, path, query):
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("invalid pagination reached service")

    app = _register_route(
        monkeypatch,
        should_not_run,
        smoothing_reader=should_not_run,
        change_points_reader=should_not_run,
    )
    with TestClient(app) as client:
        response = client.get(f"/operator/api/trends/{LOCATION_ID}/{path}?{query}")
    assert response.status_code == 422
    assert not called


_TREND_TIMESTAMP = "2026-03-03T12:00:00+00:00"
_TREND_READ_PROJECTIONS = {
    "estimates": {
        "location_id": LOCATION_ID,
        "items": [{
            "metric_key": "soil_carbon",
            "period_start": "2026-01-01T00:00:00+00:00",
            "period_end": "2026-03-01T00:00:00+00:00",
            "data_points": 10,
            "slope": 0.1,
            "intercept": 1.0,
            "r_squared": 0.8,
            "standard_error": 0.01,
            "slope_p_value": 0.02,
            "direction": "improving",
            "confidence_level": "high",
            "slope_ci_lower": 0.08,
            "slope_ci_upper": 0.12,
            "time_unit": "day",
            "computed_at": _TREND_TIMESTAMP,
        }],
        "limit": 1,
        "offset": 0,
        "has_more": False,
    },
    "smoothing": {
        "location_id": LOCATION_ID,
        "metric_key": "soil_carbon",
        "items": [{
            "metric_key": "soil_carbon",
            "smoothing_type": "exponential",
            "timestamp": _TREND_TIMESTAMP,
            "original_value": 4.0,
            "smoothed_value": 3.5,
            "computed_at": _TREND_TIMESTAMP,
        }],
    },
    "change-points": {
        "location_id": LOCATION_ID,
        "metric_key": "soil_carbon",
        "items": [{
            "metric_key": "soil_carbon",
            "detection_method": "cusum",
            "change_point_index": 14,
            "change_point_timestamp": _TREND_TIMESTAMP,
            "magnitude": 0.7,
            "direction": "increase",
            "confidence": 0.9,
            "segment_count": 2,
            "status": "confirmed",
            "detected_at": _TREND_TIMESTAMP,
        }],
    },
    "decomposition": {
        "location_id": LOCATION_ID,
        "metric_key": "soil_carbon",
        "item": {
            "metric_key": "soil_carbon",
            "decomposition_method": "stl",
            "period": 12,
            "trend_component": [1.0, 2.0, None],
            "seasonal_component": [0.2, 0.3, 0.4],
            "residual_component": [None, -0.1, None],
            "seasonal_strength": 0.7,
            "trend_strength": 0.8,
            "residual_variance": 0.05,
            "data_points": 240,
            "trend_component_points": 240,
            "seasonal_component_points": 240,
            "residual_component_points": 240,
            "truncated": True,
            "computed_at": _TREND_TIMESTAMP,
        },
    },
    "forecast": {
        "location_id": LOCATION_ID,
        "metric_key": "soil_carbon",
        "item": {
            "metric_key": "soil_carbon",
            "model_type": "arima",
            "forecast_values": [4.2],
            "intervals": [{"step": 1, "forecast": 4.2, "lower": 3.8, "upper": 4.6}],
            "interval_confidence": 0.95,
            "forecast_horizon": 1,
            "time_unit": "day",
            "training_points": 30,
            "status": "active",
            "truncated": False,
            "forecast_at": _TREND_TIMESTAMP,
        },
    },
}


def _trend_response_app(monkeypatch, route_name, result):
    def empty_estimates(*_args, **_kwargs):
        return {
            "location_id": LOCATION_ID,
            "items": [],
            "limit": 25,
            "offset": 0,
            "has_more": False,
        }

    def selected(name):
        def read(*_args, **_kwargs):
            if route_name == name:
                return result
            if name == "estimates":
                return empty_estimates()
            return {
                "location_id": LOCATION_ID,
                "metric_key": "soil_carbon",
                "items": [],
            }

        return read

    return _register_route(
        monkeypatch,
        selected("estimates"),
        smoothing_reader=selected("smoothing"),
        change_points_reader=selected("change-points"),
        decomposition_reader=selected("decomposition"),
        forecast_reader=selected("forecast"),
    )


@pytest.mark.parametrize(
    ("route_name", "query"),
    [
        ("estimates", "?limit=1&offset=0"),
        ("smoothing", "?metric_key=soil_carbon&limit=1"),
        ("change-points", "?metric_key=soil_carbon&limit=1"),
        ("decomposition", "?metric_key=soil_carbon"),
        ("forecast", "?metric_key=soil_carbon"),
    ],
)
def test_saved_trend_read_response_models_accept_safe_projections(
    monkeypatch, route_name, query
):
    app = _trend_response_app(monkeypatch, route_name, _TREND_READ_PROJECTIONS[route_name])
    with TestClient(app) as client:
        response = client.get(f"/operator/api/trends/{LOCATION_ID}/{route_name}{query}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID


@pytest.mark.parametrize(
    ("route_name", "query"),
    [
        ("estimates", "?limit=1&offset=0"),
        ("smoothing", "?metric_key=soil_carbon&limit=1"),
        ("change-points", "?metric_key=soil_carbon&limit=1"),
        ("decomposition", "?metric_key=soil_carbon"),
        ("forecast", "?metric_key=soil_carbon"),
    ],
)
def test_saved_trend_read_rejects_unknown_projection_fields_without_leaking(
    monkeypatch, route_name, query
):
    result = dict(_TREND_READ_PROJECTIONS[route_name])
    result["unselected_private_payload"] = "must not be returned"
    app = _trend_response_app(monkeypatch, route_name, result)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/trends/{LOCATION_ID}/{route_name}{query}")
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    expected_error = {
        "estimates": "Trend estimates unavailable",
        "smoothing": "Trend smoothing unavailable",
        "change-points": "Trend change-point read unavailable",
        "decomposition": "Trend decomposition unavailable",
        "forecast": "Trend forecast unavailable",
    }
    assert response.json() == {"error": expected_error[route_name]}


def test_saved_trend_get_routes_publish_success_models_in_openapi(monkeypatch):
    app = _trend_response_app(monkeypatch, "estimates", _TREND_READ_PROJECTIONS["estimates"])
    paths = app.openapi()["paths"]
    for route_name in _TREND_READ_PROJECTIONS:
        path = f"/operator/api/trends/{{location_id}}/{route_name}"
        assert "schema" in paths[path]["get"]["responses"]["200"]["content"]["application/json"]
