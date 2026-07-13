"""Forecast engine unit tests (no database required)."""

from services.forecast.models import (
    PriceAssumptions,
    YieldAssumptions,
    CostAssumptions,
    GrowthAssumptions,
    ScenarioAssumptions,
)
from services.forecast.pricing import project_prices
from services.forecast.risk import calculate_confidence_interval


def test_price_assumptions_defaults():
    pa = PriceAssumptions()
    assert pa.maize_per_tonne_usd == 280.0
    assert pa.beans_per_tonne_usd == 650.0


def test_price_assumptions_from_dict_ignores_unknown_keys():
    pa = PriceAssumptions.from_dict({"maize_per_tonne_usd": 300.0, "unknown": 99})
    assert pa.maize_per_tonne_usd == 300.0
    assert pa.cassava_per_tonne_usd == 180.0


def test_scenario_assumptions_from_dict():
    sa = ScenarioAssumptions.from_dict({"inflation_rate": 0.08, "period": "2026-Q1"})
    assert sa.inflation_rate == 0.08
    assert sa.period == "2026-Q1"


def test_project_prices_applies_growth():
    hist = {"Maize": 200.0, "Beans": 500.0}
    pa = PriceAssumptions(maize_per_tonne_usd=280.0, beans_per_tonne_usd=650.0)
    ga = GrowthAssumptions(price_appreciation_pct=0.10)
    projected = project_prices(hist, pa, ga.price_appreciation_pct)
    assert projected["Maize"] > 200.0
    assert projected["Beans"] > 500.0


def test_yield_and_cost_assumptions_roundtrip():
    ya = YieldAssumptions.from_dict({"maize_yield_tonne_ha": 3.0})
    ca = CostAssumptions.from_dict({"labor_usd_per_ha": 250.0})
    assert ya.maize_yield_tonne_ha == 3.0
    assert ca.labor_usd_per_ha == 250.0


def test_retained_value_computed_after_total_noi():
    """Guard against using total_noi before the crop NOI loop assigns it."""
    import inspect
    from services.forecast.engine import run_forecast

    source = inspect.getsource(run_forecast)
    assert source.index("total_noi = 0.0") < source.index("retained_value = total_noi")


def test_forecast_submission_does_not_publish():
    """Forecast calculation must submit outputs for review, never publish them."""
    import inspect
    from services.forecast import engine

    run_source = inspect.getsource(engine.run_forecast)
    dashboard_source = inspect.getsource(engine._write_dashboard_dataset)
    assert "SET status = 'submitted'" in run_source
    assert "SET status = 'published'" not in run_source
    assert "'draft'" in dashboard_source
    assert "status = 'published'" not in dashboard_source


def test_negative_financial_interval_is_ordered_and_preserves_downside():
    low, high = calculate_confidence_interval(-100.0, 0.8)
    assert low < -100.0 < high


if __name__ == "__main__":
    test_price_assumptions_defaults()
    test_price_assumptions_from_dict_ignores_unknown_keys()
    test_scenario_assumptions_from_dict()
    test_project_prices_applies_growth()
    test_yield_and_cost_assumptions_roundtrip()
    test_retained_value_computed_after_total_noi()
    print("All forecast tests passed ✓")
