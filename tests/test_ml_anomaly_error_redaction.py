"""Ensure ML model failures do not expose provider or local artifact details."""

import logging
import pickle

from services.ingestion import ml_anomaly_detector

LOCATION_ID = "12345678-location"
SENSITIVE_DETAIL = "credential=synthetic-private-value /private/model/path"


def test_fit_prophet_logs_only_bounded_exception_class(monkeypatch, caplog):
    class _Model:
        def fit(self, _data):
            raise RuntimeError(SENSITIVE_DETAIL)

    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    monkeypatch.setattr(ml_anomaly_detector, "_prophet", lambda **_kwargs: _Model())
    monkeypatch.setattr(
        ml_anomaly_detector,
        "_query_sensor_timeseries",
        lambda *_args: list(range(100)),
    )
    monkeypatch.setattr(
        ml_anomaly_detector,
        "_build_prophet_features",
        lambda *_args: object(),
    )
    caplog.set_level(logging.ERROR, logger="kokonut.ingestion.ml_anomaly_detector")

    assert ml_anomaly_detector.fit_prophet(
        object(), LOCATION_ID, "soil_moisture"
    ) is None

    assert "Prophet fit failed (RuntimeError)" in caplog.text
    assert SENSITIVE_DETAIL not in caplog.text
    assert "soil_moisture" not in caplog.text


def test_save_model_failures_log_only_bounded_exception_classes(
    monkeypatch, tmp_path, caplog
):
    class _Cursor:
        def execute(self, *_args):
            pass

        def fetchall(self):
            return [{"sensor_type": "soil_moisture"}]

        def close(self):
            pass

    class _Connection:
        def cursor(self, **_kwargs):
            return _Cursor()

    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(
        ml_anomaly_detector,
        "fit_prophet",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        ml_anomaly_detector,
        "fit_isolation_forest",
        lambda *_args, **_kwargs: (object(), object(), []),
    )

    def _fail_save(*_args):
        raise RuntimeError(SENSITIVE_DETAIL)

    monkeypatch.setattr(ml_anomaly_detector, "_save_model_artifact", _fail_save)
    caplog.set_level(logging.ERROR, logger="kokonut.ingestion.ml_anomaly_detector")

    result = ml_anomaly_detector.save_models(_Connection(), LOCATION_ID)

    assert result["status"] == "success"
    assert result["models_saved"] == []
    assert caplog.text.count("RuntimeError") == 2
    assert SENSITIVE_DETAIL not in caplog.text
    assert "soil_moisture" not in caplog.text
    assert "iforest_12345678.pkl" not in caplog.text


def test_model_load_failures_do_not_log_artifact_names_or_raw_errors(
    monkeypatch, tmp_path, caplog
):
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    prophet_file = model_dir / f"prophet_{LOCATION_ID[:8]}_soil_moisture.pkl"
    iforest_file = model_dir / f"iforest_{LOCATION_ID[:8]}.pkl"
    for artifact in (prophet_file, iforest_file):
        artifact.write_bytes(pickle.dumps({"synthetic": True}))
        artifact.chmod(0o600)

    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)

    def _fail_load(_stream):
        raise RuntimeError(SENSITIVE_DETAIL)

    monkeypatch.setattr(pickle, "load", _fail_load)
    caplog.set_level(logging.WARNING, logger="kokonut.ingestion.ml_anomaly_detector")

    result = ml_anomaly_detector.load_models(LOCATION_ID)

    assert result == {"prophet": {}, "iforest": None}
    assert caplog.text.count("RuntimeError") == 2
    assert SENSITIVE_DETAIL not in caplog.text
    assert prophet_file.name not in caplog.text
    assert iforest_file.name not in caplog.text

