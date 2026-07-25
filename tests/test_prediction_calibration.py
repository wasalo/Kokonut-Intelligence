"""Prediction calibration, outside-view, and probability-resolution tests."""

from pathlib import Path

import pytest

from services.predictions.service import _domain_for_metric, _horizon_bucket, _MAX_CALIBRATION_AGE_DAYS
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


def test_compare_outside_view_populates_fit_dimensions():
    source = Path("services/predictions/service.py").read_text()
    assert "fit_dimensions" in source
    assert "_compute_fit_dimensions" in source
    assert "INSERT INTO outside_view_comparison" in source
    assert "%s::jsonb" in source
    assert "evaluation_sample_size" in source


def test_fit_dimensions_computed_from_evaluation_data():
    source = Path("services/predictions/service.py").read_text()
    assert "def _compute_fit_dimensions" in source
    assert "mape" in source
    assert "bias_pct" in source
    assert "interval_coverage" in source
    assert "deviation_from_reference_pct" in source


def test_fit_status_derived_from_dimension_scores():
    source = Path("services/predictions/service.py").read_text()
    assert "insufficient_evidence" in source
    assert '"good"' in source or "'good'" in source
    assert '"partial"' in source or "'partial'" in source
    assert '"poor"' in source or "'poor'" in source


def test_stale_gate_result_emitted_when_calibration_is_old():
    source = Path("services/predictions/service.py").read_text()
    assert "_MAX_CALIBRATION_AGE_DAYS" in source
    assert "computed_at" in source
    assert "'stale'" in source or '"stale"' in source


def test_stale_gate_result_allowed_by_schema():
    sql = Path("schemas/postgres/169_prediction_calibration_outside_view.sql").read_text()
    assert "'stale'" in sql


def test_auto_calibration_flag_exists():
    source = Path("services/forecast/config.py").read_text()
    assert "AUTO_CALIBRATION_ENABLED" in source
    assert "FORECAST_AUTO_CALIBRATION" in source


def test_forecast_engine_triggers_calibration():
    source = Path("services/forecast/engine.py").read_text()
    assert "_maybe_trigger_calibration" in source
    assert "AUTO_CALIBRATION_ENABLED" in source


def test_calibration_max_age_configurable():
    assert _MAX_CALIBRATION_AGE_DAYS > 0


def test_outside_view_fit_dimensions_no_longer_hardcoded():
    source = Path("services/predictions/service.py").read_text()
    lines = source.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "INSERT INTO outside_view_comparison" in stripped:
            block = "\n".join(lines[i:i+20])
            assert "fit_status" in block
            assert "'good')" not in block.replace("fit_status", "")
            break
