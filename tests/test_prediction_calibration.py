"""Prediction calibration, outside-view, and probability-resolution tests."""

from pathlib import Path

import pytest

from services.predictions.service import _domain_for_metric, _horizon_bucket
from services.threatcasting.probability import brier_score


def test_brier_score_canonical_cases():
    assert brier_score(0.8, 1) == 0.04
    assert brier_score(0.8, 0) == 0.64
    assert brier_score(0.0, 0) == 0.0
    assert brier_score(1.0, 1) == 0.0


def test_brier_score_rejects_invalid_probability():
    with pytest.raises(ValueError):
        brier_score(float("nan"), 1)
    with pytest.raises(ValueError):
        brier_score(1.1, 1)


def test_prediction_scope_classification():
    assert _domain_for_metric("projected_revenue_usd") == "financial"
    assert _domain_for_metric("total_yield_tonnes") == "yield"
    assert _domain_for_metric("carbon_sequestration_tonnes") == "carbon"
    assert _horizon_bucket(7 * 86400) == "0-7d"
    assert _horizon_bucket(400 * 86400) == "366d+"


def test_prediction_schema_has_governed_ledger_and_publication_gate():
    sql = Path("schemas/postgres/169_prediction_calibration_outside_view.sql").read_text()
    for table in (
        "prediction_ledger", "prediction_outcome", "prediction_evaluation",
        "prediction_calibration_assessment", "reference_class", "outside_view_comparison",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "block_materially_uncalibrated_forecast" in sql
    assert "gate_result = 'fail'" in sql
    assert "selection_rationale TEXT NOT NULL" in sql
    assert "failure_rate" in sql
    assert "sample_size" in sql


def test_delphi_threat_schema_separates_resolution_concepts():
    sql = Path("schemas/postgres/170_delphi_threat_resolution.sql").read_text()
    assert "delphi_diversity_assessment" in sql
    assert "delphi_minority_report" in sql
    assert "time_limit_without_consensus" in sql
    assert "threat_forecast_resolution" in sql
    assert "threat_forecast_score" in sql
    assert "delphi_expert_calibration" in sql


def test_forecast_engine_writes_shared_ledger_atomically():
    source = Path("services/forecast/engine.py").read_text()
    assert "INSERT INTO prediction_ledger" in source
    assert "'forecast_output'" in source


def test_forecast_outcome_matching_is_allowlisted_and_draft_first():
    source = Path("services/predictions/service.py").read_text()
    assert "projected_revenue_usd" in source
    assert "total_yield_tonnes" in source
    assert "status IN ('verified','published')" in source
    assert "'verified_sources',%s,'draft'" in source
    assert "def verify_outcome" in source


def test_crisp_never_selects_highest_benchmark_fallback():
    source = Path("services/crisp/carbon_yield.py").read_text()
    assert "ORDER BY benchmark_co2e_per_ha DESC" not in source
    assert "if not species:" in source
    assert "sequestration_rate_tonnes_co2e_ha_year" in source
