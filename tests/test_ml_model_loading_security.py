"""Security tests for locally persisted sklearn/Prophet pickle artifacts."""

import os
import pickle

from services.ingestion import ml_anomaly_detector

LOCATION_ID = "12345678-location"


def test_load_models_skips_group_or_world_writable_artifact(monkeypatch, tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    artifact = model_dir / f"iforest_{LOCATION_ID[:8]}.pkl"
    artifact.write_bytes(pickle.dumps({"test_model": "must not load"}))
    artifact.chmod(0o666)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)

    result = ml_anomaly_detector.load_models(LOCATION_ID)

    assert result["iforest"] is None


def test_load_models_accepts_private_process_owned_artifact(monkeypatch, tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    artifact = model_dir / f"iforest_{LOCATION_ID[:8]}.pkl"
    expected = {"test_model": "locally generated"}
    artifact.write_bytes(pickle.dumps(expected))
    artifact.chmod(0o600)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)

    result = ml_anomaly_detector.load_models(LOCATION_ID)

    assert result["iforest"] == expected


def test_load_models_accepts_private_prophet_artifact(monkeypatch, tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    artifact = model_dir / f"prophet_{LOCATION_ID[:8]}_soil_moisture.pkl"
    expected = {"test_model": "locally generated Prophet model"}
    artifact.write_bytes(pickle.dumps(expected))
    artifact.chmod(0o600)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)

    result = ml_anomaly_detector.load_models(LOCATION_ID)

    assert result["prophet"]["soil_moisture"] == expected


def test_save_models_does_not_create_through_symlinked_ancestor(
    monkeypatch, tmp_path
):
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir(mode=0o700)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    model_dir = linked_parent / "nested" / "models" / "ml_anomaly"
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)
    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)

    result = ml_anomaly_detector.save_models(object(), LOCATION_ID)

    assert result["status"] == "error"
    assert not (real_parent / "nested").exists()


def test_save_models_creates_private_nested_directory(monkeypatch, tmp_path):
    model_dir = tmp_path / "nested" / "models" / "ml_anomaly"
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)
    monkeypatch.setattr(ml_anomaly_detector, "_ensure_deps", lambda: True)
    monkeypatch.setattr(
        ml_anomaly_detector,
        "fit_prophet",
        lambda *_args, **_kwargs: {"model": "locally generated"},
    )
    monkeypatch.setattr(
        ml_anomaly_detector,
        "fit_isolation_forest",
        lambda *_args, **_kwargs: None,
    )

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

    result = ml_anomaly_detector.save_models(_Connection(), LOCATION_ID)

    artifact = model_dir / f"prophet_{LOCATION_ID[:8]}_soil_moisture.pkl"
    assert result["models_saved"] == ["prophet_soil_moisture"]
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert ml_anomaly_detector.load_models(LOCATION_ID)["prophet"]["soil_moisture"] == {
        "model": "locally generated"
    }


def test_load_models_rejects_symlinked_directory_ancestor(monkeypatch, tmp_path):
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir(mode=0o700)
    model_dir = real_parent / "models"
    model_dir.mkdir(mode=0o700)
    artifact = model_dir / f"iforest_{LOCATION_ID[:8]}.pkl"
    artifact.write_bytes(pickle.dumps({"must_not_load": True}))
    artifact.chmod(0o600)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", linked_parent / "models")

    result = ml_anomaly_detector.load_models(LOCATION_ID)

    assert result["iforest"] is None


def test_load_models_rejects_artifact_replaced_with_symlink_before_open(
    monkeypatch, tmp_path
):
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    artifact = model_dir / f"iforest_{LOCATION_ID[:8]}.pkl"
    artifact.write_bytes(pickle.dumps({"trusted": True}))
    artifact.chmod(0o600)
    attacker_artifact = tmp_path / "attacker.pkl"
    attacker_artifact.write_bytes(pickle.dumps({"attacker": True}))
    attacker_artifact.chmod(0o600)
    monkeypatch.setattr(ml_anomaly_detector, "MODEL_DIR", model_dir)

    real_open = os.open
    swapped = False

    def swap_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == artifact.name and kwargs.get("dir_fd") is not None and not swapped:
            artifact.unlink()
            artifact.symlink_to(attacker_artifact)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(ml_anomaly_detector.os, "open", swap_before_open)

    result = ml_anomaly_detector.load_models(LOCATION_ID)

    assert swapped
    assert result["iforest"] is None
