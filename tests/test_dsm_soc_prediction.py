"""Tests for time-series feature aggregation and SOC prediction."""

from datetime import date
from pathlib import Path

from services.analytics.time_series_features import (
    aggregate_remote_sensing_seasonal,
    aggregate_weather_seasonal,
    build_complete_feature_set,
    compute_window,
    get_season,
)
from services.analytics.soc_prediction import (
    extract_training_data,
    prepare_feature_matrix,
    train_xgboost_model,
)
from services.analytics.model_validation import (
    aggregate_to_field_level,
    compute_mec,
    compute_me,
    compute_mae,
    compute_r_squared,
    compute_regression_metrics,
    compute_rmse,
    geographic_cross_validation,
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


def test_geographic_cv_few_fields() -> None:
    data = [{"plot_id": "plot-1", "carbon_pct": 1.0}]
    folds = geographic_cross_validation(data, n_folds=5)
    assert len(folds) <= 1


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
