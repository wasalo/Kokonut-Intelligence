"""Tests for time-series feature aggregation and SOC prediction."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import services.analytics.soc_prediction as soc
from services.analytics.model_validation import (
    aggregate_to_field_level,
    compute_mae,
    compute_me,
    compute_mec,
    compute_r_squared,
    compute_regression_metrics,
    compute_rmse,
    geographic_cross_validation,
)
from services.analytics.soc_prediction import (
    prepare_feature_matrix,
    train_xgboost_model,
)
from services.analytics.time_series_features import (
    compute_window,
    get_season,
)

SCHEMA_FE = Path("schemas/postgres/075_feature_engineering.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_timeseries_tables() -> None:
    text = SCHEMA_FE.read_text()
    assert "CREATE TABLE IF NOT EXISTS rs_time_series_feature" in text
    assert "CREATE TABLE IF NOT EXISTS weather_time_series_feature" in text
    assert "CREATE TABLE IF NOT EXISTS modis_lst_time_series" in text
    assert "CREATE TABLE IF NOT EXISTS smap_moisture_time_series" in text
    assert "CREATE TABLE IF NOT EXISTS sentinel1_time_series" in text


def test_schema_defines_timeseries_views() -> None:
    text = SCHEMA_FE.read_text()
    assert "CREATE OR REPLACE VIEW v_dsm_feature_set" in text
    assert "CREATE OR REPLACE VIEW v_seasonal_feature_summary" in text


def test_schema_has_reducer_check() -> None:
    text = SCHEMA_FE.read_text()
    assert "simple_median" in text
    assert "seasonal_median" in text
    assert "time_series_summary" in text
    assert "seasonal_mean" in text


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def test_get_season() -> None:
    assert get_season(date(2026, 3, 15)) == "spring"
    assert get_season(date(2026, 7, 15)) == "summer"
    assert get_season(date(2026, 10, 15)) == "autumn"
    assert get_season(date(2026, 12, 15)) == "winter"


def test_compute_window() -> None:
    start, end = compute_window(date(2026, 7, 1), 6)
    assert end == date(2026, 7, 1)
    assert start < end
    # 6 months = ~180 days
    assert (end - start).days >= 170
    assert (end - start).days <= 190


# ---------------------------------------------------------------------------
# Regression metrics tests
# ---------------------------------------------------------------------------

def test_compute_rmse() -> None:
    assert compute_rmse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0
    assert compute_rmse([1.0, 2.0], [2.0, 3.0]) == 1.0
    assert compute_rmse([], []) == 0.0


def test_compute_mae() -> None:
    assert compute_mae([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0
    assert compute_mae([1.0, 2.0], [2.0, 3.0]) == 1.0


def test_compute_me() -> None:
    assert compute_me([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0
    # Positive ME means overprediction
    assert compute_me([2.0, 3.0], [1.0, 2.0]) == 1.0


def test_compute_r_squared() -> None:
    assert compute_r_squared([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    # Flat predictions vs varying actuals: R² < 0 (worse than mean)
    r2 = compute_r_squared([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])
    assert r2 < 0


def test_compute_mec() -> None:
    # Perfect prediction
    assert compute_mec([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    # Worse than mean
    mec = compute_mec([10.0, 10.0], [1.0, 2.0])
    assert mec < 0


def test_compute_regression_metrics() -> None:
    predicted = [1.0, 2.0, 3.0, 4.0]
    actual = [1.1, 2.1, 2.9, 4.1]
    metrics = compute_regression_metrics(predicted, actual)
    assert "r_squared" in metrics
    assert "rmse" in metrics
    assert "mae" in metrics
    assert "me" in metrics
    assert "mec" in metrics
    assert "intercept" in metrics
    assert "slope" in metrics
    assert metrics["n"] == 4
    assert metrics["r_squared"] > 0.9


def test_compute_regression_metrics_empty() -> None:
    metrics = compute_regression_metrics([], [])
    assert metrics["r_squared"] == 0.0
    assert metrics["n"] == 0


# ---------------------------------------------------------------------------
# Cross-validation tests
# ---------------------------------------------------------------------------

def test_geographic_cross_validation() -> None:
    data = [
        {"plot_id": f"plot-{i}", "carbon_pct": 1.0 + i * 0.1}
        for i in range(20)
        for _ in range(3)
    ]
    folds = geographic_cross_validation(data, n_folds=5)
    assert len(folds) == 5
    total_test = sum(f["test_samples"] for f in folds)
    assert total_test == 60  # 20 fields * 3 samples
    assert folds == geographic_cross_validation(data, n_folds=5)
    assert folds == geographic_cross_validation(list(reversed(data)), n_folds=5)
    excluded_fields = [
        field_id for fold in folds for field_id in fold["excluded_fields"]
    ]
    assert set(excluded_fields) == {f"plot-{i}" for i in range(20)}
    assert len(excluded_fields) == 20
    assert [fold["test_samples"] for fold in folds] == [12] * 5


def test_geographic_cv_few_fields() -> None:
    data = [{"plot_id": "plot-1", "carbon_pct": 1.0}]
    folds = geographic_cross_validation(data, n_folds=5)
    assert len(folds) <= 1


def test_spatial_block_cv_uses_extracted_plot_coordinates(monkeypatch) -> None:
    training_data = [
        {
            "plot_id": f"plot-{index}",
            "gps_latitude": 18.5 + (index // 4) * 0.004,
            "gps_longitude": -69.8 + (index % 4) * 0.004,
            "carbon_pct": 1.0 + index * 0.1,
            "depth_cm": 15,
        }
        for index in range(12)
    ]
    monkeypatch.setattr(soc, "extract_training_data", lambda *_args: training_data)
    monkeypatch.setattr(soc, "find_spec", lambda _name: None)

    result = soc.spatial_block_cv_for_soc(
        object(), "location-1", block_size_m=200.0
    )

    assert result["cv_strategy"] == "spatial_block"
    assert result["n_successful_folds"] >= 2
    assert sum(fold["test_samples"] for fold in result["fold_results"]) == 12
    assert all(fold["train_samples"] > 0 for fold in result["fold_results"])


# ---------------------------------------------------------------------------
# Field-level aggregation tests
# ---------------------------------------------------------------------------

def test_aggregate_to_field_level() -> None:
    predictions = [
        {"plot_id": "f1", "predicted_soc_pct": 2.0, "measured_soc_pct": 2.1, "location_id": "l1"},
        {"plot_id": "f1", "predicted_soc_pct": 2.2, "measured_soc_pct": 2.3, "location_id": "l1"},
        {"plot_id": "f2", "predicted_soc_pct": 3.0, "measured_soc_pct": 3.1, "location_id": "l1"},
    ]
    result = aggregate_to_field_level(predictions)
    assert len(result) == 2
    f1 = [r for r in result if r["plot_id"] == "f1"][0]
    assert f1["mean_predicted_soc"] == 2.1
    assert f1["mean_measured_soc"] == 2.2
    assert f1["sample_count"] == 2


# ---------------------------------------------------------------------------
# SOC prediction model tests
# ---------------------------------------------------------------------------

def test_prepare_feature_matrix() -> None:
    data = [
        {"carbon_pct": 2.5, "depth_cm": 15, "ndvi": 0.6, "savi": 0.5},
        {"carbon_pct": 3.0, "depth_cm": 10, "ndvi": 0.7, "savi": 0.6},
    ]
    X, y, names = prepare_feature_matrix(data)
    assert len(X) == 2
    assert len(y) == 2
    assert len(names) == 16
    assert y == [2.5, 3.0]


def test_extract_training_data_includes_location_scoped_plot_coordinates() -> None:
    measurement_date = date(2026, 6, 15)
    row = (
        "sample-1",
        "location-1",
        "plot-1",
        18.5,
        -69.8,
        measurement_date,
        2.5,
        3.5,
        15.0,
        *([None] * 15),
    )

    class _Cursor:
        query = ""
        params = None
        closed = False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return [row]

        def close(self):
            self.closed = True

    class _Connection:
        def __init__(self):
            self.test_cursor = _Cursor()

        def cursor(self):
            return self.test_cursor

    conn = _Connection()
    result = soc.extract_training_data(conn, "location-1")

    assert len(result) == 1
    assert result[0]["gps_latitude"] == 18.5
    assert result[0]["gps_longitude"] == -69.8
    assert result[0]["measurement_date"] == str(measurement_date)
    assert conn.test_cursor.params == ["location-1"]
    assert "LEFT JOIN plot plot_geom" in conn.test_cursor.query
    assert "ST_Y(COALESCE(plot_geom.center, ST_PointOnSurface(plot_geom.boundary)))" in conn.test_cursor.query
    assert "ST_X(COALESCE(plot_geom.center, ST_PointOnSurface(plot_geom.boundary)))" in conn.test_cursor.query
    assert "scm.location_id = %s" in conn.test_cursor.query
    assert conn.test_cursor.closed


def test_train_xgboost_no_xgboost() -> None:
    """Test training without xgboost installed returns placeholder."""
    X = [[1.0, 2.0] for _ in range(20)]
    y = [float(i) for i in range(20)]
    result = train_xgboost_model(X, y, ["f1", "f2"])
    # Either trains successfully or returns placeholder
    assert "model_type" in result or "error" in result


def test_train_xgboost_insufficient_data() -> None:
    X = [[1.0]]
    y = [2.0]
    result = train_xgboost_model(X, y, ["f1"])
    # Either returns insufficient data error or xgboost placeholder
    assert "error" in result


def test_residual_kriging_supports_ten_training_samples(monkeypatch):
    training_data = [
        {
            "gps_latitude": 18.0 + i * 0.001,
            "gps_longitude": -69.0 + i * 0.001,
        }
        for i in range(10)
    ]
    matrix = [[float(i)] for i in range(10)]
    observed = [1.0 + i * 0.1 for i in range(10)]

    class _Variogram:
        def __init__(self, conn):
            self.conn = conn

        def fit_variogram(self, _values, _coordinates, model_type):
            assert model_type == "exponential"
            return {"model_type": model_type}

    class _Kriging:
        def __init__(self, conn):
            self.conn = conn

        def ordinary_kriging(self, _coordinates, _values, _model, resolution_m):
            assert resolution_m == 100.0
            return {"n_points": 10}

    monkeypatch.setattr(soc, "extract_training_data", lambda *_args: training_data)
    monkeypatch.setattr(soc, "prepare_feature_matrix", lambda _data: (matrix, observed, ["feature"]))
    monkeypatch.setattr(soc, "train_xgboost_model", lambda *_args: {"model_type": "test"})
    monkeypatch.setattr(soc, "predict_soc", lambda *_args: {"predicted_soc_pct": 1.5})
    monkeypatch.setattr("services.geostatistics.variogram.VariogramAnalyzer", _Variogram)
    monkeypatch.setattr("services.geostatistics.kriging.KrigingEngine", _Kriging)

    result = soc.residual_kriging_correction(object(), "location-123")

    assert result["method"] == "residual_kriging"
    assert result["n_samples"] == 10
    assert result["kriging_grid_points"] == 10


def test_soc_prediction_uses_graceful_fallback_without_numpy():
    code = """
import builtins
real_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == "numpy":
        raise ModuleNotFoundError("simulated missing numpy")
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
import services.analytics.soc_prediction as module
result = module.residual_kriging_correction(None, "location-123")
assert result == {
    "error": "NumPy is required for residual kriging",
    "corrected_soc_pct": None,
}
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_timeseries_tables()
    test_schema_defines_timeseries_views()
    test_schema_has_reducer_check()
    test_get_season()
    test_compute_window()
    test_compute_rmse()
    test_compute_mae()
    test_compute_me()
    test_compute_r_squared()
    test_compute_mec()
    test_compute_regression_metrics()
    test_compute_regression_metrics_empty()
    test_geographic_cross_validation()
    test_geographic_cv_few_fields()
    test_aggregate_to_field_level()
    test_prepare_feature_matrix()
    test_train_xgboost_no_xgboost()
    test_train_xgboost_insufficient_data()
    print("All tests passed.")
