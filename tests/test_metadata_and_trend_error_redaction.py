"""Keep metadata and trend-analysis failure logs free of private details."""

import logging
import sys
import types
from unittest.mock import MagicMock

from services.metadata_api import anchor
from services.threatcasting.principles import PrincipleManager


def test_batch_metadata_anchor_omits_iri_and_raw_exception(caplog, monkeypatch):
    private_iri = "kokonut:location:private-record:v1"
    sensitive_detail = "rpc=https://private-token.example/rpc /private/key.pem"
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = [
        {"iri": private_iri}
    ]

    def _fail_anchor(*_args, **_kwargs):
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr(anchor, "anchor_metadata", _fail_anchor)
    caplog.set_level(logging.WARNING, logger="kokonut.metadata_api.anchor")

    result = anchor.batch_anchor(conn, "location", "location-123")

    assert result == 0
    assert "Metadata anchor failed (RuntimeError)" in caplog.text
    assert private_iri not in caplog.text
    assert sensitive_detail not in caplog.text


def test_trend_analysis_omits_metric_and_raw_exception(caplog, monkeypatch):
    private_metric = "private-participant-outcome"
    sensitive_detail = "token=private-value /private/model/path"

    class _TrendEstimator:
        def compute_trend_per_metric(self, *_args, **_kwargs):
            raise RuntimeError(sensitive_detail)

    estimator_module = types.ModuleType("services.trends.estimator")
    estimator_module.TrendEstimator = _TrendEstimator
    monkeypatch.setitem(sys.modules, "services.trends.estimator", estimator_module)
    caplog.set_level(logging.WARNING, logger="kokonut.threatcasting.principles")

    result = PrincipleManager()._compute_effectiveness_trend(
        private_metric, "location-123"
    )

    assert result is None
    assert "Trend analysis failed (RuntimeError)" in caplog.text
    assert private_metric not in caplog.text
    assert sensitive_detail not in caplog.text
