"""Fortune 500 calculator unit tests (no database required)."""

from services.fortune500.calculator import (
    FarmMetrics,
    score_financial,
    score_ecological,
    score_governance,
    score_growth,
    calculate_score,
    WEIGHTS,
)


def test_score_financial_high_performer():
    m = FarmMetrics(
        location_id="test",
        revenue_per_ha_usd=1500,
        operating_margin_pct=25,
        loss_rate_pct=5,
    )
    score = score_financial(m)
    assert score >= 800


def test_score_financial_low_performer():
    m = FarmMetrics(
        location_id="test",
        revenue_per_ha_usd=300,
        operating_margin_pct=5,
        loss_rate_pct=40,
    )
    score = score_financial(m)
    assert score < 500


def test_score_ecological_with_data():
    m = FarmMetrics(location_id="test", avg_ndvi=0.6, soil_organic_matter_pct=3.0)
    score = score_ecological(m)
    assert 400 <= score <= 1000


def test_score_governance_verified_activities():
    m = FarmMetrics(
        location_id="test",
        total_activities=10,
        verified_activities=8,
        attestation_count=2,
        data_completeness_pct=80,
    )
    score = score_governance(m)
    assert score > 500


def test_composite_score_weights():
    m = FarmMetrics(
        location_id="test",
        revenue_per_ha_usd=1500,
        operating_margin_pct=25,
        loss_rate_pct=5,
        avg_ndvi=0.6,
        soil_organic_matter_pct=3.0,
        total_activities=10,
        verified_activities=8,
        attestation_count=2,
        data_completeness_pct=80,
        revenue_growth_pct=10,
        yield_growth_pct=5,
    )
    result = calculate_score(m)
    assert 0 <= result.composite_score <= 1000
    assert result.financial_score > 0
    assert result.ecological_score > 0
    assert sum(WEIGHTS.values()) == 1.0


def test_forecast_output_queries_use_calculated_at():
    """forecast_output has calculated_at, not created_at."""
    import inspect
    from services.fortune500.calculator import get_farm_metrics

    source = inspect.getsource(get_farm_metrics)
    assert "ORDER BY calculated_at DESC" in source
    assert "forecast_output" in source
    assert "ORDER BY created_at DESC" not in source


if __name__ == "__main__":
    test_score_financial_high_performer()
    test_score_financial_low_performer()
    test_score_ecological_with_data()
    test_score_governance_verified_activities()
    test_composite_score_weights()
    test_forecast_output_queries_use_calculated_at()
    print("All fortune500 tests passed ✓")
