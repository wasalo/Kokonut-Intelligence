"""Scenario parameters tests: schema, seeds, params, monte carlo, sensitivity."""

from pathlib import Path

from services.forecast.scenario_params import (
    ScenarioParam,
    apply_params_to_forecast,
    compute_param_summary,
    get_param_value,
    load_scenario_params,
    sample_all_params,
)
from services.forecast.monte_carlo import (
    run_monte_carlo,
    run_sensitivity_analysis,
    run_sensitivity_tornado,
)

SCHEMA = Path("schemas/postgres/060_scenario_parameters.sql")
SEED = Path("schemas/seeds/060_scenario_parameters.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS scenario_parameter" in text
    assert "CREATE TABLE IF NOT EXISTS scenario_simulation" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_public_scenario_parameters" in text
    assert "CREATE OR REPLACE VIEW v_public_simulation_results" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (parameter_category IN" in text
    assert "CHECK (distribution IN" in text
    assert "CHECK (simulation_type IN" in text


def test_schema_has_unique_constraint() -> None:
    text = SCHEMA.read_text()
    assert "UNIQUE (scenario_id, parameter_key)" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_baseline_parameters() -> None:
    text = SEED.read_text()
    assert "loss_rate" in text
    assert "drought_yield_impact" in text
    assert "pest_disease_loss" in text
    assert "maize_price" in text
    assert "fertilizer_cost_inflation" in text
    assert "drought_probability" in text
    assert "carbon_sequestration_rate" in text
    assert "public_goods_allocation_pct" in text
    assert "retention_rate_pct" in text


def test_seed_has_optimistic_parameters() -> None:
    text = SEED.read_text()
    assert "optimistic" in text


def test_seed_has_conservative_parameters() -> None:
    text = SEED.read_text()
    assert "conservative" in text


def test_seed_has_all_categories() -> None:
    text = SEED.read_text()
    assert "'yield'" in text
    assert "'price'" in text
    assert "'cost'" in text
    assert "'weather'" in text
    assert "'ecological'" in text
    assert "'governance'" in text


# ---------------------------------------------------------------------------
# ScenarioParam tests
# ---------------------------------------------------------------------------

def test_scenario_param_sample_triangular() -> None:
    p = ScenarioParam(key="test", category="yield", name="Test", unit="ratio",
                      base_value=0.05, worst_value=0.15, best_value=0.02,
                      distribution="triangular")
    samples = [p.sample() for _ in range(100)]
    assert all(0.02 <= s <= 0.15 for s in samples)
    assert abs(statistics.mean(samples) - 0.05) < 0.03


def test_scenario_param_sample_normal() -> None:
    import statistics
    p = ScenarioParam(key="test", category="price", name="Test", unit="usd",
                      base_value=280, worst_value=200, best_value=350,
                      distribution="normal", std_deviation=30)
    samples = [p.sample() for _ in range(1000)]
    assert abs(statistics.mean(samples) - 280) < 20


def test_scenario_param_worst_best() -> None:
    p = ScenarioParam(key="test", category="yield", name="Test", unit="ratio",
                      base_value=0.05, worst_value=0.15, best_value=0.02)
    assert p.worst_case() == 0.15
    assert p.best_case() == 0.02


def test_scenario_param_range_pct() -> None:
    p = ScenarioParam(key="test", category="yield", name="Test", unit="ratio",
                      base_value=0.05, worst_value=0.15, best_value=0.02)
    assert p.range_pct() == 260.0  # (0.15 - 0.02) / 0.05 * 100


# ---------------------------------------------------------------------------
# Analytics tests (with mock data)
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def execute(self, query, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._single

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows, self._single)


def test_load_scenario_params() -> None:
    rows = [
        ("loss_rate", "yield", "Loss Rate", "ratio", 0.05, 0.15, 0.02, "triangular", 0.03, 0.0, 0.30),
        ("maize_price", "price", "Maize Price", "usd_per_tonne", 280, 200, 350, "normal", 30, 150, 400),
    ]
    params = load_scenario_params(_MockConn(rows=rows), "test-scenario")
    assert len(params) == 2
    assert "loss_rate" in params
    assert "maize_price" in params
    assert params["loss_rate"].base_value == 0.05


def test_get_param_value() -> None:
    params = {
        "loss_rate": ScenarioParam(key="loss_rate", category="yield", name="Loss Rate",
                                   unit="ratio", base_value=0.05, worst_value=0.15, best_value=0.02),
    }
    assert get_param_value(params, "loss_rate", "base") == 0.05
    assert get_param_value(params, "loss_rate", "worst") == 0.15
    assert get_param_value(params, "loss_rate", "best") == 0.02
    assert get_param_value(params, "nonexistent", "base") is None


def test_sample_all_params() -> None:
    params = {
        "loss_rate": ScenarioParam(key="loss_rate", category="yield", name="Loss Rate",
                                   unit="ratio", base_value=0.05, worst_value=0.15, best_value=0.02),
    }
    sampled = sample_all_params(params)
    assert "loss_rate" in sampled
    assert 0.02 <= sampled["loss_rate"] <= 0.15


def test_compute_param_summary() -> None:
    params = {
        "loss_rate": ScenarioParam(key="loss_rate", category="yield", name="Loss Rate",
                                   unit="ratio", base_value=0.05, worst_value=0.15, best_value=0.02),
        "maize_price": ScenarioParam(key="maize_price", category="price", name="Maize Price",
                                     unit="usd", base_value=280, worst_value=200, best_value=350),
    }
    summary = compute_param_summary(params)
    assert summary["total_parameters"] == 2
    assert "yield" in summary["categories"]
    assert "price" in summary["categories"]


def test_apply_params_to_forecast() -> None:
    params = {
        "loss_rate": ScenarioParam(key="loss_rate", category="yield", name="Loss Rate",
                                   unit="ratio", base_value=0.05, worst_value=0.15, best_value=0.02),
        "drought_yield_impact": ScenarioParam(key="drought_yield_impact", category="yield",
                                               name="Drought Impact", unit="ratio",
                                               base_value=0.00, worst_value=0.30, best_value=0.00),
        "fertilizer_cost_inflation": ScenarioParam(key="fertilizer_cost_inflation", category="cost",
                                                    name="Fertilizer Inflation", unit="ratio",
                                                    base_value=0.05, worst_value=0.15, best_value=0.02),
        "public_goods_allocation_pct": ScenarioParam(key="public_goods_allocation_pct", category="governance",
                                                      name="Public Goods", unit="ratio",
                                                      base_value=0.10, worst_value=0.15, best_value=0.05),
    }
    result = apply_params_to_forecast(params, case="base")
    assert "yield_adjustments" in result
    assert "cost_adjustments" in result
    assert "governance" in result
    assert result["yield_adjustments"]["loss_rate"] == 0.05
    assert result["cost_adjustments"]["fertilizer"] == 0.05
    assert result["governance"]["public_goods_allocation_pct"] == 0.10


# ---------------------------------------------------------------------------
# Monte Carlo tests
# ---------------------------------------------------------------------------

def test_monte_carlo_runs() -> None:
    import statistics
    rows = [
        ("loss_rate", "yield", "Loss Rate", "ratio", 0.05, 0.15, 0.02, "triangular", 0.03, 0.0, 0.30),
    ]
    result = run_monte_carlo(_MockConn(rows=rows), "test-scenario",
                             base_noi_usd=9200, base_yield_tonnes=15.0,
                             base_revenue_usd=24500, simulations=100)
    assert result["simulations_count"] == 100
    assert "mean_noi_usd" in result
    assert "p10_noi_usd" in result
    assert "p90_noi_usd" in result
    assert "prob_negative_noi" in result
    assert "execution_time_ms" in result
    assert result["mean_noi_usd"] != 0  # Should vary from base


def test_sensitivity_analysis_runs() -> None:
    rows = [
        ("loss_rate", "yield", "Loss Rate", "ratio", 0.05, 0.15, 0.02, "triangular", 0.03, 0.0, 0.30),
    ]
    result = run_sensitivity_analysis(_MockConn(rows=rows), "test-scenario",
                                      "loss_rate", base_noi_usd=9200,
                                      base_yield_tonnes=15.0, base_revenue_usd=24500,
                                      steps=5)
    assert result["parameter_key"] == "loss_rate"
    assert result["steps"] == 5
    assert len(result["sensitivity_curve"]) == 5
    assert "noi_range_usd" in result
    assert "elasticity" in result


def test_sensitivity_tornado_runs() -> None:
    rows = [
        ("loss_rate", "yield", "Loss Rate", "ratio", 0.05, 0.15, 0.02, "triangular", 0.03, 0.0, 0.30),
        ("maize_price", "price", "Maize Price", "usd", 280, 200, 350, "normal", 30, 150, 400),
    ]
    result = run_sensitivity_tornado(_MockConn(rows=rows), "test-scenario",
                                      base_noi_usd=9200, base_yield_tonnes=15.0,
                                      base_revenue_usd=24500, steps=5)
    assert result["total_parameters"] == 2
    assert len(result["parameters"]) == 2
    # Should be ranked by impact
    assert result["parameters"][0]["rank"] == 1
    assert result["parameters"][1]["rank"] == 2


def test_monte_carlo_no_params() -> None:
    result = run_monte_carlo(_MockConn(rows=[]), "test-scenario",
                             base_noi_usd=9200, base_yield_tonnes=15.0,
                             base_revenue_usd=24500)
    assert "error" in result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import statistics
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_check_constraints()
    test_schema_has_unique_constraint()
    test_schema_has_governed_columns()
    test_seed_has_baseline_parameters()
    test_seed_has_optimistic_parameters()
    test_seed_has_conservative_parameters()
    test_seed_has_all_categories()
    test_scenario_param_sample_triangular()
    test_scenario_param_sample_normal()
    test_scenario_param_worst_best()
    test_scenario_param_range_pct()
    test_load_scenario_params()
    test_get_param_value()
    test_sample_all_params()
    test_compute_param_summary()
    test_apply_params_to_forecast()
    test_monte_carlo_runs()
    test_sensitivity_analysis_runs()
    test_sensitivity_tornado_runs()
    test_monte_carlo_no_params()
    print("All tests passed.")
