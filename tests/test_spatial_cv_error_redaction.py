from services.geostatistics.cross_validation import SpatialCrossValidator

SECRET = "coordinate payload and database credential"


def _fail_prediction(*_args, **_kwargs):
    raise RuntimeError(SECRET)


def test_spatial_block_cv_redacts_per_fold_errors(monkeypatch):
    validator = SpatialCrossValidator()
    monkeypatch.setattr(validator, "_kriging_predict", _fail_prediction)

    result = validator.spatial_block_cv(
        coordinates=[(0, 0), (300, 0), (0, 300), (300, 300), (600, 0), (600, 300)],
        values=[1, 2, 3, 4, 5, 6],
        variogram_model={"model_type": "exponential", "sill": 1, "range": 10, "nugget": 0},
    )

    assert result["error"] == "No successful folds"
    assert all(
        fold["error"] == "spatial cross-validation fold failed (RuntimeError)"
        for fold in result["fold_results"]
    )
    assert SECRET not in repr(result)


def test_leave_one_out_cv_redacts_per_fold_errors(monkeypatch):
    validator = SpatialCrossValidator()
    monkeypatch.setattr(validator, "_kriging_predict", _fail_prediction)

    result = validator.leave_one_out_cv(
        coordinates=[(0, 0), (1, 0), (0, 1), (1, 1)],
        values=[1, 2, 3, 4],
        variogram_model={"model_type": "exponential", "sill": 1, "range": 10, "nugget": 0},
    )

    assert result["error"] == "No successful folds"
    assert all(
        fold["error"] == "spatial cross-validation fold failed (RuntimeError)"
        for fold in result["fold_results"]
    )
    assert SECRET not in repr(result)
