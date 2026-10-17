"""Variogram fit results must not include raw model-library diagnostics."""

import gstools

from services.geostatistics.variogram import VariogramAnalyzer


def test_model_fit_failure_returns_only_exception_class(monkeypatch):
    secret = "database password=private-token and confidential coordinate"

    def fail(**_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(gstools, "Exponential", fail)
    empirical = {
        "lags": [1.0, 2.0, 3.0],
        "semivariances": [0.2, 0.5, 0.8],
    }

    result = VariogramAnalyzer(conn=object()).fit_variogram_model(empirical)

    assert result == {"error": "Model fitting failed (RuntimeError)"}
    assert secret not in repr(result)
