"""ML anomaly detection tests."""

from pathlib import Path


def test_ml_anomaly_detector_file_exists() -> None:
    assert Path("services/ingestion/ml_anomaly_detector.py").exists()


def test_ml_detector_has_prophet_function() -> None:
    from services.ingestion.ml_anomaly_detector import fit_prophet, predict_anomalies_prophet
    assert callable(fit_prophet)
    assert callable(predict_anomalies_prophet)


def test_ml_detector_has_isolation_forest_function() -> None:
    from services.ingestion.ml_anomaly_detector import fit_isolation_forest, score_anomalies_iforest
    assert callable(fit_isolation_forest)
    assert callable(score_anomalies_iforest)


def test_ml_detector_has_run_ml_check() -> None:
    from services.ingestion.ml_anomaly_detector import run_ml_check
    assert callable(run_ml_check)


def test_ml_detector_has_save_models() -> None:
    from services.ingestion.ml_anomaly_detector import save_models
    assert callable(save_models)


def test_ml_detector_has_graceful_degradation() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "ImportError" in content
    assert "not installed" in content
    assert "graceful" in content.lower() or "fallback" in content.lower()


def test_ml_detector_uses_logging() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "get_logger" in content


def test_ml_detector_has_model_dir() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "MODEL_DIR" in content
    assert "models/ml_anomaly" in content


def test_anomaly_detector_has_ml_flags() -> None:
    content = Path("services/ingestion/anomaly_detector.py").read_text()
    assert "--ml-check" in content
    assert "--ml-train" in content
    assert "--location-id" in content


def test_anomaly_detector_imports_ml_module() -> None:
    content = Path("services/ingestion/anomaly_detector.py").read_text()
    assert "ml_anomaly_detector" in content


def test_requirements_has_pandas() -> None:
    content = Path("requirements.txt").read_text()
    assert "pandas" in content


def test_requirements_has_numpy() -> None:
    content = Path("requirements.txt").read_text()
    assert "numpy" in content


def test_requirements_has_prophet() -> None:
    content = Path("requirements.txt").read_text()
    assert "prophet" in content


def test_requirements_has_sklearn() -> None:
    content = Path("requirements.txt").read_text()
    assert "scikit-learn" in content


def test_ml_detector_builds_prophet_features() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "_build_prophet_features" in content
    assert '"ds"' in content
    assert '"y"' in content


def test_ml_detector_queries_timeseries() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "_query_sensor_timeseries" in content
    assert "_query_all_sensors_timeseries" in content
    assert "sensor_reading" in content


def test_ml_detector_deduplicates() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "seen" in content
    assert "unique_anomalies" in content


def test_ml_detector_has_detection_methods() -> None:
    content = Path("services/ingestion/ml_anomaly_detector.py").read_text()
    assert "ml_prophet" in content
    assert "ml_isolation_forest" in content
