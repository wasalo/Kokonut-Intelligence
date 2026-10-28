"""Saved geostatistics reads require exact signed location grants."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.geostatistics_reads import (
    GeostatisticalKrigingNotFound,
    _safe_spatial_fold_diagnostics,
    list_location_cross_validation,
    list_location_kriging_points,
    list_location_kriging_summaries,
    list_location_realization_points,
    list_location_realization_summaries,
    list_location_sensor_network_designs,
    list_location_spatial_autocorrelation,
    list_location_variogram_models,
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
        elif "FROM geostat_cv_result" in query:
            self.description = [(name,) for name in (
                "property_key", "cv_strategy", "n_folds", "block_size_m",
                "mean_error", "mean_squared_error", "root_mean_squared_error",
                "mean_absolute_error", "r_squared", "computed_at", "fold_diagnostics",
            )]
            self.rows = (
                ("soil_carbon", "spatial_block", 5, 250.0, 0.1, 2.0,
                 1.4, 0.9, float("nan"), "2026-03-04", [
                     {"train_samples": "30", "test_samples": "5", "mean_error": "0.1",
                      "mean_squared_error": "2.0", "rmse": "1.4", "mae": "0.9",
                      "r_squared": "NaN", "block_id": "private"}
                 ] * 5),
                ("soil_carbon", "k_fold", 5, None, 0.0, 1.0,
                 1.0, 0.8, 0.7, "2026-03-03", [
                     {"actual": "private", "predicted": "private"}
                 ] * 5),
            )
        elif "FROM variogram_model" in query:
            self.description = [(name,) for name in (
                "property_key", "model_type", "sill", "range", "nugget",
                "partial_sill", "lag_distance", "lag_tolerance", "bandwidth",
                "n_pairs", "r_squared", "fitted_at",
            )]
            self.rows = (
                ("soil_carbon", "spherical", 0.8, 120.0, 0.02, 0.78,
                 10.0, 5.0, None, 240, float("inf"), "2026-03-05"),
                ("soil_moisture", "matern", 1.2, 80.0, 0.1, 1.1,
                 8.0, 4.0, 12.0, 180, 0.82, "2026-03-04"),
            )
        elif "FROM sensor_network_design" in query:
            self.description = [(name,) for name in (
                "property_key", "optimal_spacing_m", "coverage_radius_m",
                "recommended_n_sensors", "current_n_sensors", "coverage_gap_pct",
                "confidence_level", "computed_at",
            )]
            self.rows = (
                ("soil_moisture", 25.0, 15.0, 12, 8, 33.3, float("nan"), "2026-03-06"),
                ("soil_carbon", 50.0, 30.0, 6, 5, 16.7, 0.85, "2026-03-05"),
            )
        elif "FROM selected_runs AS run" in query and "kriging_point" in query:
            self.description = [(name,) for name in (
                "prediction_id", "property_key", "method", "grid_resolution_m", "n_points",
                "result_point_count", "mean_predicted", "mean_variance", "mean_std",
                "min_predicted", "max_predicted", "created_at",
            )]
            self.rows = (
                ("55555555-5555-4555-8555-555555555555", "soil_moisture", "ordinary", 10.0, 100, 98, 0.4,
                 float("nan"), 0.2, -0.5, 1.4, "2026-03-07"),
                ("66666666-6666-4666-8666-666666666666", "soil_carbon", "simple", 25.0, 40, 40, 0.8,
                 0.3, 0.5, -0.2, 1.6, "2026-03-06"),
            )
        elif "FROM kriging_prediction" in query and "kriging_point" not in query:
            self.description = [(name,) for name in (
                "id", "property_key", "method", "grid_resolution_m", "n_points", "created_at",
            )]
            self.rows = ((
                "55555555-5555-4555-8555-555555555555", "soil_carbon", "ordinary",
                10.0, 100, "2026-03-07",
            ),)
        elif "FROM kriging_point AS point" in query and "COUNT(*)" in query:
            self.description = [("count",)]
            self.rows = ((3,),)
        elif "FROM kriging_point AS point" in query:
            self.description = [(name,) for name in (
                "longitude", "latitude", "predicted_value", "prediction_variance", "prediction_std",
            )]
            point_rows = (
                (-69.9, 18.5, 2.25, 0.25, 0.5),
                (-69.89, 18.51, float("inf"), -0.1, -1.0),
            )
            if params:
                self.rows = point_rows[params[3]:params[3] + params[2]]
            else:
                self.rows = point_rows
        elif "FROM selected_runs AS run" in query and "geostat_realization_point" in query:
            self.description = [(name,) for name in (
                "realization_id", "property_key", "realization_number", "method", "grid_resolution_m",
                "n_points", "result_point_count", "mean_simulated_value",
                "stddev_simulated_value", "min_simulated_value", "max_simulated_value",
                "created_at",
            )]
            self.rows = (
                ("33333333-3333-4333-8333-333333333333", "soil_moisture", 2, "sgs", 10.0, 100, 99, 0.42,
                 float("inf"), -0.2, 1.2, "2026-03-08"),
                ("44444444-4444-4444-8444-444444444444", "soil_moisture", 1, "sgs", 10.0, 100, 100, 0.4,
                 0.18, -0.1, 1.1, "2026-03-07"),
            )
        elif "FROM geostat_realization_point AS point" in query and "COUNT(*)" in query:
            self.description = [("count",)]
            self.rows = ((3,),)
        elif "FROM geostat_realization_point AS point" in query:
            self.description = [(name,) for name in (
                "longitude", "latitude", "simulated_value",
            )]
            point_rows = (
                (-69.9, 18.5, 1.25),
                (-69.89, 18.51, float("nan")),
            )
            if params:
                self.rows = point_rows[params[3]:params[3] + params[2]]
            else:
                self.rows = point_rows
        elif "FROM geostat_realization" in query:
            self.description = [(name,) for name in (
                "id", "property_key", "realization_number", "method",
                "grid_resolution_m", "n_points", "created_at",
            )]
            self.rows = ((
                "33333333-3333-4333-8333-333333333333", "soil_carbon", 4,
                "sgs", 10.0, 100, "2026-03-08",
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


def test_cross_validation_read_sets_tenant_and_projects_only_safe_spatial_folds(monkeypatch):
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
    result = list_location_cross_validation(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=3,
        connection_factory=lambda: connection,
    )
    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM geostat_cv_result" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE cv.location_id = %s::uuid" in query
    assert "ORDER BY cv.computed_at DESC, cv.property_key, cv.cv_strategy" in query
    assert "jsonb_array_elements(cv.fold_results)" in query
    assert "'actual'" not in query and "'predicted'" not in query
    assert "'block_id'" not in query and "metadata" not in query
    assert "soc_model_id" not in query and "variogram_model_id" not in query
    assert params == (10, 16 * 1024, LOCATION_ID, 2, 3)
    assert result["items"][0]["cv_strategy"] == "spatial_block"
    assert result["items"][0]["r_squared"] is None
    assert result["items"][0]["fold_diagnostics"][0] == {
        "fold": 1,
        "train_samples": 30,
        "test_samples": 5,
        "mean_error": 0.1,
        "mean_squared_error": 2.0,
        "rmse": 1.4,
        "mae": 0.9,
        "r_squared": None,
    }
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_cross_validation_scope_or_page_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid operator identifier"):
        list_location_cross_validation("bad", LOCATION_ID, connection_factory=connect)
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_cross_validation(
            OPERATOR_ID, LOCATION_ID, limit=0, connection_factory=connect
        )
    assert not called


def test_cross_validation_fold_diagnostics_reject_point_level_and_small_sample_data():
    leave_one_out = [{
        "train_samples": 9,
        "test_samples": 1,
        "actual": 0.4,
        "predicted": 0.5,
        "rmse": 0.1,
    }]
    assert _safe_spatial_fold_diagnostics("leave_one_out", 1, leave_one_out) == []

    small_spatial_block = [{
        "train_samples": 9,
        "test_samples": 4,
        "mean_error": 0.1,
        "mean_squared_error": 0.2,
        "rmse": 0.4,
        "mae": 0.3,
        "r_squared": 0.7,
    }]
    assert _safe_spatial_fold_diagnostics("spatial_block", 1, small_spatial_block) == []


def test_cross_validation_fold_diagnostics_are_bounded_and_fail_closed():
    fold = {
        "train_samples": "10",
        "test_samples": "5",
        "mean_error": "0.1",
        "mean_squared_error": "0.2",
        "rmse": "0.4",
        "mae": "0.3",
        "r_squared": "0.7",
        "error": "private exception detail",
        "block_id": 12345,
    }
    assert _safe_spatial_fold_diagnostics("spatial_block", 11, [fold] * 11) == []
    assert _safe_spatial_fold_diagnostics("spatial_block", 1, [fold] * 2) == []
    assert _safe_spatial_fold_diagnostics("spatial_block", 1, "[" + " " * (16 * 1024) + "]") == []
    safe = _safe_spatial_fold_diagnostics("spatial_block", 1, [fold])
    assert safe == [{
        "fold": 1,
        "train_samples": 10,
        "test_samples": 5,
        "mean_error": 0.1,
        "mean_squared_error": 0.2,
        "rmse": 0.4,
        "mae": 0.3,
        "r_squared": 0.7,
    }]


def test_variogram_read_is_scoped_bounded_and_omits_model_identity(monkeypatch):
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
    result = list_location_variogram_models(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=2,
        connection_factory=lambda: connection,
    )
    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM variogram_model" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "ORDER BY fitted_at DESC, property_key, model_type, id DESC" in query
    assert "metadata" not in query and "id," not in query
    assert params == (LOCATION_ID, 2, 2)
    assert result["items"][0]["model_type"] == "spherical"
    assert result["items"][0]["r_squared"] is None
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_variogram_scope_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        list_location_variogram_models(OPERATOR_ID, "bad", connection_factory=connect)
    assert not called


def test_sensor_design_read_is_scoped_bounded_and_omits_notes_and_ids(monkeypatch):
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
    result = list_location_sensor_network_designs(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=7,
        connection_factory=lambda: connection,
    )
    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM sensor_network_design" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "ORDER BY computed_at DESC, property_key, id DESC" in query
    assert "notes" not in query and "metadata" not in query
    assert "variogram_model_id" not in query and "id," not in query
    assert params == (LOCATION_ID, 2, 7)
    assert result["items"][0]["property_key"] == "soil_moisture"
    assert result["items"][0]["confidence_level"] is None
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_sensor_design_scope_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        list_location_sensor_network_designs(OPERATOR_ID, "bad", connection_factory=connect)
    assert not called


def test_kriging_read_aggregates_selected_location_runs_and_hides_points(monkeypatch):
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
    result = list_location_kriging_summaries(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=1,
        connection_factory=lambda: connection,
    )
    query, params = next(
        (query, params) for query, params in connection.queries
        if "FROM selected_runs AS run" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "LIMIT %s OFFSET %s" in query
    assert "LEFT JOIN kriging_point" in query
    assert "AVG(point.predicted_value)" in query
    assert "point_geometry" not in query and "metadata" not in query
    assert "variogram_model_id" not in query and "threshold_value" not in query
    assert params == (LOCATION_ID, 2, 1)
    assert result["items"][0]["prediction_id"] == "55555555-5555-4555-8555-555555555555"
    assert result["items"][0]["result_point_count"] == 98
    assert result["items"][0]["mean_variance"] is None
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_kriging_scope_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid operator identifier"):
        list_location_kriging_summaries("bad", LOCATION_ID, connection_factory=connect)
    assert not called


def test_kriging_point_read_sets_signed_scope_and_returns_bounded_points(monkeypatch):
    connection = _Connection()
    prediction_id = "55555555-5555-4555-8555-555555555555"
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
    result = list_location_kriging_points(
        OPERATOR_ID,
        LOCATION_ID,
        prediction_id,
        limit=1,
        offset=1,
        connection_factory=lambda: connection,
    )

    run_query, run_params = connection.queries[3]
    count_query, count_params = connection.queries[4]
    point_query, point_params = connection.queries[5]
    assert order[:4] == ["query", "query", "query", "context"]
    assert "FROM kriging_prediction" in run_query
    assert "WHERE id = %s::uuid AND location_id = %s::uuid" in run_query
    assert run_params == (prediction_id, LOCATION_ID)
    assert "run.location_id = %s::uuid" in count_query
    assert count_params == (prediction_id, LOCATION_ID)
    assert "ST_X(point.point_geometry) AS longitude" in point_query
    assert "ORDER BY ST_Y(point.point_geometry)" in point_query
    for omitted in ("weight_sum", "n_neighbors", "search_radius_m", "threshold_value", "metadata"):
        assert omitted not in point_query
    assert point_params == (prediction_id, LOCATION_ID, 1, 1)
    assert result["location_id"] == LOCATION_ID
    assert result["prediction_id"] == prediction_id
    assert result["prediction"]["method"] == "ordinary"
    assert result["items"] == [{
        "longitude": -69.89,
        "latitude": 18.51,
        "predicted_value": None,
        "prediction_variance": None,
        "prediction_std": None,
        "point_number": 2,
    }]
    assert result["total"] == 3
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_kriging_point_scope_or_page_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    prediction_id = "55555555-5555-4555-8555-555555555555"
    with pytest.raises(ValueError, match="Invalid prediction identifier"):
        list_location_kriging_points(OPERATOR_ID, LOCATION_ID, "bad", connection_factory=connect)
    with pytest.raises(ValueError, match="Invalid location identifier"):
        list_location_kriging_points(OPERATOR_ID, "bad", prediction_id, connection_factory=connect)
    with pytest.raises(ValueError, match="limit"):
        list_location_kriging_points(
            OPERATOR_ID, LOCATION_ID, prediction_id, limit=51, connection_factory=connect
        )
    assert not called


def test_unowned_kriging_prediction_is_not_found_after_signed_scope(monkeypatch):
    connection = _Connection()
    original_execute = _Cursor.execute
    context_calls = []

    def execute(self, query, params=None):
        original_execute(self, query, params)
        if "FROM kriging_prediction" in query and "kriging_point" not in query:
            self.rows = ()

    def set_context(conn, **kwargs):
        context_calls.append((conn, kwargs))

    monkeypatch.setattr(_Cursor, "execute", execute)
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.set_operator_tenant_context", set_context
    )
    with pytest.raises(GeostatisticalKrigingNotFound):
        list_location_kriging_points(
            OPERATOR_ID,
            LOCATION_ID,
            "55555555-5555-4555-8555-555555555555",
            connection_factory=lambda: connection,
        )
    assert len(context_calls) == 1
    assert connection.closed


def test_realization_read_aggregates_selected_runs_and_hides_point_details(monkeypatch):
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
    result = list_location_realization_summaries(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=2,
        connection_factory=lambda: connection,
    )
    query, params = next(
        (query, params) for query, params in connection.queries
        if "geostat_realization_point" in query
    )
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE location_id = %s::uuid" in query
    assert "LIMIT %s OFFSET %s" in query
    assert "STDDEV_POP(point.simulated_value)" in query
    assert "point_geometry" not in query and "seed" not in query
    assert "variogram_model_id" not in query and "metadata" not in query
    assert params == (LOCATION_ID, 2, 2)
    assert result["items"][0]["realization_number"] == 2
    assert result["items"][0]["realization_id"] == "33333333-3333-4333-8333-333333333333"
    assert result["items"][0]["stddev_simulated_value"] is None
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_invalid_realization_scope_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        list_location_realization_summaries(OPERATOR_ID, "bad", connection_factory=connect)
    assert not called


def test_realization_point_read_sets_signed_scope_and_returns_bounded_points(monkeypatch):
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
    result = list_location_realization_points(
        OPERATOR_ID,
        LOCATION_ID,
        "33333333-3333-4333-8333-333333333333",
        limit=1,
        offset=1,
        connection_factory=lambda: connection,
    )

    run_query, run_params = connection.queries[3]
    count_query, count_params = connection.queries[4]
    point_query, point_params = connection.queries[5]
    assert order[:4] == ["query", "query", "query", "context"]
    assert "WHERE id = %s::uuid AND location_id = %s::uuid" in run_query
    assert run_params == ("33333333-3333-4333-8333-333333333333", LOCATION_ID)
    assert "run.location_id = %s::uuid" in count_query
    assert count_params == ("33333333-3333-4333-8333-333333333333", LOCATION_ID)
    assert "ST_X(point.point_geometry) AS longitude" in point_query
    assert "ORDER BY ST_Y(point.point_geometry)" in point_query
    assert "seed" not in point_query and "metadata" not in point_query
    assert point_params == ("33333333-3333-4333-8333-333333333333", LOCATION_ID, 1, 1)
    assert result["location_id"] == LOCATION_ID
    assert result["realization"]["realization_number"] == 4
    assert result["items"] == [{
        "longitude": -69.89,
        "latitude": 18.51,
        "simulated_value": None,
        "point_number": 2,
    }]
    assert result["total"] == 3
    assert result["has_more"] is True
    assert connection.rollback_count == 1
    assert connection.closed


def test_realization_point_read_rejects_bad_scope_or_page_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid realization identifier"):
        list_location_realization_points(OPERATOR_ID, LOCATION_ID, "bad", connection_factory=connect)
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_realization_points(
            OPERATOR_ID, LOCATION_ID,
            "33333333-3333-4333-8333-333333333333", limit=51,
            connection_factory=connect,
        )
    assert not called


def test_unowned_realization_is_not_found_after_signed_scope(monkeypatch):
    connection = _Connection()
    original_execute = _Cursor.execute
    context_calls = []

    def execute(self, query, params=None):
        original_execute(self, query, params)
        if "FROM geostat_realization" in query and "FROM geostat_realization_point" not in query:
            self.rows = ()

    def set_context(conn, **kwargs):
        context_calls.append((conn, kwargs))

    monkeypatch.setattr(_Cursor, "execute", execute)
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.set_operator_tenant_context", set_context
    )
    from services.gateway.geostatistics_reads import GeostatisticalRealizationNotFound

    with pytest.raises(GeostatisticalRealizationNotFound):
        list_location_realization_points(
            OPERATOR_ID,
            LOCATION_ID,
            "33333333-3333-4333-8333-333333333333",
            connection_factory=lambda: connection,
        )
    assert len(context_calls) == 1
    assert connection.closed


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

    cross_validation = f"/operator/api/geostatistics/{LOCATION_ID}/cross-validation"
    assert auth_route_policy("GET", cross_validation, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", cross_validation, enabled=True) is None

    variograms = f"/operator/api/geostatistics/{LOCATION_ID}/variogram-models"
    assert auth_route_policy("GET", variograms, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", variograms, enabled=True) is None

    sensor_designs = f"/operator/api/geostatistics/{LOCATION_ID}/sensor-network-designs"
    assert auth_route_policy("GET", sensor_designs, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", sensor_designs, enabled=True) is None

    kriging = f"/operator/api/geostatistics/{LOCATION_ID}/kriging-summaries"
    assert auth_route_policy("GET", kriging, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", kriging, enabled=True) is None

    realizations = f"/operator/api/geostatistics/{LOCATION_ID}/realization-summaries"
    assert auth_route_policy("GET", realizations, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", realizations, enabled=True) is None

    points = f"/operator/api/geostatistics/{LOCATION_ID}/realizations/33333333-3333-4333-8333-333333333333/points"
    assert auth_route_policy("GET", points, enabled=True) == {
        "resource": "geostatistics",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", points, enabled=True) is None
    assert auth_route_policy("GET", points + "/extra", enabled=True) is None


def _app(monkeypatch, reader):
    from services.gateway.geostatistics_routes import register_geostatistics_routes

    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_spatial_autocorrelation",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_cross_validation",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_variogram_models",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_sensor_network_designs",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_kriging_summaries",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_kriging_points",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_realization_summaries",
        reader,
    )
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.list_location_realization_points",
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


def test_cross_validation_http_route_is_no_store_and_passes_scope(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert limit == 2
        assert offset == 1
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
            f"/operator/api/geostatistics/{LOCATION_ID}/cross-validation?limit=2&offset=1"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 1


def test_cross_validation_http_route_denies_missing_tenant_grant(monkeypatch):
    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    app = _app(monkeypatch, deny)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/cross-validation"
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_variogram_http_route_is_no_store_and_passes_scope(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert limit == 4
        assert offset == 5
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
            f"/operator/api/geostatistics/{LOCATION_ID}/variogram-models?limit=4&offset=5"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 5


def test_sensor_design_http_route_is_no_store_and_passes_scope(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert limit == 6
        assert offset == 2
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
            f"/operator/api/geostatistics/{LOCATION_ID}/sensor-network-designs?limit=6&offset=2"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 2


def test_kriging_http_route_is_no_store_and_passes_scope(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert limit == 5
        assert offset == 4
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
            f"/operator/api/geostatistics/{LOCATION_ID}/kriging-summaries?limit=5&offset=4"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 4


def test_kriging_points_http_route_is_no_store_and_location_scoped(monkeypatch):
    prediction_id = "55555555-5555-4555-8555-555555555555"

    def reader(operator_id, location_id, requested_prediction_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert requested_prediction_id == prediction_id
        assert limit == 5
        assert offset == 10
        return {
            "location_id": location_id,
            "prediction_id": requested_prediction_id,
            "prediction": {"method": "ordinary"},
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }

    app = _app(monkeypatch, reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/kriging/{prediction_id}/points?limit=5&offset=10"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["prediction_id"] == prediction_id


def test_kriging_points_http_route_hides_unowned_run(monkeypatch):
    def reader(*_args, **_kwargs):
        raise GeostatisticalKrigingNotFound

    app = _app(monkeypatch, reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/kriging/55555555-5555-4555-8555-555555555555/points"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_realization_http_route_is_no_store_and_passes_scope(monkeypatch):
    def reader(operator_id, location_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert limit == 3
        assert offset == 2
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
            f"/operator/api/geostatistics/{LOCATION_ID}/realization-summaries?limit=3&offset=2"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["offset"] == 2


def test_realization_points_http_route_is_no_store_and_location_scoped(monkeypatch):
    realization_id = "33333333-3333-4333-8333-333333333333"

    def reader(operator_id, location_id, requested_realization_id, *, limit, offset):
        assert operator_id == OPERATOR_ID
        assert location_id == LOCATION_ID
        assert requested_realization_id == realization_id
        assert limit == 5
        assert offset == 10
        return {
            "location_id": location_id,
            "realization_id": requested_realization_id,
            "realization": {"realization_number": 4},
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }

    app = _app(monkeypatch, reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/realizations/{realization_id}/points?limit=5&offset=10"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["realization_id"] == realization_id


def test_realization_points_http_route_hides_unowned_run(monkeypatch):
    from services.gateway.geostatistics_reads import GeostatisticalRealizationNotFound

    def reader(*_args, **_kwargs):
        raise GeostatisticalRealizationNotFound

    app = _app(monkeypatch, reader)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/realizations/33333333-3333-4333-8333-333333333333/points"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def _autocorrelation_projection(location_id=LOCATION_ID, *, limit=25, offset=0):
    return {
        "location_id": location_id,
        "items": [
            {
                "property_key": "soil_carbon",
                "metric": "morans_i",
                "statistic_value": 0.7,
                "expected_value": 0.1,
                "p_value": 0.03,
                "z_score": 2.1,
                "n_samples": 30,
                "spatial_weights_type": "knn",
                "distance_threshold": None,
                "k_neighbors": 8,
                "computed_at": "2026-10-28T12:00:00+00:00",
            }
        ],
        "limit": limit,
        "offset": offset,
        "has_more": False,
    }


def test_autocorrelation_http_contract_is_documented_and_validated(monkeypatch):
    app = _app(monkeypatch, lambda *_args, **_kwargs: _autocorrelation_projection())
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/autocorrelation"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["items"][0]["metric"] == "morans_i"
    schema = app.openapi()["paths"][
        "/operator/api/geostatistics/{location_id}/autocorrelation"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("SpatialAutocorrelationPage")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result["items"][0].update(private_metadata={"secret": True}),
        lambda result: result["items"][0].update(metric="unregistered_metric"),
        lambda result: result["items"][0].update(n_samples=True),
        lambda result: result["items"][0].update(statistic_value="0.7"),
        lambda result: result.update(location_id="33333333-3333-4333-8333-333333333333"),
        lambda result: result.update(limit=24),
        lambda result: result.update(has_more=True),
    ],
)
def test_autocorrelation_http_rejects_malformed_projection(monkeypatch, mutate):
    result = _autocorrelation_projection()
    mutate(result)
    app = _app(monkeypatch, lambda *_args, **_kwargs: result)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/geostatistics/{LOCATION_ID}/autocorrelation"
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == {"error": "Spatial autocorrelation unavailable"}


def test_autocorrelation_service_stops_continuation_at_offset_ceiling(monkeypatch):
    monkeypatch.setattr(
        "services.gateway.geostatistics_reads.set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )
    connection = _Connection()
    result = list_location_spatial_autocorrelation(
        OPERATOR_ID,
        LOCATION_ID,
        limit=1,
        offset=10_000,
        connection_factory=lambda: connection,
    )

    assert len(result["items"]) == 1
    assert result["has_more"] is False
    assert connection.closed
